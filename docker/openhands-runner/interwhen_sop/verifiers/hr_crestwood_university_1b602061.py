"""Crestwood University HR - 1b602061 (today 04/13/2026 11:46am, coordinator back from sick leave).

Built blind from the SOP, instruction and seed data only. Situation:
- Inbox 34 (Diane Pham, CU-1020): FMLA request received 04/09/2026 (eligible: hired 06/01/2011 -> 178 months,
  2,080 hours) + ADA accommodation (wheelchair ramp). One consolidated reply (Templates 15 + 19, cert form
  attached, due 04/23/2026), forward to p.huang, Jira LEAVE-Pham-04092026 / LEAVE-Pham-ADA-04092026,
  #hr-leave-requests FMLA REQUEST post, calendar "FMLA Certification Due – Diane Pham" on 04/23/2026,
  nothing about the disability in Slack. P2 -> stays in Inbox, flagged.
- Inbox 35 (Jenna Park, CU-1006): ER complaint + payroll -> forward to m.voss and c.briggs, one consolidated
  reply (Templates 2 + 3), Jira ER-Park-04092026 / BENEFITS-Park-04092026, escalate to the HR Director.
- Inbox 36 (facilities follow-up): out of scope, already escalated 03/26 -> do not process (no reply).
- Deadline sweep: Tomás Salazar (CU-1026) I-9 - start 04/02, Easter Friday/Monday closed -> deadline
  04/08/2026, Template 6 sent 04/07, still missing -> Template 7 to p.huang (hiring manager per HR-6) cc
  n.ashford + j.whitfield and "I-9 OVERDUE" post in #hr-escalations. Everything else is either already
  actioned (Cross, Trent, Yee, Fontaine) or not due today (Nair/Salazar benefits Day 15 = 04/16).
"""

from __future__ import annotations

import dataclasses
import json
import re

from ..kit import (COMM_KINDS, Action, Comm, Context, World, comm_rules, dashes, forbid_writes, nh,
                   no_placeholders, norm, pre_rule, state_rule, world)

# ---- SOP references (section, paragraph prefix, label) -------------------------------------------
OUT_OF_SCOPE = ("1", "Do not deviate from the procedures", "1 Overview (out-of-scope requests)")
DATES = ("3.1", "All times in this document are Mountain", "3.1 Dates & Times")
EMAILS = ("3.2", "All employee internal email addresses follow", "3.2 Employee Email Addresses")
NO_DM = ("5", "All operational HR communications must use designated Slack", "5 Slack Channels")
CH_LEAVE = ("5", "#hr-leave-requests", "5 #hr-leave-requests")
CH_ESC = ("5", "#hr-escalations", "5 #hr-escalations")
SWEEP = ("8", "At the beginning of the day", "8 Triage (daily deadline sweep / already actioned)")
ER = ("8", "Step 2: If the request involves employee relations", "8 Step 2 (employee relations)")
PAY = ("8", "Step 3: If the request involves payroll", "8 Step 3 (payroll)")
NO_DUP = ("8", "Step 4: Check Jira for existing open tickets", "8 Step 4 (no duplicate Jira tickets)")
JIRA_NAME = ("8", "Format: [PREFIX]-[Employee Last Name]", "8 Jira Ticket Naming Convention")
JIRA_LEAVE = ("8", "Leave Management | LEAVE", "8 Jira prefix LEAVE")
JIRA_ER = ("8", "Employee Relations | ER", "8 Jira prefix ER")
JIRA_BEN = ("8", "Benefits & Payroll | BENEFITS", "8 Jira prefix BENEFITS")
MULTI = ("8", "Multi-topic requests", "8 Multi-topic requests")
REPLIES = ("8", "Replies to previous emails", "8 Replies to previous emails")
FWD = ("8", "Forwarded Emails:", "8 Forwarded Emails")
HOLIDAYS = ("10", "HR office hours are Monday", "10 Service Level Agreements (holidays)")
ONB_EXACT = ("11", "Onboarding begins when the HR office", "11 Onboarding (follow the steps exactly)")
I9_DEF = ("11.2", "Federal law requires that Section 1", "11.2 I-9 deadline")
I9_DAY2 = ("11.2", "Day 2 (if I-9 not received by 9AM)", "11.2 Day 2 (Template 6)")
I9_LATE = ("11.2", "After Day 3 (deadline at 9AM passed", "11.2 After Day 3 (Template 7)")
I9_POST = ("11.2", "n.ashford@crestwood.edu and j.whitfield@crestwood.edu. Post to #hr-escalations",
           "11.2 I-9 OVERDUE post")
BEN_D15 = ("11.3", "Day 15: If benefits_enrollment.xlsx", "11.3 Day 15 (Template 8)")
BEN_D25 = ("11.3", "Day 25: If still no enrollment", "11.3 Day 25 (Template 9)")
BEN_D30 = ("11.3", "Day 30 (Deadline)", "11.3 Day 30 (Template 10)")
ONB_DONE = ("11.4", "When all items in onboarding_checklist.xlsx", "11.4 Onboarding Completion")
LEAVE_EXACT = ("13", "Crestwood University provides leave", "13 Leave Management (follow the steps exactly)")
FMLA_ELIG = ("13.1", "FMLA entitles eligible employees", "13.1 FMLA eligibility")
FMLA_MONTHS = ("13.1", "Step 1: Open employee_roster.xlsx and confirm the employee", "13.1 Step 1 (months)")
FMLA_HOURS = ("13.1", "Step 2: In employee_roster.xlsx, locate", "13.1 Step 2 (hours)")
FMLA_OK = ("13.1", "Step 3: If BOTH conditions are met", "13.1 Step 3 (eligible)")
FMLA_T15 = ("13.1", "Step 4: Send Template 15", "13.1 Step 4 (Template 15)")
FMLA_JIRA = ("13.1", "Step 5: Create a Jira ticket: LEAVE-[Last Name]-[Date", "13.1 Step 5 (Jira)")
FMLA_POST = ("13.1", "Step 6: Post to #hr-leave-requests: FMLA REQUEST", "13.1 Step 6 (Slack)")
FMLA_CAL = ("13.1", "Step 7: Create a Calendar reminder", "13.1 Step 7 (calendar)")
CERT_T18 = ("13.1", "Send Template 18 (FMLA Certification Overdue)", "13.1 Template 18")
CERT_POST = ("13.1", "Post to #hr-leave-requests: FMLA CERTIFICATION OVERDUE", "13.1 overdue post")
CERT_MAIL = ("13.1", "Send an email to p.huang@crestwood.edu with the subject", "13.1 FMLA Deadline Passed email")
ADA_FWD = ("13.2", "Step 1: Forward the request to p.huang", "13.2 Step 1 (forward ADA request)")
ADA_JIRA = ("13.2", "Step 2: Create a Jira ticket: LEAVE-[Last Name]-ADA", "13.2 Step 2 (Jira)")
ADA_T19 = ("13.2", "Step 3: Send Template 19", "13.2 Step 3 (Template 19)")
ADA_PRIV = ("13.2", "Do not discuss the nature of the employee", "13.2 ADA confidentiality")
P1_ESC = ("16", "Any P1 issue.", "16 Escalations (P1)")
HARM_ESC = ("16", "Any situation involving potential harm", "16 Escalations (potential harm)")
READ = ("17", "Mark as read |", "17 Mark as read")
P12 = ("17", "P1 / P2 emails |", "17 P1/P2 emails")
FWD_ONLY = ("17", "Forwarded-only emails |", "17 Forwarded-only emails")
FOLDERS = ("17", "Folder names must match exactly", "17 Email Folders")
AS_WRITTEN = ("18", "Templates must be used as written", "18 Email Templates")
FILL = ("6", "The following Word document templates", "6 Document Templates (fill [bracketed] fields)")
JIRA_DESC = ("19", "When creating a Jira ticket, the ticket description starts empty",
             "19 Default Jira Ticket Description")
JIRA_UPD = ("19", "When the SOP instructs you to update a Jira ticket", "19 Jira ticket updates")
JIRA_COMMENT = ("19", "[Date and time] [SOP SUBHEADER]", "19 Default Jira Comment Format")
JIRA_ACTIONS = ("19", "The Action must be one of the following", "19 Jira comment actions")
SUBJ_NEW = ("19", "When composing a new email (not a reply or forward)", "19 Default Email Subject Line Format")
SUBJ_FMT = ("19", "[Template Name] — [Employee Last Name", "19 subject format")
SUBJ_KEEP = ("19", "When replying or forwarding, keep the existing subject", "19 keep subject on reply/forward")

# ---- task facts (seed data) ------------------------------------------------------------------------
PHAM, PARK, FAC = "34", "35", "36"
PHAM_EMAIL, PARK_EMAIL, HUANG, VOSS, BRIGGS = ("d.pham@crestwood.edu", "j.park@crestwood.edu",
                                               "p.huang@crestwood.edu", "m.voss@crestwood.edu",
                                               "c.briggs@crestwood.edu")
ASHFORD, WHITFIELD = "n.ashford@crestwood.edu", "j.whitfield@crestwood.edu"
SOP_ADDRESSES = {"hr@crestwood.edu", "hr-escalations@crestwood.edu", "communications@crestwood.edu",
                 "applications@crestwood.edu", ASHFORD, WHITFIELD, HUANG, VOSS, BRIGGS,
                 "d.okonkwo@crestwood.edu", "j.park@crestwood.edu"}
I9_POST_TEXT = "I-9 OVERDUE: Tomás Salazar, CU-1026, Start Date: 04/02/2026, Deadline: 04/08/2026"
FMLA_POST_TEXT = "FMLA REQUEST: Diane Pham, CU-1020, Eligible: YES, Certification Due: 04/23/2026, Jira: [Ticket ID]"
CAL_TITLE, CAL_DATE = "FMLA Certification Due – Diane Pham", "2026-04-23"
TICKETS = [("LEAVE-Pham-04092026", "FMLA request of Diane Pham (received 04/09/2026), assignee Patricia Huang",
            [FMLA_JIRA, JIRA_NAME, JIRA_LEAVE]),
           ("LEAVE-Pham-ADA-04092026", "ADA accommodation request of Diane Pham (received 04/09/2026)",
            [ADA_JIRA, MULTI]),
           ("ER-Park-04092026", "Jenna Park's employee-relations complaint (received 04/09/2026), assignee Marta Voss",
            [MULTI, JIRA_NAME, JIRA_ER]),
           ("BENEFITS-Park-04092026", "Jenna Park's payroll discrepancy (received 04/09/2026), assignee Calvin Briggs",
            [MULTI, JIRA_NAME, JIRA_BEN])]
# Employees whose case already has an open Jira ticket (seed): HR-6/HR-4/HR-5 onboarding, HR-1/HR-3 FMLA.
OPEN_TICKETS = {"salazar": "HR-6", "mendez": "HR-4", "nair": "HR-5", "cross": "HR-1", "yee": "HR-3"}
MULTI_PHRASE = (r"Since your message concerns multiple topics, I am addressing them here together",
                "the multi-topic opening line \"Since your message concerns multiple topics, I am addressing them "
                "here together\" after the greeting")
NEXT_MATTER = (r"Concerning your next matter:", "the separator line \"Concerning your next matter:\" between the "
                                               "two template bodies")
FOLDER_NAMES = ("Onboarding", "Offboarding", "Leave", "Performance", "Recruiting", "General")
JIRA_ACTION_WORDS = ("TEMPLATE SENT|FILE ATTACHED|EMAIL FORWARDED|SPREADSHEET UPDATED|CALENDAR EVENT CREATED|"
                     "CALENDAR EVENT REMOVED|SLACK POSTED|WAITING ON|CONFIRMED RECEIVED|TICKET UPDATED|ESCALATED|CLOSED")
EMAIL_KINDS = ("email_send", "email_draft")


# ---- helpers ---------------------------------------------------------------------------------------

def _seed_mail(w: World) -> dict[str, dict]:
    return {str(e.get("email_id")): e for e in w.seed_emails}


def _eid(a: Action) -> str:
    return str(a.args.get("email_id") or a.args.get("message_id") or a.args.get("id") or "")


def _is_reply(a: Action) -> bool:
    return "reply" in a.tool


def _is_forward(a: Action) -> bool:
    return "forward" in a.tool


def _eff(a: Action, w: World) -> Action:
    """Fill the implicit recipient / subject of a reply or forward from the seed email it refers to."""
    if a.kind not in EMAIL_KINDS:
        return a
    src = _seed_mail(w).get(_eid(a))
    if not src:
        return a
    changes = {}
    if _is_reply(a) and not a.recipients:
        changes["recipients"] = [str(src.get("from_addr") or "").lower()]
    if not a.subject and (_is_reply(a) or _is_forward(a)):
        changes["subject"] = ("Re: " if _is_reply(a) else "Fwd: ") + str(src.get("subject") or "")
    return dataclasses.replace(a, **changes) if changes else a


def _to(a: Action) -> set[str]:
    return {x.lower() for x in a.recipients + a.cc}


def _txt(a: Action) -> str:
    return dashes(f"{a.subject}\n{a.text}")


class _C(Comm):
    """Comm whose checks see replies/forwards with their implicit recipient filled in."""

    def problems(self, a: Action, w: World) -> list[str]:
        return super().problems(_eff(a, w), w)


def _spec(w: World, **kw) -> _C:
    return _C(**kw)


def _email_about(w: World, pred):
    def about(a: Action) -> bool:
        if a.kind not in EMAIL_KINDS:
            return False
        return bool(pred(_eff(a, w)))
    return about


def _slack_about(rx: str):
    def about(a: Action) -> bool:
        return a.kind in ("slack_post", "slack_dm") and bool(re.search(rx, dashes(a.text), re.I | re.S))
    return about


def _forward_of(w: World, eid: str, person: str, mention: str, sender: str):
    def pred(a: Action) -> bool:
        if person not in _to(a) or sender in _to(a):
            return False
        return (_is_forward(a) and _eid(a) == eid) or bool(re.search(mention, _txt(a), re.I))
    return _email_about(w, pred)


# ---- messages --------------------------------------------------------------------------------------

def _specs(ctx: Context) -> list[Comm]:
    w = world(ctx)
    t7 = _email_about(w, lambda a: re.search(r"Salazar", _txt(a), re.I) and re.search(r"I-?\s?9", _txt(a))
                      and not re.search(r"urgent reminder", _txt(a), re.I))
    return [
        # 11.2 After Day 3 - Template 7 + escalation post
        _spec(w, key="i9_t7", kind="email", about=t7, what="Template 7 (I-9 Deadline Passed) for Tomás Salazar",
              refs=[I9_LATE, I9_POST, I9_DEF, HOLIDAYS, P1_ESC, SUBJ_NEW], to=[HUANG], cc=[ASHFORD, WHITFIELD],
              exact_to=False, subject=r".+?\s?–\s?Salazar,\s*\(?CU-1026\)?\s*",
              subject_hint="Template 7 — Salazar, CU-1026",
              body=[(r"^\s*(Hi|Hello|Dear) Patricia\b", "the greeting \"Hi Patricia,\" (hiring manager per Jira HR-6)"),
                    (r"I-9 Employment Eligibility Verification for Tom[aá]s Salazar \(CU-1026\) has not been "
                     r"completed by the federal deadline",
                     "\"This is to inform you that the I-9 Employment Eligibility Verification for Tomás Salazar "
                     "(CU-1026) has not been completed by the federal deadline.\""),
                    (r"Tom[aá]s Salazar may not continue working until this requirement is fulfilled",
                     "\"Tomás Salazar may not continue working until this requirement is fulfilled. Please do not "
                     "assign work to this employee until further notice from the HR Office.\""),
                    (r"This matter has been escalated to the HR Director",
                     "\"This matter has been escalated to the HR Director.\"")]),
        _spec(w, key="i9_post", kind="slack_post",
              about=lambda a: a.kind in ("slack_post", "slack_dm") and bool(re.search(r"Salazar|CU-1026", a.text, re.I))
              and bool(re.search(r"I-?\s?9", a.text)),
              what="#hr-escalations I-9 OVERDUE notice for Tomás Salazar", refs=[I9_POST, I9_DEF, HOLIDAYS, CH_ESC],
              channel="hr-escalations",
              body=[(r"I-9 OVERDUE: Tom[aá]s Salazar, CU-1026, Start Date: 04/02/2026, Deadline: 04/08/2026",
                     f"exactly \"{I9_POST_TEXT}\" (deadline = 3rd business day; 04/03 and 04/06 are SOP holidays)")]),
        # 13.1 / 13.2 - Diane Pham (FMLA eligible + ADA): one consolidated reply
        _spec(w, key="pham_reply", kind="email", about=_email_about(w, lambda a: PHAM_EMAIL in _to(a)),
              what="one consolidated reply to Diane Pham with Template 15 (FMLA Eligibility Notice – Approved) and "
                   "Template 19 (ADA Request Acknowledged)",
              refs=[FMLA_T15, ADA_T19, FMLA_MONTHS, FMLA_HOURS, FMLA_OK, MULTI, AS_WRITTEN, DATES],
              to=[PHAM_EMAIL], exact_to=False,
              body=[(r"^\s*(Hi|Hello|Dear) Diane\b", "the greeting \"Hi Diane,\""), MULTI_PHRASE,
                    (r"Based on our records, you meet the eligibility requirements \(employed for 178 months; "
                     r"2,?080 hours worked in the preceding 12 months\)",
                     "\"Based on our records, you meet the eligibility requirements (employed for 178 months; 2,080 "
                     "hours worked in the preceding 12 months).\" (hired 06/01/2011)"),
                    (r"within 15 calendar days of your request \(due by 04/23/2026\)",
                     "\"...return the attached Medical Certification Form within 15 calendar days of your request "
                     "(due by 04/23/2026)...\" (request received 04/09/2026 = day 1)"),
                    NEXT_MATTER,
                    (r"Thank you for submitting your request for a workplace accommodation",
                     "the Template 19 body \"Thank you for submitting your request for a workplace accommodation. "
                     "Your request has been received and forwarded to our Benefits & Leave Manager...\"")],
              attach=[(r"fmla_medical_certification\.pdf", "fmla_medical_certification.pdf")]),
        _spec(w, key="pham_fwd", kind="forward",
              about=_forward_of(w, PHAM, HUANG, r"Pham|CU-1020|accommodat|wheelchair|ramp", PHAM_EMAIL),
              what="forward of Diane Pham's accommodation request email to p.huang@crestwood.edu",
              refs=[ADA_FWD, FWD, ADA_PRIV], to=[HUANG], exact_to=False),
        _spec(w, key="pham_post", kind="slack_post", about=_slack_about(r"Pham|CU-1020"),
              what="#hr-leave-requests FMLA REQUEST notice for Diane Pham", refs=[FMLA_POST, CH_LEAVE, ADA_PRIV],
              channel="hr-leave-requests",
              body=[(r"FMLA REQUEST: Diane Pham, CU-1020, Eligible: YES, Certification Due: 04/23/2026, Jira: \S+",
                     f"exactly \"{FMLA_POST_TEXT}\" (Ticket ID of LEAVE-Pham-04092026)")]),
        # 8 Steps 2-3 - Jenna Park (employee relations + payroll)
        _spec(w, key="park_voss", kind="forward",
              about=_forward_of(w, PARK, VOSS, r"Park|CU-1006|Getting Fed Up", PARK_EMAIL),
              what="forward of Jenna Park's email (\"Getting Fed Up\") to m.voss@crestwood.edu",
              refs=[ER, FWD], to=[VOSS], exact_to=False),
        _spec(w, key="park_briggs", kind="forward",
              about=_forward_of(w, PARK, BRIGGS, r"Park|CU-1006|Getting Fed Up", PARK_EMAIL),
              what="forward of Jenna Park's email (\"Getting Fed Up\") to c.briggs@crestwood.edu",
              refs=[PAY, FWD], to=[BRIGGS], exact_to=False),
        _spec(w, key="park_reply", kind="email",
              about=_email_about(w, lambda a: PARK_EMAIL in _to(a) and not _is_forward(a)),
              what="one consolidated reply to Jenna Park with Template 2 (Employee Relations Referral) and "
                   "Template 3 (Payroll Referral)",
              refs=[ER, PAY, MULTI, AS_WRITTEN], to=[PARK_EMAIL], exact_to=False,
              body=[(r"^\s*(Hi|Hello|Dear) Jenna\b", "the greeting \"Hi Jenna,\""), MULTI_PHRASE,
                    (r"Your message has been forwarded to our Employee Relations Specialist, who will follow up with "
                     r"you directly",
                     "the Template 2 body \"Thank you for contacting us. Your message has been forwarded to our "
                     "Employee Relations Specialist, who will follow up with you directly. Please allow 2 business "
                     "days for initial contact.\""),
                    NEXT_MATTER,
                    (r"please contact our Payroll Liaison, Calvin Briggs, directly at c\.briggs@crestwood\.edu",
                     "the Template 3 body \"Thank you for reaching out. For all payroll and compensation questions, "
                     "please contact our Payroll Liaison, Calvin Briggs, directly at c.briggs@crestwood.edu. Your "
                     "message has been forwarded to him.\"")],
              banned=[(r"apolog", "Templates must be used as written - do not add an apology or other commentary.")]),
        # Out-of-scope facilities follow-up: do not process further
        _spec(w, key="facilities", kind="email", about=_email_about(w, lambda a: "facilities@crestwood.edu" in _to(a)),
              what="reply to Facilities about the room 214 light bulb", refs=[OUT_OF_SCOPE, REPLIES],
              forbidden="Maintenance requests are out of scope: do not process further (it was already escalated "
                        "in #hr-general on 03/26). Do not reply to or email Facilities."),
        # Already actioned before today - do not repeat
        _spec(w, key="t6_again", kind="email",
              about=_email_about(w, lambda a: re.search(r"Salazar", _txt(a)) and re.search(r"urgent reminder", _txt(a), re.I)),
              what="Template 6 (I-9 Urgent Reminder) for Tomás Salazar", refs=[I9_DAY2, SWEEP],
              forbidden="Template 6 was already sent on 04/07/2026; the deadline (04/08/2026) has passed - send "
                        "Template 7 instead."),
        _spec(w, key="t18_again", kind="email",
              about=_email_about(w, lambda a: "m.cross@crestwood.edu" in _to(a)
                                 and re.search(r"certification", _txt(a), re.I)),
              what="Template 18 (FMLA Certification Overdue) to Meghan Cross", refs=[CERT_T18, SWEEP],
              forbidden="Already actioned on 04/07/2026 (Template 18 sent); Patricia Huang now decides on denial or "
                        "extension."),
        _spec(w, key="cert_mail_again", kind="email",
              about=_email_about(w, lambda a: re.search(r"FMLA Deadline Passed", _txt(a), re.I)
                                 and re.search(r"CU-1023|Cross", _txt(a), re.I)),
              what="\"FMLA Deadline Passed - CU-1023\" email", refs=[CERT_MAIL, SWEEP],
              forbidden="Already actioned on 04/07/2026 (email to p.huang sent)."),
        _spec(w, key="cert_post_again", kind="slack_post", about=_slack_about(r"CERTIFICATION OVERDUE.*Cross"),
              what="FMLA CERTIFICATION OVERDUE post for Meghan Cross", refs=[CERT_POST, SWEEP],
              forbidden="Already posted in #hr-leave-requests on 04/11/2026."),
        _spec(w, key="trent_again", kind="email",
              about=_email_about(w, lambda a: _to(a) & {"w.trent@crestwood.edu", "william.trent.work@gmail.com"}
                                 and re.search(r"enrol", _txt(a), re.I)),
              what="benefits enrollment email to William Trent", refs=[BEN_D30, SWEEP],
              forbidden="Already actioned: default enrollment recorded and Template 10 sent on 04/07/2026."),
        _spec(w, key="benefits_early", kind="email",
              about=_email_about(w, lambda a: _to(a) & {"p.nair@crestwood.edu", "pnair.bio@gmail.com",
                                                        "t.salazar@crestwood.edu", "tomas.salazar.co@protonmail.com"}
                                 and re.search(r"benefits enrollment|enrollment deadline", _txt(a), re.I)),
              what="benefits enrollment reminder to Priya Nair / Tomás Salazar", refs=[BEN_D15, BEN_D25, ONB_EXACT],
              forbidden="Not due: both started 04/02/2026, so Day 15 (Template 8) is 04/16/2026 and Day 25 is "
                        "04/26/2026. Send nothing about benefits today."),
        _spec(w, key="onb_complete", kind="slack_post", about=_slack_about(r"ONBOARDING COMPLETE"),
              what="ONBOARDING COMPLETE post", refs=[ONB_DONE, SWEEP],
              forbidden="No open onboarding is complete (Salazar's I-9 and Nair/Mendez/Salazar benefits are "
                        "outstanding; Trent was already posted on 04/07/2026)."),
        _spec(w, key="new_hire_again", kind="slack_post", about=_slack_about(r"^\s*NEW HIRE:"),
              what="NEW HIRE post", refs=[SWEEP],
              forbidden="Every new hire was already posted in #hr-onboarding; there is no new hire notification "
                        "to process."),
    ]


# ---- pre rules -------------------------------------------------------------------------------------

def _fwd_commentary(ctx: Context, a: Action):
    if a.kind not in EMAIL_KINDS or not _is_forward(a):
        return None
    extra = [k for k in ("body", "body_text", "note", "message", "comment", "additional_message", "text")
             if str(a.args.get(k) or "").strip()]
    return (f"Forwarded emails must not include extra commentary (remove the '{extra[0]}' text and forward the "
            "email as is).") if extra else None


ADA_WORDS = r"wheelchair|\bramps?\b|accessible entrance|accommodat|disabilit|(?<![-\w])ADA(?![-\w])"


def _ada_privacy(ctx: Context, a: Action):
    w = world(ctx)
    if a.kind in ("slack_post", "slack_dm"):
        t = a.text
        if re.search(r"wheelchair|\bramps?\b|accessible entrance", t, re.I) or (
                re.search(r"Pham|Diane|CU-1020", t, re.I) and re.search(ADA_WORDS, t, re.I)):
            return ("Do not discuss Diane Pham's disability or accommodation in Slack - the ADA request is handled "
                    "by email only (forward to p.huang@crestwood.edu). The #hr-leave-requests post is only "
                    f"\"{FMLA_POST_TEXT}\".")
        return None
    if a.kind not in EMAIL_KINDS:
        return None
    e = _eff(a, w)
    allowed = {HUANG, ASHFORD, PHAM_EMAIL}
    about_pham = (_is_forward(a) and _eid(a) == PHAM) or re.search(r"wheelchair|\bramps?\b", _txt(e), re.I) or (
        re.search(r"Pham|Diane|CU-1020", _txt(e), re.I) and re.search(ADA_WORDS, _txt(e), re.I))
    extra = sorted(_to(e) - allowed)
    if about_pham and extra:
        return (f"Diane Pham's accommodation request may only go to Patricia Huang and Nicole Ashford (and the "
                f"employee) - remove {', '.join(extra)}.")
    return None


def _no_dm(ctx: Context, a: Action):
    if a.kind == "slack_dm" or (a.kind == "slack_post" and world(ctx).dm_recipients(a)):
        return "Case-related communication must use the designated Slack channels, not direct messages."
    return None


def _known_addresses(ctx: Context) -> set[str]:
    def build():
        w = world(ctx)
        out = set(SOP_ADDRESSES)
        out |= {norm(w.col(r, r"^Email$")) for r in w.rows(r"employee_roster", r"Employee ID", "initial")}
        for e in w.seed_emails:
            for k in ("from_addr", "to_addr", "cc_addr", "bcc_addr"):
                v = e.get(k)
                for x in (v if isinstance(v, list) else [v]):
                    out |= set(re.findall(r"[\w.+-]+@[\w.-]+\w", str(x or "").lower()))
        return out
    return ctx.memo("t.addresses", build)


def _addresses(ctx: Context, a: Action):
    if a.kind not in EMAIL_KINDS:
        return None
    bad = sorted(x for x in _to(a) if x.endswith("@crestwood.edu") and x not in _known_addresses(ctx))
    if bad:
        return (f"{', '.join(bad)} is not a Crestwood address on record - look the employee's address up in the "
                "Email column of employee_roster.xlsx (e.g. Tomás Salazar = t.salazar@crestwood.edu).")
    return None


def _jira_made(w: World) -> list[str]:
    """Summaries of Jira issues actually created (the result carries the new issue key)."""
    return [norm(dashes(e.action.subject)) for e in w.state.executed
            if e.action.kind == "jira_create" and w.ok(e) and re.search(r'"key"\s*:', e.result or "")]


def _jira_dup(ctx: Context, a: Action):
    if a.kind != "jira_create":
        return None
    w = world(ctx)
    summ = dashes(a.subject)
    name = re.search(r"Employee Name:\s*(.+)", a.text or "")
    who = f"{summ} {name.group(1) if name else ''}".lower()
    for last, key in OPEN_TICKETS.items():
        if re.search(rf"\b{last}\b", who):
            return (f"An open Jira ticket already exists for this employee ({key}) - add the information as a "
                    f"comment on {key} instead of creating a new ticket.")
    if re.search(r"light bulb|lightbulb|facilities|room 214|rm 214|out of scope", who, re.I):
        return ("The facilities light-bulb email is out of scope and a follow-up to an already escalated email - "
                "do not open a Jira ticket for it.")
    if summ and norm(summ) in _jira_made(w):
        return f"A Jira ticket named \"{summ}\" was already created - do not create a duplicate."
    return None


DESC_LINE = re.compile(r"(Employee Name|Employee ID|Assignee):\s*\S.*|Priority:\s*P[1-4]\b.*|"
                       r"Deadline:\s*\d{2}/\d{2}/\d{4}\s*|Status\s*[:–—-]\s*\S.*", re.I)


def _jira_desc(ctx: Context, a: Action):
    if a.kind not in ("jira_create", "jira_update") or not (a.text or "").strip():
        return None
    bad = [ln.strip() for ln in a.text.splitlines() if ln.strip() and not DESC_LINE.fullmatch(ln.strip())]
    if bad:
        return ("A Jira ticket description holds only the SOP fields, one per line, in the exact format "
                "\"Employee Name: [Full Name]\", \"Employee ID: [ID]\", \"Assignee: [Full Name]\", "
                "\"Priority: [P1/P2/P3/P4]\", \"Deadline: [MM/DD/YYYY]\", \"Status: [value]\" - remove "
                f"\"{bad[0][:90]}\" (log actions as Jira comments instead).")
    return None


COMMENT_LINE = re.compile(r"\[?\d{2}/\d{2}/\d{4},?\s+\d{1,2}:\d{2}\s?(?:am|pm)\]?\s+\S.*?\s[—–-]+\s(?:"
                          + JIRA_ACTION_WORDS + r")\s[—–-]+\s\S.*", re.I)


def _jira_comment(ctx: Context, a: Action):
    if a.kind != "jira_comment":
        return None
    bad = [ln.strip() for ln in (a.text or "").splitlines() if ln.strip() and not COMMENT_LINE.fullmatch(ln.strip())]
    if bad:
        return ("Each Jira comment line must follow \"[MM/DD/YYYY HH:MMam/pm] [SOP SUBHEADER] — [Action] — "
                "[Object]\" with Action one of TEMPLATE SENT, FILE ATTACHED, EMAIL FORWARDED, SPREADSHEET UPDATED, "
                "CALENDAR EVENT CREATED, CALENDAR EVENT REMOVED, SLACK POSTED, WAITING ON, CONFIRMED RECEIVED, "
                "TICKET UPDATED, ESCALATED, CLOSED (e.g. \"04/13/2026 11:46am [11.2] — TEMPLATE SENT — Template 7 "
                f"to p.huang@crestwood.edu\"). Fix: \"{bad[0][:90]}\".")
    return None


def _folders(ctx: Context, a: Action):
    if a.kind == "other_write" and re.search(r"folder|label", a.tool, re.I) and re.search(r"create|add|new", a.tool, re.I):
        return "Do not create new email folders - use only " + ", ".join(FOLDER_NAMES) + "."
    if a.kind != "email_move":
        return None
    target = a.channel.strip()
    if target.lower() != "inbox" and target not in FOLDER_NAMES:
        return f"Folder \"{target}\" does not exist - use exactly one of: {', '.join(FOLDER_NAMES)}."
    ids = set(a.recipients)
    if PHAM in ids and target.lower() != "inbox":
        return ("Diane Pham's FMLA/ADA email is P2 and the case is not resolved - leave it in the Inbox (flagged "
                "important); do not move it to a folder yet.")
    if PARK in ids and target.lower() != "inbox" and target != "General":
        return "Jenna Park's email stays in the Inbox (P1/P2, flagged) or, as a forwarded-only email, goes to General."
    return None


def _dates(ctx: Context, a: Action):
    if a.kind not in COMM_KINDS or _is_forward(a):
        return None
    m = re.search(r"\b20\d\d-\d\d-\d\d\b", a.text or "")
    return f"Write dates as MM/DD/YYYY in correspondence (got \"{m.group(0)}\")." if m else None


def _subjects(ctx: Context, a: Action):
    if a.kind not in EMAIL_KINDS:
        return None
    w = world(ctx)
    src = _seed_mail(w).get(_eid(a))
    if (_is_reply(a) or _is_forward(a)) and src and a.args.get("subject"):
        orig = str(src.get("subject") or "")
        if norm(orig) not in norm(a.args.get("subject")):
            return f"When replying or forwarding keep the existing subject line (\"{orig}\")."
        return None
    if _is_reply(a) or _is_forward(a):
        return None
    to = _to(a)
    for who, last, eid in ((PHAM_EMAIL, "Pham", "CU-1020"), (PARK_EMAIL, "Park", "CU-1006")):
        if who in to and not re.fullmatch(rf".+?\s?–\s?{last},\s*\(?{eid}\)?\s*", dashes(a.subject), re.I):
            return (f"A new email's subject follows \"[Template Name] — [Last Name], [Employee ID]\" - end it with "
                    f"\"— {last}, {eid}\" (got \"{a.subject}\"), or reply to the original email instead.")
    return None


def _calendar(ctx: Context, a: Action):
    if a.kind not in ("calendar_create", "calendar_update"):
        return None
    if not re.search(r"FMLA Certification Due", a.subject, re.I) or not re.search(r"Pham", a.subject, re.I):
        return None
    when = json.dumps(a.args.get("start") or a.args.get("start_time") or a.args.get("date") or "")
    if a.kind == "calendar_create" and CAL_DATE not in when:
        return (f"\"{CAL_TITLE}\" goes on the certification deadline 04/23/2026 (15 calendar days counting "
                "04/09/2026 as day 1).")
    return None


# ---- completion rules ------------------------------------------------------------------------------

def _ticket_checks(ctx: Context):
    w = world(ctx)
    made = _jira_made(w)
    for name, what, refs in TICKETS:
        ok = any(norm(name) in m for m in made)
        yield ok, f"Create the Jira ticket named \"{name}\" ({what}).", refs


def _calendar_checks(ctx: Context):
    w = world(ctx)
    ok = any(re.fullmatch(r"FMLA Certification Due\s*–\s*Diane Pham", dashes(a.subject).strip(), re.I)
             and CAL_DATE in json.dumps(a.args.get("start") or a.args.get("start_time") or a.args.get("date") or "")
             for a in w.calls("calendar_create", "calendar_update"))
    yield ok, f"Create the calendar reminder \"{CAL_TITLE}\" on 04/23/2026.", [FMLA_CAL]


def _marks(w: World, flag: str) -> set[str]:
    out: set[str] = set()
    for a in w.calls("email_mark"):
        if a.args.get(flag) in (True, "true", "True", 1):
            out |= set(a.recipients)
    return out


def _housekeeping_checks(ctx: Context):
    w = world(ctx)
    read = _marks(w, "is_read")
    for eid, who in ((PHAM, "Diane Pham's \"Upcoming Surgery in June\""), (PARK, "Jenna Park's \"Getting Fed Up\""),
                     (FAC, "Facilities' \"Re: HR office light bulb out\"")):
        yield eid in read, f"Mark {who} email (id {eid}) as read.", [READ]
    yield PHAM in _marks(w, "is_important"), (
        f"Flag Diane Pham's email (id {PHAM}) as important and leave it in the Inbox (P2: FMLA request)."), [P12]


def _escalation_checks(ctx: Context):
    w = world(ctx)
    ok = any(re.search(r"Park|CU-1006|Getting Fed Up", a.text, re.I) for a in w.posts_in("hr-escalations"))
    for a in w.comms():
        e = _eff(a, w)
        if e.kind == "email_send" and _to(e) & {ASHFORD, "hr-escalations@crestwood.edu"} and (
                (_is_forward(a) and _eid(a) == PARK) or re.search(r"Park|CU-1006|Getting Fed Up", _txt(e), re.I)):
            ok = True
    yield ok, ("Escalate Jenna Park's complaint (reported harassment by her supervisor, does not feel safe) to the "
               "HR Director: post in #hr-escalations naming Jenna Park, CU-1006 and the subject \"Getting Fed Up\" "
               "(or forward the email to n.ashford@crestwood.edu)."), [HARM_ESC, P1_ESC, CH_ESC]


CHECKLIST_FREE = {"CU-1021": ("NOTES",), "CU-1025": ("Benefits Enrolled", "NOTES"),
                  "CU-1026": ("Benefits Enrolled", "NOTES")}


def _workbook_checks(ctx: Context):
    w = world(ctx)
    changed = w.changed_files(r"onboarding_checklist")
    yield not changed, (f"{', '.join(changed)} must stay unchanged - no SOP step today updates it. Restore the "
                        "original values."), [LEAVE_EXACT, ONB_EXACT, SWEEP]
    init = {w.col(r, r"^Employee ID$"): r for r in w.rows(r"onboarding_checklist", r"Employee ID", "initial")}
    cur = {w.col(r, r"^Employee ID$"): r for r in w.rows(r"onboarding_checklist", r"Employee ID", "current")}
    if not init:
        return
    probs = [f"new row {k}" for k in cur if k not in init] + [f"row {k} removed" for k in init if k not in cur]
    for k, r in init.items():
        c = cur.get(k)
        if c is None:
            continue
        for col, v in r.items():
            if col == "__row__" or col in CHECKLIST_FREE.get(k, ()):
                continue
            if nh(c.get(col, "")) != nh(v):
                probs.append(f"{k} {col} changed from \"{v}\" to \"{c.get(col, '')}\"")
    yield not probs, ("onboarding_checklist.xlsx has changes no SOP step calls for today: " + "; ".join(probs[:4])
                      + ". Restore them (e.g. Tomás Salazar's I-9 has NOT been received)."), [ONB_EXACT, SWEEP]


RULES = (
    comm_rules("comms", _specs)
    + no_placeholders([AS_WRITTEN, FILL], literal=["[OUT OF SCOPE]"])
    + pre_rule("comms.forward_as_is", _fwd_commentary, [FWD])
    + pre_rule("comms.ada_privacy", _ada_privacy, [ADA_PRIV])
    + pre_rule("comms.no_dm", _no_dm, [NO_DM])
    + pre_rule("comms.addresses", _addresses, [EMAILS])
    + pre_rule("comms.date_format", _dates, [DATES])
    + pre_rule("comms.subject", _subjects, [SUBJ_NEW, SUBJ_FMT, SUBJ_KEEP])
    + pre_rule("jira.no_duplicate", _jira_dup, [NO_DUP, REPLIES, OUT_OF_SCOPE])
    + pre_rule("jira.description", _jira_desc, [JIRA_DESC, JIRA_UPD])
    + pre_rule("jira.comment", _jira_comment, [JIRA_COMMENT, JIRA_ACTIONS])
    + pre_rule("mail.folders", _folders, [FOLDERS, P12, FWD_ONLY])
    + pre_rule("calendar.fmla_due", _calendar, [FMLA_CAL])
    + forbid_writes("files.no_unrequested_writes",
                    r"employee_roster|benefits_enrollment|leave_tracker|recruiting_tracker",
                    "no SOP step for today's cases updates this workbook (Pham's FMLA is not recorded until the "
                    "certification arrives; I-9 and complaints change no workbook).",
                    [LEAVE_EXACT, ONB_EXACT, SWEEP])
    + state_rule("jira.tickets", _ticket_checks, "Create the missing Jira ticket(s).")
    + state_rule("calendar.fmla_reminder", _calendar_checks, "Create the calendar reminder.")
    + state_rule("mail.housekeeping", _housekeeping_checks, "Use google_mail mark tools as listed.")
    + state_rule("escalation.park", _escalation_checks, "Escalate as listed.")
    + state_rule("files.unchanged", _workbook_checks, "Restore the workbook.")
)
