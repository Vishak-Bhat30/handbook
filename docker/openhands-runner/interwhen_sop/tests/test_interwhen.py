"""Scenario tests for interwhen_sop.

Fixtures are built only from the task's *environment seed* (Slack/mail/workbooks),
never from tests/rubrics. Scenario tests call the live SLM and are skipped when it
is unreachable; pure-Python unit tests always run.

    INTERWHEN_SLM_URL=http://127.0.0.1:8000/v1 INTERWHEN_XLSX_PYTHON=<python with openpyxl> \
    INTERWHEN_REPO=/path/to/Vishak_Handbook python3 -m unittest interwhen_sop.tests.test_interwhen -v
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

TASK = "logistics_gear_sytems_inc_9b60992d"
REPO = Path(os.environ.get("INTERWHEN_REPO", Path(__file__).resolve().parents[4]))
ENV = REPO / "tasks" / TASK / "environment"

GOOD_BODY = """Hi Maribel,

I need the following to proceed with a receiving item. Please respond as soon as possible.

This relates to:
• Re-inspection completed today on REC-20260407-003
• Discrepancy reported in #receiving-dock for REC-20260407-003

Please provide:
• Photos of all affected units (all damage angles)
• Written description: count of affected units, location and nature of damage, any other observations

Needed to complete:
• Receiving log amendment

Thanks,
JV"""


def _slm_up() -> bool:
    from interwhen_sop import slm
    return slm.model_name() is not None


class Base(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)
        self.tmp = Path(tempfile.mkdtemp(prefix="iw-test-"))
        os.environ["INTERWHEN_TASK"] = TASK
        os.environ["INTERWHEN_STATE_DIR"] = str(self.tmp / "state")
        os.environ["INTERWHEN_WORKDIR"] = str(self.tmp / "workdir")
        os.environ["INTERWHEN_INITIAL_DATA"] = str(ENV / "initial_external_services")
        shutil.copytree(ENV / "initial_workspace", self.tmp / "workdir")
        from interwhen_sop import ledger, slm, sopdata
        sopdata.load.cache_clear()
        slm._model_cache = None
        self.ledger = ledger
        self.n = 0

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def call(self, tool: str, args: dict, observation: str | None = None) -> dict:
        from interwhen_sop import engine
        out = engine.pre_tool(tool, {"data": args})
        self.n += 1
        cid = f"c{self.n}"
        self.ledger.append({"type": "action", "id": cid, "call_id": cid, "tool": tool, "args": args})
        if out["decision"] == "deny":
            self.ledger.append({"type": "rejection", "call_id": cid, "tool": tool, "text": out["reason"]})
        elif observation is not None:
            self.ledger.append({"type": "observation", "call_id": cid, "tool": tool,
                                "text": f"[Tool '{tool}' executed.]{observation}"})
        return out

    def seed_reads(self):
        """Instruction + the reads a careful agent makes (channel, users, receiving log, emails)."""
        from interwhen_sop import workbooks
        workbooks.snapshot()
        self.ledger.append({"type": "user_message", "text": (REPO / "tasks" / TASK / "instruction.md").read_text()})
        slack = json.loads((ENV / "initial_external_services" / "slack" / "slack.json").read_text())
        chans = [{"id": c["id"], "name": c["name"], "is_channel": True} for c in slack["channels"].values()]
        self.call("slack__list_channels", {}, json.dumps({"ok": True, "channels": chans}))
        self.call("slack__get_channel_history", {"channel_id": "C001"},
                  json.dumps({"ok": True, "messages": list(reversed(slack["messages"]["C001"]))}))
        rows = workbooks.dump()["receiving_log.xlsx"]
        text = "\n".join("  ".join(r) for r in next(iter(rows.values())))
        self.call("syntara__executeBash",
                  {"command": "cd /workdir && python3 -c \"import pandas as pd; print(pd.read_excel('receiving_log.xlsx'))\""},
                  json.dumps({"stdout": text, "returncode": 0}))
        mail = json.loads((ENV / "initial_external_services" / "google_mail" / "inbox.json").read_text())
        self.call("google_mail__get_emails", {}, json.dumps({"emails": mail["emails"]}))


class UnitTests(Base):
    def test_classify_reads_and_writes(self):
        from interwhen_sop.actions import classify
        read = classify("syntara__executeBash", {"command": "cd /workdir && python3 <<'EOF'\nimport pandas as pd\n"
                                                 "df=pd.read_excel('ncr_log.xlsx')\nprint(len(df)>3)\nEOF"})
        self.assertEqual(read.kind, "read")
        write = classify("syntara__executePython", {"code": "import openpyxl\nP='/workdir/ncr_log.xlsx'\n"
                                                    "wb=openpyxl.load_workbook(P)\nwb.active.append([1])\nwb.save(P)"})
        self.assertEqual((write.kind, write.files_written), ("workbook_write", ["ncr_log.xlsx"]))
        dele = classify("syntara__executePython", {"code": "import openpyxl\nwb=openpyxl.load_workbook('/workdir/"
                                                   "receiving_log.xlsx')\nwb.active.delete_rows(5)\nwb.save('/workdir/receiving_log.xlsx')"})
        self.assertTrue(dele.deletes)
        self.assertEqual(classify("slack__get_channel_history", {"channel_id": "C001"}).kind, "read")

    def test_template31_exact_passes_and_extra_text_fails(self):
        from interwhen_sop import sopdata, templates
        sop = sopdata.load(TASK)
        tpl = sop.template(31)["body"]
        req = [b for b in tpl if b.startswith(("• Re-inspection", "• Discrepancy", "• Photos", "• Written", "• Receiving log"))]
        kw = dict(fill={"[ID]": "20260407-003"}, required_bullets=req, first_name="Maribel", initials_rule=("JV", "t"))
        ok = templates.check(sop, 31, "Information Request — REC-20260407-003", GOOD_BODY, **kw)
        self.assertEqual(ok.problems, [])
        bad = templates.check(sop, 31, "Information Request — REC-20260407-003 (HW-3305)",
                              GOOD_BODY.replace("Thanks,", "I've already opened an NCR.\nThanks,"), **kw)
        self.assertTrue(any("Subject" in p for p in bad.problems))
        self.assertTrue(any("as written" in p for p in bad.problems))

    def test_business_days_and_holidays(self):
        import datetime as dt
        from interwhen_sop import sopdata
        sop = sopdata.load(TASK)
        self.assertEqual(sop.business_days_between(dt.date(2026, 4, 7), dt.date(2026, 4, 14)), 5)
        self.assertEqual(sop.business_days_between(dt.date(2026, 5, 22), dt.date(2026, 5, 26)), 1)  # Memorial Day

    def test_read_only_and_deletion_rules(self):
        self.seed_reads_no_slm()
        out = self.call("syntara__executePython", {"code": "import openpyxl\nwb=openpyxl.load_workbook('/workdir/"
                                                   "supplier_master.xlsx')\nwb.save('/workdir/supplier_master.xlsx')"})
        self.assertEqual(out["decision"], "deny")
        self.assertIn("read-only", out["reason"])
        out = self.call("syntara__executeBash", {"command": "rm /workdir/ncr_log.xlsx"})
        self.assertEqual(out["decision"], "deny")

    def seed_reads_no_slm(self):
        os.environ["INTERWHEN_SLM_URL"] = "http://127.0.0.1:9/v1"  # unreachable: SLM-dependent rules fall open
        self.ledger.append({"type": "user_message", "text": "noop"})


@unittest.skipUnless(os.environ.get("INTERWHEN_SLM_URL") and _slm_up(), "SLM not reachable")
class ScenarioTests(Base):
    def test_compliant_path(self):
        self.seed_reads()
        out = self.call("google_mail__send_email", {"to": "maribel.ortiz@gearsystems.com",
                                                    "subject": "Information Request — REC-20260407-003",
                                                    "body": GOOD_BODY},
                        json.dumps({"status": "sent", "email": {"email_id": "22", "folder": "Sent"}}))
        self.assertEqual(out["decision"], "allow", out.get("reason"))
        from interwhen_sop import engine
        self.assertEqual(engine.completion("test")["decision"], "allow")

    def test_premature_steps_blocked_and_feedback_has_template(self):
        self.seed_reads()
        out = self.call("syntara__executePython", {"code": "import openpyxl\nwb=openpyxl.load_workbook('/workdir/"
                        "receiving_log.xlsx')\nwb.active.append(['REC-20260407-003-T4','MER-PO-HIST-05'])\n"
                        "wb.save('/workdir/receiving_log.xlsx')"})
        self.assertEqual(out["decision"], "deny")
        self.assertIn("11.7.1 step 5", out["reason"])
        out = self.call("slack__post_message", {"channel_id": "C001", "text": "QUARANTINE: HW-3305 12 units to Q-HOLD @mortiz"})
        self.assertEqual(out["decision"], "deny")
        out = self.call("google_mail__send_email", {"to": "maribel.ortiz@gearsystems.com",
                                                    "subject": "Information Request — REC-20260407-003 (HW-3305)",
                                                    "body": GOOD_BODY.replace("Thanks,", "NCR opened.\nThanks,")})
        self.assertEqual(out["decision"], "deny")
        self.assertIn("Subject: Information Request — REC-20260407-003", out["reason"])

    def test_completion_requires_request_then_budget(self):
        self.seed_reads()
        from interwhen_sop import config, engine
        for _ in range(config.MAX_COMPLETION_DENIALS):
            out = engine.completion("test")
            self.assertEqual(out["decision"], "deny")
            self.assertIn("Template 31", out["reason"])
        self.assertEqual(engine.completion("test")["decision"], "allow")

    def test_evidence_unlocks_tier4_steps(self):
        self.seed_reads()
        self.call("google_mail__send_email", {"to": "maribel.ortiz@gearsystems.com",
                                              "subject": "Information Request — REC-20260407-003", "body": GOOD_BODY},
                  json.dumps({"status": "sent", "email": {"email_id": "22", "folder": "Sent"}}))
        reply = {"email_id": "23", "from_addr": "maribel.ortiz@gearsystems.com",
                 "to_addr": "receiving.meridian@gearsystems.com", "folder": "inbox",
                 "subject": "Re: Information Request — REC-20260407-003", "date": "2026-04-14T15:00:00-05:00",
                 "body_text": "Photos attached. 12 lock nuts (HW-3305) in HW-1 Bin 1D have cracked flanges and "
                              "flattened threads on one side, consistent with impact.",
                 "attachments": [{"filename": "HW-3305_damage_1.jpg", "content_type": "image/jpeg"}]}
        self.call("google_mail__get_emails", {"query": "REC-20260407-003"}, json.dumps({"emails": [reply]}))
        out = self.call("syntara__executePython", {"code": "import openpyxl\nwb=openpyxl.load_workbook('/workdir/"
                        "receiving_log.xlsx')\nwb.active.append(['REC-20260407-003-T4','MER-PO-HIST-05'])\n"
                        "wb.save('/workdir/receiving_log.xlsx')"}, json.dumps({"returncode": 0}))
        self.assertEqual(out["decision"], "allow", out.get("reason"))


if __name__ == "__main__":
    unittest.main()
