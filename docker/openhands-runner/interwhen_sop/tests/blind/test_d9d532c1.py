"""Blind unit tests for finance_sunshine_set_d9d532c1 (April 1-15 commission cutoff)."""

import subprocess

from interwhen_sop.tests.base import XLSX_PY, TaskCase

OLIVIA = "olivia.mercer@sunshineandsetauto.com"
HANNAH = "hannah.price@sunshineandsetauto.com"
MARCUS = "marcus.hale@sunshineandsetauto.com"
MEGAN = "megan.price@sunshineandsetauto.com"

FLAG = ("<@U012> Apr 1-15 new vehicle sheet: Deal 4507 (Foster, Stock N2044, VIN 3TMCZ5AN0RM704507) is not posted "
        "in the deal log - excluded from payroll, sheet returned to you. Deal 4505 (Park, Stock N2043) was unwound "
        "and the posting reversed 04/16 - excluded.")
NOTICE = {"to": MEGAN, "cc": f"{MARCUS}, {HANNAH}", "subject": "Commission Chargeback Offset Notice - Deal 4492",
          "body": "Megan,\n\nWritten notice: SafeGuard GAP chargeback on Deal 4492 (Patricia Dunn) of $1,400. Your "
                  "April 1-15 commission of $1,050 is offset; the remaining $350 is carried forward to the May 1-15 "
                  "pay period. You may dispute this by replying.\n\nLeah Morgan"}
RETURN = {"to": OLIVIA, "subject": "New Vehicle Commission Sheet Returned - April 1-15",
          "body": "Olivia, returning the sheet: Deal 4507 is not posted in the deal log and Deal 4505 was unwound. "
                  "Both are excluded from this payroll.\n\nLeah"}
SUPPORT = {"to": HANNAH, "cc": MARCUS, "subject": "Payroll Support - April 1-15, 2026",
           "body": "Hannah,\n\nRegular commissions: Vaughn 4504 $1,550; Price 4502/4506/4508 $1,050; Vega 4503/4509 "
                   "$1,000.\nPrior-period adjustment: Deal 4501 (posted 03/31) - original pay period March 16-31, "
                   "original amount $0, corrected amount $1,450, variance $1,450; missed on the March sheet.\n"
                   "Excluded: 4505 (unwound), 4507 (not posted).\nChargeback offset: Megan Price, Deal 4492 $1,400 - "
                   "$1,050 offset this period, $350 carried forward.\n\nLeah"}
CAL = {"summary": "Payroll funding - April 1-15", "start": {"date": "2026-04-20"}, "end": {"date": "2026-04-21"}}


class D9(TaskCase):
    TASK = "finance_sunshine_set_d9d532c1"

    def golden(self, skip=()):
        steps = {"flag": ("slack__post_message", {"channel_id": "C007", "text": FLAG}),
                 "notice": ("google_mail__send_email", NOTICE),
                 "return": ("google_mail__send_email", RETURN),
                 "support": ("google_mail__send_email", SUPPORT),
                 "cal": ("google_calendar__create_event", CAL)}
        for k, (tool, args) in steps.items():
            if k not in skip:
                self.did(tool, args)

    def new_book(self, name, rows):
        path = self.tmp / "workdir" / name
        code = ("import openpyxl,sys,json\nwb=openpyxl.Workbook();ws=wb.active\n"
                "for r in json.loads(sys.argv[2]): ws.append(r)\nwb.save(sys.argv[1])\n")
        import json
        subprocess.run([XLSX_PY, "-c", code, str(path), json.dumps(rows)], check=True)


class TestInitial(D9):
    def test_initial_obligations(self):
        d = self.done_all()
        rules = {r for r, _ in d}
        self.assertEqual(rules, {"comm.messages_sent", "comm.return_sheet", "calendar.payroll_funding"})
        self.assertEqual(sum(r == "comm.messages_sent" for r, _ in d), 4)

    def test_golden_path(self):
        for tool, args in [("slack__post_message", {"channel_id": "C007", "text": FLAG}),
                           ("google_mail__send_email", NOTICE), ("google_mail__send_email", RETURN),
                           ("google_mail__send_email", SUPPORT), ("google_calendar__create_event", CAL)]:
            self.assertEqual(self.pre(tool, args), set(), tool)
            self.did(tool, args)
        self.assertEqual(self.done(), {})


class TestFlags(D9):
    def test_flag_missing_stock_blocked(self):
        bad = FLAG.replace(", Stock N2044, VIN 3TMCZ5AN0RM704507", "")
        self.assertIn("comm.messages", self.pre("slack__post_message", {"channel_id": "C007", "text": bad}))

    def test_flag_missing_tag_blocked(self):
        bad = FLAG.replace("<@U012> ", "")
        self.assertIn("comm.messages", self.pre("slack__post_message", {"channel_id": "C007", "text": bad}))

    def test_flag_ok_and_other_channel_ignored(self):
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C007", "text": FLAG}), set())
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C001", "text": "Deal 4507 question"}), set())
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C007", "text": "Cutoff today"}), set())

    def test_flag_completion(self):
        self.golden(skip=("flag",))
        self.assertIn("comm.messages_sent", self.done())
        self.did("slack__post_message", {"channel_id": "C007", "text": FLAG})
        self.assertEqual(self.done(), {})


class TestOffsetNotice(D9):
    def test_notice_missing_cc_blocked(self):
        args = dict(NOTICE, cc=MARCUS)
        self.assertIn("comm.messages", self.pre("google_mail__send_email", args))

    def test_notice_missing_dispute_blocked(self):
        args = dict(NOTICE, body=NOTICE["body"].replace("You may dispute this by replying.", ""))
        self.assertIn("comm.messages", self.pre("google_mail__send_email", args))

    def test_notice_ok(self):
        self.assertEqual(self.pre("google_mail__send_email", NOTICE), set())

    def test_support_before_notice_blocked(self):
        self.assertIn("offset.notice_first", self.pre("google_mail__send_email", SUPPORT))
        self.did("google_mail__send_email", NOTICE)
        self.assertEqual(self.pre("google_mail__send_email", SUPPORT), set())


class TestSupport(D9):
    def setUp(self):
        super().setUp()
        self.did("google_mail__send_email", NOTICE)

    def test_support_missing_adjustment_fields_blocked(self):
        body = SUPPORT["body"].replace("original pay period March 16-31, original amount $0, corrected amount $1,450, "
                                       "variance $1,450", "$1,450 for March 16-31")
        self.assertIn("comm.messages", self.pre("google_mail__send_email", dict(SUPPORT, body=body)))

    def test_support_missing_exclusions_blocked(self):
        body = SUPPORT["body"].replace("Excluded: 4505 (unwound), 4507 (not posted).\n", "")
        self.assertIn("comm.messages", self.pre("google_mail__send_email", dict(SUPPORT, body=body)))

    def test_support_fields_in_attachment_ok(self):
        body = SUPPORT["body"].replace("original pay period March 16-31, original amount $0, corrected amount $1,450, "
                                       "variance $1,450", "$1,450, see attached")
        self.new_book("Commission_Support_Apr1-15_v2.xlsx",
                      [["Deal#", "Original Pay Period", "Original Amount", "Corrected Amount", "Variance"],
                       [4501, "March 16-31", 0, 1450, 1450]])
        args = dict(SUPPORT, body=body, attachments=["/workdir/Commission_Support_Apr1-15_v2.xlsx"])
        self.assertEqual(self.pre("google_mail__send_email", args), set())

    def test_support_ok_and_followup_free(self):
        self.assertEqual(self.pre("google_mail__send_email", SUPPORT), set())
        self.did("google_mail__send_email", SUPPORT)
        follow = dict(SUPPORT, subject="Payroll Support - supplement", body="Deal 4504 update attached.")
        self.assertEqual(self.pre("google_mail__send_email", follow), set())


class TestReturnSheet(D9):
    def test_partial_return_flagged(self):
        self.golden(skip=("return",))
        self.did("google_mail__send_email", dict(RETURN, body="Olivia, Deal 4507 is not posted; returning the sheet."))
        self.assertIn("comm.return_sheet", self.done())

    def test_reply_all_return_ok(self):
        self.golden(skip=("return",))
        self.did("google_mail__reply_email", {"email_id": "11", "reply_all": True,
                                              "body": "Olivia, returning the sheet: 4507 not posted, 4505 unwound."})
        self.assertEqual(self.done(), {})


class TestCalendar(D9):
    def test_wrong_date_flagged(self):
        self.golden(skip=("cal",))
        self.did("google_calendar__create_event", dict(CAL, start={"date": "2026-05-20"}, end={"date": "2026-05-21"}))
        self.assertIn("calendar.payroll_funding", self.done())

    def test_funding_reminder_ok(self):
        self.golden()
        self.assertNotIn("calendar.payroll_funding", self.done())


class TestWorkbooks(D9):
    def test_deal_log_new_row_flagged(self):
        self.golden()
        self.edit("Deal_Log_April2026.xlsx", "ws.append(['4507','N2044','New','2026-04-11','Foster','Brian'])")
        self.assertIn("deallog.unchanged", self.done())

    def test_deal_log_post_date_change_flagged(self):
        self.golden()
        self.edit("Deal_Log_April2026.xlsx",
                  "for r in range(2, ws.max_row+1):\n"
                  "    if str(ws.cell(r,1).value)=='4501': ws.cell(r, col['Post Date']).value='2026-04-06'")
        self.assertIn("deallog.unchanged", self.done())

    def test_deal_log_note_ok(self):
        self.golden()
        self.edit("Deal_Log_April2026.xlsx",
                  "for r in range(2, ws.max_row+1):\n"
                  "    if str(ws.cell(r,1).value)=='4505': ws.cell(r, col['Notes']).value='Commission excluded'")
        self.assertEqual(self.done(), {})

    def test_unrelated_record_flagged(self):
        self.golden()
        self.edit("Funding_Tracker_April2026.xlsx", "ws.cell(2, col['Notes']).value='x'")
        self.assertIn("scope.unrelated_records", self.done())

    def test_chargeback_tracker_update_ok(self):
        self.golden()
        self.edit("Chargeback_Tracker_April2026.xlsx", "ws.cell(2, col['Notes']).value='Offset notice sent 04/16'")
        self.assertEqual(self.done(), {})

    def test_source_sheet_overwrite_flagged(self):
        self.golden()
        self.edit("CommSheet_NewVehicles_Apr1-15_OliviaMercer.xlsx", "ws['A20']='edited'")
        self.assertIn("files.source_sheets", self.done())

    def test_source_sheet_copy_ok(self):
        self.golden()
        self.new_book("CommSheet_NewVehicles_Apr1-15_OliviaMercer_v2.xlsx", [["Deal#"], [4503]])
        self.assertEqual(self.done(), {})

    def test_excluded_marked_verified_flagged(self):
        self.golden()
        self.edit("Commission_Sheet_April_1-15_2026.xlsx",
                  "for r in range(2, ws.max_row+1):\n"
                  "    if str(ws.cell(r,2).value)=='4507': ws.cell(r, col['Verified (Y/N)']).value='Y'")
        self.assertIn("verify.excluded_deals", self.done())

    def test_excluded_marked_n_ok(self):
        self.golden()
        self.edit("Commission_Sheet_April_1-15_2026.xlsx",
                  "for r in range(2, ws.max_row+1):\n"
                  "    v=str(ws.cell(r,2).value)\n"
                  "    ws.cell(r, col['Verified (Y/N)']).value = 'N' if v in ('4505','4507') else 'Y'")
        self.assertEqual(self.done(), {})


class TestPlaceholders(D9):
    def test_placeholder_blocked(self):
        args = {"channel_id": "C014", "text": "Hello [Customer Last Name], update soon"}
        self.assertIn("comms.no_placeholders", self.pre("slack__post_message", args))

    def test_no_placeholder_ok(self):
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C014", "text": "Hello team"}), set())
