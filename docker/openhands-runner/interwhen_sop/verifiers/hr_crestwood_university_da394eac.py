"""Interwhen SOP verifiers for hr_crestwood_university_da394eac (blind build from SOP + seed data only).

Situation (today 04/07/2026 noon MDT; 04/03 and 04/06 are SOP holidays):
- unread: Lisa Fontaine PTO inquiry (Template 20, 68 h, 4.62 h/pay period -> Leave folder);
  facilities light-bulb request (out of scope -> #hr-general "[OUT OF SCOPE] – <subject>", no reply -> General).
- William Trent: 30-day benefits window closed 04/02/2026, Templates 8/9 already sent -> default enrollment
  effective 05/01/2026, Template 10, then onboarding complete (roster Active, HR-7 "Status – CLOSED", Slack).
- Tomás Salazar: I-9 Section 2 not received; Day 2 = 04/07 -> Template 6 to hiring manager Patricia Huang
  (per Jira HR-6), CC employee; deadline (Day 3) 04/08/2026 -> no overdue escalation yet.
- Meghan Cross: FMLA certification due 04/07/2026 11AM, not received -> Template 18, Slack overdue post,
  "FMLA Deadline Passed - CU-1023" email to Patricia.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import re
from dataclasses import dataclass

from ..kit import (Action, Comm, Context, World, comm_rules, dashes, no_placeholders, norm, pre_rule, same,
                   state_rule, world)

TODAY = "04/07/2026"
REPLY_TOOLS = ("google_mail__reply_to_email", "google_mail__reply_email")
FOLDERS = ("Onboarding", "Offboarding", "Leave", "Performance", "Recruiting", "General")

TRENT = ("w.trent@crestwood.edu", "william.trent.work@gmail.com")
SALAZAR = ("t.salazar@crestwood.edu", "tomas.salazar.co@protonmail.com")
HUANG = "p.huang@crestwood.edu"
CROSS = "m.cross@crestwood.edu"
FONTAINE = "l.fontaine@crestwood.edu"

R_OOS = ("1", "Do not deviate from the procedures described in this document.", "1 Overview (out of scope)")
R_DM = ("5", "All operational HR communications must use designated Slack channels.", "5 Slack channels")
R_TICKETS = ("8", "Step 5: Check Jira for existing open tickets", "8 Step 5")
R_REPLIES = ("8", "Replies to previous emails:", "8 Replies")
R_EMAILS = ("3.2", "All employee internal email addresses follow", "3.2 Employee email addresses")
R_DATES = ("3.1", "All times in this document", "3.1 Dates & Times")
R_SLA = ("10", "HR office hours are Monday", "10 Business days")
R_HOLIDAYS = ("10", "Observed Holidays – 2026", "10 Observed holidays")
R_ONB = ("11", "Crestwood University – HR Standard Operating Procedure Among each", "11 Onboarding (hiring manager in Jira)")
R_I9 = ("11.2", "Federal law requires that Section 1", "11.2 I-9")
R_I9_D2 = ("11.2", "Day 2 (if I-9 not received by 9AM)", "11.2 Day 2")
R_I9_D3 = ("11.2", "Day 3 (if I-9 still not received by 9AM)", "11.2 Day 3")
R_I9_AFTER = ("11.2", "After Day 3 (deadline at 9AM passed", "11.2 After Day 3")
R_BEN = ("11.3", "New employees have 30 calendar days", "11.3 Benefits window")
R_BEN15 = ("11.3", "Day 15: If benefits_enrollment.xlsx", "11.3 Day 15")
R_BEN25 = ("11.3", "Day 25: If still no enrollment", "11.3 Day 25")
R_BEN_EFF = ("11.3", "Default enrollment effective date rule:", "11.3 Default effective date")
R_BEN_EX = ("11.3", "Crestwood University – HR Standard Operating Procedure example, if", "11.3 Effective date example")
R_BEN_EXT = ("11.3", "Prior to processing any default enrollment", "11.3 Extension check")
R_BEN30 = ("11.3", "Day 30 (Deadline):", "11.3 Day 30")
R_ONB_DONE = ("11.4", "When all items in onboarding_checklist.xlsx", "11.4 Onboarding completion")
R_LEAVE = ("13", "Crestwood University provides leave", "13 Leave management")
R_CERT = ("13.1", "If the employee does not return the medical certification by 11AM", "13.1 Certification overdue")
R_T18 = ("13.1", "Send Template 18 (FMLA Certification Overdue)", "13.1 Template 18")
R_CERT_SLACK = ("13.1", "Post to #hr-leave-requests:", "13.1 Overdue Slack post")
R_CERT_HUANG = ("13.1", "Send an email to p.huang@crestwood.edu with the subject line", "13.1 Email to Patricia")
R_PTO1 = ("13.3", "Step 1: Open leave_tracker.xlsx", "13.3 Step 1")
R_PTO2 = ("13.3", "Step 2: Reply to the employee using Template 20", "13.3 Step 2")
R_LT_RO = ("12", "Crestwood University – HR Standard Operating Procedure separation type.", "6 leave_tracker (read-only)")
R_FOLDERS = ("17", "Folder names must match exactly", "17 Email housekeeping")
R_FOLDER_TBL = ("17", "Folder Name Use For Precedence", "17 Folder table")
R_FOLDER_LEAVE = ("17", "Leave FMLA, ADA, PTO", "17 Leave folder")
R_FOLDER_GEN = ("17", "Crestwood University – HR Standard Operating Procedure General", "17 General folder")
R_TEMPLATES = ("18", "Templates must be used as written.", "18 Email templates")
R_T6 = ("18", "Crestwood University – HR Standard Operating Procedure Best regards, Crestwood University – Office of Human Resources hr@crestwood.edu Template 6", "Template 6")  # noqa: E501
R_T7 = ("2", "Best regards, Crestwood University – Office of Human Resources hr@crestwood.edu Template 7",
        "Template 7")
R_T8 = ("2", "Best regards, Crestwood University – Office of Human Resources hr@crestwood.edu Template 8",
        "Template 8")
R_T9 = ("2", "Best regards, Crestwood University – Office of Human Resources hr@crestwood.edu Template 9",
        "Template 9")
R_T10 = ("2", "Best regards, Crestwood University – Office of Human Resources hr@crestwood.edu Template 10",
         "Template 10")
R_T18_TXT = ("2", "Crestwood University – HR Standard Operating Procedure This is a reminder that your FMLA",
             "Template 18")
R_T20 = ("2", "Best regards, Crestwood University – Office of Human Resources hr@crestwood.edu Template 20",
         "Template 20")
R_JIRA_DESC = ("19", "Field Format Add When", "19 Jira description fields")
R_JIRA_COMMENT = ("19", "Crestwood University – HR Standard Operating Procedure Default Jira Comment Format",
                  "19 Jira comment format")
R_JIRA_LINE = ("19", "[Date and time] [SOP SUBHEADER]", "19 Jira comment line")
R_JIRA_ACTIONS = ("19", "Action Use When TEMPLATE SENT", "19 Jira comment actions")
R_SUBJECT = ("19", "Crestwood University – HR Standard Operating Procedure CLOSED The ticket", "19 Email subject format")


# ---- helpers ---------------------------------------------------------------------------------------

def as_date(v) -> dt.date | None:
    s = str(v if v is not None else "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S", "%m/%d/%y"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def seed_email(w: World, eid) -> dict:
    return next((e for e in w.seed_emails if str(e.get("email_id")) == str(eid)), {})


def resolved(a: Action, w: World) -> Action:
    """Replies carry only an email id: add the original sender as recipient and 'Re: <subject>'."""
    if a.tool not in REPLY_TOOLS:
        return a
    e = seed_email(w, a.args.get("email_id") or a.args.get("id") or "")
    to = list(a.recipients)
    sender = str(e.get("from_addr") or "").lower()
    if sender and sender not in to:
        to.append(sender)
    subj = a.subject or (f"Re: {e.get('subject')}" if e.get("subject") else "")
    return dataclasses.replace(a, recipients=to, subject=subj)


def is_email(a: Action) -> bool:
    return a.kind in ("email_send", "email_draft")


def body(a: Action) -> str:
    return dashes(f"{a.subject}\n{a.text}")


@dataclass
class TComm(Comm):
    """Comm with reply resolution, alternative subjects/recipients and an exact raw subject."""
    subjects: tuple = ()      # regexes, fullmatch on the dash-normalised subject (any one)
    raw_subject: str = ""     # exact subject as printed in the SOP (no dash normalisation)
    to_any: tuple = ()
    cc_any: tuple = ()

    def problems(self, a: Action, w: World) -> list[str]:
        a = resolved(a, w)
        out = super().problems(a, w)
        if self.forbidden or self.kind not in ("email", "forward", "draft") or not is_email(a):
            return out
        rec = {x.lower() for x in a.recipients}
        allr = rec | {x.lower() for x in a.cc}
        if self.to_any and not rec & set(self.to_any):
            out.append(f"To must be {self.to_any[0]} (the address on employee_roster.xlsx).")
        if self.cc_any and not allr & set(self.cc_any):
            out.append(f"CC must include {self.cc_any[0]}.")
        if self.subjects and not any(re.fullmatch(s, dashes(a.subject).strip(), re.I) for s in self.subjects):
            out.append(f"Subject must follow the SOP format: {self.subject_hint} (got \"{a.subject}\").")
        if self.raw_subject and a.subject.strip() != self.raw_subject:
            out.append(f"Subject must be exactly \"{self.raw_subject}\" (got \"{a.subject}\").")
        return out


# ---- messages ---------------------------------------------------------------------------------------

def specs(ctx: Context) -> list[Comm]:
    w = world(ctx)

    def rec(a: Action) -> set[str]:
        r = resolved(a, w)
        return {x.lower() for x in r.recipients + r.cc}

    def rx(p: str, a: Action) -> bool:
        return bool(re.search(p, body(a), re.I | re.S))

    return [
        TComm("pto_fontaine", "email", lambda a: is_email(a) and FONTAINE in rec(a),
              "Template 20 (PTO Balance Response) reply to Lisa Fontaine", [R_PTO1, R_PTO2, R_T20, R_DATES],
              to=[FONTAINE], exact_to=False,
              subjects=(r"Re: PTO balance check", r"(Template 20 [-–—] )?PTO Balance Response [-–—] Fontaine, CU-1010"),
              subject_hint="reply to her email (keeps \"Re: PTO balance check\")",
              body=[(r"as of 04/07/2026 is 68(\.0+)? hours",
                     "\"Your current PTO balance as of 04/07/2026 is 68 hours.\" (leave_tracker.xlsx Current PTO Balance)"),
                    (r"accrual rate is 4\.62 hours per pay period",
                     "\"Your accrual rate is 4.62 hours per pay period.\" (Accrual Schedule, Non-Exempt Full-Time)")]),
        TComm("oos_slack", "slack_post", lambda a: a.kind in ("slack_post", "slack_dm") and rx(r"OUT OF SCOPE|light bulb", a),
              "out-of-scope notice for the facilities light-bulb email", [R_OOS], channel="hr-general",
              body=[(r"\[OUT OF SCOPE\] [-–—] HR office light bulb out [-–—] Main Campus rm 214",
                     "\"[OUT OF SCOPE] – HR office light bulb out – Main Campus rm 214\"")]),
        TComm("oos_no_reply", "email",
              lambda a: is_email(a) and ("facilities@crestwood.edu" in rec(a)
                                         or (a.tool in REPLY_TOOLS and str(a.args.get("email_id")) == "11")),
              "reply to the out-of-scope facilities request", [R_OOS],
              forbidden="The light-bulb request is out of scope: do not process it further - only post "
                        "\"[OUT OF SCOPE] – HR office light bulb out – Main Campus rm 214\" in #hr-general."),
        TComm("t10_trent", "email", lambda a: is_email(a) and bool(rec(a) & set(TRENT)) and rx(r"default|automatically enrolled", a),
              "Template 10 (Default Benefits Enrollment Confirmation) to William Trent (w.trent@crestwood.edu)",
              [R_BEN, R_BEN_EFF, R_BEN_EX, R_BEN30, R_T10, R_EMAILS, R_SUBJECT], to_any=TRENT, exact_to=False,
              subjects=(r"(Template 10 [-–—] )?Default Benefits Enrollment Confirmation [-–—] Trent, CU-1022",
                        r"Re: New Hire [-–—] William Trent [-–—] Start 03/03/2026"),
              subject_hint="Default Benefits Enrollment Confirmation — Trent, CU-1022",
              body=[(r"enrollment deadline of 04/02/2026 has passed", "deadline 04/02/2026 (start 03/03/2026 + 30 days)"),
                    (r"automatically enrolled in Crestwood University.s default health plan effective 05/01/2026",
                     "\"automatically enrolled in Crestwood University's default health plan effective 05/01/2026\"")]),
        TComm("t6_salazar", "email",
              lambda a: is_email(a) and rx(r"I-9", a) and rx(r"Salazar", a)
              and not rx(r"may not continue working|not been completed by the federal deadline", a),
              "Template 6 (I-9 Urgent Reminder, Day 2) for Tomás Salazar to the hiring manager Patricia Huang "
              "(per Jira HR-6), CC the employee (t.salazar@crestwood.edu)",
              [R_I9_D2, R_ONB, R_T6, R_SLA, R_HOLIDAYS, R_SUBJECT], to=[HUANG], exact_to=False, cc_any=SALAZAR,
              subjects=(r"(Template 6 [-–—] )?I-9 Urgent Reminder [-–—] Salazar, CU-1026",
                        r"Re: New Hire [-–—] Tom[aá]s Salazar [-–—] Student Affairs [-–—] 04/02"),
              subject_hint="I-9 Urgent Reminder — Salazar, CU-1026",
              body=[(r"urgent reminder regarding the I-9 Employment Eligibility Verification for Tom[aá]s Salazar \(CU-1026\)",
                     "Template 6 text \"This is an urgent reminder regarding the I-9 Employment Eligibility Verification "
                     "for Tomás Salazar (CU-1026).\""),
                    (r"Section 2 of the I-9 is 04/08/2026",
                     "\"The federal deadline for completing Section 2 of the I-9 is 04/08/2026.\" (Day 3; 04/03 and 04/06 "
                     "are holidays)")]),
        TComm("t18_cross", "email",
              lambda a: is_email(a) and CROSS in rec(a) and rx(r"certification", a)
              and not rx(r"do not meet the eligibility", a),
              "Template 18 (FMLA Certification Overdue) to Meghan Cross", [R_CERT, R_T18, R_T18_TXT, R_SUBJECT],
              to=[CROSS], exact_to=False,
              subjects=(r"(Template 18 [-–—] )?FMLA Certification Overdue [-–—] Cross, CU-1023", r"Re: FMLA Leave Request"),
              subject_hint="FMLA Certification Overdue — Cross, CU-1023",
              body=[(r"FMLA Medical Certification Form was due on 04/07/2026 and has not been received",
                     "\"your FMLA Medical Certification Form was due on 04/07/2026 and has not been received\"")]),
        TComm("cross_huang", "email",
              lambda a: is_email(a) and HUANG in rec(a) and CROSS not in rec(a)
              and (rx(r"FMLA Deadline Passed", a) or (rx(r"Meghan Cross|CU-1023", a) and rx(r"overdue", a))),
              "\"FMLA Deadline Passed\" email to Patricia Huang for Meghan Cross", [R_CERT, R_CERT_HUANG],
              to=[HUANG], exact_to=False, raw_subject="FMLA Deadline Passed - CU-1023",
              subject_hint="FMLA Deadline Passed - CU-1023",
              exact=r"(?i)Meghan Cross FMLA Certification overdue\.?",
              exact_hint="Meghan Cross FMLA Certification overdue"),
        TComm("cross_slack", "slack_post",
              lambda a: a.kind in ("slack_post", "slack_dm") and (rx(r"CERTIFICATION OVERDUE", a)
                                                                  or (rx(r"Meghan Cross|CU-1023", a) and rx(r"overdue", a))),
              "FMLA CERTIFICATION OVERDUE post for Meghan Cross", [R_CERT_SLACK, R_CERT], channel="hr-leave-requests",
              body=[(r"FMLA CERTIFICATION OVERDUE: Meghan Cross, CU-1023, Due: 04/07/2026, 1 day(\(s\)|s)? overdue",
                     "\"FMLA CERTIFICATION OVERDUE: Meghan Cross, CU-1023, Due: 04/07/2026, 1 day(s) overdue\"")]),
        TComm("trent_complete", "slack_post",
              lambda a: a.kind in ("slack_post", "slack_dm") and rx(r"ONBOARDING COMPLETE", a),
              "ONBOARDING COMPLETE post for William Trent", [R_ONB_DONE], channel="hr-onboarding",
              body=[(r"ONBOARDING COMPLETE: William Trent, CU-1022, 04/07/2026",
                     "\"ONBOARDING COMPLETE: William Trent, CU-1022, 04/07/2026\" (only Trent's onboarding is complete)")]),
        TComm("i9_not_overdue", "email",
              lambda a: (a.kind in ("slack_post", "slack_dm") and rx(r"I-9 OVERDUE", a))
              or (is_email(a) and rx(r"may not continue working|not been completed by the federal deadline", a)),
              "I-9 overdue escalation / Template 7", [R_I9_D3, R_I9_AFTER, R_T7, R_SLA, R_HOLIDAYS],
              forbidden="No I-9 is overdue: Tomás Salazar started 04/02/2026 and 04/03 and 04/06 are university "
                        "holidays, so today is Day 2 and the Section 2 deadline (Day 3) is 04/08/2026. Today only "
                        "Template 6 to the hiring manager applies; the other new hires' I-9s are recorded complete."),
        TComm("no_benefit_reminders", "email",
              lambda a: is_email(a) and rx(r"benefits enrollment deadline is|final notice that your benefits|"
                                           r"Benefits Enrollment Reminder|Benefits Final Notice", a),
              "Template 8/9 benefits reminder", [R_BEN15, R_BEN25, R_REPLIES, R_T8, R_T9],
              forbidden="No benefits reminder is due today: William Trent already received Templates 8 and 9 (per "
                        "Jira HR-7) and his window closed 04/02/2026 (Template 10 applies); Rafael Mendez (start "
                        "03/26), Priya Nair and Tomás Salazar (start 04/02) have not reached Day 15."),
        TComm("no_cross_denial", "email",
              lambda a: is_email(a) and CROSS in rec(a)
              and rx(r"do not meet the eligibility|Template 17|(leave|request) (has been|is|was) denied", a),
              "FMLA denial to Meghan Cross", [R_CERT_HUANG],
              forbidden="Do not deny Meghan Cross's FMLA leave: Patricia Huang determines denial vs extension. Send "
                        "only Template 18 to the employee."),
        TComm("no_t6_others", "email",
              lambda a: is_email(a) and rx(r"urgent reminder regarding the I-9", a) and not rx(r"Salazar", a),
              "Template 6 for an employee other than Tomás Salazar", [R_I9_D2],
              forbidden="Only Tomás Salazar's I-9 is outstanding; the other new hires' I-9s are recorded in "
                        "onboarding_checklist.xlsx."),
    ]


# ---- pre rules ----------------------------------------------------------------------------------------

def _no_dm(ctx: Context, a: Action):
    if a.kind == "slack_dm" or (a.kind == "slack_post" and world(ctx).dm_recipients(a)):
        return "Case-related Slack communication must go to the designated channel, not a direct message."
    return None


def _no_ticket(ctx: Context, a: Action):
    if a.kind == "jira_create":
        return ("Do not create Jira tickets: no SOP step in this situation directs a new ticket. Log actions as "
                "comments on the existing tickets (HR-7 Trent, HR-6 Salazar, HR-1 Cross).")
    return None


def _folders(ctx: Context, a: Action):
    if a.kind == "other_write" and re.search(r"(create|add|new)_?(folder|label)", a.tool, re.I):
        return f"Do not create new mail folders; use only {', '.join(FOLDERS)}."
    if a.kind != "email_move":
        return None
    folder = str(a.channel or "").strip()
    if folder not in FOLDERS and folder.upper() != "INBOX":
        return f"Folder \"{folder}\" is not an SOP folder; use exactly one of: {', '.join(FOLDERS)}."
    want = {"8": "Leave", "11": "General"}
    bad = [f"email {i} -> {want[i]}" for i in a.recipients if str(i) in want and folder != want[str(i)]]
    if bad:
        return ("Route the unread emails per Section 17: " + "; ".join(bad) +
                " (8 = Lisa Fontaine PTO inquiry -> Leave; 11 = out-of-scope facilities request -> General).")
    return None


# ---- completion rules ------------------------------------------------------------------------------------

BEN, CHK, ROSTER = r"benefits_enrollment", r"onboarding_checklist", r"employee_roster"


def _trent_default(ctx: Context):
    w = world(ctx)
    b = w.find(BEN, r"^Employee ID$", r"^Employee ID$", "CU-1022") or {}
    c = w.find(CHK, r"^Employee ID$", r"^Employee ID$", "CU-1022") or {}
    eff = dt.date(2026, 5, 1)
    refs = [R_BEN30, R_BEN_EFF, R_BEN_EX, R_BEN_EXT]
    yield (same(w.col(b, r"^Plan Elected"), "Default Enrollment"),
           "benefits_enrollment.xlsx CU-1022 (William Trent): set Plan Elected to \"Default Enrollment\" "
           f"(got \"{w.col(b, r'^Plan Elected')}\").", refs)
    yield (as_date(w.col(b, r"^Enrollment Date")) == eff,
           "benefits_enrollment.xlsx CU-1022: set Enrollment Date to the default effective date 05/01/2026 "
           f"(got \"{w.col(b, r'^Enrollment Date')}\").", refs)
    yield (as_date(w.col(c, r"^Benefits Enrolled")) == eff,
           "onboarding_checklist.xlsx CU-1022: set Benefits Enrolled to the effective date 05/01/2026 "
           f"(got \"{w.col(c, r'^Benefits Enrolled')}\").", refs)


def _trent_active(ctx: Context):
    w = world(ctx)
    r = w.find(ROSTER, r"^Employee ID$", r"^Employee ID$", "CU-1022") or {}
    yield (same(w.col(r, r"^Status$"), "Active"),
           "employee_roster.xlsx CU-1022 (William Trent): all checklist items are complete after default enrollment "
           f"- change Status from \"Onboarding\" to \"Active\" (got \"{w.col(r, r'^Status$')}\").", [R_ONB_DONE])


def _unrequested(ctx: Context):
    w = world(ctx)
    refs = [R_ONB, R_LEAVE, R_LT_RO]
    for name, label in ((BEN, "benefits_enrollment.xlsx"), (CHK, "onboarding_checklist.xlsx"),
                        (ROSTER, "employee_roster.xlsx")):
        init = w.rows(name, r"^Employee ID$", "initial")
        if not init:
            continue
        cur = {norm(w.col(r, r"^Employee ID$")): r for r in w.rows(name, r"^Employee ID$")}
        bad = []
        for r in init:
            eid = w.col(r, r"^Employee ID$")
            if eid == "CU-1022":
                continue
            now = cur.get(norm(eid))
            if now is None:
                bad.append(f"{eid} removed")
                continue
            diff = [k for k, v in r.items() if k != "__row__" and k and not same(now.get(k), None if v in ("", "None") else v)]
            if diff:
                bad.append(f"{eid} {', '.join(diff)}")
        ids = {norm(w.col(r, r"^Employee ID$")) for r in init}
        bad += [f"new row {w.col(r, r'^Employee ID$') or '?'}" for r in cur.values()
                if norm(w.col(r, r"^Employee ID$")) not in ids]
        yield (not bad, f"{label}: only William Trent's (CU-1022) row needs changes today; restore the other rows "
                        f"to their original values ({'; '.join(bad[:6])}).", refs)
    for name, label in ((r"leave_tracker", "leave_tracker.xlsx"), (r"recruiting_tracker", "recruiting_tracker.xlsx")):
        changed = w.changed_files() if w.initial else []
        hit = [k for k in changed if re.search(name, k, re.I)]
        yield (not hit, f"{label} was modified, but no SOP step in this situation updates it (PTO balances are "
                        "read-only; the overdue FMLA steps do not change leave_tracker). Restore it.", refs)


def _mail_filed(ctx: Context):
    w = world(ctx)
    moves = [(str(i), str(a.channel).strip()) for a in w.calls("email_move") for i in a.recipients]
    for eid, folder, what in (("8", "Leave", "Lisa Fontaine's PTO inquiry (email 8)"),
                              ("11", "General", "the out-of-scope facilities request (email 11)")):
        last = [f for i, f in moves if i == eid]
        yield (bool(last) and last[-1] == folder, f"Move {what} out of the inbox to the \"{folder}\" folder.",
               [R_FOLDERS, R_FOLDER_LEAVE if folder == "Leave" else R_FOLDER_GEN])


def _hr7_closed(ctx: Context):
    w = world(ctx)
    ok = any(norm(a.channel) == "hr-7" and re.search(r"Status\s*[-–—]\s*CLOSED", dashes(a.text) + str(a.args))
             for a in w.calls("jira_update"))
    yield (ok, "Close William Trent's onboarding ticket HR-7 by adding \"Status – CLOSED\" to the ticket "
               "description (jira update of HR-7).", [R_ONB_DONE, R_JIRA_DESC])


JIRA_LOG = (
    ("HR-7", r"TEMPLATE SENT.{0,20}Template 10\b", "TEMPLATE SENT — Template 10 to w.trent@crestwood.edu"),
    ("HR-7", r"SPREADSHEET UPDATED", "SPREADSHEET UPDATED — benefits_enrollment.xlsx — Plan Elected set to Default Enrollment"),
    ("HR-7", r"SLACK POSTED", "SLACK POSTED — hr-onboarding"),
    ("HR-6", r"TEMPLATE SENT.{0,20}Template 6\b", "TEMPLATE SENT — Template 6 to p.huang@crestwood.edu"),
    ("HR-1", r"TEMPLATE SENT.{0,20}Template 18\b", "TEMPLATE SENT — Template 18 to m.cross@crestwood.edu"),
    ("HR-1", r"SLACK POSTED", "SLACK POSTED — hr-leave-requests"),
)


def _jira_log(ctx: Context):
    w = world(ctx)
    comments = [(norm(a.channel), dashes(a.text)) for a in w.calls("jira_comment")]
    for key, pattern, example in JIRA_LOG:
        ok = any(k == norm(key) and re.search(pattern, t, re.I | re.S) for k, t in comments)
        yield (ok, f"Log the action as a comment on Jira {key} in the SOP format, e.g. "
                   f"\"{TODAY} 12:00pm [section] — {example}\" (one comment per discrete action).",
               [R_JIRA_COMMENT, R_JIRA_LINE, R_JIRA_ACTIONS])


RULES = [
    *comm_rules("comms", specs),
    *no_placeholders([R_TEMPLATES], literal=("[OUT OF SCOPE]",)),
    *pre_rule("slack.no_dm", _no_dm, [R_DM], "Post in the designated #hr- channel instead."),
    *pre_rule("jira.no_new_tickets", _no_ticket, [R_TICKETS], "Comment on the existing ticket instead."),
    *pre_rule("mail.folders", _folders, [R_FOLDERS, R_FOLDER_TBL, R_FOLDER_LEAVE, R_FOLDER_GEN],
              "Move the email to the SOP folder named above."),
    *state_rule("mail.filed", _mail_filed, "Move the email as listed."),
    *state_rule("wb.trent_default", _trent_default, "Update the cells as listed."),
    *state_rule("wb.trent_active", _trent_active, "Update the roster status."),
    *state_rule("wb.no_unrequested", _unrequested, "Restore the listed cells to their original values."),
    *state_rule("jira.hr7_closed", _hr7_closed, "Update the HR-7 description."),
    *state_rule("jira.comments", _jira_log, "Add the Jira comment(s)."),
]
