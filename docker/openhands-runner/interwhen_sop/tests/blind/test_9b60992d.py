"""Blind unit tests for logistics_gear_sytems_inc_9b60992d (Maribel's HW-3305 concealed damage, REC-20260407-003)."""

from __future__ import annotations

import json
import unittest

from interwhen_sop.tests.base import TaskCase

MARIBEL = "maribel.ortiz@gearsystems.com"
SEND = "google_mail__send_email"
PY = "syntara__executePython"

T31_BODY = """Hi Maribel,

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
T31 = {"to": MARIBEL, "subject": "Information Request — REC-20260407-003", "body": T31_BODY}
REPLY = json.dumps({"emails": [{"from_addr": MARIBEL, "subject": "Re: Information Request — REC-20260407-003",
                                "body": "Photos attached. 12 units with impact dents on the flange."}]})


class Base(TaskCase):
    TASK = "logistics_gear_sytems_inc_9b60992d"

    def set_cell(self, book: str, key: str, col: int, value) -> None:
        self.edit(book, f"r = next(i for i in range(4, ws.max_row + 1) if ws.cell(i, 1).value == {key!r})\n"
                        f"ws.cell(r, {col}).value = {value!r}")

    def add_row(self, book: str, values: list) -> None:
        self.edit(book, f"ws.append({values!r})")


class TestInitialAndGolden(Base):
    def test_initial_only_t31_outstanding(self):
        self.assertEqual(set(self.done()), {"iw.t31.messages_sent"})

    def test_golden_path(self):
        self.assertEqual(self.pre(SEND, T31), set())
        self.did(SEND, T31)
        self.assertEqual(self.done(), {})


class TestT31(Base):
    def test_compliant_with_extra_internal_cc(self):
        self.assertEqual(self.pre(SEND, {**T31, "cc": "theo.brandt@gearsystems.com"}), set())

    def test_wrong_subject(self):
        self.assertIn("iw.t31.messages", self.pre(SEND, {**T31, "subject": "HW-3305 damage photos"}))

    def test_missing_photo_request(self):
        body = T31_BODY.replace("• Photos of all affected units (all damage angles)\n", "")
        self.assertIn("iw.t31.messages", self.pre(SEND, {**T31, "body": body}))

    def test_inapplicable_line_kept(self):
        body = T31_BODY.replace("This relates to:\n",
                                "This relates to:\n• Inbound receipt under PO #MER-PO-HIST-05, received today\n")
        self.assertIn("iw.t31.messages", self.pre(SEND, {**T31, "body": body}))

    def test_wrong_recipient_does_not_satisfy(self):
        self.did(SEND, {**T31, "to": "theo.brandt@gearsystems.com"})
        self.assertIn("iw.t31.messages_sent", self.done())

    def test_supplier_facing_blocked(self):
        args = {**T31, "to": "sandra.yee@coastalfasteners.com"}
        self.assertIn("iw.t31_internal", self.pre(SEND, args))
        self.assertEqual(self.pre(SEND, T31) & {"iw.t31_internal"}, set())


class TestScope(Base):
    def test_slack_dm_to_maribel_blocked(self):
        self.assertIn("iw.maribel_email_only",
                      self.pre("slack__send_dm", {"user_id": "U007", "text": "Please send photos of HW-3305."}))

    def test_thread_reply_to_maribel_blocked(self):
        args = {"channel_id": "C001", "thread_ts": "1776183000.001350", "text": "Thanks, emailing you now."}
        self.assertIn("iw.maribel_email_only", self.pre("slack__reply_to_thread", args))

    def test_plain_channel_post_allowed(self):
        args = {"channel_id": "C001", "text": "REC-20260407-003 HW-3305: Tier 4 concealed damage, photos requested."}
        self.assertEqual(self.pre("slack__post_message", args), set())

    def test_other_issue_email_blocked(self):
        args = {"to": "joonho.park@gearsystems.com", "subject": "NCR-2026-0031 overdue",
                "body": "NCR-2026-0031 is overdue."}
        self.assertIn("iw.scope_comms", self.pre(SEND, args))

    def test_unrelated_external_blocked_and_carrier_allowed(self):
        bad = {"to": "claims@yellowfreight.com", "subject": "YF-CLM-88214", "body": "Status of YF-CLM-88214?"}
        self.assertIn("iw.scope_comms", self.pre(SEND, bad))
        ok = {"to": "claims@rlcarriers.com", "subject": "Concealed damage notice — REC-20260407-003",
              "body": "Concealed damage found on 12 of 800 HW-3305 lock nuts from the 04/07/2026 delivery."}
        self.assertNotIn("iw.scope_comms", self.pre(SEND, ok))

    def test_other_issue_workbook_write_blocked(self):
        code = ('import openpyxl\nwb=openpyxl.load_workbook("/workdir/ncr_log.xlsx")\nws=wb.active\n'
                'ws["N7"]="Overdue - Escalated"  # NCR-2026-0031\nwb.save("/workdir/ncr_log.xlsx")')
        self.assertIn("iw.scope_writes", self.pre(PY, {"code": code}))
        ok = ('import openpyxl\nwb=openpyxl.load_workbook("/workdir/inventory_master.xlsx")\nws=wb.active\n'
              'ws["W13"]="HW-3305 concealed damage reported"\nwb.save("/workdir/inventory_master.xlsx")')
        self.assertNotIn("iw.scope_writes", self.pre(PY, {"code": ok}))


class TestWindowAndGate(Base):
    def test_outside_window_claim_blocked(self):
        args = {**T31, "body": T31_BODY + "\nREC-20260407-003 is outside the 10-business-day window."}
        self.assertIn("iw.window", self.pre(SEND, args))

    T4_CODE = ('import openpyxl\nwb=openpyxl.load_workbook("/workdir/receiving_log.xlsx")\nws=wb.active\n'
               'ws.append(["REC-20260407-003-T4","MER-PO-HIST-05",1,"HW-3305"])\nwb.save("/workdir/receiving_log.xlsx")')

    def test_t4_row_before_reply_blocked(self):
        self.assertIn("iw.t4_gate", self.pre(PY, {"code": self.T4_CODE}))

    def test_t4_row_after_reply_allowed(self):
        self.did("google_mail__get_emails", {"folder": "INBOX"}, REPLY)
        self.assertNotIn("iw.t4_gate", self.pre(PY, {"code": self.T4_CODE}))


class TestRecords(Base):
    def test_posted_row_edit_flagged(self):
        self.did(SEND, T31)
        self.set_cell("receiving_log.xlsx", "REC-20260407-003", 13, "4")
        self.assertIn("iw.records_unchanged", self.done())

    def test_hw3305_inventory_edit_allowed(self):
        self.did(SEND, T31)
        self.set_cell("inventory_master.xlsx", "HW-3305", 23, "Tier 4 concealed damage reported 04/14/2026")
        self.assertEqual(self.done(), {})

    def test_other_inventory_row_flagged(self):
        self.did(SEND, T31)
        self.set_cell("inventory_master.xlsx", "DS-7735", 10, "N")
        self.assertIn("iw.records_unchanged", self.done())

    def test_ncr_status_change_flagged(self):
        self.did(SEND, T31)
        self.set_cell("ncr_log.xlsx", "NCR-2026-0028", 14, "Closed")
        self.assertIn("iw.records_unchanged", self.done())

    def test_t4_row_without_reply_flagged(self):
        self.did(SEND, T31)
        self.add_row("receiving_log.xlsx", ["REC-20260407-003-T4", "MER-PO-HIST-05", 1, "HW-3305"])
        self.assertIn("iw.records_unchanged", self.done())

    def test_t4_row_after_reply_ok(self):
        self.did(SEND, T31)
        self.did("google_mail__get_emails", {"folder": "INBOX"}, REPLY)
        self.add_row("receiving_log.xlsx", ["REC-20260407-003-T4", "MER-PO-HIST-05", 1, "HW-3305"])
        self.assertEqual(self.done(), {})

    def test_correction_row_flagged(self):
        self.did(SEND, T31)
        self.did("google_mail__get_emails", {"folder": "INBOX"}, REPLY)
        self.add_row("receiving_log.xlsx", ["REC-20260407-003-C1", "MER-PO-HIST-05", 1, "HW-3305"])
        self.assertIn("iw.records_unchanged", self.done())


class TestProhibitions(Base):
    def test_email_delete_blocked(self):
        self.assertIn("iw.no_delete", self.pre("google_mail__delete_emails", {"email_ids": ["18"]}))
        self.assertNotIn("iw.no_delete", self.pre("google_mail__move_emails",
                                                  {"email_ids": ["18"], "target_folder": "Internal"}))

    def test_record_file_delete_blocked(self):
        self.assertIn("iw.no_delete", self.pre("syntara__executeBash", {"command": "rm /workdir/ncr_log.xlsx"}))

    def test_promise_to_supplier_blocked(self):
        bad = {"to": "sandra.yee@coastalfasteners.com", "subject": "HW-3305 damage — REC-20260407-003",
               "body": "We found damage on 12 HW-3305 lock nuts. We will issue a credit for them."}
        self.assertIn("iw.no_promise", self.pre(SEND, bad))
        ok = {**bad, "body": "We found damage on 12 HW-3305 lock nuts. Procurement will follow up."}
        self.assertNotIn("iw.no_promise", self.pre(SEND, ok))

    def test_supplier_master_readonly(self):
        code = ('import openpyxl\nwb=openpyxl.load_workbook("/workdir/supplier_master.xlsx")\nws=wb.active\n'
                'ws["W6"]="HW-3305 concealed damage"\nwb.save("/workdir/supplier_master.xlsx")')
        self.assertIn("iw.readonly", self.pre(PY, {"code": code}))
        ok = code.replace("supplier_master", "inventory_master")
        self.assertNotIn("iw.readonly", self.pre(PY, {"code": ok}))

    def test_placeholders_blocked(self):
        args = {**T31, "body": T31_BODY.replace("JV", "[Coordinator Initials]")}
        self.assertIn("comms.no_placeholders", self.pre(SEND, args))


if __name__ == "__main__":
    unittest.main()
