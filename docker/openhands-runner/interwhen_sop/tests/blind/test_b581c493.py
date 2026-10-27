"""Blind unit tests for finance_sunshine_set_b581c493 (fixtures from the task environment seed only)."""

from __future__ import annotations

from interwhen_sop.tests.base import TaskCase

T = "finance_sunshine_set_b581c493"
V = "interwhen_sop.verifiers." + T

TPL_A = ("The posted deal gross for Deal #4481 (Hernandez, Stock #U-2241, VIN ending 109189) does not tie to the approved "
         "desk recap.\n\nApproved gross: $9,200.00\nPosted gross: $9,550.00\nVariance: $350.00\n\n"
         "Source of difference: trade allowance — re-entered near the end of the deal.\n\n"
         "Please confirm the correct figure or provide an updated approval so the deal can be finalized. The deal will "
         "remain unposted until this is resolved.\n\nAttach: buyer's order, desk recap, and deal log excerpt showing the "
         "discrepancy.\n\nJasmine Patel | Senior Deal Posting Specialist")
VAR = ("Deal #4481 / Hernandez – gross variance. Approved: $9,200.00 | Posted: $9,550.00 | Variance: $350.00. "
       "Delivery: 02:30 PM. @marcus.hale please review before posting.\n— Jasmine Patel")
LEAD = "ESCALATION — Deal #4481 / Hernandez | Variance: $350.00 | Delivery: 02:30 PM. @derrick.soto\n— Jasmine Patel"
PAYOFF = ("Payoff error — Wells Fargo Dealer Services Ref WFB-2026-DPO-88491 / Deal #4477 / Morales. Payment applied to "
          "wrong account. @priya.bennett @marcus.hale – same day resolution required.\n— Jasmine Patel")
CB = ("Chargeback received — CB Ref CB-2608 / Castellano / $1,600.00. @sofia.ramirez @hannah.price @marcus.hale — "
      "Marcus Hale approval required.\n— Jasmine Patel")
TPL_H = ("Hi Trent Holloway, thank you for reaching out. This request falls outside of my jobs scope. I have forwarded "
         "your request to Darius Kim who can assist you directly.\n\nJasmine Patel")

SOFIA = "sofia.ramirez@sunshineandsetauto.com"
PRIYA = "priya.bennett@sunshineandsetauto.com"
DARIUS = "darius.kim@sunshineandsetauto.com"

ROW_EDIT = """
hrow = next(r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value in ({key_hdr!r},))
cols = {{str(ws.cell(hrow, c).value).replace('\\n', ' '): c for c in range(1, ws.max_column + 1)}}
row = next(r for r in range(hrow + 1, ws.max_row + 1) if str(ws.cell(r, 1).value) == {key!r})
ws.cell(row, cols[{col!r}]).value = {val!r}
"""


class B581(TaskCase):
    TASK = T

    def set_cell(self, fname, sheet, key_hdr, key, col, val):
        self.edit(fname, ROW_EDIT.format(key_hdr=key_hdr, key=key, col=col, val=val), sheet)

    def post(self, ch, text):
        return ("slack__post_message", {"channel_id": ch, "text": text})

    def everything(self):
        self.did("google_mail__send_email", {"to": SOFIA, "cc": "marcus.hale@sunshineandsetauto.com",
                                             "subject": "Deal Gross Variance — Deal #4481 / Hernandez", "body": TPL_A})
        self.did(*self.post("C001", VAR))
        self.did(*self.post("C013", LEAD))
        self.did(*self.post("C011", PAYOFF))
        self.did("google_mail__forward_email", {"email_id": "email-001", "to": PRIYA, "body": "Priya, for your action."})
        self.did(*self.post("C009", CB))
        self.did("google_mail__reply_email", {"email_id": "email-004", "body": TPL_H})
        self.did("google_mail__forward_email", {"email_id": "email-004", "to": DARIUS, "body": "Darius, Trent's ACV ask."})
        self.write("Accounting/Chargebacks/2026-04/CB-2608_Castellano_MeridianGAP_notice.txt", "CB-2608 notice")

    # ---- golden path / initial state ----
    def test_initial_state_lists_outstanding_obligations(self):
        got = self.done_all()
        rules = {r for r, _ in got}
        self.assertEqual(rules, {"b581.dealvar.messages_sent", "b581.payoff.messages_sent",
                                 "b581.chargeback.messages_sent", "b581.redirect.messages_sent", "b581.cb_backup"})
        self.assertEqual(len(got), 9)

    def test_golden_path(self):
        self.everything()
        self.set_cell("chargeback_tracker.xlsx", None, "CB Ref #", "CB-2608", "Status", "Formal Notice Received — Posting")
        self.set_cell("chargeback_tracker.xlsx", None, "CB Ref #", "CB-2608", "Notes / Actions",
                      "Received 4/24; notice posted to #acct-chargebacks")
        self.set_cell("deal_log.xlsx", "Deal Log", "Deal #", "4481", "Notes", "Variance $350 escalated to M. Hale 4/24")
        self.assertEqual(self.done(), {})

    # ---- deal 4481 variance ----
    def test_template_a(self):
        ok = {"to": SOFIA, "subject": "Deal Gross Variance — Deal #4481 / Hernandez", "body": TPL_A}
        self.assertEqual(self.pre("google_mail__send_email", ok), set())
        self.assertIn("b581.dealvar.messages", self.pre("google_mail__send_email", {**ok, "subject": "Deal 4481 variance"}))
        self.assertIn("b581.dealvar.messages", self.pre("google_mail__send_email",
                                                         {**ok, "body": TPL_A.replace("$350.00", "-$350.00")}))
        self.assertIn("b581.dealvar.messages", self.pre("google_mail__send_email",
                                                         {**ok, "to": "marcus.hale@sunshineandsetauto.com"}))

    def test_deal_posting_post(self):
        self.assertEqual(self.pre(*self.post("C001", VAR)), set())
        self.assertEqual(self.pre(*self.post("C001", VAR.replace("02:30", "2:30"))), set())
        self.assertIn("b581.dealvar.messages", self.pre(*self.post("C008", VAR)))
        self.assertIn("b581.dealvar.messages", self.pre(*self.post("C001", VAR.replace("@marcus.hale", "@elena.brooks"))))
        # a same-day DM to Marcus is allowed (SOP 1.5)
        self.assertEqual(self.pre("slack__send_dm", {"user_id": "U002", "text": VAR}), set())

    def test_leadership_post(self):
        self.assertEqual(self.pre(*self.post("C013", LEAD)), set())
        self.assertIn("b581.dealvar.messages", self.pre(*self.post("C013", "Deal 4481 Hernandez has a variance today.")))

    def test_variance_resolved_forbidden(self):
        msg = "Deal #4481 / Hernandez — variance resolved. Cleared for posting per @marcus.hale approval."
        self.assertIn("b581.dealvar.messages", self.pre(*self.post("C001", msg)))

    def test_deal_4481_stays_unposted(self):
        self.set_cell("deal_log.xlsx", "Deal Log", "Deal #", "4481", "Variance Status", "Posted ✓")
        self.assertIn("b581.deal4481_not_posted", self.done())

    def test_deal_4481_pending_note_ok(self):
        self.set_cell("deal_log.xlsx", "Deal Log", "Deal #", "4481", "Variance Status", "PENDING — escalated to M. Hale")
        d = self.done()
        self.assertNotIn("b581.deal4481_not_posted", d)
        self.assertNotIn("b581.logs_intact", d)

    # ---- payoff error ----
    def test_payoff_post(self):
        self.assertEqual(self.pre(*self.post("C011", PAYOFF)), set())
        self.assertEqual(self.pre(*self.post("C011", PAYOFF.replace("WFB-2026-DPO-88491", "REF#90181034"))), set())
        self.assertIn("b581.payoff.messages", self.pre(*self.post("C003", PAYOFF)))
        self.assertIn("b581.payoff.messages", self.pre(*self.post("C011", PAYOFF.replace("@priya.bennett ", ""))))

    def test_lender_reply_blocked(self):
        self.assertIn("b581.payoff.messages", self.pre("google_mail__reply_email",
                                                        {"email_id": "email-001", "body": "We will correct it."}))
        self.assertIn("b581.payoff.messages", self.pre("google_mail__send_email", {
            "to": "payoffs@wellsfargo.com", "subject": "WFB-2026-DPO-88491", "body": "Please reapply."}))
        self.assertEqual(self.pre("google_mail__forward_email", {"email_id": "email-001", "to": PRIYA, "body": "FYI"}),
                         set())

    # ---- chargeback ----
    def test_chargeback_post(self):
        self.assertEqual(self.pre(*self.post("C009", CB)), set())
        self.assertEqual(self.pre(*self.post("C009", CB.replace("Marcus Hale approval", "Assistant Controller approval"))),
                         set())
        self.assertIn("b581.chargeback.messages",
                      self.pre(*self.post("C009", CB.replace("Marcus Hale approval", "Jasmine Patel approval"))))
        self.assertIn("b581.chargeback.messages", self.pre(*self.post("C007", CB)))
        # a payroll-offset note in #acct-payroll-commissions is not the chargeback notice
        self.assertEqual(self.pre(*self.post("C007", "CB-2608 offset for D. Watts — @leah.morgan please confirm.")),
                         set())

    def test_chargeback_backup(self):
        self.assertIn("b581.cb_backup", self.done())
        self.write("Accounting/Chargebacks/2026-04/CB-2608.pdf", b"%PDF-1.4")
        self.assertNotIn("b581.cb_backup", self.done())

    # ---- role-boundary redirect ----
    def test_template_h(self):
        ok = {"email_id": "email-004", "body": TPL_H}
        self.assertEqual(self.pre("google_mail__reply_email", ok), set())
        self.assertIn("b581.redirect.messages", self.pre("google_mail__reply_email",
                                                          {**ok, "body": TPL_H.replace("Trent Holloway", "Trent")}))
        self.assertIn("b581.redirect.messages", self.pre("google_mail__reply_email", {
            "email_id": "email-004", "body": "Hi Trent, U-2196 book cost is $14,200 and U-2203 is $9,800."}))

    def test_forward_to_darius(self):
        self.assertEqual(self.pre("google_mail__forward_email", {"email_id": "email-004", "to": DARIUS, "body": "FYI"}),
                         set())
        self.assertIn("b581.redirect.messages", self.pre("google_mail__send_email", {
            "to": DARIUS, "subject": "Trent ACV request", "body": "Trent wants ACV for U-2196 and U-2203."}))

    def test_no_action_on_acv_request(self):
        self.assertIn("b581.redirect.messages", self.pre(*self.post(
            "C006", "ACV inquiry — Stock U-2196 (2018 Chevy Traverse LT). Pre-wholesale evaluation. @darius.kim")))

    # ---- invariants ----
    def test_logs_intact(self):
        self.set_cell("chargeback_tracker.xlsx", None, "CB Ref #", "CB-2601", "Status", "Reopened")
        self.assertIn("b581.logs_intact", self.done())

    def test_logs_no_new_rows(self):
        self.edit("chargeback_tracker.xlsx", "ws.append(['CB-2608','4/24/26',4451,None,'Castellano'])")
        self.assertIn("b581.logs_intact", self.done())

    def test_logs_notes_ok(self):
        self.set_cell("deal_log.xlsx", "Payoff Control Log", "Deal #", "4477", "Status / Notes",
                      "WFB misapplied ACH; escalated 4/24")
        self.assertNotIn("b581.logs_intact", self.done())

    def test_payoff_log_value_change(self):
        self.set_cell("deal_log.xlsx", "Payoff Control Log", "Deal #", "4477", "Actual Payoff", 12610)
        self.assertIn("b581.logs_intact", self.done())

    def test_protect_files(self):
        self.assertIn("b581.protect_files", self.pre("syntara__executePython",
                                                     {"code": "import os\nos.remove('/workdir/deal_log.xlsx')"}))
        self.assertEqual(self.pre("syntara__executePython", {
            "code": "import openpyxl\nwb=openpyxl.load_workbook('/workdir/deal_log.xlsx')\nprint(wb.sheetnames)"}), set())
        self.assertEqual(self.pre("syntara__executePython", {
            "code": "import os,openpyxl\np='/workdir/chargeback_tracker.xlsx'\nwb=openpyxl.load_workbook(p)\n"
                    "wb.save(p)\nos.remove('/tmp/scratch.txt')"}), set())

    def test_placeholders(self):
        self.assertIn("comms.no_placeholders", self.pre(*self.post("C001", "Deal #4481 / [Customer Last Name] variance")))
        self.assertIn("b581.placeholders", self.pre(*self.post("C001", "Deal #[number] / Hernandez – gross variance")))
        self.assertNotIn("b581.placeholders", self.pre(*self.post("C001", VAR)))
