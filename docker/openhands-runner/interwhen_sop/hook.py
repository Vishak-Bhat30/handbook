"""OpenHands command-hook entry point.

    python -m interwhen_sop.hook pre    # PreToolUse  (stdin: HookEvent JSON)
    python -m interwhen_sop.hook prompt # UserPromptSubmit (SOP checklist, INTERWHEN_CHECKLIST=1)
    python -m interwhen_sop.hook stop   # Stop

Prints {"decision": "allow"|"deny", "reason": ...} on stdout and always exits 0,
so an internal error falls open instead of blocking the agent.
"""

from __future__ import annotations

import json
import sys
import traceback

from . import config, engine, framework, sopdata


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "pre"
    try:
        event = json.loads(sys.stdin.read() or "{}")
        if not (sopdata.available() and framework.has_verifiers(config.task_id())):
            out = {"decision": "allow"}
        elif mode == "pre":
            out = engine.pre_tool(event.get("tool_name") or "", event.get("tool_input") or {})
        elif mode == "prompt":
            out = engine.checklist()
        else:
            out = engine.completion("stop_hook")
    except Exception:
        config.write_shared(config.state_dir() / "hook_errors.log",
                            f"--- {mode}\n{traceback.format_exc()}\n", append=True)
        out = {"decision": "allow"}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
