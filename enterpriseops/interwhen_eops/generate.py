"""Generation: the creator model drafts each policy's package, validated locally.

A draft that fails validation is fixed with small JSON patches against the reported
error; if the patch budget runs out the creator retries with the error as feedback.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path

import jsonpatch

from .prompts import CREATOR_PROMPT, DSL_CONTRACT, FORMAT_SPEC, GENERATION_PATCH_PROMPT
from .utils import llm
from .utils.contracts import validate_package
from .utils.data import write_json

ATTEMPTS = 2
PATCH_ATTEMPTS = 3


def apply_patch(package: dict, reply) -> dict:
    """Apply a creator patch reply.

    Args:
        package: Package to patch (not modified).
        reply: ``{"patch": [RFC 6902 operations], "reason": str}``.

    Returns:
        The patched package.

    Raises:
        ValueError: If the reply or patch is invalid.
    """
    if (not isinstance(reply, dict) or set(reply) != {"patch", "reason"} or not isinstance(reply["patch"], list)
            or not isinstance(reply["reason"], str) or not reply["reason"].strip()):
        raise ValueError("Patch reply must contain patch array and nonempty reason only")
    try:
        candidate = jsonpatch.JsonPatch(reply["patch"]).apply(deepcopy(package), in_place=False)
    except (jsonpatch.JsonPatchException, jsonpatch.JsonPointerException, TypeError, KeyError) as error:
        raise ValueError("Invalid RFC 6902 patch: " + str(error)) from error
    if not isinstance(candidate, dict):
        raise ValueError("Patched package must remain an object")
    return candidate


def patch_package(policy: str, package: dict, error: str, work: Path) -> dict | None:
    """Fix an invalid draft with bounded JSON-patch requests.

    Args:
        policy: Source policy.
        package: Invalid draft.
        error: Its validation error.
        work: Folder for request records.

    Returns:
        A valid package, or None if the patch budget is exhausted.
    """
    failure = None
    for attempt in range(PATCH_ATTEMPTS):
        data = {"policy": policy, "package": package, "package_contract": FORMAT_SPEC,
                "dsl_and_runtime_contract": DSL_CONTRACT, "validation_error": error}
        if failure:
            data["previous_patch_failure"] = failure
        candidate = None
        try:
            candidate = apply_patch(package, llm.chat_json(GENERATION_PATCH_PROMPT, data, "creator",
                                                           work / f"patch_{attempt:02d}"))
            validate_package(candidate, policy)
            return candidate
        except (ValueError, TypeError, KeyError) as exc:
            failure = {"validation_error": str(exc)}
            if candidate is not None:
                package, error = candidate, str(exc)
    return None


def generate_package(document: dict, work: Path) -> dict:
    """Draft a valid package for one policy.

    Args:
        document: Entry from ``policy_documents``.
        work: Folder for request records.

    Returns:
        A package that passes ``validate_package``.

    Raises:
        ValueError: If no valid package results within the attempt budget.
    """
    policy = document["policy"]
    # Demonstration collection is not part of this pipeline; the creator contract still names the field.
    data = {"policy": policy, "tool_names": document["tools"], "training_examples": []}
    for attempt in range(ATTEMPTS):
        package = None
        try:
            package = llm.chat_json(CREATOR_PROMPT, data, "creator", work / f"create_{attempt:02d}")
            validate_package(package, policy)
            return package
        except (ValueError, TypeError, KeyError) as error:
            if isinstance(package, dict):
                fixed = patch_package(policy, package, str(error), work / f"create_{attempt:02d}")
                if fixed is not None:
                    return fixed
            data = {**data, "previous_package": package, "validation_error": str(error)}
    raise ValueError("Creator package still invalid after bounded attempts")


def run(documents: dict[str, dict], out: Path, work: Path, concurrency: int = 3) -> dict:
    """Generation stage: draft a package for every policy without one in ``out``.

    Args:
        documents: Policy ID to document.
        out: Folder for ``<policy_id>.json`` packages.
        work: Folder for request records.
        concurrency: Policies processed in parallel.

    Returns:
        ``{completed, held}`` where ``held`` maps policy ID to its error.
    """
    pending = [owner for owner in documents if not (out / f"{owner}.json").exists()]

    def one(owner):
        """Generate and save one package; return ``(owner, error or None)``."""
        try:
            write_json(out / f"{owner}.json", generate_package(documents[owner], work / owner))
        except ValueError as error:
            return owner, str(error)
        return owner, None

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        held = {owner: error for owner, error in pool.map(one, pending) if error}
    return {"completed": len(pending) - len(held), "held": held}
