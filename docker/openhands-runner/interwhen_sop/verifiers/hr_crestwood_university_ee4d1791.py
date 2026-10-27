"""SOP verifiers for hr_crestwood_university_ee4d1791 (blind build; SOP + seed data only).

Today is 04/12/2026. Unread emails from today:
  #1 Maria Torres (E-1001, m.torres@) FMLA request 06/29-08/07 with medical_certification_torres.pdf attached.
     Hire 02/10/2024 -> 26 months; 1,420 hours (>= 1,250) -> ELIGIBLE (12.1 Steps 1-3).
     Template 15 (cert due 04/12 + 15 days = 04/27/2026), Jira LEAVE-Torres-04122026 (Patricia Huang),
     Slack FMLA REQUEST in #hr-leave-requests; certification already received -> forward to p.huang and set
     leave_tracker dates 06/29/2026-08/07/2026, status "Approved – Pending Certification Review" (Step 8).
  #2 Jenna Park confirms David Kim (E-1002) access revoked -> reply to existing case OFFBOARD-1: update the
     ticket (11.4 Step 2), no new ticket, no re-sent templates. COBRA (04/07), final pay (03/20) and the declined
     exit interview (03/23) are already done -> offboarding complete (11.6): roster Separated / 04/06/2026 /
     Voluntary Resignation and Slack OFFBOARDING COMPLETE in #hr-offboarding.
  Housekeeping: mark #1/#2 read, move #1 -> Leave, #2 -> Offboarding.
  #3 James Okafor's resignation is dated today but already read: not required; only checked for correctness if
     the agent chooses to process it.
"""

from __future__ import annotations

import re

from ..kit import (COMM_KINDS, Comm, Context, Ref, comm_rules, dashes, no_placeholders, norm, pre_rule, state_rule,
                   text_of, world)

TORRES = "m.torres@crestwood.edu"
MICHAEL = "m.p.torres@crestwood.edu"
HUANG = "p.huang@crestwood.edu"
JPARK = "j.park@crestwood.edu"
BRIGGS = "c.briggs@crestwood.edu"
OKAFOR = "j.okafor@crestwood.edu"
CERT_DUE = "04/27/2026"
LEAVE_SUMMARY = "LEAVE-Torres-04122026"
LEAVE_START, LEAVE_END = "06/29/2026", "08/07/2026"
LEAVE_STATUS = "Approved – Pending Certification Review"
KIM_TICKETS = {"OFFBOARD-1", "OFFBOARD-KIM-04062026"}
OKAFOR_SUMMARY = "OFFBOARD-Okafor-05062026"
CAL_TITLE = "FMLA Certification Due – Maria Torres"
FOLDERS = ("Onboarding", "Offboarding", "Leave", "Performance", "Recruiting", "General")
EXPECTED_FOLDER = {"1": "Leave", "2": "Offboarding", "3": "Offboarding"}

# --- SOP references (section, paragraph prefix, label) ---
R_DEVIATE: Ref = ("1", "Do not deviate from the procedures", "1 Overview")
R_DATES: Ref = ("3.1", "All times in this document", "3.1 Dates")
R_DM: Ref = ("5", "All operational HR communications must use designated Slack channels.", "5 Slack channels")
R_CH_LEAVE: Ref = ("5", "#hr-leave-requests | FMLA requests", "5 #hr-leave-requests")
R_CH_OFF: Ref = ("5", "#hr-offboarding | Resignations", "5 #hr-offboarding")
R_PTO_RO: Ref = ("6", "leave_tracker.xlsx | FMLA eligibility data", "6 leave_tracker.xlsx")
R_TRIAGE5: Ref = ("8", "Step 5: Check Jira for existing open tickets", "8 Step 5")
R_TRIAGE6: Ref = ("8", "Step 6: Create a Jira ticket.", "8 Step 6")
R_NAMING: Ref = ("8", "Format: [PREFIX]-[Employee Last Name]-[DATE in MMDDYYYY]", "8 Jira naming")
R_ROUTE_LEAVE: Ref = ("8", "Leave Management | LEAVE | Patricia Huang", "8 routing table")
R_REPLY: Ref = ("8", "Replies to previous emails:", "8 Replies to previous emails")
R_OFF_JIRA: Ref = ("11.1", "Step 2: Create a Jira ticket: OFFBOARD-", "11.1 Step 2")
R_OFF_SEP: Ref = ("11.1", "Step 3: Post to #hr-offboarding: SEPARATION", "11.1 Step 3")
R_FINALPAY: Ref = ("11.3", "Step 2: Email c.briggs@crestwood.edu", "11.3 Step 2")
R_FINALPAY_T: Ref = ("18", "Separation Type: [Voluntary Resignation", "Template 12")
R_REVOKE: Ref = ("11.4", "Step 1: Email j.park@crestwood.edu using Template 13", "11.4 Step 1")
R_REVOKE_DONE: Ref = ("11.4", "Step 2: Update the Jira ticket when IT confirms revocation.", "11.4 Step 2")
R_EXIT: Ref = ("11.5", "Step 1: Send Template 14", "11.5 Step 1")
R_OFF_DONE: Ref = ("11.6", "When all offboarding steps are complete", "11.6 Offboarding Completion")
R_OFF_ROSTER: Ref = ("11.6", "Update employee_roster.xlsx: change status to", "11.6 roster update")
R_OFF_SLACK: Ref = ("11.6", "Post to #hr-offboarding: OFFBOARDING COMPLETE", "11.6 Slack post")
R_ELIG1: Ref = ("12.1", "Step 1: Open employee_roster.xlsx", "12.1 Step 1")
R_ELIG2: Ref = ("12.1", "Step 2: In employee_roster.xlsx", "12.1 Step 2")
R_ELIG3: Ref = ("12.1", "Step 3: If BOTH conditions", "12.1 Step 3")
R_T15: Ref = ("12.1", "Step 4: Send Template 15", "12.1 Step 4")
R_T17: Ref = ("12.1", "Step 4: Send Template 17", "12.1 Step 4 (ineligible)")
R_LEAVE_JIRA: Ref = ("12.1", "Step 5: Create a Jira ticket: LEAVE-", "12.1 Step 5")
R_LEAVE_SLACK: Ref = ("12.1", "Step 6: Post to #hr-leave-requests", "12.1 Step 6")
R_LEAVE_CAL: Ref = ("12.1", "Step 7: Create a Calendar reminder", "12.1 Step 7")
R_CERT: Ref = ("12.1", "Step 8: When medical certification is received", "12.1 Step 8")
R_STEP9: Ref = ("12.1", "Step 9: After Patricia approves", "12.1 Step 9")
R_MARK: Ref = ("16", "Mark as read | Every processed email", "16 Mark as read")
R_MOVE: Ref = ("16", "Move to topic folder |", "16 Move to topic folder")
R_FOLDERS: Ref = ("16", "Folder names must match exactly", "16 Email folders")
R_F_LEAVE: Ref = ("16", "Leave | FMLA, ADA", "16 Leave folder")
R_F_OFF: Ref = ("16", "Offboarding | All offboarding-related", "16 Offboarding folder")
R_TEMPLATES: Ref = ("18", "Templates must be used as written.", "18 Email Templates")
R_T15_TEXT: Ref = ("18", "We have reviewed your request for leave under the Family and Medical Leave Act (FMLA). Based",
                   "Template 15")
R_T15_DUE: Ref = ("18", "To proceed, please complete and return the Medical Certification Form", "Template 15")
R_DESC: Ref = ("19", "When creating a Jira ticket, the ticket description starts empty.", "19 Jira description")
R_DESC_NAME: Ref = ("19", "Employee Name | Employee Name: [Full Name]", "19 Jira description")
R_DESC_ID: Ref = ("19", "Employee ID | Employee ID: [ID]", "19 Jira description")
R_DESC_ASG: Ref = ("19", "Assignee | Assignee: [Full Name]", "19 Jira description")
R_DESC_DL: Ref = ("19", "Deadline | Deadline: [MM/DD/YYYY]", "19 Jira description")
R_CMT_UPD: Ref = ("19", "When the SOP instructs you to update a Jira ticket", "19 Jira update")
R_CMT_FMT: Ref = ("19", "[Date and time] [SOP SUBHEADER]", "19 Jira comment format")
R_CMT_ACT: Ref = ("19", "The Action must be one of the following:", "19 Jira comment actions")
R_SUBJ_NEW: Ref = ("19", "When composing a new email using a Template", "19 Subject line format")
R_SUBJ: Ref = ("19", "[Template Name]", "19 Subject line format")
R_REPLY_SUBJ: Ref = ("19", "When replying using the email tool", "19 Reply subject")

ACTIONS = ("TEMPLATE SENT", "FILE ATTACHED", "EMAIL FORWARDED", "SPREADSHEET UPDATED", "CALENDAR EVENT CREATED",
           "CALENDAR EVENT REMOVED", "SLACK POSTED", "WAITING ON", "CONFIRMED RECEIVED", "TICKET UPDATED",
           "ESCALATED", "CLOSED")
COMMENT_RX = re.compile(r"\s*\d{2}/\d{2}/\d{4},?\s+\d{1,2}:\d{2}\s?(?:[ap]m)?\s+\[[^\]]+\]\s+[–-]{1,2}\s+(?:"
                        + "|".join(ACTIONS) + r")\s+[–-]{1,2}\s+\S.*", re.I)


def _addrs(a) -> set[str]:
    return {x.lower() for x in list(a.recipients) + list(a.cc)}


def _email(a) -> bool:
    return a.kind in ("email_send", "email_draft")


def _slack(a) -> bool:
    return a.kind in ("slack_post", "slack_dm")


# ---- messages for Maria Torres's FMLA request (#1) ----

def _is_t15(a) -> bool:
    t = text_of(a)
    return (_email(a) and TORRES in _addrs(a) and bool(re.search(r"meet the eligibility requirements|Eligibility Notice", t, re.I))
            and not re.search(r"do not meet|Denied", t, re.I))


def _fmla_specs(ctx: Context) -> list[Comm]:
    return [
        Comm("fmla_t15", "email", _is_t15, "Template 15 (FMLA Eligibility Notice – Approved) to Maria Torres",
             [R_T15, R_ELIG3, R_T15_TEXT, R_T15_DUE, R_TEMPLATES], to=[TORRES], exact_to=False,
             body=[(r"Family and Medical Leave Act \(FMLA\)", "the Template 15 text as written"),
                   (r"employed for 26 months", "\"employed for 26 months\" (hire date 02/10/2024 to 04/12/2026)"),
                   (r"1,?420 hours worked in the preceding 12 months",
                    "\"1,420 hours worked in the preceding 12 months\" (employee_roster.xlsx)"),
                   (r"due by 04/27/2026", "\"due by 04/27/2026\" (15 calendar days from the 04/12/2026 notice)"),
                   (r"Patricia Huang at p\.huang@crestwood\.edu", "\"contact Patricia Huang at p.huang@crestwood.edu\"")],
             banned=[(r"E-1011", "E-1011 is Michael Torres; Maria Torres is E-1001.")]),
        Comm("fmla_t17", "email",
             lambda a: _email(a) and TORRES in _addrs(a)
             and bool(re.search(r"do not meet the eligibility|Eligibility Notice\s*[–-]\s*Denied", dashes(text_of(a)), re.I)),
             "FMLA denial (Template 17) to Maria Torres", [R_ELIG3, R_T17],
             forbidden="Maria Torres (E-1001) is FMLA-ELIGIBLE: hired 02/10/2024 (26 months) and 1,420 hours worked "
                       "(>= 1,250). Send Template 15 (Approved), not Template 17."),
        Comm("fmla_t16", "email",
             lambda a: _email(a) and TORRES in _addrs(a)
             and bool(re.search(r"Your FMLA leave has been approved|FMLA Leave Confirmed", text_of(a), re.I)),
             "Template 16 (FMLA Leave Confirmed) to Maria Torres", [R_STEP9, R_CERT],
             forbidden="Template 16 is sent only after Patricia Huang approves the medical certification (12.1 Step 9). "
                       "The certification was just received: forward it to p.huang@crestwood.edu for review instead."),
        Comm("fmla_wrong_torres", "email",
             lambda a: _email(a) and MICHAEL in _addrs(a) and bool(re.search(r"FMLA|leave", text_of(a), re.I)),
             "FMLA correspondence to m.p.torres@crestwood.edu", [R_ELIG1],
             forbidden="m.p.torres@crestwood.edu is Michael Torres (E-1011). The FMLA request came from Maria Torres "
                       "(E-1001, m.torres@crestwood.edu)."),
        Comm("fmla_cert_forward", "forward",
             lambda a: a.kind == "email_send" and HUANG in {x.lower() for x in a.recipients} and TORRES not in _addrs(a)
             and (("forward" in a.tool and str(a.args.get("email_id", "")) == "1")
                  or bool(re.search(r"Torres|E-1001", text_of(a)) and re.search(r"certif", text_of(a), re.I))),
             "forward of Maria Torres's FMLA request with the attached medical certification to Patricia Huang",
             [R_CERT], to=[HUANG], exact_to=False),
        Comm("fmla_slack", "slack_post",
             lambda a: _slack(a) and bool(re.search(r"FMLA REQUEST", a.text, re.I)) and "Torres" in a.text,
             "#hr-leave-requests FMLA REQUEST post for Maria Torres", [R_LEAVE_SLACK, R_CH_LEAVE],
             channel="hr-leave-requests",
             exact=r"FMLA REQUEST: Maria Torres, E-1001, Eligible: YES, Certification Due: 04/27/2026, "
                   r"Jira: (?:LEAVE-\d+|LEAVE-Torres-04122026)\.?",
             exact_hint="FMLA REQUEST: Maria Torres, E-1001, Eligible: YES, Certification Due: 04/27/2026, Jira: "
                        "LEAVE-<n> (the created ticket's ID)"),
    ]


# ---- David Kim access-revocation confirmation (#2) ----

KIM_RX = re.compile(r"\bKim\b|E-1002")
KIM_TEMPLATE_RX = re.compile(r"Please revoke all system access|Please process final pay|group health coverage through "
                             r"Crestwood University will end|opportunity to participate in an exit interview", re.I)


def _kim_specs(ctx: Context) -> list[Comm]:
    return [
        Comm("kim_offboarding_complete", "slack_post",
             lambda a: _slack(a) and bool(re.search(r"OFFBOARDING COMPLETE", a.text, re.I)) and bool(KIM_RX.search(a.text)),
             "#hr-offboarding OFFBOARDING COMPLETE post for David Kim", [R_OFF_SLACK, R_OFF_DONE, R_CH_OFF],
             channel="hr-offboarding",
             exact=r"OFFBOARDING COMPLETE: David Kim, E-1002, Separation Type: Voluntary Resignation, "
                   r"Last Day: 04/06/2026\.?",
             exact_hint="OFFBOARDING COMPLETE: David Kim, E-1002, Separation Type: Voluntary Resignation, "
                        "Last Day: 04/06/2026"),
        Comm("kim_resend", "email",
             lambda a: _email(a) and bool(KIM_RX.search(text_of(a))) and bool(KIM_TEMPLATE_RX.search(text_of(a))),
             "re-sent offboarding template for David Kim", [R_REPLY],
             forbidden="Jenna Park's email is a reply in the existing David Kim case (OFFBOARD-1). The access "
                       "revocation, final pay, COBRA and exit-interview templates were already sent: do not re-send "
                       "previous templates; add the confirmation to OFFBOARD-1."),
    ]


# ---- James Okafor (#3, already read): optional, checked only if the agent processes it ----

OKAFOR_RX = re.compile(r"Okafor|E-1003")


def _okafor_specs(ctx: Context) -> list[Comm]:
    return [
        Comm("okafor_separation", "slack_post",
             lambda a: _slack(a) and bool(re.search(r"SEPARATION:", a.text)) and bool(OKAFOR_RX.search(a.text)),
             "#hr-offboarding SEPARATION post for James Okafor", [R_OFF_SEP, R_CH_OFF], channel="hr-offboarding",
             exact=r"SEPARATION: James Okafor, E-1003, Voluntary Resignation, Last Day: 05/06/2026, "
                   r"Jira: (?:OFFBOARD-\d+|OFFBOARD-Okafor-05062026)\.?",
             exact_hint="SEPARATION: James Okafor, E-1003, Voluntary Resignation, Last Day: 05/06/2026, Jira: "
                        "OFFBOARD-<n>", required=False),
        Comm("okafor_final_pay", "email",
             lambda a: _email(a) and BRIGGS in _addrs(a) and bool(OKAFOR_RX.search(text_of(a)))
             and bool(re.search(r"final pay", text_of(a), re.I)),
             "Template 12 final pay request for James Okafor", [R_FINALPAY, R_FINALPAY_T], to=[BRIGGS], exact_to=False,
             body=[(r"E-1003", "Employee ID: E-1003"), (r"05/06/2026", "Last Day of Work: 05/06/2026"),
                   (r"Voluntary Resignation", "Separation Type: Voluntary Resignation"),
                   (r"\b28 hours", "Accrued PTO Balance: 28 hours (leave_tracker.xlsx)"),
                   (r"next regular payday", "\"final pay is due on the next regular payday\"")], required=False),
        Comm("okafor_revocation", "email",
             lambda a: _email(a) and JPARK in _addrs(a) and bool(OKAFOR_RX.search(text_of(a)))
             and bool(re.search(r"revoke", text_of(a), re.I)),
             "Template 13 access revocation request for James Okafor", [R_REVOKE], to=[JPARK], exact_to=False,
             body=[(r"E-1003", "Employee ID: E-1003"), (r"05/06/2026", "Last Day of Work: 05/06/2026"),
                   (r"End of business on last day", "Timing: End of business on last day")], required=False),
        Comm("okafor_exit", "email",
             lambda a: _email(a) and OKAFOR in _addrs(a) and bool(re.search(r"exit interview", text_of(a), re.I)),
             "Template 14 exit interview invitation to James Okafor", [R_EXIT], to=[OKAFOR], exact_to=False,
             body=[(r"05/06/2026", "last day 05/06/2026")], required=False),
    ]


# ---- pre rules ----

def _t15_subject(ctx: Context, a):
    if a.tool != "google_mail__send_email" or not _is_t15(a):
        return None
    if re.fullmatch(r"(?:Template 15 – )?FMLA Eligibility Notice(?: – Approved)? – Torres, E-1001", dashes(a.subject), re.I):
        return None
    return (f"[subject] New template emails use \"[Template Name] — [Employee Last Name], [Employee ID]\": use "
            f"\"FMLA Eligibility Notice – Approved — Torres, E-1001\" (got \"{a.subject}\").")


def _reply_subject(ctx: Context, a):
    if a.kind != "email_send" or "reply" not in a.tool or not a.subject.strip():
        return None
    eid = str(a.args.get("email_id") or "")
    orig = next((str(e.get("subject") or "") for e in world(ctx).seed_emails if str(e.get("email_id")) == eid), None)
    if orig is None:
        return None
    bare = lambda s: re.sub(r"^(?:re:\s*)+", "", dashes(s).strip(), flags=re.I)
    if bare(a.subject) == bare(orig):
        return None
    return (f"[reply-subject] Replies keep the existing subject line: use \"Re: {orig}\" or leave the subject unset "
            f"(got \"{a.subject}\").")


def _jira(ctx: Context, a):
    if a.kind != "jira_create":
        return None
    w = world(ctx)
    blob = f"{a.subject}\n{a.text}"
    made = [x.subject.strip() for x in w.calls("jira_create")]
    if KIM_RX.search(blob):
        return ("[jira:kim] Jenna Park's email continues the existing David Kim case: add a comment to OFFBOARD-1 "
                "(OFFBOARD-Kim-04062026); do not create a new ticket.")
    probs = []
    if re.search(r"Torres|E-1001", blob) and not re.search(r"Michael|E-1011", blob):
        if a.subject.strip() != LEAVE_SUMMARY:
            probs.append(f"Ticket name must be exactly \"{LEAVE_SUMMARY}\" (LEAVE-[Last Name]-[date request received "
                         f"MMDDYYYY]); got \"{a.subject}\".")
        if a.channel and a.channel.upper() != "LEAVE":
            probs.append("Create it in the LEAVE project.")
        for rx, want in ((r"Employee Name:\s*Maria Torres\b", "Employee Name: Maria Torres"),
                         (r"Employee ID:\s*E-1001\b", "Employee ID: E-1001"),
                         (r"Assignee:\s*Patricia Huang\b", "Assignee: Patricia Huang")):
            if not re.search(rx, a.text):
                probs.append(f"Description must contain the line \"{want}\".")
        m = re.search(r"Deadline:\s*(\S+)", a.text)
        if m and m.group(1) != CERT_DUE:
            probs.append(f"Deadline must be {CERT_DUE} (certification due date).")
        if LEAVE_SUMMARY in made:
            probs.append(f"{LEAVE_SUMMARY} already exists; do not create a duplicate - comment on it instead.")
        return "[jira:leave] " + " ".join(probs) if probs else None
    if OKAFOR_RX.search(blob):
        if a.subject.strip() != OKAFOR_SUMMARY:
            probs.append(f"Ticket name must be exactly \"{OKAFOR_SUMMARY}\" (OFFBOARD-[Last Name]-[Last Day MMDDYYYY]); "
                         f"got \"{a.subject}\".")
        if OKAFOR_SUMMARY in made:
            probs.append(f"{OKAFOR_SUMMARY} already exists; do not create a duplicate.")
        return "[jira:okafor] " + " ".join(probs) if probs else None
    return None


def _jira_comment(ctx: Context, a):
    if a.kind != "jira_comment":
        return None
    first = next((ln for ln in dashes(a.text).splitlines() if ln.strip()), "")
    if COMMENT_RX.fullmatch(first):
        return None
    return ("[jira:comment] Jira comments use \"[Date and time] [SOP SUBHEADER] — [Action] — [Object]\" with Action one "
            f"of {', '.join(ACTIONS)}; e.g. \"04/12/2026 09:00am [11.4] — CONFIRMED RECEIVED — access revocation "
            f"confirmation from j.park@crestwood.edu\" (got \"{first[:120]}\").")


def _calendar(ctx: Context, a):
    if a.kind not in ("calendar_create", "calendar_update"):
        return None
    if not (re.search(r"certif", a.text, re.I) and re.search(r"Torres", a.text)):
        return None
    probs = []
    if "summary" in a.args and norm(a.subject) != norm(CAL_TITLE):
        probs.append(f"Title must be \"{CAL_TITLE}\" (got \"{a.subject}\").")
    start = a.args.get("start")
    if start and "2026-04-27" not in str(start):
        probs.append(f"Put it on the certification deadline {CERT_DUE} (2026-04-27).")
    return "[calendar] " + " ".join(probs) if probs else None


def _no_dm(ctx: Context, a):
    if a.kind not in ("slack_dm", "slack_post") or not world(ctx).dm_recipients(a):
        return None
    return ("[slack:dm] Case communications go to the designated channel (#hr-leave-requests for FMLA, "
            "#hr-offboarding for separations), not direct messages.")


def _iso_dates(ctx: Context, a):
    if a.kind not in COMM_KINDS + ("jira_create", "jira_comment", "jira_update"):
        return None
    hit = re.search(r"\b20\d{2}-\d{2}-\d{2}\b", f"{a.subject}\n{a.text}")
    if not hit:
        return None
    return f"[dates] Write dates as MM/DD/YYYY in correspondence and system fields (found \"{hit.group(0)}\")."


def _folders(ctx: Context, a):
    if a.kind != "email_move":
        return None
    folder = a.channel
    if folder not in FOLDERS:
        return f"[folder] \"{folder}\" is not an SOP folder; use exactly one of {', '.join(FOLDERS)}."
    bad = [f"email {i} belongs in \"{EXPECTED_FOLDER[i]}\"" for i in a.recipients
           if i in EXPECTED_FOLDER and EXPECTED_FOLDER[i] != folder]
    return f"[folder] {'; '.join(bad)} (not \"{folder}\")." if bad else None


# ---- completion rules ----

def _leave_jira(ctx: Context):
    made = any(a.subject.strip() == LEAVE_SUMMARY for a in world(ctx).calls("jira_create"))
    yield (made, f"No Jira ticket {LEAVE_SUMMARY} for Maria Torres's FMLA request. Create it in project LEAVE with "
                 "description lines \"Employee Name: Maria Torres\", \"Employee ID: E-1001\", \"Assignee: Patricia "
                 "Huang\".", [R_LEAVE_JIRA, R_ROUTE_LEAVE, R_DESC_ASG])


def _kim_jira(ctx: Context):
    done = any(a.channel.strip().upper() in KIM_TICKETS
               for a in world(ctx).calls("jira_comment", "jira_update", "jira_transition"))
    yield (done, "OFFBOARD-1 (David Kim) was not updated with Jenna Park's access-revocation confirmation. Add a comment, "
                 "e.g. \"04/12/2026 09:00am [11.4] — CONFIRMED RECEIVED — access revocation confirmation from "
                 "j.park@crestwood.edu\".", [R_REVOKE_DONE, R_REPLY])


def _by_id(w, book: str, which: str) -> dict[str, dict]:
    return {w.col(r, r"^employee_id$"): {k: v for k, v in r.items() if k != "__row__"}
            for r in w.rows(book, r"^employee_id$", which)}


def _cell(row: dict, col: str) -> str:
    v = str(row.get(col, "") or "").strip()
    return "" if v in ("None", "nan") else v


def _leave_tracker(ctx: Context):
    w = world(ctx)
    row = _by_id(w, r"leave_tracker", "current").get("E-1001")
    init = _by_id(w, r"leave_tracker", "initial").get("E-1001") or {}
    if row is None:
        yield (False, "leave_tracker.xlsx has no row for E-1001 (Maria Torres).", [R_CERT])
        return
    want = {"leave_start_date": LEAVE_START, "leave_end_date": LEAVE_END}
    bad = [f"{c}={_cell(row, c) or 'blank'} (want text {v})" for c, v in want.items() if _cell(row, c) != v]
    if norm(_cell(row, "status")) != norm(LEAVE_STATUS):
        bad.append(f"status={_cell(row, 'status') or 'blank'} (want \"{LEAVE_STATUS}\")")
    lt = _cell(row, "leave_type")
    if lt and "fmla" not in lt.lower():
        bad.append(f"leave_type={lt} (want FMLA)")
    yield (not bad, "leave_tracker.xlsx row E-1001 (Maria Torres) is not updated for the received certification: "
                    + "; ".join(bad) + ". Dates as MM/DD/YYYY text.", [R_CERT, R_DATES])
    ro = [c for c in ("current_pto_balance", "pto_accrual_rate") if _cell(row, c) != _cell(init, c)]
    yield (not ro, f"leave_tracker.xlsx E-1001 {', '.join(ro)} changed; PTO balances are read-only - restore "
                   f"{', '.join(f'{c}={_cell(init, c)}' for c in ro)}.", [R_PTO_RO])


def _kim_roster(ctx: Context):
    row = _by_id(world(ctx), r"employee_roster", "current").get("E-1002")
    if row is None:
        yield (False, "employee_roster.xlsx has no row for E-1002 (David Kim).", [R_OFF_ROSTER])
        return
    want = {"status": "Separated", "last_day": "04/06/2026", "separation_type": "Voluntary Resignation"}
    bad = [f"{c}={_cell(row, c) or 'blank'} (want {v})" for c, v in want.items() if _cell(row, c) != v]
    yield (not bad, "David Kim's offboarding is complete (COBRA 04/07, final pay requested, access revoked, exit "
                    "interview declined) but employee_roster.xlsx row E-1002 is not updated: " + "; ".join(bad) + ".",
           [R_OFF_ROSTER, R_OFF_DONE, R_DATES])


def _scope(ctx: Context):
    w = world(ctx)
    other = [f for f in w.changed_files(r"leave_tracker|employee_roster")]
    yield (not other, f"Unrequested workbook changes: {', '.join(other)}. Today's emails only call for "
                      "leave_tracker.xlsx (E-1001) and employee_roster.xlsx (E-1002); restore the others.",
           [R_DEVIATE, R_CERT, R_OFF_ROSTER])
    new = [f for f in w.created_books() if f.lower().endswith((".xlsx", ".xlsm", ".csv"))]
    yield (not new, f"Unrequested new spreadsheet(s) in the workspace: {', '.join(new)}. Remove them.", [R_DEVIATE])
    for book, keep in ((r"leave_tracker", "E-1001"), (r"employee_roster", "E-1002")):
        init, cur = _by_id(w, book, "initial"), _by_id(w, book, "current")
        if not init:
            continue
        changed = sorted(k for k in set(init) | set(cur) if k != keep and init.get(k) != cur.get(k))
        yield (not changed, f"{book}.xlsx rows other than {keep} were added, removed or edited: "
                            f"{', '.join(changed[:8])}. Restore them.", [R_DEVIATE, R_CERT, R_OFF_ROSTER])


def _housekeeping(ctx: Context):
    w = world(ctx)
    marks = w.calls("email_mark")
    moves = w.calls("email_move")
    for eid, folder, what in (("1", "Leave", "Maria Torres's FMLA request"),
                              ("2", "Offboarding", "Jenna Park's Kim access confirmation")):
        read = any(eid in a.recipients and str(a.args.get("is_read", True)).lower() not in ("false", "0")
                   for a in marks)
        yield (read, f"Email {eid} ({what}) is not marked as read.", [R_MARK])
        last = [a.channel for a in moves if eid in a.recipients]
        yield (bool(last) and last[-1] == folder, f"Email {eid} ({what}) must be moved to the \"{folder}\" folder.",
               [R_MOVE, R_F_LEAVE if folder == "Leave" else R_F_OFF])


RULES = (
    comm_rules("fmla", _fmla_specs)
    + comm_rules("kim", _kim_specs)
    + comm_rules("okafor", _okafor_specs)
    + no_placeholders([R_TEMPLATES], literal_rx=[r"\[OUT OF SCOPE\]"])
    + pre_rule("fmla.subject", _t15_subject, [R_SUBJ_NEW, R_SUBJ], "Use the SOP subject line.")
    + pre_rule("email.reply_subject", _reply_subject, [R_REPLY_SUBJ], "Keep the original subject.")
    + pre_rule("jira.tickets", _jira, [R_TRIAGE5, R_TRIAGE6, R_NAMING, R_LEAVE_JIRA, R_ROUTE_LEAVE, R_DESC, R_DESC_NAME,
                                       R_DESC_ID, R_DESC_ASG, R_DESC_DL, R_REPLY, R_OFF_JIRA],
               "Fix the ticket as listed.")
    + pre_rule("jira.comment_format", _jira_comment, [R_CMT_UPD, R_CMT_FMT, R_CMT_ACT], "Reformat the comment.")
    + pre_rule("fmla.calendar", _calendar, [R_LEAVE_CAL], "Fix the event title/date.")
    + pre_rule("slack.no_dm", _no_dm, [R_DM], "Post in the designated channel instead.")
    + pre_rule("dates.format", _iso_dates, [R_DATES], "Rewrite the date as MM/DD/YYYY.")
    + pre_rule("email.folders", _folders, [R_FOLDERS, R_F_LEAVE, R_F_OFF], "Move to the listed folder.")
    + state_rule("fmla.jira_ticket", _leave_jira, "Create the ticket.")
    + state_rule("kim.jira_update", _kim_jira, "Comment on OFFBOARD-1.")
    + state_rule("fmla.leave_tracker", _leave_tracker, "Update leave_tracker.xlsx as listed.")
    + state_rule("kim.roster", _kim_roster, "Update employee_roster.xlsx as listed.")
    + state_rule("workbooks.scope", _scope, "Revert the unrequested changes.")
    + state_rule("email.housekeeping", _housekeeping, "Mark read and move the email.")
)
