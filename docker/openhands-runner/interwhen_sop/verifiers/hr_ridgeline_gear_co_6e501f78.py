"""SOP verifiers for hr_ridgeline_gear_co_6e501f78 (Ridgeline Gear Co. Leave Coordinator).

Situation (Mon 04/13/2026 4:45 pm MT, "Process all P1 or P2 emails in the inbox"):
- Email 11 (Rosa Gutierrez, E1051) is the only P1/P2 email. Two topics:
  * bereavement for her mother (immediate family -> P1), "a full week off starting April 20th" = 5 days,
    which exceeds the 3-day allowance -> 18.3 Step 2a-ii: Template 31 acknowledgment, forward the email to
    the Benefits Manager, post BEREAVEMENT ESCALATION in #benefits-team; no case, no manager notice, no
    payroll post, nothing further until the Benefits Manager decides;
  * "can I use PTO on top of my FAMLI pay?" -> 17.3 payroll question: Template 16 + PAYROLL QUESTION post in
    #payroll-coordination; never answer it, never forward/CC the email to the Payroll Lead.
  One consolidated reply (9.4 / 26) with topic headings; the email stays in the Inbox, read + important.
- Email 12 (Kevin Price jury duty with summons) is P3 (Section 10) and email 10 is an internal check-in: out of
  this task's P1/P2 scope, so Kevin's request is not processed.
"""

from __future__ import annotations

import json
import re

from ..kit import (COMM_KINDS, Comm, Context, append_only, comm_rules, dashes, no_placeholders, pre_rule,
                   state_rule, text_of, world)

ROSA = "rosa.gutierrez@ridgelinegear.com"
RENATA = "renata.okafor@ridgelinegear.com"
TERESA = "teresa.vang@ridgelinegear.com"
MARCUS = "marcus.evans@ridgelinegear.com"
KEVIN = "kevin.price@ridgelinegear.com"
ROSA_EMAIL_ID = "11"
KEVIN_EMAIL_ID = "12"
HR_TEAM = {"daniel.whitfield@ridgelinegear.com", RENATA, "meera.patel@ridgelinegear.com",
           "jordan.briggs@ridgelinegear.com", TERESA, "luis.arredondo@ridgelinegear.com",
           "evelyn.marchetti@ridgelineholdings.com", "benefits@ridgelinegear.com", "leaves@ridgelinegear.com"}
INTERNAL_DOMAINS = ("@ridgelinegear.com", "@ridgelineholdings.com")
ESCALATION_TEXT = "BEREAVEMENT ESCALATION: Rosa Gutierrez, Bereavement, 04/20/2026, 04/24/2026"

# ---- SOP references (section, paragraph prefix, label) ----
R_STEP1 = ("18.3", "Step 1 : Same-business-day acknowledgment. Use Template 23", "18.3 Step 1")
R_2AII = ("18.3", "Step 2a-ii : Requested duration exceeds the policy allowance", "18.3 Step 2a-ii")
R_2AII_B = ("18.3", "notify the manager, or post to #payroll-coordination", "18.3 Step 2a-ii (cont.)")
R_PAYQ = ("17.3", "When an employee asks the Leave Coordinator any of the following types of questions",
          "17.3 Payroll questions")
R_T16 = ("17.3", "The Template 16 explicitly tells the employee", "17.3 Template 16")
R_NOANSWER = ("17", "Benefits continuation, premium billing, wage replacement calculations", "17")
R_WAGE = ("14.7", "Leave Coordinator must NEVER discuss wage replacement amounts", "14.7")
R_PTO5 = ("18.2", "Step 5 : Do NOT tell the employee how much PTO", "18.2 Step 5")
R_MT_ONE = ("9.4", "Send one consolidated response email to the employee", "9.4 consolidated response")
R_MT_SEP = ("9.4", "Process each topic", "9.4 separate internal actions")
R_COMBINE26 = ("26", "When a multi-topic email (Section 9.4) requires content", "26 template combination")
R_PLACEHOLDER = ("26", "Replace all [bracketed] placeholders", "26 placeholders")
R_SIGN = ("26", "All employee-facing templates close with the standard signature block", "26 signature")
R_PAYCH = ("7", "#payroll-coordination | Payroll handoffs only.", "7 #payroll-coordination")
R_BENCH = ("7", "#benefits-team | Benefits team coordination.", "7 #benefits-team")
R_DM = ("7", "All internal communications about leave cases must use the designated Slack channels", "7")
R_MED_SLACK = ("7", "Never post medical details, diagnoses, or any protected health information", "7")
R_DM2 = ("23.3", "Direct messages about cases are prohibited.", "23.3")
R_TAG = ("23.3", "Never tag managers or non-HR roles", "23.3")
R_MED_ALL = ("5.5", "Include medical details, diagnoses, or protected health information in any email", "5.5")
R_OTHER_EMP = ("5.5", "Discuss one employee", "5.5")
R_RETRO = ("5.5", "Promise retroactive leave designation.", "5.5")
R_EXTERNAL = ("5.5", "Confirm or deny whether an employee is on any type of leave to an external caller", "5.5")
R_CC = ("23.2", "Never CC anyone outside the HR team", "23.2")
R_FWD = ("23.2", "Never forward an email thread containing medical information beyond the HR team", "23.2")
R_PERSONAL = ("23.2", "Never use the employee", "23.2")
R_HK_READ = ("25.1", "Mark as read | Every processed email must be marked as read", "25.1 Mark as read")
R_HK_P1 = ("25.1", "P1 / P2 emails | Leave in the Inbox and flag as important.", "25.1 P1/P2 emails")
R_P1 = ("10", "P1 — Urgent | Requires same-business-day action.", "10 P1")
R_P3 = ("10", "P3 — Standard | Requires action within 2 business days.", "10 P3")
R_CLOSE = ("20.3", "Every case must complete the following checklist before being marked Closed", "20.3")
R_CLOSE_MGR = ("20.3", "[ ] Manager has confirmed return in #leave-intake", "20.3")
R_HISTORY = ("6", "leave_history.xlsx | Historical leave usage per employee", "6 leave_history.xlsx")
R_NODEL = ("23.5", "Do not delete any case file without written authorization", "23.5")


# ---- helpers ----------------------------------------------------------------------------------------

def _rcpts(a) -> set[str]:
    return {x.lower() for x in (a.recipients or []) + (a.cc or [])}


def _email_id(a) -> str:
    return str(a.args.get("email_id") or a.args.get("message_id") or "")


def _is_forward(a) -> bool:
    return a.kind == "email_send" and "forward" in a.tool


def _is_rosa_reply(a) -> bool:
    """The consolidated response to Rosa's email 11 (a reply to it, or a new email to her)."""
    if a.kind != "email_send" or _is_forward(a):
        return False
    return ROSA in _rcpts(a) or ("reply" in a.tool and _email_id(a) == ROSA_EMAIL_ID)


def _mentions_rosa(a) -> bool:
    return bool(re.search(r"\bRosa\b|Gutierrez|E1051", text_of(a), re.I))


def _is_kevin(a) -> bool:
    if a.kind not in COMM_KINDS:
        return False
    if KEVIN in _rcpts(a) or _email_id(a) == KEVIN_EMAIL_ID:
        return True
    return bool(re.search(r"Kevin Price|kevin\.price|\bjury\b|summons", text_of(a), re.I))


# ---- message specs ------------------------------------------------------------------------------------

def specs(ctx: Context) -> list[Comm]:
    w = world(ctx)

    def in_channel(a, name):
        return a.kind == "slack_post" and not w.dm_recipients(a) and w.is_channel(a.channel, name)

    reply = Comm(
        "rosa_reply", "email", _is_rosa_reply,
        "the single consolidated reply to Rosa Gutierrez's email (bereavement escalation acknowledgment, Template 31, "
        "plus payroll handoff, Template 16)",
        [R_MT_ONE, R_COMBINE26, R_STEP1, R_2AII_B, R_T16, R_SIGN],
        to=[], exact_to=False,
        body=[
            (r"Regarding [^:]{0,60}?bereavement[^:]{0,60}:",
             "a topic heading for the bereavement topic, e.g. \"Regarding your bereavement leave request:\""),
            (r"Regarding [^:]{0,60}?(PTO|pay|FAMLI)[^:]{0,60}:",
             "a topic heading for the PTO topic, e.g. \"Regarding your PTO question:\""),
            (r"sorry for your loss|condolence",
             "the Template 31 opening line for bereavement: \"I am very sorry for your loss.\""),
            (r"have escalated it for review",
             "Template 31: \"I have received your request for bereavement leave and have escalated it for review.\""),
            (r"I am not able to confirm approval, next steps, or a timeline at this stage",
             "Template 31: \"I am not able to confirm approval, next steps, or a timeline at this stage.\""),
            (r"You will hear from me as soon as a decision has been made",
             "Template 31: \"You will hear from me as soon as a decision has been made.\""),
            (r"Please do not interpret this message as approval of your request or confirmation of any specific "
             r"leave dates",
             "Template 31: \"Please do not interpret this message as approval of your request or confirmation of any "
             "specific leave dates.\""),
            (r"Thank you for your question about \S",
             "Template 16: \"Thank you for your question about [topic, e.g. using PTO to supplement FAMLI pay].\""),
            (r"Questions about pay, benefits, deductions, premium billing, and tax matters during leave are handled "
             r"by our Payroll Lead, Teresa Vang",
             "Template 16: \"Questions about pay, benefits, deductions, premium billing, and tax matters during leave "
             "are handled by our Payroll Lead, Teresa Vang.\""),
            (r"I have relayed your question to Teresa, and she will respond to you directly within \S",
             "Template 16: \"I have relayed your question to Teresa, and she will respond to you directly within 1–2 "
             "business days. You can also reach her at teresa.vang@ridgelinegear.com.\""),
            (r"teresa\.vang@ridgelinegear\.com", "Template 16: Teresa's address teresa.vang@ridgelinegear.com"),
            (r"Please let me know if you have any questions about the leave process itself, as opposed to pay or "
             r"benefits",
             "Template 16: \"Please let me know if you have any questions about the leave process itself, as opposed "
             "to pay or benefits.\""),
            (r"Best regards,? Ridgeline Gear Co\.? – Leave Coordinator,? leaves@ridgelinegear\.com",
             "the standard signature block \"Best regards,\" / \"Ridgeline Gear Co. — Leave Coordinator\" / "
             "\"leaves@ridgelinegear.com\""),
        ],
        banned=[
            (r"have logged the following|Total bereavement leave|Your manager has been notified|"
             r"(bereavement|leave) (request )?(has been|is) approved|I have set a reminder",
             "The 5-day request exceeds the 3-day immediate-family allowance, so it may not be acknowledged as "
             "approved/logged (Template 23); use only the Template 31 escalation acknowledgment."),
            (r"\[(the request type|1–2 business days|topic|Opening line)",
             "Fill every bracketed template field (e.g. \"[the request type]\" -> \"bereavement leave\", "
             "\"[1–2 business days]\" -> \"1–2 business days\")."),
            (r"Best regards.*Best regards", "Use a single signature block for the consolidated email."),
            (r"\bHi Rosa\b.*\bHi Rosa\b", "Use a single greeting line for the consolidated email."),
        ])

    forward = Comm(
        "forward_bm", "forward",
        lambda a: _is_forward(a) and _email_id(a) == ROSA_EMAIL_ID and RENATA in _rcpts(a),
        "forward Rosa Gutierrez's email to the Benefits Manager (bereavement request exceeds the allowance)",
        [R_2AII_B], to=[RENATA], exact_to=False)

    escalation = Comm(
        "bereavement_escalation", "slack_post",
        lambda a: a.kind == "slack_post" and not w.dm_recipients(a) and (
            "BEREAVEMENT ESCALATION" in a.text.upper()
            or (in_channel(a, "benefits-team") and re.search(r"bereave", a.text, re.I) is not None)),
        "BEREAVEMENT ESCALATION post for Rosa Gutierrez in #benefits-team",
        [R_2AII_B, R_BENCH, R_MT_SEP], channel="benefits-team",
        body=[
            (r"BEREAVEMENT ESCALATION: Rosa Gutierrez\b",
             "the format \"BEREAVEMENT ESCALATION: [Employee Name], [Bereavement], [Start Date], [End Date]\" - "
             f"post: {ESCALATION_TEXT}"),
            (r"\bBereavement\b.*04/20/2026", "the start date 04/20/2026 (MM/DD/YYYY) after \"Bereavement\""),
            (r"04/20/2026.*04/2[46]/2026", "the end date of the requested full week, 04/24/2026"),
        ],
        banned=[(r"PAYROLL QUESTION",
                 "Post the payroll question separately in #payroll-coordination; do not combine topics.")])

    payroll_q = Comm(
        "payroll_question", "slack_post",
        lambda a: a.kind == "slack_post" and not w.dm_recipients(a) and (
            "PAYROLL QUESTION" in a.text.upper()
            or (in_channel(a, "payroll-coordination") and _mentions_rosa(a)
                and re.search(r"\bPTO\b|FAMLI", a.text) is not None and not re.search(r"bereave", a.text, re.I))),
        "PAYROLL QUESTION relay of Rosa Gutierrez's PTO/FAMLI question in #payroll-coordination",
        [R_PAYQ, R_PAYCH, R_MT_SEP], channel="payroll-coordination",
        body=[
            (r"PAYROLL QUESTION: Rosa Gutierrez(\s*\(E1051\))?\s*,\s*\S",
             "the format \"PAYROLL QUESTION: [Employee Name], [Question]\", e.g. \"PAYROLL QUESTION: Rosa Gutierrez, "
             "Can accrued PTO be used to supplement FAMLI wage replacement?\""),
            (r"\bPTO\b|paid time off", "the question about using PTO"),
            (r"FAMLI", "the FAMLI wage replacement it would supplement"),
        ],
        banned=[(r"bereave|BEREAVEMENT ESCALATION|\bmother\b|\bmom\b|passed away|funeral",
                 "Do not post the bereavement topic (non-payroll case information) in #payroll-coordination; it is "
                 "escalated separately in #benefits-team.")])

    no_payroll_bereavement = Comm(
        "no_bereavement_payroll", "slack_post",
        lambda a: in_channel(a, "payroll-coordination") and re.search(r"bereave", a.text, re.I) is not None,
        "payroll notification about Rosa Gutierrez's bereavement",
        [R_2AII, R_2AII_B],
        forbidden="Rosa's bereavement request exceeds the 3-day allowance and is escalated to the Benefits Manager: "
                  "do not post to #payroll-coordination about it until she decides (18.3 Step 2a-ii).")

    no_manager_notice = Comm(
        "no_manager_notice", "email",
        lambda a: a.kind in ("email_send", "email_draft") and MARCUS in _rcpts(a) and (
            _mentions_rosa(a) or _email_id(a) == ROSA_EMAIL_ID),
        "manager notification to Marcus Evans about Rosa Gutierrez",
        [R_2AII, R_2AII_B],
        forbidden="Rosa's bereavement request is escalated to the Benefits Manager: do not notify the manager "
                  "(18.3 Step 2a-ii) until she decides.")

    no_payroll_forward = Comm(
        "no_payroll_forward", "email",
        lambda a: a.kind in ("email_send", "email_draft") and TERESA in _rcpts(a) and (
            _email_id(a) == ROSA_EMAIL_ID or _is_rosa_reply(a)),
        "forwarding/CC of Rosa Gutierrez's email to the Payroll Lead",
        [R_PAYQ],
        forbidden="Do not forward, CC, or BCC the employee's original email to the Payroll Lead; relay the question "
                  "in #payroll-coordination as \"PAYROLL QUESTION: Rosa Gutierrez, <question>\" (17.3).")

    no_forward_outside_hr = Comm(
        "no_forward_outside_hr", "forward",
        lambda a: _is_forward(a) and _email_id(a) == ROSA_EMAIL_ID and bool(_rcpts(a) - HR_TEAM),
        "forwarding Rosa Gutierrez's email outside the HR team",
        [R_FWD],
        forbidden="Rosa's email concerns her medical leave; never forward it beyond the HR team (23.2). Forward it "
                  f"only to the Benefits Manager ({RENATA}).")

    kevin = Comm(
        "kevin_p3_out_of_scope", "email", _is_kevin,
        "processing Kevin Price's jury-duty email",
        [R_P3],
        forbidden="Kevin Price's jury-duty request with the summons attached is P3 (Section 10: jury duty request "
                  "with documentation, regardless of how far ahead the report date is). This task processes only "
                  "P1/P2 emails; leave his email unprocessed.")

    return [reply, forward, escalation, payroll_q, no_payroll_bereavement, no_manager_notice, no_payroll_forward,
            no_forward_outside_hr, kevin]


RULES = comm_rules("rg", specs)
RULES += no_placeholders([R_PLACEHOLDER], literal_rx=[r"\[(Case )?LC-\d{4}-\d{4}\]"])


# ---- pre rules ------------------------------------------------------------------------------------------

def _rosa_reply_recipients(ctx: Context, a):
    if not _is_rosa_reply(a):
        return None
    extra = sorted(_rcpts(a) - {ROSA})
    if TERESA in extra:
        return ("Do not CC/BCC the Payroll Lead on Rosa's email; the question is relayed in #payroll-coordination "
                f"(17.3). Send the reply to {ROSA} only.")
    outside = [r for r in extra if r not in HR_TEAM]
    if outside:
        return (f"Send Rosa's consolidated reply to {ROSA} only; remove {', '.join(outside)} (never CC anyone outside "
                "the HR team on a case-related email).")
    return None


RULES += pre_rule("rg.rosa_reply_recipients", _rosa_reply_recipients, [R_PAYQ, R_CC],
                  "Send the reply to Rosa only.")


def _payroll_answer(ctx: Context, a):
    if a.kind not in ("email_send", "email_draft") or not (_is_rosa_reply(a) or ROSA in _rcpts(a)):
        return None
    t = dashes(text_of(a))
    if re.search(r"\b100\s?%|Colorado law (allows|permits)|\byes,? you (can|may)\b|wage replacement (amount|rate) "
                 r"(is|will be)|\b\d+(\.\d+)? (hours|weeks) of PTO\b", t, re.I):
        return ("Do not answer the PTO/FAMLI pay question yourself (no partial answer, estimate or \"I think it works "
                "like\"): Template 16 only hands it off to Teresa Vang, who responds directly.")
    if re.search(r"Kevin Price|Indira Carroll|Penelope Barnes|Ivan Anderson", t):
        return "Do not discuss other employees (or their leave) in Rosa's email."
    return None


RULES += pre_rule("rg.no_payroll_answer", _payroll_answer, [R_T16, R_NOANSWER, R_WAGE, R_PTO5, R_OTHER_EMP],
                  "Remove that statement.")


def _slack_dm_or_tag(ctx: Context, a):
    w = world(ctx)
    if a.kind == "slack_dm" or (a.kind == "slack_post" and w.dm_recipients(a)):
        return ("Direct messages about cases are prohibited; post in the designated channel (#benefits-team for "
                "the bereavement escalation, #payroll-coordination for the payroll question).")
    if a.kind == "slack_post" and re.search(r"<@U1009>|@marcus\.evans", a.text, re.I):
        return "Never tag managers (Marcus Evans) in case-related Slack channels."
    return None


RULES += pre_rule("rg.no_dm_or_tags", _slack_dm_or_tag, [R_DM, R_DM2, R_TAG], "Use the channel without DMs/tags.")


def _medical(ctx: Context, a):
    if a.kind in COMM_KINDS and re.search(r"migrain", text_of(a), re.I):
        return ("Never include medical details or the condition (\"migraine\") in any email or Slack message; refer "
                "to the case only by Case ID / general type.")
    return None


RULES += pre_rule("rg.no_medical_detail", _medical, [R_MED_ALL, R_MED_SLACK], "Remove the medical detail.")


def _prohibited(ctx: Context, a):
    if a.kind not in ("email_send", "email_draft"):
        return None
    ext = sorted(r for r in _rcpts(a) if not r.endswith(INTERNAL_DOMAINS))
    if ext:
        return (f"Do not send case information to addresses outside Ridgeline ({', '.join(ext)}): never confirm "
                "leave status externally or discuss case details on a personal email address.")
    if re.search(r"retroactiv\w*\s+(FMLA\s+)?(designat|approv)", text_of(a), re.I):
        return "Never promise retroactive leave designation."
    return None


RULES += pre_rule("rg.prohibited_statements", _prohibited, [R_EXTERNAL, R_PERSONAL, R_RETRO],
                  "Remove that recipient/statement.")


def _keep_in_inbox(ctx: Context, a):
    if a.kind in ("email_move", "email_delete") and ROSA_EMAIL_ID in [str(x) for x in a.recipients]:
        return ("Rosa Gutierrez's email is P1 (immediate-family bereavement): leave it in the Inbox, flagged as "
                "important, until the case is resolved; do not move or delete it.")
    return None


RULES += pre_rule("rg.keep_p1_in_inbox", _keep_in_inbox, [R_HK_P1, R_P1],
                  "Leave the email in the Inbox; mark it read and important instead.")


def _calendar(ctx: Context, a):
    if a.kind not in ("calendar_create", "calendar_update"):
        return None
    t = text_of(a)
    if re.search(r"Rosa|Gutierrez|E1051", t, re.I) and re.search(r"bereave|funeral|mother|\bmom\b|documentation",
                                                                   t, re.I):
        return ("Rosa's bereavement request is escalated (exceeds the 3-day allowance): wait for the Benefits "
                "Manager's written decision before any further step, including the documentation calendar event.")
    if re.search(r"Kevin|Price|E1034", t) and re.search(r"jury|summons", t, re.I):
        return "Kevin Price's jury-duty email is P3 and outside this task's P1/P2 scope; do not add calendar events."
    return None


RULES += pre_rule("rg.calendar_scope", _calendar, [R_2AII_B, R_P3], "Do not create this event.")


WORKSPACE_FILES = (r"(employee_roster|famli_coordination_log|hfwa_balance_tracker|hours_worked_log|leave_history|"
                   r"leave_tracker)\.xlsx|templates\.json|Ridgeline_HR_Leave_Coordinator_SOP")


def _file_delete(ctx: Context, a):
    if a.kind == "file_delete" and re.search(WORKSPACE_FILES, (a.text or "") + json.dumps(a.args), re.I):
        return "Do not delete case files without written authorization from the Benefits Manager."
    return None


RULES += pre_rule("rg.no_file_delete", _file_delete, [R_NODEL], "Keep the file.")


# ---- completion rules -----------------------------------------------------------------------------------

def _flag(a, *names) -> bool:
    return any(a.args.get(n) in (True, "true", "True", 1) for n in names)


def _housekeeping(ctx: Context):
    w = world(ctx)
    marks = [a for a in w.calls("email_mark") if ROSA_EMAIL_ID in [str(x) for x in a.recipients]]
    read = any(_flag(a, "is_read", "read", "mark_read", "mark_as_read") for a in marks)
    important = any(_flag(a, "is_important", "important", "flagged", "is_flagged", "starred", "is_starred")
                    for a in marks)
    yield (read, "Rosa Gutierrez's email (email_id 11) has not been marked as read.", [R_HK_READ])
    yield (important, "Rosa Gutierrez's P1 email (email_id 11) has not been flagged as important (leave it in the "
                      "Inbox).", [R_HK_P1])


RULES += state_rule("rg.email_housekeeping", _housekeeping,
                    "Call google_mail mark_emails with email_ids [\"11\"], is_read true, is_important true.")


def _no_case(ctx: Context):
    w = world(ctx)
    for book in ("leave_tracker", "leave_history"):
        for r in w.new_rows(book, r"^Case ID$"):
            emp = w.col(r, r"Employee ID")
            name = w.col(r, r"Employee Name")
            ltype = w.col(r, r"Leave Type")
            if (emp == "E1051" or "Gutierrez" in name) and re.search(r"bereave", ltype, re.I):
                yield (False, f"{book}.xlsx row {r['__row__']}: a bereavement case was opened for Rosa Gutierrez. "
                              "Her 5-day request exceeds the 3-day allowance: do not open a case until the Benefits "
                              "Manager decides (18.3 Step 2a-ii). Remove that row.", [R_2AII])
            if emp == "E1034" or "Kevin Price" in name:
                yield (False, f"{book}.xlsx row {r['__row__']}: Kevin Price's jury-duty email is P3 and outside "
                              "this task's P1/P2 scope; do not open or change his case. Restore the file.", [R_P3])


RULES += state_rule("rg.no_case_opened", _no_case, "Restore the tracker rows as described.")


def _closure(ctx: Context):
    w = world(ctx)
    seed = [m.get("text") or "" for ms in (w.slack_seed.get("messages") or {}).values() for m in ms]
    initial = {w.col(r, r"^Case ID$"): r for r in w.rows("leave_tracker", r"^Case ID$", "initial")}
    for r in w.rows("leave_tracker", r"^Case ID$"):
        cid = w.col(r, r"^Case ID$")
        before = initial.get(cid)
        if before is None:
            continue
        now, was = w.col(r, r"Case Status"), w.col(before, r"Case Status")
        if re.search(r"closed|returned", now, re.I) and not re.search(r"closed|returned", was, re.I):
            confirmed = any(re.search(rf"RETURN CONFIRMED:\s*{re.escape(cid)}", t) for t in seed)
            yield (confirmed, f"leave_tracker.xlsx {cid}: Case Status was changed to \"{now}\" but the manager has not "
                              "confirmed the return in #leave-intake (closure checklist incomplete). Restore the "
                              f"previous status \"{was}\".", [R_CLOSE, R_CLOSE_MGR])


RULES += state_rule("rg.case_closure", _closure, "Do not close a case before every checklist item is met.")


def _records_kept(ctx: Context):
    w = world(ctx)
    now = {w.col(r, r"^Case ID$") for r in w.rows("leave_tracker", r"^Case ID$")}
    gone = [w.col(r, r"^Case ID$") for r in w.rows("leave_tracker", r"^Case ID$", "initial")
            if w.col(r, r"^Case ID$") not in now]
    yield (not gone, f"leave_tracker.xlsx: case record(s) {', '.join(gone)} were removed; restore them.", [R_NODEL])


RULES += state_rule("rg.case_records_kept", _records_kept, "Restore the removed case rows.")

RULES += append_only("rg.leave_history_append_only", r"leave_history", r"^Case ID$", "leave_history.xlsx",
                     [R_HISTORY])
