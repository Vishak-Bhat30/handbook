"""Replay a Harbor trajectory.json through the interwhen engine (offline, no agent).

    INTERWHEN_SLM_URL=http://127.0.0.1:8000/v1 python -m interwhen_sop.tests.replay_trace \
        <trajectory.json> --task logistics_gear_sytems_inc_9b60992d --workdir <initial_workspace>

Each recorded tool call is evaluated by the PreToolUse engine with the ledger as it
would have been at that point. Blocked calls are recorded as rejections (their
recorded observation is dropped), so later decisions see the counterfactual state.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path


def _apply(tool: str, args: dict, workdir: Path) -> str:
    """Re-execute an allowed write so later checks see its effect (container-only)."""
    import subprocess

    if tool == "syntara__writeFile":
        p = Path(args["file_path"])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(args.get("content", ""))
        return json.dumps({"success": True})
    if tool == "syntara__executePython":
        cmd = [os.environ.get("INTERWHEN_XLSX_PYTHON", "/app/.venv/bin/python"), "-c", args.get("code", "")]
    else:
        cmd = ["bash", "-c", args.get("command", "")]
    env = {**os.environ, "PATH": f"{Path(os.environ.get('INTERWHEN_XLSX_PYTHON', '/app/.venv/bin/python')).parent}:"
           f"{os.environ.get('PATH', '')}"}
    proc = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, timeout=120, env=env)
    return json.dumps({"stdout": proc.stdout[-2000:], "stderr": proc.stderr[-1000:], "returncode": proc.returncode})


def replay(traj_path: Path, task: str, workdir: Path, state_dir: Path, verbose: bool = True,
           apply_writes: bool = False) -> list[dict]:
    if apply_writes and str(workdir) != "/workdir":
        raise SystemExit("--apply-writes runs trace code; use it only inside a container with /workdir")
    os.environ["INTERWHEN_TASK"] = task
    os.environ["INTERWHEN_STATE_DIR"] = str(state_dir)
    os.environ["INTERWHEN_WORKDIR"] = str(workdir)
    from interwhen_sop import engine, ledger, workbooks

    workbooks.snapshot()
    traj = json.loads(traj_path.read_text())
    repo = Path(os.environ.get("INTERWHEN_REPO") or Path(__file__).resolve().parents[4])
    ledger.append({"type": "user_message", "text": (repo / "tasks" / task / "instruction.md").read_text()})

    results = []
    for step in traj.get("steps", []):
        for call in step.get("tool_calls") or []:
            tool, args = call["function_name"], call.get("arguments") or {}
            tool_input = {"message": args.get("message", "")} if tool == "finish" else {"data": args}
            out = engine.pre_tool(tool, tool_input)
            cid = call.get("tool_call_id")
            ledger.append({"type": "action", "id": cid, "call_id": cid, "tool": tool, "args": args})
            if out["decision"] == "deny":
                ledger.append({"type": "rejection", "call_id": cid, "tool": tool, "text": out.get("reason", "")})
            else:
                from interwhen_sop.actions import classify

                kind = classify(tool, args).kind
                results_ = (step.get("observation") or {}).get("results") or []
                if apply_writes and kind in ("workbook_write", "file_write"):
                    results_ = [{"content": f"[Tool '{tool}' executed.]" + _apply(tool, args, workdir)}]
                for res in results_:
                    ledger.append({"type": "observation", "call_id": cid, "tool": tool, "text": res.get("content", "")})
            row = {"tool": tool, "decision": out["decision"],
                   "summary": json.dumps(args, ensure_ascii=False)[:140],
                   "reason": out.get("reason", "")}
            results.append(row)
            if verbose:
                mark = "DENY " if out["decision"] == "deny" else "allow"
                print(f"{mark} {tool:34s} {row['summary'][:110]}")
    final = engine.completion("replay_end")
    results.append({"tool": "<completion>", "decision": final["decision"], "reason": final.get("reason", "")})
    if verbose:
        print(f"{'DENY ' if final['decision'] == 'deny' else 'allow'} <completion>")
    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("trajectory", type=Path)
    ap.add_argument("--task", required=True)
    ap.add_argument("--workdir", type=Path, required=True)
    ap.add_argument("--state-dir", type=Path)
    ap.add_argument("--show-reasons", action="store_true")
    ap.add_argument("--apply-writes", action="store_true")
    a = ap.parse_args()
    state_dir = a.state_dir or Path(tempfile.mkdtemp(prefix="interwhen-replay-"))
    res = replay(a.trajectory, a.task, a.workdir, state_dir, apply_writes=a.apply_writes)
    if a.show_reasons:
        for r in res:
            if r["decision"] == "deny":
                print("\n" + "=" * 100 + f"\n{r['tool']}\n{r['reason']}")
    print(f"\nstate dir: {state_dir}")


if __name__ == "__main__":
    main()
