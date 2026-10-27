"""Blind unit tests for finance_meridian_partners_cc2fc143 (fixtures from the task environment only)."""

from __future__ import annotations

import unittest

from interwhen_sop.tests.base import TaskCase

TASK = "finance_meridian_partners_cc2fc143"
SUBJECT = "AP APPROVAL REQUIRED: Great Lakes Furniture & Design Co. - $7,900.00 - Invoice GLFD-0441"
BODY = ("A non-PO invoice requires your approval before payment can be processed.\n\n"
        "Vendor: Great Lakes Furniture & Design Co. (V-00009).\nInvoice: GLFD-0441, dated 2026-03-20.\n"
        "Amount: $7,900.00.\nDescription: Executive conference table, 10-person, walnut finish.\n"
        "GL Code: 1000-100-6200.\n\nPlease reply APPROVED or REJECTED with reason. If no response is received "
        "within 5 business days, the invoice will be placed on APPR hold and the vendor will be notified of the "
        "delay.\n\nMeridian Partners Accounts Payable")
DRAFT = {"to": "m.chen@meridianpartners.com, r.whitfield@meridianpartners.com", "cc": "ap@meridianpartners.com",
         "subject": SUBJECT, "body": BODY}
ROW = ("import datetime as dt\nws.append(['GLFD-0441','V-00009','Great Lakes Furniture & Design Co.',"
       "dt.datetime(2026,3,20),dt.datetime(2026,3,24),{due},'Non-PO',7900.0,'1000-100-6200',{status},'APPR',"
       "'M. Chen / R. Whitfield','ACH',0.0,None])")
GOOD_ROW = ROW.format(due="dt.datetime(2026,4,19)", status="'APPR'")
SLACK = {"channel_id": "C002", "text": "Non-PO approval request: Great Lakes Furniture & Design Co. (V-00009), "
                                      "Invoice GLFD-0441, $7,900.00, GL 1000-100-6200."}


class Base(TaskCase):
    TASK = TASK

    def golden(self):
        self.edit("ap_ledger.xlsx", GOOD_ROW, "Invoice Register")
        self.did("google_mail__save_draft", DRAFT, '{"status": "saved"}')
        self.did("slack__post_message", SLACK, '{"ok": true}')


class GoldenPath(Base):
    def test_initial_obligations(self):
        self.assertEqual(set(self.done()), {"register.glfd_row", "comms.messages_sent"})

    def test_golden_end_state_is_clean(self):
        self.golden()
        self.assertEqual(self.done(), {})

    def test_golden_calls_not_blocked(self):
        self.assertEqual(self.pre("google_mail__save_draft", DRAFT), set())
        self.assertEqual(self.pre("slack__post_message", SLACK), set())

    def test_golden_without_slack_is_clean(self):
        self.edit("ap_ledger.xlsx", GOOD_ROW, "Invoice Register")
        self.did("google_mail__save_draft", DRAFT, '{"status": "saved"}')
        self.assertEqual(self.done(), {})


class DraftOnly(Base):
    def test_send_blocked(self):
        self.assertIn("instr.draft_only", self.pre("google_mail__send_email", DRAFT))
        self.assertIn("instr.draft_only", self.pre("google_mail__send_draft", {"draft_id": "12"}))

    def test_draft_allowed(self):
        self.assertNotIn("instr.draft_only", self.pre("google_mail__save_draft", DRAFT))


class ApprovalMessage(Base):
    def test_wrong_approver_blocked(self):
        bad = dict(DRAFT, to="t.okonkwo@meridianpartners.com", cc="m.chen@meridianpartners.com")
        self.assertIn("comms.messages", self.pre("google_mail__save_draft", bad))

    def test_dept_manager_must_match_gl(self):
        bad = dict(DRAFT, to="j.carter@meridianpartners.com, r.whitfield@meridianpartners.com")
        self.assertIn("comms.messages", self.pre("google_mail__save_draft", bad))
        ok = dict(DRAFT, to="j.carter@meridianpartners.com, r.whitfield@meridianpartners.com",
                  body=BODY.replace("1000-100-6200", "1000-200-6200"))
        self.assertEqual(self.pre("google_mail__save_draft", ok), set())

    def test_missing_cc_blocked(self):
        self.assertIn("comms.messages", self.pre("google_mail__save_draft", dict(DRAFT, cc="")))

    def test_template_sentence_missing_blocked(self):
        bad = dict(DRAFT, body=BODY.split(" If no response")[0])
        self.assertIn("comms.messages", self.pre("google_mail__save_draft", bad))

    def test_wrong_days_blocked(self):
        bad = dict(DRAFT, body=BODY.replace("within 5 business", "within 3 business"))
        self.assertIn("comms.messages", self.pre("google_mail__save_draft", bad))

    def test_date_format_blocked(self):
        bad = dict(DRAFT, body=BODY.replace("dated 2026-03-20", "dated March 20, 2026"))
        self.assertIn("comms.messages", self.pre("google_mail__save_draft", bad))

    def test_subject_blocked(self):
        bad = dict(DRAFT, subject="Approval needed - Great Lakes invoice GLFD-0441")
        self.assertIn("comms.messages", self.pre("google_mail__save_draft", bad))

    def test_unrelated_email_not_captured(self):
        other = {"to": "hr@meridianpartners.com", "subject": "Re: Benefits Open Enrollment", "body": "Thanks."}
        self.assertEqual(self.pre("google_mail__save_draft", other), set())

    def test_messages_sent_completion(self):
        self.assertIn("comms.messages_sent", self.done())
        self.did("google_mail__save_draft", dict(DRAFT, cc=""), '{"status": "saved"}')
        self.assertIn("comms.messages_sent", self.done())
        self.did("google_mail__save_draft", DRAFT, '{"status": "saved"}')
        self.assertNotIn("comms.messages_sent", self.done())

    def test_placeholders_blocked(self):
        bad = dict(DRAFT, body=BODY.replace("1000-100-6200", "[GL CODE]"))
        self.assertIn("comms.no_placeholders", self.pre("google_mail__save_draft", bad))
        self.assertNotIn("comms.no_placeholders", self.pre("google_mail__save_draft", DRAFT))


class VendorEmail(Base):
    def test_vendor_email_blocked(self):
        ret = {"to": "orders@greatlakesfurniture.com", "subject": "Meridian Partners - Incomplete Invoice GLFD-0441",
               "body": "Dear Derek Paulson, ..."}
        self.assertIn("comms.messages", self.pre("google_mail__save_draft", ret))


class SlackRouting(Base):
    def test_wrong_channel_blocked(self):
        self.assertIn("comms.messages", self.pre("slack__post_message", dict(SLACK, channel_id="C003")))

    def test_dm_blocked(self):
        self.assertIn("comms.messages", self.pre("slack__send_dm", {"user_id": "U002", "text": SLACK["text"]}))

    def test_unrelated_slack_free(self):
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C004", "text": "Batch confirmed."}), set())


class RegisterRow(Base):
    def test_row_required(self):
        self.assertIn("register.glfd_row", self.done())
        self.edit("ap_ledger.xlsx", GOOD_ROW, "Invoice Register")
        self.assertNotIn("register.glfd_row", self.done())

    def test_blank_due_date_flagged(self):
        self.edit("ap_ledger.xlsx", ROW.format(due="None", status="'APPR'"), "Invoice Register")
        self.assertIn("2026-04-19", self.done().get("register.glfd_row", ""))

    def test_paid_status_flagged(self):
        self.edit("ap_ledger.xlsx", ROW.format(due="dt.datetime(2026,4,19)", status="'Paid'"), "Invoice Register")
        self.assertIn("register.glfd_row", self.done())

    def test_open_status_not_flagged(self):
        self.edit("ap_ledger.xlsx", ROW.format(due="'2026-04-19'", status="'Open'"), "Invoice Register")
        self.assertNotIn("register.glfd_row", self.done())

    def test_wrong_gl_flagged(self):
        self.edit("ap_ledger.xlsx", GOOD_ROW.replace("1000-100-6200", "1000-100-6500"), "Invoice Register")
        self.assertIn("register.glfd_row", self.done())

    def test_check_method_flagged(self):
        self.edit("ap_ledger.xlsx", GOOD_ROW.replace("'ACH'", "'Check'"), "Invoice Register")
        self.assertIn("register.glfd_row", self.done())

    def test_duplicate_row_flagged(self):
        self.edit("ap_ledger.xlsx", GOOD_ROW + "\n" + GOOD_ROW.split("\n", 1)[1], "Invoice Register")
        self.assertIn("register.glfd_row", self.done())


class AppendOnly(Base):
    def test_register_existing_row_edit(self):
        self.edit("ap_ledger.xlsx", GOOD_ROW + "\nws.cell(row=11, column=col['Status'], value='Open')",
                  "Invoice Register")
        self.assertIn("register.append_only", self.done())

    def test_po_register_edit(self):
        self.edit("ap_ledger.xlsx", "ws.cell(row=9, column=col['GR Qty'], value=1)", "PO Register")
        self.assertIn("ledger.po_register_unchanged", self.done())

    def test_payment_queue_edit(self):
        self.edit("ap_ledger.xlsx", "ws.cell(row=8, column=col['Status'], value='Paid')", "Payment Queue")
        self.assertIn("ledger.payment_queue_unchanged", self.done())

    def test_gl_postings_edit(self):
        self.edit("ap_ledger.xlsx", "ws.cell(row=25, column=col['Posted By'], value='X')", "GL Postings")
        self.assertIn("ledger.gl_postings_unchanged", self.done())


class NoPaymentOrPosting(Base):
    def test_payment_queue_row_flagged(self):
        self.golden()
        self.edit("ap_ledger.xlsx", "ws.append(['PAY-2026-0324-003','GLFD-0441','V-00009','Great Lakes',7900,0,7900,"
                                    "'ACH',None,'Pending','Pending'])", "Payment Queue")
        self.assertIn("ledger.no_payment_or_posting", self.done())

    def test_gl_posting_row_flagged(self):
        self.golden()
        self.edit("ap_ledger.xlsx", "ws.append(['JE-2026-0090',None,'1000-100-6200','Office Supplies',7900,None,"
                                    "'GLFD-0441','Furniture','J. Trevors'])", "GL Postings")
        self.assertIn("ledger.no_payment_or_posting", self.done())

    def test_clean(self):
        self.golden()
        self.assertNotIn("ledger.no_payment_or_posting", self.done())


class Files(Base):
    def test_vendor_master_edit_flagged(self):
        self.golden()
        self.edit("vendor_master.xlsx", "ws.cell(row=12, column=col['Payment Terms'], value='Net 45')")
        self.assertIn("files.unchanged", self.done())

    def test_match_log_row_flagged(self):
        self.golden()
        self.edit("match_log_2026_Q1.xlsx", "ws.append(['2026-03-24','GLFD-0441'])")
        self.assertIn("files.unchanged", self.done())

    def test_resave_without_change_ok(self):
        self.golden()
        self.edit("match_log_2026_Q1.xlsx", "pass")
        self.edit("vendor_master.xlsx", "pass")
        self.assertEqual(self.done(), {})

    def test_new_workbook_flagged(self):
        self.golden()
        import shutil
        shutil.copy(self.tmp / "workdir" / "ap_ledger.xlsx", self.tmp / "workdir" / "ap_ledger_backup.xlsx")
        self.assertIn("files.unchanged", self.done())


if __name__ == "__main__":
    unittest.main()
