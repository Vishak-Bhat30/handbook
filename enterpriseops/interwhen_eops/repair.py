"""Targeted repair of rules a review left unresolved.

The reviewer edits the package with small JSON patches over stable identifiers
(rules and inventory keyed by id, variables by name). Only the selected rules may
change, response schemas stay host-derived, every removed rule needs a cited
retirement that an independent comparison confirms was unsupported by the policy,
and the whole repaired package is re-reviewed before it can be accepted.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import jsonpatch

from . import review
from .prompts import DSL_CONTRACT, REPAIR_PROMPT, RETIREMENT_PROMPT
from .utils import llm
from .utils.contracts import citation_text, digest, format_schema, validate_package

MAX_PATCH_PAGES = 4
MAX_PATCH_OPERATIONS = 8
FORMAT_ATTEMPTS = 2
REPAIR_CYCLES = 2
COLLECTION_KEYS = {"rules": "id", "inventory": "id", "variables": "name"}
FORMAT_KEYS = {"reviewer": ("decision_key", "issues_key"), "extractor": ("facts_key", "evidence_key")}


class RepairHeld(RuntimeError):
    """Targeted repair could not produce an accepted package within its budget."""


def keyed_package(package: dict) -> dict:
    """Editable view: response schemas removed, collections keyed by stable identifier.

    Raises:
        ValueError: If an identifier repeats.
    """
    candidate = deepcopy(package)
    for kind in FORMAT_KEYS:
        candidate[kind + "_format"].pop("response_schema")
    for collection, key in COLLECTION_KEYS.items():
        entries = candidate[collection]
        candidate[collection] = {entry[key]: entry for entry in entries}
        if len(candidate[collection]) != len(entries):
            raise ValueError("Duplicate package identifier")
    return candidate


def listed_package(candidate: dict) -> dict:
    """Inverse of ``keyed_package`` (response schemas stay removed).

    Raises:
        ValueError: If a key differs from its entry's identifier.
    """
    package = deepcopy(candidate)
    for collection, key in COLLECTION_KEYS.items():
        entries = package[collection]
        if not isinstance(entries, dict) or any(identifier != entry.get(key) for identifier, entry in entries.items()):
            raise ValueError("Package key and entry identifier differ")
        package[collection] = list(entries.values())
    return package


def materialize_package(candidate: dict, original: dict) -> dict:
    """Restore response schemas: the original if its keys/facts are unchanged, else the fixed interface."""
    package = deepcopy(candidate)
    for kind, keys in FORMAT_KEYS.items():
        specification = package[kind + "_format"]
        if "response_schema" in specification:
            raise ValueError("Response schemas are fixed by the host interface")
        unchanged = all(specification.get(key) == original[kind + "_format"].get(key) for key in keys)
        if kind == "extractor":
            unchanged = unchanged and [item["name"] for item in package["variables"]] == \
                [item["name"] for item in original["variables"]]
        specification["response_schema"] = (deepcopy(original[kind + "_format"]["response_schema"]) if unchanged
                                            else format_schema(specification, package["variables"], kind))
    return package


def apply_patch_reply(candidate: dict, reply, policy: str) -> dict:
    """Apply one page of a repair reply to the keyed package.

    Args:
        candidate: Keyed package (not modified).
        reply: ``{"patch": [...], "retirements": [...], "done": bool}``.
        policy: Source policy for retirement quotes.

    Returns:
        The patched keyed package.

    Raises:
        ValueError: If the reply, a patch path or a retirement citation is invalid.
    """
    if (not isinstance(reply, dict) or set(reply) != {"patch", "retirements", "done"}
            or type(reply["done"]) is not bool or not isinstance(reply["patch"], list)
            or len(reply["patch"]) > MAX_PATCH_OPERATIONS or not isinstance(reply["retirements"], list)):
        raise ValueError("Expected a bounded patch, retirement evidence and Boolean done")
    for operation in reply["patch"]:
        if not isinstance(operation, dict):
            raise ValueError("Patch operations must be objects")
        for field in ("path", "from") if operation.get("op") in {"move", "copy"} else ("path",):
            path = operation.get(field)
            if (not isinstance(path, str) or len(path.split("/")) < 3 or path.split("/")[1] not in candidate
                    or "response_schema" in path.split("/")):
                raise ValueError("Patch only package entries or fields, not whole collections or fixed schemas")
    for item in reply["retirements"]:
        if (not isinstance(item, dict) or set(item) != {"rule_id", "quote", "reason"}
                or any(not isinstance(item[key], str) or not item[key].strip() for key in item)
                or citation_text(item["quote"]) not in citation_text(policy)):
            raise ValueError("Rule retirement requires source-cited model evidence")
    try:
        updated = jsonpatch.JsonPatch(reply["patch"]).apply(candidate, in_place=False)
    except (jsonpatch.JsonPatchException, jsonpatch.JsonPointerException) as error:
        raise ValueError("Invalid RFC 6902 patch: " + str(error)) from error
    listed_package(updated)
    return updated


def validate_repair(original: dict, candidate: dict, policy: str, retirements: list[dict], allowed: set[str]) -> dict:
    """Check a finished repair.

    Args:
        original: Package before repair.
        candidate: Repaired keyed package.
        policy: Source policy.
        retirements: Every rule removal with its citation.
        allowed: Rule IDs the repair may change or remove.

    Returns:
        The repaired package with response schemas restored.

    Raises:
        ValueError: If the package is invalid, rules were added or renamed, an unselected rule
            changed, or removals and retirements differ.
    """
    package = materialize_package(listed_package(candidate), original)
    validate_package(package, policy)
    before = {rule["id"]: rule for rule in original["rules"]}
    after = {rule["id"]: rule for rule in package["rules"]}
    if set(after) - set(before):
        raise ValueError("Targeted repair cannot add or rename verifiers")
    removed = set(before) - set(after)
    if not removed | {name for name in after if after[name] != before[name]} <= allowed:
        raise ValueError("Repair changed an unselected verifier")
    retired = [item["rule_id"] for item in retirements]
    if len(retired) != len(set(retired)) or set(retired) != removed:
        raise ValueError("Every removed verifier needs exactly one retirement justification")
    return package


def request_checked(prompt: str, data: dict, validator, work: Path):
    """Reviewer request retried once with validation feedback.

    Args:
        prompt: System prompt.
        data: Request content.
        validator: Raises ValueError for an unacceptable reply.
        work: Folder for request records.

    Returns:
        The first reply that passes ``validator``.

    Raises:
        RepairHeld: If no reply passes.
    """
    feedback = None
    for attempt in range(FORMAT_ATTEMPTS):
        response = None
        try:
            response = llm.chat_json(prompt, {**data, "validation_feedback": feedback}, "reviewer",
                                     work / f"attempt_{attempt:02d}")
            validator(response)
            return response
        except (ValueError, TypeError, KeyError) as error:
            feedback = {"validation_error": str(error), "reply": response}
    raise RepairHeld(f"Repair response contract remained invalid: {work}")


def repair_package(policy, original, current, findings, allowed, retired, work):
    """Patch the package page by page until the reviewer reports done.

    Args:
        policy: Source policy.
        original: Package before repair.
        current: Package to continue from.
        findings: Review findings to address.
        allowed: Rule IDs the repair may change or remove.
        retired: Retirements carried from earlier cycles.
        work: Folder for request records.

    Returns:
        ``(package, retirements)`` after a validated repair.

    Raises:
        RepairHeld: If the page or format budget is exhausted.
    """
    candidate, retired = keyed_package(current), deepcopy(retired)
    for page in range(MAX_PATCH_PAGES):
        def check(reply):
            """Accept a page only if it applies, and validates fully when marked done."""
            updated = apply_patch_reply(candidate, reply, policy)
            if reply["done"]:
                validate_repair(original, updated, policy, retired + reply["retirements"], allowed)

        response = request_checked(REPAIR_PROMPT, {
            "policy": policy, "package": candidate, "findings": findings, "selected_rules": sorted(allowed),
            "original_selected_rules": [rule for rule in original["rules"] if rule["id"] in allowed],
            "previous_retirements": retired, "dsl_and_runtime_contract": DSL_CONTRACT,
            "pages_remaining": MAX_PATCH_PAGES - page}, check, work / f"page_{page:02d}")
        candidate = apply_patch_reply(candidate, response, policy)
        retired.extend(response["retirements"])
        if response["done"]:
            return validate_repair(original, candidate, policy, retired, allowed), retired
    raise RepairHeld("Stable-ID repair patch budget exhausted")


def validate_retirements(original: dict, final: dict, policy: str, records: list[dict]) -> None:
    """Check that every removed rule was independently judged unsupported by the policy.

    Raises:
        ValueError: If a removal lacks an ``unsupported`` comparison or a record is invalid.
    """
    before = {rule["id"]: rule for rule in original["rules"]}
    removed = set(before) - {rule["id"] for rule in final["rules"]}
    seen = set()
    for item in records:
        if (not isinstance(item, dict) or set(item) != {"rule_id", "status", "quote", "reason", "original_rule_sha256"}
                or item["rule_id"] not in removed or item["rule_id"] in seen or item["status"] != "unsupported"
                or item["original_rule_sha256"] != digest(before[item["rule_id"]])
                or any(not isinstance(item[key], str) or not item[key].strip() for key in ("quote", "reason"))
                or citation_text(item["quote"]) not in citation_text(policy)):
            raise ValueError("Retired verifier is not approved as unsupported by the source")
        seen.add(item["rule_id"])
    if seen != removed:
        raise ValueError("Missing policy comparison for a retired verifier")


def compare_retirements(policy, original, final, reasons, work) -> list[dict]:
    """Ask the reviewer whether each removed rule was unsupported by the policy.

    Args:
        policy: Source policy.
        original: Package before repair.
        final: Repaired package.
        reasons: Retirement justifications from the repair.
        work: Folder for request records.

    Returns:
        One validated comparison record per removed rule.

    Raises:
        RepairHeld: If no acceptable comparison is returned.
    """
    before = {rule["id"]: rule for rule in original["rules"]}
    removed = set(before) - {rule["id"] for rule in final["rules"]}
    if not removed:
        return []

    def records(reply):
        """Comparison records bound to the original rule hashes."""
        if not isinstance(reply, dict) or set(reply) != {"retirements"} or not isinstance(reply["retirements"], list):
            raise ValueError("Expected a retirement comparison array")
        return [{**item, "original_rule_sha256": digest(before[item["rule_id"]])} for item in reply["retirements"]]

    reply = request_checked(RETIREMENT_PROMPT, {
        "policy": policy, "retired_verifiers": [before[name] for name in sorted(removed)],
        "fact_definitions": original["variables"], "retirement_reasons": reasons,
        "dsl_and_runtime_contract": DSL_CONTRACT},
        lambda value: validate_retirements(original, final, policy, records(value)), work)
    return records(reply)


def repair_policy(policy: str, held: review.ReviewHeld, work: Path) -> dict:
    """Repair a held review and re-review the whole package.

    Args:
        policy: Source policy.
        held: The review hold to repair.
        work: Folder for request records.

    Returns:
        The accepted ``review_package`` result plus ``targeted_repair`` provenance.

    Raises:
        RepairHeld: If no cycle yields an accepted package.
    """
    original, current, retired = held.package, deepcopy(held.package), []
    findings, selected = held.findings, set(held.selected)
    for cycle in range(REPAIR_CYCLES):
        location = work / f"cycle_{cycle:02d}"
        try:
            current, retired = repair_package(policy, original, current, findings, selected, retired, location)
            removals = compare_retirements(policy, original, current, retired, location / "retired")
            accepted = review.review_package(policy, current, location / "review")
            validate_retirements(original, accepted["package"], policy, removals)
        except (RepairHeld, ValueError) as error:
            latest = {"validation_error": str(error)}
            if isinstance(error, review.ReviewHeld):
                latest["comparison"] = error.findings
                selected.update(error.selected)
            findings = {"previous": findings, "latest": latest}
            continue
        accepted["targeted_repair"] = {"input_package_sha256": digest(original), "retirements": removals,
                                       "repair_cycle": cycle}
        return accepted
    raise RepairHeld("Targeted repair remained unresolved")
