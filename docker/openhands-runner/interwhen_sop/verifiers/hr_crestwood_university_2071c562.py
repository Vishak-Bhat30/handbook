"""Crestwood University HR (task 2071c562): Derek Okonkwo is today's HR coordinator (04/09/2026) and resolves the
two unread emails.

- Email 5: Ramona Clint forwards Gerta Teodoor's (10741, Art, Exempt) resignation, last day 04/19/2026. Per the
  user, SOP 12.2 (COBRA, incl. its Jira notes) and 12.3 (final pay) are NOT done. Remaining: 12.1 (Jira
  OFFBOARD-Teodoor-04192026 assigned to the coordinator on duty, SEPARATION post), 12.4 (Template 13 to Jenna
  Park), 12.5 (Template 14 to g.teodoor@crestwood.edu - roster email is blank, SOP 3.2 address format).
  12.6 is not reached (access not yet confirmed, exit interview pending), so the roster stays unchanged.
- Email 4: Ardisj Parke (10980) raises a pay discrepancy and a coworker-conduct complaint. Parke is under a
  legal-threat escalation (SOP 16, LEAVE-Parke ticket, #hr-escalations "do not reply"): Dr. Whitfield and
  Nicole Ashford handle all further communication, so no email goes to Parke. The items are still routed
  internally: forward to c.briggs (payroll) and m.voss (employee relations).
Not enforced (ambiguous): Parke Jira handling, Parke email folder/flag.
"""

from __future__ import annotations

import json
import re

from ..kit import (Comm, Context, comm_rules, dashes, forbid_writes, no_placeholders, norm, pre_rule, state_rule,
                   text_of, world)

EMP, EID, LAST = "Gerta Teodoor", "10741", "04/19/2026"
EMP_MAIL = "g.teodoor@crestwood.edu"
TICKET = "OFFBOARD-Teodoor-04192026"
PARKE = "a.parke@crestwood.edu"
FOLDERS = ("Onboarding", "Offboarding", "Leave", "Performance", "Recruiting", "General", "INBOX", "Inbox")

R_SLACK = ("5", "All operational HR communications must use designated Slack channels", "5 Slack channels")
R_EMAIL_FMT = ("3.2", "All employee internal email addresses follow the format", "3.2 Employee email addresses")
R_PAYROLL = ("7", "Benefits enrollment changes, qualifying life events, payroll", "7 Benefits & Payroll")
R_ER = ("7", "Workplace complaints, harassment reports", "7 Employee Relations")
R_STEP3 = ("8", "Step 3: If the request involves employee relations", "8 Triage Step 3")
R_STEP4 = ("8", "Step 4: If the request involves payroll or compensation", "8 Triage Step 4")
R_NAMING = ("8", "Format: [PREFIX]-[Employee Last Name]-[DATE in MMDDYYYY]", "8 Jira naming")
R_OFF_ROW = ("8", "Offboarding | OFFBOARD | HR Coordinator on duty", "8 Jira routing table")
R_NODUP = ("8", "Note: Check Jira for existing open tickets", "8 Jira duplicates")
R_CONFIRM = ("12.1", "Step 1: Open employee_roster.xlsx and confirm", "12.1 Step 1")
R_JIRA = ("12.1", "Step 2: Create a Jira ticket: OFFBOARD-", "12.1 Step 2")
R_SEP = ("12.1", "Step 3: Post to #hr-offboarding: SEPARATION:", "12.1 Step 3")
R_COBRA = ("12.2", "Step 2: If the employee was enrolled in health benefits", "12.2 Step 2 (excluded by the user)")
R_COBRA_ROW = ("12.2", "Step 3: Update benefits_enrollment.xlsx", "12.2 Step 3 (excluded by the user)")
R_NOCOBRA = ("12.2", "If the employee was NOT enrolled in health benefits", "12.2 (excluded by the user)")
R_FINALPAY = ("12.3", "Step 2: Email c.briggs@crestwood.edu with the employee", "12.3 Step 2 (excluded by the user)")
R_REVOKE = ("12.4", "Step 1: Email j.park@crestwood.edu using Template 13", "12.4 Step 1")
R_EXIT = ("12.5", "Step 1: Send Template 14 (Exit Interview Invitation)", "12.5 Step 1")
R_EXIT_CAL = ("12.5", "Step 2: If the employee accepts, schedule", "12.5 Step 2")
R_DONE = ("12.6", "When all offboarding steps are complete", "12.6 Offboarding completion")
R_DONE_ROSTER = ("12.6", "Update employee_roster.xlsx: change status to", "12.6 roster update")
R_DONE_CLOSE = ("12.6", "Close the Jira ticket.", "12.6 close ticket")
R_DONE_POST = ("12.6", "Post to #hr-offboarding: OFFBOARDING COMPLETE:", "12.6 completion post")
R_LEGAL = ("16", "For legal threats: Do NOT reply to the email.", "16 Legal threats")
R_READ = ("17", "Mark as read | Every processed email", "17 Mark as read")
R_P3 = ("17", "P3 / P4 emails | Move to the matching folder", "17 P3/P4 emails")
R_OFF_FOLDER = ("17", "Offboarding | All offboarding-related emails", "17 Offboarding folder")
R_TPL = ("18", "Templates must be used as written.", "18 Email templates")
R_T13 = ("18", "Please revoke all system access for the following employee", "Template 13")
R_T14 = ("18", "As part of our offboarding process", "Template 14")
R_SUBJ = ("19", "When composing a new email (not a reply or forward)", "19 Subject line format")
R_SUBJ_FWD = ("19", "forwarding, keep the existing subject line", "19 Keep subject when forwarding")


def _blob(a) -> str:
    return dashes(f"{text_of(a)}\n{' '.join(a.recipients + a.cc)}")


def _about_teodoor(a) -> bool:
    return bool(re.search(r"teodoor|\b10741\b", _blob(a), re.I))


def _ids(a) -> set[str]:
    return {str(x) for x in (a.recipients or [])} | {str(a.args.get("email_id") or "")} - {""}


def _folder(a) -> str:
    if a.channel:
        return a.channel
    for v in a.args.values():
        if isinstance(v, str) and v.strip() in FOLDERS:
            return v.strip()
    return ""


def _ticket_key(ctx: Context) -> str | None:
    for e in world(ctx).state.executed:
        if e.action.kind == "jira_create" and norm(e.action.subject) == norm(TICKET):
            m = re.search(r"\b(OFFBOARD-\d+)\b", e.result or "")
            if m:
                return m.group(1)
    return None


def _parke_fwd(a) -> bool:
    return bool("4" in _ids(a) or re.search(r"parke|\b10980\b|pay discrepancy|coworker conduct", text_of(a), re.I))


FWD_SUBJ = r"(?:(?:fwd?|fw|re)\s*:\s*)*(?:Inquiry: Pay discrepancy and coworker conduct)?"


def specs(ctx: Context) -> list[Comm]:
    ticket_hint = _ticket_key(ctx) or TICKET
    sep = f"SEPARATION: {EMP}, {EID}, Voluntary Resignation, Last Day: {LAST}, Jira: "
    return [
        Comm("separation_post", "slack_post",
             lambda a: a.kind in ("slack_post", "slack_dm") and bool(re.search(r"teodoor", a.text, re.I))
             and bool(re.search(r"SEPARATION", a.text, re.I)) and not re.search(r"OFFBOARDING COMPLETE", a.text, re.I),
             f"SEPARATION post for {EMP} in #hr-offboarding", [R_SEP, R_CONFIRM, R_SLACK], channel="hr-offboarding",
             exact=re.escape(sep) + rf"(?:{re.escape(TICKET)}|OFFBOARD-\d+)\.?", exact_hint=sep + ticket_hint),
        Comm("offboarding_complete", "slack_post",
             lambda a: a.kind in ("slack_post", "slack_dm") and bool(re.search(r"OFFBOARDING COMPLETE", a.text, re.I)),
             "OFFBOARDING COMPLETE post", [R_DONE, R_DONE_POST],
             forbidden=(f"Offboarding for {EMP} is not complete (access revocation not yet confirmed by IT, exit "
                        "interview not completed or declined), so the OFFBOARDING COMPLETE post is premature.")),
        Comm("t13_access_revocation", "email",
             lambda a: a.kind == "email_send" and (bool(re.search(r"Template 13\b", a.subject))
                                                 or ("j.park@crestwood.edu" in a.recipients + a.cc and _about_teodoor(a))),
             f"Template 13 (Access Revocation Request) for {EMP}", [R_REVOKE, R_T13, R_TPL, R_SUBJ],
             to=["j.park@crestwood.edu"],
             subject=r"(?:Template 13(?:\s*[-–:]\s*Access Revocation Request)?|Access Revocation Request) – Teodoor, 10741",
             subject_hint="Template 13 — Teodoor, 10741",
             body=[(r"Hi Jenna", "greeting \"Hi Jenna,\""),
                   (r"Please revoke all system access for the following employee",
                    "\"Please revoke all system access for the following employee:\""),
                   (rf"Name:\s*{EMP}", f"\"Name: {EMP}\""),
                   (rf"Employee ID:\s*{EID}", f"\"Employee ID: {EID}\""),
                   (rf"Last Day of Work:\s*{LAST}", f"\"Last Day of Work: {LAST}\""),
                   (r"Timing:\s*End of business on last day",
                    "\"Timing: End of business on last day\" (voluntary resignation)"),
                   (r"This includes email, VPN, building access, and all university systems",
                    "\"This includes email, VPN, building access, and all university systems. Please confirm when "
                    "complete.\""),
                   (r"Crestwood University – Office of Human Resources",
                    "sign-off \"Crestwood University – Office of Human Resources\"")]),
        Comm("t14_exit_interview", "email",
             lambda a: a.kind == "email_send" and (bool(re.search(r"Template 14\b|exit interview", a.subject, re.I))
                                                 or any("teodoor" in r for r in a.recipients + a.cc)),
             f"Template 14 (Exit Interview Invitation) to {EMP}", [R_EXIT, R_T14, R_EMAIL_FMT, R_TPL, R_SUBJ],
             to=[EMP_MAIL],
             subject=r"(?:Template 14(?:\s*[-–:]\s*Exit Interview Invitation)?|Exit Interview Invitation) – Teodoor, 10741",
             subject_hint="Template 14 — Teodoor, 10741",
             body=[(r"Hi Gerta", "greeting \"Hi Gerta,\""),
                   (r"As part of our offboarding process, we would like to offer you the opportunity to participate "
                    r"in an exit interview", "the Template 14 text as written"),
                   (r"This is completely voluntary and confidential", "\"This is completely voluntary and "
                                                                       "confidential.\""),
                   (rf"30-minute meeting before your last day of {LAST}",
                    f"\"... we will schedule a 30-minute meeting before your last day of {LAST}.\""),
                   (r"Crestwood University – Office of Human Resources",
                    "sign-off \"Crestwood University – Office of Human Resources\"")]),
        Comm("t12_final_pay", "email",
             lambda a: a.kind == "email_send" and (bool(re.search(r"Template 12\b", a.subject))
                                                 or ("c.briggs@crestwood.edu" in a.recipients + a.cc
                                                     and _about_teodoor(a))),
             f"final pay request for {EMP}", [R_FINALPAY],
             forbidden=("The user instructed not to perform SOP 12.3 (Final Pay & Accrued PTO) for this offboarding; "
                        "do not send the final-pay request.")),
        Comm("t11_cobra", "email",
             lambda a: a.kind == "email_send" and (bool(re.search(r"Template 11\b", a.subject))
                                                 or (bool(re.search(r"COBRA", text_of(a), re.I)) and _about_teodoor(a))),
             f"COBRA notification for {EMP}", [R_COBRA, R_NOCOBRA],
             forbidden="The user instructed not to perform SOP 12.2 (COBRA Notification); do not send COBRA emails."),
        Comm("fwd_payroll", "email",
             lambda a: a.kind == "email_send" and "c.briggs@crestwood.edu" in a.recipients + a.cc and _parke_fwd(a),
             "forward of Ardisj Parke's pay-discrepancy email (email 4) to the Payroll Liaison",
             [R_STEP4, R_PAYROLL, R_SUBJ_FWD], to=["c.briggs@crestwood.edu"], exact_to=False,
             subject=FWD_SUBJ, subject_hint="Fwd: Inquiry: Pay discrepancy and coworker conduct"),
        Comm("fwd_er", "email",
             lambda a: a.kind == "email_send" and "m.voss@crestwood.edu" in a.recipients + a.cc and _parke_fwd(a),
             "forward of Ardisj Parke's coworker-conduct complaint (email 4) to the Employee Relations Specialist",
             [R_STEP3, R_ER, R_SUBJ_FWD], to=["m.voss@crestwood.edu"], exact_to=False,
             subject=FWD_SUBJ, subject_hint="Fwd: Inquiry: Pay discrepancy and coworker conduct"),
    ]


RULES = []
RULES += comm_rules("comms", specs)
RULES += no_placeholders([R_TPL])


def _no_parke(ctx: Context, a) -> str | None:
    if a.kind not in ("email_send", "calendar_create", "calendar_update"):
        return None
    reply_to_parke = "reply" in a.tool and str(a.args.get("email_id") or "") in ("2", "4")
    if PARKE in a.recipients + a.cc or reply_to_parke:
        return ("[legal hold] Ardisj Parke is under a legal-threat escalation (#hr-escalations: \"LEGAL THREAT: Ardisj "
                "Parke ... – do not reply\"). Per SOP 16, Dr. Whitfield and Nicole Ashford handle all further "
                "communication with him: do not email or invite a.parke@crestwood.edu. Route his new items internally "
                "only (forward email 4 to c.briggs@crestwood.edu and m.voss@crestwood.edu).")
    return None


RULES += pre_rule("legal.parke_no_contact", _no_parke, [R_LEGAL], "Do not contact Ardisj Parke.")


def _no_dm(ctx: Context, a) -> str | None:
    if a.kind in ("slack_post", "slack_dm") and world(ctx).dm_recipients(a):
        return ("Case-related communication must go to the designated Slack channel, not a direct message "
                "(SEPARATION posts go to #hr-offboarding).")
    return None


RULES += pre_rule("slack.no_dm", _no_dm, [R_SLACK], "Post in the designated channel instead.")

RULES += forbid_writes(
    "files.no_workbook_writes", r"employee_roster\.xlsx|benefits_enrollment\.xlsx",
    "no SOP step in this task updates the roster or benefits workbook: COBRA / benefits status (SOP 12.2) is "
    "excluded by the user, and the roster is only set to Separated at offboarding completion (SOP 12.6), which "
    "is not reached yet (IT has not confirmed access revocation; the exit interview is pending).",
    [R_DONE, R_DONE_ROSTER, R_COBRA_ROW])


def _unchanged(ctx: Context):
    changed = world(ctx).changed_files()
    yield (not changed, f"Workbook(s) changed without an SOP step requiring it: {', '.join(changed)}. Restore them "
                        "to their original content (no roster/benefits update applies in this task).",
           [R_DONE, R_DONE_ROSTER, R_COBRA_ROW])


RULES += state_rule("files.unchanged", _unchanged, "Restore the original workbook content.")


def _jira_pre(ctx: Context, a) -> str | None:
    if not a.kind.startswith("jira_"):
        return None
    if re.search(r"COBRA", f"{a.subject}\n{a.text}\n{json.dumps(a.args)}", re.I):
        return ("The user instructed: no Jira updates for SOP 12.2 (COBRA). Do not record COBRA status/notes in "
                "Jira.")
    if a.kind == "jira_transition" and (a.channel.upper().startswith("OFFBOARD") or _ticket_key(ctx) == a.channel) \
            and re.search(r"^(2|4)$|clos", a.code.strip(), re.I):
        return (f"Do not close the offboarding ticket for {EMP}: SOP 12.6 closes it only when all offboarding steps "
                "are complete (access revocation not yet confirmed, exit interview pending).")
    if a.kind != "jira_create" or not re.search(r"teodoor|\b10741\b", f"{a.subject}\n{a.text}", re.I):
        return None
    probs = []
    if a.subject.strip() != TICKET:
        probs.append(f"the summary (ticket name) must be exactly \"{TICKET}\" (got \"{a.subject}\")")
    if a.channel and "offboard" not in a.channel.lower():
        probs.append(f"create it in the OFFBOARD project (got \"{a.channel}\")")
    if a.recipients and not re.search(r"okonkwo", " ".join(a.recipients), re.I):
        probs.append("assign it to the HR Coordinator on duty, Derek Okonkwo (U_OKONKWO)")
    if not probs and any(norm(x.subject) == norm(TICKET) for x in world(ctx).calls("jira_create")):
        probs.append(f"{TICKET} already exists; do not create a duplicate")
    return f"Offboarding Jira ticket for {EMP}: " + "; ".join(probs) + "." if probs else None


RULES += pre_rule("offboard.jira_pre", _jira_pre, [R_JIRA, R_NAMING, R_OFF_ROW, R_NODUP, R_NOCOBRA, R_DONE_CLOSE],
                  "Fix the Jira call as described.")


def _jira_done(ctx: Context):
    w = world(ctx)
    made = [a for a in w.calls("jira_create") if a.subject.strip() == TICKET]
    yield (bool(made), f"Jira ticket \"{TICKET}\" (project OFFBOARD, assignee Derek Okonkwo) has not been created "
                       f"for {EMP}'s resignation.", [R_JIRA, R_NAMING, R_OFF_ROW])
    if made:
        key = _ticket_key(ctx)
        assigned = any(re.search(r"okonkwo", " ".join(a.recipients), re.I) for a in made) or any(
            re.search(r"okonkwo", " ".join(a.recipients), re.I) and key and a.channel == key
            for a in w.calls("jira_update"))
        yield (assigned, f"Assign {TICKET} to the HR Coordinator on duty, Derek Okonkwo (U_OKONKWO).", [R_OFF_ROW])


RULES += state_rule("offboard.jira", _jira_done, "Create/assign the ticket as listed.")


def _exit_cal(ctx: Context, a) -> str | None:
    if a.kind in ("calendar_create", "calendar_update") and re.search(r"exit interview", a.text, re.I):
        return (f"Schedule the exit interview only after {EMP} accepts the Template 14 invitation (SOP 12.5 Step 2); "
                "no acceptance has been received.")
    return None


RULES += pre_rule("offboard.exit_calendar", _exit_cal, [R_EXIT_CAL], "Wait for the employee's reply.")


def _mail_pre(ctx: Context, a) -> str | None:
    if "5" not in _ids(a):
        return None
    if a.kind == "email_move":
        f = _folder(a)
        if f and f != "Offboarding":
            return (f"Email 5 (Gerta Teodoor resignation, P3 standard resignation) must be moved to the folder "
                    f"\"Offboarding\" (got \"{f}\").")
    if a.kind == "email_mark":
        flag = next((v for k, v in a.args.items() if re.search(r"important|flag|star", k, re.I)), None)
        action = str(a.args.get("action") or a.args.get("mark_as") or a.args.get("status") or "").lower()
        if flag is True or str(flag).lower() == "true" or re.fullmatch(r"(mark_)?(important|flagged|starred)", action):
            return "Email 5 is a P3 email: move it to Offboarding and do not flag it."
    return None


RULES += pre_rule("mail.housekeeping_pre", _mail_pre, [R_P3, R_OFF_FOLDER], "Use the Offboarding folder, unflagged.")


def _mail_done(ctx: Context):
    w = world(ctx)
    read = set()
    for a, out in w.state.reads:
        if re.search(r"(read|get)_email$", a.tool) and not re.search(r'"error"|not found', out or "", re.I):
            read |= _ids(a)
    for a in w.calls("email_mark"):
        if not re.search(r"unread|\"is_read\":\s*false", json.dumps(a.args), re.I):
            read |= _ids(a)
    for eid, what in (("5", "Gerta Teodoor resignation (email 5)"), ("4", "Ardisj Parke inquiry (email 4)")):
        yield (eid in read, f"Mark the processed email as read: {what}.", [R_READ])
    moved = any("5" in _ids(a) and _folder(a) == "Offboarding" for a in w.calls("email_move"))
    yield (moved, "Move email 5 (Fwd: Notice of Resignation - Gerta Teodoor, P3) to the \"Offboarding\" folder.",
           [R_P3, R_OFF_FOLDER])


RULES += state_rule("mail.housekeeping", _mail_done, "Complete the email housekeeping as listed.")
