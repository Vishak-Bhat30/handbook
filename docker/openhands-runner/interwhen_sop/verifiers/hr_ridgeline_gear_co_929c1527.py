"""SOP verifiers for hr_ridgeline_gear_co_929c1527 (Ridgeline Gear Co. Leave Coordinator, 04/10/2026).

Situation derived from the seed data only:
- Elena Vasquez (R-2317, non-exempt, 0.5 FTE) requests continuous leave 04/20-05/15/2026 for her own condition.
  Tenure is met (hired 10/02/2024) but hours_worked_log shows 1,038 < 1,250 -> FMLA-ineligible on hours; a
  non-exempt hours denial is an LC-level denial (SOP 12.2): Template 3 cc Benefits Manager, FAMLI referral to
  CDLE, tracker row with Case Status = Denied, #leave-intake "FMLA DENIED (INELIGIBILITY)" post. Foreseeable
  request with < 30 days notice -> P2.
- James Nkomo LC-2026-0203 (intermittent, certified 1-2 episodes/month): absences 03/10, 03/19, 03/26, 04/02 and
  04/07 (already logged, 52 h used / 428 h balance) fall in one 30-day window -> 5 vs a certified high end of 2
  (+150%), although the notes record the 04/07 review as "within parameters" -> pattern flag:
  #hr-escalations RECURRING ISSUE post, RECURRING ISSUE email to the Benefits Manager, "Pattern flagged" note,
  no disclosure to the employee/manager. The Absence Log/balance rule only guards against double counting.
- Marcus DeLuca LC-2026-0320 (jury duty): RETURN CONFIRMED 04/10/2026 by his manager in #leave-intake ->
  Actual End Date, closure, #payroll-coordination return notification, closure housekeeping.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field

from .. import templates
from ..kit import (Comm, blank, comm_rules, forbid_writes, nh, norm, num, pre_rule, same, state_rule, text_of,
                   world)

# ---- SOP references (section, paragraph text prefix, label) ------------------------------------------------
P0100 = ("3.1", "All times in this document are in Mountain Time", "3.1 date format")
P0130 = ("5.2", "Intermittent leave pattern concerns", "5.2 pattern concerns")
P0148 = ("5.5", "Disclose any employee medical information", "5.5 never disclose medical information")
P0149 = ("5.5", "Promise retroactive leave designation", "5.5 never promise retroactive designation")
P0150 = ("5.5", "Confirm or deny whether an employee is on any type of leave", "5.5 no external confirmation")
P0151 = ("5.5", "Discuss one employee's leave with another employee", "5.5 no discussion with other employees")
P0154 = ("5.5", "Include medical details, diagnoses", "5.5 no medical details")
P0169 = ("4", "All internal communications about leave cases must use", "4 Slack channels")
P0171 = ("4", "#leave-intake | Primary Leave Coordinator channel", "4 #leave-intake")
P0173 = ("4", "#hr-escalations | Escalations requiring", "4 #hr-escalations")
P0174 = ("4", "#payroll-coordination | Payroll handoffs only", "4 #payroll-coordination")
P0177 = ("4", "Never post medical details, diagnoses, or any protected health information in any Slack channel under",
         "4 no PHI in Slack")
P0198 = ("6.1", "Step 4 : Open leave_tracker.xlsx and search", "6.1 Step 4")
P0201 = ("6.1", "Step 7 : Assign a priority level", "6.1 Step 7")
P0202 = ("6.1", "Step 8 : If a new case is needed", "6.1 Step 8")
P0203 = ("6.1", "Step 9 : Act per the relevant section", "6.1 Step 9")
P0204 = ("6.1", "Step 10 : Post a case notification", "6.1 Step 10")
P0206 = ("6.1", "Step 12 : Complete email housekeeping", "6.1 Step 12")
P0208 = ("6.2", "Before opening a case in leave_tracker.xlsx, confirm", "6.2 minimum intake data")
P0222 = ("6.3", "Open ONE Case ID in leave_tracker.xlsx", "6.3 one Case ID")
P0224 = ("6.3", "Send one consolidated acknowledgment email", "6.3 one consolidated email")
P0225 = ("6.3", "Apply the highest priority level", "6.3 priority")
P0329 = ("8.1", "Step 3. Open hoursworkedlog.xlsx", "8.1 Step 3")
P0330 = ("8.1", "Step 4. If hours worked in the preceding 12 months is less than 1,250", "8.1 Step 4")
P0331 = ("8.1", "Step 5. Criterion 3 is automatically met", "8.1 Step 5")
P0332 = ("8.1", "Step 6. If any criterion is not met", "8.1 Step 6")
P0370 = ("8.4", "Eligibility Notice (Part A of WH-381)", "8.4 Eligibility Notice")
P0411 = ("8.6", "Intermittent: Log each absence individually", "8.6 intermittent tracking")
P0415 = ("8.6", "At the 30-day review required by Section 7, compare", "8.6 pattern check")
P0435 = ("8.7", "At intake: populate all fields", "8.7 intake fields")
P0436 = ("8.7", "At each intermittent absence: add a row", "8.7 Absence Log")
P0439 = ("8.7", "At return or closure: populate Actual End Date", "8.7 closure")
P0454 = ("8.8", "Step 5. On the day of return, the manager confirms", "8.8 Step 5")
P0455 = ("8.8", "Step 6. Complete the case closure checklist", "8.8 Step 6")
P0476 = ("8.9", "Step 2. For LC-level denials", "8.9 Step 2")
P0478 = ("8.9", "Step 4. Log denial in leave_tracker.xlsx", "8.9 Step 4")
P0484 = ("9.1", "Wage replacement under FAMLI is paid by CDLE, NOT by Ridgeline", "9.1 wage replacement")
P0485 = ("9.1", "FAMLI claims are filed by the employee directly", "9.1 FAMLI claims")
P0499 = ("9.3", "If the employee is eligible for only one of the two laws", "9.3 one law only")
P0503 = ("9.3", "FAMLI eligibility determination by the LC", "9.3 FAMLI determination")
P0512 = ("9.5", "Step 1 : Employees file FAMLI claims directly", "9.5 Step 1")
P0525 = ("9.6", "Open a Case ID in leave_tracker.xlsx with Leave Type = ", "9.6 FAMLI-only leave type")
P0527 = ("9.6", "Do NOT send FMLA notices (WH-381 or WH-382) for a FAMLI-only case", "9.6 no FMLA notices")
P0531 = ("9.7", "Leave Coordinator must NEVER discuss wage replacement", "9.7 wage replacement")
P0592 = ("10.2", "When the Leave Coordinator issues the FMLA Designation Notice", "10.2 manager notification")
P0601 = ("10.2", "The Manager Leave Notification must NEVER include", "10.2 manager notification content")
P0630 = ("10.5", "The Leave Coordinator updates leave_tracker.xlsx with the absence hours", "10.5 absence logging")
P0636 = ("10.6", "The LC closes the case per the case closure checklist", "10.6 closure")
P0645 = ("10.1", "Actual return from leave (confirmation from the manager)", "10.1 payroll: actual return")
P0646 = ("10.1", "Each intermittent-leave absence that reduces", "10.1 payroll: intermittent absence")
P0647 = ("10.1", "Case closure.", "10.1 payroll: case closure")
P0651 = ("10.2", "LEAVE PAYROLL NOTIFICATION: [Case ID]", "10.2 payroll format")
P0654 = ("10.2", "Do not include medical details, diagnoses, or the reason category in the payroll", "10.2 payroll")
P0768 = ("11.4", "Step 7 : When jury duty ends", "11.4 Step 7")
P0804 = ("12.1", "Intermittent absences are reported to the Leave Coordinator", "12.1 absence intake")
P0807 = ("12.1", "Step 3 : Record the absence in leave_tracker.xlsx Absence Log", "12.1 Step 3")
P0809 = ("12.1", "Step 5 : Recalculate the Hours Used To Date", "12.1 Step 5")
P0817 = ("12.2", "Step 5 : If variance exceeds +50%", "12.2 30-day review Step 5")
P0824 = ("12.3", "Do not request recertification independently", "12.3 recertification")
P0826 = ("12.4", "Actual usage exceeds certified frequency by more than 50% in any 30-day period.", "12.4 trigger")
P0831 = ("12.4", "Any of these triggers requires escalation", "12.4 escalation")
P0845 = ("12.2", "Step 2 : Leave Coordinator posts to #payroll-coordination", "12.2 day-of-return Step 2")
P0846 = ("12.2", "Step 3 : Leave Coordinator updates leave_tracker.xlsx: populate Actual End Date", "12.2 Step 3")
P0847 = ("12.2", "Step 4 : Leave Coordinator begins the case closure checklist", "12.2 Step 4")
P0850 = ("12.3", "[ ] Actual End Date populated", "12.3 checklist")
P0851 = ("12.3", "[ ] Case Status set to Closed", "12.3 checklist")
P0856 = ("12.3", "[ ] Payroll Lead notified of the return date", "12.3 checklist")
P0861 = ("12.3", "[ ] Case notes updated with closure date", "12.3 checklist")
P0862 = ("12.3", "[ ] All related HR Leave Deadlines calendar events", "12.3 checklist")
P0863 = ("12.3", "[ ] Email thread moved to the Closed Cases folder", "12.3 checklist")
P0897 = ("12.2", "Step 2 : Prepare the WH-381 with Part A marked", "12.2 independent denial Step 2")
P0898 = ("12.2", "Step 3 : Send the denial using Template 3", "12.2 independent denial Step 3")
P0899 = ("12.2", "Step 4 : Update leave_tracker.xlsx: Case Status = Denied", "12.2 independent denial Step 4")
P0900 = ("12.2", "Step 5 : Check FAMLI eligibility separately", "12.2 independent denial Step 5")
P0901 = ("12.2", "Step 6 : Post to #leave-intake: FMLA DENIED", "12.2 independent denial Step 6")
P0929 = ("12.1", "Three or more intermittent absences in a rolling 30-day window", "12.1 recurring issue")
P0937 = ("12.2", "Step 2 : Document the pattern in leave_tracker.xlsx case notes", "12.2 pattern Step 2")
P0938 = ("12.2", "Step 3 : Post to #hr-escalations using the format: RECURRING ISSUE", "12.2 pattern Step 3")
P0939 = ("12.2", "Step 4 : Forward any relevant email thread", "12.2 pattern Step 4")
P0940 = ("12.2", "Step 5 : Add a case note entry", "12.2 pattern Step 5")
P0941 = ("12.2", "Step 6 : Do NOT communicate the flag", "12.2 pattern Step 6")
P0942 = ("12.2", "Step 7 : Wait for direction from the Benefits Manager", "12.2 pattern Step 7")
P0952 = ("12.4", "Never disclose a pattern flag to the employee's manager", "12.4 pattern confidentiality")
P0953 = ("12.4", "Never discuss pattern concerns with the employee", "12.4 pattern confidentiality")
P0954 = ("12.4", "Never include pattern details in any Slack post", "12.4 pattern confidentiality")
P0956 = ("12.4", "Never suggest to any party", "12.4 pattern confidentiality")
P0964 = ("13.1", "File naming conventions", "13.1 file naming")
P0966 = ("13.2", "Never include medical details, diagnoses, or protected health information in the body",
         "13.2 email confidentiality")
P0967 = ("13.2", "Never CC anyone outside the HR team", "13.2 CC limits")
P0968 = ("13.2", "Never forward an email thread containing medical information", "13.2 forwarding")
P0969 = ("13.2", "If an employee sends an email containing more medical detail", "13.2 quoting")
P0970 = ("13.2", "Never use the employee's personal email", "13.2 personal email")
P0972 = ("13.3", "Never post medical details, diagnoses, or protected health information in any Slack channel, incl",
         "13.3 Slack confidentiality")
P0974 = ("13.3", "Never tag managers or non-HR roles", "13.3 no tagging")
P0975 = ("13.3", "Direct messages about cases are prohibited", "13.3 no DMs")
P0979 = ("13.4", "Never confirm or deny leave status to external callers", "13.4 external parties")
P0984 = ("13.5", "Do not delete any case file", "13.5 retention")
P0985 = ("13.5", "When retention periods expire", "13.5 retention")
P1007 = ("13.1", "Mark as read | Every processed email", "13.1 mark as read")
P1008 = ("13.1", "P1 / P2 emails | Leave in the Inbox", "13.1 P1/P2 emails")
P1021 = ("13.2", "Closed Cases | Any case correspondence", "13.2 Closed Cases folder")
P1024 = ("13.2", "Folder names must match exactly as listed", "13.2 folder names")
P1027 = ("13", "Use templates as written", "13 templates")
P1028 = ("13", "Replace all [bracketed] placeholders", "13 placeholders")
P1029 = ("13", "Do not add medical details, diagnoses, or other protected health information to any template",
         "13 templates")
P1032 = ("13", "All employee-facing templates close with the standard signature block", "13 signature")

# ---- seed facts --------------------------------------------------------------------------------------------
TRACKER, TRACKER_SHEET, ABSENCE_SHEET = r"leave_tracker\.xlsx", "Leave Tracker", "Absence Log"
TODAY = "04/10/2026"
RENATA = "renata.okafor@ridgelinegear.com"
ELENA = {"elena.vasquez@ridgelinegear.com", "elenavee@gmail.com"}
JAMES = {"james.nkomo@ridgelinegear.com", "jnkomo.home@gmail.com"}
MARCUS = {"marcus.deluca@ridgelinegear.com", "mdeluca.co@gmail.com"}
AMY = "amy.sandoval@ridgelinegear.com"
HR_TEAM = {"daniel.whitfield@ridgelinegear.com", RENATA, "meera.patel@ridgelinegear.com",
           "jordan.briggs@ridgelinegear.com", "teresa.vang@ridgelinegear.com", "luis.arredondo@ridgelinegear.com",
           "evelyn.marchetti@ridgelineholdings.com", "leaves@ridgelinegear.com", "benefits@ridgelinegear.com"}
EXTERNAL_OK = {"elenavee@gmail.com", "claims@famli.colorado.gov"}
MEDICAL_EMAIL_IDS = {"2", "4", "8", "10", "35"}  # seed emails describing a condition or carrying a certification
FOLDERS = {"FMLA Cases", "FAMLI Cases", "ADA Intake", "HFWA & Paid Leave", "Personal/Military Leave", "Closed Cases",
           "Unknown Senders", "General", "INBOX", "Inbox"}
MANAGER_UIDS = {"U009", "U010", "U011", "U012", "U013"}
MANAGER_HANDLES = ("samir.haddad", "sandra.ellison", "marcus.deluca", "amy.sandoval", "wei.zhang")

MEDICAL_RX = re.compile(r"\bsurg(?:ery|eries|ical)\b|\bdiagnos\w*|\bback (?:issue|pain|condition|injury|problem)s?\b|"
                        r"\bchronic back\b|\bphysical therapy\b|\bmigraines?\b|\bPT appointment", re.I)
PATTERN_RX = re.compile(r"recurring issue|pattern|exceed\w*|variance|suspicio\w*|above (?:the )?certified|"
                        r"more than (?:the )?certified|over (?:the )?certified", re.I)
NKOMO_RX = re.compile(r"Nkomo|LC-2026-0203|R-2401", re.I)
ELENA_CASE_HINT = "LC-2026-NNNN"
PATTERN_NOTE = ("Pattern flagged 04/10/2026 — 5 intermittent absences 03/10–04/07/2026 vs certified 1-2 episodes/month "
               "(+150% over the high end) — escalated to Benefits Manager per Section 12.")
FOLDER_SET_TEXT = ", ".join(sorted(f for f in FOLDERS if f != "Inbox"))


def fold(s) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", norm(s)) if not unicodedata.combining(c))


def mmddyyyy_ok(got, want: str) -> bool:
    """MM/DD/YYYY text, or a real date cell (dumped as 'YYYY-MM-DD 00:00:00') for the same day."""
    g = str(got or "").strip()
    m, d, y = want.split("/")
    return g == want or g == f"{y}-{m}-{d} 00:00:00"


def _cell_key(v) -> str:
    n = num(v)
    return f"{n:.4f}" if n is not None and not re.search(r"[/:-]", str(v)) else nh(v)


def _row_key(r: dict) -> tuple:
    return tuple(_cell_key(v) for k, v in r.items() if k != "__row__" and k)


def row_diff(a: list[dict], b: list[dict]) -> list[dict]:
    """Rows of ``a`` not in ``b`` (multiset); numbers compare by value since an openpyxl save turns 8.0 into 8."""
    rest = [_row_key(r) for r in b]
    out = []
    for r in a:
        k = _row_key(r)
        if k in rest:
            rest.remove(k)
        else:
            out.append(r)
    return out


def _seed_sender(w, eid: str) -> str:
    for e in w.seed_emails:
        if str(e.get("email_id")) == eid:
            return str(e.get("from_addr") or e.get("from") or "").lower()
    return ""


def rcpts(w, a) -> list[str]:
    """To-recipients; a reply without explicit 'to' goes to the original sender."""
    to = list(a.recipients)
    if not to and a.kind in ("email_send", "email_draft") and "reply" in a.tool:
        s = _seed_sender(w, str(a.args.get("email_id") or ""))
        to = [s] if s else []
    return to


def all_rcpts(w, a) -> set[str]:
    return {x.lower() for x in rcpts(w, a)} | {x.lower() for x in a.cc}


def tracker_rows(w, which="current"):
    return w.rows(TRACKER, r"^Case ID$", which, TRACKER_SHEET)


def absence_rows(w, which="current"):
    return w.rows(TRACKER, r"^Absence Date$", which, ABSENCE_SHEET)


def case_row(w, case_id, which="current"):
    return next((r for r in tracker_rows(w, which) if norm(w.col(r, r"^Case ID$")) == norm(case_id)), None)


def elena_rows(w) -> list[dict]:
    init_ids = {norm(w.col(r, r"^Case ID$")) for r in tracker_rows(w, "initial")}
    return [r for r in tracker_rows(w) if norm(w.col(r, r"^Employee ID$")) == "r-2317"
            and norm(w.col(r, r"^Case ID$")) not in init_ids]


def elena_case(w) -> dict | None:
    rows = elena_rows(w)
    return next((r for r in rows if re.search(r"denied", w.col(r, r"^Case Status$"), re.I)), rows[0] if rows else None)


def elena_case_id(w) -> str | None:
    r = elena_case(w)
    cid = w.col(r, r"^Case ID$") if r else ""
    return cid if re.fullmatch(r"LC-2026-\d{4}", cid) else None


@dataclass
class ToAny(Comm):
    """Email whose To must contain at least one of ``any_to`` (e.g. the employee's work or requested personal
    address)."""
    any_to: list = field(default_factory=list)

    def problems(self, a, w):
        out = super().problems(a, w)
        if not self.forbidden and self.any_to and a.kind in ("email_send", "email_draft"):
            if not {x.lower() for x in rcpts(w, a)} & {x.lower() for x in self.any_to}:
                out.insert(0, f"To must be the employee ({' or '.join(self.any_to)}).")
        return out


# ---- message specs -----------------------------------------------------------------------------------------

def specs(ctx) -> list[Comm]:
    w = world(ctx)
    cid = elena_case_id(w)
    cid_rx = re.escape(cid) if cid else r"LC-2026-\d{4}"
    cid_txt = cid or ELENA_CASE_HINT + " (the Case ID you opened in leave_tracker.xlsx)"

    def is_post(a):
        return a.kind in ("slack_post", "slack_dm")

    def to_elena(a):
        return a.kind == "email_send" and bool(all_rcpts(w, a) & ELENA)

    def pattern_post(a):
        if not is_post(a) or "RECURRING ISSUE" not in a.text.upper():
            return False
        return not (a.kind == "slack_post" and not w.dm_recipients(a)
                    and (w.is_channel(a.channel, "benefits-team") or w.is_channel(a.channel, "legal-review")))

    return [
        ToAny("elena_denial", "email", to_elena,
              "FMLA ineligibility notice to Elena Vasquez (Template 3, CC the Benefits Manager, FAMLI referral)",
              [P0898, P0900, P0476, P0332, P1027, P1032, P0970, P0224],
              cc=[RENATA], exact_to=False, any_to=sorted(ELENA),
              body=[(r"NOT currently eligible for FMLA leave",
                     'the Template 3 sentence "...you are NOT currently eligible for FMLA leave for the following '
                     'reason:"'),
                    (r"1,?250", "the failed criterion: FMLA requires at least 1,250 hours worked in the 12 months "
                                "immediately preceding the leave start date"),
                    (r"1,?038", "her hours worked in that period: 1,038 (hours_worked_log.xlsx), below the threshold"),
                    (cid_rx, f"Case ID: {cid_txt}"),
                    (r"claims@famli\.colorado\.gov", "the FAMLI referral: her leave may still qualify under Colorado "
                                                    "FAMLI; she should file a claim directly with CDLE at "
                                                    "claims@famli.colorado.gov"),
                    (r"If you believe this FMLA determination is in error",
                     'the Template 3 line "If you believe this FMLA determination is in error, please reply to this '
                     'email and I will review."'),
                    (r"Ridgeline Gear Co\.\s*[–—-]\s*Leave Coordinator",
                     'the signature "Best regards," / "Ridgeline Gear Co. — Leave Coordinator" / '
                     '"leaves@ridgelinegear.com"')]),
        Comm("elena_denied_post", "slack_post",
             lambda a: is_post(a) and bool(re.search(r"DENIED", a.text, re.I))
             and bool(re.search(r"Vasquez|Elena|R-2317", a.text, re.I)),
             "#leave-intake FMLA DENIED (INELIGIBILITY) post for Elena Vasquez",
             [P0901, P0204, P0171], channel="leave-intake",
             body=[(rf"^\s*FMLA DENIED \(INELIGIBILITY\): {cid_rx}, Elena Vasquez, [^\n]*hours",
                    f"the exact format: FMLA DENIED (INELIGIBILITY): {cid_txt}, Elena Vasquez, Hours (1,038 hours "
                    "worked in the prior 12 months; 1,250 required)")]),
        Comm("nkomo_pattern_post", "slack_post", pattern_post,
             "#hr-escalations RECURRING ISSUE post for LC-2026-0203", [P0938, P0831, P0173, P0817],
             channel="hr-escalations",
             body=[(r"^\s*RECURRING ISSUE: James Nkomo, LC-2026-0203, ",
                    "the exact opening \"RECURRING ISSUE: James Nkomo, LC-2026-0203, \" followed by [Pattern "
                    "Description], [Data Points] — please review."),
                   (r"\d{2}/\d{2}", "the data points (absence dates, e.g. 03/10, 03/19, 03/26, 04/02, 04/07/2026 = 5 "
                                    "absences in 30 days vs certified high end of 2)"),
                   (r"please review", 'the closing "— please review."')]),
        Comm("nkomo_pattern_email", "email",
             lambda a: a.kind == "email_send" and bool(re.search(r"RECURRING ISSUE", a.subject, re.I)),
             "RECURRING ISSUE email/forward to the Benefits Manager for LC-2026-0203", [P0939, P0831, P0130],
             to=[RENATA], exact_to=False, subject=r"(?:(?:Fwd?|FW):\s*)?RECURRING ISSUE – LC-2026-0203",
             subject_hint="RECURRING ISSUE — LC-2026-0203", max_count=2),
        Comm("deluca_payroll", "slack_post",
             lambda a: is_post(a) and "PAYROLL" in a.text.upper() and bool(re.search(r"LC-2026-0320|DeLuca", a.text, re.I)),
             "#payroll-coordination return notification for LC-2026-0320 (jury duty ended, return confirmed 04/10/2026)",
             [P0768, P0845, P0645, P0856, P0651, P0174], channel="payroll-coordination", max_count=2,
             body=[(r"^\s*LEAVE PAYROLL NOTIFICATION: LC-2026-0320, Marcus DeLuca, [^,\n]+, 04/10/2026, Continuous",
                    "the standard format: LEAVE PAYROLL NOTIFICATION: LC-2026-0320, Marcus DeLuca, Return from Leave, "
                    "04/10/2026, Continuous")]),
        Comm("nkomo_payroll", "slack_post",
             lambda a: is_post(a) and "PAYROLL" in a.text.upper() and bool(NKOMO_RX.search(a.text)),
             "#payroll-coordination notification for the 04/07/2026 LC-2026-0203 absence", [P0646, P0651, P0174],
             channel="payroll-coordination", required=False,
             body=[(r"^\s*LEAVE PAYROLL NOTIFICATION: LC-2026-0203, James Nkomo, [^,\n]+, 04/07/2026, Intermittent",
                    "the standard format: LEAVE PAYROLL NOTIFICATION: LC-2026-0203, James Nkomo, Intermittent Absence, "
                    "04/07/2026, Intermittent, 8 hours")]),
    ]


# ---- completion: workbooks ---------------------------------------------------------------------------------

def elena_checks(ctx):
    w = world(ctx)
    refs = [P0202, P0198, P0222, P0435, P0899, P0478]
    rows = elena_rows(w)
    if not rows:
        yield (False, "No case is open in leave_tracker.xlsx (Leave Tracker) for Elena Vasquez's 04/10/2026 request. "
                      "Append ONE row: Case ID = next unused LC-2026-NNNN, Employee ID R-2317, Employee Name Elena "
                      "Vasquez, Start Date 04/20/2026, Expected End Date 05/15/2026, Leave Form Continuous, Priority P2 "
                      "(foreseeable request with < 30 days notice), Case Status Denied, Notes explaining the basis "
                      "(FMLA-ineligible: 1,038 hours in the prior 12 months < 1,250; tenure met).", refs)
        return
    r = elena_case(w)
    cid = w.col(r, r"^Case ID$")
    init_ids = {norm(w.col(x, r"^Case ID$")) for x in tracker_rows(w, "initial")}
    yield (bool(re.fullmatch(r"LC-2026-\d{4}", cid)) and norm(cid) not in init_ids,
           f"Elena's Case ID \"{cid}\" must be a new, unused ID in the format LC-2026-NNNN.",
           [("8.7", "Case ID (generated at intake; format LC-YYYY-NNNN).", "8.7 Case ID")] + refs[:1])
    yield (fold(w.col(r, r"^Employee Name$")) == "elena vasquez",
           "Elena's case row: Employee Name must be \"Elena Vasquez\".", [P0435])
    for col, want in ((r"^Start Date$", "04/20/2026"), (r"^Expected End Date$", "05/15/2026")):
        got = w.col(r, col)
        yield (mmddyyyy_ok(got, want), f"Elena's case {cid}: {col.strip('^$')} must be {want} (MM/DD/YYYY text), "
                                       f"got \"{got}\".", [P0435, P0100])
    yield (bool(re.match(r"continuous", w.col(r, r"^Leave Form$"), re.I)),
           f"Elena's case {cid}: Leave Form must be Continuous (04/20–05/15/2026, one uninterrupted block).", [P0435])
    yield (bool(re.match(r"P2\b", w.col(r, r"^Priority$"))),
           f"Elena's case {cid}: Priority must be P2 — a foreseeable FMLA/FAMLI request submitted with less than 30 "
           f"days notice (requested 04/10 for 04/20); got \"{w.col(r, r'^Priority$')}\".", [P0201, P0225])
    yield (bool(re.search(r"denied", w.col(r, r"^Case Status$"), re.I)),
           f"Elena's case {cid}: Case Status must be Denied (LC-level FMLA ineligibility, hours criterion); got "
           f"\"{w.col(r, r'^Case Status$')}\".", [P0899, P0478])
    yield (bool(re.search(r"1,?038|1,?250|hours", w.col(r, r"^Notes$"), re.I)),
           f"Elena's case {cid}: add a Notes entry explaining the denial basis (FMLA-ineligible: 1,038 hours worked "
           "in the 12 months before 04/20/2026 < 1,250 required; non-exempt; tenure met).", [P0899, P0478])
    lt = w.col(r, r"^Leave Type")
    yield (norm(lt).replace(" ", "") != "fmla+famli",
           f"Elena's case {cid}: Leave Type(s) must not be \"FMLA + FAMLI\" — she is not FMLA-eligible, so no "
           "concurrent FMLA/FAMLI designation applies (FAMLI is not designated until CDLE confirms a claim).",
           [P0499, P0525, P0503])


def nkomo_log_checks(ctx):
    w = world(ctx)
    refs = [P0436, P0807, P0804, P0411, P0630]
    hits = []
    for r in absence_rows(w):
        if norm(w.col(r, r"^Case ID$")) != "lc-2026-0203":
            continue
        d = w.col(r, r"^Absence Date$")
        if re.match(r"0?4/0?7/(20)?26$", d) or d.startswith("2026-04-07"):
            hits.append(r)
    if not hits:
        yield (False, "The 04/07/2026 intermittent absence reported by manager Marcus DeLuca (email \"Nkomo out today "
                      "4/7\", full day) is not in leave_tracker.xlsx Absence Log. Append: LC-2026-0203 | R-2401 | James "
                      "Nkomo | 04/07/2026 | 8.0 | Mgr DeLuca | 428.0 | (non-medical note).", refs)
    else:
        r = hits[0]
        yield (len(hits) == 1, "The 04/07/2026 LC-2026-0203 absence is logged more than once in the Absence Log; keep "
                               "exactly one row.", refs)
        yield (mmddyyyy_ok(w.col(r, r"^Absence Date$"), "04/07/2026"),
               "Absence Log: write the Absence Date as 04/07/2026 (MM/DD/YYYY text).", [P0807, P0100])
        yield (same(w.col(r, r"^Hours Used$"), 8), "Absence Log 04/07/2026: Hours Used must be 8.0 (full day, 1.0 FTE).",
               [P0807])
        yield (same(w.col(r, r"^Running Balance After$"), 428),
               "Absence Log 04/07/2026: Running Balance After must be 428.0 (480 − 52 hours used in the rolling "
               "12 months, including this absence).", [P0807, P0809])
        yield (not blank(w.col(r, r"^Reported By$")), "Absence Log 04/07/2026: Reported By must be filled "
                                                      "(Mgr DeLuca).", [P0807])
    main = case_row(w, "LC-2026-0203")
    if main:
        yield (same(w.col(main, r"^Hours Used To Date$"), 52) and same(w.col(main, r"^Rolling 12-Mo Balance$"), 428),
               "Leave Tracker LC-2026-0203: Hours Used To Date must be 52.0 and Rolling 12-Mo Balance 428.0 (sum of "
               "the Absence Log incl. 04/07/2026; do not count the 04/07 absence twice).", [P0809, P0436])


def absence_append_only(ctx):
    w = world(ctx)
    gone = row_diff(absence_rows(w, "initial"), absence_rows(w))
    eg = " | ".join(nh(v) for k, v in gone[0].items() if k != "__row__")[:120] if gone else ""
    yield (not gone, f"The Absence Log is append-only: {len(gone)} existing row(s) were edited or removed (e.g. {eg}). "
                     "Restore them and only append new rows.", [P0436, P0807])


def nkomo_note_checks(ctx):
    w = world(ctx)
    cur, ini = case_row(w, "LC-2026-0203"), case_row(w, "LC-2026-0203", "initial")
    if not cur:
        yield (False, "Case LC-2026-0203 is missing from leave_tracker.xlsx; restore it.", [P0937])
        return
    notes = w.col(cur, r"^Notes$")
    yield (bool(re.search(r"pattern flagged", notes, re.I)) and bool(re.search(r"benefits manager", notes, re.I)),
           "LC-2026-0203 Notes: append the pattern-flag entry, e.g. \"" + PATTERN_NOTE + "\"", [P0940, P0937])
    if ini:
        yield (nh(w.col(ini, r"^Notes$")) in nh(notes),
               "LC-2026-0203 Notes are a running log: keep the existing entries and append the new one.", [P0937])


def deluca_checks(ctx):
    w = world(ctx)
    refs = [P0768, P0846, P0439, P0850, P0851]
    r, ini = case_row(w, "LC-2026-0320"), case_row(w, "LC-2026-0320", "initial")
    if not r:
        yield (False, "Case LC-2026-0320 is missing from leave_tracker.xlsx; restore it.", refs)
        return
    got = w.col(r, r"^Actual End Date$")
    yield (mmddyyyy_ok(got, "04/10/2026"),
           f"LC-2026-0320 (Marcus DeLuca, jury duty): manager Sandra Ellison posted RETURN CONFIRMED 04/10/2026 in "
           f"#leave-intake. Set Actual End Date = 04/10/2026 (got \"{got}\").", refs + [P0100])
    st = norm(w.col(r, r"^Case Status$"))
    yield (bool(re.fullmatch(r"closed|returned\s*-\s*closing", st)),
           "LC-2026-0320: set Case Status to Closed once the closure checklist is complete (or \"Returned — Closing\" "
           f"while completing it); got \"{w.col(r, r'^Case Status$')}\".", [P0851, P0846, P0847, P0636, P0455])
    if ini:
        old, new = nh(w.col(ini, r"^Notes$")), nh(w.col(r, r"^Notes$"))
        yield (old in new and len(new) > len(old),
               "LC-2026-0320 Notes: keep the existing entries and append the return/closure entry with the date and a "
               "one-line case summary (e.g. \"04/10: RTW confirmed by mgr Ellison. Payroll notified. Case closed "
               "04/10/2026 — jury duty 04/06–04/10/2026.\").", [P0861])


def deluca_housekeeping(ctx):
    w = world(ctx)
    r = case_row(w, "LC-2026-0320")
    if not r or norm(w.col(r, r"^Case Status$")) != "closed":
        return
    cal = any("lc-2026-0320-rtw" in json.dumps(a.args).lower() for a in w.calls("calendar_update", "calendar_delete"))
    yield (cal, "LC-2026-0320 is Closed: mark the calendar event \"Expected Return — LC-2026-0320 Marcus DeLuca (Jury "
                "Duty)\" (id lc-2026-0320-rtw) complete (prefix the summary with [DONE]) or cancel it.", [P0862])
    moved = any("16" in a.recipients and norm(a.channel) == "closed cases" for a in w.calls("email_move"))
    yield (moved, "LC-2026-0320 is Closed: move Marcus DeLuca's jury duty email (\"Jury duty next week\", id 16) to "
                  "the Closed Cases folder.", [P0863, P1021])


def mailbox_checks(ctx):
    w = world(ctx)
    marks = [a for a in w.calls("email_mark") if "35" in a.recipients]
    read = any(a.args.get("is_read") in (True, "true", "True") for a in marks)
    imp = any(a.args.get("is_important") in (True, "true", "True") for a in marks)
    moved = any("35" in a.recipients and norm(a.channel) not in ("inbox", "") for a in w.calls("email_move"))
    yield (read, "Mark Elena's email \"Need to take leave for surgery\" (id 35) as read after processing it.",
           [P1007, P0206])
    if not moved:
        yield (imp, "Elena's case is P2: flag her email (id 35) as important and leave it in the Inbox.", [P1008])


def famli_checks(ctx):
    w = world(ctx)
    name, hdr = r"famli_coordination_log\.xlsx", r"^Employee ID$"
    new = row_diff(w.rows(name, hdr), w.rows(name, hdr, "initial"))
    yield (not new, "famli_coordination_log.xlsx: no CDLE Employer Response notice has been received for any new claim, "
                    "so no FAMLI row may be added yet (the LC only advises the employee to file with CDLE). Remove the "
                    f"added row(s): {[' | '.join(list(x.values())[:3]) for x in new][:2]}.", [P0503, P0512])


def notice_file_checks(ctx):
    w = world(ctx)
    for f in w.files():
        if re.search(r"WH-?38\d", f, re.I) and f.lower().endswith(".pdf"):
            yield (bool(re.search(r"(^|/)R-2317/WH-381_LC-2026-\d{4}_2026\d{4}\.pdf$", f)),
                   f"Completed notice file \"{f}\": save Elena's WH-381 as a PDF in her R-2317/ folder named "
                   "WH-381_[Case ID]_[YYYYMMDD].pdf (e.g. R-2317/WH-381_LC-2026-NNNN_20260410.pdf).", [P0897, P0964])


# ---- pre rules ---------------------------------------------------------------------------------------------

SENDS = ("email_send", "slack_post", "slack_dm")


def no_dm(ctx, a):
    w = world(ctx)
    if a.kind == "slack_dm" or (a.kind == "slack_post" and w.dm_recipients(a)):
        return ("Case-related Slack direct messages are not permitted (they cannot be audited). Post in the "
                "designated channel instead (#leave-intake, #hr-escalations, #payroll-coordination, #benefits-team).")
    return None


def no_medical(ctx, a):
    if a.kind not in SENDS:
        return None
    m = MEDICAL_RX.search(a.text or "")
    if m:
        return (f"The message contains medical detail (\"{m.group(0)}\"). Emails and Slack posts may reference only the "
                "Case ID, dates and general leave type — never the condition, diagnosis or treatment.")
    return None


def no_tag(ctx, a):
    if a.kind != "slack_post":
        return None
    t = a.text or ""
    hit = [u for u in MANAGER_UIDS if f"<@{u}" in t] + [h for h in MANAGER_HANDLES if f"@{h}" in t.lower()]
    return (f"Do not tag managers or non-HR roles in Slack case posts ({', '.join(hit)}); managers are notified by "
            "email templates.") if hit else None


def hr_only(ctx, a):
    w = world(ctx)
    if a.kind != "email_send":
        return None
    to = {x.lower() for x in rcpts(w, a)}
    allowed = HR_TEAM | (ELENA if to & ELENA else set()) | to
    bad = sorted({x.lower() for x in a.cc} - allowed)
    if bad:
        return f"Do not CC anyone outside the HR team on a case email (remove {', '.join(bad)})."
    if "forward" in a.tool and str(a.args.get("email_id") or "") in MEDICAL_EMAIL_IDS:
        out = sorted(all_rcpts(w, a) - HR_TEAM)
        if out:
            return (f"Email {a.args.get('email_id')} contains medical information; do not forward it outside the HR "
                    f"team ({', '.join(out)}).")
    return None


def external(ctx, a):
    w = world(ctx)
    if a.kind != "email_send":
        return None
    bad = sorted(x for x in all_rcpts(w, a) if not x.endswith(("@ridgelinegear.com", "@ridgelineholdings.com"))
                 and x not in EXTERNAL_OK)
    return (f"Do not send case information to {', '.join(bad)}: leave status is never shared with external parties, "
            "and an employee's personal email is used only when that employee asked for it (here only Elena Vasquez: "
            "elenavee@gmail.com).") if bad else None


def roster(w) -> list[dict]:
    return ctx_cache(w, "roster", lambda: [
        {"name": fold(w.col(r, r"^Full Name$")), "emails": {norm(w.col(r, r"^Work Email$")), norm(w.col(r, r"^Personal Email$"))},
         "mgr": norm(w.col(r, r"^Manager Email$")), "id": norm(w.col(r, r"^Employee ID$"))}
        for r in w.rows(r"employee_roster\.xlsx", r"^Employee ID$", "initial")])


def ctx_cache(w, key, fn):
    store = w.__dict__.setdefault("_t929", {})
    if key not in store:
        store[key] = fn()
    return store[key]


def other_employee(ctx, a):
    w = world(ctx)
    if a.kind != "email_send":
        return None
    emps = roster(w)
    case_ids = {norm(w.col(r, r"^Employee ID$")) for r in tracker_rows(w, "initial")} | {"r-2317"}
    by_addr = {e: p for p in emps for e in p["emails"] if e}
    rec = [by_addr[x] for x in all_rcpts(w, a) if x in by_addr and x not in HR_TEAM]
    body = fold(f"{a.subject}\n{a.text}")
    for p in emps:
        if p["id"] not in case_ids or not p["name"] or p["name"] not in body:
            continue
        for r in rec:
            if r["id"] != p["id"] and not (p["mgr"] and p["mgr"] in r["emails"]):
                return (f"This email to {r['name'].title()} discusses {p['name'].title()}'s leave; one employee's leave "
                        "may only be discussed with that employee, their manager of record, or the HR team.")
    return None


def never(ctx, a):
    if a.kind not in SENDS:
        return None
    t = a.text or ""
    if re.search(r"\b(?:will|can|shall|would)\s+(?:be\s+)?(?:retroactive(?:ly)?\s+(?:designat|approv)\w*|"
                 r"(?:designat|approv)\w*\s+retroactive(?:ly)?)", t, re.I):
        return "Never promise retroactive leave designation (Benefits Manager decision)."
    if re.search(r"wage replacement[^.\n]{0,80}(?:\$\s?\d|\d+(?:\.\d+)?\s?%)", t, re.I):
        return ("Never discuss FAMLI wage replacement amounts or rates; direct those questions to CDLE at "
                "claims@famli.colorado.gov.")
    return None


def placeholders(ctx, a):
    if a.kind not in SENDS:
        return None
    left = templates.unfilled_placeholders(text_of(a))
    return f"The message still contains unfilled template placeholders {left}." if left else None


def payroll_channel(ctx, a):
    w = world(ctx)
    if a.kind != "slack_post" or not w.is_channel(a.channel, "payroll-coordination"):
        return None
    m = re.search(r"RECURRING|pattern|DENIED|ineligib|not eligible|serious health|own illness|bonding|surg|diagnos|"
                  r"medical", a.text or "", re.I)
    return (f"#payroll-coordination is for payroll handoffs only (\"{m.group(0)}\" does not belong there); use the "
            "format LEAVE PAYROLL NOTIFICATION: [Case ID], [Employee Name], [Event Type], [Effective Date], "
            "[Continuous/Intermittent], [Notes] with no reason category.") if m else None


def nkomo_confidential(ctx, a):
    w = world(ctx)
    if a.kind in ("email_send", "email_draft"):
        rec = all_rcpts(w, a)
        t = f"{a.subject}\n{a.text}"
        if rec & JAMES and (PATTERN_RX.search(t) or re.search(r"certif|frequen", t, re.I)):
            return ("Do not raise the LC-2026-0203 pattern concern or a recertification request with James Nkomo; the "
                    "flag is escalated to the Benefits Manager, who decides any recertification.")
        if rec & MARCUS and NKOMO_RX.search(t) and (PATTERN_RX.search(t) or re.search(r"frequen", t, re.I)):
            return "Do not disclose the LC-2026-0203 pattern flag or certified frequency to the manager (Marcus DeLuca)."
    if a.kind in ("slack_post", "slack_dm") and NKOMO_RX.search(a.text or "") and PATTERN_RX.search(a.text or ""):
        if a.kind == "slack_dm" or w.dm_recipients(a) or not any(
                w.is_channel(a.channel, c) for c in ("hr-escalations", "benefits-team", "legal-review")):
            return ("LC-2026-0203 pattern details may only go to the escalation chain (#hr-escalations, #benefits-team, "
                    "#legal-review).")
    return None


def elena_not_eligible(ctx, a):
    w = world(ctx)
    t = a.text or ""
    if a.kind in ("email_send", "email_draft") and all_rcpts(w, a) & ELENA:
        if re.search(r"\bARE eligible\b|DESIGNATED as FMLA|WH-382|WH-380", t):
            return ("Elena Vasquez is NOT FMLA-eligible (1,038 hours < 1,250 in the prior 12 months): send the Template 3 "
                    "ineligibility notice, not an eligibility/designation notice or certification request.")
    if a.kind in ("slack_post", "slack_dm") and re.search(r"Elena Vasquez,\s*Eligible\b|FMLA DESIGNATED: [^\n]*Vasquez", t):
        return "Elena Vasquez is NOT FMLA-eligible (1,038 hours < 1,250); post FMLA DENIED (INELIGIBILITY), not eligibility."
    if a.kind == "email_send" and AMY in all_rcpts(w, a) and re.search(r"Elena|Vasquez", t) \
            and re.search(r"approved leave|FMLA leave", t, re.I):
        return ("Elena Vasquez's FMLA request is denied (ineligible) and no FAMLI claim is confirmed: do not send her "
                "manager an approved-leave notification.")
    return None


def folders(ctx, a):
    if a.kind != "email_move":
        return None
    return None if a.channel in FOLDERS else (f"Folder \"{a.channel}\" is not an SOP folder; use exactly one of: "
                                               f"{FOLDER_SET_TEXT}.")


CASE_FILES = re.compile(r"(leave_tracker|leave_history|employee_roster|hours_worked_log|famli_coordination_log|"
                        r"hfwa_balance_tracker)\.xlsx|Ridgeline SOP\.docx|WH-38\d", re.I)


def no_delete(ctx, a):
    if a.kind != "file_delete":
        return None
    return ("Do not delete case files; deletion requires written Benefits Manager authorization."
            if CASE_FILES.search(f"{a.text}\n{json.dumps(a.args)}") else None)


RULES = (
    state_rule("elena.case_row", elena_checks, "Update the Leave Tracker row as listed.")
    + state_rule("nkomo.absence_log", nkomo_log_checks, "Fix the Absence Log / Leave Tracker values as listed.")
    + state_rule("nkomo.pattern_note", nkomo_note_checks, "Append the case note as listed.")
    + state_rule("deluca.close", deluca_checks, "Update case LC-2026-0320 as listed.")
    + state_rule("deluca.housekeeping", deluca_housekeeping, "Complete the closure checklist item.")
    + state_rule("mail.housekeeping", mailbox_checks, "Use the mailbox mark tool as listed.")
    + state_rule("famli.no_unconfirmed_row", famli_checks, "Remove the row.")
    + state_rule("files.notice_name", notice_file_checks, "Rename/move the file as listed.")
    + state_rule("tracker.absence_log_append_only", absence_append_only, "Restore the original Absence Log rows.")
    + comm_rules("comms", specs)
    + pre_rule("comms.no_dm", no_dm, [P0975, P0169])
    + pre_rule("comms.no_medical", no_medical, [P0154, P0148, P0966, P0969, P0177, P0972, P0601, P0654, P1029])
    + pre_rule("comms.no_manager_tags", no_tag, [P0974])
    + pre_rule("comms.hr_only_cc", hr_only, [P0967, P0968])
    + pre_rule("comms.external", external, [P0150, P0979, P0970])
    + pre_rule("comms.other_employee", other_employee, [P0151])
    + pre_rule("comms.never", never, [P0149, P0484, P0531])
    + pre_rule("comms.placeholders", placeholders, [P1028])
    + pre_rule("comms.payroll_channel", payroll_channel, [P0174, P0654])
    + pre_rule("nkomo.confidential", nkomo_confidential, [P0941, P0942, P0952, P0953, P0954, P0956, P0824, P0415])
    + pre_rule("elena.not_eligible", elena_not_eligible, [P0330, P0331, P0332, P0527, P0592])
    + pre_rule("mail.folder_names", folders, [P1024])
    + pre_rule("files.no_delete", no_delete, [P0984, P0985])
    + forbid_writes("files.hours_log_readonly", r"hours_worked_log\.xlsx",
                    "hours_worked_log.xlsx is maintained by Payroll; use its values directly and never edit them.",
                    [P0329])
)
