"""Blind unit tests for hr_crestwood_university_ee4d1791 verifiers (SOP + seed data only)."""

from interwhen_sop.tests.base import TaskCase

TASK = "hr_crestwood_university_ee4d1791"

T15_BODY = (
    "Hi Maria,\n\nWe have reviewed your request for leave under the Family and Medical Leave Act (FMLA). Based on our "
    "records, you meet the eligibility requirements (employed for 26 months; 1,420 hours worked in the preceding 12 "
    "months).\n\nTo proceed, please complete and return the Medical Certification Form (mailed to you separately) "
    "within 15 calendar days of this notice (due by 04/27/2026). Failure to return the certification by this date may "
    "result in denial of your FMLA leave request.\n\nIf you have questions, please contact Patricia Huang at "
    "p.huang@crestwood.edu.\n\nBest regards, Crestwood University – Office of Human Resources hr@crestwood.edu")
T15 = ("google_mail__send_email", {"to": "m.torres@crestwood.edu",
                                   "subject": "FMLA Eligibility Notice – Approved — Torres, E-1001", "body": T15_BODY})
FWD = ("google_mail__forward_email", {"email_id": "1", "to": "p.huang@crestwood.edu",
                                      "body": "Forwarding Maria Torres's (E-1001) FMLA request and attached medical "
                                              "certification for review. Jira: LEAVE-2."})
JIRA = ("jira__create_issue", {"project_key": "LEAVE", "summary": "LEAVE-Torres-04122026", "issue_type": "Task",
                               "description": "Employee Name: Maria Torres\nEmployee ID: E-1001\n"
                                              "Assignee: Patricia Huang\nDeadline: 04/27/2026"})
SLACK_FMLA = ("slack__post_message", {"channel_id": "C003", "text": "FMLA REQUEST: Maria Torres, E-1001, Eligible: YES, "
                                                                    "Certification Due: 04/27/2026, Jira: LEAVE-2"})
KIM_COMMENT = ("jira__add_comment", {"issue_key": "OFFBOARD-1", "comment": "04/12/2026 09:00am [11.4] — CONFIRMED "
                                     "RECEIVED — Access revocation confirmation from j.park@crestwood.edu"})
SLACK_KIM = ("slack__post_message", {"channel_id": "C002", "text": "OFFBOARDING COMPLETE: David Kim, E-1002, Separation "
                                                                   "Type: Voluntary Resignation, Last Day: 04/06/2026"})
MARK = ("google_mail__mark_emails", {"email_ids": ["1", "2"], "is_read": True})
MOVE1 = ("google_mail__move_emails", {"email_ids": ["1"], "target_folder": "Leave"})
MOVE2 = ("google_mail__move_emails", {"email_ids": ["2"], "target_folder": "Offboarding"})
JIRA_OK = '{"id":"10010","key":"LEAVE-2"}'

LEAVE_EDIT = ("assert ws.cell(row=2, column=1).value == 'E-1001'\n"
              "ws.cell(row=2, column=col['leave_type'], value='FMLA')\n"
              "ws.cell(row=2, column=col['leave_start_date'], value='06/29/2026')\n"
              "ws.cell(row=2, column=col['leave_end_date'], value='08/07/2026')\n"
              "ws.cell(row=2, column=col['status'], value='Approved – Pending Certification Review')")
ROSTER_EDIT = ("assert ws.cell(row=3, column=1).value == 'E-1002'\n"
               "ws.cell(row=3, column=col['status'], value='Separated')\n"
               "ws.cell(row=3, column=col['last_day'], value='04/06/2026')\n"
               "ws.cell(row=3, column=col['separation_type'], value='Voluntary Resignation')")

GOLDEN = [T15, FWD, JIRA, SLACK_FMLA, KIM_COMMENT, SLACK_KIM, MARK, MOVE1, MOVE2]


class Base(TaskCase):
    TASK = TASK

    def golden(self, skip=()):
        for tool, args in GOLDEN:
            if (tool, args) in skip:
                continue
            self.assertEqual(self.pre(tool, args), set(), (tool, args))
            self.did(tool, args, JIRA_OK if tool == "jira__create_issue" else '{"ok": true}')
        self.edit("leave_tracker.xlsx", LEAVE_EDIT)
        self.edit("employee_roster.xlsx", ROSTER_EDIT)


class TestInitialAndGolden(Base):
    def test_initial_obligations(self):
        self.assertEqual(set(self.done()), {"fmla.messages_sent", "kim.messages_sent", "fmla.jira_ticket",
                                            "kim.jira_update", "fmla.leave_tracker", "kim.roster",
                                            "email.housekeeping"})

    def test_golden_path(self):
        self.golden()
        self.assertEqual(self.done(), {})


class TestFmlaMessages(Base):
    def test_t15_wrong_months_blocked(self):
        args = dict(T15[1], body=T15_BODY.replace("26 months", "25 months"))
        self.assertIn("fmla.messages", self.pre(T15[0], args))

    def test_t15_cc_huang_allowed(self):
        self.assertEqual(self.pre(T15[0], dict(T15[1], cc="p.huang@crestwood.edu")), set())

    def test_t15_to_michael_blocked(self):
        self.assertIn("fmla.messages", self.pre(T15[0], dict(T15[1], to="m.p.torres@crestwood.edu")))

    def test_t17_denial_blocked(self):
        body = ("Hi Maria,\n\nWe have reviewed your request for leave under the Family and Medical Leave Act (FMLA). "
                "Unfortunately, you do not meet the eligibility requirements at this time.")
        self.assertIn("fmla.messages", self.pre("google_mail__send_email", {
            "to": "m.torres@crestwood.edu", "subject": "FMLA Eligibility Notice – Denied — Torres, E-1001", "body": body}))

    def test_t16_blocked_before_approval(self):
        self.assertIn("fmla.messages", self.pre("google_mail__send_email", {
            "to": "m.torres@crestwood.edu", "subject": "FMLA Leave Confirmed — Torres, E-1001",
            "body": "Hi Maria,\n\nYour FMLA leave has been approved. Leave Start Date: 06/29/2026"}))

    def test_t15_sent_twice_blocked(self):
        self.did(*T15)
        self.assertIn("fmla.messages", self.pre(*T15))

    def test_forward_ok_and_new_email_blocked(self):
        self.assertEqual(self.pre(*FWD), set())
        self.assertIn("fmla.messages", self.pre("google_mail__send_email", {
            "to": "p.huang@crestwood.edu", "subject": "Torres FMLA certification",
            "body": "Maria Torres (E-1001) submitted her medical certification."}))

    def test_slack_fmla(self):
        self.assertEqual(self.pre(*SLACK_FMLA), set())
        bad = dict(SLACK_FMLA[1], text=SLACK_FMLA[1]["text"].replace("04/27/2026", "04/26/2026"))
        self.assertIn("fmla.messages", self.pre(SLACK_FMLA[0], bad))
        self.assertIn("fmla.messages", self.pre(SLACK_FMLA[0], dict(SLACK_FMLA[1], channel_id="C007")))

    def test_missing_forward_completion(self):
        self.golden(skip=[FWD])
        self.assertIn("fmla.messages_sent", self.done())

    def test_subject(self):
        self.assertIn("fmla.subject", self.pre(T15[0], dict(T15[1], subject="Template 15 — Torres, E-1001")))
        self.assertNotIn("fmla.subject", self.pre(T15[0], dict(T15[1], subject="FMLA Eligibility Notice - Torres, E-1001")))

    def test_reply_subject(self):
        args = {"email_id": "1", "body": T15_BODY}
        self.assertEqual(self.pre("google_mail__reply_to_email", dict(args, subject="Re: FMLA Leave Request")), set())
        self.assertEqual(self.pre("google_mail__reply_to_email", args), set())
        self.assertIn("email.reply_subject", self.pre("google_mail__reply_to_email", dict(
            args, subject="FMLA Eligibility Notice – Approved — Torres, E-1001")))

    def test_placeholders(self):
        self.assertIn("comms.no_placeholders", self.pre(T15[0], dict(T15[1], body=T15_BODY.replace("Maria", "[First Name]"))))


class TestKim(Base):
    def test_offboarding_complete_post(self):
        self.assertEqual(self.pre(*SLACK_KIM), set())
        bad = dict(SLACK_KIM[1], text="OFFBOARDING COMPLETE: David Kim, E-1002, Last Day: 04/06/2026")
        self.assertIn("kim.messages", self.pre(SLACK_KIM[0], bad))

    def test_resend_template_blocked(self):
        self.assertIn("kim.messages", self.pre("google_mail__send_email", {
            "to": "j.park@crestwood.edu", "subject": "Access Revocation Request — Kim, E-1002",
            "body": "Hi Jenna,\n\nPlease revoke all system access for the following employee: David Kim, E-1002"}))
        self.assertEqual(self.pre("google_mail__reply_to_email", {
            "email_id": "2", "body": "Thanks Jenna, confirmation for David Kim noted."}), set())

    def test_no_new_kim_ticket(self):
        self.assertIn("jira.tickets", self.pre("jira__create_issue", {
            "project_key": "OFFBOARD", "summary": "OFFBOARD-Kim-04062026", "description": "Employee ID: E-1002"}))

    def test_jira_update_completion(self):
        self.did("jira__add_comment", {"issue_key": "LEAVE-2", "comment": KIM_COMMENT[1]["comment"]})
        self.assertIn("kim.jira_update", self.done())
        self.did(*KIM_COMMENT)
        self.assertNotIn("kim.jira_update", self.done())

    def test_roster(self):
        self.edit("employee_roster.xlsx", ROSTER_EDIT.replace("'Voluntary Resignation'", "'Resignation'"))
        self.assertIn("kim.roster", self.done())

    def test_roster_ok(self):
        self.edit("employee_roster.xlsx", ROSTER_EDIT)
        self.assertNotIn("kim.roster", self.done())


class TestOkaforOptional(Base):
    def test_separation_post(self):
        ok = {"channel_id": "C002", "text": "SEPARATION: James Okafor, E-1003, Voluntary Resignation, "
                                            "Last Day: 05/06/2026, Jira: OFFBOARD-2"}
        self.assertEqual(self.pre("slack__post_message", ok), set())
        self.assertIn("okafor.messages", self.pre("slack__post_message", dict(ok, text=ok["text"].replace("05/06", "05/05"))))
        self.assertNotIn("okafor.messages_sent", self.done())

    def test_final_pay(self):
        body = ("Hi Calvin,\n\nPlease process final pay for the following separating employee:\n\nName: James Okafor "
                "Employee ID: E-1003 Last Day of Work: 05/06/2026\nSeparation Type: Voluntary Resignation Accrued PTO "
                "Balance: 28 hours (per leave_tracker.xlsx)\n\nPer Colorado law, final pay is due on the next regular "
                "payday.")
        args = {"to": "c.briggs@crestwood.edu", "subject": "Final Pay Request to Payroll — Okafor, E-1003", "body": body}
        self.assertEqual(self.pre("google_mail__send_email", args), set())
        self.assertIn("okafor.messages", self.pre("google_mail__send_email", dict(args, body=body.replace("28 hours", "36 hours"))))

    def test_okafor_ticket_name(self):
        args = {"project_key": "OFFBOARD", "summary": "OFFBOARD-Okafor-05062026", "description": "Employee ID: E-1003"}
        self.assertEqual(self.pre("jira__create_issue", args), set())
        self.assertIn("jira.tickets", self.pre("jira__create_issue", dict(args, summary="OFFBOARD-Okafor-04122026")))


class TestJira(Base):
    def test_leave_ticket_ok(self):
        self.assertEqual(self.pre(*JIRA), set())

    def test_leave_ticket_bad_name(self):
        self.assertIn("jira.tickets", self.pre(JIRA[0], dict(JIRA[1], summary="Maria Torres FMLA request")))

    def test_leave_ticket_missing_assignee(self):
        self.assertIn("jira.tickets", self.pre(JIRA[0], dict(
            JIRA[1], description="Employee Name: Maria Torres\nEmployee ID: E-1001")))

    def test_leave_ticket_duplicate(self):
        self.did(*JIRA, result=JIRA_OK)
        self.assertNotIn("fmla.jira_ticket", self.done())
        self.assertIn("jira.tickets", self.pre(*JIRA))

    def test_comment_format(self):
        self.assertEqual(self.pre(*KIM_COMMENT), set())
        self.assertIn("jira.comment_format", self.pre("jira__add_comment", {
            "issue_key": "LEAVE-2", "comment": "04/12/2026 [12.1] — TEMPLATE SENT — Template 15 to m.torres@crestwood.edu"}))
        self.assertIn("jira.comment_format", self.pre("jira__add_comment", {
            "issue_key": "OFFBOARD-1", "comment": "IT confirmed access revoked."}))


class TestMisc(Base):
    def test_calendar(self):
        ok = {"summary": "FMLA Certification Due – Maria Torres", "start": {"date": "2026-04-27"}, "end": {"date": "2026-04-28"}}
        self.assertEqual(self.pre("google_calendar__create_event", ok), set())
        self.assertIn("fmla.calendar", self.pre("google_calendar__create_event", dict(ok, start={"date": "2026-04-26"})))
        self.assertIn("fmla.calendar", self.pre("google_calendar__create_event", dict(
            ok, summary="Reminder: Torres certification deadline")))

    def test_no_dm(self):
        self.assertIn("slack.no_dm", self.pre("slack__send_dm", {"user_id": "U002", "text": "Maria Torres FMLA cert received"}))

    def test_iso_dates(self):
        args = dict(SLACK_FMLA[1], text="FMLA REQUEST: Maria Torres, E-1001, Eligible: YES, Certification Due: "
                                        "2026-04-27, Jira: LEAVE-2")
        self.assertIn("dates.format", self.pre(SLACK_FMLA[0], args))
        self.assertNotIn("dates.format", self.pre(*SLACK_FMLA))

    def test_folders(self):
        self.assertEqual(self.pre(*MOVE1), set())
        self.assertIn("email.folders", self.pre(MOVE1[0], {"email_ids": ["1"], "target_folder": "Offboarding"}))
        self.assertIn("email.folders", self.pre(MOVE1[0], {"email_ids": ["2"], "target_folder": "Access Revocation"}))

    def test_housekeeping_wrong_folder(self):
        self.golden(skip=[MOVE2])
        self.did(MOVE2[0], {"email_ids": ["2"], "target_folder": "General"})
        self.assertIn("email.housekeeping", self.done())

    def test_leave_tracker_wrong(self):
        self.edit("leave_tracker.xlsx", LEAVE_EDIT.replace("'Approved – Pending Certification Review'", "'Approved'"))
        self.assertIn("fmla.leave_tracker", self.done())

    def test_leave_tracker_datetime_rejected(self):
        self.edit("leave_tracker.xlsx", LEAVE_EDIT.replace(
            "value='06/29/2026'", "value=__import__('datetime').datetime(2026, 6, 29)"))
        self.assertIn("fmla.leave_tracker", self.done())

    def test_leave_tracker_pto_readonly(self):
        self.edit("leave_tracker.xlsx", LEAVE_EDIT + "\nws.cell(row=2, column=col['current_pto_balance'], value=40)")
        self.assertTrue(any("read-only" in p for r, p in self.done_all() if r == "fmla.leave_tracker"))

    def test_leave_tracker_ok(self):
        self.edit("leave_tracker.xlsx", LEAVE_EDIT)
        self.assertNotIn("fmla.leave_tracker", self.done())

    def test_scope_other_workbook(self):
        self.golden()
        self.edit("benefits_enrollment.xlsx", "ws.cell(row=2, column=7, value='On Leave')")
        self.assertIn("workbooks.scope", self.done())

    def test_scope_other_row(self):
        self.golden()
        self.edit("leave_tracker.xlsx", "ws.cell(row=4, column=col['status'], value='Approved')")
        self.assertIn("workbooks.scope", self.done())


if __name__ == "__main__":
    import unittest
    unittest.main()
