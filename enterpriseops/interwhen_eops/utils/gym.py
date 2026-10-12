"""Bridge to an unmodified EnterpriseOps-Gym checkout (``ENTERPRISEOPS_REPO``).

``load_evaluate`` imports the gym's ``evaluate`` module and installs the runtime
adapters that define the evaluated configuration, so the checkout stays pristine:

* numeric-sql-v2 scoring: a SQL number compared with a numeric string compares as a
  number (upstream compares ``3 == "3"`` as False);
* teams-source-v2 tools: the documented ``create_call`` source identity schema;
* agent LLM config supplied in memory (the API key is never written to disk).

``task_payload`` also strips padded context keys (illegal as HTTP headers) and
prefixes verifier names with their index so same-named checks are not overwritten.
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from pathlib import Path

from . import config
from ..guard import make_orchestrator

NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z")
CALL_SOURCE_DESCRIPTION = (
    "Optional source participant. Supports identity.user (id, displayName, tenantId) "
    "or identity.applicationInstance. Explicit source identity is preserved by the simulator; "
    "omitting source leaves it unset. This does not change API authentication or permissions.")


def compare_values(actual, expected, comparison_type: str) -> dict:
    """Compare a SQL result with its expected value (numeric-sql-v2).

    Args:
        actual: Value returned by the verifier query.
        expected: Expected value from the task.
        comparison_type: ``equals``, ``greater_than``, ``less_than`` or ``contains``.

    Returns:
        ``{passed, details}`` as produced by the upstream verifier.
    """
    left, right, normalized = actual, expected, False
    if (comparison_type in {"equals", "greater_than", "less_than"} and type(actual) in (int, float)
            and (type(actual) is int or math.isfinite(actual)) and isinstance(expected, str) and NUMBER.fullmatch(expected)):
        try:
            left, right = Decimal(str(actual)), Decimal(expected)
            normalized = left.is_finite() and right.is_finite()
        except InvalidOperation:
            normalized = False
        if not normalized:
            left, right = actual, expected
    try:
        if comparison_type == "equals":
            passed = left == right
        elif comparison_type == "greater_than":
            passed = left > right
        elif comparison_type == "less_than":
            passed = left < right
        elif comparison_type == "contains":
            passed = expected in str(actual)
        else:
            return {"passed": False, "details": f"Unknown comparison type: {comparison_type}"}
        return {"passed": bool(passed), "details": f"Comparison {comparison_type}: {actual} vs {expected}"}
    except Exception as error:  # noqa: BLE001 - mirrors upstream comparison semantics
        return {"passed": False, "details": f"Comparison error: {error}"}


def tool_catalog(tools: list[dict]) -> list[dict]:
    """Apply the teams-source-v2 ``create_call`` schema correction.

    Args:
        tools: Tool list from an MCP server.

    Returns:
        A corrected copy; other tools are unchanged.

    Raises:
        ValueError: If the upstream ``create_call`` source schema is not the one corrected.
    """
    corrected = deepcopy(tools)
    for tool in corrected:
        if tool.get("name") != "create_call":
            continue
        source = tool["inputSchema"]["properties"]["source"]
        identities = source["properties"]["identity"]["properties"]
        user = {"type": "object", "properties": {
            "id": {"type": "string"}, "displayName": {"type": "string"}, "tenantId": {"type": "string"}}}
        if "applicationInstance" not in identities or ("user" in identities and identities["user"] != user):
            raise ValueError("Upstream call source schema changed; review the contract correction")
        identities["user"] = user
        source["description"] = CALL_SOURCE_DESCRIPTION
    return corrected


def task_payload(task: dict) -> dict:
    """Gym benchmark config for a dataset task.

    Args:
        task: Dataset task row.

    Returns:
        One-run config with stripped context keys and index-prefixed verifier names.
    """
    payload = deepcopy({key: value for key, value in task.items() if key not in {"task_id", "domain"}})
    for key in ("gym_servers_config", "verifiers"):
        if isinstance(payload.get(key), str):
            payload[key] = json.loads(payload[key])
    gyms = payload["gym_servers_config"]
    for gym in gyms if isinstance(gyms, list) else [gyms]:
        if isinstance(gym.get("context"), dict):
            gym["context"] = {key.strip(): value for key, value in gym["context"].items()}
    for index, verifier in enumerate(payload["verifiers"]):
        verifier["name"] = f"{index + 1:02d}_{verifier.get('name') or f'verifier_{index + 1}'}"
    payload.update(number_of_runs=1, reset_database_between_runs=True)
    return payload


def agent_config(redact: bool = False) -> dict:
    """Agent LLM config in the gym's ``LLMConfig`` fields.

    Args:
        redact: Replace the API key, for manifests.
    """
    return {**config.AGENT_SETTINGS, "llm_model": config.model("agent"), "llm_api_endpoint": config.endpoint(),
            "llm_api_key": "<redacted>" if redact else config.api_key()}


def load_evaluate(packages: dict[str, dict] | None = None):
    """Import the gym's ``evaluate`` module with the runtime adapters installed.

    Args:
        packages: Reviewed packages; if given, registers the ``interwhen`` orchestrator.

    Returns:
        The gym's ``evaluate`` module.
    """
    repo = config.gym_repo()
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    os.chdir(repo)
    import evaluate
    from benchmark.mcp_client import MCPClient
    from benchmark.models import LLMConfig
    from benchmark.verifier import VerifierEngine

    if not getattr(MCPClient.list_tools, "_interwhen_adapter", False):
        upstream_list_tools = MCPClient.list_tools

        async def list_tools(self):
            """Upstream tool list with the contract correction applied."""
            return tool_catalog(await upstream_list_tools(self))

        list_tools._interwhen_adapter = True
        MCPClient.list_tools = list_tools
    VerifierEngine._compare_values = lambda self, actual, expected, kind: compare_values(actual, expected, kind)
    evaluate.load_llm_configs = lambda _path: [LLMConfig(**agent_config())]
    if packages is not None:
        evaluate.ORCHESTRATOR_MAP["interwhen"] = make_orchestrator(evaluate.ORCHESTRATOR_MAP["react"], packages)
    return evaluate


async def run_task(evaluate, task: dict, arm: str, folder: Path) -> Path:
    """Run one task once; the gym skips tasks whose result file already exists.

    Args:
        evaluate: Module from ``load_evaluate``.
        task: Dataset task row.
        arm: ``"baseline"`` (ReAct) or ``"interwhen"``.
        folder: Arm output folder.

    Returns:
        Path of the task's result file.
    """
    payload_path = folder / "payloads" / f"{task['task_id']}.json"
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload_path.write_text(json.dumps(task_payload(task), indent=2), encoding="utf-8")
    await evaluate.execute_sample(str(payload_path), "in-memory", str(folder),
                                  orchestrator="react" if arm == "baseline" else "interwhen", max_num_attempts=1)
    return folder / f"results_{task['task_id']}.json"
