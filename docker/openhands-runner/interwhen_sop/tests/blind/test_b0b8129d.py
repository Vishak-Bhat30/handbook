"""Unit tests for interwhen_sop/verifiers/finance_sunshine_set_b0b8129d.py (fixtures from the task seed only)."""

from __future__ import annotations

import shutil

from interwhen_sop.tests.base import TaskCase

FP = "Floorplan_Worksheet_April2026.xlsx"
NEW = "Inventory_New_April2026.xlsx"
USED = "Inventory_Used_April2026.xlsx"
MARCUS = "marcus.hale@sunshineandsetauto.com"
ELENA = "elena.brooks@sunshineandsetauto.com"

SLACK_48 = ("N2048: Aged curtailment. 94 days on floor. Curtailment past due since 02/11/2026 (64 days past due). "
            "@marcus.hale @elena.brooks")
SLACK_41 = ("N2041: Sold-not-paid. Deal 4501, Robert Chen. Payoff not sent. @marcus.hale @elena.brooks "
            "Concurrent collection issue: $2,000 NSF, 04/13/2026.")
EMAIL_I = {"to": f"{MARCUS}, {ELENA}", "subject": "Aged Curtailment for N2048",
           "body": "Stock N2048, 2026 Toyota Highlander Platinum. Principal balance: $48,200.\n\n"
                   "Aged curtailment. Curtailment due 02/11/2026, 64 days past due. 94 days on floor.\n\n"
                   "Slack notification sent to #acct-floorplan.\n\nDarius Kim"}
EMAIL_J = {"to": MARCUS, "cc": ELENA, "subject": "Sold-not-paid for N2041",
           "body": "Stock N2041, 2026 Toyota Camry LE. Deal 4501, Robert Chen. Principal balance: $28,250.\n\n"
                   "Sold-not-paid. Payoff not sent. Deadline 04/03/2026, 9 business days past due.\n\n"
                   "Late payoff interest: $185 per lender statement.\n\n"
                   "Concurrent collection issue: $2,000 NSF, 04/13/2026.\n\n"
                   "Slack notification sent to #acct-floorplan."}
REPLY = {"email_id": "9", "body": "Marcus,\n\nReconciliation complete; worksheet ties to $319,750.\n"
                                  "1. N2041 sold-not-paid (Deal 4501).\n2. N2048 aged curtailment.\nDarius"}
U1090_MAIL = {"to": ELENA, "cc": MARCUS, "subject": "U1090 recon escalation",
              "body": "U1090 book cost $31,150 exceeds expected retail $29,500; SBP-4821 recon $5,200 exceeds $5,000."}

FP_CODE = """
def row(s):
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, 1).value == s:
            return r
r = row('N2041')
ws.cell(r, col['Status']).value = 'Sold \u2014 not paid off FP'
ws.cell(r, col['Notes']).value = ('Deal 4501, sold 03/31/2026. Payoff not sent. 3-business-day deadline: 04/03/2026. '
                                  '9 business days past due. Late interest: $185 per lender statement.')
r = row('N2048')
ws.cell(r, col['Curtailment Due Date']).value = '02/11/2026'
ws.cell(r, col['Status']).value = 'Aged Curtailment \u2014 Immediate Escalation'
ws.cell(r, col['Notes']).value = 'Aged curtailment. Due 02/11/2026. 64 days past due. Escalated to Marcus Hale and Elena Brooks.'
ws.append(['N2043', '5TDJZRAH0RS504505', '2026 Toyota Highlander XLE', 'JM Family Enterprises', '04/02/2026', 40100,
           '05/02/2026', 'Reinstated', 14, 'On lot', 'Reinstated after Deal 4505 unwind. Effective 04/16/2026.'])
ws.append(['N2049', '5TFDY5F10RX904516', '2026 Toyota Tundra SR5', 'JM Family Enterprises', '04/15/2026', 34600,
           '05/15/2026', 'In Stock', 1, 'On lot', 'Advance date 04/15/2026. Invoice $34,600.'])
el = wb['Exception Log']
el.append(['04/16/2026', '4501', 'Robert Chen', 'N2041', '$28,250.00', 'JM Family statement 04/16/2026',
           'Accounting Error', 'Marcus Hale; Elena Brooks', 'Escalated via Slack and email', '04/17/2026', 'Open', ''])
"""
NEW_CODE = """
for r in range(2, ws.max_row + 1):
    if ws.cell(r, 1).value == 'N2041':
        ws.cell(r, col['Notes']).value = 'Sold 03/31/2026, funded 04/10/2026. Floorplan payoff NOT sent. Day 16.'
ws.append(['N2049', '5TFDY5F10RX904516', 2026, 'Toyota', 'Tundra', 'SR5', '04/16/2026', 34600, 500, 0, 35100,
           'In Stock', 0, 'Y', None, 'JM Family', 'Stocked 04/16/2026. Invoice $34,600.'])
"""


def set_cell(stock: str, column: str, value: str) -> str:
    return (f"for r in range(2, ws.max_row + 1):\n    if ws.cell(r, 1).value == {stock!r}:\n"
            f"        ws.cell(r, col[{column!r}]).value = {value!r}\n")


class Base(TaskCase):
    TASK = "finance_sunshine_set_b0b8129d"

    def workbooks_done(self, fp: str = FP, new: str = NEW):
        self.edit(fp, FP_CODE, "Floorplan Tracking")
        self.edit(new, NEW_CODE, "New Inventory")

    def slack(self, text: str, channel: str = "C010"):
        self.did("slack__post_message", {"channel_id": channel, "text": text})

    def messages_done(self):
        self.slack(SLACK_48)
        self.slack(SLACK_41)
        self.did("google_mail__send_email", EMAIL_I)
        self.did("google_mail__send_email", EMAIL_J)
        self.did("google_mail__send_email", U1090_MAIL)
        self.did("google_mail__reply_email", REPLY)


class TestInitialAndGolden(Base):
    def test_initial_obligations(self):
        got = self.done()
        self.assertEqual(set(got), {"fp.statement_units", "fp.unit_annotations", "fp.exception_log",
                                    "inv.n2049_stock_in", "inv.n2041_note", "recon.u1090_escalation",
                                    "fp.comms.messages_sent"})

    def test_golden_in_place(self):
        self.workbooks_done()
        self.messages_done()
        self.assertEqual(self.done(), {})

    def test_golden_revised_copies(self):
        for f in (FP, NEW):
            shutil.copy(self.tmp / "workdir" / f, self.tmp / "workdir" / f.replace(".xlsx", "_v2.xlsx"))
        self.workbooks_done(FP.replace(".xlsx", "_v2.xlsx"), NEW.replace(".xlsx", "_v2.xlsx"))
        self.messages_done()
        self.assertEqual(self.done(), {})


class TestFloorplan(Base):
    def test_statement_units(self):
        self.workbooks_done()
        self.messages_done()
        self.edit(FP, set_cell("N2046", "Principal Balance", 31000), "Floorplan Tracking")
        self.assertIn("N2046 Principal Balance", self.done().get("fp.statement_units", ""))

    def test_unit_annotations_paraphrase(self):
        self.workbooks_done()
        self.messages_done()
        self.edit(FP, set_cell("N2049", "Notes", "New unit added. Advance date 04/15/2026. Invoice $34,600."),
                  "Floorplan Tracking")
        got = self.done()
        self.assertIn("N2049 column 'Notes'", got.get("fp.unit_annotations", ""))

    def test_unit_annotations_hyphen_status(self):
        self.workbooks_done()
        self.edit(FP, set_cell("N2041", "Status", "Sold - not paid off FP"), "Floorplan Tracking")
        self.assertIn("N2041 column 'Status'", " ".join(p for r, p in self.done_all() if r == "fp.unit_annotations"))

    def test_format_date_and_status(self):
        self.workbooks_done()
        self.messages_done()
        self.edit(FP, set_cell("U1092", "Status", "Active"), "Floorplan Tracking")
        probs = [p for r, p in self.done_all() if r == "fp.format"]
        self.assertTrue(any("U1092: Status 'Active'" in p for p in probs))

    def test_format_datetime(self):
        self.workbooks_done()
        self.messages_done()
        self.edit(FP, "import datetime\n" + set_cell("N2049", "Advance Date", "X").replace(
            "'X'", "datetime.datetime(2026, 4, 15)"), "Floorplan Tracking")
        probs = [p for r, p in self.done_all() if r in ("fp.format", "fp.unit_annotations")]
        self.assertTrue(any("Advance Date" in p for p in probs))

    def test_format_u1087_notes_template_ok(self):
        self.workbooks_done()
        self.messages_done()
        self.edit(FP, set_cell("U1087", "Notes", "Payoff confirmed by lender 04/10/2026 per JM Family Enterprises "
                                                 "statement."), "Floorplan Tracking")
        self.assertEqual(self.done(), {})
        self.edit(FP, set_cell("U1087", "Notes", "Payoff received 04/10 per JM Family."), "Floorplan Tracking")
        self.assertIn("U1087: Notes", self.done().get("fp.format", ""))

    def test_exception_log_append_only(self):
        self.workbooks_done()
        self.messages_done()
        self.edit(FP, "ws.cell(2, 11).value = 'Closed'", "Exception Log")
        self.assertIn("append-only", self.done().get("fp.exception_log", ""))

    def test_exception_log_bad_classification(self):
        self.workbooks_done()
        self.messages_done()
        self.edit(FP, "ws.append(['04/16/2026', '4505', 'JM Family', 'N2043', '$40,100.00', 'Statement', "
                      "'Missing Vehicle', 'Marcus Hale', '', '', 'Open', ''])", "Exception Log")
        self.assertIn("Classification", " ".join(p for r, p in self.done_all() if r == "fp.exception_log"))


class TestInventory(Base):
    def test_n2049_pack(self):
        self.workbooks_done()
        self.messages_done()
        self.edit(NEW, set_cell("N2049", "Pack", 750), "New Inventory")
        self.assertIn("'Pack'", " ".join(p for r, p in self.done_all() if r == "inv.n2049_stock_in"))

    def test_n2041_note(self):
        self.workbooks_done()
        self.messages_done()
        self.assertNotIn("inv.n2041_note", self.done())
        self.edit(NEW, set_cell("N2041", "Notes", "Sold 03/31/2026, funded 04/10/2026. Payoff pending."), "New Inventory")
        self.assertIn("inv.n2041_note", self.done())

    def test_inventory_status_format(self):
        self.workbooks_done()
        self.messages_done()
        self.edit(USED, set_cell("U1087", "Status", "Sold 04/07/2026"), "Used Inventory")
        self.assertEqual(self.done(), {})
        self.edit(USED, set_cell("U1087", "Status", "Sold, unfunded"), "Used Inventory")
        self.assertIn("inv.format", self.done())

    def test_costs_unchanged(self):
        self.workbooks_done()
        self.messages_done()
        self.edit(USED, set_cell("U1090", "Recon", 10400), "Used Inventory")
        self.assertIn("U1090: Recon changed", " ".join(p for r, p in self.done_all() if r == "inv.costs_unchanged"))


class TestEscalationAndScope(Base):
    def test_u1090_via_slack_mention(self):
        self.workbooks_done()
        self.slack(SLACK_48)
        self.slack(SLACK_41)
        self.did("google_mail__send_email", EMAIL_I)
        self.did("google_mail__send_email", EMAIL_J)
        self.did("google_mail__reply_email", REPLY)
        self.slack("Trent, SBP-4821 on U1090 is fine.", "C006")
        self.assertIn("recon.u1090_escalation", self.done())
        self.slack("@elena.brooks U1090 book cost $31,150 exceeds retail $29,500 after SBP-4821.", "C006")
        self.assertNotIn("recon.u1090_escalation", self.done())

    def test_other_workbook_changed(self):
        self.workbooks_done()
        self.messages_done()
        self.edit("Deal_Log_April2026.xlsx", "ws.cell(12, 30).value = 'Floorplan payoff not sent'", "Deal Log")
        self.assertIn("scope.other_workbooks", self.done())

    def test_source_docs(self):
        self.assertIn("files.source_docs", self.pre("syntara__writeFile",
                                                     {"file_path": "/workdir/Invoice_SBP4821.pdf", "content": "x"}))
        self.assertNotIn("files.source_docs", self.pre("syntara__writeFile",
                                                        {"file_path": "/workdir/recon_notes.txt", "content": "x"}))


class TestMessages(Base):
    M = "fp.comms.messages"

    def test_slack_n2041_needs_concurrent_line(self):
        bad = "N2041: Sold-not-paid. Deal 4501, Robert Chen. Payoff not sent. @marcus.hale @elena.brooks"
        self.assertIn(self.M, self.pre("slack__post_message", {"channel_id": "C010", "text": bad}))
        self.assertNotIn(self.M, self.pre("slack__post_message", {"channel_id": "C010", "text": SLACK_41}))
        alt = ("N2041: Sold-not-paid. Deal 4501, Robert Chen. Payoff not sent.@marcus.hale @elena.brooks "
               "Concurrent collection issue: $2000 NSF, 04/13/2026.")
        self.assertNotIn(self.M, self.pre("slack__post_message", {"channel_id": "C010", "text": alt}))

    def test_slack_wrong_channel_and_values(self):
        self.assertIn(self.M, self.pre("slack__post_message", {"channel_id": "C006", "text": SLACK_48}))
        wrong = SLACK_48.replace("64 days past due", "65 days past due")
        self.assertIn(self.M, self.pre("slack__post_message", {"channel_id": "C010", "text": wrong}))
        self.assertNotIn(self.M, self.pre("slack__post_message", {"channel_id": "C010", "text": SLACK_48}))

    def test_unrelated_posts_pass(self):
        summary = "Daily recon done: N2041 sold-not-paid and N2048 aged curtailment escalated."
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C010", "text": summary}), set())
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C006", "text": "Trent, N2049 added."}), set())

    def test_email_after_slack(self):
        self.assertIn(self.M, self.pre("google_mail__send_email", EMAIL_J))
        self.slack(SLACK_41)
        self.assertNotIn(self.M, self.pre("google_mail__send_email", EMAIL_J))

    def test_email_template_lines(self):
        self.slack(SLACK_48)
        self.assertNotIn(self.M, self.pre("google_mail__send_email", EMAIL_I))
        bad = dict(EMAIL_I, body=EMAIL_I["body"].replace("Slack notification sent to #acct-floorplan.", ""))
        self.assertIn(self.M, self.pre("google_mail__send_email", bad))
        self.assertIn(self.M, self.pre("google_mail__send_email", dict(EMAIL_I, subject="Aged curtailment - N2048")))
        self.assertIn(self.M, self.pre("google_mail__send_email", dict(EMAIL_I, to=MARCUS)))

    def test_email_j_needs_concurrent(self):
        self.slack(SLACK_41)
        bad = dict(EMAIL_J, body=EMAIL_J["body"].replace("Concurrent collection issue: $2,000 NSF, 04/13/2026.", ""))
        self.assertIn(self.M, self.pre("google_mail__send_email", bad))

    def test_duplicate_blocked(self):
        self.slack(SLACK_48)
        self.assertIn(self.M, self.pre("slack__post_message", {"channel_id": "C010", "text": SLACK_48}))

    def test_reply_needs_exceptions(self):
        self.assertIn(self.M, self.pre("google_mail__reply_email", {"email_id": "9", "body": "Done, all reconciled."}))
        self.assertNotIn(self.M, self.pre("google_mail__reply_email", REPLY))

    def test_placeholders(self):
        self.assertIn("comms.no_placeholders",
                      self.pre("slack__post_message", {"channel_id": "C014", "text": "Unit [STOCK] escalated"}))

    def test_wrong_escalation_unit(self):
        bad = "N2049: Sold-not-paid. Deal #, Customer Name not identified. Payoff not sent.@marcus.hale @elena.brooks"
        self.assertIn("fp.escalation_units", self.pre("slack__post_message", {"channel_id": "C010", "text": bad}))
        self.assertIn("fp.escalation_units", self.pre("google_mail__send_email",
                                                      dict(EMAIL_J, subject="Sold-not-paid for U1087")))
        self.assertNotIn("fp.escalation_units", self.pre("slack__post_message", {"channel_id": "C010", "text": SLACK_41}))
