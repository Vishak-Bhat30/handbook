"""Replay an agent trajectory (agent/trajectory.json only - never verifier output) through a task's verifiers.

Usage: python3 replay.py <task_suffix> <trial_dir> [--quiet]
Prints each write call the pre rules would block, then the completion findings on the replayed ledger.
Workbooks are the initial workspace (the trial's final files are not replayed).
"""
import json
import sys
from pathlib import Path

from iwh import run, setup
import interwhen_sop.sopdata as sd
from interwhen_sop.actions import classify

task, trial = sys.argv[1], Path(sys.argv[2])
setup(task)
sd.load.cache_clear()
steps = json.load(open(trial / "agent" / "trajectory.json"))["steps"]
records = []
for s in steps:
    if s.get("source") == "user" and s.get("message") and not records:
        records.append({"type": "user_message", "text": s["message"]})
    obs = {r.get("source_call_id"): r.get("content", "") for r in ((s.get("observation") or {}).get("results") or [])}
    for tc in s.get("tool_calls") or []:
        tool, args, cid = tc["function_name"], tc.get("arguments") or {}, tc["tool_call_id"]
        a = classify(tool, args)
        if a.is_write:
            findings, errors = run("pre", records, tool, args)
            if findings or errors:
                print(f"[step {s['step_id']}] WOULD BLOCK {tool} {a.channel} {json.dumps(args)[:200]}")
                for f in findings:
                    print("    -", f.problem[:400])
                for e in errors:
                    print("    ! ERR", e)
        records.append({"type": "action", "call_id": cid, "tool": tool, "args": args})
        records.append({"type": "observation", "call_id": cid, "tool": tool, "text": obs.get(cid, "")})
print("== completion")
findings, errors = run("completion", records)
for f in findings:
    print(" -", f.rule, "|", f.problem[:400])
for e in errors:
    print(" ! ERR", e)
