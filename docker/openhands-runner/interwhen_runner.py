"""Interwhen variant of the in-container OpenHands runner.

Wraps the unchanged baseline ``openhands_runner.run`` and adds:
- a ledger callback that mirrors every conversation event to /logs/agent/interwhen/ledger.jsonl
- PreToolUse + Stop command hooks running ``interwhen_sop.hook`` (SOP verifiers)
- a workbook snapshot at session start for record-integrity checks

Same CLI contract as the baseline runner: argv[1]=config JSON, argv[2]=result JSON.
The config's ``interwhen`` object carries {task, slmUrl, maxCompletionDenials}.
"""

from __future__ import annotations

import json
import os
import shlex
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import openhands_runner as base  # noqa: E402


def _configure(cfg: dict) -> None:
    iw = cfg.get("interwhen") or {}
    os.environ["INTERWHEN_TASK"] = iw.get("task", "")
    os.environ["INTERWHEN_STATE_DIR"] = os.path.join(cfg.get("logDir") or "/logs/agent", "interwhen")
    if iw.get("slmUrl"):
        os.environ["INTERWHEN_SLM_URL"] = iw["slmUrl"]
    if iw.get("maxCompletionDenials") is not None:
        os.environ["INTERWHEN_MAX_COMPLETION_DENIALS"] = str(iw["maxCompletionDenials"])
    if iw.get("maxStaleDenials") is not None:
        os.environ["INTERWHEN_MAX_STALE_DENIALS"] = str(iw["maxStaleDenials"])
    os.environ["INTERWHEN_CHECKLIST"] = "1" if iw.get("checklist") else "0"


def _install_hooks() -> dict:
    import openhands.sdk as sdk
    from openhands.sdk.hooks import HookConfig, HookDefinition, HookMatcher

    from interwhen_sop import config, framework, ledger, slm, sopdata, workbooks

    info = {"task": config.task_id(), "sop_available": sopdata.available(),
            "verifier_module": framework.verifier_module(config.task_id()),
            "verifiers_available": framework.has_verifiers(config.task_id()),
            "slm_model": slm.model_name(), "slm_url": config.slm_url(),
            "snapshot": workbooks.snapshot()}
    config.write_shared(config.state_dir() / "session.json", json.dumps(info, indent=2))
    base._log(f"interwhen: {info}")
    if not (info["sop_available"] and info["verifiers_available"]):
        base._log("interwhen: no SOP data or verifier module for this task; running without hooks")
        return info

    cmd = f"PYTHONPATH={shlex.quote(HERE)} {shlex.quote(sys.executable)} -m interwhen_sop.hook"
    hooks = HookConfig(
        pre_tool_use=[HookMatcher(matcher="*", hooks=[HookDefinition(command=f"{cmd} pre", timeout=240)])],
        stop=[HookMatcher(matcher="*", hooks=[HookDefinition(command=f"{cmd} stop", timeout=240)])],
        user_prompt_submit=([HookMatcher(matcher="*", hooks=[HookDefinition(command=f"{cmd} prompt", timeout=240)])]
                            if config.CHECKLIST else []),
    )

    def record(event) -> None:
        try:
            ledger.record_event(event)
        except Exception as exc:  # the ledger must never break the agent loop
            base._log(f"interwhen ledger error: {exc}")

    original = sdk.Conversation

    def conversation_with_hooks(*args, **kwargs):
        kwargs["hook_config"] = hooks
        kwargs["callbacks"] = [record, *(kwargs.get("callbacks") or [])]
        return original(*args, **kwargs)

    # base.run() imports Conversation from openhands.sdk at call time.
    sdk.Conversation = conversation_with_hooks
    return info


def _summary() -> dict:
    from interwhen_sop import config

    path = config.state_dir() / "decisions.jsonl"
    rows = [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()] if path.exists() else []
    denied = [r for r in rows if r.get("decision") == "deny"]
    return {
        "pre_tool_checks": sum(r.get("stage") == "pre" for r in rows),
        "pre_tool_denials": sum(r.get("stage") == "pre" for r in denied),
        "completion_checks": sum(r.get("stage") == "completion" for r in rows),
        "completion_denials": sum(r.get("stage") == "completion" for r in denied),
        "rules_fired": sorted({f["rule"] for r in denied for f in r.get("findings", [])}),
    }


def main() -> None:
    if len(sys.argv) != 3:
        base._log("usage: interwhen_runner.py <config.json> <output.json>")
        sys.exit(2)
    config_path, output_path = sys.argv[1], sys.argv[2]
    cfg = json.loads(open(config_path).read())
    _configure(cfg)
    try:
        info = _install_hooks()
        result = base.run(cfg)
        result["interwhen"] = {**info, **_summary()}
    except Exception as e:
        result = {
            "agent_id": "openhands_sdk", "model": cfg.get("model"),
            "agent": {"model_name": cfg.get("model")}, "steps": [], "final_output": "",
            "n_tool_calls": 0, "stopped_reason": "error", "error_message": str(e),
            "input_tokens": None, "output_tokens": None, "cache_tokens": None, "cost_usd": None,
        }
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)
    base._log(f"wrote trajectory to {output_path} (stopped_reason={result.get('stopped_reason')}, "
              f"interwhen={result.get('interwhen')})")


if __name__ == "__main__":
    main()
