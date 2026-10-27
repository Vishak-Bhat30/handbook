"""Verifiers for hr_ridgeline_gear_co_6950ff2b - Portia Nzinga (EMP-1222) medical leave intake (email 106).

Facts from the seed data: Portia is non-exempt, 0.5 FTE, hired 2021-01-11, 1,018 actual hours in the rolling
12 months (hours_worked_log.xlsx) -> FMLA-ineligible on hours, a denial the LC may issue alone (SOP 5.1, 13.9,
21.2). The SOP path is: WH-381 (not eligible) saved to EMP-1222/, Template 3 to Portia with the Benefits Manager
CC'd, the denied FMLA row kept in leave_tracker.xlsx, a NEW FAMLI-only row (Leave Type "FAMLI", status
"Intake"), Template 31 to Portia, famli_coordination_log tracking, "FMLA DENIED (INELIGIBILITY)" in #leave-intake,
and housekeeping of email 106 (P3 -> mark read, move to "FAMLI Cases"). Ridgeline never files the FAMLI claim.
pnzinga@gmail.com is not in the mail contacts (sends to it bounce), so the hints name her work address.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable

from ..kit import (COMM_KINDS, WRITE_KINDS, Action, Comm, Context, Finding, Rule, World, append_only, attachments,
                   cites, comm_rules, dashes, nh, no_placeholders, norm, registry, same, state_rule, strict_writes,
                   text_of, world)

EMP = "EMP-1222"
WORK = "p.nzinga@ridgelinegear.com"
PORTIA = {WORK, "pnzinga@gmail.com"}
MANAGER = "t.mbeki@ridgelinegear.com"
BM = "r.okafor@ridgelinegear.com"
HR_TEAM = {"m.hale@ridgelinegear.com", "leaves@ridgelinegear.com", "benefits@ridgelinegear.com",
           "hrdirector@ridgelinegear.com", "hrteam@ridgelinegear.com", "d.whitfield@ridgelinegear.com",
           "daniel.whitfield@ridgelinegear.com", BM, "m.patel@ridgelinegear.com", "j.briggs@ridgelinegear.com",
           "t.vang@ridgelinegear.com", "teresa.vang@ridgelinegear.com", "l.arredondo@ridgelinegear.com",
           "evelyn.marchetti@ridgelineholdings.com", "d.marceau@ridgelinegear.com", "o.hassan@ridgelinegear.com",
           "famli-employer@ridgelinegear.com"}
CDLE = re.compile(r"cdle|famli\.colorado\.gov|state\.co\.us", re.I)
INTAKE_ID = "106"
START = "2026-05-14"
FOLDERS = ("FMLA Cases", "FAMLI Cases", "ADA Intake", "HFWA & Paid Leave", "Personal/Military Leave", "Closed Cases",
           "Unknown Senders", "General")
MENTION = re.compile(r"Portia|Nzinga|EMP-1222|pnzinga|p\.nzinga", re.I)
MEDICAL = re.compile(r"kidney|renal|nephr|dialys|transplant|surg(?:ery|ical|eon)", re.I)
REASON = re.compile(r"medical leave|serious health|health condition|personal health", re.I)
T3_LITERAL = re.compile(r"NOT\s+currently\s+eligible\s+for\s+FMLA", re.I)
T3RX = re.compile(r"not\s+(?:currently\s+)?eligible\s+for\s+FMLA", re.I)
T31RX = re.compile(r"administered under Colorado FAMLI|Leave Request Received|claims@famli\.colorado\.gov", re.I)
ELIGIBLE = re.compile(r"confirmed that you ARE eligible|DESIGNATED as FMLA|(?<!believe )(?<!if )\byou are eligible "
                      r"for FMLA", re.I)
FAMLI_DENIAL = re.compile(r"\bnot\s+(?:currently\s+)?eligible\s+(?:for|under)\s+(?:Colorado\s+)?FAMLI|FAMLI\s+"
                          r"(?:claim|leave|request)\s+(?:is|has\s+been)\s+denied", re.I)
CASE = re.compile(r"LC-\d{4}-\d{4}")
TRACKER, SHEET, HDR = r"leave_tracker\.xlsx$", r"^Active Cases$", r"^Case ID$"
FLOG, FHDR = r"famli_coordination_log\.xlsx$", r"^FAMLI Claim ID"

# ---- SOP references (section, paragraph prefix, label) --------------------------------------------------
R_DATES = ("3.1", "All times in this document are in Mountain Time", "§3.1 Dates")
R_LOG_USAGE = ("5.1", "Log leave usage in leave_tracker.xlsx", "§5.1")
R_DENY_LC = ("5.1", "Deny FMLA leave on the basis of clear ineligibility only", "§5.1")
R_FAMLI_DENY = ("5.2", "Any FMLA or FAMLI denial other than clear ineligibility", "§5.2")
R_NO_DISCLOSE = ("5.5", "Disclose any employee medical information", "§5.5")
R_NO_CONFIRM = ("5.5", "Confirm or deny whether an employee is on any type of leave", "§5.5")
R_NO_DISCUSS = ("5.5", "Discuss one employee's leave with another employee", "§5.5")
R_NO_MEDICAL = ("5.5", "Include medical details, diagnoses, or protected health information", "§5.5")
R_ROSTER = ("6", "Source Contents When to Use employee_roster.xlsx", "§6 Tools")
R_HOURS_SRC = ("6", "Status, Residence State. hours_worked_log.xlsx", "§6 Tools")
R_BLANK_FORMS = ("40", "CO_FAMLI_Employee_Notic Never modify", "§6 Tools")
R_NO_DM = ("7", "All internal communications about leave cases must use", "§7")
R_INTAKE_CH = ("7", "Channel When to Use #leave-intake", "§7")
R_SLACK_MED = ("7", "Never post medical details, diagnoses", "§7")
R_STEP7 = ("9.1", "Step 7: Assign a priority level", "§9.1 Step 7")
R_STEP8 = ("9.1", "Step 8: If a new case is needed", "§9.1 Step 8")
R_STEP9 = ("9.1", "Step 9: Act per the relevant section", "§9.1 Step 9")
R_STEP10 = ("9.1", "Step 10: Post a case notification", "§9.1 Step 10")
R_STEP12 = ("9.1", "Step 12: Complete email housekeeping", "§9.1 Step 12")
R_MIN_ID = ("9.2", "Employee identity: full name and Employee ID", "§9.2")
R_MIN_START = ("9.2", "Requested leave start date", "§9.2")
R_NO_DIAG = ("9.2", "Reason category only", "§9.2")
R_MIN_FORESEE = ("9.2", "Whether the need is foreseeable", "§9.2")
R_MIN_MGR = ("9.2", "Manager name (retrieve from employee_roster.xlsx", "§9.2")
R_MIN_CONTACT = ("9.2", "Contact preference during leave", "§9.2")
R_PRIO = ("10", "Every case must be assigned a priority at intake", "§10")
R_P3 = ("3", "P3 - Requires action within 2 business", "§10 Priority Matrix (P3)")
R_SEND_NOW = ("11.1", "CRITICAL (Leave Coordinator only)", "§11.1")
R_HOURS_FILE = ("13.1", "Step 3. Open hours_worked_log.xlsx", "§13.1 Step 3")
R_HOURS = ("13.1", "Step 4. If hours worked in the preceding 12 months", "§13.1 Step 4")
R_INELIG = ("13.1", "Step 6. If any criterion is not met", "§13.1 Step 6")
R_FAMLI_STILL = ("13.1", "An employee may still be eligible for Colorado FAMLI", "§13.1")
R_WH381_FILL = ("13.4", "Step 1: Open the blank WH-381 PDF", "§13.4 Step 1")
R_WH381_SAVE = ("13.4", "Step 2: Save the completed WH-381", "§13.4 Step 2")
R_T2 = ("13.4", "Step 3: Send the completed WH-381 to the employee via email using Template 2", "§13.4 Step 3")
R_WH380 = ("13.4", "Step 4: If the employee IS eligible", "§13.4 Step 4")
R_TRACK = ("13.7", "Every FMLA case must be tracked in leave_tracker.xlsx", "§13.7")
R_CASE_ID = ("13.7", "Case ID (generated at intake", "§13.7")
R_F_EMPID = ("13.7", "Employee ID.", "§13.7")
R_F_TYPE = ("13.7", "Leave Type(s) - list all applicable", "§13.7")
R_F_START = ("13.7", "Start Date (requested or actual leave start)", "§13.7")
R_F_ACTEND = ("13.7", "Actual End Date (blank until closure)", "§13.7")
R_F_HOURS = ("13.7", "Hours Used To Date.", "§13.7")
R_F_MGR = ("13.7", "Manager Name.", "§13.7")
R_F_PRIO = ("13.7", "Priority (P1/P2/P3/P4).", "§13.7")
R_F_STATUS = ("13.7", "Case Status - Intake", "§13.7")
R_F_NOTES = ("13.7", "Notes (running log of every action", "§13.7")
R_F_FORESEE = ("13.7", "Foreseeable / Unforeseeable - whether", "§13.7")
R_F_CONTACT = ("13.7", "Contact Preference - employee's preferred", "§13.7")
R_INTAKE = ("13.7", "At intake: populate Case ID", "§13.7 update rules")
R_LC_HOURS = ("13.9", "Ineligibility due to insufficient hours", "§13.9")
R_T3 = ("13.9", "Step 2. For LC-level denials", "§13.9 Step 2")
R_DENIED_LOG = ("13.9", "Step 4. Log denial in leave_tracker.xlsx", "§13.9 Step 4")
R_WAGE_CDLE = ("14.1", "Wage replacement under FAMLI is paid by CDLE", "§14.1")
R_NO_FILE = ("14.1", "FAMLI claims are filed by the employee directly with CDLE", "§14.1")
R_FAMLI_IMPL = ("14.2", "Implication: Many employees who are NOT eligible", "§14.2")
R_ONLY_ONE = ("14.3", "If the employee is eligible for only one of the two laws", "§14.3")
R_CDLE_STEP1 = ("14.5", "Step 1: Employees file FAMLI claims directly with CDLE", "§14.5 Step 1")
R_LOG_STEP4 = ("14.5", "Step 4: Open famli_coordination_log.xlsx", "§14.5 Step 4")
R_FAMLI_ROW = ("14.6", "Open a Case ID in leave_tracker.xlsx with Leave Type", "§14.6")
R_FAMLI_STATUS = ("14.6", "Set initial Case Status", "§14.6")
R_T31 = ("14.6", "Reply to the employee using Template 31", "§14.6")
R_FAMLI_LOG = ("14.6", "Track in famli_coordination_log.xlsx", "§14.6")
R_NO_FMLA_NOTICE = ("14.6", "Do NOT send FMLA notices", "§14.6")
R_WAGE = ("14.7", "Leave Coordinator must NEVER discuss wage replacement", "§14.7")
R_MGR_NO_DX = ("16.1", "The specific medical condition, diagnosis, or treatment.", "§16.1")
R_MGR_REASON = ("16.2", "The Manager Leave Notification must NEVER include", "§16.2")
R_PAYROLL_REASON = ("17.2", "Do not include medical details, diagnoses, or the reason category", "§17.2")
R_BENEFITS = ("17.4", "The LC's only role in benefits continuation", "§17.4")
R_HFWA_LOG = ("18.1", "Step 7: Log the HFWA use in hfwa_balance_tracker.xlsx", "§18.1 Step 7")
R_RECAP_BM = ("21.1", "Denials requiring Benefits Manager approval", "§21.1")
R_212_S1 = ("21.2", "Step 1: Confirm the specific failed criterion", "§21.2 Step 1")
R_212_S2 = ("21.2", "Step 2: Prepare the WH-381", "§21.2 Step 2")
R_212_S3 = ("21.2", "Step 3: Send the denial using Template 3", "§21.2 Step 3")
R_212_S4 = ("21.2", "Step 4: Update leave_tracker.xlsx: Case Status = Denied", "§21.2 Step 4")
R_212_S5 = ("21.2", "Step 5: Check FAMLI eligibility separately", "§21.2 Step 5")
R_212_KEEP = ("14.6", "intact as the record of the FMLA ineligibility", "§21.2 Step 5")
R_212_S6 = ("14.6", "Step 6: Post to #leave-intake: FMLA DENIED", "§21.2 Step 6")
R_NAMING = ("23.1", "File naming conventions", "§23.1")
R_EMAIL_MED = ("23.2", "Never include medical details, diagnoses, or protected health information in the body",
               "§23.2")
R_CC = ("23.2", "Never CC anyone outside the HR team", "§23.2")
R_FWD = ("23.2", "Never forward an email thread containing medical information", "§23.2")
R_QUOTE = ("23.2", "If an employee sends an email containing more medical detail", "§23.2")
R_PERSONAL = ("23.2", "Never use the employee's personal email", "§23.2")
R_SLACK_NO_MED = ("23.3", "Never post medical details, diagnoses, or protected health information in any Slack",
                  "§23.3")
R_SLACK_TAG = ("23.3", "Never tag managers or non-HR roles", "§23.3")
R_SLACK_DM = ("23.3", "Direct messages about cases are prohibited", "§23.3")
R_NO_DELETE = ("23.5", "Do not delete any case file", "§23.5")
R_NO_DESTROY = ("23.5", "When retention periods expire", "§23.5")
R_HOUSEKEEP = ("25", "After processing every leave-related email", "§25")
R_READ = ("25.1", "Rule Action Mark as read", "§25.1")
R_P3_MOVE = ("25.1", "P3 / P4 emails Move to the matching folder", "§25.1")
R_FOLDER = ("25.2", "FAMLI Cases All FAMLI-related emails", "§25.2")
R_FOLDER_NAMES = ("25.2", "Folder names must match exactly", "§25.2")
R_TEMPLATES = ("26", "Use templates as written", "§26")
R_PLACEHOLDERS = ("26", "Replace all [bracketed] placeholders", "§26")
R_TPL_NO_MED = ("26", "Do not add medical details", "§26")
R_TPL_SECTIONS = ("26", "Do not delete sections of a template", "§26")
R_SIGNATURE = ("26", "All employee-facing templates close with the standard signature", "§26")
R_TPL_JSON = ("26", "Template text is maintained in templates.json", "§26")


# ---- helpers ---------------------------------------------------------------------------------------------

def recips(a: Action) -> set[str]:
    out = {x.lower() for x in a.recipients + a.cc}
    if "reply" in a.tool and str(a.args.get("email_id")) == INTAKE_ID:
        out.add(WORK)
    return out


def to_portia(a: Action) -> bool:
    return bool(recips(a) & PORTIA)


def is_t3(a: Action) -> bool:
    t = text_of(a)
    return bool(T3_LITERAL.search(t) or (T3RX.search(t) and not T31RX.search(t)))


def case_rows(w: World) -> tuple[dict | None, dict | None, list[dict]]:
    """(denied FMLA row, FAMLI-only candidate row, all new EMP-1222 rows) in leave_tracker Active Cases."""
    def build():
        rows = [r for r in w.new_rows(TRACKER, HDR, SHEET) if norm(w.col(r, r"^Employee ID$")) == norm(EMP)]
        denied = [r for r in rows if re.search(r"denied", w.col(r, r"^Case Status$"), re.I)
                  and re.search(r"FMLA", w.col(r, r"^Leave Type"), re.I)]
        famli = [r for r in rows if r not in denied and re.search(r"FAMLI", w.col(r, r"^Leave Type"), re.I)]
        return (denied[0] if denied else None, famli[0] if famli else None, rows)
    return w.ctx.memo("t6950.case_rows", build)


def case_id(w: World, row: dict | None) -> str | None:
    return nh(w.col(row, r"^Case ID$")) if row else None


def used_ids(w: World) -> set[str]:
    """Case IDs already in use in the seed workbooks, mail, Slack and calendar."""
    def build():
        blob = json.dumps(w.initial) + json.dumps(w.seed_emails) + json.dumps(w.slack_seed) + json.dumps(w.seed_events)
        return set(CASE.findall(blob))
    return w.ctx.memo("t6950.used_ids", build)


def related(w: World, a: Action) -> bool:
    """The call concerns Portia's case (mentions her, is addressed to her, or touches email 106)."""
    ids = {i for i in (case_id(w, r) for r in case_rows(w)[:2]) if i}
    txt = f"{text_of(a)}\n{json.dumps(a.args, ensure_ascii=False)}"
    return (bool(MENTION.search(txt)) or bool(recips(a) & PORTIA) or str(a.args.get("email_id")) == INTAKE_ID
            or any(i in txt for i in ids))


def id_problems(w: World, got: str | None, want: str | None, other: str | None, what: str) -> list[str]:
    if not got:
        return [f"State the {what} Case ID (format LC-2026-NNNN)."]
    out = []
    if not re.fullmatch(r"LC-2026-\d{4}", got):
        out.append(f"Case ID {got} must use the format LC-2026-NNNN (§13.7).")
    if got in used_ids(w):
        out.append(f"Case ID {got} is already in use at Ridgeline; pick an unused LC-2026-NNNN (§13.7).")
    if want and got != want:
        out.append(f"Use the {what} Case ID logged in leave_tracker.xlsx: {want} (got {got}).")
    elif other and got == other:
        out.append(f"{got} is the other case; the {what} needs its own Case ID.")
    return out


def sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def pre(rule_id: str, fn: Callable[[Context, Action], list[tuple[str, list]]], fix: str) -> list[Rule]:
    """Pre-tool rule whose findings cite only the paragraphs relevant to each problem."""
    rules: list[Rule] = []

    @registry(rules)(rule_id, "pre", [])
    def check(ctx: Context, action: Action) -> list[Finding]:
        return [Finding(rule_id, cites(ctx, refs), msg, [fix]) for msg, refs in fn(ctx, action)]
    return rules


# ---- messages --------------------------------------------------------------------------------------------

@dataclass
class PComm(Comm):
    """Comm whose email checks are fully task-specific (recipients may be either of Portia's addresses)."""
    check: Callable[[Action, World], list[str]] | None = None

    def problems(self, a: Action, w: World) -> list[str]:
        if self.forbidden:
            return [self.forbidden]
        if self.kind == "email":
            if a.kind != "email_send":
                return ["This must be sent as an email, not saved as a draft."]
            out: list[str] = []
        else:
            out = super().problems(a, w)
        return out + (self.check(a, w) if self.check else [])


T3_BODY = [(r"NOT currently eligible for FMLA", "the Template 3 wording \"you are NOT currently eligible for FMLA leave "
            "for the following reason:\""),
           (r"1,?018", "the specific failed criterion with her hours: 1,018 hours worked in the preceding 12 months "
                       "(hours_worked_log.xlsx value, not recalculated)"),
           (r"1,?250", "the 1,250-hour FMLA threshold"),
           (r"Colorado FAMLI", "the Template 3 paragraph that she may still be eligible under Colorado FAMLI"),
           (r"Case ID:\s*LC-\d{4}-\d{4}", "\"Case ID: <FMLA case ID>\" (the case you log as Denied)"),
           (r"leaves@ridgelinegear\.com", "the standard signature block ending leaves@ridgelinegear.com")]
T31_BODY = [(r"administered under Colorado FAMLI", "the Template 31 wording \"your leave will be administered under "
             "Colorado FAMLI\""),
            (r"claims@famli\.colorado\.gov", "the CDLE filing address claims@famli.colorado.gov"),
            (r"Case ID:\s*LC-\d{4}-\d{4}", "\"Case ID: <FAMLI case ID>\" (the new FAMLI-only case)"),
            (r"leaves@ridgelinegear\.com", "the standard signature block ending leaves@ridgelinegear.com")]


def specs(ctx: Context) -> list[Comm]:
    w = world(ctx)
    den, fam, _ = case_rows(w)
    den_id, fam_id = case_id(w, den), case_id(w, fam)

    def t3_check(a: Action, w: World) -> list[str]:
        out = []
        if BM not in recips(a):
            out.append(f"CC the Benefits Manager {BM} on the denial (§13.9 Step 2, §21.2 Step 3); use send_email "
                       f"to {WORK} with cc {BM}.")
        body = dashes(a.text)
        out += [f"Missing: {d}." for rx, d in T3_BODY if not re.search(rx, body, re.I)]
        if re.search(r"Tenure:\s*FMLA requires", body, re.I):
            out.append("The failed criterion is hours (1,018 < 1,250), not tenure - she was hired 2021-01-11.")
        m = re.search(r"Case ID:\s*(LC-\d{4}-\d{4})", body)
        if m:
            out += id_problems(w, m.group(1), den_id, fam_id, "FMLA (denied)")
        return out

    def t31_check(a: Action, w: World) -> list[str]:
        out = []
        subj = dashes(a.subject)
        ms = re.fullmatch(r"Leave Request Received\s*[–-]\s*(LC-\d{4}-\d{4})", subj.strip())
        if not ms:
            out.append(f"Subject must be the Template 31 subject \"Leave Request Received – {fam_id or '[FAMLI Case ID]'}\""
                       f" (got \"{a.subject}\").")
        body = dashes(a.text)
        out += [f"Missing: {d}." for rx, d in T31_BODY if not re.search(rx, body, re.I)]
        m = re.search(r"Case ID:\s*(LC-\d{4}-\d{4})", body)
        if m:
            out += id_problems(w, m.group(1), fam_id, den_id, "FAMLI-only")
            if ms and ms.group(1) != m.group(1):
                out.append("The Case ID in the subject and the body must be the same FAMLI case ID.")
        if any(re.search(r"WH-38[12]", f, re.I) for f in attachments(a)):
            out.append("Do not attach FMLA notices (WH-381/WH-382) to the FAMLI-only acknowledgment (§14.6).")
        return out

    def slack_check(a: Action, w: World) -> list[str]:
        m = re.search(r"FMLA DENIED \(INELIGIBILITY\):\s*(LC-\d{4}-\d{4})\s*,\s*([^\n]*)", dashes(a.text))
        if not m:
            return [f"Use the SOP format \"FMLA DENIED (INELIGIBILITY): {den_id or '[Case ID]'}, Hours\"."]
        out = id_problems(w, m.group(1), den_id, fam_id, "FMLA (denied)")
        if not re.search(r"hour", m.group(2), re.I):
            out.append("The failed criterion is hours (non-exempt, 1,018 < 1,250); state it after the Case ID.")
        return out

    def denied_about(a: Action) -> bool:
        if a.kind != "slack_post":
            return False
        t = dashes(a.text).strip()
        return bool(re.match(r"FMLA DENIED", t, re.I)
                    or (w.is_channel(a.channel, "leave-intake") and re.search(r"FMLA DENIED", t, re.I)))

    t3 = PComm(
        "t3_ineligibility", "email",
        lambda a: a.kind == "email_send" and to_portia(a) and is_t3(a),
        "Template 3 (FMLA Ineligibility Notice) to Portia Nzinga - not eligible on hours (1,018 < 1,250), "
        "Benefits Manager CC'd",
        [R_T3, R_212_S3, R_212_S1, R_HOURS_FILE, R_HOURS, R_LC_HOURS, R_DENY_LC, R_SEND_NOW, R_TEMPLATES,
         R_TPL_SECTIONS, R_SIGNATURE],
        to=[WORK], cc=[BM], body=T3_BODY, check=t3_check)
    t31 = PComm(
        "t31_famli_ack", "email",
        lambda a: a.kind == "email_send" and to_portia(a) and bool(T31RX.search(text_of(a))) and not is_t3(a),
        "Template 31 (FAMLI-Only Intake Acknowledgment) to Portia Nzinga for the new FAMLI-only case",
        [R_T31, R_212_S5, R_STEP9, R_NO_FMLA_NOTICE, R_TEMPLATES, R_SIGNATURE],
        to=[WORK], subject_hint=f"Leave Request Received – {fam_id or '[FAMLI Case ID]'}", body=T31_BODY,
        check=t31_check)
    denied_post = PComm(
        "fmla_denied_post", "slack_post", denied_about,
        "#leave-intake post of the FMLA ineligibility denial", [R_212_S6, R_STEP10, R_INTAKE_CH], channel="leave-intake",
        body=[(r"FMLA DENIED \(INELIGIBILITY\):", f"\"FMLA DENIED (INELIGIBILITY): {den_id or '[Case ID]'}, "
               "Hours\" (no medical details)")], check=slack_check)
    eligible = PComm(
        "fmla_eligible_notice", "email",
        lambda a: a.kind in ("email_send", "email_draft") and to_portia(a) and bool(
            ELIGIBLE.search(text_of(a)) or any(re.search(r"WH-38[02]", f, re.I) for f in attachments(a))),
        "FMLA eligibility/designation notice or certification request to Portia",
        [R_HOURS, R_INELIG, R_T2, R_WH380, R_NO_FMLA_NOTICE],
        forbidden="Portia Nzinga is NOT FMLA-eligible: non-exempt, 1,018 hours in the rolling 12 months "
                  "(hours_worked_log.xlsx) < 1,250. Send Template 3 (ineligibility) instead; no Template 2/4, "
                  "WH-380-E/F or WH-382.",
        required=False)
    famli_denial = PComm(
        "famli_denial", "email",
        lambda a: a.kind in ("email_send", "email_draft") and to_portia(a) and bool(FAMLI_DENIAL.search(text_of(a))),
        "FAMLI denial to Portia", [R_FAMLI_DENY, R_RECAP_BM, R_212_S5],
        forbidden="The LC may not deny FAMLI (only FMLA tenure/hours ineligibility). FAMLI eligibility is possible "
                  "(no hours/tenure test): open the FAMLI-only case and send Template 31 instead.",
        required=False)
    return [t3, t31, denied_post, eligible, famli_denial]


# ---- pre rules -------------------------------------------------------------------------------------------

AMOUNT = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?|\b\d{1,3}(?:\.\d+)?\s?%")
WAGE_CTX = re.compile(r"wage replacement|benefit amount|weekly benefit|replacement rate|of (?:your|her) (?:average |"
                      r"regular )?(?:weekly )?(?:wages|pay|earnings)|per week|weekly", re.I)
BENEFIT = re.compile(r"health insurance|premium|401\s?\(?k\)?|COBRA|\bHSA\b|\bFSA\b", re.I)
ASSERT = re.compile(r"\b(?:will|continues?|continued|maintain(?:s|ed)?|deducted|stops?|suspend(?:s|ed)?)\b", re.I)
ROUTING = re.compile(r"question|contact|reach|direct|route|forward|\bask\b|Teresa|Payroll Lead|Benefits Manager|Renata",
                     re.I)


def _content(ctx: Context, a: Action) -> list[tuple[str, list]]:
    if a.kind not in COMM_KINDS + ("calendar_create", "calendar_update"):
        return []
    w = world(ctx)
    if not related(w, a):
        return []
    txt = dashes(text_of(a))
    out = []
    m = MEDICAL.search(txt)
    if m:
        out.append((f"Confidentiality: the message names the medical condition/procedure (\"{m.group(0)}\"). Never "
                    "include medical details in email, Slack or calendar - use the reason category only.",
                    [R_NO_MEDICAL, R_EMAIL_MED, R_SLACK_MED, R_SLACK_NO_MED, R_TPL_NO_MED, R_QUOTE, R_PERSONAL]))
    if a.kind in ("email_send", "email_draft"):
        r = recips(a)
        if MANAGER in r and not (r & PORTIA) and REASON.search(txt):
            out.append(("Confidentiality: a manager notification may not state the reason category or that the leave "
                        "is medical - say \"approved leave\" with dates only.", [R_MGR_REASON, R_MGR_NO_DX]))
        if r & PORTIA:
            wage = [s for s in sentences(txt) if AMOUNT.search(s) and WAGE_CTX.search(s)]
            if wage:
                out.append((f"Do not discuss FAMLI wage-replacement amounts or percentages (\"{wage[0][:100]}\") - "
                            "CDLE answers those.", [R_WAGE, R_WAGE_CDLE]))
            ben = [s for s in sentences(txt) if BENEFIT.search(s) and ASSERT.search(s) and not ROUTING.search(s)]
            if ben:
                out.append((f"Benefits continuation is not discussed by the LC (\"{ben[0][:100]}\") - route such "
                            "questions to the Payroll Lead / Benefits Manager.", [R_BENEFITS]))
    if a.kind == "slack_post":
        if w.is_channel(a.channel, "payroll-coordination") and REASON.search(txt):
            out.append(("Payroll notifications may not include the reason category (\"FMLA + FAMLI concurrent\" / "
                        "\"FAMLI-only\" is the maximum).", [R_PAYROLL_REASON]))
        if re.search(r"<@U017>|@theo", txt, re.I):
            out.append(("Never tag the manager (Theo Mbeki) in a case channel; managers get email notifications.",
                        [R_SLACK_TAG]))
    return out


def _recipients(ctx: Context, a: Action) -> list[tuple[str, list]]:
    w = world(ctx)
    if a.kind == "slack_dm" or (a.kind == "slack_post" and w.dm_recipients(a)):
        if related(w, a):
            return [("Direct messages about leave cases are prohibited (not auditable). Post the case notification in "
                     "#leave-intake instead.", [R_NO_DM, R_SLACK_DM])]
        return []
    if a.kind not in ("email_send", "email_draft") or not related(w, a):
        return []
    r = recips(a)
    extra = sorted(x for x in r - PORTIA - HR_TEAM - {MANAGER} if not CDLE.search(x))
    if extra:
        return [(f"Portia Nzinga's leave may only be discussed with her, the HR team and (via Template 11) her manager "
                 f"{MANAGER}; remove {', '.join(extra)}.", [R_NO_DISCUSS, R_NO_DISCLOSE, R_NO_CONFIRM, R_CC, R_FWD])]
    if r & PORTIA and MANAGER in r:
        return [(f"Do not copy the manager ({MANAGER}) on case emails to the employee - managers get their own "
                 "Template 11 notification without medical details.", [R_CC])]
    return []


def _cdle(ctx: Context, a: Action) -> list[tuple[str, list]]:
    if a.kind not in ("email_send", "email_draft"):
        return []
    w = world(ctx)
    if any(CDLE.search(x) for x in recips(a)) and related(w, a):
        return [("Ridgeline does NOT file FAMLI claims on the employee's behalf. Portia files directly with CDLE "
                 "(claims@famli.colorado.gov); tell her so in Template 31 and do not email CDLE about her claim.",
                 [R_NO_FILE, R_CDLE_STEP1])]
    return []


BLANK = (r"(?:WH-38[0-5](?:-[EF])?|CO_FAMLI_Employee_Notice|CO_HFWA_Notice|Ridgeline_Leave_Policy|"
         r"Ridgeline_HR_Leave_Coordinator_SOP_Fixed)\.pdf|templates\.json|mailbox_data\.json")
BLANK_NAME = re.compile(rf"^(?:{BLANK})$", re.I)
BLANK_IN = re.compile(rf"(?<![\w.-])(?:{BLANK})(?![\w.-])", re.I)
DELETE_CALL = re.compile(r"\brm\s|os\.(?:remove|unlink)\(|\.unlink\(|shutil\.rmtree\(", re.I)


def _deletes_blank(text: str) -> bool:
    """A deletion call and a protected file name in the same shell/python statement."""
    return any(DELETE_CALL.search(seg) and BLANK_IN.search(seg) for seg in re.split(r"[;\n&|]+", text))


def _protected(ctx: Context, a: Action) -> list[tuple[str, list]]:
    if a.kind not in WRITE_KINDS:
        return []
    hit = [f for f in strict_writes(a) if BLANK_NAME.match(f)]
    if not hit and a.kind == "file_delete" and _deletes_blank(a.text or json.dumps(a.args)):
        hit = ["(deleted file)"]
    if not hit:
        return []
    return [(f"{', '.join(hit)}: blank forms, templates.json, the SOP and mailbox data are never modified or deleted - "
             "copy a blank form to EMP-1222/ before filling it.", [R_BLANK_FORMS, R_TPL_JSON, R_NO_DELETE,
                                                                     R_NO_DESTROY])]


def _mail(ctx: Context, a: Action) -> list[tuple[str, list]]:
    out = []
    if a.kind == "email_move":
        target = nh(a.channel)
        if target not in FOLDERS:
            out.append((f"Folder \"{target}\" is not an SOP folder; use one of: {', '.join(FOLDERS)} (exact names; "
                        "Portia's email 106 belongs in \"FAMLI Cases\").", [R_FOLDER_NAMES]))
    elif a.kind == "other_write" and re.search(r"create_(?:folder|label)", a.tool, re.I):
        out.append(("Do not create new mail folders; use the existing SOP folders.", [R_FOLDER_NAMES]))
    elif a.kind == "email_mark" and INTAKE_ID in a.recipients and re.search(
            r'"is_(?:important|flagged|starred)":\s*true|"flag(?:ged)?":\s*true', json.dumps(a.args), re.I):
        out.append(("Email 106 is a P3 email: do not flag it as important; mark it read and move it to \"FAMLI "
                    "Cases\".", [R_P3_MOVE]))
    return out


# ---- completion rules ------------------------------------------------------------------------------------

def _denied_checks(ctx: Context):
    w = world(ctx)
    den, _, _ = case_rows(w)
    if den is None:
        yield (False, "leave_tracker.xlsx (Active Cases) has no FMLA case row for EMP-1222 Portia Nzinga with Case "
                      "Status = \"Denied\". Log the FMLA ineligibility as its own row: Case ID = a new unused "
                      "LC-2026-NNNN, Employee ID EMP-1222, Employee Name Portia Nzinga, Leave Type(s) FMLA, Start "
                      "Date 2026-05-14, Case Status \"Denied\", Notes stating the basis (non-exempt, 1,018 hours < "
                      "1,250).", [R_212_S4, R_DENIED_LOG, R_STEP8, R_F_EMPID])
        return
    cid = case_id(w, den)
    yield (bool(re.search(r"hour|1,?018|1,?250", w.col(den, r"^Notes$"), re.I)),
           f"Denied FMLA row {cid}: Notes must explain the basis - hours criterion, 1,018 hours in the preceding 12 "
           "months (non-exempt, hours_worked_log.xlsx) < 1,250.", [R_212_S4, R_DENIED_LOG, R_F_NOTES])
    yield (norm(w.col(den, r"^Employee Name$")) == "portia nzinga",
           f"Denied FMLA row {cid}: Employee Name must be \"Portia Nzinga\".", [R_MIN_ID])


def _famli_checks(ctx: Context):
    w = world(ctx)
    _, fam, _ = case_rows(w)
    if fam is None:
        yield (False, "leave_tracker.xlsx (Active Cases) has no separate FAMLI-only case for EMP-1222 Portia Nzinga. "
                      "Open a NEW row (do not reuse the denied FMLA row): Case ID = a new unused LC-2026-NNNN, "
                      "Employee ID EMP-1222, Employee Name Portia Nzinga, Leave Type(s) \"FAMLI\", Case Status "
                      "\"Intake\", Start Date 2026-05-14, Priority P3, Foreseeable, Manager Name Theo Mbeki, "
                      "Contact Preference Personal Email, Hours Used To Date 0, Actual End Date blank.",
               [R_212_S5, R_FAMLI_STILL, R_FAMLI_IMPL, R_FAMLI_ROW, R_FAMLI_STATUS, R_INTAKE, R_F_EMPID])
        return
    cid = case_id(w, fam)
    col = lambda rx: w.col(fam, rx)
    checks = [
        (norm(col(r"^Leave Type")) == "famli", "Leave Type(s) must be exactly \"FAMLI\" (not \"FMLA + FAMLI\")",
         [R_FAMLI_ROW, R_212_S5, R_ONLY_ONE, R_F_TYPE]),
        (norm(col(r"^Case Status$")) == "intake", "Case Status must be \"Intake\"",
         [R_FAMLI_STATUS, R_212_S5, R_F_STATUS]),
        (norm(col(r"^Employee Name$")) == "portia nzinga", "Employee Name must be \"Portia Nzinga\"", [R_MIN_ID]),
        (nh(col(r"^Start Date$")).startswith(START), f"Start Date must be {START} (requested leave start, "
                                                      "YYYY-MM-DD)", [R_INTAKE, R_MIN_START, R_F_START, R_DATES]),
        (norm(col(r"^Manager Name$")) == "theo mbeki", "Manager Name must be \"Theo Mbeki\" (employee_roster.xlsx)",
         [R_INTAKE, R_MIN_MGR, R_F_MGR]),
        (norm(col(r"^Priority$")) == "p3",
         "Priority must be \"P3\" (standard foreseeable FAMLI request with 30+ days notice: received 2026-04-10, "
         "leave starts 2026-05-14)", [R_P3, R_PRIO, R_STEP7, R_F_PRIO]),
        (norm(col(r"^Foreseeable")) == "foreseeable",
         "Foreseeable / Unforeseeable must be \"Foreseeable\" (34 days advance notice)",
         [R_INTAKE, R_MIN_FORESEE, R_F_FORESEE]),
        (bool(re.search(r"personal", col(r"^Contact Preference$"), re.I)),
         "Contact Preference must be \"Personal Email\" (she asked to be reached at pnzinga@gmail.com during leave)",
         [R_INTAKE, R_MIN_CONTACT, R_F_CONTACT]),
        (same(col(r"^Hours Used To Date$"), 0), "Hours Used To Date must be 0 at intake", [R_INTAKE, R_F_HOURS]),
        (not col(r"^Actual End Date$"), "Actual End Date must stay blank until closure", [R_INTAKE, R_F_ACTEND]),
    ]
    for ok, msg, refs in checks:
        yield ok, f"FAMLI-only case {cid}: {msg}.", refs


def _id_checks(ctx: Context):
    w = world(ctx)
    den, fam, _ = case_rows(w)
    cur = [nh(w.col(r, r"^Case ID$")) for r in w.rows(TRACKER, HDR, "current", SHEET)]
    for row, what in ((den, "denied FMLA"), (fam, "FAMLI-only")):
        cid = case_id(w, row)
        if not row:
            continue
        probs = id_problems(w, cid, None, None, what)
        if cur.count(cid) > 1:
            probs.append(f"{cid} appears on {cur.count(cid)} rows of leave_tracker.xlsx")
        yield (not probs, f"The {what} case ID: " + " ".join(probs), [R_CASE_ID])
    if den and fam:
        yield (case_id(w, den) != case_id(w, fam),
               "The FAMLI-only case needs a NEW Case ID, different from the denied FMLA case.", [R_212_S5, R_212_KEEP])


def _no_medical_records(ctx: Context):
    w = world(ctx)
    _, _, rows = case_rows(w)
    rows = rows + [r for r in w.new_rows(FLOG, FHDR) if norm(w.col(r, r"^Employee ID$")) == norm(EMP)]
    for r in rows:
        hit = MEDICAL.search(" | ".join(v for k, v in r.items() if k != "__row__"))
        yield (not hit, f"A new record for EMP-1222 (row {r['__row__']}) names the medical condition/procedure "
                        f"(\"{hit.group(0) if hit else ''}\"). Record the reason category only (employee's own "
                        "serious health condition).", [R_NO_DIAG, R_NO_MEDICAL])


def _famli_log_checks(ctx: Context):
    w = world(ctx)
    _, fam, _ = case_rows(w)
    fam_id = case_id(w, fam)
    rows = [r for r in w.new_rows(FLOG, FHDR) if norm(w.col(r, r"^Employee ID$")) == norm(EMP)]
    want = fam_id or "the FAMLI-only Case ID"
    if not rows:
        yield (False, "famli_coordination_log.xlsx has no row tracking Portia Nzinga's FAMLI-only case. Append a row: "
                      f"Case ID (Ridgeline) {want}, Employee ID EMP-1222, Employee Name Portia Nzinga, FAMLI Claim ID "
                      "blank (CDLE has not issued one), Claim Start Date 2026-05-14, Claimed Reason Category Employee "
                      "own serious health condition, Concurrent FMLA? No.", [R_FAMLI_LOG, R_LOG_STEP4])
        return
    r = rows[-1]
    got_id = nh(w.col(r, r"^Case ID"))
    if fam_id:
        yield (got_id == fam_id, f"famli_coordination_log.xlsx: Case ID (Ridgeline) must be the FAMLI-only case "
                                 f"{fam_id} (got \"{got_id}\").", [R_FAMLI_LOG])
    yield (bool(re.fullmatch(r"(n|no)\b.*", norm(w.col(r, r"^Concurrent FMLA")))),
           "famli_coordination_log.xlsx: Concurrent FMLA? must be \"No\" (she is not FMLA-eligible).",
           [R_FAMLI_LOG, R_ONLY_ONE])
    claim = w.col(r, r"^FAMLI Claim ID")
    yield (not re.search(r"FAMLI-CO-\d{4}-\d+", claim),
           f"famli_coordination_log.xlsx: FAMLI Claim ID \"{claim}\" was not issued by CDLE - leave it blank until "
           "the CDLE notice arrives.", [R_FAMLI_LOG, R_NO_FILE])


def _unchanged(ctx: Context):
    w = world(ctx)
    why = {"employee_roster": (R_ROSTER, "the master roster is read-only for this intake"),
           "hours_worked_log": (R_HOURS_SRC, "hours data is maintained by Payroll and only read for eligibility"),
           "hfwa_balance_tracker": (R_HFWA_LOG, "no HFWA use was reported, so there is nothing to log"),
           "leave_history": (R_LOG_USAGE, "no leave has been used yet, so there is nothing to log")}
    for f in w.changed_files():
        for key, (ref, reason) in why.items():
            if key in f:
                yield (False, f"{f} was modified, but {reason}. Restore it to its original content.", [ref])


def _wh381(ctx: Context):
    w = world(ctx)
    den, _, _ = case_rows(w)
    den_id = case_id(w, den)
    rx = re.compile(r"(?:^|/)EMP-1222/WH-381_(LC-\d{4}-\d{4})_(?:\d{8}|\d{4}-\d{2}-\d{2})\.pdf$", re.I)
    hits = [m.group(1) for m in (rx.search(f) for f in w.files()) if m]
    name = f"EMP-1222/WH-381_{den_id or '[FMLA Case ID]'}_20260413.pdf"
    if not hits:
        yield (False, f"The completed WH-381 (Part A marked \"not eligible\", hours criterion: 1,018 worked, 1,250 "
                      f"required) is not saved. Save it as {name} (copy the blank WH-381.pdf; never modify the blank).",
               [R_WH381_FILL, R_WH381_SAVE, R_212_S2, R_NAMING])
    elif den_id and den_id not in hits:
        yield (False, f"The saved WH-381 must carry the denied FMLA Case ID: {name}.", [R_WH381_SAVE, R_NAMING])


def _housekeeping(ctx: Context):
    w = world(ctx)
    marks = [a for a in w.calls("email_mark") if INTAKE_ID in a.recipients]
    read = any(re.search(r'"is_read":\s*true|"(?:mark_as|status|action|read)":\s*"?(?:read|true)', json.dumps(a.args),
                         re.I) for a in marks)
    yield (read, "Email 106 (Portia Nzinga's request) is still unread - mark it as read.",
           [R_READ, R_STEP12, R_HOUSEKEEP])
    moves = [a for a in w.calls("email_move") if INTAKE_ID in a.recipients]
    last = moves[-1].channel if moves else "INBOX"
    yield (norm(last) == "famli cases",
           f"Email 106 must be filed in the \"FAMLI Cases\" folder (P3 email; the open case is FAMLI-only and the FMLA "
           f"case is denied) - currently \"{last}\".", [R_P3_MOVE, R_FOLDER, R_STEP12])


RULES = (
    comm_rules("famli", specs)
    + no_placeholders([R_PLACEHOLDERS])
    + pre("conf.content", _content, "Remove the confidential content and send again.")
    + pre("conf.recipients", _recipients, "Address the message only to permitted recipients/channels.")
    + pre("famli.no_cdle_filing", _cdle, "Do not send this email.")
    + pre("files.protected", _protected, "Leave that file unchanged.")
    + pre("mail.folders", _mail, "Use the SOP mail folders as listed.")
    + state_rule("tracker.fmla_denied_row", _denied_checks, "Update leave_tracker.xlsx as listed.")
    + state_rule("tracker.famli_row", _famli_checks, "Update leave_tracker.xlsx as listed.")
    + state_rule("tracker.case_ids", _id_checks, "Use unique, unused LC-2026-NNNN Case IDs.")
    + state_rule("records.no_medical", _no_medical_records, "Replace the medical detail with the reason category.")
    + append_only("tracker.append_only", TRACKER, HDR, "leave_tracker.xlsx Active Cases", [R_212_KEEP, R_STEP8],
                  SHEET)
    + append_only("tracker.absence_log_append_only", TRACKER, r"^Absence Date$", "leave_tracker.xlsx Absence Log",
                  [R_TRACK], r"^Absence Log$")
    + state_rule("famli_log.row", _famli_log_checks, "Update famli_coordination_log.xlsx as listed.")
    + append_only("famli_log.append_only", FLOG, FHDR, "famli_coordination_log.xlsx", [R_FAMLI_LOG])
    + state_rule("files.unchanged", _unchanged, "Restore the file.")
    + state_rule("files.wh381_saved", _wh381, "Save the completed WH-381 as listed.")
    + state_rule("mail.housekeeping", _housekeeping, "Complete the email housekeeping as listed.")
)
