"""Ridgeline Gear Co. leave coordinator - Taylor Gonzalez HFWA request (task 2deeab56).

Situation (seed data): Charlie Szabo (manager) asks in #leave-intake to process an HFWA sick leave for Taylor
Gonzalez (R-0014) on 04/08-04/09/2025. Taylor's own email "Leave Request - HFWA" (email 1) says he discussed the
request with "a legal professional" who reviewed it against US Department of Labor guidelines. Per SOP 12.5 (and
its note: a regulator citation plus personal legal counsel = legal threat) this is a legal threat on a NEW request
(Taylor's earlier cases are Closed), so the SOP outcome is:
  - no reply to the employee, no case opened, no further communication with the employee or manager;
  - #legal-review post "LEGAL THREAT: Taylor Gonzalez, New Case, Leave Request - HFWA, [Brief Description] — do not
    reply";
  - the thread forwarded to General Counsel evelyn.marchetti@ridgelineholdings.com with subject
    "LEGAL THREAT — Taylor Gonzalez — New Case";
  - housekeeping: the P1 email is marked read, flagged important and left in the Inbox.
"""

from __future__ import annotations

import re

from ..kit import Comm, comm_rules, dashes, forbid_writes, no_placeholders, pre_rule, state_rule, world

# ---- SOP references (section, paragraph prefix, label) ------------------------------------------------
R_AUTH = ("5", "The Leave Coordinator", "5 Authority & Decision Limits")
R_GC = ("5.4", "Any employee communication mentioning an attorney", "5.4 General Counsel decisions")
R_NEVER_MED = ("5.5", "Disclose any employee medical information", "5.5 never disclose medical information")
R_NEVER_EXT = ("5.5", "Confirm or deny whether an employee is on any type of leave", "5.5 never confirm leave status")
R_NEVER_OTHER = ("5.5", "Discuss one employee's leave with another employee", "5.5 never discuss with others")
R_NEVER_PHI = ("5.5", "Include medical details, diagnoses", "5.5 no medical details in messages")
R_BLANK = ("40", "CO_FAMLI_Employee_Notice.pdf, Never modify", "4 Tools, Files & Systems (blank forms)")
R_NO_DM = ("4", "All internal communications about leave cases must use", "4 Slack channels (no DMs)")
R_LEGAL_CH = ("4", "#legal-review General Counsel attention", "4 Slack channels (#legal-review)")
R_SLACK_PHI = ("4", "Never post medical details, diagnoses", "4 Slack channels (no medical details)")
R_STEP12 = ("6.1", "Step 12: Complete email housekeeping", "6.1 Triage Step 12")
R_P1 = ("6", "Priority Description Examples P1", "6 Priority Matrix (P1: legal threat)")
R_WAGE = ("9.1", "Wage replacement under FAMLI is paid by CDLE", "9.1 FAMLI wage replacement")
R_WAGE2 = ("9.7", "Leave Coordinator must NEVER discuss wage replacement", "9.7 wage replacement")
R_MGR_NOT = ("10.1", "The specific medical condition, diagnosis, or treatment", "10.1 what a manager may not know")
R_T11 = ("10.2", "The Manager Leave Notification must NEVER include", "10.2 manager notification limits")
R_PAY_PHI = ("10.2", "Do not include medical details, diagnoses, or the reason category", "10.2 payroll format")
R_TRIGGER = ("12.5", "If any of the following are present in any communication", "12.5 Legal Threats")
R_ATTORNEY = ("12.5", "Mention of an attorney, lawyer, legal counsel", "12.5 attorney / legal counsel")
R_REGULATOR = ("12.5", "Mention of EEOC, CDLE, DOL", "12.5 regulator mention")
R_NOTE = ("12.5", "Note: A general or informational citation", "12.5 note (regulator + personal counsel)")
R_NO_REPLY = ("12.5", "Step 1: DO NOT reply to the email", "12.5 Step 1")
R_POST = ("12.5", "Step 2: Post to #legal-review", "12.5 Step 2")
R_FWD = ("12.5", "Step 3: Forward the email thread", "12.5 Step 3")
R_NO_CASE = ("12.5", "Step 4: If it is an ongoing case", "12.5 Step 4")
R_NO_RESPOND = ("12.5", "Step 5: If the manager, employee", "12.5 Step 5")
R_EMAIL_PHI = ("13.2", "Never include medical details, diagnoses", "13.2 email confidentiality")
R_CC = ("13.2", "Never CC anyone outside the HR team", "13.2 email confidentiality (HR team only)")
R_FWD_HR = ("13.2", "Never forward an email thread containing medical information", "13.2 forwarding limits")
R_QUOTE = ("13.2", "If an employee sends an email containing more medical detail", "13.2 quoted medical detail")
R_PERSONAL = ("13.2", "Never use the employee's personal email", "13.2 personal email")
R_SLACK_PHI2 = ("13.3", "Never post medical details", "13.3 Slack confidentiality")
R_NO_TAG = ("13.3", "Never tag managers or non-HR roles", "13.3 no tagging managers")
R_DM2 = ("13.3", "Direct messages about cases are prohibited", "13.3 no DMs")
R_DELETE = ("13.5", "Do not delete any case file", "13.5 records retention")
R_HOUSE = ("13", "After processing every leave-related email", "13 Email Housekeeping")
R_READ = ("13.1", "Rule Action Mark as read", "13.1 mark as read")
R_INBOX = ("13.1", "P1 / P2 emails Leave in the Inbox", "13.1 P1/P2 emails")
R_PLACE = ("13", "Replace all [bracketed] placeholders", "13 Email Templates (placeholders)")

# ---- task facts (seed data) ---------------------------------------------------------------------------
GC_EMAIL = "evelyn.marchetti@ridgelineholdings.com"
TAYLOR_EMAILS = {"taylor.gonzalez@ridgelinegear.com", "taylor.gonzalez@gmail.com"}
CHARLIE_EMAILS = {"charlie.szabo@ridgelinegear.com", "charlie.szabo@gmail.com"}
TAYLOR_UID, CHARLIE_UID = "U025", "U022"
CASE_EMAIL_IDS = {"1", "32", "33"}       # Taylor's request, Taylor's earlier HFWA inquiry, Charlie's heads-up
REQUEST_EMAIL_ID, HEADS_UP_EMAIL_ID = "1", "33"
REQUEST_THREAD_TS = "1744156800.001300"  # Charlie's #leave-intake request
HR_TEAM = {"daniel.whitfield@ridgelinegear.com", "renata.okafor@ridgelinegear.com", "meera.patel@ridgelinegear.com",
           "jordan.briggs@ridgelinegear.com", "teresa.vang@ridgelinegear.com", "luis.arredondo@ridgelinegear.com",
           GC_EMAIL, "benefits@ridgelinegear.com", "leaves@ridgelinegear.com"}
SEED_BOOKS_RX = (r"^(employee_roster|hours_worked_log|leave_tracker|leave_history|hfwa_balance_tracker|"
                 r"famli_coordination_log)\.xlsx$")
# the medical details in Taylor's email / Charlie's heads-up (condition, treatment, provider)
MED_RX = (r"\bsurg\w*|hospitali[sz]\w*|complication|orthop\w*|\bDr\.?\s*Anand|\bAnand\b|"
          r"overnight observation|corrective treatment")
# separator before "do not reply": the SOP prints an em dash; a period/semicolon is tolerated
POST_RX = (r"(?s)(?:<@U02[67]>\s*|@evelyn\.marchetti\s*)?LEGAL THREAT: Taylor Gonzalez, New Case, "
           r"[\"“']?Leave Request\s*[-–]\s*HFWA[\"”']?, .+?\s*[-–.;,]\s*(?i:do not reply)\.?")
POST_HINT = ("LEGAL THREAT: Taylor Gonzalez, New Case, Leave Request - HFWA, <brief description without medical "
             "details> — do not reply")
SUBJECT_RX = r"(?:Fwd?:\s*)?[\"“]?LEGAL THREAT\s*[-–]\s*Taylor Gonzalez\s*[-–]\s*New Case[\"”]?"
SUBJECT_HINT = "LEGAL THREAT — Taylor Gonzalez — New Case"


def about_taylor(text: str) -> bool:
    t = re.sub(r"Jordan Taylor|Finley Gonzalez|taylor\.jordan|jordan\.taylor", "", str(text or ""), flags=re.I)
    return bool(re.search(r"\bTaylor\b|Gonzalez|R-0014|LEGAL THREAT", t, re.I))


def _addrs(a) -> set[str]:
    return {x.lower() for x in a.recipients + a.cc}


def case_email(a) -> bool:
    return about_taylor(f"{a.subject}\n{a.text}") or str(a.args.get("email_id") or "") in CASE_EMAIL_IDS


def _medical(text: str) -> list[str]:
    return sorted({m.group(0) for m in re.finditer(MED_RX, str(text or ""), re.I)})


# ---- 12.5 legal threat: required escalation messages -----------------------------------------------------

def _legal_post_done(ctx) -> bool:
    w = world(ctx)
    return any(re.fullmatch(POST_RX, dashes(a.text).strip()) and not _medical(a.text)
               for a in w.posts_in("legal-review"))


def specs(ctx) -> list[Comm]:
    w = world(ctx)
    post_done = _legal_post_done(ctx)

    def about_post(a):
        if a.kind not in ("slack_post", "slack_dm"):
            return False
        if re.search(r"LEGAL THREAT", a.text, re.I) and about_taylor(a.text):
            return True
        return (not post_done and a.kind == "slack_post" and not w.dm_recipients(a)
                and w.is_channel(a.channel, "legal-review") and about_taylor(a.text))

    def about_gc(a):
        return (a.kind in ("email_send", "email_draft") and a.tool != "google_mail__forward_email"
                and any("evelyn.marchetti" in r for r in _addrs(a)) and case_email(a))

    return [
        Comm("legal_review_post", "slack_post", about_post,
             "#legal-review LEGAL THREAT post for Taylor Gonzalez's new request (subject line \"Leave Request - HFWA\")",
             [R_POST, R_LEGAL_CH, R_TRIGGER, R_ATTORNEY, R_REGULATOR, R_NOTE, R_GC, R_SLACK_PHI],
             channel="legal-review", exact=POST_RX, exact_hint=POST_HINT,
             banned=[(MED_RX, "Remove the medical details (condition, treatment, provider) - Slack posts may not "
                              "contain protected health information.")]),
        Comm("gc_forward", "email", about_gc,
             "email forwarding Taylor Gonzalez's email thread to General Counsel (google_mail__forward_email cannot "
             "set the required subject, so use google_mail__send_email and paste the original email below a "
             "'---------- Forwarded message ---------' line)",
             [R_FWD, R_TRIGGER, R_ATTORNEY, R_NOTE, R_GC],
             to=[GC_EMAIL], exact_to=False, subject=SUBJECT_RX, subject_hint=SUBJECT_HINT,
             body=[(r"Leave Request\s*[-–]\s*HFWA",
                    "the forwarded thread - Taylor Gonzalez's original email (Subject: Leave Request - HFWA, "
                    "From: taylor.gonzalez@ridgelinegear.com) with its full text")]),
    ]


# ---- 12.5 STOP: no reply, no case, no communication with employee/manager -------------------------------

def hold_problem(ctx, a) -> str | None:
    w = world(ctx)
    why = ("Taylor Gonzalez's email mentions a legal professional and DOL guidelines, so this request is a legal "
           "threat under SOP 12.5: do not reply, do not open a case, and do not communicate with the employee or "
           "the manager - General Counsel handles all further communication.")
    if a.kind == "email_send":
        if "reply" in a.tool and str(a.args.get("email_id") or "") in CASE_EMAIL_IDS:
            return f"Replying to this email is not allowed. {why}"
        hit = _addrs(a) & TAYLOR_EMAILS
        if hit:
            return f"Emailing the employee ({', '.join(sorted(hit))}) is not allowed. {why}"
        hit = _addrs(a) & CHARLIE_EMAILS
        if hit and case_email(a):
            return f"Emailing the manager about this case ({', '.join(sorted(hit))}) is not allowed. {why}"
    if a.kind in ("slack_dm", "slack_post"):
        dm = w.dm_recipients(a)
        if a.kind == "slack_dm" or dm:
            if set(a.recipients) & {TAYLOR_UID, CHARLIE_UID} or dm & {TAYLOR_UID, CHARLIE_UID} or about_taylor(a.text):
                return ("Direct messages about leave cases are prohibited (they cannot be audited), and the employee "
                        f"and manager may not be contacted. {why}")
            return None
        if re.search(rf"<@({TAYLOR_UID}|{CHARLIE_UID})>|@charlie\.szabo|@taylor\.gonzalez", a.text, re.I):
            return f"Do not tag the employee or the manager in Slack. {why}"
        if str(a.args.get("thread_ts") or "") == REQUEST_THREAD_TS:
            return f"Do not reply to Charlie Szabo's #leave-intake request thread. {why}"
        name = w.channel_name(a.channel).lower()
        if name in ("leave-intake", "payroll-coordination", "unknown-senders-hr") and about_taylor(a.text):
            return (f"Do not post about Taylor Gonzalez's request in #{name}: no case is opened and nothing is "
                    f"approved or scheduled. The only Slack post the SOP requires is the LEGAL THREAT post in "
                    f"#legal-review. {why}")
    if a.kind in ("calendar_create", "calendar_update"):
        people = set(a.recipients) & (TAYLOR_EMAILS | CHARLIE_EMAILS)
        if people or about_taylor(a.text):
            return ("Do not add calendar events for Taylor Gonzalez's request: no case is opened, so there are no "
                    f"case deadlines, and the employee/manager may not be contacted. {why}")
    return None


# ---- confidentiality ----------------------------------------------------------------------------------------

def slack_phi_problem(ctx, a) -> str | None:
    if a.kind not in ("slack_post", "slack_dm") or not about_taylor(a.text):
        return None
    hits = _medical(a.text)
    return (f"Slack messages may not contain medical details or protected health information (found: "
            f"{', '.join(hits)}). Refer only to the employee name / case and general category.") if hits else None


def hr_only_problem(ctx, a) -> str | None:
    if a.kind != "email_send" or not case_email(a):
        return None
    # employee/manager are handled by legal.hold; the parent legal entity (General Counsel's office) is allowed
    out = sorted(x for x in _addrs(a) - HR_TEAM - TAYLOR_EMAILS - CHARLIE_EMAILS
                 if not x.endswith("@ridgelineholdings.com"))
    if out:
        return (f"Case-related emails (and forwarded threads with medical information) may go only to the HR team "
                f"(HR Director, Benefits Manager, HR Generalists, Payroll Lead, Safety & WC Coordinator, General "
                f"Counsel {GC_EMAIL}). Remove: {', '.join(out)}.")
    return None


# ---- 13 email housekeeping ------------------------------------------------------------------------------------

def _truthy(v) -> bool | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("true", "1", "yes")


def mail_flags(ctx) -> dict[str, dict]:
    """Per email id: read / important / moved, replayed in call order from the ledger."""
    flags: dict[str, dict] = {}
    pending: dict = {}
    for rec in ctx.state.records:
        if rec.get("type") == "action":
            pending[rec.get("call_id") or rec.get("id")] = (rec.get("tool", ""), rec.get("args") or {})
        elif rec.get("type") == "observation":
            tool, args = pending.pop(rec.get("call_id"), ("", {}))
            text = rec.get("text", "") or ""
            if re.search(r'"status"\s*:\s*"(error|failed)"|"error"\s*:\s*"[^"]', text):
                continue
            ids = [str(i) for i in (args.get("email_ids") or ([args["email_id"]] if args.get("email_id") else []))]
            for i in ids:
                f = flags.setdefault(i, {"read": False, "important": False, "moved": None})
                if tool == "google_mail__read_email":
                    f["read"] = True
                elif tool in ("google_mail__mark_emails", "google_mail__mark_email"):
                    r, imp = _truthy(args.get("is_read")), _truthy(args.get("is_important"))
                    f["read"] = f["read"] if r is None else r
                    f["important"] = f["important"] if imp is None else imp
                elif tool in ("google_mail__move_emails", "google_mail__move_email"):
                    folder = str(args.get("target_folder") or args.get("folder") or "")
                    f["moved"] = None if folder.lower() == "inbox" else folder
                elif tool in ("google_mail__delete_emails", "google_mail__delete_email", "google_mail__trash_emails"):
                    f["moved"] = "Trash"
    return flags


def housekeeping_checks(ctx):
    flags = mail_flags(ctx)
    req = flags.get(REQUEST_EMAIL_ID, {"read": False, "important": False, "moved": None})
    refs = [R_HOUSE, R_READ, R_INBOX, R_P1, R_STEP12]
    yield (req["read"], "Taylor Gonzalez's email \"Leave Request - HFWA\" (email id 1) is not marked as read. Mark it "
                        "read (google_mail__mark_emails email_ids [\"1\"], is_read true).", refs)
    yield (req["important"], "Taylor Gonzalez's email \"Leave Request - HFWA\" (email id 1) is a P1 case (legal "
                             "threat) and must be flagged important (google_mail__mark_emails email_ids [\"1\"], "
                             "is_important true) and left in the Inbox.", refs)
    yield (req["moved"] is None, f"Email id 1 was moved to \"{req['moved']}\"; P1 emails stay in the Inbox until the "
                                 "case is resolved - move it back to INBOX.", refs)
    head = flags.get(HEADS_UP_EMAIL_ID, {"read": False})
    yield (head["read"], "Charlie Szabo's email \"Heads Up — Taylor Gonzalez Absence April 8-9\" (email id 33) is a "
                         "processed leave-related email and must be marked as read.", [R_HOUSE, R_READ])


def keep_in_inbox_problem(ctx, a) -> str | None:
    if a.kind not in ("email_move", "email_delete"):
        return None
    if REQUEST_EMAIL_ID in a.recipients and not (a.kind == "email_move" and a.channel.lower() == "inbox"):
        return ("Email id 1 (Taylor Gonzalez, \"Leave Request - HFWA\") is a P1 case (legal threat): leave it in the "
                "Inbox flagged important; do not move or delete it until the case is resolved.")
    return None


# ---- workbooks ---------------------------------------------------------------------------------------------

def workbook_checks(ctx):
    w = world(ctx)
    changed = [f for f in w.changed_files() if re.search(SEED_BOOKS_RX, f.split("/")[-1], re.I)]
    yield (not changed, f"Workbooks were changed: {', '.join(changed)}. This request is under legal review as a NEW "
                        "request: do not open a case, log HFWA use or edit any tracker - restore the original "
                        "content.", [R_NO_CASE, R_GC, R_AUTH])


RULES = (
    comm_rules("legal", specs)
    + pre_rule("legal.hold", hold_problem,
               [R_NO_REPLY, R_NO_CASE, R_NO_RESPOND, R_GC, R_AUTH, R_NO_DM, R_DM2, R_NO_TAG, R_NEVER_MED,
                R_NEVER_OTHER, R_MGR_NOT, R_T11, R_QUOTE, R_PERSONAL, R_WAGE, R_WAGE2],
               "Do not send this; the only communications for this request are the #legal-review post and the "
               "email to General Counsel.")
    + forbid_writes("legal.no_case_writes", SEED_BOOKS_RX,
                    "this request is a legal threat on a new request (SOP 12.5 Step 4: do not open a new case); no "
                    "tracker, HFWA balance, history or FAMLI log entry may be written - General Counsel directs any "
                    "further handling.", [R_NO_CASE, R_GC, R_AUTH, R_DELETE])
    + forbid_writes("files.blank_forms", r"^WH-38\d|^CO_\w*Notice\.pdf$|^Ridgeline_HR_Leave_Coordinator_SOP\.pdf$",
                    "blank DOL forms and the SOP are never modified, and no FMLA notice (WH-381/WH-382) may be "
                    "prepared for a request under legal review.", [R_BLANK, R_NO_CASE])
    + state_rule("legal.workbooks_unchanged", workbook_checks, "Restore the workbooks to their original content.")
    + pre_rule("slack.no_phi", slack_phi_problem, [R_SLACK_PHI, R_SLACK_PHI2, R_NEVER_PHI, R_PAY_PHI],
               "Rewrite the message without medical details.")
    + pre_rule("email.hr_only", hr_only_problem, [R_CC, R_FWD_HR, R_NEVER_EXT, R_NEVER_OTHER, R_EMAIL_PHI],
               "Address the email only to HR team members.")
    + pre_rule("mail.keep_in_inbox", keep_in_inbox_problem, [R_INBOX, R_P1], "Leave the email in the Inbox.")
    + state_rule("mail.housekeeping", housekeeping_checks, "Complete the email housekeeping as listed.")
    + no_placeholders([R_PLACE])
)
