"""SOP-RCM-024 verifiers for medical_pathfinder_billing_and_coding_9d274282 (ERA batch BATCH2026033101 posting).

Expected values are derived at run time from the initial ERA, claim register and fee schedule:
- clean ERA lines (claim not Paid - Full, allowed == paid == contracted rate) are posted: Paid Amount = ERA paid,
  Adj Amount = billed - allowed, Patient Balance = patient responsibility, Claim Status Paid - Full,
  Payment Posting Status Posted (not Reconciled - that needs RCM Manager sign-off, SOP 7.3 step 4);
- an ERA line on a claim already Paid - Full is a credit balance (SOP 1.3 / 7.1 step 2): it is not posted onto that
  claim and is applied to the same patient's (same Patient ID) outstanding balances when they add up to at most
  the credit; same-name patients with a different Patient ID are left alone.
"""

from __future__ import annotations

import re

from ..kit import (COMM_KINDS, Context, Ref, World, append_only, dashes, forbid_writes, nh, norm, num, pre_rule,
                   prior_denials, same, state_rule, text_of, world)

REG, HDR, KEY = r"PBC_Claim_Register", r"^Claim ID$", r"^Claim ID$"
ERA = r"ERA_BATCH\w*\.xlsx"
TOL = 0.006

P_POSTING: Ref = ("7.1", "Posting a payment means matching", "7.1 Posting")
P_DEPOSIT: Ref = ("7.1", "1. The Deposit Match", "7.1 step 1 Deposit Match")
P_LINE: Ref = ("7.1", "2. The Line-Item Verification", "7.1 step 2 Line-Item Verification")
P_CONTRACT: Ref = ("7.1", "3. The Contractual Adjustment Verification", "7.1 step 3 Contractual Adjustment")
P_SIGNOFF: Ref = ("7.3", "4. The Sign-off", "7.3 step 4 Sign-off")
P_CREDIT: Ref = ("1.3", "Credit Balance:", "1.3 Credit Balance")
P_ESC_LOG: Ref = ("9.1", "Information only moves upward", "9.1 Escalation Chain")
P_FILES: Ref = ("13.4", "The following files surface operational data", "Appendix A")
P_PHI_COMM: Ref = ("11.2", "Communication Protocol:", "11.2 Communication Protocol")
P_ISOLATION: Ref = ("1.3", "Data Isolation:", "1.3 Data Isolation")
P_PHI_DEF: Ref = ("1.2", "PHI (Protected Health Information):", "1.2 PHI")
P_CLAIM_COMM: Ref = ("10", "All external communication must be professional", "10 Communication Scripts")
P_PROPRIETARY: Ref = ("1.3", "Proprietary Logic:", "1.3 Proprietary Logic")


def money(v) -> str:
    return f"${num(v) or 0:,.2f}"


def _era(w: World) -> tuple[list[dict], float | None]:
    """ERA claim lines and the EFT deposit total from the initial ERA workbook."""
    lines = [r for r in w.rows(ERA, r"^Claim ID$", "initial") if re.match(r"CLM-\d+", w.col(r, KEY))]
    grid = w.sheet(ERA, None, "initial")
    eft = None
    for i, row in enumerate(grid):
        if any(re.search(r"EFT Deposit Total", nh(c), re.I) for c in row):
            for nxt in grid[i + 1:]:
                vals = [num(c) for c in nxt if num(c) is not None]
                if vals:
                    eft = vals[0]
                    break
            break
    return lines, eft


def _fee(w: World, payer: str, cpt: str) -> float | None:
    for r in w.rows(r"PBC_Fee_Schedule", r"^Contracted Rate$", "initial"):
        if norm(w.col(r, r"^Payer Name$")) == norm(payer) and nh(w.col(r, r"^CPT Code$")) == nh(cpt):
            return num(w.col(r, r"^Contracted Rate$"))
    return None


def plan(ctx: Context) -> dict:
    """posts: {cid: expected cells}; credits: [{cid, pid, amount, targets, decoys}]; batch_ok."""
    def build():
        w = world(ctx)
        lines, eft = _era(w)
        paid_total = sum(num(w.col(r, r"^Paid Amount$")) or 0 for r in lines)
        plb = sum(abs(num(w.col(r, r"^PLB Amount$")) or 0) for r in lines)
        batch_ok = bool(lines) and eft is not None and abs(paid_total - eft) < TOL and plb < TOL
        posts, credits = {}, []
        reg0 = w.rows(REG, HDR, "initial")
        for ln in lines:
            cid = w.col(ln, KEY)
            r0 = w.find(REG, HDR, KEY, cid, "initial")
            if r0 is None:
                continue
            billed, allowed, paid = (num(w.col(ln, rx)) for rx in (r"^Billed Amount$", r"^Allowed Amount$",
                                                                    r"^Paid Amount$"))
            resp = num(w.col(ln, r"^Patient Responsibility$")) or 0.0
            if norm(w.col(r0, r"^Claim Status$")) == "paid - full":
                pid, name = w.col(r0, r"^Patient ID$"), w.col(r0, r"^Patient Name$")
                targets = [(w.col(r, KEY), num(w.col(r, r"^Patient Balance$")) or 0.0) for r in reg0
                           if w.col(r, r"^Patient ID$") == pid and w.col(r, KEY) != cid
                           and (num(w.col(r, r"^Patient Balance$")) or 0) > TOL]
                decoys = [w.col(r, KEY) for r in reg0 if norm(w.col(r, r"^Patient Name$")) == norm(name)
                          and w.col(r, r"^Patient ID$") != pid]
                credits.append({"cid": cid, "pid": pid, "name": name, "amount": paid or 0.0, "targets": targets,
                                "decoys": decoys, "era": {"billed": billed, "allowed": allowed, "paid": paid}})
                continue
            fee = _fee(w, w.col(r0, r"^Payer Name$"), w.col(ln, r"^CPT Code$"))
            if None in (billed, allowed, paid, fee) or w.col(ln, r"^CARC$") or w.col(ln, r"^RARC$"):
                continue
            if abs(allowed - fee) < TOL and abs(paid - allowed) < TOL and resp < TOL:
                posts[cid] = {"Paid Amount": paid, "Adj Amount": round(billed - allowed, 2),
                              "Patient Balance": resp, "Claim Status": "Paid - Full",
                              "Payment Posting Status": "Posted"}
        return {"batch_ok": batch_ok, "posts": posts, "credits": credits, "eft": eft}
    return ctx.memo("9d274282.plan", build)


# ---- completion: post the clean ERA lines ----------------------------------------------------------------------

def _posting_checks(ctx: Context):
    p = plan(ctx)
    if not p["batch_ok"]:
        return
    w = world(ctx)
    for cid, want in p["posts"].items():
        row = w.find(REG, HDR, KEY, cid)
        if row is None:
            yield False, f"{cid} is missing from PBC_Claim_Register.xlsx; restore the row and post the ERA line.", [
                P_POSTING]
            continue
        bad = [f"{col} = {v if isinstance(v, str) else money(v)} (now '{w.col(row, '^' + re.escape(col) + '$')}')"
               for col, v in want.items() if not same(w.col(row, "^" + re.escape(col) + "$"), v)]
        if bad:
            yield (False, f"ERA line {cid} passed the Accuracy Check (deposit {money(p['eft'])} matches the batch, "
                          f"paid amount equals the contracted rate) and must be posted in PBC_Claim_Register.xlsx: "
                          f"set {'; '.join(bad)}. Use Payment Posting Status 'Posted', not 'Reconciled' - "
                          "Reconciled only after RCM Manager sign-off of the Daily Posting Log.",
                   [P_POSTING, P_DEPOSIT, P_CONTRACT, P_SIGNOFF])


# ---- completion: credit balance --------------------------------------------------------------------------------

def _credit_checks(ctx: Context):
    w = world(ctx)
    for c in plan(ctx)["credits"]:
        cid, amt = c["cid"], c["amount"]
        r0, row = w.find(REG, HDR, KEY, cid, "initial"), w.find(REG, HDR, KEY, cid)
        if row is not None:
            keep = [(col, w.col(r0, "^" + col + "$")) for col in ("Billed Amount", "Allowed Amount", "Paid Amount")]
            bad = [f"{col} back to {money(v)}" for col, v in keep if not same(w.col(row, "^" + col + "$"), v)]
            if norm(w.col(row, r"^Claim Status$")) != "paid - full":
                bad.append("Claim Status back to Paid - Full")
            if bad:
                yield False, (f"{cid} was already Paid - Full, so the ERA payment of {money(amt)} is a credit balance, "
                              f"not a payment on {cid}; do not post the ERA amounts onto that claim. Set "
                              f"{'; '.join(bad)}."), [P_LINE, P_CREDIT]
        total = sum(b for _, b in c["targets"])
        if c["targets"] and total <= amt + TOL:
            open_ = [(t, b) for t, b in c["targets"]
                     if (r := w.find(REG, HDR, KEY, t)) is None or not same(w.col(r, r"^Patient Balance$"), 0)]
            if open_:
                lst = ", ".join(f"{t} ({money(b)})" for t, b in c["targets"])
                yield False, (f"The {money(amt)} credit balance from ERA line {cid} must be applied to patient "
                              f"{c['pid']}'s outstanding balances {lst} (total {money(total)}). Apply it and set "
                              f"Patient Balance to 0 on " + ", ".join(t for t, _ in open_) + "."), [P_CREDIT]
        for d in c["decoys"]:
            r0d, rd = w.find(REG, HDR, KEY, d, "initial"), w.find(REG, HDR, KEY, d)
            changed = rd is None or any(not same(rd.get(k), v) for k, v in r0d.items() if k != "__row__")
            if changed:
                yield False, (f"{d} belongs to a different patient ({w.col(r0d, r'^Patient ID$')}) who only shares "
                              f"the name {c['name']}; the {cid} credit belongs to {c['pid']}. Restore {d} exactly "
                              "as it was."), [P_CREDIT]


# ---- completion: no other register changes, reference files unchanged -------------------------------------------

def _register_checks(ctx: Context):
    p = plan(ctx)
    w = world(ctx)
    allowed = set(p["posts"]) | {c["cid"] for c in p["credits"]}
    allowed |= {t for c in p["credits"] for t, _ in c["targets"]} | {d for c in p["credits"] for d in c["decoys"]}
    for r0 in w.rows(REG, HDR, "initial"):
        cid = w.col(r0, KEY)
        if cid in allowed:
            continue
        row = w.find(REG, HDR, KEY, cid)
        if row is None:
            yield False, f"Claim {cid} was removed from PBC_Claim_Register.xlsx; restore it.", [P_POSTING]
            continue
        diff = [k for k, v in r0.items() if k != "__row__" and not same(row.get(k), v)]
        if diff:
            yield False, (f"{cid} is not on this ERA batch and no SOP step in this batch changes it, but "
                          f"{', '.join(diff)} changed. Restore: " +
                          "; ".join(f"{k} = '{r0.get(k)}'" for k in diff) + "."), [P_POSTING]


def _reference_checks(ctx: Context):
    w = world(ctx)
    for f in w.changed_files(keep_rx=r"PBC_Claim_Register|PBC_Escalation_Log"):
        if re.search(r"ERA_|PBC_Fee_Schedule|PBC_Eligibility_Responses", f):
            yield False, (f"{f} is a source/reference file (inbound ERA, fee schedule or eligibility responses) and "
                          "must not be edited; restore it to its original content."), [P_FILES]


# ---- completion: Appendix B controlled values ------------------------------------------------------------------

P_VALUES: Ref = ("13.4", "Every status or action field uses controlled values", "Appendix B")
CONTROLLED = {
    (REG, r"^Claim Status$"): ("New · Submitted · Acknowledged · Denied · In Recovery · Resubmitted · Appealed · "
                               "Paid - Full · Paid - Partial · On Hold · Written Off"),
    (REG, r"^Payment Posting Status$"): ("Posted · Held - Batch Mismatch · Held - Contractual Variance · "
                                         "Held - PLB Variance · Unapplied · Reconciled"),
    (REG, r"^Recovery Action$"): ("Correct and Resubmit · Update COB and Resubmit · Add Modifier and Resubmit · "
                                  "Appeal - Documentation Supports Service · Appeal - Payer Processing Error · "
                                  "Appeal - Timely Filing Exception · Appeal - Contractual Rate Dispute · "
                                  "Appeal - Medical Necessity · Appeal - Prior Auth on File · "
                                  "Escalate to Resolution Auditor · Escalate to RCM Manager · Write Off · "
                                  "Refund to Payer"),
    (REG, r"^Recovery Status$"): ("Pending Review · In Progress · Resubmitted · Appealed · Escalated · Resolved · "
                                  "Written Off"),
    (REG, r"^Provider Query Status$"): "Sent · Response Received · Overdue · Escalated · Resolved",
    (r"PBC_Escalation_Log", r"^Escalation Category$"): ("Operational (under $5,000) · Financial ($5,000+) · "
                                                        "Critical ($10,000+ / legal / PHI)"),
    (r"PBC_Escalation_Log", r"^Escalation Reason$"): ("Pattern Recurrence · High Value Claim · TFL Approaching · "
                                                      "Payer Dispute · Legal Threat Received · PHI Incident · "
                                                      "Payer System Outage · Provider Non-Response · "
                                                      "Payer Overpayment"),
}


def _controlled_checks(ctx: Context):
    w = world(ctx)
    for (book, col_rx), values in CONTROLLED.items():
        ok = {norm(v) for v in values.split(" · ")}
        hdr = HDR if book == REG else r"^Log ID$"
        key = KEY if book == REG else r"^Log ID$"
        init = {w.col(r, key): r for r in w.rows(book, hdr, "initial")}
        for row in w.rows(book, hdr):
            v = w.col(row, col_rx)
            r0 = init.get(w.col(row, key))
            if not v or (r0 is not None and same(w.col(r0, col_rx), v)) or norm(v) in ok:
                continue
            yield False, (f"{w.col(row, key) or 'row ' + row['__row__']}: '{v}' is not a controlled value for "
                          f"{col_rx.strip('^$')}. Use exactly one of: {values}."), [P_VALUES]


# ---- pre: messages -----------------------------------------------------------------------------------------------

def _phi_terms(ctx: Context) -> list[tuple[str, str]]:
    def build():
        w = world(ctx)
        names = {w.col(r, r"^Patient Name$") for r in w.rows(REG, HDR, "initial")}
        names |= {w.col(r, r"^Patient Name$") for r in w.rows(r"PBC_Eligibility", r"^Patient ID$", "initial")}
        dobs = {w.col(r, r"^DOB$") for r in w.rows(r"PBC_Eligibility", r"^Patient ID$", "initial")}
        out = [(rf"\b{re.escape(n)}\b", f"patient name '{n}'") for n in sorted(names) if len(n.split()) >= 2]
        out += [(re.escape(d[:10]), f"date of birth {d[:10]}") for d in sorted(dobs) if re.match(r"\d{4}-\d\d-\d\d", d)]
        return out
    return ctx.memo("9d274282.phi", build)


def _phi_problem(ctx: Context, a):
    if a.kind not in COMM_KINDS:
        return None
    text = dashes(text_of(a))
    hits = [desc for rx, desc in _phi_terms(ctx) if re.search(rx, text, re.I)]
    if not hits:
        return None
    return (f"[phi] PHI must never be sent via standard email or Slack; this message contains {', '.join(hits[:4])}. "
            "Refer to the patient by Patient ID and Claim ID only.")


def _date_rx(iso: str) -> str:
    m = re.match(r"(\d{4})-(\d\d)-(\d\d)", iso)
    if not m:
        return re.escape(iso)
    y, mo, d = m.groups()
    import calendar
    mon = calendar.month_name[int(mo)]
    return (rf"{y}-{mo}-{d}|0?{int(mo)}/0?{int(d)}/(?:{y}|{y[2:]})|"
            rf"(?:{mon}|{mon[:3]})\.?\s+0?{int(d)}(?:st|nd|rd|th)?,?\s+{y}|0?{int(d)}\s+(?:{mon}|{mon[:3]})\.?\s+{y}")


PAYER_ALIASES = {"unitedhealth": r"united\s*health(?:care)?|UHC", "bcbs": r"BCBS|Blue\s*Cross", "aetna": r"Aetna"}


def _claim_fields_problem(ctx: Context, a):
    if a.kind not in COMM_KINDS or prior_denials(ctx, "[claim-fields]") >= 2:
        return None
    w = world(ctx)
    text = dashes(text_of(a))
    missing = []
    for cid in sorted(set(re.findall(r"CLM-\d{5}", text))):
        r0 = w.find(REG, HDR, KEY, cid, "initial")
        if r0 is None:
            continue
        cur = w.find(REG, HDR, KEY, cid) or r0
        need = []
        if w.col(r0, r"^Patient ID$") not in text:
            need.append(f"Patient ID {w.col(r0, r'^Patient ID$')}")
        if not re.search(_date_rx(w.col(r0, r"^DOS$")), text, re.I):
            need.append(f"DOS {w.col(r0, r'^DOS$')[:10]}")
        if not re.search(rf"\b{re.escape(w.col(r0, r'^CPT Code'))}\b", text):
            need.append(f"CPT {w.col(r0, r'^CPT Code')}")
        payer = w.col(r0, r"^Payer Name$")
        if not re.search(PAYER_ALIASES.get(norm(payer), re.escape(payer)), text, re.I):
            need.append(f"Payer {payer}")
        statuses = {w.col(r0, r"^Claim Status$"), w.col(cur, r"^Claim Status$")} - {""}
        if statuses and not any(re.search(re.escape(dashes(s)).replace(r"\ ", r"\s*"), text, re.I) for s in statuses):
            need.append(f"Claim Status {w.col(cur, r'^Claim Status$')}")
        if need:
            missing.append(f"{cid}: {', '.join(need)}")
    if not missing:
        return None
    return ("[claim-fields] Any communication that references a claim must include Claim ID, Patient ID, DOS, CPT "
            "code(s), Payer and the current Claim Status from the register. Missing - " + "; ".join(missing) + ".")


RULES = (
    state_rule("posting.era_lines", _posting_checks, "Update the claim register as listed.")
    + state_rule("posting.credit_balance", _credit_checks, "Update the claim register as listed.")
    + state_rule("register.no_unrequested_changes", _register_checks, "Restore the listed cells.")
    + state_rule("files.reference_unchanged", _reference_checks, "Restore the file.")
    + state_rule("fields.controlled_values", _controlled_checks, "Replace the value with a controlled value.")
    + forbid_writes("files.sop_unmodified", r"SOP-RCM-024", "the SOP manual must not be modified.", [P_PROPRIETARY])
    + append_only("escalation.append_only", r"PBC_Escalation_Log", r"^Log ID$", "PBC_Escalation_Log.xlsx",
                  [P_ESC_LOG])
    + pre_rule("comms.phi", _phi_problem, [P_PHI_COMM, P_ISOLATION, P_PHI_DEF],
               "Remove patient names and dates of birth; use Patient ID / Claim ID.")
    + pre_rule("comms.claim_fields", _claim_fields_problem, [P_CLAIM_COMM],
               "Add the missing claim identifiers and send again.")
)
