"""Review: each rule is compared with its source policy, a few rules per request.

The reviewer approves a rule or returns a corrected rule with the same ID; facts,
formats and inventory are out of scope here. A batch still unresolved after its
attempts holds the policy with ``ReviewHeld``, which targeted repair consumes.
Publication requires every final rule approved against its exact final content.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path

from .prompts import DSL_CONTRACT, REVIEW_PROMPT
from .utils import llm
from .utils.contracts import citation_text, digest, validate_package
from .utils.data import read_json, write_json

BATCH_SIZE = 4
ATTEMPTS = 2
FINDING_KEYS = {"rule_id", "status", "quote", "reason", "replacement_rule"}


class ReviewHeld(ValueError):
    """A review batch stayed unresolved; carries the state targeted repair starts from.

    Attributes:
        package: Package with every accepted correction so far.
        findings: Last rejected review feedback.
        selected: Rule IDs the repair may change.
    """

    def __init__(self, package: dict, findings: dict, selected: list[str]):
        """Record the hold state (see class attributes)."""
        super().__init__(f"Verifier-to-policy review held on {selected}")
        self.package, self.findings, self.selected = package, findings, selected


def apply_reviews(package: dict, policy: str, requested: list[str], response) -> tuple[dict, list[dict]]:
    """Apply one batch of reviewer findings.

    Args:
        package: Package under review (not modified).
        policy: Source policy.
        requested: Rule IDs in the batch.
        response: Reviewer JSON ``{"reviews": [...]}``.

    Returns:
        ``(package, records)``: package with same-ID replacements, and hashed findings.

    Raises:
        ValueError: If findings are malformed, uncited, incomplete or break the package.
    """
    if not isinstance(response, dict) or set(response) != {"reviews"} or not isinstance(response["reviews"], list):
        raise ValueError("Expected only a reviews array")
    candidate = deepcopy(package)
    indexed = {rule["id"]: index for index, rule in enumerate(candidate["rules"])}
    if not set(requested) <= set(indexed):
        raise ValueError("Requested verifier is not in this package")
    records, seen = [], set()
    for entry in response["reviews"]:
        if (not isinstance(entry, dict) or set(entry) != FINDING_KEYS
                or entry["rule_id"] not in requested or entry["rule_id"] in seen
                or entry["status"] not in {"approved", "unresolved"}
                or any(not isinstance(entry[key], str) or not entry[key].strip() for key in ("quote", "reason"))
                or citation_text(entry["quote"]) not in citation_text(policy)):
            raise ValueError("Invalid or duplicate verifier-to-policy finding")
        seen.add(entry["rule_id"])
        replacement = entry["replacement_rule"]
        if replacement is not None:
            if entry["status"] != "approved" or not isinstance(replacement, dict) or replacement.get("id") != entry["rule_id"]:
                raise ValueError("Replacement must keep its verifier ID and be approved against the policy")
            candidate["rules"][indexed[entry["rule_id"]]] = deepcopy(replacement)
        final = candidate["rules"][indexed[entry["rule_id"]]]
        records.append({key: entry[key] for key in ("rule_id", "status", "quote", "reason")} | {"rule_sha256": digest(final)})
    if seen != set(requested):
        raise ValueError("Every requested verifier must have exactly one finding")
    validate_package(candidate, policy)
    return candidate, records


def publication_report(package: dict, policy: str, records: list[dict]) -> dict:
    """Summarize a completed review.

    Args:
        package: Final package.
        policy: Source policy.
        records: Findings for every final rule.

    Returns:
        Report whose ``publication_allowed`` is True only if every rule is approved.

    Raises:
        ValueError: If findings do not match the final rules exactly.
    """
    validate_package(package, policy)
    indexed = {rule["id"]: rule for rule in package["rules"]}
    if (sorted(entry["rule_id"] for entry in records) != sorted(indexed)
            or any(entry["rule_sha256"] != digest(indexed[entry["rule_id"]]) for entry in records)):
        raise ValueError("Verifier-to-policy approval does not match the final rules")
    return {"scope": "verifier_to_source_policy_only", "rules_checked": len(records),
            "publication_allowed": all(entry["status"] == "approved" for entry in records),
            "package_sha256": digest(package), "policy_sha256": digest(policy)}


def held_rules(feedback: dict, batch: list[str]) -> list[str]:
    """Rules to repair after a held batch: unresolved ones, else replaced ones, else the whole batch."""
    entries = [entry for entry in ((feedback.get("reply") or {}).get("reviews") or []) if isinstance(entry, dict)]
    for wanted in (lambda entry: entry.get("status") == "unresolved",
                   lambda entry: entry.get("replacement_rule") is not None):
        selected = sorted({entry["rule_id"] for entry in entries if wanted(entry) and entry.get("rule_id") in batch})
        if selected:
            return selected
    return list(batch)


def review_package(policy: str, package: dict, work: Path) -> dict:
    """Review every rule against the policy in batches.

    Args:
        policy: Source policy.
        package: Package to review.
        work: Folder for request records.

    Returns:
        ``{package, reviews, report}`` with every rule approved.

    Raises:
        ReviewHeld: If a batch stays unresolved after its attempts.
    """
    validate_package(package, policy)
    candidate, records = deepcopy(package), []
    for start in range(0, len(candidate["rules"]), BATCH_SIZE):
        requested = [rule["id"] for rule in candidate["rules"][start:start + BATCH_SIZE]]
        feedback = None
        for attempt in range(ATTEMPTS):
            data = {"policy": policy, "verifiers": candidate["rules"][start:start + BATCH_SIZE],
                    "fact_definitions": candidate["variables"], "dsl_and_runtime_contract": DSL_CONTRACT,
                    "previous_feedback": feedback}
            response = None
            try:
                response = llm.chat_json(REVIEW_PROMPT, data, "reviewer", work / f"batch_{start:04d}" / f"attempt_{attempt:02d}")
                updated, findings = apply_reviews(candidate, policy, requested, response)
                candidate = updated
                if any(item["status"] != "approved" for item in findings):
                    raise ValueError("One or more verifier-to-policy comparisons remain unresolved")
            except (ValueError, TypeError, KeyError) as error:
                feedback = {"validation_error": str(error), "reply": response}
            else:
                records.extend(findings)
                break
        else:
            raise ReviewHeld(candidate, feedback, held_rules(feedback, requested))
    report = publication_report(candidate, policy, records)
    return {"package": candidate, "reviews": records, "report": report}


def run(documents: dict[str, dict], source: Path, out: Path, work: Path, concurrency: int = 3) -> dict:
    """Review stage: review each package and repair held ones.

    Args:
        documents: Policy ID to document.
        source: Folder of packages to review.
        out: Folder for accepted packages; acceptance records go to ``out/acceptance``.
        work: Folder for request records.
        concurrency: Policies processed in parallel.

    Returns:
        ``{completed, held}`` where ``held`` maps policy ID to its error.
    """
    from .repair import RepairHeld, repair_policy  # repair re-reviews through this module

    pending = [owner for owner in documents if not (out / f"{owner}.json").exists()]

    def one(owner):
        """Review (and if held, repair) one package; return ``(owner, error or None)``."""
        policy, work_dir = documents[owner]["policy"], work / owner
        try:
            try:
                accepted = review_package(policy, read_json(source / f"{owner}.json"), work_dir)
            except ReviewHeld as held:
                accepted = repair_policy(policy, held, work_dir / "repair")
        except (ValueError, RepairHeld) as error:
            return owner, str(error)
        write_json(out / "acceptance" / f"{owner}.json", accepted)
        write_json(out / f"{owner}.json", accepted["package"])
        return owner, None

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        held = {owner: error for owner, error in pool.map(one, pending) if error}
    return {"completed": len(pending) - len(held), "held": held}
