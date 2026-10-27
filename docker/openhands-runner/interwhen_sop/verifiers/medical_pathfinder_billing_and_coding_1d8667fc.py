"""Verifiers for medical_pathfinder_billing_and_coding_1d8667fc (blind build, scripts/algo.md Steps 0-4).

Situation (seed data only): the unread email is BCBS 835 ERA EFT-BCBS-20260315-00047312 for Northside Internal
Medicine; the attachment is /workdir/ERA_20260315_BCBS.xlsx (batch ID 20260315_BCBS, payment date 2026-03-15).
Accuracy check (SOP 7.1):
- Deposit match: header Payment Amount 167.00 = Net EFT 167.00 -> no batch mismatch.
- CLM-1008 BCBS 99215: paid 180 + patient resp 30 = 210 = contracted 210; 180+30+70 = billed 280 -> post,
  Paid - Full / Posted.
- CLM-1033 BCBS 99214: paid 142 + patient resp 20 = 162 vs contracted 165 -> Held - Contractual Variance
  (a $3 SBWO write-off reading of 5.1 is also accepted).
- PLB: claims 322 - 30 - 125 = 167 = deposit -> reconciles, no PLB variance. RECOUP-2026-0107 = CLM-1016
  overpayment: paid 172 vs payer share 162 allowed - 20 patient resp = 142 -> 30.00, matches the recoupment, so
  CLM-1016 Notes get 'Clawback applied 2026-03-15: $30.00 via 20260315_BCBS.' and nothing else changes.
"""

from __future__ import annotations

import re

from ..kit import (COMM_KINDS, WRITE_KINDS, Action, Context, World, book_eq, nh, no_placeholders, norm, pre_rule,
                   prior_denials, same, state_rule, text_of, world)

REG, REG_HDR, REG_SHEET = r"PBC_Claim_Register", r"^Claim ID$", r"^PBC_Claim_Register$"
BATCH = "20260315_BCBS"
BATCH_RX = r"(?:ERA[_-])?20260315[_-]BCBS"
CLAWBACK = f"Clawback applied 2026-03-15: $30.00 via {BATCH}."
CLAWBACK_RX = r"Clawback applied 2026-03-15: \$30\.00 via " + BATCH_RX + r"\.?"
ERA_CLAIMS = ("CLM-1008", "CLM-1033", "CLM-1016")

R_POST = [("7.1", "PBC_Claim_Register.xlsx by Claim ID and updating", "7.1 Posting a payment"),
          ("7.1", "- Full. For initial posting", "7.1 initial posting status")]
R_DEPOSIT = ("7.1", "1. The Deposit Match", "7.1 Deposit Match")
R_LINE = ("2", "corresponding claim in PBC_Claim_Register.xlsx by Claim ID and CPT", "7.1 Line-Item Verification")
R_CONTRACT = ("2", "3. The Contractual Adjustment Verification", "7.1 Contractual Adjustment Verification")
R_PLB = ("2", "4. The PLB Audit", "7.1 PLB Audit / checkpoint table")
R_SBWO = ("5.1", "Trigger Type Criteria", "5.1 SBWO")
R_RECOUP = [("7.2", "Prior Agreement Recoupments", "7.2 Prior Agreement Recoupments"),
            ("7.2", "Pathfinder Billing and Coding SOP-RCM-024 PBC_Claim_Register.xlsx, verify the recoupment",
             "7.2 clawback note format")]
R_FEE = ("13.4", "Used to verify contractual adjustments", "Appendix A file ecosystem")
R_COMMS = ("10", "All external communication must be professional", "10 Internal Communication Scripts")
R_PHI = [("11.1", "1. Minimalist Access", "11.1 Minimalist Access"),
         ("1.3", "Data Isolation", "1.3 Data Isolation")]
R_TEMPLATES = [("10.1", "Use this when clinical documentation", "10.1 Provider Query template"),
               ("10.4", "Slack/Email: \"Urgent Escalation", "10.4 High-Value Escalation template")]

COLS = {"allowed": r"^Allowed Amount", "paid": r"^Paid Amount", "adj": r"^Contractual Adj", "pr": r"^Patient Resp",
        "status": r"^Claim Status$", "posting": r"^Payment Posting Status$", "batch": r"^ERA Batch ID$",
        "notes": r"^Notes$"}


def _row(w: World, claim: str, which: str = "current") -> dict | None:
    return w.find(REG, REG_HDR, r"^Claim ID$", claim, which, REG_SHEET)


def _v(w: World, row: dict | None, key: str) -> str:
    return w.col(row, COLS[key]) if row else ""


def _register_present(w: World) -> bool:
    return bool(w.rows(REG, REG_HDR, "current", REG_SHEET))


# ---- CLM-1008: post in full ---------------------------------------------------------------------

def _clm1008(ctx: Context):
    w = world(ctx)
    if not _register_present(w):
        return [(False, "PBC_Claim_Register.xlsx (sheet PBC_Claim_Register) is missing or unreadable; restore it.",
                 R_POST)]
    r = _row(w, "CLM-1008")
    if r is None:
        return [(False, "CLM-1008 is no longer in PBC_Claim_Register.xlsx; restore the row and post the ERA line.",
                 R_POST)]
    why = ("ERA 20260315_BCBS passes the batch checks: header Payment Amount $167.00 = Net EFT $167.00, and claims "
           "$322.00 - PLB $30.00 - PLB $125.00 = $167.00, so the PLB reconciles to the deposit (the CLM-1016 "
           "recoupment of $30.00 equals its overpayment: paid $172.00 vs payer share $162.00 allowed - $20.00 patient "
           "resp = $142.00). CLM-1008 BCBS 99215: paid $180.00 + patient resp $30.00 = $210.00 = contracted rate "
           "$210.00, and $180 + $30 + $70 adj = billed $280.00.")
    want = [("paid", "Paid Amount ($)", 180.0), ("adj", "Contractual Adj ($)", 70.0), ("pr", "Patient Resp ($)", 30.0),
            ("status", "Claim Status", "Paid - Full"), ("posting", "Payment Posting Status", "Posted")]
    bad = [f"{label} = {val if isinstance(val, str) else f'{val:.2f}'} (got '{_v(w, r, key)}')"
           for key, label, val in want if not same(_v(w, r, key), val)]
    got = _v(w, r, "batch")
    if not re.fullmatch(BATCH_RX, got.strip(), re.I):
        bad.append(f"ERA Batch ID = {BATCH} (got '{got}')")
    got = _v(w, r, "allowed")
    if got and not same(got, 210.0):
        bad.append(f"Allowed Amount = 210.00 (got '{got}')")
    return [(not bad, "Post ERA line CLM-1008 in PBC_Claim_Register.xlsx: " + "; ".join(bad) + ". " + why,
             R_POST + [R_DEPOSIT, R_PLB])]


# ---- CLM-1033: contractual variance -------------------------------------------------------------

def _clm1033(ctx: Context):
    w = world(ctx)
    r = _row(w, "CLM-1033")
    if r is None:
        return [] if not _register_present(w) else [
            (False, "CLM-1033 is no longer in PBC_Claim_Register.xlsx; restore the row.", [R_LINE])]
    posting, status = _v(w, r, "posting"), _v(w, r, "status")
    ok = norm(posting) == "held - contractual variance" or norm(status) == "written off"
    return [(ok, "CLM-1033 (BCBS 99214) fails the contractual adjustment check: paid $142.00 + patient resp $20.00 = "
                 "$162.00 vs contracted rate $165.00 in PBC_Fee_Schedule.xlsx. Set its Payment Posting Status to "
                 f"'Held - Contractual Variance' (got Payment Posting Status '{posting}', Claim Status '{status}') "
                 "and route it to the Resolution Auditor for Payer Underpayment (CO-45).",
             [R_CONTRACT, R_PLB, R_SBWO])]


# ---- CLM-1016: clawback note only ---------------------------------------------------------------

def _clawback(ctx: Context):
    w = world(ctx)
    r, r0 = _row(w, "CLM-1016"), _row(w, "CLM-1016", "initial")
    if r0 is None or not _register_present(w):
        return []
    if r is None:
        return [(False, "CLM-1016 was removed from PBC_Claim_Register.xlsx; restore it.", R_RECOUP)]
    notes = nh(_v(w, r, "notes"))
    out = [(bool(re.search(CLAWBACK_RX, notes)),
            "PLB RECOUP-2026-0107 claws back the CLM-1016 overpayment ($30.00 = paid $172.00 - ($162.00 allowed - "
            "$20.00 patient resp)). Record it in CLM-1016's Notes exactly as: '" + CLAWBACK + f"' (got '{notes}').",
            R_RECOUP)]
    changed = [k for k in r0 if k not in ("__row__",) and not re.search(COLS["notes"], k)
               and nh(r0.get(k)) != nh(r.get(k))]
    out.append((not changed, f"CLM-1016: update no other fields than Notes; restore {', '.join(changed)} to the "
                             "original values (" + "; ".join(f"{k}='{r0.get(k)}'" for k in changed) + ").",
                R_RECOUP))
    return out


# ---- other rows / reference files unchanged ------------------------------------------------------

def _others(ctx: Context):
    w = world(ctx)
    if not _register_present(w):
        return []
    key = lambda r: w.col(r, r"^Claim ID$")
    init = [r for r in w.rows(REG, REG_HDR, "initial", REG_SHEET) if key(r) not in ERA_CLAIMS]
    cur = [r for r in w.rows(REG, REG_HDR, "current", REG_SHEET) if key(r) not in ERA_CLAIMS]
    strip = lambda r: tuple(nh(v) for k, v in r.items() if k != "__row__")
    cur_s = [strip(r) for r in cur]
    changed = []
    for r in init:
        s = strip(r)
        if s in cur_s:
            cur_s.remove(s)
        else:
            changed.append(key(r))
    init_ids = {key(r) for r in w.rows(REG, REG_HDR, "initial", REG_SHEET)}
    added = [key(r) or f"row {r['__row__']}" for r in cur if key(r) not in init_ids]
    ok = not changed and not cur_s
    return [(ok, "This ERA only posts to CLM-1008 and CLM-1033 and records the clawback on CLM-1016; the "
                 "credentialing-fee PLB is not applied to any claim line. Restore the other claim rows exactly "
                 f"(changed/removed: {', '.join(changed) or 'none'}; added: {', '.join(added) or 'none'}).",
             [R_LINE])]


def _ref_files(ctx: Context):
    w = world(ctx)
    out = []
    for rx, what in ((r"ERA_20260315_BCBS\.xlsx$", "the inbound ERA file ERA_20260315_BCBS.xlsx"),
                     (r"PBC_Fee_Schedule\.xlsx$", "the contracted-rate reference PBC_Fee_Schedule.xlsx")):
        k = next((k for k in w.initial if re.search(rx, k)), None)
        if k and not book_eq(w.current.get(k), w.initial[k]):
            out.append((False, f"Do not modify {what}; restore it to its original content.", [R_FEE]))
    return out


# ---- pre rules ----------------------------------------------------------------------------------

def _batch_hold(ctx: Context, a: Action):
    if a.kind not in WRITE_KINDS or not re.search(r"Claim_Register", a.text or "", re.I):
        return None
    m = re.search(r"Held\s*[-–—]\s*(PLB Variance|Batch Mismatch)", a.text or "", re.I)
    if not m or prior_denials(ctx, "[batch-hold]") >= 2:
        return None
    return (f"[batch-hold] This write sets '{m.group(0)}', but ERA 20260315_BCBS passes both batch checkpoints: header "
            "Payment Amount $167.00 = Net EFT $167.00, and claims $322.00 - PLB $30.00 (RECOUP-2026-0107) - PLB "
            "$125.00 (CRED-2026-0315) = $167.00, so interest/offsets reconcile to the deposit. The $30.00 recoupment "
            "matches the CLM-1016 overpayment (paid $172.00 vs payer share $162.00 allowed - $20.00 patient resp = "
            "$142.00). Post CLM-1008 (Paid - Full / Posted); only CLM-1033 is held (Held - Contractual Variance).")


DOS = {"CLM-1008": "2026-01-05", "CLM-1033": "2026-02-24", "CLM-1016": "2026-01-15"}
PID = {"CLM-1008": "PT-120", "CLM-1033": "PT-119", "CLM-1016": "PT-101"}
CPT = {"CLM-1008": "99215", "CLM-1033": "99214", "CLM-1016": "99214"}
MONTHS = {1: "Jan(?:uary)?", 2: "Feb(?:ruary)?"}
STATUSES = ("New", "Submitted", "Acknowledged", "Denied", "In Recovery", "Resubmitted", "Appealed", "Paid - Full",
            "Paid - Partial", "On Hold", "Closed", "Written Off")


def _dos_rx(iso: str) -> str:
    y, m, d = (int(x) for x in iso.split("-"))
    mon = MONTHS[m]
    return "|".join([rf"{y}-0?{m}-0?{d}", rf"{y}{m:02d}{d:02d}", rf"0?{m}/0?{d}/(?:{y}|{y % 100})",
                     rf"0?{d}\s+{mon}\.?,?\s+{y}", rf"{mon}\.?\s+0?{d}(?:st|nd|rd|th)?,?\s+{y}"])


def _claim_fields(ctx: Context, a: Action):
    if a.kind not in COMM_KINDS:
        return None
    text = text_of(a)
    out = []
    for claim in ERA_CLAIMS:
        if not re.search(rf"\b{claim}\b", text) or prior_denials(ctx, f"[claim-fields:{claim}]") >= 2:
            continue
        miss = []
        if not re.search(rf"\b{PID[claim]}\b", text):
            miss.append(f"Patient ID {PID[claim]}")
        if not re.search(_dos_rx(DOS[claim]), text, re.I):
            miss.append(f"DOS {DOS[claim]}")
        if not re.search(rf"\b{CPT[claim]}\b", text):
            miss.append(f"CPT {CPT[claim]}")
        if not re.search(r"BCBS|Blue\s*Cross", text, re.I):
            miss.append("Payer Blue Cross Blue Shield")
        if not any(re.search(rf"\b{re.escape(s)}\b", text, re.I) for s in STATUSES):
            miss.append("the current Claim Status from the register")
        if miss:
            out.append(f"[claim-fields:{claim}] A message referencing {claim} must include {', '.join(miss)}.")
    return " ".join(out) or None


PHI_RX = (r"Harold\s+Jensen|Jensen,?\s+H(?:arold)?\b|Elaine\s+Foster|Foster,?\s+E(?:laine)?\b|Sarah\s+Mitchell|"
          r"Mitchell,?\s+S(?:arah)?\b|\bPT-(?:120|119|101)\b")
OK_DOMAINS = ("pathfinderbilling.com", "northsideinternal.com", "bcbsil.com")


def _phi(ctx: Context, a: Action):
    if a.kind not in ("email_send", "email_draft"):
        return None
    outside = sorted(x for x in set(a.recipients) | set(a.cc) if not x.endswith(tuple("@" + d for d in OK_DOMAINS)))
    m = re.search(PHI_RX, text_of(a), re.I)
    if not outside or not m:
        return None
    return (f"[phi] The message contains PHI of Northside Internal Medicine patients on this ERA ('{m.group(0)}') "
            f"and goes to {', '.join(outside)}, who is not involved in that case. Remove the patient details or "
            "those recipients.")


RULES = (
    state_rule("posting.clm1008_posted", _clm1008, "Update the CLM-1008 row in PBC_Claim_Register.xlsx as listed.")
    + state_rule("posting.clm1033_variance", _clm1033, "Update the CLM-1033 row in PBC_Claim_Register.xlsx.")
    + state_rule("posting.clm1016_clawback", _clawback, "Fix the CLM-1016 row in PBC_Claim_Register.xlsx.")
    + state_rule("register.other_rows_unchanged", _others, "Restore the listed claim rows.")
    + state_rule("files.reference_unchanged", _ref_files, "Restore the file.")
    + pre_rule("posting.no_batch_hold", _batch_hold, [R_DEPOSIT, R_PLB],
               "Do not hold the batch; post CLM-1008 and hold only CLM-1033.")
    + pre_rule("comms.claim_fields", _claim_fields, [R_COMMS],
               "Add the missing claim fields (Claim ID, Patient ID, DOS, CPT, Payer, current Claim Status).")
    + pre_rule("comms.phi_third_party", _phi, R_PHI, "Do not share these patients' PHI with that recipient.")
    + no_placeholders(R_TEMPLATES)
)
