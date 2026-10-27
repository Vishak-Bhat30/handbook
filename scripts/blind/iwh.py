"""Local harness: build a verifier Context for a task with a synthetic ledger and run rules.

Usage (host):  python3 harness.py <task_suffix> [--copy]
Sets INTERWHEN_* env to the task's environment so World/workbooks read the initial data.
"""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path("/mnt/datadrive/t-bhatvishak/Vishak_Handbook")
sys.path.insert(0, str(REPO / "docker" / "openhands-runner"))


def setup(suffix: str) -> Path:
    task = next(p.name for p in (REPO / "tasks").iterdir() if p.name.endswith(suffix))
    env = REPO / "tasks" / task / "environment"
    work = Path(tempfile.mkdtemp(prefix=f"iw_{suffix}_"))
    shutil.copytree(env / "initial_workspace", work / "workdir")
    state = work / "state"
    state.mkdir()
    os.environ.update({
        "INTERWHEN_TASK": task,
        "INTERWHEN_STATE_DIR": str(state),
        "INTERWHEN_WORKDIR": str(work / "workdir"),
        "INTERWHEN_INITIAL_DATA": str(env / "initial_external_services"),
        "INTERWHEN_XLSX_PYTHON": "/home/t-bhatvishak/miniconda3/bin/python3",
        "INTERWHEN_SLM_URL": "http://127.0.0.1:8000/v1",
    })
    from interwhen_sop import workbooks
    assert workbooks.snapshot()
    return work


def context(records):
    from interwhen_sop import framework, sopdata, state
    return framework.Context(sopdata.load(), state.build(records), [])


_n = [0]


def act(tool, args, result='{"ok": true}'):
    """Ledger records for one executed tool call."""
    _n[0] += 1
    cid = f"c{_n[0]}"
    return [{"type": "action", "call_id": cid, "tool": tool, "args": args},
            {"type": "observation", "call_id": cid, "tool": tool, "text": result}]


def run(stage, records, tool=None, args=None):
    from interwhen_sop import framework
    from interwhen_sop.actions import classify
    ctx = context(records)
    rules = framework.load_rules(os.environ["INTERWHEN_TASK"])
    if stage == "pre":
        return framework.run(rules, "pre", ctx, classify(tool, args))
    return framework.run(rules, "completion", ctx)


def show(res):
    findings, errors = res
    for f in findings:
        print(" -", f.rule, "|", f.problem[:600])
    for e in errors:
        print(" ! ERR", e)
    if not findings and not errors:
        print(" (allow)")
