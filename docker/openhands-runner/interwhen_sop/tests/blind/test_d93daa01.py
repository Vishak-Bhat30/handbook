"""Blind verifier tests for hr_crestwood_university_d93daa01 (exit interview scheduling)."""

from __future__ import annotations

import datetime as dt
import json

from interwhen_sop.tests.base import TaskCase

CAL = "google_calendar__create_event"
UPD = "google_calendar__update_event"
DEL = "google_calendar__delete_event"
SEND = "google_mail__send_email"
GOOD = {
    "smith": ("Exit Interview – James Smith", "2026-02-12T15:30:00-07:00", "2026-02-12T16:30:00-07:00"),
    "romero": ("Exit Interview – Teresa Romero", "2026-02-13T09:00:00-07:00", "2026-02-13T09:30:00-07:00"),
    "tran": ("Exit Interview – Gabriel Tran", "2026-02-20T14:00:00-07:00", "2026-02-20T14:30:00-07:00"),
}


def ev_args(summary, start, end, **kw):
    return {"summary": summary, "start": {"dateTime": start, "timeZone": "America/Denver"},
            "end": {"dateTime": end, "timeZone": "America/Denver"}, **kw}


class D93(TaskCase):
    TASK = "hr_crestwood_university_d93daa01"

    def create(self, summary, start, end, eid):
        args = ev_args(summary, start, end)
        res = "[Tool 'google_calendar__create_event' executed.]" + json.dumps(
            {"status": "success", "event": {**args, "id": eid}})
        self.did(CAL, args, res)

    def golden(self):
        for i, (k, v) in enumerate(GOOD.items()):
            self.create(*v, f"new{i}")


class TestCompletion(D93):
    def test_initial_lists_three_interviews(self):
        found = self.done_all()
        self.assertEqual([r for r, _ in found], ["exit.scheduled"] * 3)
        text = " ".join(p for _, p in found)
        for v in GOOD.values():
            self.assertIn(v[0], text)
        self.assertIn("02/12/2026 3:30pm–4:30pm", text)
        self.assertIn("02/13/2026 9:00am–9:30am", text)
        self.assertIn("02/20/2026 2:00pm–2:30pm", text)

    def test_golden_path(self):
        self.golden()
        self.assertEqual(self.done(), {})

    def test_wrong_slot_flagged(self):
        self.create("Exit Interview – James Smith", "2026-02-13T09:00:00-07:00", "2026-02-13T10:00:00-07:00", "a")
        self.create(*GOOD["romero"][:1], "2026-02-16T14:00:00-07:00", "2026-02-16T14:30:00-07:00", "b")
        self.create(*GOOD["tran"], "c")
        found = self.done_all()
        self.assertEqual(len([r for r, _ in found if r == "exit.scheduled"]), 2)
        self.assertTrue(any("holiday" in p for _, p in found))
        self.assertTrue(any("only slot that works for Teresa Romero" in p for _, p in found))

    def test_duplicate_and_ineligible_flagged(self):
        self.golden()
        self.create("Exit Interview – Gabriel Tran", "2026-02-20T08:00:00-07:00", "2026-02-20T08:30:00-07:00", "d")
        self.create("Exit Interview – Kathryn Williams", "2026-02-12T09:30:00-07:00", "2026-02-12T10:00:00-07:00", "e")
        probs = [p for _, p in self.done_all()]
        self.assertTrue(any("2 exit interview events" in p for p in probs))
        self.assertTrue(any("involuntary" in p for p in probs))

    def test_delete_then_recreate_ok(self):
        self.create(*GOOD["romero"][:1], "2026-02-16T14:00:00-07:00", "2026-02-16T14:30:00-07:00", "x1")
        self.did(DEL, {"eventId": "x1"}, '{"status":"success","message":"Event deleted"}')
        self.create(*GOOD["smith"], "s")
        self.create(*GOOD["romero"], "r")
        self.create(*GOOD["tran"], "t")
        self.assertEqual(self.done(), {})

    def test_failed_create_ignored(self):
        self.did(CAL, ev_args(*GOOD["smith"]), "")
        self.assertIn("exit.scheduled", self.done())
        self.assertEqual(self.pre(CAL, ev_args(*GOOD["smith"])), set())

    def test_seed_event_deleted_flagged(self):
        self.golden()
        self.did(DEL, {"eventId": "evt-108"}, '{"status":"success","message":"Event deleted"}')
        self.assertIn("calendar.unchanged_otherwise", self.done())

    def test_update_moves_event(self):
        self.golden()
        res = json.dumps({"status": "success", "event": {**ev_args("Exit Interview – Gabriel Tran",
                                                                    "2026-02-20T08:00:00-07:00",
                                                                    "2026-02-20T08:30:00-07:00"), "id": "new2"}})
        self.did(UPD, {"eventId": "new2", "start": {"dateTime": "2026-02-20T08:00:00-07:00"}}, res)
        self.assertIn("exit.scheduled", self.done())

    def test_roster_edit_flagged(self):
        self.golden()
        self.edit("employee_roster.xlsx", "ws.cell(row=66, column=col['Status']).value='Separated'")
        self.assertIn("roster.unchanged", self.done())


class TestSlotPre(D93):
    def test_good_slots_pass(self):
        for v in GOOD.values():
            self.assertEqual(self.pre(CAL, ev_args(*v)), set())

    def test_holiday_and_wfh_blocked(self):
        self.assertIn("exit.calendar_slot", self.pre(CAL, ev_args(
            "Exit Interview – Teresa Romero", "2026-02-16T14:00:00-07:00", "2026-02-16T14:30:00-07:00")))
        self.assertIn("exit.calendar_slot", self.pre(CAL, ev_args(
            "Exit Interview – Teresa Romero", "2026-02-12T08:00:00-07:00", "2026-02-12T08:30:00-07:00")))

    def test_today_tomorrow_blocked(self):
        self.assertIn("exit.calendar_slot", self.pre(CAL, ev_args(
            "Exit Interview – James Smith", "2026-02-11T15:30:00-07:00", "2026-02-11T16:30:00-07:00")))

    def test_duration_title_conflict(self):
        self.assertIn("exit.calendar_slot", self.pre(CAL, ev_args(
            "Exit Interview – James Smith", "2026-02-12T15:30:00-07:00", "2026-02-12T16:00:00-07:00")))
        self.assertIn("exit.calendar_slot", self.pre(CAL, ev_args(
            "Exit Interview - Gabriel Tran", "2026-02-20T14:00:00-07:00", "2026-02-20T14:30:00-07:00")))
        self.assertIn("exit.calendar_slot", self.pre(CAL, ev_args(
            "Exit Interview – Gabriel Tran", "2026-02-19T15:00:00-07:00", "2026-02-19T15:30:00-07:00")))

    def test_friday_after_3_and_last_day(self):
        self.assertIn("exit.calendar_slot", self.pre(CAL, ev_args(
            "Exit Interview – Gabriel Tran", "2026-02-20T16:30:00-07:00", "2026-02-20T17:00:00-07:00")))

    def test_reserved_slot_blocked(self):
        self.assertIn("exit.calendar_slot", self.pre(CAL, ev_args(
            "Exit Interview – James Smith", "2026-02-13T09:00:00-07:00", "2026-02-13T10:00:00-07:00")))

    def test_ineligible_and_unknown_blocked(self):
        self.assertIn("exit.calendar_slot", self.pre(CAL, ev_args(
            "Exit Interview – Kathryn Williams", "2026-02-12T09:30:00-07:00", "2026-02-12T10:00:00-07:00")))
        self.assertIn("exit.calendar_slot", self.pre(CAL, ev_args(
            "Exit Interview – Diana Ramirez", "2026-02-12T09:30:00-07:00", "2026-02-12T10:00:00-07:00")))

    def test_duplicate_create_blocked(self):
        self.create(*GOOD["tran"], "t1")
        self.assertIn("exit.calendar_slot", self.pre(CAL, ev_args(*GOOD["tran"])))

    def test_update_checked(self):
        self.create(*GOOD["tran"], "t1")
        self.assertEqual(self.pre(UPD, {"eventId": "t1", "description": "In person"}), set())
        self.assertIn("exit.calendar_slot", self.pre(UPD, {
            "eventId": "t1", "start": {"dateTime": "2026-02-18T14:00:00-07:00"},
            "end": {"dateTime": "2026-02-18T14:30:00-07:00"}}))

    def test_unique_feasible_slots(self):
        from interwhen_sop import framework, sopdata, state
        from interwhen_sop.verifiers import hr_crestwood_university_d93daa01 as m
        ctx = framework.Context(sopdata.load(), state.build([]), [])
        evs = m.calendar(ctx)
        found = {}
        for key, e in m.EMP.items():
            day = dt.date(2026, 2, 9)
            while day <= dt.date(2026, 2, 27):
                t = dt.datetime.combine(day, dt.time(7, 0))
                while t.time() <= dt.time(17, 0):
                    end = t + dt.timedelta(minutes=e["minutes"])
                    if not m.slot_problems(key, t, end, evs):
                        found.setdefault(key, []).append((t, end))
                    t += dt.timedelta(minutes=5)
                day += dt.timedelta(days=1)
        self.assertEqual(found, {k: [e["slot"]] for k, e in m.EMP.items()})

    def test_wfh_matches_roster(self):
        from interwhen_sop import framework, sopdata, state
        from interwhen_sop.kit import world
        ctx = framework.Context(sopdata.load(), state.build([]), [])
        w = world(ctx)
        notes = {eid: w.col(w.find(r"employee_roster", r"^Email$", r"Employee ID", eid, "initial"), r"Notes")
                 for eid in ("E-1052", "E-1158", "E-1064")}
        self.assertIn("Tuesdays and Thursdays", notes["E-1052"])
        self.assertIn("Mon/Wed", notes["E-1158"])
        self.assertNotIn("WFH", notes["E-1064"])


class TestCalendarOther(D93):
    def test_other_event_blocked(self):
        self.assertIn("calendar.no_unrequested", self.pre(CAL, ev_args(
            "Paperwork wrap-up", "2026-02-13T15:00:00-07:00", "2026-02-13T16:00:00-07:00")))
        self.assertEqual(self.pre(CAL, ev_args(*GOOD["smith"])), set())

    def test_seed_edit_blocked(self):
        self.assertIn("calendar.no_unrequested", self.pre(DEL, {"eventId": "evt-053"}))
        self.assertIn("calendar.no_unrequested", self.pre(UPD, {"eventId": "evt-108", "summary": "x"}))
        self.create(*GOOD["tran"], "t1")
        self.assertEqual(self.pre(DEL, {"eventId": "t1"}), set())

    def test_other_event_completion(self):
        self.golden()
        self.create("Hold", "2026-02-13T15:00:00-07:00", "2026-02-13T16:00:00-07:00", "h")
        self.assertIn("calendar.unchanged_otherwise", self.done())


class TestComms(D93):
    T14 = ("Hi James,\n\nAs part of our offboarding process, we would like to offer you the opportunity to participate "
           "in an exit interview.")

    def test_no_resend_t14(self):
        self.assertIn("comms.no_resend_t14", self.pre(SEND, {"to": "j.smith@crestwood.edu", "subject": "x",
                                                            "body": self.T14}))
        self.assertEqual(self.pre(SEND, {"to": "j.smith@crestwood.edu", "subject": "Exit Interview — Smith, E-1064",
                                         "body": "Your exit interview is on 02/12/2026 at 3:30pm."}), set())

    def test_recipients(self):
        self.assertIn("comms.recipients", self.pre(SEND, {"to": "jsmith@crestwood.edu", "subject": "s", "body": "b"}))
        self.assertEqual(self.pre(SEND, {"to": "n.ashford@crestwood.edu", "subject": "s", "body": "b"}), set())

    def test_placeholders(self):
        self.assertIn("comms.no_placeholders", self.pre(SEND, {
            "to": "j.smith@crestwood.edu", "subject": "s", "body": "Hi [First Name], see you"}))

    def test_reply_subject(self):
        self.assertIn("comms.reply_subject", self.pre("google_mail__reply_to_email", {
            "email_id": "2", "subject": "Exit interview scheduled", "body": "See you 02/12/2026."}))
        self.assertEqual(self.pre("google_mail__reply_to_email", {
            "email_id": "2", "subject": "Re: Exit Interview Invitation — Smith, E-1064",
            "body": "See you 02/12/2026."}), set())

    def test_slack(self):
        self.assertIn("slack.channels", self.pre("slack__send_dm", {"user_id": "U1", "text": "hi"}))
        self.assertIn("slack.channels", self.pre("slack__post_message", {"channel": "random", "text": "hi"}))
        self.assertIn("slack.channels", self.pre("slack__post_message", {
            "channel": "hr-leave-requests", "text": "Murphy ADA accommodation update"}))
        self.assertEqual(self.pre("slack__post_message", {"channel": "hr-offboarding", "text": "Exit interviews set"}),
                         set())

    def test_dates(self):
        self.assertIn("dates.format", self.pre(CAL, ev_args(*GOOD["smith"], description="Last day 2026-02-13")))
        self.assertIn("dates.format", self.pre(CAL, ev_args(*GOOD["smith"], description="Last day Feb 13")))
        self.assertIn("dates.format", self.pre(CAL, ev_args(*GOOD["smith"], description="Last day 2/13/2026")))
        self.assertEqual(self.pre(CAL, ev_args(*GOOD["smith"], description="Last day 02/13/2026, 9:30am-2:00pm")),
                         set())


class TestJiraEmailFiles(D93):
    def test_jira_no_duplicate(self):
        self.assertIn("jira.no_duplicate", self.pre("jira__create_issue", {
            "project_key": "OFFBOARD", "summary": "OFFBOARD-Smith-02132026", "description": ""}))
        self.assertEqual(self.pre("jira__create_issue", {"project_key": "HR", "summary": "Unrelated",
                                                         "description": ""}), set())

    def test_not_complete(self):
        self.assertIn("offboarding.not_complete", self.pre("jira__transition_issue", {
            "issue_key": "OFFBOARD-4", "transition": "Closed"}))
        self.assertEqual(self.pre("jira__transition_issue", {"issue_key": "OFFBOARD-4", "transition": "In Progress"}),
                         set())
        self.assertIn("offboarding.not_complete", self.pre("slack__post_message", {
            "channel": "hr-offboarding", "text": "OFFBOARDING COMPLETE: James Smith, E-1064"}))

    def test_jira_comment_format(self):
        self.assertEqual(self.pre("jira__add_comment", {
            "issue_key": "OFFBOARD-4", "comment": "02/10/2026 10:00am [12.5] — CALENDAR EVENT CREATED — Exit "
                                                  "Interview – James Smith on 02/12/2026"}), set())
        self.assertIn("jira.comment_format", self.pre("jira__add_comment", {
            "issue_key": "OFFBOARD-4", "comment": "Scheduled exit interview for Thursday."}))

    def test_housekeeping(self):
        self.assertEqual(self.pre("google_mail__move_emails", {"email_ids": ["2"], "target_folder": "Offboarding"}),
                         set())
        self.assertIn("email.housekeeping", self.pre("google_mail__move_emails", {
            "email_ids": ["2"], "target_folder": "General"}))
        self.assertIn("email.housekeeping", self.pre("google_mail__move_emails", {
            "email_ids": ["2"], "target_folder": "Exit Interviews"}))
        self.assertIn("email.housekeeping", self.pre("google_mail__mark_emails", {"email_ids": ["2"],
                                                                                  "is_read": False}))
        self.assertEqual(self.pre("google_mail__mark_emails", {"email_ids": ["2"], "is_read": True}), set())

    def test_roster_writes(self):
        code = "import openpyxl\nwb=openpyxl.load_workbook('/workdir/employee_roster.xlsx')\nwb.save('/workdir/employee_roster.xlsx')"
        self.assertIn("roster.no_writes", self.pre("syntara__executePython", {"code": code}))
        self.assertEqual(self.pre("syntara__executePython", {
            "code": "import openpyxl\nwb=openpyxl.load_workbook('/workdir/employee_roster.xlsx')\nprint(wb.sheetnames)"}),
            set())
