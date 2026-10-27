"""Blind unit tests for hr_crestwood_university_2071c562 (fixtures from the task seed only)."""

from __future__ import annotations

from interwhen_sop.tests.base import TaskCase

TICKET = "OFFBOARD-Teodoor-04192026"
SEP = f"SEPARATION: Gerta Teodoor, 10741, Voluntary Resignation, Last Day: 04/19/2026, Jira: {TICKET}"
T13_BODY = ("Hi Jenna,\n\nPlease revoke all system access for the following employee:\n\n"
            "Name: Gerta Teodoor\nEmployee ID: 10741\nLast Day of Work: 04/19/2026\n"
            "Timing: End of business on last day\n\n"
            "This includes email, VPN, building access, and all university systems. Please confirm when complete.\n\n"
            "Best regards,\nCrestwood University – Office of Human Resources\nhr@crestwood.edu")
T14_BODY = ("Hi Gerta,\n\nAs part of our offboarding process, we would like to offer you the opportunity to participate "
            "in an exit interview. This is completely voluntary and confidential. Your feedback helps us improve the "
            "employee experience at Crestwood University.\n\nIf you are interested, please reply with your "
            "availability and we will schedule a 30-minute meeting before your last day of 04/19/2026.\n\n"
            "Best regards,\nCrestwood University – Office of Human Resources\nhr@crestwood.edu")
T13 = {"to": ["j.park@crestwood.edu"], "subject": "Template 13 — Teodoor, 10741", "body": T13_BODY}
T14 = {"to": ["g.teodoor@crestwood.edu"], "subject": "Template 14 — Teodoor, 10741", "body": T14_BODY}
JIRA = {"project_key": "OFFBOARD", "summary": TICKET, "issue_type": "Task", "assignee": "U_OKONKWO",
        "description": "Employee Name: Gerta Teodoor\nEmployee ID: 10741\nLast Day: 04/19/2026"}
FWD_PAY = {"email_id": "4", "to": ["c.briggs@crestwood.edu"], "body": "Payroll discrepancy raised by Ardisj Parke."}
FWD_ER = {"email_id": "4", "to": ["m.voss@crestwood.edu"], "body": "Coworker conduct concern raised by Ardisj Parke."}
SAVE_ROSTER = ("import openpyxl\nwb=openpyxl.load_workbook('/workdir/employee_roster.xlsx')\n"
               "wb.active['K2']='Separated'\nwb.save('/workdir/employee_roster.xlsx')")


class T(TaskCase):
    TASK = "hr_crestwood_university_2071c562"

    # initial state ------------------------------------------------------------------------------
    def test_initial_obligations(self):
        got = self.done_all()
        rules = {r for r, _ in got}
        self.assertEqual(rules, {"comms.messages_sent", "offboard.jira", "mail.housekeeping"})
        self.assertEqual(sum(r == "comms.messages_sent" for r, _ in got), 5)

    # SEPARATION post ------------------------------------------------------------------------------
    def test_separation_post_ok(self):
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C_OFFBOARDING", "text": SEP}), set())
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C_OFFBOARDING",
                                                           "text": SEP.replace(TICKET, "OFFBOARD-1")}), set())

    def test_separation_post_wrong(self):
        self.assertIn("comms.messages", self.pre("slack__post_message", {"channel_id": "C_ESCALATIONS", "text": SEP}))
        self.assertIn("comms.messages", self.pre("slack__post_message", {
            "channel_id": "C_OFFBOARDING", "text": SEP.replace("Voluntary Resignation", "Resignation")}))

    def test_offboarding_complete_forbidden(self):
        self.assertIn("comms.messages", self.pre("slack__post_message", {
            "channel_id": "C_OFFBOARDING", "text": "OFFBOARDING COMPLETE: Gerta Teodoor, 10741, Separation Type: "
                                                   "Voluntary Resignation, Last Day: 04/19/2026"}))

    # Template 13 / 14 -----------------------------------------------------------------------------
    def test_t13_ok(self):
        self.assertEqual(self.pre("google_mail__send_email", T13), set())
        alt = dict(T13, subject="Template 13 – Access Revocation Request — Teodoor, 10741")
        self.assertEqual(self.pre("google_mail__send_email", alt), set())

    def test_t13_wrong(self):
        bad = dict(T13, body=T13_BODY.replace("End of business on last day", "Immediately"))
        self.assertIn("comms.messages", self.pre("google_mail__send_email", bad))
        self.assertIn("comms.messages", self.pre("google_mail__send_email", dict(T13, subject="Access revocation")))

    def test_t14_ok(self):
        self.assertEqual(self.pre("google_mail__send_email", T14), set())

    def test_t14_wrong_recipient(self):
        self.assertIn("comms.messages", self.pre("google_mail__send_email", dict(T14, to=["r.clint@crestwood.edu"])))
        self.assertIn("comms.messages", self.pre("google_mail__send_email",
                                                 dict(T14, body=T14_BODY.replace("04/19/2026", "[Last Day]"))))

    def test_excluded_final_pay_and_cobra(self):
        self.assertIn("comms.messages", self.pre("google_mail__send_email", {
            "to": ["c.briggs@crestwood.edu"], "subject": "Template 12 — Teodoor, 10741",
            "body": "Hi Calvin, Please process final pay for Gerta Teodoor."}))
        self.assertIn("comms.messages", self.pre("google_mail__send_email", {
            "to": ["g.teodoor@crestwood.edu"], "subject": "Template 11 — Teodoor, 10741",
            "body": "Hi Gerta, COBRA notice for Gerta Teodoor."}))

    # Parke routing / legal hold ------------------------------------------------------------------------
    def test_parke_forwards_ok(self):
        self.assertEqual(self.pre("google_mail__forward_email", FWD_PAY), set())
        self.assertEqual(self.pre("google_mail__forward_email", FWD_ER), set())
        both = dict(FWD_PAY, to=["c.briggs@crestwood.edu", "m.voss@crestwood.edu"])
        self.assertEqual(self.pre("google_mail__forward_email", both), set())

    def test_parke_forward_modified_subject(self):
        self.assertIn("comms.messages", self.pre("google_mail__forward_email",
                                                 dict(FWD_PAY, subject="Payroll issue — Parke, 10980")))

    def test_parke_no_contact(self):
        self.assertIn("legal.parke_no_contact", self.pre("google_mail__reply_to_email", {
            "email_id": "4", "body": "Hi Ardisj, your message has been forwarded."}))
        self.assertIn("legal.parke_no_contact", self.pre("google_mail__send_email", {
            "to": ["a.parke@crestwood.edu"], "subject": "Template 2 — Parke, 10980", "body": "Hi Ardisj"}))
        self.assertNotIn("legal.parke_no_contact", self.pre("google_mail__forward_email", FWD_ER))

    # Slack DM ----------------------------------------------------------------------------------------
    def test_no_dm(self):
        self.assertIn("slack.no_dm", self.pre("slack__send_dm", {"user_id": "U_PARK", "text": "Teodoor leaving"}))
        self.assertNotIn("slack.no_dm", self.pre("slack__post_message", {"channel_id": "C_OFFBOARDING", "text": SEP}))

    # workbooks ----------------------------------------------------------------------------------------
    def test_no_workbook_writes(self):
        self.assertIn("files.no_workbook_writes", self.pre("syntara__executePython", {"code": SAVE_ROSTER}))
        read = "import openpyxl\nwb=openpyxl.load_workbook('/workdir/employee_roster.xlsx')\nprint(wb.active['A2'].value)"
        self.assertNotIn("files.no_workbook_writes", self.pre("syntara__executePython", {"code": read}))

    def test_files_unchanged(self):
        self.assertNotIn("files.unchanged", self.done())
        self.edit("employee_roster.xlsx", "ws.cell(row=2, column=11, value='Separated')")
        self.assertIn("files.unchanged", self.done())

    # Jira ---------------------------------------------------------------------------------------------
    def test_jira_create_ok(self):
        self.assertEqual(self.pre("jira__create_issue", JIRA), set())

    def test_jira_create_wrong(self):
        self.assertIn("offboard.jira_pre", self.pre("jira__create_issue", dict(JIRA, summary="OFFBOARD-Teodoor-04082026")))
        self.assertIn("offboard.jira_pre", self.pre("jira__create_issue", dict(JIRA, assignee="U_HUANG")))
        self.did("jira__create_issue", JIRA, '{"key": "OFFBOARD-1"}')
        self.assertIn("offboard.jira_pre", self.pre("jira__create_issue", JIRA))

    def test_jira_cobra_and_close_blocked(self):
        self.did("jira__create_issue", JIRA, '{"key": "OFFBOARD-1"}')
        self.assertIn("offboard.jira_pre", self.pre("jira__add_comment", {
            "issue_key": "OFFBOARD-1", "comment": "No COBRA required – employee not enrolled in health benefits."}))
        self.assertIn("offboard.jira_pre", self.pre("jira__transition_issue", {"issue_key": "OFFBOARD-1",
                                                                               "transition_id": "2"}))
        self.assertNotIn("offboard.jira_pre", self.pre("jira__add_comment", {
            "issue_key": "OFFBOARD-1", "comment": "Access revocation requested from IT (Template 13)."}))

    def test_jira_completion(self):
        self.assertIn("offboard.jira", self.done())
        self.did("jira__create_issue", dict(JIRA, assignee=""), '{"key": "OFFBOARD-1"}')
        self.assertIn("Assign", self.done().get("offboard.jira", ""))
        self.did("jira__update_issue", {"issue_key": "OFFBOARD-1", "assignee": "U_OKONKWO"})
        self.assertNotIn("offboard.jira", self.done())

    # calendar -----------------------------------------------------------------------------------------
    def test_exit_calendar(self):
        self.assertIn("offboard.exit_calendar", self.pre("google_calendar__create_event", {
            "summary": "Exit Interview – Gerta Teodoor", "start": "2026-04-15T10:00:00-06:00",
            "end": "2026-04-15T10:30:00-06:00"}))
        self.assertNotIn("offboard.exit_calendar", self.pre("google_calendar__create_event", {
            "summary": "Team sync", "start": "2026-04-15T10:00:00-06:00", "end": "2026-04-15T10:30:00-06:00"}))

    # mail housekeeping --------------------------------------------------------------------------------
    def test_mail_pre(self):
        self.assertIn("mail.housekeeping_pre", self.pre("google_mail__move_emails",
                                                        {"email_ids": ["5"], "target_folder": "General"}))
        self.assertNotIn("mail.housekeeping_pre", self.pre("google_mail__move_emails",
                                                           {"email_ids": ["5"], "target_folder": "Offboarding"}))
        self.assertIn("mail.housekeeping_pre", self.pre("google_mail__mark_emails",
                                                        {"email_ids": ["5"], "is_important": True}))
        self.assertNotIn("mail.housekeeping_pre", self.pre("google_mail__mark_emails",
                                                           {"email_ids": ["5"], "is_read": True}))

    def test_mail_completion(self):
        self.did("google_mail__read_email", {"email_id": "5"}, '{"email": {"email_id": "5", "is_read": true}}')
        self.did("google_mail__mark_emails", {"email_ids": ["4"], "is_read": True})
        probs = [p for r, p in self.done_all() if r == "mail.housekeeping"]
        self.assertEqual(len(probs), 1)
        self.assertIn("Offboarding", probs[0])
        self.did("google_mail__move_emails", {"email_ids": ["5"], "target_folder": "Offboarding"})
        self.assertNotIn("mail.housekeeping", self.done())

    # placeholders -------------------------------------------------------------------------------------
    def test_placeholders(self):
        self.assertIn("comms.no_placeholders", self.pre("slack__post_message", {
            "channel_id": "C_OFFBOARDING", "text": "SEPARATION: [Employee Name], 10741"}))
        self.assertNotIn("comms.no_placeholders", self.pre("slack__post_message",
                                                           {"channel_id": "C_OFFBOARDING", "text": SEP}))

    # golden path --------------------------------------------------------------------------------------
    def test_golden_path(self):
        self.did("google_mail__read_email", {"email_id": "5"}, '{"email": {"email_id": "5", "is_read": true}}')
        self.did("google_mail__read_email", {"email_id": "4"}, '{"email": {"email_id": "4", "is_read": true}}')
        self.did("jira__create_issue", JIRA, '{"key": "OFFBOARD-1", "id": "10020"}')
        self.did("slack__post_message", {"channel_id": "C_OFFBOARDING", "text": SEP.replace(TICKET, "OFFBOARD-1")})
        self.did("google_mail__send_email", T13)
        self.did("google_mail__send_email", T14)
        self.did("google_mail__forward_email", FWD_PAY)
        self.did("google_mail__forward_email", FWD_ER)
        self.did("jira__add_comment", {"issue_key": "ER-1", "comment": "New email: pay discrepancy and coworker "
                                                                          "conduct; forwarded to C. Briggs and M. Voss."})
        self.did("google_mail__move_emails", {"email_ids": ["5"], "target_folder": "Offboarding"})
        self.assertEqual(self.done(), {})
