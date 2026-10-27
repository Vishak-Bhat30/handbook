"""Decision engine: run verifiers for a hook event and format steering feedback."""

from __future__ import annotations

import json
import time

from . import config, framework, ledger, sopdata, state
from .actions import classify


def _feedback(kind: str, findings: list[framework.Finding]) -> str:
    head = ("SOP CHECK (interwhen): this tool call was BLOCKED before execution - nothing was changed."
            if kind == "pre" else
            "SOP CHECK (interwhen): the task is not complete yet per the SOP.")
    parts = [head, "", "Problems:"]
    for i, f in enumerate(findings, 1):
        parts.append(f"{i}. {f.problem}")
        for ref in f.refs:
            parts.append(f"   - {ref}")
    fixes = [x for f in findings for x in f.fix]
    if fixes:
        parts += ["", "What to do instead:"] + [f"- {x}" for x in dict.fromkeys(fixes)]
    return "\n".join(parts)


def _log(entry: dict) -> None:
    config.write_shared(config.state_dir() / "decisions.jsonl",
                        json.dumps(entry, ensure_ascii=False, default=str) + "\n", append=True)


def _context() -> framework.Context:
    return framework.Context(sopdata.load(), state.build(ledger.read()), [])


def _rules() -> list[framework.Rule]:
    return framework.load_rules(config.task_id())


def pre_tool(tool: str, tool_input: dict) -> dict:
    t0 = time.time()
    args = tool_input.get("data") if isinstance(tool_input.get("data"), dict) else tool_input
    if tool == "finish":
        return completion("finish_tool")
    action = classify(tool, args)
    if not action.is_write:
        _log({"stage": "pre", "tool": tool, "kind": action.kind, "decision": "allow", "fast": True})
        return {"decision": "allow"}
    ctx = _context()
    findings, errors = framework.run(_rules(), "pre", ctx, action)
    decision = "deny" if findings else "allow"
    _log({"stage": "pre", "tool": tool, "kind": action.kind, "files": action.files_written,
          "decision": decision, "findings": [f.__dict__ for f in findings], "errors": errors,
          "slm": ctx.log, "secs": round(time.time() - t0, 2)})
    if decision == "allow":
        return {"decision": "allow"}
    text = _feedback("pre", findings)
    return {"decision": "deny", "reason": text}


def completion(trigger: str) -> dict:
    t0 = time.time()
    counter = config.state_dir() / "completion_denials.json"
    hist = json.loads(counter.read_text()) if counter.exists() else []
    hist = hist if isinstance(hist, list) else [None] * int(hist)
    denials = len(hist)
    ctx = _context()
    findings, errors = framework.run(_rules(), "completion", ctx)
    # Keep refusing while the agent is still closing findings; give up after a few refusals without progress.
    stale, best = 0, None
    for n in [x for x in hist if x is not None] + [len(findings)]:
        best, stale = (n, 0) if best is None or n < best else (best, stale + 1)
    exhausted = bool(findings) and (denials >= config.MAX_COMPLETION_DENIALS or stale >= config.MAX_STALE_DENIALS)
    decision = "deny" if findings and not exhausted else "allow"
    _log({"stage": "completion", "trigger": trigger, "decision": decision, "budget_exhausted": exhausted,
          "denials_before": denials, "stale": stale, "findings": [f.__dict__ for f in findings], "errors": errors,
          "slm": ctx.log, "secs": round(time.time() - t0, 2)})
    if decision == "allow":
        return {"decision": "allow"}
    config.write_shared(counter, json.dumps(hist + [len(findings)]))
    text = _feedback("completion", findings)
    return {"decision": "deny", "reason": text, "additionalContext": text}


def checklist() -> dict:
    """UserPromptSubmit: list the SOP obligations still open on the initial state (algo.md Step 5)."""
    marker = config.state_dir() / "checklist.txt"
    if not config.CHECKLIST or marker.exists():
        return {"decision": "allow"}
    ctx = _context()
    findings, errors = framework.run(_rules(), "completion", ctx)
    lines = ["SOP CHECKLIST (interwhen): per the SOP and the files/messages in this task, the following must be "
             "done before you finish. Verify each against the SOP while you work; completion is checked."]
    lines += [f"{i}. {f.problem}" for i, f in enumerate(findings, 1)]
    text = "\n".join(lines) if findings else ""
    config.write_shared(marker, text)
    _log({"stage": "checklist", "items": len(findings), "errors": errors, "slm": ctx.log})
    return {"decision": "allow", **({"additionalContext": text} if text else {})}
