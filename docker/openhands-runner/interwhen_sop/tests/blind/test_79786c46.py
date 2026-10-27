"""Blind verifier tests for hr_crestwood_university_79786c46 (fixtures from the task seed only)."""

from __future__ import annotations

import unittest

from interwhen_sop.tests.base import TaskCase

TASK = "hr_crestwood_university_79786c46"
SEND = "google_mail__send_email"
POST = "slack__post_message"
JIRA = "jira__create_issue"
CAL = "google_calendar__create_event"

HIRES = [
    ("E-1015", "Daniel", "Yoon", "danielyoon.work@gmail.com", "Marketing Coordinator", "Marketing", "West",
     "04/28/2026", "2026-04-28", "Exempt", "Sandra Bloom", "s.bloom@crestwood.edu"),
    ("E-1016", "Priya", "Kapoor", "priya.kapoor@outlook.com", "Finance Analyst", "Finance", "Main",
     "05/05/2026", "2026-05-05", "Exempt", "Robert Chen", "r.chen@crestwood.edu"),
    ("E-1017", "Marcus", "Webb", "marcuswebb84@gmail.com", "IT Support Specialist", "Information Technology", "Main",
     "04/28/2026", "2026-04-28", "Non-Exempt", "Lisa Nguyen", "l.nguyen@crestwood.edu"),
]
SIGN = "Best regards,\nCrestwood University – Office of Human Resources\nhr@crestwood.edu"


def welcome(h, subject=None, attach=("/workdir/i9_form.pdf",), start=None):
    eid, first, last, personal, pos, dept, campus, sd, iso, cls, sup, sup_email = h
    body = (f"Hi {first},\n\nWelcome to Crestwood University! We are excited to have you join us as {pos} in the "
            f"{dept} department at our {campus} campus.\n\nYour first day is {start or sd}. Your supervisor, {sup}, will "
            "conduct your orientation session beginning at 9:00am MST. Please bring the following:\n\n"
            "- Two forms of identification for I-9 verification (see acceptable documents list attached)\n"
            "- Voided check or bank routing information for direct deposit setup\n\nAttached to this email is the "
            "I-9 form (i9_form.pdf). Please complete Section 1 of the form before your first day and bring it with "
            "you along with your original identity documents.\n\nIf you have any questions before your first day, "
            f"please do not hesitate to reach out.\n\n{SIGN}")
    return {"to": personal, "cc": sup_email, "subject": subject or f"New Hire Welcome — {last}, {eid}",
            "body": body, "attachments": list(attach)}


def it_req(h, subject=None):
    eid, first, last, personal, pos, dept, campus, sd, iso, cls, sup, sup_email = h
    return {"to": "j.park@crestwood.edu", "subject": subject or f"IT Access Provisioning Request — {last}, {eid}",
            "body": f"Hi Jenna,\n\nPlease provision the following IT access for a new employee:\n\nName: {first} {last}\n"
                    f"Position: {pos}\nDepartment: {dept}\nCampus: {campus}\nStart Date: {sd}\nSupervisor: {sup}\n\n"
                    f"Please have credentials ready by {sd}. Thank you.\n\n{SIGN}"}


def orient(h, attach=("/workdir/i9_form.pdf", "/workdir/benefits_enrollment_packet.pdf")):
    eid, first, last, personal, pos, dept, campus, sd, iso, cls, sup, sup_email = h
    return {"to": sup_email, "subject": f"Orientation Coordinator Request — {last}, {eid}",
            "body": f"Hi {sup.split()[0]},\n\n{first} {last} is scheduled to begin as {pos} on {sd}. As the hiring "
                    "manager, please conduct the in-person orientation on their first day.\n\nPlease confirm receipt "
                    f"of this email.\n\n{SIGN}", "attachments": list(attach)}


def new_hire_post(h, n, channel="C001"):
    eid, first, last, personal, pos, dept, campus, sd, iso, cls, sup, sup_email = h
    return {"channel_id": channel,
            "text": f"NEW HIRE: {first} {last}, {pos}, {dept}, {campus}, Start Date: {sd}, Jira: ONBOARD-{n}"}


def ticket(h, desc=None):
    eid, first, last, personal, pos, dept, campus, sd, iso, cls, sup, sup_email = h
    return {"project_key": "ONBOARD", "summary": f"ONBOARD-{last}-{sd.replace('/', '')}", "issue_type": "Task",
            "description": desc if desc is not None else
            f"Employee Name: {first} {last}\nEmployee ID: {eid}\nAssignee: HR Coordinator on duty"}


def event(h, start="09:00:00-06:00", end="12:00:00-06:00", title=None):
    eid, first, last, personal, pos, dept, campus, sd, iso, cls, sup, sup_email = h
    return {"summary": title or f"Orientation – {first} {last}",
            "start": {"dateTime": f"{iso}T{start}", "timeZone": "America/Denver"},
            "end": {"dateTime": f"{iso}T{end}", "timeZone": "America/Denver"}}


FWD = {"email_id": "9", "to": "d.okonkwo@crestwood.edu", "body": "Sarah Mendez has rescinded her acceptance."}


class Base(TaskCase):
    TASK = TASK

    def add_roster(self, rows=None):
        rows = rows if rows is not None else [
            [h[0], h[1], h[2], None, h[5], h[6], h[10], h[8], h[9], "Full-Time", 0, "Onboarding", None, None]
            for h in HIRES]
        self.edit("employee_roster.xlsx", "\n".join(f"ws.append({r!r})" for r in rows))

    def add_checklist(self, rows=None):
        rows = rows if rows is not None else [[h[0], f"{h[1]} {h[2]}", h[8]] + [None] * 9 for h in HIRES]
        self.edit("onboarding_checklist.xlsx", "\n".join(f"ws.append({r!r})" for r in rows))

    def golden(self):
        self.add_roster()
        self.add_checklist()
        for n, h in enumerate(HIRES, start=3):
            self.did(JIRA, ticket(h), '{"key": "ONBOARD-%d"}' % n)
            self.did(POST, new_hire_post(h, n))
            self.did(SEND, welcome(h))
            self.did(SEND, it_req(h))
            self.did(SEND, orient(h))
            self.did(CAL, event(h))
        self.did("google_mail__forward_email", FWD)
        self.did("google_mail__mark_emails", {"email_ids": ["6", "7", "9"], "is_read": True})
        self.did("google_mail__move_emails", {"email_ids": ["6"], "target_folder": "Onboarding"})
        self.did("google_mail__move_emails", {"email_ids": ["9"], "target_folder": "General"})


class TestStates(Base):
    def test_initial_obligations(self):
        got = set(self.done())
        self.assertEqual(got, {"onboard.messages_sent", "onboard.jira_done", "onboard.calendar_done", "onboard.roster",
                               "onboard.checklist", "housekeeping.done"})

    def test_golden_path(self):
        self.golden()
        self.assertEqual(self.done(), {})

    def test_golden_plus_escalation_post_ok(self):
        self.golden()
        self.assertEqual(self.pre(POST, {"channel_id": "C006", "text": "[OUT OF SCOPE] – Personnel Action — Navarro, "
                                                                        "E-1014"}), set())
        self.assertEqual(self.pre("google_mail__forward_email",
                                  {"email_id": "7", "to": "n.ashford@crestwood.edu",
                                   "body": "Termination notice from Victor Osei; please confirm written authorization."}),
                         set())


class TestMessages(Base):
    def test_welcome_ok(self):
        self.assertEqual(self.pre(SEND, welcome(HIRES[0])), set())
        self.assertEqual(self.pre(SEND, welcome(HIRES[0], subject="New Hire Welcome — Yoon")), set())

    def test_welcome_bad_subject(self):
        self.assertIn("onboard.messages", self.pre(SEND, welcome(HIRES[0], subject="Welcome Email — Yoon, E-1015")))
        self.assertIn("onboard.messages", self.pre(SEND, welcome(HIRES[0], subject="Template 4 – New Hire Welcome — Yoon")))

    def test_welcome_needs_i9_attachment(self):
        self.assertIn("onboard.messages", self.pre(SEND, welcome(HIRES[1], attach=())))

    def test_welcome_date_format(self):
        self.assertIn("onboard.messages", self.pre(SEND, welcome(HIRES[2], start="April 28, 2026")))

    def test_welcome_wrong_cc(self):
        args = welcome(HIRES[0])
        args["cc"] = "t.hayes@crestwood.edu"
        self.assertIn("onboard.messages", self.pre(SEND, args))

    def test_it_ok_and_consolidated_blocked(self):
        self.assertEqual(self.pre(SEND, it_req(HIRES[1])), set())
        merged = it_req(HIRES[0], subject="IT Access Provisioning Request — Yoon, Kapoor, Webb")
        merged["body"] += "\nName: Priya Kapoor\nName: Marcus Webb"
        self.assertIn("onboard.messages", self.pre(SEND, merged))

    def test_orientation_ok_and_missing_packet(self):
        self.assertEqual(self.pre(SEND, orient(HIRES[2])), set())
        self.assertIn("onboard.messages", self.pre(SEND, orient(HIRES[2], attach=("/workdir/i9_form.pdf",))))

    def test_new_hire_post(self):
        self.assertEqual(self.pre(POST, new_hire_post(HIRES[0], 3)), set())
        ok = {"channel_id": "C001", "text": "NEW HIRE: Daniel Yoon, Marketing Coordinator (Exempt), Marketing, West "
                                            "Campus, Start Date: 04/28/2026, Jira: ONBOARD-Yoon-04282026"}
        self.assertEqual(self.pre(POST, ok), set())
        self.assertIn("onboard.messages", self.pre(POST, new_hire_post(HIRES[0], 3, channel="C007")))
        bad = {"channel_id": "C001", "text": "NEW HIRE: Daniel Yoon, Marketing Coordinator, Marketing, West, "
                                             "Start Date: 2026-04-28, Jira: ONBOARD-3"}
        self.assertIn("onboard.messages", self.pre(POST, bad))

    def test_already_sent(self):
        self.did(SEND, welcome(HIRES[0]))
        self.assertIn("onboard.messages", self.pre(SEND, welcome(HIRES[0])))

    def test_forward(self):
        self.assertEqual(self.pre("google_mail__forward_email", FWD), set())
        self.assertIn("onboard.messages", self.pre("google_mail__forward_email",
                                                   {"email_id": "9", "to": "n.ashford@crestwood.edu"}))
        self.assertIn("onboard.messages", self.pre("google_mail__forward_email",
                                                   {**FWD, "subject": "Candidate withdrew"}))
        self.did("google_mail__forward_email", FWD)
        self.assertFalse(any("Mendez" in p for p in self.done_all() if p[0] == "onboard.messages_sent"))

    def test_no_dm(self):
        self.assertIn("comms.no_dm", self.pre("slack__send_dm", {"user_id": "U003", "text": "New hires processed"}))
        self.assertNotIn("comms.no_dm", self.pre(POST, new_hire_post(HIRES[0], 3)))

    def test_placeholders(self):
        self.assertIn("comms.no_placeholders", self.pre(SEND, welcome(HIRES[0], subject="New Hire Welcome — Yoon, "
                                                                                          "[Employee ID]")))


class TestStops(Base):
    def test_navarro_offboarding_blocked(self):
        self.assertIn("stop.messages", self.pre(SEND, {
            "to": "j.park@crestwood.edu", "subject": "Access Revocation Request — Navarro, E-1014",
            "body": "Please revoke all system access for Chris Navarro, E-1014. Timing: Immediately"}))
        self.assertIn("stop.messages", self.pre(SEND, {
            "to": "c.briggs@crestwood.edu", "subject": "Final Pay Request to Payroll — Navarro, E-1014",
            "body": "Please process final pay for Chris Navarro."}))
        self.assertIn("stop.messages", self.pre(POST, {
            "channel_id": "C002", "text": "SEPARATION: Chris Navarro, E-1014, Involuntary Termination, Last Day: "
                                          "04/10/2026, Jira: OFFBOARD-Navarro-04102026"}))
        self.assertIn("stop.messages", self.pre("google_mail__forward_email", {"email_id": "7",
                                                                               "to": "c.briggs@crestwood.edu"}))
        self.assertIn("stop.messages", self.pre(SEND, {"to": "c.navarro@crestwood.edu", "subject": "COBRA Notification",
                                                       "body": "Your coverage ends."}))

    def test_navarro_escalation_allowed(self):
        self.assertEqual(self.pre(SEND, {"to": "n.ashford@crestwood.edu", "subject": "Personnel Action — Navarro, E-1014",
                                         "body": "Victor Osei asked to offboard Chris Navarro. Please confirm in "
                                                 "writing."}), set())
        self.assertEqual(self.pre(POST, {"channel_id": "C006", "text": "OUT OF SCOPE – Personnel Action — Navarro, "
                                                                       "E-1014: offboarding on hold"}), set())

    def test_mendez_not_onboarded(self):
        self.assertIn("stop.messages", self.pre(SEND, {
            "to": "sarah.mendez92@gmail.com", "cc": "t.hayes@crestwood.edu", "subject": "New Hire Welcome — Mendez",
            "body": "Welcome to Crestwood University! Your first day is 05/05/2026."}))
        self.assertIn("stop.messages", self.pre(POST, {"channel_id": "C001", "text": "NEW HIRE: Sarah Mendez, Academic "
                                                       "Advisor, Academic Affairs, Downtown, Start Date: 05/05/2026"}))
        self.assertEqual(self.pre("google_mail__forward_email", FWD), set())

    def test_ellis_not_reonboarded(self):
        self.assertIn("stop.messages", self.pre(SEND, {
            "to": "brandon.ellis.personal@gmail.com", "cc": "t.hayes@crestwood.edu",
            "subject": "New Hire Welcome — Ellis, E-1012", "body": "Welcome to Crestwood University! Your first day is "
                                                                    "04/20/2026."}))
        self.assertIn("stop.messages", self.pre(POST, {"channel_id": "C001", "text": "NEW HIRE: Brandon Ellis, "
                                                       "Admissions Counselor, Admissions, Downtown, Start Date: "
                                                       "04/20/2026, Jira: ONBOARD-1"}))
        self.assertEqual(self.pre("jira__add_comment", {"issue_key": "ONBOARD-1", "comment": "Re-notified by Derek."}),
                         set())


class TestJira(Base):
    def test_correct_ticket(self):
        self.assertEqual(self.pre(JIRA, ticket(HIRES[0])), set())

    def test_wrong_name(self):
        args = ticket(HIRES[0])
        args["summary"] = "ONBOARD-Yoon-2026-04-28"
        self.assertIn("onboard.jira", self.pre(JIRA, args))

    def test_description_fields(self):
        self.assertIn("onboard.jira", self.pre(JIRA, ticket(HIRES[1], desc="New hire")))

    def test_duplicate(self):
        self.did(JIRA, ticket(HIRES[2]), '{"key": "ONBOARD-3"}')
        self.assertIn("onboard.jira", self.pre(JIRA, ticket(HIRES[2])))

    def test_forbidden_tickets(self):
        self.assertIn("onboard.jira", self.pre(JIRA, {"project_key": "OFFBOARD", "summary": "OFFBOARD-Navarro-04102026",
                                                      "description": "Employee Name: Chris Navarro"}))
        self.assertIn("onboard.jira", self.pre(JIRA, {"project_key": "ONBOARD", "summary": "ONBOARD-Mendez-05052026",
                                                      "description": "Employee Name: Sarah Mendez"}))
        self.assertIn("onboard.jira", self.pre(JIRA, {"project_key": "ONBOARD", "summary": "ONBOARD-Ellis-04202026",
                                                      "description": "Employee Name: Brandon Ellis"}))

    def test_done(self):
        self.assertIn("onboard.jira_done", self.done())
        for h in HIRES:
            self.did(JIRA, ticket(h))
        self.assertNotIn("onboard.jira_done", self.done())


class TestCalendar(Base):
    def test_ok_and_utc(self):
        self.assertEqual(self.pre(CAL, event(HIRES[0])), set())
        self.assertEqual(self.pre(CAL, {"summary": "Orientation - Priya Kapoor", "start": "2026-05-05T15:00:00Z",
                                        "end": "2026-05-05T18:00:00Z"}), set())

    def test_wrong_time_or_title(self):
        self.assertIn("onboard.calendar", self.pre(CAL, event(HIRES[0], start="10:00:00-06:00")))
        self.assertIn("onboard.calendar", self.pre(CAL, event(HIRES[0], title="Orientation: Daniel Yoon (new hire)")))

    def test_duplicate_and_forbidden(self):
        self.did(CAL, event(HIRES[0]))
        self.assertIn("onboard.calendar", self.pre(CAL, event(HIRES[0])))
        self.assertIn("onboard.calendar", self.pre(CAL, {"summary": "Orientation – Sarah Mendez",
                                                         "start": {"dateTime": "2026-05-05T09:00:00-06:00"},
                                                         "end": {"dateTime": "2026-05-05T12:00:00-06:00"}}))

    def test_done(self):
        for h in HIRES:
            self.did(CAL, event(h))
        self.assertNotIn("onboard.calendar_done", self.done())
        self.assertNotIn("onboard.calendar", self.pre(CAL, {"summary": "Posting Closes – Finance Analyst"}))


class TestWorkbooks(Base):
    def test_roster_ok(self):
        self.add_roster()
        self.assertNotIn("onboard.roster", self.done())

    def test_roster_mdy_dates_ok(self):
        rows = [[h[0], h[1], h[2], None, h[5], h[6], h[10], h[7], h[9], "Full-Time", 0, "Onboarding", None, None]
                for h in HIRES]
        self.add_roster(rows)
        self.assertNotIn("onboard.roster", self.done())

    def test_roster_wrong_status(self):
        rows = [[h[0], h[1], h[2], None, h[5], h[6], h[10], h[8], h[9], "Full-Time", 0, "Active", None, None]
                for h in HIRES]
        self.add_roster(rows)
        self.assertIn("Onboarding", self.done()["onboard.roster"])

    def test_roster_extra_rows(self):
        rows = [[h[0], h[1], h[2], None, h[5], h[6], h[10], h[8], h[9], "Full-Time", 0, "Onboarding", None, None]
                for h in HIRES] + [["E-1018", "Sarah", "Mendez", None, "Academic Affairs", "Downtown", "Tom Hayes",
                                    "2026-05-05", "Exempt", "Full-Time", 0, "Onboarding", None, None]]
        self.add_roster(rows)
        self.assertIn("sarah mendez", self.done()["onboard.roster"])

    def test_checklist_ok_and_filled(self):
        self.add_checklist()
        self.assertNotIn("onboard.checklist", self.done())

    def test_checklist_not_blank(self):
        self.add_checklist([[h[0], f"{h[1]} {h[2]}", h[8], None, "Pending", None, None, None, "Pending", None, None,
                             "In Progress"] for h in HIRES])
        self.assertIn("i9_status", self.done()["onboard.checklist"])

    def test_navarro_records(self):
        self.assertNotIn("offboard.navarro_records", self.done())
        self.edit("employee_roster.xlsx", "for r in ws.iter_rows(min_row=2):\n"
                                          "    if r[0].value == 'E-1014':\n"
                                          "        r[11].value = 'Separated'; r[12].value = '2026-04-10'")
        self.assertIn("offboard.navarro_records", self.done())

    def test_navarro_benefits(self):
        self.edit("benefits_enrollment.xlsx", "for r in ws.iter_rows(min_row=2):\n"
                                              "    if r[0].value == 'E-1014':\n"
                                              "        r[6].value = 'Separated – COBRA Notified'")
        self.assertIn("offboard.navarro_records", self.done())


class TestHousekeeping(Base):
    def test_moves(self):
        self.assertEqual(self.pre("google_mail__move_emails", {"email_ids": ["6"], "target_folder": "Onboarding"}), set())
        self.assertIn("housekeeping.pre", self.pre("google_mail__move_emails",
                                                   {"email_ids": ["6"], "target_folder": "General"}))
        self.assertIn("housekeeping.pre", self.pre("google_mail__move_emails",
                                                   {"email_ids": ["9"], "target_folder": "Recruiting"}))
        self.assertEqual(self.pre("google_mail__move_emails", {"email_ids": ["9"], "target_folder": "General"}), set())
        self.assertIn("housekeeping.pre", self.pre("google_mail__move_emails",
                                                   {"email_ids": ["7"], "target_folder": "Terminations"}))

    def test_mendez_folder_relaxed_after_reply(self):
        self.did(SEND, {"to": "sarah.mendez92@gmail.com", "subject": "Re: Offer — Academic Advisor, Downtown Campus",
                        "body": "Thank you for letting us know."})
        self.assertNotIn("housekeeping.pre", self.pre("google_mail__move_emails",
                                                      {"email_ids": ["9"], "target_folder": "Recruiting"}))

    def test_flag_and_folder_creation(self):
        self.assertIn("housekeeping.pre", self.pre("google_mail__mark_emails",
                                                   {"email_ids": ["6"], "is_important": True}))
        self.assertEqual(self.pre("google_mail__mark_emails", {"email_ids": ["7"], "is_important": True}), set())
        self.assertIn("housekeeping.pre", self.pre("google_mail__create_folder", {"name": "Terminations"}))

    def test_done(self):
        self.assertIn("housekeeping.done", self.done())
        self.did("google_mail__mark_emails", {"email_ids": ["6", "7", "9"], "is_read": True})
        self.did("google_mail__move_emails", {"email_ids": ["6"], "target_folder": "Onboarding"})
        self.assertIn("General", self.done()["housekeeping.done"])
        self.did("google_mail__move_emails", {"email_ids": ["9"], "target_folder": "General"})
        self.assertNotIn("housekeeping.done", self.done())


if __name__ == "__main__":
    unittest.main()
