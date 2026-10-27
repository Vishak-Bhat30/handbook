"""Pathfinder Billing and Coding - ERA_20260417 (BCBS TX) posting and denial routing (task c01deb6e).

Built blind from the SOP (SOP-RCM-024 r3.26), the instruction and the seed workspace only.
Expected values below are derived from ERA_20260417.xlsx, PBC_Claim_Register.xlsx, PBC_Fee_Schedule.xlsx,
PBC_NCCI_Edits.xlsx, the BCTX denial letter and the 03/20/2026 operative report:
  0845 / 0878 / 1104  paid == BCTX contracted rate (142 / 228 / 1850)     -> clean post
  0892  CO-16 N382 (wrong subscriber id)                                   -> Correct and Resubmit (freq 7)
  1105  CO-97 N520, 29881+29876 NCCI indicator 1, separate knees (op rpt)  -> Add Modifier (LT) and Resubmit
  0967  CO-45 N130, paid 4200 vs contracted 6900, Dollar Value 7500        -> Held - Contractual Variance,
        Appeal - Contractual Rate Dispute, escalation Financial / Payer Dispute
  CO-16 for Dr. Sarah Chen: 0234, 0356, 0489, 0612 (worklist) + 0892 = 5   -> Pattern Recurrence log + email
"""

from __future__ import annotations

import json
import re
import subprocess

from .. import config
from ..kit import (COMM_KINDS, Action, Comm, Context, World, append_only, comm_rules, no_placeholders, norm,
                   num, pre_rule, prior_denials, same, state_rule, text_of, world)

TODAY = "04/24/2026"
ACTOR, ACTOR_ROLE = "Maria Santos", "Resolution Auditor"
RCM_MANAGER, RCM_EMAIL = "David Park", "david.park@pathfinderbilling.com"
INTERNAL_DOMAIN = "@pathfinderbilling.com"

REG = r"(^|/)PBC_Claim_Register\.xlsx$"
DEN = r"(^|/)PBC_Denial_Worklist\.xlsx$"
RAQ = r"(^|/)PBC_RA_Queue\.xlsx$"
ESC = r"(^|/)PBC_Escalation_Log\.xlsx$"
REFERENCE = r"(^|/)(ERA_20260417|PBC_Fee_Schedule|PBC_NCCI_Edits)\.xlsx$"

# ERA_20260417 lines: claim -> (CPT, paid, adjustment); patient responsibility is $0.00 on every line.
ERA = {"CLM-2026-0845": ("99213", 142, 38), "CLM-2026-0878": ("99214", 228, 57),
       "CLM-2026-0892": ("99214", 0, 285), "CLM-2026-1104": ("29881", 1850, 350),
       "CLM-2026-1105": ("29876", 0, 1850), "CLM-2026-0967": ("27447", 4200, 3300)}
CLEAN = {"CLM-2026-0845": ("Paid - Full",), "CLM-2026-0878": ("Paid - Full",),
         # 1104 and 1105 are the same operative session; the SOP's multi-line rule may read them as one claim.
         "CLM-2026-1104": ("Paid - Full", "Paid - Partial")}
DENIED_STATUS = {"CLM-2026-0892": ("Denied", "Resubmitted", "In Recovery"),
                 "CLM-2026-1105": ("Denied", "Resubmitted", "In Recovery", "Paid - Partial")}
VARIANCE = "CLM-2026-0967"
POSTING_FIELDS = ("Claim Status", "Payment Amount", "Adjustment Amount", "Patient Balance",
                  "Payment Posting Status", "CARC", "RARC", "Provider Query Status")

DENIALS = {  # claim -> expected Denial Worklist values (None = not enforced)
    "CLM-2026-0892": {"Patient ID": "PAT-1042", "Patient Name": "Michael Torres", "Date of Service": "03/15/2026",
                      "Payer": "BlueCross TX", "CARC": "CO-16", "RARC": "N382",
                      "Denial Category": "Technical/Administrative", "Recovery Action": "Correct and Resubmit",
                      "Recovery Status": "Resubmitted", "Date Opened": TODAY},
    "CLM-2026-1105": {"Patient ID": "PAT-1058", "Patient Name": "Linda Park", "Date of Service": "03/20/2026",
                      "Payer": "BlueCross TX", "CARC": "CO-97", "RARC": "N520",
                      "Denial Category": "Technical/Administrative", "Recovery Action": "Add Modifier and Resubmit",
                      "Recovery Status": "Resubmitted", "Date Opened": TODAY},
    "CLM-2026-0967": {"Patient ID": "PAT-1063", "Patient Name": "Robert Daniels", "Date of Service": "03/08/2026",
                      "Payer": "BlueCross TX", "CARC": "CO-45", "RARC": "N130",
                      "Denial Category": "Contractual/Payer Error",
                      "Recovery Action": "Appeal - Contractual Rate Dispute", "Date Opened": TODAY},
}
CORRECTED = ("CLM-2026-0892", "CLM-2026-1105")
COPY_FIELDS = ("Patient ID", "Date of Service", "Provider NPI", "Payer", "Payer ID", "CPT Code", "ICD-10 Code",
               "Dollar Value")
PATTERN_CLAIMS = {"CLM-2026-0234": "PAT-1008", "CLM-2026-0356": "PAT-1012", "CLM-2026-0489": "PAT-1019",
                  "CLM-2026-0612": "PAT-1027", "CLM-2026-0892": "PAT-1042"}

VOCAB = {
    "Claim Status": ("New", "Submitted", "Acknowledged", "Denied", "In Recovery", "Resubmitted", "Appealed",
                     "Paid - Full", "Paid - Partial", "On Hold", "Closed", "Written Off"),
    "Recovery Action": ("Correct and Resubmit", "Update COB and Resubmit", "Add Modifier and Resubmit",
                        "Appeal - Documentation Supports Service", "Appeal - Payer Processing Error",
                        "Appeal - Timely Filing Exception", "Appeal - Contractual Rate Dispute",
                        "Appeal - Medical Necessity", "Appeal - Prior Auth on File", "Escalate to Resolution Auditor",
                        "Escalate to RCM Manager", "Write Off"),
    "Recovery Status": ("Pending Review", "In Progress", "Resubmitted", "Appealed", "Escalated", "Resolved",
                        "Written Off"),
    "Payment Posting Status": ("Posted", "Held - Batch Mismatch", "Held - Contractual Variance",
                               "Held - PLB Variance", "Unapplied", "Reconciled"),
    "Escalation Category": ("Operational", "Financial", "Critical"),
    "Escalation Reason": ("Pattern Recurrence", "High Value Claim", "High-Value Dispute", "TFL Approaching",
                          "Payer Dispute", "Legal Threat Received", "PHI Incident", "Payer System Outage",
                          "Provider Non-Response"),
    "Provider Query Status": ("Sent", "Response Received", "Overdue", "Escalated", "Resolved"),
    "Denial Category": ("Technical/Administrative", "Clinical/Coding", "Patient/Coverage", "Contractual/Payer Error"),
}
NAME_COLS = ("Assigned Auditor", "Escalated By", "Escalated To")
FILENAME = {REG: "PBC_Claim_Register.xlsx", DEN: "PBC_Denial_Worklist.xlsx", RAQ: "PBC_RA_Queue.xlsx",
            ESC: "PBC_Escalation_Log.xlsx"}
FILES = {  # file -> (id column, id prefix, date columns, controlled columns)
    REG: ("Claim ID", "CLM", ("Date of Service",),
          ("Claim Status", "Payment Posting Status", "Provider Query Status")),
    DEN: ("Denial ID", "DEN", ("Date of Service", "Date Opened", "Date Resolved"),
          ("Denial Category", "Recovery Action", "Recovery Status")),
    RAQ: ("Queue Entry ID", "RA", ("Queue Entry Date", "Resolution Date"), ()),
    ESC: ("Escalation ID", "ESC", ("Date", "Date Resolved"), ("Escalation Category", "Escalation Reason")),
}

# ---- SOP references ------------------------------------------------------------------------------
R_POST = ("7.1", "Posting a payment means matching each ERA line", "7.1 payment posting")
R_DEPOSIT = ("7.1", "1. The Deposit Match", "7.1 Deposit Match")
R_LINE = ("7.1", "2. The Line-Item Verification", "7.1 Line-Item Verification")
R_CONTRACT = ("7.1", "3. The Contractual Adjustment Verification", "7.1 Contractual Adjustment Verification")
R_PLB = ("7.1", "4. The PLB Audit", "7.1 PLB Audit")
R_BATCH_ROW = ("7.1", "Batch Total | Must match bank deposit", "7.1 Batch Total checkpoint")
R_VAR_ROW = ("7.1", "Contractual Adj | Paid amount plus", "7.1 Contractual Adj checkpoint")
R_PLB_ROW = ("7.1", "PLB Mismatch |", "7.1 PLB checkpoint")
R_MULTI = ("7.1", "When a claim has multiple lines with mixed outcomes", "7.1 mixed outcomes")
R_SIGNOFF = ("7.3", "4. The Sign-off:", "7.3 Sign-off")
R_TRIAGE = ("6.1", "When a denial is identified", "6.1 Denial Triage")
R_TRIAGE2 = ("6.1", "PBC_Denial_Worklist.xlsx with Recovery Status set to Pending Review", "6.1 Denial Triage")
R_CAT_TECH = ("6.1", "Technical/Administrative | CO-16, CO-97", "6.1 category table")
R_CAT_CONTRACT = ("6.1", "Contractual/Payer Error | CO-45", "6.1 category table")
R_CAT_NOTE = ("6.1", "Note: Denial Categories (this table)", "6.1 note")
R_PLANS = ("6.2", "All denials require a specific Recovery Plan", "6.2 Recovery Plans")
R_CO16_FIX = ("6.2", "3. Correction: Update the claim", "6.2 CO-16 step 3")
R_CO16_WL = ("6.2", "4. Update PBC_Denial_Worklist.xlsx : Set Recovery Action to Correct", "6.2 CO-16 step 4")
R_CO16_PATTERN = ("6.2", "5. Pattern Check", "6.2 CO-16 step 5 Pattern Check")
R_CO45_AUDIT = ("1", "1. Contract Audit", "6.2 CO-45 step 1")
R_CO45_CASE = ("1", "2. Case Review: If the payment matches", "6.2 CO-45 step 2")
R_CO45_REASON = ("1", "3. Escalation Reason: Use the Payer Dispute", "6.2 CO-45 step 3")
R_CO97_NCCI = ("1", "1. NCCI Edit Check", "6.2 CO-97 step 1")
R_CO97_MOD = ("1", "2. Modifier Review", "6.2 CO-97 step 2")
R_CO97_RESUB = ("1", "4. Resubmit with the appropriate modifier", "6.2 CO-97 step 4")
R_IND1 = ("8.2", "Indicator 1:", "8.2 NCCI Indicator 1")
R_MOD59 = ("8.3", "Precision Rule: Modifier 59", "8.3 Modifier 59")
R_LTRT = ("8.5", "-RT / -LT", "8.5 anatomical modifiers")
R_BILAT = ("8.5", "-50 (Bilateral)", "8.5 bilateral modifier")
R_HVC = ("4.3", "Escalation Reason High Value Claim is used", "4.3 escalation reasons")
R_CHAIN = ("9.1", "Information only moves upward", "9.1 Escalation Chain")
R_OPER = ("9.1", "Operational | Technical coding", "9.1 Operational level")
R_FIN = ("9.1", "Financial | Any single claim dispute", "9.1 Financial level")
R_ROUTING = ("9.1", "For internal routing, add a row", "9.1 routing")
R_CATEGORY = ("9.1", "The escalation category is determined", "9.1 category by Dollar Value")
R_COMMS = ("10", "All external communication must be professional", "10 communication content")
R_PR_USE = ("10.5", "Use this when a pattern recurrence threshold", "10.5 Pattern Recurrence Report")
R_PR_BODY = ("10.5", "This is [Your Name], [Your Role]", "10.5 Pattern Recurrence Report")
R_PR_LOG = ("10.5", "Escalation Log Entry ID:", "10.5 Pattern Recurrence Report")
R_PHI = ("11.2", "Communication Protocol: PHI must never", "11.2 Communication Protocol")
R_ISOLATION = ("1.3", "Data Isolation:", "1.3 Data Isolation")
R_RA_AUTH = ("2.2", "Authorization Level: The Resolution Auditor is authorized", "2.2 RA authorization")
R_VOCAB = ("13.4", "Every status or action field uses controlled values", "Appendix B")
R_DATES = ("1", "Dates: MM/DD/YYYY", "Appendix B date format")
R_MONEY = ("1", "Dollar Amounts:", "Appendix B dollar format")
R_IDS = ("1", "Identifier Formats:", "Appendix B identifier formats")
R_NPI = ("1", "NPI: 10-digit", "Appendix B NPI format")
R_NAMES = ("1", "Names: All names", "Appendix B names")
R_F_REG = ("13.4", "PBC_Claim_Register.xlsx | Master claim record", "Appendix A")
R_F_DEN = ("13.4", "PBC_Denial_Worklist.xlsx | Active denials", "Appendix A")
R_F_RAQ = ("13.4", "PBC_RA_Queue.xlsx | Resolution Auditor", "Appendix A")
R_F_ESC = ("13.4", "PBC_Escalation_Log.xlsx | All escalations", "Appendix A")
R_F_FEE = ("13.4", "PBC_Fee_Schedule.xlsx | Contracted rates", "Appendix A")
R_F_ERA = ("13.4", "ERA_[BatchID].xlsx | Inbound payment file", "Appendix A")


# ---- helpers -------------------------------------------------------------------------------------

def c(row: dict | None, name: str) -> str:
    return World.col(row, rf"^{re.escape(name)}$") if row else ""


def rows(w: World, f: str, which: str = "current") -> list[dict]:
    return w.rows(f, rf"^{re.escape(FILES[f][0])}$", which)


def reg_row(w: World, claim: str, which: str = "current") -> dict | None:
    return next((r for r in rows(w, REG, which) if norm(c(r, "Claim ID")) == norm(claim)), None)


def added(w: World, f: str) -> list[dict]:
    """Rows whose ID was not in the initial file (edited initial rows are not 'added')."""
    idc = FILES[f][0]
    old = {norm(c(r, idc)) for r in rows(w, f, "initial")}
    return [r for r in rows(w, f) if norm(c(r, idc)) not in old or not c(r, idc)]


def money(v) -> str:
    return f"${v:,.2f}"


def is_vocab(value: str, col: str) -> bool:
    return any(norm(value) == norm(v) for v in VOCAB[col])


def tokens(mod: str) -> set[str]:
    return {t for t in re.split(r"[\s,;/+&-]+", mod.upper()) if t}


def esc_kind(r: dict) -> str:
    if norm(c(r, "Escalation Reason")) == "pattern recurrence" or "CLM-2026-0892" in c(r, "Claim ID(s)").upper():
        return "pattern"
    if VARIANCE in c(r, "Claim ID(s)").upper():
        return "payer_dispute"
    return ""


def pattern_email(w: World) -> Action | None:
    return next((a for a in w.calls("email_send") if is_pattern_email(a)), None)


def is_pattern_email(a: Action) -> bool:
    return a.kind == "email_send" and bool(re.search(r"pattern\s+recurrence", text_of(a), re.I))


# ---- completion: payment posting -----------------------------------------------------------------

def _amount_issues(r: dict, claim: str) -> list[str]:
    _, paid, adj = ERA[claim]
    out = []
    for col, want in (("Payment Amount", paid), ("Adjustment Amount", adj), ("Patient Balance", 0)):
        if not same(c(r, col), want):
            out.append(f"{col} = {money(want)} (now '{c(r, col)}')")
    return out


def clean_checks(ctx: Context):
    w = world(ctx)
    for claim, statuses in CLEAN.items():
        r = reg_row(w, claim)
        if r is None:
            yield False, f"{claim} is missing from PBC_Claim_Register.xlsx.", [R_POST]
            continue
        issues = _amount_issues(r, claim)
        if norm(c(r, "Claim Status")) not in {norm(s) for s in statuses}:
            issues.append(f"Claim Status = {' or '.join(statuses)} (now '{c(r, 'Claim Status')}')")
        if norm(c(r, "Payment Posting Status")) not in ("posted", "reconciled"):
            issues.append(f"Payment Posting Status = Reconciled (or Posted) (now '{c(r, 'Payment Posting Status')}')")
        yield (not issues, f"ERA_20260417 line for {claim} (CPT {ERA[claim][0]}) paid the BCTX contracted rate and "
                           f"passes the batch, line, contractual and PLB checks, so post it in PBC_Claim_Register.xlsx: "
                           + "; ".join(issues) + ".",
               [R_POST, R_LINE, R_CONTRACT, R_DEPOSIT, R_PLB, R_SIGNOFF, R_MULTI])


def denied_checks(ctx: Context):
    w = world(ctx)
    for claim, statuses in DENIED_STATUS.items():
        r = reg_row(w, claim)
        if r is None:
            continue
        issues = _amount_issues(r, claim)
        if norm(c(r, "Claim Status")) not in {norm(s) for s in statuses}:
            issues.append(f"Claim Status = Denied (or Resubmitted / In Recovery) (now '{c(r, 'Claim Status')}')")
        yield (not issues, f"Record the ERA_20260417 denial line on original claim {claim} in PBC_Claim_Register.xlsx "
                           "(the exact Paid and Adjustment Amounts from the ERA, even for a denied line): "
                           + "; ".join(issues) + ".", [R_POST, R_TRIAGE])


def variance_checks(ctx: Context):
    w = world(ctx)
    r = reg_row(w, VARIANCE)
    if r is None:
        return
    issues = _amount_issues(r, VARIANCE)
    if norm(c(r, "Payment Posting Status")) != norm("Held - Contractual Variance"):
        issues.append(f"Payment Posting Status = Held - Contractual Variance (now '{c(r, 'Payment Posting Status')}')")
    if norm(c(r, "Claim Status")) != "in recovery":
        issues.append(f"Claim Status = In Recovery (now '{c(r, 'Claim Status')}')")
    yield (not issues, f"{VARIANCE} (CPT 27447, BlueCross TX): paid $4,200.00 but the contracted rate in "
                       "PBC_Fee_Schedule.xlsx is $6,900.00, so the payment is held and the CO-45 goes to an appeal "
                       "(no write-off - the $2,700.00 shortfall exceeds the Resolution Auditor's $250.00 limit). "
                       "In PBC_Claim_Register.xlsx set: " + "; ".join(issues) + ".",
           [R_CONTRACT, R_VAR_ROW, R_CO45_AUDIT, R_CO45_CASE, R_RA_AUTH])


# ---- completion: denial routing ------------------------------------------------------------------

def worklist_checks(ctx: Context):
    w = world(ctx)
    new = added(w, DEN)
    for claim, want in DENIALS.items():
        hits = [r for r in new if norm(c(r, "Claim ID")) == norm(claim)]
        refs = [R_TRIAGE, R_TRIAGE2, R_PLANS] + (
            [R_CAT_TECH, R_CO16_WL] if claim == "CLM-2026-0892" else
            [R_CAT_TECH, R_CO97_RESUB] if claim == "CLM-2026-1105" else [R_CAT_CONTRACT, R_CO45_CASE])
        spec = "; ".join(f"{k} = {v}" for k, v in want.items())
        if not hits:
            yield False, (f"Add a row to PBC_Denial_Worklist.xlsx for the {want['CARC']} denial on {claim} (next "
                          f"DEN-2026-NNNN id): Claim ID = {claim}; {spec}."), refs
            continue
        r = hits[0]
        issues = [f"{k} = {v} (now '{c(r, k)}')" for k, v in want.items() if not same(c(r, k), v)]
        yield not issues, f"Denial Worklist row for {claim} ({c(r, 'Denial ID')}): set " + "; ".join(issues) + ".", refs


def corrected_checks(ctx: Context):
    w = world(ctx)
    new = added(w, REG)
    for orig in CORRECTED:
        base = reg_row(w, orig, "initial") or {}
        hits = [r for r in new if norm(c(r, "Original Claim ID")) == norm(orig)]
        mod_note = " with Modifier LT (29876 was performed on the left knee - a separate anatomical site per the " \
                   "03/20/2026 operative report; NCCI 29881/29876 is indicator 1, and the anatomical modifier is " \
                   "used before 59)" if orig == "CLM-2026-1105" else \
                   " (corrected subscriber ID BCTX-TOR-8872491 per the BCTX denial letter)"
        refs = ([R_PLANS, R_CO16_FIX] if orig == "CLM-2026-0892" else
                [R_PLANS, R_CO97_NCCI, R_CO97_MOD, R_CO97_RESUB, R_IND1, R_MOD59, R_LTRT, R_BILAT])
        if not hits:
            yield False, (f"Resubmit {orig} as a corrected claim: add a new row to PBC_Claim_Register.xlsx with the next "
                          f"CLM-2026-NNNN id, Claim Frequency Code = 7, Original Claim ID = {orig}, and the same "
                          f"Patient ID / Date of Service / NPI / Payer / CPT / ICD-10 / Dollar Value as {orig}"
                          f"{mod_note}."), refs
            continue
        r = hits[0]
        issues = []
        if num(c(r, "Claim Frequency Code")) != 7:
            issues.append(f"Claim Frequency Code = 7 (now '{c(r, 'Claim Frequency Code')}')")
        for col in COPY_FIELDS:
            if base and not same(c(r, col), c(base, col)):
                issues.append(f"{col} = {c(base, col)} as on {orig} (now '{c(r, col)}')")
        if orig == "CLM-2026-1105":
            t = tokens(c(r, "Modifier"))
            if "LT" not in t:
                issues.append(f"Modifier = LT (now '{c(r, 'Modifier')}')")
            if "50" in t:
                issues.append("remove modifier 50 (bilateral is only for the same procedure on both sides)")
        yield (not issues, f"Corrected claim {c(r, 'Claim ID')} for {orig}{mod_note}: set " + "; ".join(issues) + ".",
               refs)


def ra_queue_checks(ctx: Context):
    w = world(ctx)
    new = added(w, RAQ)
    for claim, want in DENIALS.items():
        hits = [r for r in new if norm(c(r, "Claim ID")) == norm(claim)]
        if not hits:
            yield False, (f"Route the {want['CARC']} on {claim} to the Resolution Auditor: add a row to "
                          f"PBC_RA_Queue.xlsx (next RA-2026-NNNN id) with Queue Entry Date = {TODAY}, Claim ID = "
                          f"{claim}, Patient ID = {want['Patient ID']}."), [R_TRIAGE, R_VAR_ROW, R_F_RAQ]
            continue
        r = hits[0]
        issues = [f"{k} = {v} (now '{c(r, k)}')" for k, v in (("Patient ID", want["Patient ID"]),
                                                               ("Queue Entry Date", TODAY)) if not same(c(r, k), v)]
        yield not issues, f"RA Queue row for {claim}: set " + "; ".join(issues) + ".", [R_TRIAGE, R_F_RAQ]


def _esc_issues(r: dict, category: str, reason: str) -> list[str]:
    want = (("Date", TODAY), ("Escalation Category", category), ("Escalation Reason", reason),
            ("Escalated By", ACTOR), ("Escalated To", RCM_MANAGER))
    return [f"{k} = {v} (now '{c(r, k)}')" for k, v in want if not same(c(r, k), v)]


def payer_dispute_checks(ctx: Context):
    w = world(ctx)
    hits = [r for r in added(w, ESC) if esc_kind(r) == "payer_dispute"]
    refs = [R_CO45_CASE, R_CO45_REASON, R_HVC, R_FIN, R_CATEGORY, R_CHAIN]
    want = (f"Date = {TODAY}; Claim ID(s) = {VARIANCE}; Escalation Category = Financial (Dollar Value $7,500.00 is "
            f"between $5,000 and $10,000); Escalation Reason = Payer Dispute (High Value Claim needs two failed "
            f"Resolution Goal cycles); Escalated By = {ACTOR}; Escalated To = {RCM_MANAGER}")
    if not hits:
        yield False, f"Log the CO-45 contractual rate dispute in PBC_Escalation_Log.xlsx (next ESC-2026-NNNN id): {want}.", refs
        return
    issues = _esc_issues(hits[0], "Financial", "Payer Dispute")
    yield not issues, f"Escalation {c(hits[0], 'Escalation ID')} for {VARIANCE}: set " + "; ".join(issues) + ".", refs


def pattern_checks(ctx: Context):
    w = world(ctx)
    hits = [r for r in added(w, ESC) if esc_kind(r) == "pattern"]
    refs = [R_CO16_PATTERN, R_PR_USE, R_PR_LOG, R_OPER, R_CATEGORY]
    claims = ", ".join(PATTERN_CLAIMS)
    if not hits:
        yield False, ("CO-16 has now occurred 5 times for Dr. Sarah Chen (NPI 1234567890): " + claims + ". Log it in "
                      f"PBC_Escalation_Log.xlsx (next ESC-2026-NNNN id): Date = {TODAY}; Claim ID(s) = {claims}; "
                      f"Escalation Category = Operational; Escalation Reason = Pattern Recurrence; Escalated By = "
                      f"{ACTOR}; Escalated To = {RCM_MANAGER}."), refs
        return
    r = hits[0]
    issues = _esc_issues(r, "Operational", "Pattern Recurrence")
    if "CLM-2026-0892" not in c(r, "Claim ID(s)").upper():
        issues.append(f"Claim ID(s) = {claims}")
    yield not issues, f"Pattern Recurrence escalation {c(r, 'Escalation ID')}: set " + "; ".join(issues) + ".", refs
    a = pattern_email(w)
    if a is not None:
        m = re.search(r"Escalation Log Entry ID:?\s*(ESC-\d{4}-\d{4})", a.text, re.I)
        esc_id = c(r, "Escalation ID")
        yield (not m or norm(m.group(1)) == norm(esc_id),
               f"The Pattern Recurrence email cites {m.group(1) if m else ''} but the Pattern Recurrence row in "
               f"PBC_Escalation_Log.xlsx is {esc_id}; the log entry id must match the email.", refs)


# ---- completion: record integrity ----------------------------------------------------------------

def extra_row_checks(ctx: Context):
    w = world(ctx)
    expected = {REG: (CORRECTED, "Original Claim ID", "corrected claims for CLM-2026-0892 and CLM-2026-1105"),
                DEN: (tuple(DENIALS), "Claim ID", "the three denials in ERA_20260417 (0892, 1105, 0967)"),
                RAQ: (tuple(DENIALS), "Claim ID", "the three denials in ERA_20260417 (0892, 1105, 0967)")}
    for f, (keys, col, what) in expected.items():
        seen: dict[str, int] = {}
        for r in added(w, f):
            k = c(r, col).upper()
            seen[k] = seen.get(k, 0) + 1
            if k not in keys:
                yield False, (f"Unrequested new row in {FILENAME[f]}: "
                              f"{FILES[f][0]} {c(r, FILES[f][0])} ({col} '{c(r, col)}'). Only add rows for {what}; "
                              "remove it."), [R_PLANS, R_TRIAGE]
        for k, n in seen.items():
            yield n <= 1 or k not in keys, f"Duplicate new rows for {k} ({n}); keep one.", [R_PLANS, R_TRIAGE]
    kinds: dict[str, int] = {}
    for r in added(w, ESC):
        k = esc_kind(r)
        kinds[k] = kinds.get(k, 0) + 1
        if not k:
            yield False, (f"Unrequested escalation {c(r, 'Escalation ID')} ({c(r, 'Claim ID(s)')}, "
                          f"{c(r, 'Escalation Reason')}): only the CO-45 Payer Dispute on {VARIANCE} and the CO-16 "
                          "Pattern Recurrence meet an escalation trigger in this batch. Remove it."), [R_CHAIN]
    for k, n in kinds.items():
        yield n <= 1 or not k, f"Duplicate {k.replace('_', ' ')} escalations ({n}) in PBC_Escalation_Log.xlsx; keep one.", [R_CHAIN]


def register_untouched_checks(ctx: Context):
    w = world(ctx)
    cur = {norm(c(r, "Claim ID")): r for r in rows(w, REG)}
    for old in rows(w, REG, "initial"):
        cid = c(old, "Claim ID")
        new = cur.get(norm(cid))
        if new is None:
            yield False, f"Claim {cid} was removed from PBC_Claim_Register.xlsx; restore it.", [R_F_REG, R_PLANS]
            continue
        free = POSTING_FIELDS if cid in ERA else ()
        changed = [k for k in old if k != "__row__" and k not in free and not same(c(new, k), c(old, k) or None)]
        yield (not changed, f"PBC_Claim_Register.xlsx row {cid}: {', '.join(changed)} changed but this ERA does not "
                            f"call for it (corrections go on a new frequency-7 row). Restore: "
                            + "; ".join(f"{k} = '{c(old, k)}'" for k in changed) + ".", [R_F_REG, R_PLANS, R_POST])


def reference_checks(ctx: Context):
    w = world(ctx)
    for f in w.changed_files():
        if re.search(REFERENCE, f, re.I):
            yield False, (f"{f} is a payer / reference file and must stay as received; restore its original "
                          "contents."), [R_F_ERA, R_F_FEE]


def id_checks(ctx: Context):
    w = world(ctx)
    for f, (idc, prefix, _, _) in FILES.items():
        old_nums = [int(m.group(1)) for r in rows(w, f, "initial")
                    for m in [re.fullmatch(rf"{prefix}-2026-(\d{{4}})", c(r, idc))] if m]
        top = max(old_nums or [0])
        new = added(w, f)
        bad = [c(r, idc) for r in new if not re.fullmatch(rf"{prefix}-2026-\d{{4}}", c(r, idc))]
        nums = sorted(int(c(r, idc)[-4:]) for r in new if c(r, idc) not in bad)
        want = list(range(top + 1, top + 1 + len(new)))
        ok = not bad and nums == want
        yield (ok, f"New {idc}s in {prefix} file must be assigned sequentially from the highest existing id "
                   f"({prefix}-2026-{top:04d}) in the format {prefix}-2026-NNNN: expected "
                   f"{', '.join(f'{prefix}-2026-{n:04d}' for n in want)}, got "
                   f"{', '.join(c(r, idc) for r in new)}.", [R_IDS])
        all_ids = [c(r, idc) for r in rows(w, f) if c(r, idc)]
        dup = sorted({i for i in all_ids if all_ids.count(i) > 1})
        yield not dup, f"Duplicate {idc}s in {prefix} file: {', '.join(dup)}.", [R_IDS]


def format_checks(ctx: Context):
    w = world(ctx)
    for f, (idc, prefix, dates, controlled) in FILES.items():
        new = added(w, f)
        touched = new + ([reg_row(w, k) for k in ERA if reg_row(w, k)] if f == REG else [])
        for r in new:
            for col in dates:
                v = c(r, col)
                if v and not re.fullmatch(r"\d{2}/\d{2}/\d{4}", v):
                    yield False, (f"{c(r, idc)} {col} = '{v}': dates are written MM/DD/YYYY as text like the existing "
                                  f"rows (e.g. {TODAY})."), [R_DATES]
            for col in NAME_COLS:
                v = c(r, col)
                if v and not re.fullmatch(r"[A-Z][a-z]+ [A-Z][a-z]+", v):
                    yield False, (f"{c(r, idc)} {col} = '{v}': names are written as first and last name only "
                                  f"(e.g. {ACTOR}, {RCM_MANAGER})."), [R_NAMES]
            if f == REG:
                for col in ("Provider NPI",):
                    v = c(r, col)
                    if v and not re.fullmatch(r"\d{10}", v):
                        yield False, f"{c(r, idc)} {col} = '{v}': NPI is 10 digits, no separators.", [R_NPI]
        for r in touched:
            for col in controlled:
                v = c(r, col)
                if v and not is_vocab(v, col):
                    yield False, (f"{c(r, idc)} {col} = '{v}' is not a controlled value. Use one of: "
                                  f"{' / '.join(VOCAB[col])}."), [R_VOCAB, R_CAT_NOTE]
            if f == REG and c(r, "Claim Frequency Code") and num(c(r, "Claim Frequency Code")) not in (1, 7, 8):
                yield False, f"{c(r, idc)} Claim Frequency Code must be 1, 7 or 8.", [R_VOCAB]


MONEY_SCRIPT = r"""
import json, sys, openpyxl
ws = openpyxl.load_workbook(sys.argv[1]).worksheets[0]
hdr = [str(c.value).strip() if c.value is not None else "" for c in ws[1]]
out = []
for row in ws.iter_rows(min_row=2):
    d = {hdr[i]: [None if c.value is None else c.value if isinstance(c.value, (int, float, str)) else str(c.value),
                  c.number_format] for i, c in enumerate(row) if i < len(hdr)}
    out.append(d)
print(json.dumps(out))
"""
MONEY_COLS = ("Dollar Value", "Payment Amount", "Adjustment Amount", "Patient Balance")


def money_checks(ctx: Context):
    w = world(ctx)
    path = next((config.workdir() / k for k in w.current or {} if re.search(REG, k)), None)
    if path is None:
        return
    try:
        proc = subprocess.run([config.xlsx_python(), "-c", MONEY_SCRIPT, str(path)], capture_output=True, text=True,
                              timeout=60)
        cells = json.loads(proc.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return
    initial = {norm(c(r, "Claim ID")) for r in rows(w, REG, "initial")}
    for d in cells:
        cid = str((d.get("Claim ID") or [""])[0] or "")
        if not cid or (norm(cid) in initial and cid not in ERA):
            continue
        for col in MONEY_COLS:
            v, fmt = d.get(col, [None, ""])
            if v is None or v == "":
                continue
            ok = (isinstance(v, (int, float)) and "$" in str(fmt) and "0.00" in str(fmt)) or \
                 (isinstance(v, str) and re.fullmatch(r"\$\d{1,3}(,\d{3})*\.\d{2}", v.strip()))
            if not ok:
                yield False, (f"{cid} {col} ({v!r}, format '{fmt}') must display as $#,##0.00 (e.g. $1,850.00): "
                              "keep it numeric and set number_format '$#,##0.00'."), [R_MONEY]


# ---- pre rules -----------------------------------------------------------------------------------

def _phi_patterns(ctx: Context) -> list[tuple[str, str]]:
    def build():
        w = world(ctx)
        names = {c(r, "Patient Name") for r in rows(w, REG, "initial") if c(r, "Patient Name")}
        pats = [(rf"\b{re.escape(n)}\b", f"patient name '{n}'") for n in sorted(names)]
        pats += [(r"\bBCTX-[A-Z]{3}-\d{7}\b", "member/subscriber ID"),
                 (r"\b(?:07/14/1978|09/22/1965)\b|\bDOB\b", "date of birth"),
                 (r"\bAO-\d{4}-\d{4}\b", "medical record number")]
        return pats
    return ctx.memo("c01deb6e.phi", build)


def phi_problem(ctx: Context, a: Action) -> str | None:
    if a.kind not in COMM_KINDS:
        return None
    external = [x for x in a.recipients + a.cc if not x.lower().endswith(INTERNAL_DOMAIN)]
    slack = a.kind in ("slack_post", "slack_dm")
    if not slack and not external:
        return None
    pats = _phi_patterns(ctx) + ([] if slack else [(r"\bPAT-\d{4}\b", "internal patient ID")])
    hits = [d for rx, d in pats if re.search(rx, text_of(a), re.I)]
    if not hits:
        return None
    where = "a Slack message" if slack else f"standard email to {', '.join(external)}"
    return (f"[phi] This {where} contains PHI ({'; '.join(hits[:4])}). PHI must never be sent by standard email or "
            "Slack; refer to the claim by Claim ID only, or keep patient details in the PBC files / internal email.")


def _register_index(ctx: Context) -> dict[str, dict]:
    def build():
        w = world(ctx)
        out = {}
        for which in ("initial", "current"):
            for r in rows(w, REG, which):
                if c(r, "Claim ID"):
                    out.setdefault(c(r, "Claim ID").upper(), r)
        return out
    return ctx.memo("c01deb6e.regidx", build)


def _dos_rx(dos: str) -> str:
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", dos)
    if not m:
        return re.escape(dos)
    mm, dd, yy = m.groups()
    return rf"(?:0?{int(mm)}/0?{int(dd)}/{yy}|{yy}-{mm}-{dd})"


PAYER_ALIASES = {"bluecross tx": r"BlueCross|Blue Cross|BCBS|BCTX", "aetna": r"Aetna|AETN1",
                 "unitedhealth": r"United\s?Health|UHC|UNHC1", "cigna": r"Cigna|CIGNA1"}


def claim_ref_problem(ctx: Context, a: Action) -> str | None:
    if a.kind != "email_send" or prior_denials(ctx, "[claim-ref]") >= 2:
        return None
    text = text_of(a)
    idx = _register_index(ctx)
    missing = []
    for cid in sorted(set(m.upper() for m in re.findall(r"CLM-\d{4}-\d{4}", text, re.I))):
        r = idx.get(cid)
        if r is None:
            continue
        need = []
        if c(r, "Patient ID") and c(r, "Patient ID") not in text:
            need.append(f"Patient ID {c(r, 'Patient ID')}")
        if c(r, "Date of Service") and not re.search(_dos_rx(c(r, "Date of Service")), text):
            need.append(f"DOS {c(r, 'Date of Service')}")
        if c(r, "CPT Code") and c(r, "CPT Code") not in text:
            need.append(f"CPT {c(r, 'CPT Code')}")
        payer = PAYER_ALIASES.get(norm(c(r, "Payer")), re.escape(c(r, "Payer")))
        if c(r, "Payer") and not re.search(payer, text, re.I):
            need.append(f"Payer {c(r, 'Payer')}")
        if need:
            missing.append(f"{cid}: {', '.join(need)}")
    if not missing and re.search(r"CLM-\d{4}-\d{4}", text) and not any(
            re.search(rf"\b{re.escape(s)}\b", text, re.I) for s in VOCAB["Claim Status"]):
        missing.append("the current Claim Status from the register")
    if not missing:
        return None
    return ("[claim-ref] A message that references a claim must include Claim ID, Patient ID, DOS, CPT code(s), "
            "Payer and the current Claim Status. Missing - " + " | ".join(missing) + ".")


# ---- message specs -------------------------------------------------------------------------------

def specs(ctx: Context) -> list[Comm]:
    body = [(r"Pattern Recurrence Report\s*[-–—:]\s*04/24/2026", 'the header "Pattern Recurrence Report — 04/24/2026"'),
            (rf"This is {ACTOR}, {ACTOR_ROLE}, reporting a pattern recurrence for (Dr\.? )?Sarah Chen, NPI:? 1234567890",
             f'"This is {ACTOR}, {ACTOR_ROLE}, reporting a pattern recurrence for Dr. Sarah Chen, NPI: 1234567890."'),
            (r"Denial Code:? CO-16 – RARC:? N382 – 5 instances",
             '"Denial Code: CO-16 — RARC: N382 — 5 instances identified."'),
            (r"Assessment:", 'an "Assessment:" paragraph'),
            (r"Escalation Log Entry ID:? ESC-2026-\d{4}", '"Escalation Log Entry ID: ESC-2026-NNNN" (the log row id)'),
            (r"Escalation Category:? Operational", '"Escalation Category: Operational"'),
            (r"Escalation Reason:? Pattern Recurrence", '"Escalation Reason: Pattern Recurrence"')]
    for cid, pat in PATTERN_CLAIMS.items():
        body.append((rf"Claim ID:? {cid}\b.*?{pat}", f"the line for Claim ID {cid} with Patient ID {pat}"))
    return [Comm(
        key="pattern_report", kind="email", about=is_pattern_email,
        what="Pattern Recurrence Report email to the RCM Manager (CO-16, Dr. Sarah Chen, 5 instances)",
        refs=[R_CO16_PATTERN, R_PR_USE, R_PR_BODY, R_PR_LOG], to=[RCM_EMAIL], exact_to=False,
        subject=r"Pattern Recurrence Alert: (Dr\.? )?Sarah Chen – CO-16 – 5 Instances",
        subject_hint="Pattern Recurrence Alert: Dr. Sarah Chen — CO-16 — 5 Instances", body=body)]


RULES = (
    state_rule("pbc.post_clean_lines", clean_checks, "Update the claim register row as listed.")
    + state_rule("pbc.post_denied_lines", denied_checks, "Update the claim register row as listed.")
    + state_rule("pbc.contractual_variance", variance_checks, "Update the claim register row as listed.")
    + state_rule("pbc.denial_worklist", worklist_checks, "Add / fix the Denial Worklist row as listed.")
    + state_rule("pbc.corrected_claims", corrected_checks, "Add / fix the corrected claim row as listed.")
    + state_rule("pbc.ra_queue", ra_queue_checks, "Add / fix the RA Queue row as listed.")
    + state_rule("pbc.escalation_payer_dispute", payer_dispute_checks, "Add / fix the Escalation Log row as listed.")
    + state_rule("pbc.escalation_pattern", pattern_checks, "Add / fix the Escalation Log row as listed.")
    + comm_rules("pbc.pattern_report", specs)
    + state_rule("pbc.no_extra_rows", extra_row_checks, "Remove the extra row(s).")
    + state_rule("pbc.register_untouched", register_untouched_checks, "Restore the original values.")
    + state_rule("pbc.reference_files_unchanged", reference_checks, "Restore the original file.")
    + append_only("pbc.escalation_log_append_only", ESC, r"^Escalation ID$", "PBC_Escalation_Log.xlsx", [R_F_ESC])
    + append_only("pbc.denial_worklist_append_only", DEN, r"^Denial ID$", "PBC_Denial_Worklist.xlsx", [R_F_DEN])
    + append_only("pbc.ra_queue_append_only", RAQ, r"^Queue Entry ID$", "PBC_RA_Queue.xlsx", [R_F_RAQ])
    + state_rule("pbc.new_ids_sequential", id_checks, "Renumber the new rows as listed.")
    + state_rule("pbc.field_formats", format_checks, "Fix the field value as listed.")
    + state_rule("pbc.money_format", money_checks, "Fix the cell format as listed.")
    + pre_rule("pbc.phi_in_messages", phi_problem, [R_PHI, R_ISOLATION],
               "Remove the PHI from the message (use Claim IDs) or keep it out of Slack / external email.")
    + pre_rule("pbc.claim_reference_fields", claim_ref_problem, [R_COMMS],
               "Add the missing claim details and send again.")
    + no_placeholders([R_PR_USE])
)
