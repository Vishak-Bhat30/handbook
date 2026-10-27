"""Blind unit tests for hr_crestwood_university_da394eac verifiers (seed data + SOP only)."""

from __future__ import annotations

import json

from interwhen_sop.tests.base import TaskCase

SEND = "google_mail__send_email"
REPLY = "google_mail__reply_email"
POST = "slack__post_message"
SIG = "\n\nBest regards,\nCrestwood University – Office of Human Resources\nhr@crestwood.edu"

PTO = {"email_id": "8", "body": "Hi Lisa,\n\nYour current PTO balance as of 04/07/2026 is 68 hours. Your accrual rate is "
                                "4.62 hours per pay period.\n\nIf you have questions about your balance or accrual "
                                "rate, please contact Patricia Huang at p.huang@crestwood.edu." + SIG}
OOS = {"channel_id": "CGENERAL", "text": "[OUT OF SCOPE] – HR office light bulb out – Main Campus rm 214"}
T10 = {"to": "w.trent@crestwood.edu", "subject": "Default Benefits Enrollment Confirmation — Trent, CU-1022",
       "body": "Hi William,\n\nAs your benefits enrollment deadline of 04/02/2026 has passed without a completed "
               "enrollment or waiver, you have been automatically enrolled in Crestwood University's default health "
               "plan effective 05/01/2026.\n\nIf you have questions or believe this is in error, please contact "
               "Patricia Huang at p.huang@crestwood.edu." + SIG}
T6 = {"to": "p.huang@crestwood.edu", "cc": "t.salazar@crestwood.edu",
      "subject": "I-9 Urgent Reminder — Salazar, CU-1026",
      "body": "Hi Patricia,\n\nThis is an urgent reminder regarding the I-9 Employment Eligibility Verification for "
              "Tomás Salazar (CU-1026). The federal deadline for completing Section 2 of the I-9 is 04/08/2026. We "
              "have not yet received the completed form.\n\nPlease examine the employee's original identity and work "
              "authorization documents, complete Section 2 of the I-9, and email the scanned signed form to "
              "hr@crestwood.edu as soon as possible." + SIG}
T18 = {"to": "m.cross@crestwood.edu", "subject": "FMLA Certification Overdue — Cross, CU-1023",
       "body": "Hi Meghan,\n\nThis is a reminder that your FMLA Medical Certification Form was due on 04/07/2026 and "
               "has not been received. Your FMLA leave request cannot be processed without this documentation.\n\n"
               "Please return the completed form as soon as possible. If you need an extension, please contact "
               "Patricia Huang at p.huang@crestwood.edu immediately." + SIG}
HUANG = {"to": "p.huang@crestwood.edu", "subject": "FMLA Deadline Passed - CU-1023",
         "body": "Meghan Cross FMLA Certification overdue"}
CROSS_SLACK = {"channel_id": "CLEAVE",
               "text": "FMLA CERTIFICATION OVERDUE: Meghan Cross, CU-1023, Due: 04/07/2026, 1 day(s) overdue"}
TRENT_SLACK = {"channel_id": "CONBOARDING", "text": "ONBOARDING COMPLETE: William Trent, CU-1022, 04/07/2026"}

TRENT_BEN = ("import datetime\nfor r in range(2, ws.max_row+1):\n    if ws.cell(r,1).value=='CU-1022':\n"
             "        ws.cell(r,col['Plan Elected']).value='Default Enrollment'\n"
             "        ws.cell(r,col['Enrollment Date']).value=datetime.datetime(2026,5,1)\n"
             "        ws.cell(r,col['Status']).value='Default Enrollment'\n")
TRENT_CHK = ("import datetime\nfor r in range(2, ws.max_row+1):\n    if ws.cell(r,1).value=='CU-1022':\n"
             "        ws.cell(r,col['Benefits Enrolled']).value=datetime.datetime(2026,5,1)\n")
TRENT_ROSTER = ("for r in range(2, ws.max_row+1):\n    if ws.cell(r,1).value=='CU-1022':\n"
                "        ws.cell(r,col['Status']).value='Active'\n")


def comment(key, text):
    return ("jira__add_comment", {"issue_key": key, "comment": text})


COMMENTS = [
    comment("HR-7", "04/07/2026 12:00pm [11.3] — TEMPLATE SENT — Template 10 to w.trent@crestwood.edu"),
    comment("HR-7", "04/07/2026 12:00pm [11.3] — SPREADSHEET UPDATED — benefits_enrollment.xlsx — Plan Elected set to "
                    "Default Enrollment"),
    comment("HR-7", "04/07/2026 12:00pm [11.4] — SLACK POSTED — hr-onboarding"),
    comment("HR-6", "04/07/2026 12:00pm [11.2] — TEMPLATE SENT — Template 6 to p.huang@crestwood.edu"),
    comment("HR-1", "04/07/2026 12:00pm [13.1] — TEMPLATE SENT — Template 18 to m.cross@crestwood.edu"),
    comment("HR-1", "04/07/2026 12:00pm [13.1] — SLACK POSTED — hr-leave-requests"),
]
CLOSE = ("jira__update_issue", {"issue_key": "HR-7", "fields": json.dumps(
    {"description": "New hire onboarding for William Trent (CU-1022). Start Date: 03/03/2026.\nStatus – CLOSED"})})


class Base(TaskCase):
    TASK = "hr_crestwood_university_da394eac"

    def golden(self, skip=()):
        calls = [(REPLY, PTO), (POST, OOS), (SEND, T10), (SEND, T6), (SEND, T18), (SEND, HUANG), (POST, CROSS_SLACK),
                 (POST, TRENT_SLACK), ("google_mail__move_emails", {"email_ids": ["8"], "target_folder": "Leave"}),
                 ("google_mail__move_emails", {"email_ids": ["11"], "target_folder": "General"}), *COMMENTS, CLOSE]
        for i, (tool, args) in enumerate(calls):
            if i not in skip:
                self.did(tool, args)
        self.edit("benefits_enrollment.xlsx", TRENT_BEN)
        self.edit("onboarding_checklist.xlsx", TRENT_CHK)
        self.edit("employee_roster.xlsx", TRENT_ROSTER)


class TestGolden(Base):
    def test_initial_obligations(self):
        rules = {r for r, _ in self.done_all()}
        self.assertEqual(rules, {"comms.messages_sent", "mail.filed", "wb.trent_default", "wb.trent_active",
                                 "jira.hr7_closed", "jira.comments"})

    def test_golden_path(self):
        self.golden()
        self.assertEqual(self.done(), {})

    def test_golden_calls_not_blocked(self):
        for tool, args in [(REPLY, PTO), (POST, OOS), (SEND, T10), (SEND, T6), (SEND, T18), (SEND, HUANG),
                           (POST, CROSS_SLACK), (POST, TRENT_SLACK), *COMMENTS, CLOSE,
                           ("google_mail__move_emails", {"email_ids": ["8"], "target_folder": "Leave"})]:
            self.assertEqual(self.pre(tool, args), set(), (tool, args))


class TestMessages(Base):
    def test_pto_wrong_balance(self):
        self.assertEqual(self.pre(REPLY, {**PTO, "body": PTO["body"].replace("68 hours", "72.62 hours")}),
                         {"comms.messages"})

    def test_pto_new_email_default_subject_ok(self):
        args = {"to": "l.fontaine@crestwood.edu", "subject": "PTO Balance Response — Fontaine, CU-1010",
                "body": PTO["body"]}
        self.assertEqual(self.pre(SEND, args), set())

    def test_oos_wrong_channel(self):
        self.assertEqual(self.pre(POST, {**OOS, "channel_id": "CESCALATIONS"}), {"comms.messages"})

    def test_oos_reply_to_facilities_blocked(self):
        self.assertEqual(self.pre(REPLY, {"email_id": "11", "body": "We can schedule access Tuesday."}),
                         {"comms.messages"})

    def test_t10_wrong_effective_date(self):
        self.assertEqual(self.pre(SEND, {**T10, "body": T10["body"].replace("05/01/2026", "05/02/2026")}),
                         {"comms.messages"})

    def test_t6_missing_cc(self):
        args = {k: v for k, v in T6.items() if k != "cc"}
        self.assertEqual(self.pre(SEND, args), {"comms.messages"})

    def test_t6_personal_cc_ok(self):
        self.assertEqual(self.pre(SEND, {**T6, "cc": "tomas.salazar.co@protonmail.com"}), set())

    def test_t6_wrong_hiring_manager(self):
        self.assertEqual(self.pre(SEND, {**T6, "to": "k.cho@crestwood.edu", "body": T6["body"].replace("Patricia", "Karen")}),
                         {"comms.messages"})

    def test_t6_not_template(self):
        args = {**T6, "body": "Hi Patricia,\n\nSection 2 for Tomás Salazar (CU-1026) is still missing. Due 04/08/2026."}
        self.assertEqual(self.pre(SEND, args), {"comms.messages"})

    def test_t18_missing_due_date(self):
        self.assertEqual(self.pre(SEND, {**T18, "body": T18["body"].replace(" on 04/07/2026", "")}), {"comms.messages"})

    def test_t18_reply_subject_ok(self):
        self.assertEqual(self.pre(SEND, {**T18, "subject": "Re: FMLA Leave Request"}), set())

    def test_huang_en_dash_subject(self):
        self.assertEqual(self.pre(SEND, {**HUANG, "subject": "FMLA Deadline Passed – CU-1023"}), {"comms.messages"})

    def test_huang_extra_body(self):
        self.assertEqual(self.pre(SEND, {**HUANG, "body": "Hi Patricia,\n\nMeghan Cross FMLA Certification overdue.\n\nThanks"}),
                         {"comms.messages"})

    def test_t18_cc_huang_not_captured_by_huang_spec(self):
        self.assertEqual(self.pre(SEND, {**T18, "cc": "p.huang@crestwood.edu"}), set())

    def test_cross_slack_wrong_due(self):
        self.assertEqual(self.pre(POST, {**CROSS_SLACK, "text": CROSS_SLACK["text"].replace("04/07", "04/08")}),
                         {"comms.messages"})

    def test_onboarding_complete_other_employee(self):
        self.assertEqual(self.pre(POST, {**TRENT_SLACK, "text": "ONBOARDING COMPLETE: Rafael Mendez, CU-1021, 04/07/2026"}),
                         {"comms.messages"})

    def test_i9_overdue_post_blocked(self):
        args = {"channel_id": "CESCALATIONS", "text": "I-9 OVERDUE: Tomás Salazar, CU-1026, Start Date: 04/02/2026, "
                                                      "Deadline: 04/08/2026 – Section 2 not received"}
        self.assertEqual(self.pre(POST, args), {"comms.messages"})

    def test_template7_blocked(self):
        args = {"to": "p.huang@crestwood.edu", "subject": "I-9 Deadline Passed — Salazar, CU-1026",
                "body": "Hi Patricia,\n\nThis is to inform you that the I-9 for Tomás Salazar (CU-1026) has not been "
                        "completed by the federal deadline. Tomás Salazar may not continue working until this "
                        "requirement is fulfilled."}
        self.assertIn("comms.messages", self.pre(SEND, args))

    def test_benefit_reminder_blocked(self):
        args = {"to": "r.mendez@crestwood.edu", "subject": "Benefits Enrollment Reminder — Mendez, CU-1021",
                "body": "Hi Rafael,\n\nThis is a reminder that your benefits enrollment deadline is 04/25/2026."}
        self.assertEqual(self.pre(SEND, args), {"comms.messages"})

    def test_cross_denial_blocked(self):
        args = {"to": "m.cross@crestwood.edu", "subject": "FMLA",
                "body": "Hi Meghan,\n\nYour FMLA leave request has been denied because the certification was not received."}
        self.assertIn("comms.messages", self.pre(SEND, args))

    def test_duplicate_send_blocked(self):
        self.did(SEND, T18)
        self.assertEqual(self.pre(SEND, T18), {"comms.messages"})

    def test_messages_sent_completion(self):
        self.did(SEND, T18)
        self.did(SEND, HUANG)
        probs = " ".join(p for r, p in self.done_all() if r == "comms.messages_sent")
        self.assertNotIn("Template 18", probs)
        self.assertNotIn("FMLA Deadline Passed", probs)
        self.assertIn("Template 6", probs)


class TestOtherPre(Base):
    def test_placeholders(self):
        self.assertIn("comms.no_placeholders",
                      self.pre(POST, {"channel_id": "CGENERAL", "text": "Update for [Employee Name] posted"}))
        self.assertNotIn("comms.no_placeholders", self.pre(POST, OOS))

    def test_slack_dm(self):
        self.assertEqual(self.pre("slack__send_dm", {"user_id": "UHUANG", "text": "Cross cert overdue"}),
                         {"slack.no_dm"})
        self.assertNotIn("slack.no_dm", self.pre(POST, CROSS_SLACK))

    def test_no_new_tickets(self):
        self.assertEqual(self.pre("jira__create_issue", {"project_key": "HR", "summary": "PTO inquiry – Fontaine"}),
                         {"jira.no_new_tickets"})
        self.assertEqual(self.pre(*COMMENTS[0]), set())

    def test_folders(self):
        mv = "google_mail__move_emails"
        self.assertEqual(self.pre(mv, {"email_ids": ["11"], "target_folder": "General"}), set())
        self.assertEqual(self.pre(mv, {"email_ids": ["8"], "target_folder": "General"}), {"mail.folders"})
        self.assertEqual(self.pre(mv, {"email_ids": ["8"], "target_folder": "PTO"}), {"mail.folders"})
        self.assertEqual(self.pre("google_mail__create_folder", {"name": "Facilities"}), {"mail.folders"})


class TestCompletion(Base):
    def test_mail_filed(self):
        self.assertIn("mail.filed", self.done())
        self.did("google_mail__move_emails", {"email_ids": ["8"], "target_folder": "Leave"})
        self.did("google_mail__move_emails", {"email_ids": ["11"], "target_folder": "General"})
        self.assertNotIn("mail.filed", self.done())

    def test_trent_default(self):
        self.edit("benefits_enrollment.xlsx", TRENT_BEN)
        self.edit("onboarding_checklist.xlsx", TRENT_CHK.replace("2026,5,1", "2026,4,2"))
        probs = [p for r, p in self.done_all() if r == "wb.trent_default"]
        self.assertEqual(len(probs), 1)
        self.assertIn("Benefits Enrolled", probs[0])
        self.edit("onboarding_checklist.xlsx", TRENT_CHK)
        self.assertNotIn("wb.trent_default", self.done())

    def test_trent_active(self):
        self.assertIn("wb.trent_active", self.done())
        self.edit("employee_roster.xlsx", TRENT_ROSTER)
        self.assertNotIn("wb.trent_active", self.done())

    def test_no_unrequested_checklist(self):
        self.assertNotIn("wb.no_unrequested", self.done())
        self.edit("onboarding_checklist.xlsx", "for r in range(2, ws.max_row+1):\n    if ws.cell(r,1).value=='CU-1026':\n"
                                               "        ws.cell(r,col['I-9 Completed']).value='04/02/2026'\n")
        self.assertIn("CU-1026", self.done().get("wb.no_unrequested", ""))

    def test_no_unrequested_leave_tracker(self):
        self.edit("leave_tracker.xlsx", "for r in range(2, ws.max_row+1):\n    if ws.cell(r,1).value=='CU-1023':\n"
                                        "        ws.cell(r,8).value='Certification Overdue'\n", sheet="Leave Tracker")
        self.assertIn("leave_tracker", self.done().get("wb.no_unrequested", ""))

    def test_hr7_closed(self):
        self.did("jira__transition_issue", {"issue_key": "HR-7", "transition_id": "2"})
        self.assertIn("jira.hr7_closed", self.done())
        self.did(*CLOSE)
        self.assertNotIn("jira.hr7_closed", self.done())

    def test_jira_comments(self):
        for c in COMMENTS[:-1]:
            self.did(*c)
        probs = [p for r, p in self.done_all() if r == "jira.comments"]
        self.assertEqual(len(probs), 1)
        self.assertIn("HR-1", probs[0])
        self.did(*COMMENTS[-1])
        self.assertNotIn("jira.comments", self.done())
