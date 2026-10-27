"""Unit-test base for per-task verifiers (scripts/algo.md Step 4.3).

Fixtures come only from the task's environment seed (initial workspace, external services); never tests/.

    INTERWHEN_XLSX_PYTHON=/home/t-bhatvishak/miniconda3/bin/python3 \
        python3 -m unittest interwhen_sop.tests.blind.test_<id> -v
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(os.environ.get("INTERWHEN_REPO", Path(__file__).resolve().parents[4]))
XLSX_PY = os.environ.get("INTERWHEN_XLSX_PYTHON", "/home/t-bhatvishak/miniconda3/bin/python3")


class TaskCase(unittest.TestCase):
    TASK = ""

    def setUp(self):
        self._env = dict(os.environ)
        env = REPO / "tasks" / self.TASK / "environment"
        self.tmp = Path(tempfile.mkdtemp(prefix="iw-task-"))
        shutil.copytree(env / "initial_workspace", self.tmp / "workdir")
        os.environ.update({"INTERWHEN_TASK": self.TASK, "INTERWHEN_STATE_DIR": str(self.tmp / "state"),
                           "INTERWHEN_WORKDIR": str(self.tmp / "workdir"),
                           "INTERWHEN_INITIAL_DATA": str(env / "initial_external_services"),
                           "INTERWHEN_XLSX_PYTHON": XLSX_PY,
                           "INTERWHEN_SLM_URL": "http://127.0.0.1:9/v1"})
        from interwhen_sop import sopdata, workbooks
        sopdata.load.cache_clear()
        self.assertTrue(workbooks.snapshot())
        self.records: list[dict] = []
        self.n = 0

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def did(self, tool: str, args: dict, result: str = '{"ok": true}') -> None:
        """Record an executed tool call (and its result) in the ledger."""
        self.n += 1
        cid = f"c{self.n}"
        self.records += [{"type": "action", "call_id": cid, "tool": tool, "args": args},
                         {"type": "observation", "call_id": cid, "tool": tool, "text": result}]

    def _run(self, stage, tool=None, args=None):
        from interwhen_sop import framework, sopdata, state
        from interwhen_sop.actions import classify
        ctx = framework.Context(sopdata.load(), state.build(self.records), [])
        rules = framework.load_rules(self.TASK)
        findings, errors = (framework.run(rules, "pre", ctx, classify(tool, args)) if stage == "pre"
                            else framework.run(rules, "completion", ctx))
        self.assertEqual(errors, [])
        return findings

    def pre(self, tool, args) -> set[str]:
        """Rule ids that would block this call."""
        return {f.rule for f in self._run("pre", tool, args)}

    def done(self) -> dict[str, str]:
        """Completion findings: rule id -> problem (last one per rule)."""
        return {f.rule: f.problem for f in self._run("completion")}

    def done_all(self) -> list[tuple[str, str]]:
        return [(f.rule, f.problem) for f in self._run("completion")]

    def edit(self, fname: str, code: str, sheet: str | None = None) -> None:
        """Apply an openpyxl edit to a workspace workbook. In ``code``: wb, ws, hdr (header list), col
        (header -> 1-based column index), path."""
        path = self.tmp / "workdir" / fname
        script = (f"import openpyxl\npath={str(path)!r}\nwb=openpyxl.load_workbook(path)\n"
                  f"ws=wb[{sheet!r}] if {sheet!r} else wb.active\n"
                  "hdr=[c.value for c in ws[1]]\ncol={h:i+1 for i,h in enumerate(hdr)}\n" + code + "\nwb.save(path)\n")
        subprocess.run([XLSX_PY, "-c", script], check=True)

    def write(self, rel: str, data: bytes | str) -> Path:
        p = self.tmp / "workdir" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data.encode() if isinstance(data, str) else data)
        return p
