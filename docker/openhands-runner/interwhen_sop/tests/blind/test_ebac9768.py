"""Blind unit tests for finance_sunshine_set_ebac9768 (fixtures from the task's environment seed only)."""

from __future__ import annotations

from interwhen_sop.tests.base import TaskCase

ELENA = "elena.brooks@sunshineauto.com"
MAIL = "google_mail__send_email"
POST = "slack__post_message"
DM = "slack__send_dm"

TPL_F_SUBJECT = "Chargeback Escalation — $2,800.00 — 1 Open Items Over 15 Days"
TPL_F_BODY = ("The following chargeback(s) have been open for more than 15 days or exceed the $2,500 threshold and "
              "require your review:\nDeal # SL-2026-0412 | Customer Johnson | Product Type Vehicle Service Contract | "
              "Chargeback Amount $2,800.00 | Date Received 2026-04-14 | Days Open 0 | Status Disputed - held\n"
              "Summary of actions taken: verified against deal; amount exceeds the $1,895 premium.\n"
              "Recommended next step: hold posting pending provider backup.\n"
              "Attach: chargeback tracker extract and combined support packet.")
STIP_POST = ("@noah.alvarez Deal SL-2026-0412 (Johnson), Wells Fargo: missing stips Power of Attorney and Payoff "
             "Letter. Funding deadline end of business today, April 14, 2026. Please request from F&I.")
CASH_DM = "Elena - Johnson SL-2026-0412 deposit batch 20260414-001 is short $180 (cash discrepancy), unresolved."
FUND_MAIL = ("Deal SL-2026-0412 Johnson, Wells Fargo, $30,500, unfunded 6 days. Outstanding stips: Power of Attorney, "
             "Payoff Letter (due today). Next steps: Noah following up with F&I.")
PAYOFF_MAIL = ("Chase payoff variance $290 (quoted $11,250, applied $11,540). Original total gross $5,000; recalculated "
               "total gross $4,710 (front $2,910). SOP 2.1 threshold classification: $51-$500 tier.")
FLOOR_POST = ("@darius.kim 8XJ472 / N240412 (Johnson, SL-2026-0412) is sold-not-paid, delivered 04/08, past the "
              "3-business-day payoff window; potential out-of-trust exposure.")


class Ebac9768(TaskCase):
    TASK = "finance_sunshine_set_ebac9768"

    def mail(self, to, subject, body, cc=None):
        args = {"to": to, "subject": subject, "body": body}
        if cc:
            args["cc"] = cc
        return args

    def golden_comms(self):
        self.did(MAIL, self.mail(ELENA, TPL_F_SUBJECT, TPL_F_BODY))
        self.did(POST, {"channel_id": "C002", "text": STIP_POST})
        self.did(DM, {"user_id": "U001", "text": CASH_DM})
        self.did(MAIL, self.mail(ELENA, "Funding Escalation — Deal SL-2026-0412", FUND_MAIL))
        self.did(MAIL, self.mail(ELENA, "Trade Payoff Variance — Deal SL-2026-0412", PAYOFF_MAIL))
        self.did(POST, {"channel_id": "C001", "text": FLOOR_POST})
        self.did("syntara__writeFile", {"file_path": "/workdir/actions_summary.txt", "content": "x" * 80})
        self.write("actions_summary.txt", "Actions taken and rationale for each escalation path. " * 3)

    # ---- initial state -------------------------------------------------------------------------
    def test_initial_obligations(self):
        got = self.done()
        self.assertEqual(set(got), {"ebac.comms.messages_sent", "ebac.controller_reports", "ebac.floorplan_slack",
                                    "ebac.actions_summary"})
        msgs = [p for r, p in self.done_all() if r == "ebac.controller_reports"]
        self.assertEqual(len(msgs), 3)

    def test_golden_path(self):
        self.golden_comms()
        self.edit("daily_cash_log.xlsx", "ws.cell(2, col['Status']).value = 'Discrepancy - Escalated; report held'")
        self.edit("chargeback_tracker.xlsx", "ws.cell(2, col['Status']).value = 'Escalated - Pending Review'")
        self.assertEqual(self.done(), {})

    # ---- Template F --------------------------------------------------------------------------------
    def test_template_f_ok(self):
        self.assertEqual(self.pre(MAIL, self.mail(ELENA, TPL_F_SUBJECT, TPL_F_BODY)), set())

    def test_template_f_pdf_subject_ok(self):
        self.assertEqual(self.pre(MAIL, self.mail(ELENA, "High-Value Chargeback Requiring Immediate Action",
                                                  TPL_F_BODY)), set())

    def test_template_f_bad_subject(self):
        self.assertIn("ebac.comms.messages", self.pre(MAIL, self.mail(ELENA, "Johnson chargeback", TPL_F_BODY)))

    def test_template_f_missing_fields(self):
        body = "Chargeback on SL-2026-0412 Johnson VSC for $2,800. Please review."
        self.assertIn("ebac.comms.messages", self.pre(MAIL, self.mail(ELENA, TPL_F_SUBJECT, body)))

    def test_template_f_other_recipient_not_matched(self):
        self.assertEqual(self.pre(MAIL, self.mail("marcus.hale@sunshineauto.com", "Chargeback question", "hi")),
                         set())

    def test_template_f_required(self):
        self.did(MAIL, self.mail("marcus.hale@sunshineauto.com", TPL_F_SUBJECT, TPL_F_BODY))
        probs = [p for r, p in self.done_all() if r == "ebac.comms.messages_sent"]
        self.assertTrue(any("Template F" in p for p in probs))
        self.did(MAIL, self.mail(ELENA, TPL_F_SUBJECT, TPL_F_BODY, cc="marcus.hale@sunshineauto.com"))
        probs = [p for r, p in self.done_all() if r == "ebac.comms.messages_sent"]
        self.assertFalse(any("Template F" in p for p in probs))

    # ---- stip request ------------------------------------------------------------------------------
    def test_stip_post_ok(self):
        self.assertEqual(self.pre(POST, {"channel_id": "C002", "text": STIP_POST}), set())

    def test_stip_post_missing_deadline(self):
        text = "@noah.alvarez SL-2026-0412 Johnson, Wells Fargo: missing Power of Attorney and Payoff Letter."
        self.assertIn("ebac.comms.messages", self.pre(POST, {"channel_id": "C002", "text": text}))

    def test_stip_post_other_channel_not_matched(self):
        self.assertEqual(self.pre(POST, {"channel_id": "C004", "text": "SL-2026-0412 Johnson POA stip"}), set())

    def test_stip_post_required(self):
        self.did(POST, {"channel_id": "C002", "text": STIP_POST})
        probs = [p for r, p in self.done_all() if r == "ebac.comms.messages_sent"]
        self.assertFalse(any("Missing-stip" in p for p in probs))

    # ---- Controller reports -------------------------------------------------------------------------
    def _ctrl(self):
        return [p for r, p in self.done_all() if r == "ebac.controller_reports"]

    def test_cash_report_ok(self):
        self.did(DM, {"user_id": "U001", "text": CASH_DM})
        self.assertFalse(any("$180 cash" in p for p in self._ctrl()))

    def test_cash_report_to_marcus_not_enough(self):
        self.did(DM, {"user_id": "U002", "text": CASH_DM})
        self.assertTrue(any("$180 cash" in p for p in self._ctrl()))

    def test_funding_ok_via_cc(self):
        self.did(MAIL, self.mail("marcus.hale@sunshineauto.com", "Funding", FUND_MAIL, cc=ELENA))
        self.assertFalse(any("unfunded Wells Fargo" in p for p in self._ctrl()))

    def test_funding_marcus_only(self):
        self.did(MAIL, self.mail("marcus.hale@sunshineauto.com", "Funding", FUND_MAIL))
        self.assertTrue(any("unfunded Wells Fargo" in p for p in self._ctrl()))

    def test_payoff_ok(self):
        self.did(DM, {"user_id": "U001", "text": PAYOFF_MAIL})
        self.assertFalse(any("$290 Chase" in p for p in self._ctrl()))

    def test_payoff_wrong_recalc(self):
        self.did(DM, {"user_id": "U001", "text": PAYOFF_MAIL.replace("4,710", "5,290")})
        self.assertTrue(any("$290 Chase" in p for p in self._ctrl()))

    def test_payoff_25000_is_not_5000(self):
        text = "Payoff variance $290 on a $25,000+ deal; recalculated total gross $4,710; tier $51-$500."
        self.did(MAIL, self.mail(ELENA, "Payoff", text))
        self.assertTrue(any("$290 Chase" in p for p in self._ctrl()))

    # ---- floorplan --------------------------------------------------------------------------------
    def test_floorplan_ok(self):
        self.did(POST, {"channel_id": "C001", "text": FLOOR_POST})
        self.assertNotIn("ebac.floorplan_slack", self.done())

    def test_floorplan_wrong_channel(self):
        self.did(POST, {"channel_id": "C003", "text": FLOOR_POST})
        self.assertIn("ebac.floorplan_slack", self.done())

    # ---- cash log ---------------------------------------------------------------------------------
    def test_cash_log_closed(self):
        self.edit("daily_cash_log.xlsx", "ws.cell(2, col['Status']).value = 'Resolved'")
        self.assertIn("ebac.cash_report_open", self.done())

    def test_cash_log_amount_changed(self):
        self.edit("daily_cash_log.xlsx", "ws.cell(2, col['Actual Amount']).value = 3500\n"
                                         "ws.cell(2, col['Variance']).value = 0")
        self.assertIn("ebac.cash_report_open", self.done())

    def test_cash_log_escalated_ok(self):
        self.edit("daily_cash_log.xlsx", "ws.cell(2, col['Status']).value = 'Discrepancy - Escalated'")
        self.assertNotIn("ebac.cash_report_open", self.done())

    def test_cash_log_v2_copy_closed(self):
        # saves the edited copy as daily_cash_log_v2.xlsx; the original stays untouched
        self.edit("daily_cash_log.xlsx", "ws.cell(2, col['Status']).value = 'OK'\n"
                                         "path = path.replace('.xlsx', '_v2.xlsx')")
        self.assertTrue((self.tmp / "workdir" / "daily_cash_log_v2.xlsx").exists())
        self.assertIn("ebac.cash_report_open", self.done())

    # ---- chargeback tracker ------------------------------------------------------------------------
    def test_chargeback_offset_applied(self):
        self.edit("chargeback_tracker.xlsx", "ws.cell(2, col['Commission Offset Applied']).value = 'Yes'")
        self.assertIn("ebac.chargeback_not_posted", self.done())

    def test_chargeback_posted_status(self):
        self.edit("chargeback_tracker.xlsx", "ws.cell(2, col['Status']).value = 'Posted'")
        self.assertIn("ebac.chargeback_not_posted", self.done())

    def test_chargeback_pending_ok(self):
        self.edit("chargeback_tracker.xlsx", "ws.cell(2, col['Status']).value = 'Escalated - Pending Review'\n"
                                             "ws.cell(2, col['Escalation Required']).value = 'Yes - Template F sent'")
        self.assertNotIn("ebac.chargeback_not_posted", self.done())

    def test_chargeback_duplicate_row(self):
        self.edit("chargeback_tracker.xlsx", "ws.append([c.value for c in ws[2]])")
        self.assertIn("ebac.chargeback_not_posted", self.done())

    # ---- deal log ---------------------------------------------------------------------------------
    def test_deal_gross_adjusted(self):
        self.edit("deal_log.xlsx", "ws.cell(2, col['Front Gross']).value = 2910\n"
                                   "ws.cell(2, col['Total Gross']).value = 4710", sheet="Deal Log")
        self.assertIn("ebac.deal_gross_unchanged", self.done())

    def test_deal_log_note_ok(self):
        self.edit("deal_log.xlsx", "ws.cell(2, col['Days Unfunded']).value = 6", sheet="Deal Log")
        self.assertNotIn("ebac.deal_gross_unchanged", self.done())

    # ---- summary / placeholders --------------------------------------------------------------------
    def test_summary_written(self):
        self.write("actions_summary.txt", "Summary of all actions and escalation rationale for the Johnson deal.")
        self.assertNotIn("ebac.actions_summary", self.done())

    def test_placeholder_blocked(self):
        self.assertIn("comms.no_placeholders",
                      self.pre(DM, {"user_id": "U001", "text": "Customer: [Customer Name] short $180"}))

    def test_checkbox_not_placeholder(self):
        self.assertNotIn("comms.no_placeholders",
                         self.pre(MAIL, self.mail(ELENA, TPL_F_SUBJECT, TPL_F_BODY + "\nCommission Offset: [X] No")))
