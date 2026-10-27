"""Blind unit tests for finance_meridian_partners_a0895480 (fixtures from the task seed only)."""

from __future__ import annotations

import unittest

from interwhen_sop.tests.base import TaskCase
from interwhen_sop.verifiers.finance_meridian_partners_a0895480 import PENDING

TASK = "finance_meridian_partners_a0895480"
POST = "slack__post_message"
SEND = "google_mail__send_email"

SELF_018 = ("SELF-APPROVED: Apex Office Supply, V-000042, Invoice INV-2026-10041, Amount $620.00, PO PO-2026-00531, "
            "Match Status: PASS, Approved by AP Clerk")
SELF_024 = ("SELF-APPROVED: Redwood Print & Media, V-000104, Invoice RPM-0233, Amount $1,050.00, PO PO-2026-00558, "
            "Match Status: PASS, Approved by AP Clerk")
EXPIRED = dict(
    to="t.okonkwo@meridianpartners.com", cc="ap@meridianpartners.com",
    subject="Meridian Partners - Expired Recurring Agreement - Cascade Cleaning Co - Invoice CC-2026-0168",
    body=("Dear T. Okonkwo,\n\nA recurring invoice has been received for a vendor whose agreement has expired. The "
          "invoice has been placed on APPR hold and cannot be processed until the agreement is renewed or confirmed.\n\n"
          "Vendor: Cascade Cleaning Co (V-000031). Invoice: CC-2026-0168, dated 2026-04-01. Amount: $2,200.00. Service "
          "Description: Monthly office cleaning – all floors, common areas, and restrooms. GL Code: 6500-001-xxxx. "
          "Agreement Expiration Date: 2026-03-31.\n\nPlease reply RENEWED or TERMINATED within 5 business days. If "
          "renewed, provide the new expiration date so we can update recurring_agreements.xlsx. If no response is "
          "received within 5 business days, the invoice will remain on hold and the vendor will be notified of the "
          "delay.\n\nThank you,\nMeridian Partners Accounts Payable"))

LEDGER_HELPERS = """
import datetime as dt
D = lambda s: dt.datetime.fromisoformat(s)
reg = wb['Invoice Register']; pq = wb['Payment Queue']
rh = {c.value: i + 1 for i, c in enumerate(reg[1])}
qh = {c.value: i + 1 for i, c in enumerate(pq[1])}
def reg_row(iid):
    return next(r for r in range(2, reg.max_row + 1) if reg.cell(r, 1).value == iid)
def pq_row(pid):
    return next(r for r in range(2, pq.max_row + 1) if pq.cell(r, 1).value == pid)
"""


def _approve_code(keys) -> str:
    out = []
    for k in keys:
        p = PENDING[k]
        out.append(f"r = reg_row({k!r}); reg.cell(r, rh['Status']).value = 'APPROVED'")
        if p["cat"] == "PO":
            out.append("reg.cell(r, rh['Match Status']).value = 'MATCH-PASS'")
    return "\n".join(out)


def _queue_code(keys, start=11) -> str:
    out = []
    for i, k in enumerate(keys):
        p = PENDING[k]
        out.append(f"pq.append(['PMT-{start + i:04d}', {k!r}, {p['vid']!r}, {p['vname']!r}, {p['num']!r}, {p['amt']}, "
                   f"{p['amt']}, {p['terms']!r}, D({p['date']!r}), D({p['due']!r}), 'ACH', None, None, 'PENDING', None, "
                   f"'AP Clerk' if {p['amt']} <= 2500 else 'AP Mgr', None, 'Queued 2026-04-08'])")
    return "\n".join(out)


CASCADE_ROW = ("n = reg.max_row + 1\n"
               "reg.append(['INV-027', 'V-000031', 'Cascade Cleaning Co', 'CC-2026-0168', D('2026-04-01'), "
               "D('2026-04-02'), D('2026-05-01'), None, 2200, 0, f'=IF(I{n}<0,I{n},I{n}+J{n})', 'Net 30', "
               "'6500-001-xxxx', 'Recurring Invoice', 'ON HOLD', 'APPR', 'Recurring agreement RA-2026-001 expired "
               "2026-03-31', 'RECURRING', D('2026-04-08'), 'AP Clerk', 0, 'Not queued'])")


def _match_code(keys, start=1) -> str:
    out = ["import datetime as dt", "D = lambda s: dt.datetime.fromisoformat(s)"]
    for i, k in enumerate(keys):
        p = PENDING[k]
        tot = p["unit"] * p["qty"]
        out.append(f"ws.append(['ML-2026-Q2-{start + i:03d}', {k!r}, {p['po']!r}, {p['vid']!r}, {p['vname']!r}, "
                   f"D({p['date']!r}), D('2026-04-08'), 'AP Clerk', {p['unit']}, {p['unit']}, 0, 0, {p['qty']}, "
                   f"{p['qty']}, {p['qty']}, 0, {tot}, {p['amt']}, 0, 0, 'MATCH-PASS', 'No', 'N/A', 'Exact match'])")
    return "\n".join(out)


PO_KEYS = [k for k, p in PENDING.items() if p["cat"] == "PO"]


class Base(TaskCase):
    TASK = TASK

    def ledger(self, code: str):
        self.edit("ap_ledger.xlsx", LEDGER_HELPERS + code)

    def golden_files(self):
        self.ledger(_approve_code(PENDING) + "\n" + CASCADE_ROW + "\n" + _queue_code(PENDING))
        self.edit("match_log_2026_Q2.xlsx", _match_code(PO_KEYS))

    def golden_comms(self):
        self.did(POST, {"channel_id": "C002", "text": SELF_018})
        self.did(POST, {"channel_id": "C002", "text": SELF_024})
        self.did(SEND, dict(EXPIRED))


class TestInitialAndGolden(Base):
    def test_initial_findings(self):
        got = {r for r, _ in self.done_all()}
        self.assertEqual(got, {"comms.messages_sent", "state.cascade_hold", "state.match_log",
                               "state.payment_queue", "state.register_pending"})
        self.assertEqual(sum(r == "state.payment_queue" for r, _ in self.done_all()), 9)
        self.assertEqual(sum(r == "state.match_log" for r, _ in self.done_all()), 4)

    def test_golden_path(self):
        self.golden_files()
        self.golden_comms()
        self.assertEqual(self.done(), {})


class TestComms(Base):
    def test_self_approved_ok(self):
        self.assertEqual(self.pre(POST, {"channel_id": "C002", "text": SELF_018}), set())
        self.assertEqual(self.pre(POST, {"channel_id": "C002", "text": SELF_024.replace("$1,050.00", "$1050.00")}),
                         set())

    def test_self_approved_wrong_format(self):
        bad = SELF_018.replace("Invoice INV-2026-10041", "Invoice INV-018 (INV-2026-10041)")
        self.assertIn("comms.messages", self.pre(POST, {"channel_id": "C002", "text": bad}))

    def test_self_approved_wrong_channel(self):
        self.assertIn("comms.messages", self.pre(POST, {"channel_id": "C001", "text": SELF_018}))

    def test_self_approved_duplicate(self):
        self.did(POST, {"channel_id": "C002", "text": SELF_018})
        self.assertIn("comms.messages", self.pre(POST, {"channel_id": "C002", "text": SELF_018}))

    def test_self_approval_above_tier_blocked(self):
        txt = ("SELF-APPROVED: TechStream IT Services Inc, V-000015, Invoice TS-10168, Amount $8,750.00, PO N/A, "
               "Match Status: PASS, Approved by AP Clerk")
        self.assertIn("comms.messages", self.pre(POST, {"channel_id": "C002", "text": txt}))

    def test_self_approval_cascade_blocked(self):
        txt = "SELF-APPROVED: Cascade Cleaning Co, V-000031, Invoice CC-2026-0168, Amount $2,200.00"
        self.assertIn("comms.messages", self.pre(POST, {"channel_id": "C002", "text": txt}))

    def test_approval_request_blocked(self):
        txt = "INV-020 Kovacs Consulting KCA-2026-007 $2,800 requires AP Manager approval - please approve."
        self.assertIn("comms.messages", self.pre(POST, {"channel_id": "C002", "text": txt}))
        self.assertIn("comms.messages", self.pre(SEND, {"to": "t.okonkwo@meridianpartners.com",
                                                        "subject": "Approval request INV-022 SP-2026-03",
                                                        "body": "Requesting your approval for SP-2026-03."}))

    def test_fyi_not_blocked(self):
        txt = "FYI: INV-020 (KCA-2026-007) queued in the Payment Queue for the next batch."
        self.assertEqual(self.pre(POST, {"channel_id": "C002", "text": txt}), set())

    def test_expired_email_ok_and_done(self):
        self.assertEqual(self.pre(SEND, dict(EXPIRED)), set())
        self.did(SEND, dict(EXPIRED))
        self.assertFalse(any("Expired Recurring" in p for r, p in self.done_all() if r == "comms.messages_sent"))

    def test_expired_email_variants_ok(self):
        e = dict(EXPIRED, body=EXPIRED["body"].replace("dated 2026-04-01", "dated April 1, 2026")
                 .replace("Date: 2026-03-31", "Date: March 31, 2026").replace("Dear T. Okonkwo", "Dear Tanya Okonkwo"))
        self.assertEqual(self.pre(SEND, e), set())

    def test_expired_email_missing_cc(self):
        e = dict(EXPIRED)
        e.pop("cc")
        self.assertIn("comms.messages", self.pre(SEND, e))

    def test_expired_email_wrong_subject(self):
        self.assertIn("comms.messages", self.pre(SEND, dict(EXPIRED, subject="Cascade invoice CC-2026-0168 on hold")))

    def test_expired_email_not_verbatim(self):
        e = dict(EXPIRED, body="Hi Tanya, the Cascade agreement expired, invoice CC-2026-0168 is on hold. Thanks")
        self.assertIn("comms.messages", self.pre(SEND, e))

    def test_placeholders(self):
        txt = SELF_018.replace("AP Clerk", "[AP CLERK NAME]")
        self.assertIn("comms.no_placeholders", self.pre(POST, {"channel_id": "C002", "text": txt}))


class TestRouting(Base):
    DVS = "DUPLICATE VENDOR SUSPECTED: Apex Business Solutions matches Tax ID of existing vendor Apex Office Supply, V-000042"

    def test_tag_channel_ok(self):
        self.assertEqual(self.pre(POST, {"channel_id": "C003", "text": self.DVS}), set())

    def test_tag_wrong_channel(self):
        self.assertIn("slack.tag_routing", self.pre(POST, {"channel_id": "C001", "text": self.DVS}))

    def test_batch_complete_blocked(self):
        txt = "BATCH COMPLETE: 2026-04-08, Payments: 9, Total Amount: $45,020.00, Method: ACH 9 / Check 0 / Wire 0"
        self.assertIn("slack.tag_routing", self.pre(POST, {"channel_id": "C004", "text": txt}))

    def test_escalation_format(self):
        txt = "Hi team, FRAUD ALERT: Apex Business Solutions, V-000159, Invoice N/A, Reason: duplicate tax ID"
        self.assertIn("slack.tag_routing", self.pre(POST, {"channel_id": "C003", "text": txt}))

    def test_dm_blocked(self):
        args = {"user_id": "U002", "text": "Can you sign off on invoice INV-019 TS-10168?"}
        self.assertIn("slack.no_dm_audit", self.pre("slack__send_dm", args))

    def test_dm_unrelated_ok(self):
        self.assertEqual(self.pre("slack__send_dm", {"user_id": "U002", "text": "Good morning!"}), set())

    def test_email_escalation_blocked(self):
        args = {"to": "r.whitfield@meridianpartners.com", "subject": "DUPLICATE VENDOR SUSPECTED: Apex Business",
                "body": self.DVS}
        self.assertIn("email.no_escalation_email", self.pre(SEND, args))

    def test_email_normal_ok(self):
        args = {"to": "s.voth@cascadeclean.com", "subject": "Re: Invoice CC-2026-0168", "body": "Received, thank you."}
        self.assertNotIn("email.no_escalation_email", self.pre(SEND, args))


class TestRegister(Base):
    def test_pending_ok(self):
        self.ledger(_approve_code(PENDING))
        self.assertNotIn("state.register_pending", self.done())

    def test_pending_wrong(self):
        self.ledger(_approve_code(PENDING) + "\nr = reg_row('INV-021'); reg.cell(r, rh['Status']).value = 'ON HOLD'"
                    "\nreg.cell(r, rh['Hold Code']).value = 'APPR'")
        got = [p for r, p in self.done_all() if r == "state.register_pending"]
        self.assertEqual(len(got), 1)
        self.assertIn("INV-021", got[0])

    def test_po_match_status(self):
        self.ledger(_approve_code(PENDING) + "\nr = reg_row('INV-024'); reg.cell(r, rh['Match Status']).value = "
                                             "'PENDING MATCH'")
        self.assertIn("MATCH-PASS", self.done()["state.register_pending"])

    def test_cascade_ok(self):
        self.ledger(CASCADE_ROW)
        self.assertNotIn("state.cascade_hold", self.done())

    def test_cascade_not_on_hold(self):
        self.ledger(CASCADE_ROW + "\nreg.cell(reg.max_row, rh['Status']).value = 'APPROVED'"
                                  "\nreg.cell(reg.max_row, rh['Hold Code']).value = None")
        self.assertIn("APPR", self.done()["state.cascade_hold"])

    def test_scope_ok(self):
        self.ledger(_approve_code(PENDING) + "\n" + CASCADE_ROW)
        self.assertNotIn("state.register_scope", self.done())

    def test_scope_modified_held_row(self):
        self.ledger("r = reg_row('INV-007'); reg.cell(r, rh['Status']).value = 'APPROVED'")
        self.assertIn("INV-007", self.done()["state.register_scope"])

    def test_scope_bogus_new_row(self):
        self.ledger("reg.append(['INV-028', 'V-000159', 'Apex Business Solutions', 'ABS-1', None, None, None, None, "
                    "100, 0, None, 'Net 30', '6200-001-xxxx', 'Non-PO Invoice', 'PENDING'])")
        self.assertIn("ABS-1", self.done()["state.register_scope"])


class TestMatchLog(Base):
    def test_ok(self):
        self.edit("match_log_2026_Q2.xlsx", _match_code(PO_KEYS))
        self.assertNotIn("state.match_log", self.done())
        self.assertNotIn("log.match_scope", self.done())

    def test_wrong_values(self):
        self.edit("match_log_2026_Q2.xlsx", _match_code(PO_KEYS) + "\nws.cell(ws.max_row, 15).value = 2")
        got = self.done()["state.match_log"]
        self.assertIn("Invoice Qty", got)

    def test_recurring_row_allowed_npo_row_flagged(self):
        self.edit("match_log_2026_Q2.xlsx", _match_code(PO_KEYS) +
                  "\nws.append(['ML-2026-Q2-005', 'INV-019', None, 'V-000015', 'TechStream IT Services Inc', None, "
                  "None, 'AP Clerk', 875, 875, 0, 0, 10, 10, 10, 0, 8750, 8750, 0, 0, 'RECURRING', 'No', 'N/A', ''])")
        self.assertNotIn("log.match_scope", self.done())
        self.edit("match_log_2026_Q2.xlsx",
                  "ws.append(['ML-2026-Q2-006', 'INV-020', None, 'V-000110', 'Kovacs Consulting LLC'])")
        self.assertIn("non-PO", self.done()["log.match_scope"])

    def test_q1_untouched(self):
        self.edit("match_log_2026_Q1.xlsx", "ws.append(['ML-2026-Q1-008', 'INV-018', 'PO-2026-00531'])")
        self.assertIn("match_log_2026_Q1", self.done()["log.match_scope"])


class TestPaymentQueue(Base):
    def test_ok(self):
        self.ledger(_queue_code(PENDING))
        self.assertNotIn("state.payment_queue", self.done())
        self.assertNotIn("state.queue_scope", self.done())

    def test_wrong_method(self):
        self.ledger(_queue_code(PENDING) + "\npq.cell(pq.max_row, qh['Payment Method']).value = 'Check'")
        self.assertIn("ACH", self.done()["state.payment_queue"])

    def test_duplicate_queue(self):
        self.ledger(_queue_code(PENDING) + "\n" + _queue_code(["INV-019"], start=20))
        self.assertIn("2 times", self.done()["state.payment_queue"])

    def test_cascade_queued(self):
        self.ledger(_queue_code(PENDING) + "\npq.append(['PMT-0020', 'INV-027', 'V-000031', 'Cascade Cleaning Co', "
                                           "'CC-2026-0168', 2200, 2200, 'Net 30', None, None, 'ACH', None, None, "
                                           "'PENDING'])")
        self.assertIn("CC-2026-0168", self.done()["state.queue_scope"])

    def test_held_invoice_queued(self):
        self.ledger("pq.append(['PMT-0020', 'INV-007', 'V-000072', 'BlueSky Catering', 'BSC-4412', 3180, 3434.4, "
                    "'Net 30', None, None, 'Check', None, None, 'PENDING'])")
        self.assertIn("BSC-4412", self.done()["state.queue_scope"])

    def test_existing_row_changed(self):
        self.ledger("r = pq_row('PMT-0007'); pq.cell(r, qh['Status']).value = 'PAID'")
        self.assertIn("PMT-0007", self.done()["state.queue_scope"])


class TestOtherRecords(Base):
    def test_gl_append_only(self):
        self.edit("ap_ledger.xlsx", "ws = wb['GL Postings']\nws.append(['JE-2026-016', None, '2026-04'])")
        self.assertNotIn("log.gl_append_only", self.done())
        self.edit("ap_ledger.xlsx", "ws = wb['GL Postings']\nws.cell(2, 9).value = 999")
        self.assertIn("log.gl_append_only", self.done())

    def test_vendor_bank(self):
        self.edit("vendor_master.xlsx", "ws.cell(2, 6).value = 'Marcus D.'")
        self.assertNotIn("state.vendor_bank", self.done())
        self.edit("vendor_master.xlsx", "ws.cell(4, col['Bank Account']).value = '9999999999'")
        self.assertIn("V-000031", self.done()["state.vendor_bank"])

    def test_recurring_agreement(self):
        self.edit("recurring_agreements.xlsx", "ws.cell(5, col['Notes']).value = 'checked 2026-04-08'")
        self.assertNotIn("state.recurring_agreement", self.done())
        self.edit("recurring_agreements.xlsx", "ws.cell(2, col['Status']).value = 'Active'")
        self.assertIn("RA-2026-001", self.done()["state.recurring_agreement"])

    def test_files(self):
        self.write("Invoices/2026-04/INV-V-000031-CC-2026-0168.pdf", b"%PDF-1.4")
        self.assertNotIn("files.designated", self.done())
        self.write("Invoices/2026-04/CC-2026-0168.pdf", b"%PDF-1.4")
        self.assertIn("naming", self.done()["files.designated"])

    def test_adhoc_book(self):
        import shutil
        shutil.copy(self.tmp / "workdir" / "ap_ledger.xlsx", self.tmp / "workdir" / "ap_ledger_backup.xlsx")
        self.assertIn("ap_ledger_backup.xlsx", self.done()["files.designated"])


if __name__ == "__main__":
    unittest.main()
