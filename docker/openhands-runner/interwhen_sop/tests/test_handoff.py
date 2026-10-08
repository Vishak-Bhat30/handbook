"""Scenario tests for the Section 18 end-of-shift handoff verifiers (task 74170ae1).

Fixtures come from the task's environment seed only (never tests/rubrics).

    INTERWHEN_SLM_URL=http://127.0.0.1:8000/v1 INTERWHEN_XLSX_PYTHON=<python with openpyxl> \
    python3 -m unittest interwhen_sop.tests.test_handoff -v
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from interwhen_sop.tests.test_interwhen import _slm_up

TASK = "logistics_gear_sytems_inc_74170ae1"
REPO = Path(os.environ.get("INTERWHEN_REPO", Path(__file__).resolve().parents[4]))
ENV = REPO / "tasks" / TASK / "environment"

NOTES = {
    "REC-20260414-003": "AWAITING MTR: Quantity and condition complete; 200 units quarantined in Q-HOLD, NCR-MER-2026-0251 "
                        "sent. Supplier promised the MTR by COB today. Next: verify heat numbers H-8827-A/B against "
                        "the MTR per Section 12.6, then disposition. Owner: next-shift Coordinator (supplier Susan Park "
                        "to send MTR). Deadline: escalate if no MTR by 04/21/2026.",
    "REC-20260414-005": "AWAITING QUALITY DISPOSITION: Tier 2 damage on line 001 (30 of 144), lot quarantined in Q-HOLD. "
                        "NCR-MER-2026-0252 Critical draft awaiting Theo Brandt approval; escalation awaiting Walter Finch "
                        "and Darnell Hooks. Next: send NCR once approved. Owner: Theo Brandt, then Coordinator.",
    "REC-20260414-007": "AWAITING ESCALATION ACK: 78 units in Q-HOLD, NCR-MER-2026-0253 sent, response due 04/17/2026. "
                        "Line-down risk by 04/16/2026. Next: chase Elizabeth Velasquez acknowledgement and confirm "
                        "tomorrow's MER-PO-106835 delivery. Owner: Coordinator / Elizabeth Velasquez.",
}

GOOD_POST = """END-OF-SHIFT HANDOFF 04/14/2026 — Coordinator: SM
Receipts completed today: 4
Receipts open at handoff: 3
NCRs issued today: 3 (2 Major, 1 Critical)
Quarantines applied today: 3
Escalations open: 2

OPEN RECEIPTS:
- REC-20260414-003: Awaiting MTR from Consolidated Forge Works, see Handoff_Notes
- REC-20260414-005: Tier 2 damage, awaiting Theo disposition, see Handoff_Notes
- REC-20260414-007: Band 3 short, awaiting escalation acknowledgement, see Handoff_Notes

OPEN NCRs AWAITING COORDINATOR ACTION:
- NCR-MER-2026-0252: Critical draft awaiting Theo Brandt approval before sending

OPEN ESCALATIONS:
- REC-20260414-007, $7,650.00, Override, awaiting Elizabeth Velasquez since 12:35
- REC-20260414-005, $5,565.00, Override, awaiting Walter Finch since 13:35

QUARANTINE STATUS:
- Q-HOLD currently holds 4 entries totaling approximately $76,712.00. Re-inspections scheduled: REC-20260408-001 (04/15/2026), REC-20260414-003 (04/21/2026), REC-20260414-007 (04/21/2026).

NOTES FOR TOMORROW:
- Line-down risk on AX-04827-B2; MER-PO-106835 due 04/15."""


class HandoffBase(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)
        self.tmp = Path(tempfile.mkdtemp(prefix="iw-handoff-"))
        os.environ.update(INTERWHEN_TASK=TASK, INTERWHEN_STATE_DIR=str(self.tmp / "state"),
                          INTERWHEN_WORKDIR=str(self.tmp / "workdir"))
        shutil.copytree(ENV / "initial_workspace", self.tmp / "workdir")
        from interwhen_sop import ledger, slm, sopdata, workbooks
        sopdata.load.cache_clear()
        slm._model_cache = None
        self.ledger, self.n = ledger, 0
        workbooks.snapshot()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def call(self, tool, args, observation=None, run_code=False):
        from interwhen_sop import engine
        out = engine.pre_tool(tool, {"data": args})
        self.n += 1
        cid = f"c{self.n}"
        self.ledger.append({"type": "action", "id": cid, "call_id": cid, "tool": tool, "args": args})
        if out["decision"] == "deny":
            self.ledger.append({"type": "rejection", "call_id": cid, "tool": tool, "text": out["reason"]})
            return out
        if run_code:
            proc = subprocess.run([os.environ["INTERWHEN_XLSX_PYTHON"], "-c", args["code"]],
                                  capture_output=True, text=True, cwd=self.tmp / "workdir")
            observation = json.dumps({"stdout": proc.stdout, "stderr": proc.stderr, "returncode": proc.returncode})
        if tool == "syntara__writeFile":
            Path(args["file_path"]).write_text(args["content"])
            observation = json.dumps({"success": True})
        if observation is not None:
            self.ledger.append({"type": "observation", "call_id": cid, "tool": tool,
                                "text": f"[Tool '{tool}' executed.]{observation}"})
        return out

    def seed(self):
        self.ledger.append({"type": "user_message", "text": (REPO / "tasks" / TASK / "instruction.md").read_text()})
        slack = json.loads((ENV / "initial_external_services" / "slack" / "slack.json").read_text())
        chans = [{"id": c["id"], "name": c["name"], "is_channel": True} for c in slack["channels"].values()]
        self.call("slack__list_channels", {}, json.dumps({"ok": True, "channels": chans}))
        self.call("slack__get_users", {}, json.dumps({"ok": True, "members": slack["users"]}))
        for cid in ("C001", "C003"):
            self.call("slack__get_channel_history", {"channel_id": cid},
                      json.dumps({"ok": True, "messages": list(reversed(slack["messages"][cid]))}))
        mail = json.loads((ENV / "initial_external_services" / "google_mail" / "inbox.json").read_text())
        inbox = [dict(e, **{"from": e["from_addr"], "to": e["to_addr"]}) for e in mail["emails"] if e["folder"] == "INBOX"]
        self.call("google_mail__get_emails", {"folder": "INBOX"}, json.dumps({"emails": inbox}))

    def write_notes(self, notes=NOTES, status="OPEN — handoff"):
        code = ("import openpyxl\nwb=openpyxl.load_workbook('receiving_log.xlsx')\nws=wb.active\n"
                "h=[c.value for c in ws[1]]\nN=" + json.dumps(notes) + "\n"
                "for r in ws.iter_rows(min_row=2):\n"
                "    rid=r[h.index('Receipt_ID')].value\n"
                "    if rid in N and r[h.index('Status')].value=='In Process':\n"
                f"        r[h.index('Status')].value={status!r}\n"
                "        r[h.index('Handoff_Notes')].value=N[rid]\n"
                "wb.save('receiving_log.xlsx')")
        return self.call("syntara__executePython", {"code": code}, run_code=True)

    def file_emails(self):
        plan = {"NCRs - Open": ["11"], "Receipts - In Process": ["9", "12"], "Internal": ["10"],
                "Suppliers - General": ["8"], "Carriers": ["7"], "General": ["6"]}
        outs = [self.call("google_mail__move_emails", {"email_ids": ids, "target_folder": f},
                          json.dumps({"status": "all_succeeded"})) for f, ids in plan.items()]
        self.call("google_mail__mark_emails", {"email_ids": [i for v in plan.values() for i in v], "is_read": True},
                  json.dumps({"status": "all_succeeded"}))
        return outs


@unittest.skipUnless(os.environ.get("INTERWHEN_SLM_URL") and _slm_up(), "SLM not reachable")
class HandoffScenarios(HandoffBase):
    def test_compliant_handoff(self):
        self.seed()
        self.assertEqual(self.write_notes()["decision"], "allow")
        for out in self.file_emails():
            self.assertEqual(out["decision"], "allow", out.get("reason"))
        out = self.call("slack__post_message", {"channel_id": "C001", "text": GOOD_POST}, json.dumps({"ok": True}))
        self.assertEqual(out["decision"], "allow", out.get("reason"))
        self.call("slack__send_dm", {"user_id": "U009", "text": "Open at handoff: REC-20260414-003 (Q-HOLD), "
                                     "REC-20260414-005 (Q-HOLD), REC-20260414-007 (Q-HOLD)."}, json.dumps({"ok": True}))
        wb = sorted(p.name for p in (self.tmp / "workdir").glob("*.xlsx"))
        out = self.call("syntara__writeFile", {"file_path": str(self.tmp / "workdir" / "closed_workbooks.txt"),
                                               "content": "Closed workbooks:\n" + "\n".join(wb)})
        self.assertEqual(out["decision"], "allow", out.get("reason"))
        from interwhen_sop import engine
        res = engine.completion("test")
        self.assertEqual(res["decision"], "allow", res.get("reason"))

    def test_post_blocked_before_receiving_log_and_with_wrong_counts(self):
        self.seed()
        out = self.call("slack__post_message", {"channel_id": "C001", "text": GOOD_POST})
        self.assertEqual(out["decision"], "deny")
        self.assertIn("OPEN — handoff", out["reason"])
        self.write_notes()
        bad = GOOD_POST.replace("Receipts open at handoff: 3", "Receipts open at handoff: 2") \
                       .replace("HANDOFF 04/14/2026", "HANDOFF [04/14/2026]") \
                       .replace("- REC-20260414-007, $7,650.00", "- REC-20260414-003, $15,600.00")
        out = self.call("slack__post_message", {"channel_id": "C001", "text": bad})
        self.assertEqual(out["decision"], "deny")
        for frag in ("Receipts open at handoff", "header", "REC-20260414-007"):
            self.assertIn(frag, out["reason"])

    def test_vague_handoff_note_rejected(self):
        self.seed()
        self.write_notes({k: "Open." for k in NOTES})
        out = self.call("slack__post_message", {"channel_id": "C001", "text": GOOD_POST})
        self.assertEqual(out["decision"], "deny")
        self.assertIn("Handoff_Notes", out["reason"])

    def test_wrong_folder_and_early_workbook_file(self):
        self.seed()
        out = self.call("google_mail__move_emails", {"email_ids": ["7"], "target_folder": "Internal"})
        self.assertEqual(out["decision"], "deny")
        self.assertIn("Carriers", out["reason"])
        out = self.call("google_mail__move_emails", {"email_ids": ["6"], "target_folder": "Spam"})
        self.assertEqual(out["decision"], "deny")
        wb = sorted(p.name for p in (self.tmp / "workdir").glob("*.xlsx"))
        out = self.call("syntara__writeFile", {"file_path": str(self.tmp / "workdir" / "closed_workbooks.txt"),
                                               "content": "Closed:\n" + "\n".join(wb + ["carrier_claims_log.xlsx"])})
        self.assertEqual(out["decision"], "deny")
        self.assertIn("after the handoff post", out["reason"])
        self.assertIn("carrier_claims_log.xlsx", out["reason"])

    def test_completion_lists_missing_items(self):
        self.seed()
        from interwhen_sop import engine
        res = engine.completion("test")
        self.assertEqual(res["decision"], "deny")
        for frag in ("not handed off", "No end-of-shift handoff post", "Emails still in the inbox",
                     "Curtis Yablonski", "closed_workbooks.txt"):
            self.assertIn(frag, res["reason"])


if __name__ == "__main__":
    unittest.main()
