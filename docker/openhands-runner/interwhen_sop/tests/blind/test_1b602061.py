"""Blind unit tests for hr_crestwood_university_1b602061 (fixtures from the task environment seed only)."""

from __future__ import annotations

import unittest

from interwhen_sop.tests.base import TaskCase

SENT = '{"status": "sent", "email": {"email_id": "99", "folder": "Sent"}}'
OK = '{"ok": true}'

T7_BODY = ("Hi Patricia,\n\nThis is to inform you that the I-9 Employment Eligibility Verification for Tomás Salazar "
           "(CU-1026) has not been completed by the federal deadline. Tomás Salazar may not continue working until "
           "this requirement is fulfilled. Please do not assign work to this employee until further notice from the "
           "HR Office.\n\nThis matter has been escalated to the HR Director.\n\nBest regards,\nCrestwood University – "
           "Office of Human Resources\nhr@crestwood.edu")
I9_POST = "I-9 OVERDUE: Tomás Salazar, CU-1026, Start Date: 04/02/2026, Deadline: 04/08/2026"
PHAM_BODY = ("Hi Diane,\n\nSince your message concerns multiple topics, I am addressing them here together.\n\n"
             "We have reviewed your request for leave under the Family and Medical Leave Act (FMLA). Based on our "
             "records, you meet the eligibility requirements (employed for 178 months; 2,080 hours worked in the "
             "preceding 12 months).\n\nTo proceed, please complete and return the attached Medical Certification Form "
             "within 15 calendar days of your request (due by 04/23/2026). Failure to return the certification by "
             "this date may result in denial of your FMLA leave request.\n\nIf you have questions, please contact "
             "Patricia Huang at p.huang@crestwood.edu.\n\nConcerning your next matter:\nThank you for submitting your "
             "request for a workplace accommodation. Your request has been received and forwarded to our Benefits & "
             "Leave Manager, who will coordinate the interactive process with you.\n\nYou can expect to be contacted "
             "within 5 business days to discuss your request and next steps.\n\nBest regards,\nCrestwood University – "
             "Office of Human Resources\nhr@crestwood.edu")
PARK_BODY = ("Hi Jenna,\n\nSince your message concerns multiple topics, I am addressing them here together.\n\n"
             "Thank you for contacting us. Your message has been forwarded to our Employee Relations Specialist, who "
             "will follow up with you directly. Please allow 2 business days for initial contact.\n\nConcerning your "
             "next matter:\nThank you for reaching out. For all payroll and compensation questions, please contact our "
             "Payroll Liaison, Calvin Briggs, directly at c.briggs@crestwood.edu. Your message has been forwarded to "
             "him.\n\nBest regards,\nCrestwood University – Office of Human Resources\nhr@crestwood.edu")
CERT = ["/workdir/fmla_medical_certification.pdf"]


def t7(**kw):
    a = {"to": "p.huang@crestwood.edu", "cc": "n.ashford@crestwood.edu, j.whitfield@crestwood.edu",
         "subject": "Template 7 — Salazar, CU-1026", "body": T7_BODY}
    a.update(kw)
    return "google_mail__send_email", a


def pham_reply(**kw):
    a = {"email_id": "34", "body": PHAM_BODY, "attachments": CERT}
    a.update(kw)
    return "google_mail__reply_email", a


def park_reply(**kw):
    a = {"email_id": "35", "body": PARK_BODY}
    a.update(kw)
    return "google_mail__reply_email", a


def fwd(eid, to, **kw):
    return "google_mail__forward_email", {"email_id": eid, "to": to, **kw}


def post(ch, text):
    return "slack__post_message", {"channel_id": ch, "text": text}


def jira(summary, desc="Employee Name: Diane Pham\nEmployee ID: CU-1020\nAssignee: Patricia Huang"):
    return "jira__create_issue", {"project_key": "HR", "summary": summary, "issue_type": "Task", "description": desc}


def cal(summary="FMLA Certification Due – Diane Pham", date="2026-04-23"):
    return "google_calendar__create_event", {"summary": summary, "start": {"date": date}, "end": {"date": "2026-04-24"}}


def py(code):
    return "syntara__executePython", {"code": code}


GOLDEN = [
    (t7(), SENT),
    (post("CESCALATIONS", I9_POST), OK),
    (fwd("34", "p.huang@crestwood.edu"), SENT),
    (pham_reply(), SENT),
    (jira("LEAVE-Pham-04092026"), '{"id":"10011","key":"HR-9"}'),
    (jira("LEAVE-Pham-ADA-04092026"), '{"id":"10012","key":"HR-10"}'),
    (post("CLEAVE", "FMLA REQUEST: Diane Pham, CU-1020, Eligible: YES, Certification Due: 04/23/2026, Jira: HR-9"), OK),
    (cal(), '{"status":"success"}'),
    (fwd("35", "m.voss@crestwood.edu"), SENT),
    (fwd("35", "c.briggs@crestwood.edu"), SENT),
    (park_reply(), SENT),
    (jira("ER-Park-04092026", "Employee Name: Jenna Park\nEmployee ID: CU-1006\nAssignee: Marta Voss\nPriority: P2"),
     '{"id":"10013","key":"HR-11"}'),
    (jira("BENEFITS-Park-04092026", "Employee Name: Jenna Park\nEmployee ID: CU-1006\nAssignee: Calvin Briggs"),
     '{"id":"10014","key":"HR-12"}'),
    (post("CESCALATIONS", "ESCALATED: Jenna Park, CU-1006, Getting Fed Up – Jira: HR-11"), OK),
    (post("CGENERAL", "[OUT OF SCOPE] – Re: HR office light bulb out – Main Campus rm 214"), OK),
    (("jira__add_comment", {"issue_key": "HR-6", "comment": "04/13/2026 11:46am [11.2] — TEMPLATE SENT — Template 7 to "
                                                            "p.huang@crestwood.edu"}), '{"id":"1"}'),
    (("google_mail__mark_emails", {"email_ids": ["34", "35", "36"], "is_read": True}), '{"status":"all_succeeded"}'),
    (("google_mail__mark_emails", {"email_ids": ["34", "35"], "is_important": True}), '{"status":"all_succeeded"}'),
    (("google_mail__move_emails", {"email_ids": ["36"], "target_folder": "General"}), '{"status":"all_succeeded"}'),
]


class Crestwood1b602061(TaskCase):
    TASK = "hr_crestwood_university_1b602061"

    def run_golden(self, skip=()):
        for (tool, args), res in GOLDEN:
            if (tool, args.get("summary") or args.get("text") or args.get("to")) in skip:
                continue
            self.assertEqual(self.pre(tool, args), set(), f"false block: {tool} {args}")
            self.did(tool, args, res)

    # ---- initial state / golden path
    def test_initial_obligations(self):
        rules = {r for r, _ in self.done_all()}
        self.assertEqual(rules, {"comms.messages_sent", "jira.tickets", "calendar.fmla_reminder", "mail.housekeeping",
                                 "escalation.park"})
        self.assertEqual(sum(r == "comms.messages_sent" for r, _ in self.done_all()), 8)

    def test_golden_path(self):
        self.run_golden()
        self.edit("onboarding_checklist.xlsx",
                  "for r in ws.iter_rows(min_row=2):\n    if r[0].value=='CU-1021': r[col['NOTES']-1].value='x'")
        self.assertEqual(self.done(), {})

    # ---- comms specs
    def test_t7(self):
        self.assertEqual(self.pre(*t7()), set())
        self.assertIn("comms.messages", self.pre(*t7(to="k.cho@crestwood.edu")))
        self.assertIn("comms.messages", self.pre(*t7(cc="n.ashford@crestwood.edu")))
        self.assertIn("comms.messages", self.pre(*t7(subject="I-9 overdue")))
        self.assertIn("comms.messages", self.pre(*t7(body=T7_BODY.replace("escalated to the HR Director", "noted"))))
        self.did(*t7(), SENT)
        self.assertIn("comms.messages", self.pre(*t7()))  # already sent

    def test_i9_post(self):
        self.assertEqual(self.pre(*post("CESCALATIONS", I9_POST)), set())
        self.assertIn("comms.messages", self.pre(*post("CESCALATIONS", I9_POST.replace("04/08", "04/06"))))
        self.assertIn("comms.messages", self.pre(*post("CONBOARDING", I9_POST)))

    def test_pham_reply(self):
        self.assertEqual(self.pre(*pham_reply()), set())
        self.assertIn("comms.messages", self.pre(*pham_reply(attachments=[])))
        self.assertIn("comms.messages", self.pre(*pham_reply(body=PHAM_BODY.replace("178 months", "177 months"))))
        self.assertIn("comms.messages", self.pre(*pham_reply(body=PHAM_BODY.split("Concerning")[0])))
        self.assertIn("comms.messages", self.pre(*pham_reply(body=PHAM_BODY.replace("04/23/2026", "04/24/2026"))))

    def test_park_reply(self):
        self.assertEqual(self.pre(*park_reply()), set())
        self.assertIn("comms.messages", self.pre(*park_reply(body=PARK_BODY + "\nWe sincerely apologize.")))
        self.assertIn("comms.messages", self.pre(*park_reply(body=PARK_BODY.split("Concerning")[0])))

    def test_forwards(self):
        self.assertEqual(self.pre(*fwd("35", "m.voss@crestwood.edu")), set())
        self.assertIn("comms.forward_as_is", self.pre(*fwd("35", "m.voss@crestwood.edu", body="FYI please handle")))
        self.did(*fwd("35", "m.voss@crestwood.edu"), SENT)
        self.assertIn("comms.messages", self.pre(*fwd("35", "m.voss@crestwood.edu")))
        self.assertNotIn("forward of Jenna Park's email (\"Getting Fed Up\") to m.voss@crestwood.edu",
                         " ".join(p for _, p in self.done_all()))

    def test_pham_post_and_privacy(self):
        ok = "FMLA REQUEST: Diane Pham, CU-1020, Eligible: YES, Certification Due: 04/23/2026, Jira: HR-9"
        self.assertEqual(self.pre(*post("CLEAVE", ok)), set())
        self.assertIn("comms.ada_privacy", self.pre(*post("CLEAVE", ok + " (also needs a wheelchair ramp)")))
        self.assertIn("comms.ada_privacy", self.pre(*post("CGENERAL", "Diane Pham ADA accommodation request received")))
        self.assertIn("comms.ada_privacy", self.pre(*fwd("34", "m.voss@crestwood.edu")))
        self.assertEqual(self.pre(*fwd("34", "p.huang@crestwood.edu")), set())

    def test_forbidden_repeats(self):
        cases = [
            ("google_mail__reply_email", {"email_id": "36", "body": "Tuesday 10am works."}),
            ("google_mail__send_email", {"to": "p.huang@crestwood.edu", "subject": "Template 6 — Salazar, CU-1026",
                                         "body": "This is an urgent reminder regarding the I-9 for Tomás Salazar"}),
            ("google_mail__send_email", {"to": "m.cross@crestwood.edu", "subject": "Template 18 — Cross, CU-1023",
                                         "body": "Your FMLA Medical Certification Form was due on 04/06/2026"}),
            ("google_mail__send_email", {"to": "p.huang@crestwood.edu", "subject": "FMLA Deadline Passed - CU-1023",
                                         "body": "Hi Patricia, Meghan Cross's form is overdue."}),
            post("CLEAVE", "FMLA CERTIFICATION OVERDUE: Meghan Cross, CU-1023, Due: 04/06/2026, 7 days overdue"),
            ("google_mail__send_email", {"to": "w.trent@crestwood.edu", "subject": "Template 10 — Trent, CU-1022",
                                         "body": "you have been automatically enrolled"}),
            ("google_mail__send_email", {"to": "p.nair@crestwood.edu", "subject": "Template 8 — Nair, CU-1025",
                                         "body": "This is a reminder that your benefits enrollment deadline is 05/01/2026"}),
            post("CONBOARDING", "ONBOARDING COMPLETE: Priya Nair, CU-1025, 04/13/2026"),
            post("CONBOARDING", "NEW HIRE: Tomás Salazar, Program Coordinator, Student Affairs, Downtown"),
        ]
        for tool, args in cases:
            self.assertIn("comms.messages", self.pre(tool, args), args)

    def test_placeholders(self):
        self.assertEqual(self.pre(*post("CGENERAL", "[OUT OF SCOPE] – Re: HR office light bulb out – Main Campus rm 214")),
                         set())
        self.assertIn("comms.no_placeholders", self.pre("google_mail__send_email", {
            "to": "r.mendez@crestwood.edu", "subject": "Template 8 — Mendez, CU-1021", "body": "Hi [First Name],"}))

    def test_dm_addresses_dates(self):
        self.assertIn("comms.no_dm", self.pre("slack__send_dm", {"user_id": "UHUANG", "text": "Pham FMLA question"}))
        bad = {"to": "tomas.salazar@crestwood.edu", "subject": "x — Salazar, CU-1026", "body": "hello"}
        self.assertIn("comms.addresses", self.pre("google_mail__send_email", bad))
        good = dict(bad, to="t.salazar@crestwood.edu")
        self.assertNotIn("comms.addresses", self.pre("google_mail__send_email", good))
        self.assertIn("comms.date_format", self.pre(*post("CLEAVE", "Reminder set for 2026-04-23")))
        self.assertNotIn("comms.date_format", self.pre(*post("CLEAVE", "Reminder set for 04/23/2026")))

    def test_subjects(self):
        new = {"to": "d.pham@crestwood.edu", "subject": "Workplace Accommodation Request Received", "body": PHAM_BODY,
               "attachments": CERT}
        self.assertIn("comms.subject", self.pre("google_mail__send_email", new))
        self.assertNotIn("comms.subject", self.pre("google_mail__send_email",
                                                   dict(new, subject="Template 15 — Pham, CU-1020")))
        self.assertIn("comms.subject", self.pre(*park_reply(subject="Your complaint")))
        self.assertNotIn("comms.subject", self.pre(*park_reply(subject="Re: Getting Fed Up")))

    # ---- jira
    def test_jira_duplicates(self):
        self.assertIn("jira.no_duplicate", self.pre(*jira("ONBOARD-Salazar-04022026", "")))
        self.assertIn("jira.no_duplicate", self.pre(*jira("LEAVE-Cross-03232026", "")))
        self.assertIn("jira.no_duplicate", self.pre(*jira("Facilities light bulb room 214", "")))
        self.assertEqual(self.pre(*jira("LEAVE-Pham-04092026")), set())
        self.did(*jira("LEAVE-Pham-04092026"), "")  # no key returned: not counted as created
        self.assertEqual(self.pre(*jira("LEAVE-Pham-04092026")), set())
        self.did(*jira("LEAVE-Pham-04092026"), '{"id":"1","key":"HR-9"}')
        self.assertIn("jira.no_duplicate", self.pre(*jira("LEAVE-Pham-04092026")))

    def test_jira_description_and_comment(self):
        self.assertIn("jira.description", self.pre(*jira("LEAVE-Pham-04092026", "FMLA request for surgery in June")))
        self.assertEqual(self.pre(*jira("LEAVE-Pham-04092026", "Employee Name: Diane Pham\nPriority: P2 – High\n"
                                                               "Deadline: 04/23/2026\nStatus: Open")), set())
        self.assertIn("jira.comment", self.pre("jira__add_comment", {"issue_key": "HR-6", "comment": "Sent T7 today"}))
        self.assertEqual(self.pre("jira__add_comment", {"issue_key": "HR-6", "comment": "[04/13/2026 11:46am] [11.2] — "
                                                        "SLACK POSTED — hr-escalations"}), set())

    def test_jira_tickets_completion(self):
        self.did(*jira("LEAVE-Pham-04092026"), '{"error": "User Patricia Huang not found"}')
        self.assertIn("LEAVE-Pham-04092026", " ".join(p for r, p in self.done_all() if r == "jira.tickets"))
        self.did(*jira("LEAVE-Pham-04092026"), '{"id":"1","key":"HR-9"}')
        self.assertNotIn("\"LEAVE-Pham-04092026\"", " ".join(p for r, p in self.done_all() if r == "jira.tickets"))

    # ---- calendar / mail housekeeping / escalation
    def test_calendar(self):
        self.assertIn("calendar.fmla_due", self.pre(*cal(date="2026-04-24")))
        self.assertEqual(self.pre(*cal()), set())
        self.did(*cal(summary="Create FMLA certification due calendar reminder"), '{"status":"success"}')
        self.assertIn("calendar.fmla_reminder", self.done())
        self.did(*cal(), '{"status":"success"}')
        self.assertNotIn("calendar.fmla_reminder", self.done())

    def test_folders(self):
        mv = lambda ids, f: ("google_mail__move_emails", {"email_ids": ids, "target_folder": f})
        self.assertIn("mail.folders", self.pre(*mv(["34"], "Leave")))
        self.assertIn("mail.folders", self.pre(*mv(["36"], "Misc")))
        self.assertIn("mail.folders", self.pre(*mv(["35"], "Performance")))
        self.assertEqual(self.pre(*mv(["35"], "General")), set())
        self.assertEqual(self.pre(*mv(["36"], "General")), set())
        self.assertIn("mail.folders", self.pre("google_mail__create_folder", {"name": "ADA"}))

    def test_housekeeping(self):
        self.did("google_mail__mark_emails", {"email_ids": ["34", "35", "36"], "is_read": True})
        self.assertIn("mail.housekeeping", self.done())
        self.did("google_mail__mark_emails", {"email_ids": ["34"], "is_important": True})
        self.assertNotIn("mail.housekeeping", self.done())

    def test_escalation(self):
        self.assertIn("escalation.park", self.done())
        self.did(*fwd("35", "n.ashford@crestwood.edu"), SENT)
        self.assertNotIn("escalation.park", self.done())

    # ---- workbooks
    def test_no_unrequested_writes(self):
        code = "import openpyxl\nwb=openpyxl.load_workbook('/workdir/leave_tracker.xlsx')\nwb.save('/workdir/leave_tracker.xlsx')"
        self.assertIn("files.no_unrequested_writes", self.pre(*py(code)))
        ok = code.replace("leave_tracker", "onboarding_checklist")
        self.assertNotIn("files.no_unrequested_writes", self.pre(*py(ok)))

    def test_files_unchanged(self):
        self.assertNotIn("files.unchanged", self.done())
        self.edit("onboarding_checklist.xlsx",
                  "for r in ws.iter_rows(min_row=2):\n    if r[0].value=='CU-1021': r[col['NOTES']-1].value='T8 sent 04/13/2026'")
        self.assertNotIn("files.unchanged", self.done())
        self.edit("onboarding_checklist.xlsx",
                  "for r in ws.iter_rows(min_row=2):\n    if r[0].value=='CU-1026': r[col['I-9 Completed']-1].value='04/13/2026'")
        self.assertIn("files.unchanged", self.done())

    def test_files_unchanged_other_book(self):
        self.edit("leave_tracker.xlsx", "ws.cell(row=4, column=5).value='FMLA'")
        self.assertIn("files.unchanged", self.done())


if __name__ == "__main__":
    unittest.main()
