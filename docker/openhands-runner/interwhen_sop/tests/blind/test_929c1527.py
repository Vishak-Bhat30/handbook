"""Blind unit tests for hr_ridgeline_gear_co_929c1527 verifiers (fixtures from the task seed only)."""

from __future__ import annotations

import unittest

from interwhen_sop.tests.base import TaskCase

RENATA = "renata.okafor@ridgelinegear.com"
CASE = "LC-2026-0321"
TEMPLATE3 = f"""Hi Elena,

Thank you for submitting your FMLA leave request. I have reviewed your eligibility against the federal FMLA criteria and unfortunately must inform you that you are NOT currently eligible for FMLA leave for the following reason:

Hours: FMLA requires at least 1,250 hours worked in the 12 months immediately preceding the leave start date. Your hours worked in that period are 1,038, which is below the threshold.

Attached is the official Notice of Eligibility (DOL Form WH-381) reflecting this determination.

Even though you are not eligible for FMLA, you may still be eligible for leave under Colorado FAMLI, which has different eligibility criteria (no tenure requirement, no minimum hours requirement). To pursue FAMLI, please file a claim directly with CDLE at claims@famli.colorado.gov.

If you believe this FMLA determination is in error, please reply to this email and I will review.

Case ID: {CASE}

Best regards,
Ridgeline Gear Co. — Leave Coordinator
leaves@ridgelinegear.com"""

DENIAL = ("google_mail__send_email", {"to": "elenavee@gmail.com", "cc": RENATA,
                                      "subject": f"FMLA Eligibility Determination — Case {CASE}", "body": TEMPLATE3})
DENIED_POST = ("slack__post_message", {"channel_id": "C001", "text": f"FMLA DENIED (INELIGIBILITY): {CASE}, Elena Vasquez, "
                                                                    "Hours (1,038 hours worked in the prior 12 months; "
                                                                    "1,250 required)"})
PATTERN_POST = ("slack__post_message", {"channel_id": "C003", "text": (
    "RECURRING ISSUE: James Nkomo, LC-2026-0203, intermittent absences above certified frequency (5 in 30 days vs "
    "certified high end of 2, +150%), 03/10, 03/19, 03/26, 04/02, 04/07/2026 — please review.")})
PATTERN_EMAIL = ("google_mail__send_email", {"to": RENATA, "subject": "RECURRING ISSUE — LC-2026-0203",
                                             "body": "Renata,\n\nLC-2026-0203 shows 5 absences 03/10–04/07/2026 vs a "
                                                     "certified high end of 2 per 30 days (+150%). Not shared with the "
                                                     "employee or manager. Awaiting your direction.\n\nLeave Coordinator"})
PAYROLL = ("slack__post_message", {"channel_id": "C004", "text": "LEAVE PAYROLL NOTIFICATION: LC-2026-0320, Marcus "
                                                                 "DeLuca, Return from Leave, 04/10/2026, Continuous"})
MARK = ("google_mail__mark_emails", {"email_ids": ["35"], "is_read": True, "is_important": True})
CAL = ("google_calendar__update_event", {"event_id": "lc-2026-0320-rtw",
                                         "summary": "[DONE] Expected Return — LC-2026-0320 Marcus DeLuca (Jury Duty)"})
MOVE = ("google_mail__move_emails", {"email_ids": ["16"], "target_folder": "Closed Cases"})

ELENA_ROW = (
    "ws.append(['{cid}','R-2317','Elena Vasquez','{lt}','{start}','05/15/2026',None,'Continuous',0,None,'Not Required',"
    "None,'N','{prio}','{status}','04/10: FMLA ineligible - 1,038 hours < 1,250 (non-exempt); tenure met. Template 3 "
    "sent cc Benefits Manager; referred to CDLE for FAMLI.'])\n")
NKOMO_NOTE = ("for row in ws.iter_rows(min_row=2):\n"
              "    if row[0].value=='LC-2026-0203':\n"
              "        row[15].value = row[15].value + ' 04/10: Pattern flagged 04/10/2026 — 5 absences 03/10–04/07 vs "
              "certified 1-2/month (+150%) — escalated to Benefits Manager per Section 12.'\n")
DELUCA = ("for row in ws.iter_rows(min_row=2):\n"
          "    if row[0].value=='LC-2026-0320':\n"
          "        row[6].value = '{end}'\n"
          "        row[14].value = '{status}'\n"
          "        row[15].value = row[15].value + ' 04/10: RTW confirmed by mgr Ellison. Payroll notified. Case closed "
          "04/10/2026.'\n")


class Base(TaskCase):
    TASK = "hr_ridgeline_gear_co_929c1527"

    def elena_row(self, cid=CASE, lt="FMLA", start="04/20/2026", prio="P2", status="Denied"):
        self.edit("leave_tracker.xlsx", ELENA_ROW.format(cid=cid, lt=lt, start=start, prio=prio, status=status),
                  sheet="Leave Tracker")

    def nkomo_note(self):
        self.edit("leave_tracker.xlsx", NKOMO_NOTE, sheet="Leave Tracker")

    def deluca(self, end="04/10/2026", status="Closed"):
        self.edit("leave_tracker.xlsx", DELUCA.format(end=end, status=status), sheet="Leave Tracker")

    def send(self, call, extra=None):
        tool, args = call
        args = {**args, **(extra or {})}
        self.did(tool, args)


class TestInitialState(Base):
    def test_initial_findings(self):
        self.assertEqual(set(self.done()), {"elena.case_row", "nkomo.pattern_note", "deluca.close", "mail.housekeeping",
                                            "comms.messages_sent"})
        msgs = [p for r, p in self.done_all() if r == "comms.messages_sent"]
        self.assertEqual(len(msgs), 5)
        self.assertFalse(any("04/07/2026 LC-2026-0203 absence" in p or "Absence Log" in p for _, p in self.done_all()))


class TestGoldenPath(Base):
    def test_full_correct_end_state(self):
        self.elena_row()
        self.nkomo_note()
        self.deluca()
        for call in (DENIAL, DENIED_POST, PATTERN_POST, PATTERN_EMAIL, PAYROLL, MARK, CAL, MOVE):
            self.assertEqual(self.pre(*call), set(), call[0])
            self.did(*call)
        self.assertEqual(self.done(), {})


class TestElenaCaseRow(Base):
    def test_compliant(self):
        self.elena_row()
        self.assertNotIn("elena.case_row", self.done())

    def test_wrong_priority(self):
        self.elena_row(prio="P3")
        self.assertIn("P2", self.done()["elena.case_row"])

    def test_concurrent_type_rejected(self):
        self.elena_row(lt="FMLA + FAMLI")
        self.assertIn("FMLA + FAMLI", self.done()["elena.case_row"])

    def test_status_not_denied(self):
        self.elena_row(status="Intake")
        self.assertIn("Denied", self.done()["elena.case_row"])

    def test_date_format(self):
        self.elena_row(start="2026-04-20")
        self.assertIn("04/20/2026", self.done()["elena.case_row"])

    def test_real_date_cell_accepted(self):
        self.elena_row()
        self.edit("leave_tracker.xlsx", "import datetime\nws.cell(row=ws.max_row, column=5).value = "
                                        "datetime.datetime(2026, 4, 20)", sheet="Leave Tracker")
        self.assertNotIn("elena.case_row", self.done())

    def test_reused_case_id(self):
        self.elena_row(cid="LC-2026-0320")
        self.assertIn("unused", self.done()["elena.case_row"])


class TestDenialEmail(Base):
    def test_compliant_personal_and_work(self):
        self.assertNotIn("comms.messages", self.pre(*DENIAL))
        tool, args = DENIAL
        self.assertEqual(self.pre(tool, {**args, "to": "elena.vasquez@ridgelinegear.com"}), set())

    def test_missing_cc(self):
        tool, args = DENIAL
        self.assertIn("comms.messages", self.pre(tool, {**args, "cc": ""}))

    def test_missing_famli_referral(self):
        tool, args = DENIAL
        body = args["body"].replace("claims@famli.colorado.gov", "CDLE")
        self.assertIn("comms.messages", self.pre(tool, {**args, "body": body}))

    def test_case_id_must_match_tracker(self):
        self.elena_row(cid="LC-2026-0412")
        self.assertIn("comms.messages", self.pre(*DENIAL))

    def test_sent_satisfies_completion(self):
        self.elena_row()
        self.did(*DENIAL)
        self.assertFalse(any("ineligibility notice" in p for r, p in self.done_all() if r == "comms.messages_sent"))

    def test_duplicate_blocked(self):
        self.did(*DENIAL)
        self.assertIn("comms.messages", self.pre(*DENIAL))


class TestSlackMessages(Base):
    def test_denied_post(self):
        self.assertEqual(self.pre(*DENIED_POST), set())
        self.assertIn("comms.messages", self.pre("slack__post_message", {"channel_id": "C001", "text": (
            f"FMLA DENIED: {CASE} Elena Vasquez, not eligible")}))
        self.assertIn("comms.messages", self.pre("slack__post_message", {**DENIED_POST[1], "channel_id": "C002"}))

    def test_pattern_post(self):
        self.assertEqual(self.pre(*PATTERN_POST), set())
        bad = PATTERN_POST[1]["text"].replace("James Nkomo,", "James Nkomo (R-2401),")
        self.assertIn("comms.messages", self.pre("slack__post_message", {"channel_id": "C003", "text": bad}))
        self.assertIn("comms.messages", self.pre("slack__post_message", {**PATTERN_POST[1], "channel_id": "C001"}))

    def test_pattern_post_in_benefits_team_allowed(self):
        self.assertEqual(self.pre("slack__post_message", {**PATTERN_POST[1], "channel_id": "C002"}), set())

    def test_deluca_payroll(self):
        self.assertEqual(self.pre(*PAYROLL), set())
        bad = PAYROLL[1]["text"].replace("04/10/2026", "04/09/2026")
        self.assertIn("comms.messages", self.pre("slack__post_message", {"channel_id": "C004", "text": bad}))

    def test_deluca_closure_post_after_return_allowed(self):
        self.did(*PAYROLL)
        closure = PAYROLL[1]["text"].replace("Return from Leave", "Case Closure")
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C004", "text": closure}), set())

    def test_nkomo_payroll_optional_but_formatted(self):
        ok = ("LEAVE PAYROLL NOTIFICATION: LC-2026-0203, James Nkomo, Intermittent Absence, 04/07/2026, "
              "Intermittent, 8 hours")
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C004", "text": ok}), set())
        self.assertIn("comms.messages", self.pre("slack__post_message", {"channel_id": "C004",
                                                                          "text": "Payroll: James Nkomo out 4/7"}))
        self.assertFalse(any("04/07/2026 LC-2026-0203" in p for r, p in self.done_all()))


class TestPatternEmail(Base):
    def test_compliant(self):
        self.assertEqual(self.pre(*PATTERN_EMAIL), set())
        self.did(*PATTERN_EMAIL)
        self.assertFalse(any("RECURRING ISSUE email" in p for r, p in self.done_all() if r == "comms.messages_sent"))

    def test_wrong_subject(self):
        self.assertIn("comms.messages", self.pre("google_mail__send_email", {**PATTERN_EMAIL[1],
                                                                              "subject": "RECURRING ISSUE Nkomo"}))

    def test_wrong_recipient(self):
        self.assertIn("comms.messages", self.pre("google_mail__send_email", {
            **PATTERN_EMAIL[1], "to": "daniel.whitfield@ridgelinegear.com"}))


class TestNkomoAbsenceLog(Base):
    def test_initial_ok(self):
        self.assertNotIn("nkomo.absence_log", self.done())

    def test_duplicate_row(self):
        self.edit("leave_tracker.xlsx", "ws.append(['LC-2026-0203','R-2401','James Nkomo','04/07/2026',8.0,"
                                        "'Mgr DeLuca',420.0,None])", sheet="Absence Log")
        self.assertIn("nkomo.absence_log", self.done())

    def test_double_counted_balance(self):
        self.edit("leave_tracker.xlsx", "for row in ws.iter_rows(min_row=2):\n"
                                        "    if row[0].value=='LC-2026-0203':\n"
                                        "        row[8].value=60.0; row[9].value=420.0\n", sheet="Leave Tracker")
        self.assertIn("52.0", self.done()["nkomo.absence_log"])


class TestAbsenceAppendOnly(Base):
    def test_edit_existing_row(self):
        self.edit("leave_tracker.xlsx", "ws.cell(row=17, column=5).value = 2.0", sheet="Absence Log")
        self.assertIn("tracker.absence_log_append_only", self.done())

    def test_append_ok(self):
        self.edit("leave_tracker.xlsx", "ws.append(['LC-2026-0203','R-2401','James Nkomo','04/09/2026',8.0,"
                                        "'Employee',420.0,None])", sheet="Absence Log")
        self.assertNotIn("tracker.absence_log_append_only", self.done())


class TestNkomoNote(Base):
    def test_compliant(self):
        self.nkomo_note()
        self.assertNotIn("nkomo.pattern_note", self.done())

    def test_overwritten_notes(self):
        self.edit("leave_tracker.xlsx", "for row in ws.iter_rows(min_row=2):\n"
                                        "    if row[0].value=='LC-2026-0203':\n"
                                        "        row[15].value='Pattern flagged 04/10/2026 - escalated to Benefits "
                                        "Manager per Section 12.'\n", sheet="Leave Tracker")
        self.assertIn("running log", self.done()["nkomo.pattern_note"])


class TestDeluca(Base):
    def test_returned_closing_accepted(self):
        self.deluca(status="Returned — Closing")
        self.assertNotIn("deluca.close", self.done())
        self.assertNotIn("deluca.housekeeping", self.done())

    def test_wrong_end_date(self):
        self.deluca(end="04/09/2026")
        self.assertIn("04/10/2026", self.done()["deluca.close"])

    def test_closed_requires_housekeeping(self):
        self.deluca()
        self.assertIn("deluca.housekeeping", self.done())
        self.did(*CAL)
        self.did(*MOVE)
        self.assertNotIn("deluca.housekeeping", self.done())


class TestMailbox(Base):
    def test_marked(self):
        self.did(*MARK)
        self.assertNotIn("mail.housekeeping", self.done())

    def test_read_only_not_flagged(self):
        self.did("google_mail__mark_emails", {"email_ids": ["35"], "is_read": True})
        self.assertIn("important", self.done()["mail.housekeeping"])

    def test_folder_names(self):
        self.assertIn("mail.folder_names", self.pre("google_mail__move_emails", {"email_ids": ["16"],
                                                                                  "target_folder": "Closed"}))
        self.assertNotIn("mail.folder_names", self.pre(*MOVE))


class TestFamliLog(Base):
    def test_new_row_flagged(self):
        self.edit("famli_coordination_log.xlsx", "ws.append(['R-2317','Elena Vasquez','','04/20/2026',"
                                                 "'Employee own SHC','Pending','','','',''])")
        self.assertIn("famli.no_unconfirmed_row", self.done())

    def test_resave_not_flagged(self):
        self.edit("famli_coordination_log.xlsx", "pass")
        self.assertNotIn("famli.no_unconfirmed_row", self.done())


class TestNoticeFile(Base):
    def test_wrong_location(self):
        self.write("WH-381_LC-2026-0321_20260410.pdf", "%PDF-1.4")
        self.assertIn("files.notice_name", self.done())

    def test_right_location(self):
        self.write("R-2317/WH-381_LC-2026-0321_20260410.pdf", "%PDF-1.4")
        self.assertNotIn("files.notice_name", self.done())


class TestPreProhibitions(Base):
    def test_no_dm(self):
        self.assertIn("comms.no_dm", self.pre("slack__send_dm", {"user_id": "U003", "text": "LC-2026-0203 update"}))
        self.assertNotIn("comms.no_dm", self.pre(*PATTERN_POST))

    def test_no_medical(self):
        tool, args = DENIAL
        self.assertIn("comms.no_medical", self.pre(tool, {**args, "body": args["body"] + "\nGood luck with the surgery."}))
        self.assertNotIn("comms.no_medical", self.pre(*DENIAL))

    def test_no_manager_tags(self):
        self.assertIn("comms.no_manager_tags", self.pre("slack__post_message", {**DENIED_POST[1],
                                                                                 "text": DENIED_POST[1]["text"] + " <@U012>"}))

    def test_cc_hr_only(self):
        tool, args = DENIAL
        self.assertIn("comms.hr_only_cc", self.pre(tool, {**args, "cc": "amy.sandoval@ridgelinegear.com"}))
        self.assertIn("comms.hr_only_cc", self.pre("google_mail__forward_email", {
            "email_id": "35", "to": "amy.sandoval@ridgelinegear.com", "body": "FYI"}))
        self.assertNotIn("comms.hr_only_cc", self.pre("google_mail__forward_email", {
            "email_id": "7", "to": RENATA, "body": "Relevant manager report for RECURRING ISSUE — LC-2026-0203."}))

    def test_external(self):
        self.assertIn("comms.external", self.pre("google_mail__send_email", {
            "to": "hlindqvist@icloud.com", "subject": "Your leave", "body": "Hi Hannah, update on LC-2026-0287."}))

    def test_other_employee(self):
        self.assertIn("comms.other_employee", self.pre("google_mail__send_email", {
            "to": "amy.sandoval@ridgelinegear.com", "subject": "Coverage", "body": "James Nkomo will be out again."}))
        self.assertNotIn("comms.other_employee", self.pre("google_mail__send_email", {
            "to": "marcus.deluca@ridgelinegear.com", "subject": "Coverage", "body": "James Nkomo absence logged."}))

    def test_never(self):
        self.assertIn("comms.never", self.pre("google_mail__send_email", {
            "to": "elenavee@gmail.com", "cc": RENATA, "subject": "FAMLI",
            "body": "Your FAMLI wage replacement will be about $500 per week."}))

    def test_placeholders(self):
        self.assertIn("comms.placeholders", self.pre("slack__post_message", {
            "channel_id": "C001", "text": "FMLA DENIED (INELIGIBILITY): [Case ID], Elena Vasquez, Hours"}))

    def test_payroll_channel(self):
        self.assertIn("comms.payroll_channel", self.pre("slack__post_message", {
            "channel_id": "C004", "text": "RECURRING ISSUE: James Nkomo pattern"}))

    def test_nkomo_confidential(self):
        self.assertIn("nkomo.confidential", self.pre("google_mail__send_email", {
            "to": "james.nkomo@ridgelinegear.com", "subject": "LC-2026-0203",
            "body": "Please provide an updated medical certification."}))
        self.assertIn("nkomo.confidential", self.pre("google_mail__send_email", {
            "to": "marcus.deluca@ridgelinegear.com", "subject": "Nkomo",
            "body": "James Nkomo's absences exceed his certified limits."}))
        self.assertIn("nkomo.confidential", self.pre("slack__post_message", {
            "channel_id": "C001", "text": "LC-2026-0203 pattern concern under review"}))
        self.assertNotIn("nkomo.confidential", self.pre(*PATTERN_POST))

    def test_elena_not_eligible(self):
        self.assertIn("elena.not_eligible", self.pre("google_mail__send_email", {
            "to": "elenavee@gmail.com", "cc": RENATA, "subject": "FMLA",
            "body": "You ARE eligible for FMLA leave. Please return WH-380-E."}))
        self.assertIn("elena.not_eligible", self.pre("google_mail__send_email", {
            "to": "amy.sandoval@ridgelinegear.com", "subject": "Leave Notification — Elena Vasquez",
            "body": "Employee: Elena Vasquez\nLeave type: approved leave\nStart date: 04/20/2026"}))
        self.assertNotIn("elena.not_eligible", self.pre(*DENIAL))

    def test_no_delete(self):
        self.assertIn("files.no_delete", self.pre("syntara__executeBash", {"command": "rm /workdir/leave_history.xlsx"}))
        self.assertNotIn("files.no_delete", self.pre("syntara__executeBash", {"command": "rm /tmp/scratch.txt"}))

    def test_hours_log_readonly(self):
        code = ("import openpyxl\nwb=openpyxl.load_workbook('/workdir/hours_worked_log.xlsx')\n"
                "wb.save('/workdir/hours_worked_log.xlsx')\n")
        self.assertIn("files.hours_log_readonly", self.pre("syntara__executePython", {"code": code}))
        code2 = ("import openpyxl\nh=openpyxl.load_workbook('/workdir/hours_worked_log.xlsx')\n"
                 "wb=openpyxl.load_workbook('/workdir/leave_tracker.xlsx')\nwb.save('/workdir/leave_tracker.xlsx')\n")
        self.assertNotIn("files.hours_log_readonly", self.pre("syntara__executePython", {"code": code2}))


if __name__ == "__main__":
    unittest.main()
