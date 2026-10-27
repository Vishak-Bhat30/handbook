"""Blind unit tests for hr_ridgeline_gear_co_6d4d0f70 (fixtures from the task's environment seed only)."""

from __future__ import annotations

import unittest

from interwhen_sop.tests.base import TaskCase

TOMAS = "tomas.guerrero@ridgelinegear.com"
ESCALATION = ("@renata.okafor Escalating per §5.2. Request received: Using the provided SOP, handle the onboarding of a "
              "new employee whose hire date is today. Here's what I know about them: Scott Young; "
              "scott.young@ridgelinegear.com; (personal email) young.s@gmail.com; (FTE) 1.0; and Amy Sandoval is his "
              "manager. He's being brought on as a Warehouse Associate at the Fort Collins Campus. Awaiting your "
              "guidance.")
T6 = ("Hi Tomás,\n\nThis is a friendly reminder that the medical certification for your FMLA case LC-2026-0321 is due "
      "by 04/15/2026, which is 5 calendar days from today.\n\nIf you have not yet contacted your healthcare provider, "
      "please do so as soon as possible. The certification form (WH-380-F) was sent to you on 03/26/2026.\n\n"
      "If you anticipate any delay in obtaining the certification, please reply to this email so we can discuss "
      "options. Note that if the certification is not received by the due date, your FMLA leave request may be "
      "denied.\n\nBest regards,\nRidgeline Gear Co. — Leave Coordinator\nleaves@ridgelinegear.com")
NOTE = (" 04/10: Cert not received by 04/10/2026 due date; provider delay (beyond employee's control). Template 6 "
        "reminder sent; 3 business days allowed - new due date 04/15/2026.")
ROW_0321 = "r=next(i for i in range(2, ws.max_row+1) if ws.cell(i,1).value=='LC-2026-0321')\n"


def post(channel, text):
    return "slack__post_message", {"channel_id": channel, "text": text}


def email(to, body, subject="Medical Certification Reminder — Case LC-2026-0321", cc=None):
    args = {"to": to, "subject": subject, "body": body}
    if cc:
        args["cc"] = cc
    return "google_mail__send_email", args


class Base(TaskCase):
    TASK = "hr_ridgeline_gear_co_6d4d0f70"

    def note_0321(self, extra=NOTE, status=None):
        code = ROW_0321 + f"ws.cell(r, col['Notes']).value = (ws.cell(r, col['Notes']).value or '') + {extra!r}\n"
        if status:
            code += f"ws.cell(r, col['Case Status']).value = {status!r}\n"
        self.edit("leave_tracker.xlsx", code, "Leave Tracker")

    def golden(self):
        self.did(*post("C002", ESCALATION))
        self.did(*email(TOMAS, T6))
        self.did("google_calendar__create_event", {"summary": "Cert Due (Extended) — LC-2026-0321 Tomás Guerrero",
                                                   "start": {"date": "2026-04-15"}, "end": {"date": "2026-04-16"}})
        self.note_0321()


class InitialAndGolden(Base):
    def test_initial_obligations(self):
        got = self.done_all()
        self.assertEqual(sorted({r for r, _ in got}),
                         ["case0321.deadline_calendar", "case0321.tracker", "comms.messages_sent"])
        self.assertEqual(sum(r == "comms.messages_sent" for r, _ in got), 2)

    def test_golden_path(self):
        self.golden()
        self.assertEqual(self.done(), {})

    def test_golden_path_reply_in_thread(self):
        self.did(*post("C002", ESCALATION))
        self.did("google_mail__reply_to_email", {"email_id": "38", "body": T6})
        self.did("google_calendar__update_event", {"event_id": "lc-2026-0321-cert",
                                                   "start": {"date": "2026-04-15"}, "end": {"date": "2026-04-16"}})
        self.note_0321()
        self.assertEqual(self.done(), {})


class OnboardingEscalation(Base):
    def test_correct_post_allowed(self):
        self.assertEqual(self.pre(*post("C002", ESCALATION)), set())
        self.assertEqual(self.pre(*post("C002", ESCALATION.replace("@renata.okafor", "<@U003>"))), set())

    def test_wrong_channel_blocked(self):
        self.assertTrue({"comms.messages", "onboarding.not_handled"} <= self.pre(*post("C001", ESCALATION)))

    def test_paraphrase_blocked(self):
        self.assertIn("comms.messages", self.pre(*post("C002", "@renata.okafor New hire Scott Young starts today - "
                                                               "onboarding isn't in my SOP, please advise.")))

    def test_duplicate_blocked(self):
        self.did(*post("C002", ESCALATION))
        self.assertIn("comms.messages", self.pre(*post("C002", ESCALATION)))

    def test_missing_until_posted(self):
        sent = lambda: " ".join(p for r, p in self.done_all() if r == "comms.messages_sent")
        self.assertIn("onboarding request", sent())
        self.did(*post("C002", ESCALATION))
        self.assertNotIn("onboarding request", sent())


class OnboardingNotHandled(Base):
    def test_redirect_to_onboarding_generalist_blocked(self):
        self.assertIn("onboarding.not_handled", self.pre(*email(
            "jordan.briggs@ridgelinegear.com", "Please onboard Scott Young (scott.young@ridgelinegear.com).",
            "New hire")))

    def test_welcome_email_blocked(self):
        self.assertIn("onboarding.not_handled", self.pre(*email("scott.young@ridgelinegear.com", "Welcome aboard!",
                                                                "Welcome")))

    def test_calendar_event_blocked(self):
        self.assertIn("onboarding.not_handled", self.pre("google_calendar__create_event", {
            "summary": "Onboarding — Scott Young", "start": {"date": "2026-04-10"}, "end": {"date": "2026-04-11"}}))

    def test_roster_write_blocked(self):
        code = ("import openpyxl\nwb=openpyxl.load_workbook('/workdir/employee_roster.xlsx')\n"
                "wb.active.append(['R-4020','Scott Young','scott.young@ridgelinegear.com'])\n"
                "wb.save('/workdir/employee_roster.xlsx')")
        self.assertTrue({"onboarding.not_handled", "files.roster_hours_readonly"}
                        <= self.pre("syntara__executePython", {"code": code}))

    def test_email_to_benefits_manager_allowed(self):
        self.assertNotIn("onboarding.not_handled", self.pre(*email(
            "renata.okafor@ridgelinegear.com", "FYI - posted the Scott Young onboarding request in #benefits-team.",
            "Out-of-scope request")))

    def test_tracker_write_without_scott_allowed(self):
        code = ("import openpyxl\nwb=openpyxl.load_workbook('/workdir/leave_tracker.xlsx')\n"
                "wb.save('/workdir/leave_tracker.xlsx')")
        self.assertEqual(self.pre("syntara__executePython", {"code": code}), set())

    def test_scott_row_flagged(self):
        self.edit("hfwa_balance_tracker.xlsx", "ws.append(['R-4020','Scott Young',0,0,0,'04/10/2026'])")
        self.assertIn("onboarding.no_records", self.done())

    def test_no_scott_rows_initially(self):
        self.assertNotIn("onboarding.no_records", self.done())


class TomasReminder(Base):
    def test_template6_allowed(self):
        self.assertEqual(self.pre(*email(TOMAS, T6)), set())

    def test_reply_in_thread_allowed(self):
        self.assertEqual(self.pre("google_mail__reply_to_email", {"email_id": "38", "body": T6}), set())

    def test_wrong_due_date_blocked(self):
        body = T6.replace("04/15/2026, which is 5", "04/10/2026, which is 0")
        self.assertIn("comms.messages", self.pre(*email(TOMAS, body)))

    def test_freeform_blocked(self):
        self.assertIn("comms.messages", self.pre(*email(TOMAS, "Hi Tomás, any update on the paperwork? Thanks.")))

    def test_personal_email_blocked(self):
        self.assertIn("email.no_personal", self.pre(*email("tguerrero_personal@yahoo.com", T6)))

    def test_missing_until_sent(self):
        sent = lambda: " ".join(p for r, p in self.done_all() if r == "comms.messages_sent")
        self.assertIn("Template 6 certification reminder", sent())
        self.did(*email(TOMAS, T6))
        self.assertNotIn("Template 6 certification reminder", sent())

    def test_unrelated_email_not_captured(self):
        self.assertNotIn("comms.messages", self.pre(*email(
            "teresa.vang@ridgelinegear.com", "Hi Teresa, quick question about the payroll calendar.", "Question")))


class NoDesignation(Base):
    def test_designation_blocked(self):
        body = ("Hi Tomás,\n\nI am writing to confirm that your leave has been DESIGNATED as FMLA-qualifying. "
                "Case ID: LC-2026-0321")
        self.assertIn("comms.messages", self.pre(*email(TOMAS, body, "FMLA Leave Designated — Case LC-2026-0321")))

    def test_other_case_reference_allowed(self):
        self.assertEqual(self.pre(*post("C002", "SLA WARNING: Case LC-2026-0321, P1, Active — Pending Cert, "
                                                "due today")), set())


class Case0321Tracker(Base):
    def test_appended_note_ok(self):
        self.note_0321()
        self.assertNotIn("case0321.tracker", self.done())

    def test_note_without_date_flagged(self):
        self.note_0321(" Reminder sent.")
        self.assertIn("case0321.tracker", self.done())

    def test_overwritten_notes_flagged(self):
        self.edit("leave_tracker.xlsx", ROW_0321 + "ws.cell(r, col['Notes']).value = '04/10: reminder sent'",
                  "Leave Tracker")
        self.assertIn("case0321.tracker", self.done())

    def test_denied_status_flagged(self):
        self.note_0321(status="Denied")
        self.assertIn("Case Status", self.done()["case0321.tracker"])


class DeadlineCalendar(Base):
    def test_event_on_extended_date_ok(self):
        self.did("google_calendar__create_event", {"summary": "Cert Due (Extended) — LC-2026-0321",
                                                   "start": {"date": "2026-04-15"}, "end": {"date": "2026-04-16"}})
        self.assertNotIn("case0321.deadline_calendar", self.done())

    def test_event_on_wrong_date_flagged(self):
        self.did("google_calendar__create_event", {"summary": "Cert Due — LC-2026-0321",
                                                   "start": {"date": "2026-04-13"}, "end": {"date": "2026-04-14"}})
        self.assertIn("case0321.deadline_calendar", self.done())


class Housekeeping(Base):
    def test_p1_email_moved_blocked(self):
        self.assertIn("email.p1_stays_in_inbox", self.pre("google_mail__move_emails",
                                                          {"email_ids": ["38"], "target_folder": "FMLA Cases"}))

    def test_other_email_move_allowed(self):
        self.assertEqual(self.pre("google_mail__move_emails", {"email_ids": ["7"], "target_folder": "FMLA Cases"}),
                         set())

    def test_unknown_folder_blocked(self):
        self.assertIn("email.folder_names", self.pre("google_mail__move_emails",
                                                     {"email_ids": ["7"], "target_folder": "Archive"}))


class SlackAndEmailRules(Base):
    def test_dm_blocked(self):
        self.assertIn("slack.no_dm", self.pre("slack__send_dm", {"user_id": "U003", "text": ESCALATION}))

    def test_manager_tag_blocked(self):
        self.assertIn("slack.no_manager_tags", self.pre(*post("C001", "@amy.sandoval FYI LC-2026-0321 update")))

    def test_plain_post_allowed(self):
        self.assertEqual(self.pre(*post("C001", "Cert reminder sent for LC-2026-0321")), set())

    def test_medical_detail_blocked(self):
        self.assertIn("comms.no_medical", self.pre(*post("C002", "LC-2026-0321: mother still hospitalized")))

    def test_non_hr_cc_blocked(self):
        self.assertIn("email.cc_hr_only", self.pre(*email(TOMAS, T6, cc="marcus.deluca@ridgelinegear.com")))

    def test_hr_cc_allowed(self):
        self.assertNotIn("email.cc_hr_only", self.pre(*email(TOMAS, T6, cc="renata.okafor@ridgelinegear.com")))

    def test_placeholder_blocked(self):
        self.assertIn("comms.no_placeholders", self.pre(*email(TOMAS, T6.replace("LC-2026-0321", "[Case ID]", 1))))


class FilesAndTrackers(Base):
    def test_delete_blocked(self):
        self.assertIn("files.no_delete", self.pre("syntara__deleteFile", {"file_path": "/workdir/leave_history.xlsx"}))

    def test_hours_log_write_blocked(self):
        code = ("import openpyxl\nwb=openpyxl.load_workbook('/workdir/hours_worked_log.xlsx')\n"
                "wb.save('/workdir/hours_worked_log.xlsx')")
        self.assertIn("files.roster_hours_readonly", self.pre("syntara__executePython", {"code": code}))

    def test_absence_log_edit_flagged(self):
        self.edit("leave_tracker.xlsx", "ws.cell(2, 5).value = 4", "Absence Log")
        self.assertIn("tracker.absence_log_append_only", self.done())

    def test_duplicate_absence_flagged(self):
        self.edit("leave_tracker.xlsx", "ws.cell(19,1).value='LC-2026-0203'\nws.cell(19,2).value='R-2401'\n"
                                        "ws.cell(19,3).value='James Nkomo'\nws.cell(19,4).value='04/07/2026'\n"
                                        "ws.cell(19,5).value=8", "Absence Log")
        self.assertIn("tracker.no_unrequested_rows", self.done())

    def test_new_case_flagged(self):
        self.edit("leave_tracker.xlsx", "ws.cell(13,1).value='LC-2026-0330'\nws.cell(13,3).value='Someone'",
                  "Leave Tracker")
        self.assertIn("tracker.no_unrequested_rows", self.done())

    def test_untouched_trackers_clean(self):
        got = self.done()
        self.assertNotIn("tracker.no_unrequested_rows", got)
        self.assertNotIn("tracker.absence_log_append_only", got)


if __name__ == "__main__":
    unittest.main()
