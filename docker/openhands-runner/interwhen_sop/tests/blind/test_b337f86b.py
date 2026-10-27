"""Blind verifier tests for hr_ridgeline_gear_co_b337f86b (Claire Ndubisi FMLA intake, LC-2026-0050).

INTERWHEN_XLSX_PYTHON=/home/t-bhatvishak/miniconda3/bin/python3 \
    python3 -m unittest interwhen_sop.tests.blind.test_b337f86b -v
"""

from __future__ import annotations

import unittest

from interwhen_sop.tests.base import TaskCase

CW = "claire.ndubisi@ridgelinegear.com"
GREG = "greg.ostrowski@ridgelinegear.com"
ATT = ["/workdir/WH-381-Claire.pdf", "/workdir/WH-380-F.pdf"]
T2 = """Hi Claire,

Thank you for submitting your FMLA leave request. I have reviewed your eligibility and confirmed that you ARE eligible for FMLA leave under all three federal eligibility criteria as of your requested leave start date of 04/14/2026.

Attached is your official Notice of Eligibility and Rights & Responsibilities (DOL Form WH-381), which explains your rights and obligations under FMLA. Please read it carefully.

To complete your FMLA designation, I also need a medical certification from your healthcare provider. Please find attached the appropriate certification form (WH-380-F for a family member's condition). The completed certification is due by 04/24/2026.

If the certification is not returned by the due date, your leave may be denied. If you anticipate any difficulty obtaining the certification by the deadline, please reply to this email so we can discuss.

Case ID: LC-2026-0050

Best regards,
Ridgeline Gear Co. \u2014 Leave Coordinator
leaves@ridgelinegear.com"""
T11 = """Hi Greg,

I am writing to notify you that one of your team members will be on approved leave. Please use this notification to plan workload coverage.

Employee: Claire Ndubisi
Leave type (general category only): FMLA leave
Start date: 04/14/2026
Expected end date: 05/26/2026
Leave format: Continuous

For all questions about this leave, please contact me directly at leaves@ridgelinegear.com. Please do NOT contact the employee about work matters during their leave except in genuine operational emergency.

I will be in touch closer to the return date to coordinate.

CONFIDENTIALITY REMINDER: medical information about your team members is confidential under federal and Colorado law. Please do not share this notification with other team members or discuss the reason for the leave with anyone.

Best regards,
Ridgeline Gear Co. \u2014 Leave Coordinator
leaves@ridgelinegear.com"""
INTAKE = ("FMLA INTAKE: LC-2026-0050, Claire Ndubisi, Eligible, (b) family member's serious health condition, "
          "04/14/2026, P2 <@U004> <@U005>")
SEND = "google_mail__send_email"
POST = "slack__post_message"


def t2(**kw):
    return {"to": CW, "subject": "FMLA Eligibility Notice - LC-2026-0050", "body": T2, "attachments": ATT, **kw}


def t11(**kw):
    return {"to": GREG, "subject": "Leave Notification - Claire Ndubisi", "body": T11, **kw}


class Base(TaskCase):
    TASK = "hr_ridgeline_gear_co_b337f86b"

    def golden(self, move_manager=True):
        self.did(SEND, t2(), '{"status": "sent", "email": {"email_id": "27", "folder": "Sent"}}')
        self.did(SEND, t11(), '{"status": "sent", "email": {"email_id": "28", "folder": "Sent"}}')
        self.did(POST, {"channel_id": "C001", "text": INTAKE})
        self.did("google_mail__mark_emails", {"email_ids": ["1"], "is_read": True, "is_important": False})
        self.did("google_mail__move_emails", {"email_ids": ["1", "28"] if move_manager else ["1"],
                                              "target_folder": "FMLA Cases"})


class TestGoldenPath(Base):
    def test_initial_obligations(self):
        got = self.done_all()
        rules = [r for r, _ in got]
        self.assertEqual(rules.count("comms.messages_sent"), 3)
        self.assertEqual(rules.count("mail.housekeeping"), 3)
        self.assertEqual(set(rules), {"comms.messages_sent", "mail.housekeeping"})

    def test_golden_path_complete(self):
        self.golden()
        self.assertEqual(self.done(), {})

    def test_baseline_style_posts_not_blocked(self):
        self.assertEqual(self.pre(POST, {"channel_id": "C001", "text":
            "<@U004> <@U005> FMLA INTAKE: LC-2026-0050, Claire Ndubisi, Eligible, (b) Family member's serious health "
            "condition (FMLA + FAMLI), 04/14/2026, P2\nEligibility Notice due 04/16/2026. Cert due 04/24/2026."}), set())
        self.assertEqual(self.pre(POST, {"channel_id": "C004", "text":
            "LEAVE PAYROLL NOTIFICATION: LC-2026-0050, Claire Ndubisi, Leave start, 04/14/2026, Continuous, "
            "FMLA + FAMLI concurrent"}), set())

    def test_missing_obligations_listed(self):
        self.did(SEND, t2(), '{"status": "sent", "email": {"email_id": "27", "folder": "Sent"}}')
        self.did(POST, {"channel_id": "C001", "text": INTAKE})
        msgs = [p for r, p in self.done_all() if r == "comms.messages_sent"]
        self.assertEqual(len(msgs), 1)
        self.assertIn("Template 11", msgs[0])

    def test_golden_calls_not_blocked(self):
        self.assertEqual(self.pre(SEND, t2()), set())
        self.assertEqual(self.pre(SEND, t11()), set())
        self.assertEqual(self.pre(POST, {"channel_id": "C001", "text": INTAKE}), set())
        self.assertEqual(self.pre("google_mail__move_emails", {"email_ids": ["1"], "target_folder": "FMLA Cases"}),
                         set())


class TestComms(Base):
    def test_t2_ok_with_hr_cc(self):
        self.assertEqual(self.pre(SEND, t2(cc="renata.okafor@ridgelinegear.com")), set())

    def test_t2_reply_tool_counts(self):
        self.did("google_mail__reply_to_email", {"email_id": "1", "body": T2, "attachments": ATT})
        self.assertNotIn("Template 2", " ".join(p for r, p in self.done_all()))

    def test_t2_missing_due_date_and_wrong_form(self):
        bad = T2.replace("04/24/2026", "04/23/2026").replace("WH-380-F", "WH-380-E")
        self.assertIn("comms.messages", self.pre(SEND, t2(body=bad)))

    def test_t2_without_attachments_blocked(self):
        self.assertIn("comms.messages", self.pre(SEND, t2(attachments=[])))

    def test_t2_sent_twice_blocked(self):
        self.did(SEND, t2())
        self.assertIn("comms.messages", self.pre(SEND, t2()))

    def test_t11_medical_reason_blocked(self):
        self.assertIn("comms.messages", self.pre(SEND, t11(body=T11 + "\nShe is caring for her mother.")))

    def test_intake_wrong_priority_blocked(self):
        self.assertIn("comms.messages", self.pre(POST, {"channel_id": "C001", "text": INTAKE.replace("P2", "P3")}))

    def test_intake_wrong_channel_blocked(self):
        self.assertIn("comms.messages", self.pre(POST, {"channel_id": "C002", "text": INTAKE}))

    def test_forbidden_reply_to_dana(self):
        self.assertIn("comms.messages", self.pre(SEND, {"to": "dana.wilson@ridgelinegear.com", "subject": "Re: denial",
                                                        "body": "Hi Dana, we will review."}))

    def test_forbidden_unknown_sender(self):
        self.assertIn("comms.messages", self.pre(SEND, {"to": "roberto.m.1987@gmail.com", "subject": "Re", "body": "Hi"}))

    def test_forbidden_pattern_and_ada_manager(self):
        self.assertIn("comms.messages", self.pre(SEND, {"to": "phil.nguyen@ridgelinegear.com", "subject": "Sam",
                                                        "body": "About Sam Baker's absences"}))
        self.assertIn("comms.messages", self.pre(SEND, {"to": "sandra.bloom@ridgelinegear.com", "subject": "Jordan",
                                                        "body": "Jordan asked for an accommodation"}))

    def test_unrelated_email_allowed(self):
        self.assertEqual(self.pre(SEND, {"to": "renata.okafor@ridgelinegear.com", "subject": "Question",
                                         "body": "Quick question about the Q2 audit."}), set())

    def test_messages_sent_completion(self):
        self.did(SEND, t2())
        msgs = " ".join(p for r, p in self.done_all() if r == "comms.messages_sent")
        self.assertNotIn("Template 2", msgs)
        self.assertIn("Template 11", msgs)
        self.assertIn("FMLA INTAKE", msgs)

    def test_placeholders(self):
        self.assertIn("comms.no_placeholders",
                      self.pre(SEND, t2(body=T2.replace("04/24/2026", "[Cert Due Date]"))))
        self.assertNotIn("comms.no_placeholders", self.pre(SEND, t2()))


class TestSlack(Base):
    def test_em_dash(self):
        self.assertIn("slack.no_em_dash", self.pre(POST, {"channel_id": "C001", "text": INTAKE + " \u2014 thanks"}))
        self.assertNotIn("slack.no_em_dash", self.pre(POST, {"channel_id": "C001", "text": INTAKE + " - thanks"}))

    def test_em_dash_any_channel(self):
        self.assertIn("slack.no_em_dash", self.pre(POST, {"channel_id": "C002", "text": "Note \u2014 audit"}))

    def test_tags(self):
        self.assertIn("slack.tag_generalists",
                      self.pre("slack__reply_to_thread", {"channel_id": "C001", "thread_ts": "1.0",
                                                          "text": "Update on LC-2026-0050: <@U004> only"}))
        self.assertNotIn("slack.tag_generalists",
                         self.pre(POST, {"channel_id": "C001", "text": "Update on LC-2026-0050 <@U004> <@U005>"}))
        self.assertNotIn("slack.tag_generalists", self.pre(POST, {"channel_id": "C002", "text": "LC-2026-0050 note"}))

    def test_medical(self):
        self.assertIn("slack.no_medical", self.pre(POST, {"channel_id": "C001",
                                                          "text": INTAKE + " Her mother is in hospital."}))
        self.assertIn("slack.no_medical", self.pre(POST, {"channel_id": "C004", "text":
            "LEAVE PAYROLL NOTIFICATION: LC-2026-0050, Claire Ndubisi, Leave Start, 04/14/2026, Continuous, "
            "(b) family member's serious health condition"}))
        self.assertNotIn("slack.no_medical", self.pre(POST, {"channel_id": "C004", "text":
            "LEAVE PAYROLL NOTIFICATION: LC-2026-0050, Claire Ndubisi, Leave Start, 04/14/2026, Continuous, "
            "FMLA + FAMLI concurrent"}))

    def test_dm(self):
        self.assertIn("slack.no_dm", self.pre("slack__send_dm", {"user_id": "U002", "text": "LC-2026-0050 is eligible"}))
        self.assertNotIn("slack.no_dm", self.pre("slack__send_dm", {"user_id": "U002", "text": "Lunch at noon?"}))

    def test_nonhr_tag(self):
        self.assertIn("slack.no_nonhr_tag", self.pre(POST, {"channel_id": "C001", "text": INTAKE + " <@U009>"}))
        self.assertNotIn("slack.no_nonhr_tag", self.pre(POST, {"channel_id": "C001", "text": INTAKE}))


class TestEmail(Base):
    def test_recipients(self):
        self.assertIn("email.recipients", self.pre(SEND, t2(cc=GREG)))
        self.assertIn("email.recipients", self.pre(SEND, t2(to=f"{CW}, claire.ndubisi.personal@gmail.com")))
        self.assertIn("email.recipients", self.pre(SEND, t11(cc="carlos.mendes@ridgelinegear.com")))
        self.assertNotIn("email.recipients", self.pre(SEND, t2(cc="renata.okafor@ridgelinegear.com")))
        self.assertNotIn("email.recipients", self.pre(SEND, t11()))
        self.assertNotIn("email.recipients", self.pre(SEND, t11(cc="hr-team@ridgelinegear.com")))

    def test_forward_claire_email_outside_hr(self):
        self.assertIn("email.recipients", self.pre("google_mail__forward_email",
                                                   {"email_id": "1", "to": "carlos.mendes@ridgelinegear.com",
                                                    "body": "FYI"}))
        self.assertNotIn("email.recipients", self.pre("google_mail__forward_email",
                                                      {"email_id": "1", "to": "renata.okafor@ridgelinegear.com",
                                                       "body": "FYI"}))

    def test_no_medical(self):
        self.assertIn("email.no_medical", self.pre(SEND, {"to": "renata.okafor@ridgelinegear.com", "subject": "Claire",
                                                          "body": "Claire's mother was admitted to the hospital."}))
        self.assertNotIn("email.no_medical", self.pre(SEND, t2()))

    def test_cert_form(self):
        self.assertIn("email.cert_form", self.pre(SEND, t2(attachments=["/workdir/WH-381-Claire.pdf",
                                                                       "/workdir/WH-380-E.pdf"])))
        self.assertNotIn("email.cert_form", self.pre(SEND, t2()))


class TestHousekeeping(Base):
    def test_pre_wrong_folder(self):
        self.assertIn("mail.housekeeping_pre",
                      self.pre("google_mail__move_emails", {"email_ids": ["1"], "target_folder": "FAMLI Cases"}))
        self.assertIn("mail.housekeeping_pre",
                      self.pre("google_mail__move_emails", {"email_ids": ["27"], "target_folder": "Claire Ndubisi"}))
        self.assertNotIn("mail.housekeeping_pre",
                         self.pre("google_mail__move_emails", {"email_ids": ["1"], "target_folder": "FMLA Cases"}))

    def test_pre_flag_and_delete(self):
        self.assertIn("mail.housekeeping_pre",
                      self.pre("google_mail__mark_emails", {"email_ids": ["1"], "is_important": True}))
        self.assertIn("mail.housekeeping_pre", self.pre("google_mail__delete_emails", {"email_ids": ["1"]}))
        self.assertIn("mail.housekeeping_pre",
                      self.pre("google_mail__mark_emails", {"email_ids": ["1"], "is_read": False}))
        self.assertNotIn("mail.housekeeping_pre",
                         self.pre("google_mail__mark_emails", {"email_ids": ["1"], "is_read": True,
                                                               "is_important": False}))

    def test_completion_read_moved_unflagged(self):
        self.did("google_mail__mark_emails", {"email_ids": ["1"], "is_read": True, "is_important": False})
        self.did("google_mail__move_emails", {"email_ids": ["1"], "target_folder": "FMLA Cases"})
        self.assertNotIn("mail.housekeeping", self.done())

    def test_completion_still_flagged(self):
        self.did("google_mail__mark_emails", {"email_ids": ["1"], "is_read": True})
        self.did("google_mail__move_emails", {"email_ids": ["1"], "target_folder": "FMLA Cases"})
        self.assertIn("flagged", self.done().get("mail.housekeeping", ""))

    def test_manager_notification_must_be_filed(self):
        self.golden(move_manager=False)
        self.assertIn("manager notification", self.done().get("mail.housekeeping", ""))


class TestFiles(Base):
    def test_blank_forms(self):
        self.assertIn("files.blank_forms", self.pre("syntara__writeFile", {"file_path": "/workdir/WH-380-F.pdf",
                                                                           "content": "x"}))
        self.assertIn("files.blank_forms", self.pre("syntara__executeBash", {"command": "rm /workdir/WH-381-Claire.pdf"}))
        self.assertNotIn("files.blank_forms", self.pre("syntara__executeBash", {
            "command": "mkdir -p /workdir/E-04471 && cp /workdir/WH-381-Claire.pdf "
                       "/workdir/E-04471/WH-381_LC-2026-0050_20260409.pdf"}))
        self.assertNotIn("files.blank_forms", self.pre("syntara__executeBash", {
            "command": "cp /workdir/WH-381-Claire.pdf /workdir/E-04471/WH-381-Claire.pdf"}))

    def test_hours_log(self):
        code = ("import openpyxl\nwb=openpyxl.load_workbook('/workdir/hours_worked_log.xlsx')\n"
                "wb.active['D8']=1300\nwb.save('/workdir/hours_worked_log.xlsx')")
        self.assertIn("files.hours_log", self.pre("syntara__executePython", {"code": code}))
        self.assertNotIn("files.hours_log", self.pre("syntara__executePython", {
            "code": "import openpyxl\nwb=openpyxl.load_workbook('/workdir/hours_worked_log.xlsx')\nprint(wb.active['D8'].value)"}))

    def test_leave_history_append_only(self):
        self.edit("leave_history.xlsx", "ws.cell(row=4, column=7).value = 999", sheet="Leave History (24 Months)")
        self.assertIn("files.leave_history", self.done())

    def test_leave_history_append_ok(self):
        self.edit("leave_history.xlsx", "ws.append(['LC-2026-0099','E-04471','Claire Ndubisi','FMLA','04/14/2026',"
                                        "'ONGOING',0,'x'])", sheet="Leave History (24 Months)")
        self.assertNotIn("files.leave_history", self.done())

    def test_absence_log(self):
        self.edit("leave_tracker.xlsx", "ws.cell(row=4, column=5).value = 4.0", sheet="Absence Log (Intermittent)")
        self.assertIn("files.absence_log", self.done())

    def test_famli_log(self):
        self.edit("famli_coordination_log.xlsx", "ws.cell(row=4, column=9).value = '04/09/2026'")
        self.assertIn("files.famli_log", self.done())

    def test_famli_log_new_row_ok(self):
        self.edit("famli_coordination_log.xlsx", "ws.append(['E-04471','Claire Ndubisi','Pending','04/14/2026'])")
        self.assertNotIn("files.famli_log", self.done())

    def test_tracker_other_cases(self):
        self.edit("leave_tracker.xlsx", "ws.cell(row=5, column=20).value = 'edited'", sheet="Active & Recent Cases")
        self.assertIn("files.tracker_other_cases", self.done())

    def test_tracker_claire_row_editable(self):
        self.edit("leave_tracker.xlsx", "assert ws.cell(row=12, column=1).value == 'LC-2026-0050'\n"
                                        "ws.cell(row=12, column=11).value = 'Requested'", sheet="Active & Recent Cases")
        self.assertNotIn("files.tracker_other_cases", self.done())

    def test_leave_history_claire_row_editable(self):
        self.edit("leave_history.xlsx", "assert ws.cell(row=14, column=1).value == 'LC-2026-0050'\n"
                                        "ws.cell(row=14, column=6).value = '05/26/2026'", sheet="Leave History (24 Months)")
        self.assertNotIn("files.leave_history", self.done())


if __name__ == "__main__":
    unittest.main()
