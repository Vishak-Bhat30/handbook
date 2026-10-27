"""Unit tests for finance_sunshine_set_6b9398f4 verifiers (fixtures from the task environment seed only)."""

from __future__ import annotations

import subprocess
import unittest

from interwhen_sop.tests.base import XLSX_PY, TaskCase

DEAL_LOG = "DealLog_April2026.xlsx"
TRACKER = "FundingTracker_April2026.xlsx"
JACKET = "20260414_4821_Mitchell_112847.pdf"

POST_DEAL = """
import datetime
r = 8
vals = {'I': 34500, 'J': 899, 'K': 2301, 'L': 2590, 'M': 1050, 'N': 8625, 'Q': 0.0699, 'R': 72, 'S': 2000,
        'T': 3640, 'U': 5640, 'V': 5640, 'X': datetime.datetime(2026, 4, 14), 'Y': 'J. Patel', 'Z': 'CIT',
        'AB': 'In Progress', 'AC': 'Posted 4/14; high-gross notice posted; pkg routed to Noah'}
for c, v in vals.items():
    ws[f'{c}{r}'] = v
"""

TRACKER_ROW = """
import datetime
data = [4821, 'Mitchell, Sarah', 'N-2547', '1HGCV1F34PA112847', 'Ally Financial', 31665, 1050,
        datetime.datetime(2026, 4, 14), datetime.datetime(2026, 4, {day}), 0, 'None \u2014 all cleared', None, None,
        'Active \u2014 CIT', 'Ally ref ALY-2026-0414-8823']
for i, v in enumerate(data, 1):
    ws.cell(row=8, column=i, value=v)
"""

NOTICE = ("@marcus.hale High-gross confirmation notice: Deal #4821 (Mitchell, Sarah / Stock N-2547 / VIN "
          "1HGCV1F34PA112847). Total approved gross: $5,640.00. Desk recap tie-out: ties to the approved desk recap. "
          "Variance: $0.00.")

TEMPLATE_B = ("Please find the attached funding package for the following contract:\n\nDeal #: 4821 | Customer: Sarah E. "
              "Mitchell | VIN: 1HGCV1F34PA112847 | Contract Date: April 14, 2026 | Amount Financed: $31,665.00 | "
              "Reserve: $1,050.00\n\nAll stipulations have been addressed. If any items remain outstanding, please reply "
              "to this email and copy Noah Alvarez at noah.alvarez@sunshineandsetauto.com.")


class Base(TaskCase):
    TASK = "finance_sunshine_set_6b9398f4"

    def post_notice(self, text: str = NOTICE):
        self.did("slack__post_message", {"channel_id": "C001", "text": text})

    def post_deal(self, fname: str = DEAL_LOG):
        self.edit(fname, POST_DEAL)

    def add_tracker(self, day: int = 16, fname: str = TRACKER):
        self.edit(fname, TRACKER_ROW.format(day=day))

    def make_jacket(self, parts=("01_BuyersOrder", "02_RetailInstallmentContract", "03_DeskRecap",
                                 "04_ProofOfInsurance", "05_DeliveryChecklist", "06_FandIMenu", "07_AllyStips"),
                    name: str = JACKET):
        wd = self.tmp / "workdir"
        code = ("import sys, pypdf\nw = pypdf.PdfWriter()\nfor p in sys.argv[2:]:\n    w.append(p)\n"
                "w.write(sys.argv[1])\n")
        subprocess.run([XLSX_PY, "-c", code, str(wd / name), *[str(wd / f"{p}.pdf") for p in parts]], check=True)

    def route_noah(self):
        self.did("google_mail__send_email", {"to": "noah.alvarez@sunshineandsetauto.com",
                                             "subject": "Funding Package — Deal #4821 / Mitchell / Ally Financial",
                                             "body": TEMPLATE_B, "attachments": [f"/workdir/{JACKET}"]})

    def title_priya(self):
        self.did("google_mail__send_email", {"to": "priya.bennett@sunshineandsetauto.com",
                                             "subject": "Title Work — Deal #4821 / Mitchell",
                                             "body": "Please start title work for Deal #4821, Sarah E. Mitchell, Stock "
                                                     "N-2547, VIN 1HGCV1F34PA112847. Lienholder Ally Financial. No trade."})

    def reminder(self, date: str = "2026-04-16"):
        self.did("google_calendar__create_event", {"summary": "Expected Funding — Deal #4821 Mitchell / Ally Financial",
                                                   "start": {"date": date}, "end": {"date": date},
                                                   "description": "If no funding confirmation, start daily follow-up."})

    def golden(self):
        self.post_notice()
        self.post_deal()
        self.add_tracker()
        self.make_jacket()
        self.route_noah()
        self.title_priya()
        self.reminder()


class InitialState(Base):
    def test_initial_findings(self):
        self.assertEqual(set(self.done()), {"comms.messages_sent", "deal.log_row", "deal.jacket_pdf",
                                            "funding.tracker_row", "funding.calendar_reminder", "handoff.routing"})

    def test_golden_path(self):
        self.golden()
        self.assertEqual(self.done(), {})

    def test_golden_path_with_v2_copies(self):
        self.post_notice()
        for src, dst in ((DEAL_LOG, "DealLog_April2026_v2.xlsx"), (TRACKER, "FundingTracker_April2026_v2.xlsx")):
            (self.tmp / "workdir" / dst).write_bytes((self.tmp / "workdir" / src).read_bytes())
        self.post_deal("DealLog_April2026_v2.xlsx")
        self.add_tracker(fname="FundingTracker_April2026_v2.xlsx")
        self.make_jacket()
        self.route_noah()
        self.title_priya()
        self.reminder()
        self.assertEqual(self.done(), {})


class HighGrossNotice(Base):
    def test_notice_required(self):
        self.golden_without_notice()
        self.assertIn("comms.messages_sent", self.done())

    def golden_without_notice(self):
        self.post_deal()
        self.add_tracker()
        self.make_jacket()
        self.route_noah()
        self.title_priya()
        self.reminder()

    def test_good_notice_passes(self):
        self.assertNotIn("comms.messages", self.pre("slack__post_message", {"channel_id": "C001", "text": NOTICE}))

    def test_notice_missing_variance_blocked(self):
        text = NOTICE.replace(" Variance: $0.00.", "")
        self.assertIn("comms.messages", self.pre("slack__post_message", {"channel_id": "C001", "text": text}))

    def test_notice_as_dm_blocked(self):
        self.assertIn("comms.messages", self.pre("slack__send_dm", {"user_id": "U002", "text": NOTICE}))

    def test_deal_log_write_before_notice_blocked(self):
        code = "import openpyxl\nwb=openpyxl.load_workbook('/workdir/DealLog_April2026.xlsx')\nwb.save('/workdir/DealLog_April2026.xlsx')"
        self.assertIn("deal.notice_first", self.pre("syntara__executePython", {"code": code}))
        self.post_notice()
        self.assertNotIn("deal.notice_first", self.pre("syntara__executePython", {"code": code}))


class Messages(Base):
    def test_template_a_blocked(self):
        args = {"to": "sofia.ramirez@sunshineandsetauto.com", "subject": "Deal Gross Variance — Deal #4821 / Mitchell",
                "body": "The posted deal gross for Deal #4821 does not tie."}
        self.assertIn("comms.messages", self.pre("google_mail__send_email", args))

    def test_template_b_wrong_subject_blocked(self):
        args = {"to": "carlos.mendez@ally.com", "subject": "Funding Package for 4821", "body": TEMPLATE_B}
        self.assertIn("comms.messages", self.pre("google_mail__send_email", args))

    def test_template_b_correct_passes(self):
        args = {"to": "noah.alvarez@sunshineandsetauto.com",
                "subject": "Funding Package — Deal #4821 / Mitchell / Ally Financial", "body": TEMPLATE_B}
        self.assertNotIn("comms.messages", self.pre("google_mail__send_email", args))

    def test_plain_routing_email_not_template_checked(self):
        args = {"to": "noah.alvarez@sunshineandsetauto.com", "subject": "Funding Package Ready - Deal 4821",
                "body": "Deal 4821 / Mitchell is posted; the funding package is ready for your Ally submission."}
        self.assertNotIn("comms.messages", self.pre("google_mail__send_email", args))

    def test_placeholders_blocked(self):
        args = {"to": "noah.alvarez@sunshineandsetauto.com", "subject": "Deal 4821",
                "body": "Customer: [Full Name] | Deal #: 4821"}
        self.assertIn("comms.no_placeholders", self.pre("google_mail__send_email", args))
        args["body"] = "Customer: Sarah E. Mitchell | Deal #: 4821"
        self.assertNotIn("comms.no_placeholders", self.pre("google_mail__send_email", args))

    def test_slack_post_format(self):
        bad = {"channel_id": "C002", "text": "Deal 4821 is posted, funding package ready."}
        self.assertIn("slack.post_format", self.pre("slack__post_message", bad))
        good = {"channel_id": "C002", "text": "@noah.alvarez Deal #4821 / Mitchell / Stock N-2547 posted; funding "
                                              "package ready for Ally SecureLink."}
        self.assertNotIn("slack.post_format", self.pre("slack__post_message", good))


class Handoffs(Base):
    def test_routing_required(self):
        self.post_notice()
        self.post_deal()
        self.add_tracker()
        self.make_jacket()
        self.reminder()
        probs = [p for r, p in self.done_all() if r == "handoff.routing"]
        self.assertEqual(len(probs), 2)

    def test_slack_handoffs_count(self):
        self.golden_slack()
        self.assertNotIn("handoff.routing", self.done())

    def golden_slack(self):
        self.did("slack__post_message", {"channel_id": "C002", "text": "@noah.alvarez Deal #4821 / Mitchell / N-2547 "
                                                                       "posted; funding package ready."})
        self.did("slack__send_dm", {"user_id": "U005", "text": "Title work kickoff for Deal #4821 Mitchell, VIN "
                                                               "1HGCV1F34PA112847, lienholder Ally."})


class DealLog(Base):
    def test_wrong_tax_flagged(self):
        self.post_deal()
        self.edit(DEAL_LOG, "ws['K8'] = 2469.29")
        self.assertIn("Tax = 2301", self.done().get("deal.log_row", ""))

    def test_status_not_updated_flagged(self):
        self.post_deal()
        self.edit(DEAL_LOG, "ws['Z8'] = 'Pending Posting'\nws['AB8'] = 'Not Started'")
        msg = self.done().get("deal.log_row", "")
        self.assertIn("Funding Status = CIT", msg)
        self.assertIn("Title Status", msg)

    def test_shifted_columns_flagged(self):
        self.post_deal()
        self.edit(DEAL_LOG, "import datetime\nws['W8'] = datetime.datetime(2026, 4, 14)\nws['X8'] = 'J. Patel'")
        msg = self.done().get("deal.log_row", "")
        self.assertIn("Variance = 0", msg)
        self.assertIn("Post Date = 2026-04-14", msg)

    def test_correct_row_passes(self):
        self.post_deal()
        self.assertNotIn("deal.log_row", self.done())

    def test_alternative_status_wording_passes(self):
        self.post_deal()
        self.edit(DEAL_LOG, "ws['Y8'] = 'Jasmine Patel'\nws['Z8'] = 'Pending Funding'\nws['AB8'] = 'Processing'\n"
                            "ws['Q8'] = '6.99%'")
        self.assertNotIn("deal.log_row", self.done())

    def test_other_rows_must_stay(self):
        self.post_deal()
        self.assertNotIn("deal.log_integrity", self.done())
        self.edit(DEAL_LOG, "ws['Z7'] = 'Funded'")
        self.assertIn("deal.log_integrity", self.done())


class Tracker(Base):
    def test_three_day_window_flagged(self):
        self.add_tracker(day=17)
        self.assertIn("Exp. Funding Date = 2026-04-16", self.done().get("funding.tracker_row", ""))

    def test_two_day_window_passes(self):
        self.add_tracker(day=16)
        self.assertNotIn("funding.tracker_row", self.done())

    def test_existing_rows_must_stay(self):
        self.add_tracker()
        self.assertNotIn("funding.tracker_integrity", self.done())
        self.edit(TRACKER, "ws['N6'] = 'Open'")
        self.assertIn("funding.tracker_integrity", self.done())


class Calendar(Base):
    def test_reminder_required_on_expected_date(self):
        self.reminder("2026-04-17")
        self.assertIn("funding.calendar_reminder", self.done())

    def test_reminder_on_0416_passes(self):
        self.reminder("2026-04-16")
        self.assertNotIn("funding.calendar_reminder", self.done())

    def test_ally_date_blocked(self):
        args = {"summary": "Expected Funding — Deal #4821 Mitchell", "start": {"date": "2026-04-17"},
                "end": {"date": "2026-04-17"}}
        self.assertIn("funding.calendar_date", self.pre("google_calendar__create_event", args))
        args["start"] = args["end"] = {"date": "2026-04-16"}
        self.assertNotIn("funding.calendar_date", self.pre("google_calendar__create_event", args))


class Files(Base):
    def test_jacket_required(self):
        self.assertIn("deal.jacket_pdf", self.done())
        self.make_jacket()
        self.assertNotIn("deal.jacket_pdf", self.done())

    def test_jacket_missing_contract_flagged(self):
        self.make_jacket(parts=("01_BuyersOrder", "04_ProofOfInsurance", "05_DeliveryChecklist", "06_FandIMenu",
                                "07_AllyStips"))
        self.assertIn("retail installment contract", self.done().get("deal.jacket_pdf", ""))

    def test_source_pdf_overwrite_blocked(self):
        self.assertIn("files.source_readonly",
                      self.pre("syntara__writeFile", {"file_path": "/workdir/01_BuyersOrder.pdf", "content": "x"}))
        self.assertNotIn("files.source_readonly",
                         self.pre("syntara__writeFile", {"file_path": f"/workdir/{JACKET}", "content": "x"}))


if __name__ == "__main__":
    unittest.main()
