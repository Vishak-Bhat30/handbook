"""Blind unit tests for finance_sunshine_set_7c041148 (fixtures from the task seed only)."""

from __future__ import annotations

import shutil

from interwhen_sop.tests.base import TaskCase

T = "finance_sunshine_set_7c041148"
D = "@sunshineandsetauto.com"
HELD = "Held - Returned Check"

TPL_A_BODY = (
    "The posted deal gross for Deal #10057 (Flores, Stock #N16028, VIN ending 9342FK) does not tie to the approved "
    "desk recap.\n\nApproved gross: $7,500 Posted gross: $6,700 Variance: $800\n\n"
    "Source of difference: other — incorrect accessory charge on the desk recap (confirmed by Marcus Hale).\n\n"
    "Please confirm the correct figure or provide an updated approval so the deal can be finalized. The deal will "
    "remain unposted until this is resolved.\n\nAttach: deal log excerpt.")
TPL_A = {"to": f"olivia.mercer{D}", "cc": f"sofia.ramirez{D}",
         "subject": "Deal Gross Variance — Deal #10057 / Flores", "body": TPL_A_BODY}
HOLD = {"channel_id": "C003", "text": "HOLD NOTICE: Deal #10091 | Customer: Patricia Morris | Hold reason: returned "
                                      "check $2,300 (R02 Account Closed) | Date: 03/26/2027. Please suspend title work."}
CUST = {"to": "patricia2000@aol.com", "subject": "Returned Payment Notice — Deal #10091",
        "body": "Dear Ms. Morris,\n\nYour check for $2,300.00 deposited 03/12/2027 was returned by your bank on "
                "03/25/2027 (Account Closed). Please contact us to arrange replacement payment."}
MGMT = {"to": f"marcus.hale{D}, elena.brooks{D}", "subject": "Returned Check — Deal #10091 / Morris — $2,300",
        "body": "Deal #10091, Patricia Morris: check $2,300.00 returned 03/25/2027, R02 Account Closed. Title on hold."}
RENEE = {"user_id": "U019", "text": "Renee - returned item: Deal #10091 Patricia Morris $2,300 check returned "
                                    "03/25/2027 (R02). Logged in the cash exception log."}
ORTIZ = {"to": f"marcus.hale{D}", "subject": "Review required — Deal #10099 / Ortiz",
         "body": "Deal #10099 (Andrew Ortiz, Stock #N26043, VIN 18TD0REAP8F6D030D): F&I recap total gross $8,224 vs "
                 "deal log $8,220, variance $4. Total gross > $5,000 so not posted pending your review."}

SET = "for r in range(2, ws.max_row + 1):\n    if ws.cell(r, 1).value == {deal}:\n        ws.cell(r, col[{c!r}]).value = {v!r}\n"
CASH_ROW = (
    "import datetime\nr = ws.max_row + 1\n"
    "vals = {{'Entry #': 8, 'Exception Date': datetime.datetime(2027, 3, 26), 'Exception Type': 'Returned Check (Closed Acct)',"
    " 'Deal #': {deal}, 'Customer Name': 'Patricia Morris', 'Original Deposit Date': datetime.datetime(2027, 3, 12),"
    " 'Return/Notice Date': {ret}, 'Payment Method': 'Check', 'Original Amount': 2300, 'Variance / Return Amount': 2300,"
    " 'Bank Return Reason Code': 'R02 – Account Closed', 'Investigation Status': 'Open',"
    " 'Escalated To': 'Marcus Hale; Elena Brooks', 'Escalation Date': datetime.datetime(2027, 3, 26)}}\n"
    "for k, v in vals.items():\n    ws.cell(r, col[k]).value = v\n")


class Base(TaskCase):
    TASK = T

    def set_deal(self, sheet, deal, column, value, fname="deal_log.xlsx"):
        self.edit(fname, SET.format(deal=deal, c=column, v=value), sheet)

    def cash_row(self, deal=10091, ret="datetime.datetime(2027, 3, 25)", fname="cash_exception_log.xlsx"):
        self.edit(fname, CASH_ROW.format(deal=deal, ret=ret))

    def golden(self):
        self.set_deal("Q1 2027", 10091, "Title Status", HELD)
        self.set_deal("Q4 2026", 10057, "Notes", "03/26/2027: Marcus Hale confirmed desk recap error; posted $6,700 approved.")
        self.cash_row()
        self.did("google_mail__send_email", TPL_A)
        self.did("slack__post_message", HOLD)
        self.did("google_mail__send_email", CUST)
        self.did("google_mail__send_email", MGMT)
        self.did("slack__send_dm", RENEE)
        self.did("google_mail__send_email", ORTIZ)


class TestGolden(Base):
    def test_initial_obligations(self):
        self.assertEqual(set(self.done()), {"comms.messages_sent", "deal.ortiz_escalation", "deal.flores_note",
                                            "deal.title_hold", "cash.returned_check_logged",
                                            "notify.returned_check_mgmt", "notify.renee"})

    def test_golden_path(self):
        self.golden()
        self.assertEqual(self.done(), {})

    def test_golden_path_in_v2_copies(self):
        wd = self.tmp / "workdir"
        shutil.copy(wd / "deal_log.xlsx", wd / "deal_log_v2.xlsx")
        shutil.copy(wd / "cash_exception_log.xlsx", wd / "cash_exception_log_v2.xlsx")
        self.set_deal("Q1 2027", 10091, "Title Status", HELD, "deal_log_v2.xlsx")
        self.set_deal("Q4 2026", 10057, "Notes", "Desk recap error confirmed by Marcus Hale.", "deal_log_v2.xlsx")
        self.cash_row(fname="cash_exception_log_v2.xlsx")
        for tool, args in (("google_mail__send_email", TPL_A), ("slack__post_message", HOLD),
                           ("google_mail__send_email", CUST), ("google_mail__send_email", MGMT),
                           ("slack__send_dm", RENEE), ("google_mail__send_email", ORTIZ)):
            self.did(tool, args)
        self.assertEqual(self.done(), {})


class TestTemplateA(Base):
    def test_compliant(self):
        self.assertNotIn("comms.messages", self.pre("google_mail__send_email", TPL_A))
        self.did("google_mail__send_email", TPL_A)
        self.assertFalse(any("Template A" in p for r, p in self.done_all() if r == "comms.messages_sent"))

    def test_wrong_figures(self):
        bad = dict(TPL_A, body=TPL_A_BODY.replace("$7,500", "$7,493").replace("$800", "$793"))
        self.assertIn("comms.messages", self.pre("google_mail__send_email", bad))

    def test_wrong_subject(self):
        self.assertIn("comms.messages", self.pre("google_mail__send_email", dict(TPL_A, subject="Flores desk recap")))

    def test_wrong_recipient(self):
        bad = dict(TPL_A, to=f"marcus.hale{D}", cc="")
        self.assertIn("comms.messages", self.pre("google_mail__send_email", bad))

    def test_draft_is_not_sending(self):
        self.assertIn("comms.messages", self.pre("google_mail__create_draft", TPL_A))

    def test_reply_to_marcus_not_captured(self):
        self.assertEqual(self.pre("google_mail__reply_email", {"email_id": "1", "body": "Noted on Flores #10057."}),
                         set())


class TestTitleHold(Base):
    def test_compliant(self):
        self.assertNotIn("comms.messages", self.pre("slack__post_message", HOLD))

    def test_missing_date(self):
        bad = dict(HOLD, text="Hold on Deal #10091 Patricia Morris - returned check.")
        self.assertIn("comms.messages", self.pre("slack__post_message", bad))

    def test_required(self):
        self.assertTrue(any("titles-billing" in p for r, p in self.done_all() if r == "comms.messages_sent"))
        self.did("slack__post_message", HOLD)
        self.assertFalse(any("titles-billing" in p for r, p in self.done_all() if r == "comms.messages_sent"))


class TestCustomerNotice(Base):
    def test_compliant(self):
        self.assertNotIn("comms.messages", self.pre("google_mail__send_email", CUST))
        self.did("google_mail__send_email", CUST)
        self.assertFalse(any("customer" in p for r, p in self.done_all() if r == "comms.messages_sent"))

    def test_missing_amount(self):
        bad = dict(CUST, body="Dear Ms. Morris, your check was returned. Please call us.")
        self.assertIn("comms.messages", self.pre("google_mail__send_email", bad))


class TestPreRules(Base):
    def test_placeholders(self):
        bad = dict(TPL_A, body=TPL_A_BODY + "\n[Customer Last Name]")
        self.assertIn("comms.no_placeholders", self.pre("google_mail__send_email", bad))
        self.assertNotIn("comms.no_placeholders", self.pre("google_mail__send_email", TPL_A))

    def test_iso_dates(self):
        self.assertIn("dates.format", self.pre("slack__send_dm", {"user_id": "U013", "text": "Returned 2027-03-25."}))
        self.assertNotIn("dates.format", self.pre("slack__send_dm", {"user_id": "U013", "text": "Returned 03/25/2027."}))

    def test_unlisted_tools(self):
        self.assertIn("tools.unlisted", self.pre("jira__create_issue", {"project_key": "ACC", "summary": "x"}))
        self.assertNotIn("tools.unlisted", self.pre("jira__search_issues", {"jql": "x"}))

    def test_source_docs(self):
        self.assertIn("files.source_docs", self.pre("syntara__writeFile", {
            "file_path": "/workdir/20270321_10099_Ortiz_6D030D.pdf", "content": "x"}))
        self.assertNotIn("files.source_docs", self.pre("syntara__writeFile", {
            "file_path": "/workdir/20270321_10099_Ortiz_6D030D_v2.pdf", "content": "x"}))


class TestOrtiz(Base):
    def test_posting_blocked_at_completion(self):
        self.assertNotIn("deal.ortiz_not_posted", self.done())
        self.set_deal("Q1 2027", 10099, "Posting Date", "03/26/2027")
        self.assertIn("deal.ortiz_not_posted", self.done())

    def test_escalation_email(self):
        self.did("google_mail__send_email", ORTIZ)
        self.assertNotIn("deal.ortiz_escalation", self.done())

    def test_escalation_missing_stock(self):
        self.did("slack__send_dm", {"user_id": "U013", "text": "Ortiz Deal #10099 needs review, $4 variance."})
        self.assertIn("deal.ortiz_escalation", self.done())

    def test_escalation_in_deal_posting_channel(self):
        self.did("slack__post_message", {"channel_id": "C001", "text": "@marcus.hale Deal #10099 (Ortiz, Stock "
                                         "#N26043): recap $8,224 vs log $8,220 ($4 variance); holding posting."})
        self.assertNotIn("deal.ortiz_escalation", self.done())

    def test_escalation_wrong_channel(self):
        self.did("slack__post_message", {"channel_id": "C004", "text": "@marcus.hale Deal #10099 (Ortiz, Stock "
                                         "#N26043): $4 variance."})
        self.assertIn("deal.ortiz_escalation", self.done())


class TestFlores(Base):
    def test_note(self):
        self.assertIn("deal.flores_note", self.done())
        self.set_deal("Q4 2026", 10057, "Notes", "Marcus Hale approved posted gross $6,700; desk recap in error.")
        self.assertNotIn("deal.flores_note", self.done())

    def test_gross_kept(self):
        self.assertNotIn("deal.flores_gross", self.done())
        self.set_deal("Q4 2026", 10057, "Total Deal Gross", 7500)
        self.assertIn("deal.flores_gross", self.done())


class TestReturnedCheck(Base):
    def test_title_hold(self):
        self.set_deal("Q1 2027", 10091, "Title Status", "On Hold")
        self.assertIn("deal.title_hold", self.done())
        self.set_deal("Q1 2027", 10091, "Title Status", HELD)
        self.assertNotIn("deal.title_hold", self.done())

    def test_cash_row_ok(self):
        self.cash_row()
        self.assertNotIn("cash.returned_check_logged", self.done())
        self.assertNotIn("cash.log_integrity", self.done())

    def test_cash_row_wrong_deal(self):
        self.cash_row(deal=10068)
        self.assertIn("10091", self.done().get("cash.returned_check_logged", ""))

    def test_cash_row_wrong_return_date(self):
        self.cash_row(ret="'03/12/2027'")
        self.assertIn("Return/Notice Date", self.done().get("cash.returned_check_logged", ""))

    def test_cash_log_append_only(self):
        self.edit("cash_exception_log.xlsx", "ws.cell(2, col['Investigation Status']).value = 'Open'")
        self.assertIn("cash.log_integrity", self.done())

    def test_cash_log_unrequested_row(self):
        self.edit("cash_exception_log.xlsx", "ws.cell(ws.max_row + 1, 1).value = 9\n"
                                             "ws.cell(ws.max_row, col['Deal #']).value = 10099")
        self.assertIn("cash.log_integrity", self.done())

    def test_mgmt_report(self):
        self.did("google_mail__send_email", dict(MGMT, to=f"marcus.hale{D}"))
        f = [p for r, p in self.done_all() if r == "notify.returned_check_mgmt"]
        self.assertEqual(len(f), 1)
        self.assertIn("Elena Brooks", f[0])
        self.did("slack__send_dm", {"user_id": "U012", "text": "Returned check Deal #10091 Morris $2,300 (R02)."})
        self.assertNotIn("notify.returned_check_mgmt", self.done())

    def test_renee(self):
        self.assertIn("notify.renee", self.done())
        self.did("slack__send_dm", RENEE)
        self.assertNotIn("notify.renee", self.done())


class TestDealLogIntegrity(Base):
    def test_in_scope_change_ok(self):
        self.set_deal("Q1 2027", 10091, "Title Status", HELD)
        self.assertNotIn("deal.log_integrity", self.done())

    def test_wrong_morris_deal(self):
        self.edit("deal_log.xlsx", "for r in range(2, ws.max_row + 1):\n"
                                   "    if ws.cell(r, col['Customer Name']).value == 'Patricia Morris':\n"
                                   "        ws.cell(r, col['Title Status']).value = 'Held - Returned Check'\n", "Q4 2026")
        self.assertIn("deal.log_integrity", self.done())

    def test_doc_fee_change(self):
        self.set_deal("Q1 2027", 10099, "Doc Fee", 0)
        self.assertIn("Doc Fee", self.done().get("deal.log_integrity", ""))
