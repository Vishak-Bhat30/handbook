"""Verifiers for medical_pathfinder_billing_and_coding_073e602b (SOP-RCM-024, Pathfinder Billing and Coding).

Situation (from seed data): RCM Manager Joe Malfroy asks to follow up Hull Insurance (A4789P) payments for
CPT 11241. Against PBC_Fee_Schedule.xlsx (A4789P / 11241: $80 for 2025 DOS, $75 for 2026 DOS, patient
contribution not included) every Hull 11241 claim in the register was paid $10 short - 9 claims, $90 total:
six already Reconciled (manager-directed review -> CO-45 recovery, posting status untouched) and three Posted
from today's ERA (-> Held - Contractual Variance). 9 >= 5 from one payer -> Pattern Recurrence escalation
(email report + single Escalation Log entry). CO-45 mismatch -> RA queue, Denial Worklist (Appeal -
Contractual Rate Dispute / Escalated) and a Contractual Rate Dispute to Hull saved as a draft (instruction).
"""

from __future__ import annotations

import re

from ..kit import (Comm, Context, Ref, append_only, comm_rules, dashes, norm, pre_rule, state_rule,
                   text_of, world)
from .. import templates

TODAY_US = "02/17/2026"
MANAGER = "Joe Malfroy"
MANAGER_EMAIL = "joem@pathfinder.com"
HULL_CONTACT = "ursula.james@hull.com"
PAYER, PAYER_ID, CPT = "Hull Insurance", "A4789P", "11241"

# (claim id, DOS, contracted rate, paid, initial Payment_Post_Status) - fee schedule vs claim register/ERAs.
CLAIMS = [
    ("HIC-19887899", "2025-12-01", 80, 70, "Reconciled"),
    ("HIC-19887900", "2025-12-01", 80, 70, "Reconciled"),
    ("HIC-19887901", "2025-12-03", 80, 70, "Reconciled"),
    ("HIC-25124778", "2025-12-10", 80, 70, "Reconciled"),
    ("HIC-25124779", "2025-12-12", 80, 70, "Reconciled"),
    ("HIC-25124780", "2025-12-15", 80, 70, "Reconciled"),
    ("HIC-26877757", "2025-12-29", 80, 70, "Posted"),
    ("HIC-26877758", "2026-01-02", 75, 65, "Posted"),
    ("HIC-26877795", "2026-01-05", 75, 65, "Posted"),
]
IDS = [c[0] for c in CLAIMS]
TOTAL = sum(c[2] - c[3] for c in CLAIMS)  # 90

R_PATTERN: Ref = ("2.2", "Escalation Trigger: The Billing Specialist will immediately", "2.2 Billing Specialist escalation")
R_DENIAL_TRIAGE: Ref = ("6.1", "When a denial is identified (Triggers: CO-, PR-, OA-)", "6.1 Denial Triage")
R_CO45_ROW: Ref = ("6.1", "Contractual/Payer Error | CO-45", "6.1 Denial category table")
R_RECOVERY: Ref = ("6.2", "All denials require a specific Recovery Plan", "6.2 Recovery Plans")
R_CO45: Ref = ("6.2", "Case Review: If the payment matches the contracted rate", "6.2 CO-45 Case Review")
R_HOLD: Ref = ("7.1", "The Contractual Adjustment Verification:", "7.1 Contractual Adjustment Verification")
R_HOLD_ROW: Ref = ("7.1", "Contractual Adj | Must match the contracted rate", "7.1 Accuracy Check table")
R_RECONCILED: Ref = ("7.1", "Manager-Directed Variance Review:", "7.1 Manager-Directed Variance Review")
R_LOG_ALL: Ref = ("9.1", "Information only moves upward or horizontally", "9.1 Escalation Chain")
R_QUEUE: Ref = ("9.1", "For internal routing, add a row to the appropriate queue file", "9.1 internal routing")
R_REDUNDANCY: Ref = ("9.4", "To prevent tasks from disappearing", "9.4 Escalation Redundancy Rule")
R_CALENDAR: Ref = ("4.1", "Tasks are prioritized by impact on the clinic", "4.1 calendar")
R_DISPUTE_TPL: Ref = ("10.5", "Subject: Contractual Rate Dispute", "10.5 Contractual Rate Dispute template")
R_PATTERN_TPL: Ref = ("10.6", "Use this when 5 or more claim-related issues", "10.6 Pattern Recurrence Report")
R_PHI: Ref = ("1.3", "Data Isolation: All patient data", "1.3 Data Isolation")
R_PHI_COMM: Ref = ("11.2", "Communication Protocol: PHI must never be sent", "11.2 Communication Protocol")
R_RA_FILE: Ref = ("13.4", "PBC_RA_Queue.xlsx | Resolution Auditor", "Appendix A RA queue")
R_AUDIT: Ref = ("12.2", "To ensure the CCR remains at or above 98%", "12.2 Weekly Precision Audit")
R_FEE_FILE: Ref = ("13.4", "PBC_Fee_Schedule.xlsx | Contracted rates", "Appendix A Fee Schedule")
R_ERA_FILE: Ref = ("13.4", "ERA_[BatchID].xlsx | Inbound payment file", "Appendix A ERA files")
R_CONTROLLED: Ref = ("13.4", "Every status or action field uses controlled values", "Appendix B")
R_V_CLAIM: Ref = ("13.4", "New · Submitted · Acknowledged", "Appendix B Claim Status")
R_V_ACTION: Ref = ("1", "Correct and Resubmit · Update COB and Resubmit", "Appendix B Denial Recovery Action")
R_V_RSTATUS: Ref = ("1", "Pending Review · In Progress", "Appendix B Denial Recovery Status")
R_V_POST: Ref = ("1", "Posted · Held - Batch Mismatch", "Appendix B Payment Posting Status")
R_V_CAT: Ref = ("1", "Operational (under $5,000)", "Appendix B Escalation Category")
R_V_REASON: Ref = ("1", "Pattern Recurrence · High Value Claim", "Appendix B Escalation Reason")
R_V_RA: Ref = ("1", "Open · Closed", "Appendix B RA Queue Status")

CLAIM_STATUS = ["New", "Submitted", "Acknowledged", "Denied", "In Recovery", "Resubmitted", "Appealed",
                "Paid - Full", "Paid - Partial", "On Hold", "Closed", "Written Off"]
RECOVERY_ACTION = ["Correct and Resubmit", "Update COB and Resubmit", "Add Modifier and Resubmit",
                   "Appeal - Documentation Supports Service", "Appeal - Payer Processing Error",
                   "Appeal - Timely Filing Exception", "Appeal - Contractual Rate Dispute", "Appeal - Medical Necessity",
                   "Appeal - Prior Auth on File", "Escalate to Resolution Auditor", "Escalate to RCM Manager",
                   "Write Off"]
RECOVERY_STATUS = ["Pending Review", "In Progress", "Resubmitted", "Appealed", "Escalated", "Resolved", "Written Off"]
POST_STATUS = ["Posted", "Held - Batch Mismatch", "Held - Contractual Variance", "Held - PLB Variance", "Unapplied",
               "Reconciled"]
ESC_CATEGORY = ["Operational", "Financial", "Critical"]
ESC_REASON = ["Pattern Recurrence", "High Value Claim", "TFL Approaching", "Payer Dispute", "Legal Threat Received",
              "PHI Incident", "Payer System Outage", "Provider Non-Response"]
DENIAL_CATEGORY = ["Technical/Administrative", "Clinical/Coding", "Patient/Coverage", "Contractual/Payer Error"]

REGISTER, RA_QUEUE, WORKLIST, ESC_LOG = r"PBC_Claim_Register", r"PBC_RA_Queue", r"PBC_Denial_Worklist", r"PBC_Escalation_Log"


def _money(v: int) -> str:
    return rf"-?\s?\$?\s?{v}(?:\.00)?(?!\d)"


def _today(v: str) -> bool:
    return norm(v) in ("02/17/2026", "2/17/2026", "2026-02-17", "2026-02-17 00:00:00")


def _ids_in(cell: str) -> set[str]:
    return set(re.findall(r"HIC-\d{8}", cell or "", re.I))


def _in(v: str, allowed: list[str]) -> bool:
    return norm(v) in {norm(x) for x in allowed}


# ---- claim register (7.1 hold / manager-directed review / CO-45 no closure) -----------------------------------

def _register(ctx: Context):
    w = world(ctx)
    for cid, _, rate, paid, start in CLAIMS:
        row = w.find(REGISTER, r"^Payment_Post_Status$", r"^Claim_ID$", cid)
        if row is None:
            yield False, f"{cid} is no longer in PBC_Claim_Register.xlsx; restore the row.", [R_RECONCILED]
            continue
        post, status = w.col(row, r"^Payment_Post_Status$"), w.col(row, r"^Claim_Status$")
        if start == "Reconciled":
            yield (norm(post) == "reconciled",
                   f"{cid} was already Reconciled when the RCM Manager requested this variance review; its Payment "
                   f"Posting Status must stay \"Reconciled\" (got \"{post}\").", [R_RECONCILED])
        else:
            yield (norm(post) == norm("Held - Contractual Variance"),
                   f"{cid} (posted from today's ERA, paid ${paid} vs contracted ${rate}) fails the contractual "
                   "adjustment check: set "
                   f"Payment_Post_Status to \"Held - Contractual Variance\" in PBC_Claim_Register.xlsx (got \"{post}\").",
                   [R_HOLD_ROW, R_HOLD])
        yield (norm(status) not in ("written off", "closed"),
               f"{cid} is underpaid against the contracted rate, so it goes to a Contractual Rate Dispute - it must not "
               f"be set to \"{status}\".", [R_CO45])


# ---- RA queue / denial worklist (6.1, 6.2 CO-45, 7.1, 9.1) --------------------------------------------------

def _ra_queue(ctx: Context):
    rows = world(ctx).new_rows(RA_QUEUE, r"^Staff_Assigned$")
    col = world(ctx).col
    missing = []
    for cid in IDS:
        ok = any(cid in _ids_in(col(r, r"^Claim_ID")) and re.search(r"CO-?\s?45", col(r, r"^Trigger$"), re.I)
                 and _today(col(r, r"^Trigger_Date")) and norm(col(r, r"^Staff_Assigned")).startswith("joe malfroy")
                 and norm(col(r, r"^Status$")) == "open" for r in rows)
        if not ok:
            missing.append(cid)
    yield (not missing,
           f"PBC_RA_Queue.xlsx needs a row per underpaid claim routing it to the Resolution Auditor: Claim_ID=<claim>, "
           f"Trigger=\"CO-45\", Trigger_Date=\"{TODAY_US}\", Staff_Assigned=\"{MANAGER}\" (instruction: put the RCM "
           f"Manager first), Status=\"Open\". Missing/incomplete for: {', '.join(missing)}.",
           [R_DENIAL_TRIAGE, R_HOLD_ROW, R_QUEUE, R_RA_FILE])


def _worklist(ctx: Context):
    rows = world(ctx).new_rows(WORKLIST, r"^Recovery_Action$")
    col = world(ctx).col
    missing = []
    for cid in IDS:
        ok = any(cid in _ids_in(col(r, r"^Claim_ID")) and norm(col(r, r"^Category$")) == norm("Contractual/Payer Error")
                 and re.fullmatch(r"co-?\s?45", norm(col(r, r"^CO_Code$")))
                 and norm(col(r, r"^Recovery_Action$")) == norm("Appeal - Contractual Rate Dispute")
                 and norm(col(r, r"^Recovery_Status$")) == "escalated" and _today(col(r, r"^Date_Logged"))
                 for r in rows)
        if not ok:
            missing.append(cid)
    yield (not missing,
           "PBC_Denial_Worklist.xlsx needs a row per underpaid claim: Category=\"Contractual/Payer Error\", "
           f"Claim_ID=<claim>, CO_Code=\"CO-45\", Recovery_Action=\"Appeal - Contractual Rate Dispute\", "
           f"Date_Logged=\"{TODAY_US}\", Recovery_Status=\"Escalated\". Missing/incomplete for: {', '.join(missing)}.",
           [R_DENIAL_TRIAGE, R_CO45_ROW, R_RECOVERY, R_CO45])


# ---- escalation log (2.2 pattern recurrence, single entry) ---------------------------------------------------

def _esc_log(ctx: Context):
    w = world(ctx)
    rows = [r for r in w.new_rows(ESC_LOG, r"^Esc_Reason$") if norm(w.col(r, r"^Esc_Reason$")) == "pattern recurrence"]
    want = (f"Claim_ID=\"{', '.join(IDS)}\", Payer_ID=\"{PAYER_ID}\", Category=\"Operational\" (total variance "
            f"${TOTAL} < $5,000), Esc_Reason=\"Pattern Recurrence\", Resolution_Tkg=\"RCM Manager on {TODAY_US}\"")
    if not rows:
        yield False, f"Log the pattern recurrence escalation as a single new row in PBC_Escalation_Log.xlsx: {want}.", \
            [R_PATTERN, R_LOG_ALL]
        return
    yield len(rows) == 1, (f"Log a single Pattern Recurrence entry in PBC_Escalation_Log.xlsx ({len(rows)} were "
                           "added); remove the duplicates."), [R_PATTERN]
    r = rows[0]
    bad = []
    if not set(IDS) <= _ids_in(w.col(r, r"^Claim_ID")):
        bad.append(f"Claim_ID must list all 9 claims (missing {', '.join(sorted(set(IDS) - _ids_in(w.col(r, r'^Claim_ID'))))})")
    if norm(w.col(r, r"^Payer_ID")) != norm(PAYER_ID):
        bad.append(f"Payer_ID must be \"{PAYER_ID}\"")
    if not norm(w.col(r, r"^Category$")).startswith("operational"):
        bad.append("Category must be \"Operational\" (under $5,000)")
    if not re.fullmatch(r"rcm manager on 0?2/17/2026", norm(w.col(r, r"^Resolution"))):
        bad.append(f"Resolution_Tkg must be \"RCM Manager on {TODAY_US}\"")
    yield not bad, "Pattern Recurrence row in PBC_Escalation_Log.xlsx: " + "; ".join(bad) + f". Expected: {want}.", \
        [R_PATTERN, R_LOG_ALL]


# ---- calendar record of the escalation attempt (9.4) ---------------------------------------------------------

def _calendar(ctx: Context):
    for a in world(ctx).calls("calendar_create", "calendar_update"):
        t = f"{a.subject}\n{a.args.get('description', '')}"
        if ("2026-02-17" in str(a.args.get("start", "")) and re.search(r"escalat|pattern", t, re.I)
                and re.search(r"hull|a4789p|11241|HIC-", t, re.I)):
            return [(True, "", [])]
    return [(False, "Create a calendar event dated today (2026-02-17, the time the escalation was made) recording "
                    "the Hull A4789P / CPT 11241 pattern-recurrence escalation to the RCM Manager (e.g. summary "
                    "\"Escalation - Pattern Recurrence - Hull Insurance (A4789P) CPT 11241\").",
             [R_REDUNDANCY, R_CALENDAR])]


# ---- data integrity ------------------------------------------------------------------------------------------

def _sources_unchanged(ctx: Context):
    w = world(ctx)
    changed = [f for f in w.changed_files() if re.search(r"ERA_|PBC_Fee_Schedule|PBC_Eligibility|PBC_NCCI|RARC", f, re.I)]
    return [(not changed, f"Source data files must not be modified ({', '.join(changed)}); they are inbound payer/"
                          "reference data. Restore them.", [R_FEE_FILE, R_ERA_FILE])]


def _controlled(ctx: Context):
    w = world(ctx)
    bad = []
    for r in w.rows(REGISTER, r"^Payment_Post_Status$"):
        for rx, allowed, name in ((r"^Claim_Status$", CLAIM_STATUS, "Claim_Status"),
                                  (r"^Payment_Post_Status$", POST_STATUS, "Payment_Post_Status")):
            v = w.col(r, rx)
            if v and not _in(v, allowed):
                bad.append(f"PBC_Claim_Register {w.col(r, '^Claim_ID$')} {name}=\"{v}\" (allowed: {' · '.join(allowed)})")
    for r in w.new_rows(WORKLIST, r"^Recovery_Action$"):
        for rx, allowed, name in ((r"^Category$", DENIAL_CATEGORY, "Category"),
                                  (r"^Recovery_Action$", RECOVERY_ACTION, "Recovery_Action"),
                                  (r"^Recovery_Status$", RECOVERY_STATUS, "Recovery_Status")):
            v = w.col(r, rx)
            if not _in(v, allowed):
                bad.append(f"PBC_Denial_Worklist {w.col(r, '^Claim_ID$')} {name}=\"{v}\" (allowed: {' · '.join(allowed)})")
    for r in w.new_rows(ESC_LOG, r"^Esc_Reason$"):
        cat, reason = w.col(r, r"^Category$"), w.col(r, r"^Esc_Reason$")
        if not any(norm(cat).startswith(norm(c)) for c in ESC_CATEGORY):
            bad.append(f"PBC_Escalation_Log Category=\"{cat}\" (allowed: Operational · Financial · Critical)")
        if not _in(reason, ESC_REASON):
            bad.append(f"PBC_Escalation_Log Esc_Reason=\"{reason}\" (allowed: {' · '.join(ESC_REASON)})")
    for r in w.new_rows(RA_QUEUE, r"^Staff_Assigned$"):
        v = w.col(r, r"^Status$")
        if not _in(v, ["Open", "Closed"]):
            bad.append(f"PBC_RA_Queue {w.col(r, '^Claim_ID')} Status=\"{v}\" (allowed: Open · Closed)")
    return [(not bad, "Status/action fields must use the Appendix B controlled values: " + "; ".join(bad[:6]) + ".",
             [R_CONTROLLED, R_V_CLAIM, R_V_POST, R_V_ACTION, R_V_RSTATUS, R_V_CAT, R_V_REASON, R_V_RA])]


# ---- messages ------------------------------------------------------------------------------------------------

def _external(a) -> list[str]:
    return [x for x in a.recipients + a.cc if not x.lower().endswith("@pathfinder.com")]


def _dispute_line(cid, dos, rate, paid) -> tuple[str, str]:
    rx = (rf"{cid}\s*\|\s*{dos}\s*\|\s*Contracted:\s*{_money(rate)}\s*\|\s*Paid:\s*{_money(paid)}\s*\|\s*"
          rf"Variance:\s*{_money(rate - paid)}")
    return rx, f"the line \"{cid} | {dos} | Contracted: ${rate} | Paid: ${paid} | Variance: ${rate - paid}\""


def _pattern_line(cid, rate, paid) -> tuple[str, str]:
    rx = rf"{cid}\s*\|\s*Contracted:\s*{_money(rate)}[^|]{{0,30}}\|\s*Paid:\s*{_money(paid)}"
    return rx, f"the line \"{cid} | Contracted: ${rate} | Paid: ${paid}\""


def _is_dispute(a) -> bool:
    if a.kind not in ("email_send", "email_draft"):
        return False
    if not (re.search(r"contractual rate dispute", a.subject, re.I) or
            re.search(r"formally dispute the payment amounts", dashes(a.text), re.I)):
        return False
    return a.kind == "email_draft" or bool(_external(a))


def _specs(ctx: Context) -> list[Comm]:
    dispute_body = [
        (r"formally dispute the payment amounts received for CPT 11241 under Payer ID A4789P",
         "\"I am writing on behalf of Pathfinder Billing and Coding to formally dispute the payment amounts received "
         "for CPT 11241 under Payer ID A4789P.\""),
        (r"paid below the contracted rate", "\"The following claim(s) were paid below the contracted rate with no "
                                            "adjustment reason code provided:\""),
        *[_dispute_line(cid, dos, rate, paid) for cid, dos, rate, paid, _ in CLAIMS],
        (rf"Total outstanding variance:\s*{_money(TOTAL)}", f"\"Total outstanding variance: ${TOTAL}\""),
    ]
    pattern_body = [
        (r"\bJoe\b", "the greeting \"Joe,\" ([RCM Manager First Name])"),
        (r"pattern recurrence for Hull Insurance \(A4789P\) affecting 9 claims for CPT 11241",
         "\"I am escalating a pattern recurrence for Hull Insurance (A4789P) affecting 9 claims for CPT 11241. All "
         "instances share the same discrepancy:\""),
        *[_pattern_line(cid, rate, paid) for cid, _, rate, paid, _ in CLAIMS],
        (rf"Total variance:\s*{_money(TOTAL)}", f"\"Total variance: ${TOTAL}.\""),
    ]
    return [
        Comm("rate_dispute", "draft", _is_dispute,
             "Contractual Rate Dispute to Hull Insurance (Section 10.5 template), saved as a DRAFT - not sent "
             "(task instruction)",
             [R_CO45, R_DISPUTE_TPL], to=[HULL_CONTACT], exact_to=False,
             subject=r"Contractual Rate Dispute\s*[-–—]\s*Hull Insurance\s*/\s*A4789P\s*/\s*CPT 11241",
             subject_hint="Contractual Rate Dispute — Hull Insurance / A4789P / CPT 11241",
             body=dispute_body, max_count=3,
             keep_placeholders=("[X]", "[Your Name]", "[Payer Billing/Appeals Contact Name]")),
        Comm("pattern_report", "email",
             lambda a: a.kind == "email_send" and bool(re.search(r"pattern recurrence", a.subject, re.I)),
             "Pattern Recurrence Report to the RCM Manager (Section 10.6) containing the 9 instances",
             [R_PATTERN, R_PATTERN_TPL], to=[MANAGER_EMAIL], exact_to=False,
             subject=r"Pattern Recurrence\s*[-–—]\s*Hull Insurance\s*/\s*A4789P\s*/\s*CPT 11241",
             subject_hint="Pattern Recurrence — Hull Insurance / A4789P / CPT 11241",
             body=pattern_body),
    ]


def _no_external_send(ctx: Context, a):
    if a.kind != "email_send":
        return None
    ext = _external(a)
    return (f"Payer/external correspondence ({', '.join(ext)}) must be saved as an email draft with the completed "
            "template, not sent (task instruction).") if ext else None


_HULL_PHI = re.compile("|".join(IDS + ["Hull", "A4789P", "Michelle Jule", "Edward Tee", "Optee Bowler",
                                       "Georgie Knowles", "Myles Goh", "BR87594", "FQ12578", "MU78445", "YE87154",
                                       "JP00012"]), re.I)


def _phi_recipients(ctx: Context, a):
    if a.kind not in ("email_send", "email_draft") or not _HULL_PHI.search(text_of(a)):
        return None
    wrong = [x for x in a.recipients + a.cc if not re.search(r"@(pathfinder\.com|hull\.com)$", x, re.I)]
    return (f"This message carries Hull claim/patient data (PHI) but is addressed to {', '.join(wrong)}, who is "
            "neither PBC staff nor Hull Insurance.") if wrong else None


def _sent_placeholders(ctx: Context, a):
    if a.kind not in ("email_send", "slack_post", "slack_dm"):
        return None
    left = templates.unfilled_placeholders(text_of(a))
    return f"[placeholders] The message still contains template placeholders {left}." if left else None


RULES = [
    *state_rule("pbc.claim_register", _register, "Update PBC_Claim_Register.xlsx as listed."),
    *state_rule("pbc.ra_queue", _ra_queue, "Append the RA queue rows as listed."),
    *state_rule("pbc.denial_worklist", _worklist, "Append the Denial Worklist rows as listed."),
    *state_rule("pbc.escalation_log", _esc_log, "Fix PBC_Escalation_Log.xlsx as listed."),
    *state_rule("pbc.escalation_calendar", _calendar, "Create the calendar event."),
    *state_rule("pbc.sources_unchanged", _sources_unchanged, "Restore the original file."),
    *state_rule("pbc.controlled_values", _controlled, "Use the exact Appendix B value."),
    *append_only("pbc.escalation_log_append_only", ESC_LOG, r"^Esc_Reason$", "PBC_Escalation_Log.xlsx", [R_LOG_ALL]),
    *append_only("pbc.audit_log_append_only", r"PBC_Audit_Log", r"^Audit_Date$", "PBC_Audit_Log.xlsx", [R_AUDIT]),
    *comm_rules("pbc.comms", _specs),
    *pre_rule("pbc.no_external_send", _no_external_send, [R_CO45, R_DISPUTE_TPL],
              "Save it with google_mail__save_draft instead."),
    *pre_rule("pbc.phi_recipients", _phi_recipients, [R_PHI, R_PHI_COMM],
              "Address it only to PBC staff (@pathfinder.com) or Hull's contact (ursula.james@hull.com)."),
    *pre_rule("pbc.no_placeholders", _sent_placeholders, [R_PATTERN_TPL],
              "Replace every bracketed field with the actual value before sending."),
]
