"""Verifiers for medical_pathfinder_billing_and_coding_a25684b9 (Pathfinder SOP-RCM-024, RA queue).

Situation (seed data, today 2026-03-30): Alex Rivera (Resolution Auditor) works the Open RA queue items.
- Q-2026-005 / Q-2026-007 -> CLM-2026-0062 (UHC, 99215, CO-45). Fee schedule 99215/UHC = 312.00, paid 285.00:
  underpayment 27.00. TFL 2026-04-27 is 28 days out (Orange Alert, P0104/P0064) -> the RA must apply the
  write-off authority (<= $250) by default: SBWO register update (P0115), worklist Write Off / Written Off,
  and the special-authorization Slack post (P0057).
- Q-2026-006 -> CLM-2026-0061 (Aetna, 99214, CO-27). Eligibility: PAT-1006 Plan Terminated 2026-02-19, before
  DOS 2026-02-20 -> P0161: worklist Route to PFR / In Progress, register Claim Status On Hold.
"""

from __future__ import annotations

import datetime as dt
import re

from ..kit import (COMM_KINDS, Comm, Context, Finding, Rule, World, blank, cites, comm_rules, nh, no_placeholders,
                   norm, pre_rule, prior_denials, same, state_rule, text_of, world)

ACTOR = "Alex Rivera"
WO_CLAIM, PFR_CLAIM = "CLM-2026-0062", "CLM-2026-0061"
SA_POST = f"{ACTOR}: {WO_CLAIM} special action authorized"

REG, REG_H = r"PBC_Claim_Register\.xlsx$", r"^Claim_ID$"
WL, WL_H = r"PBC_Denial_Worklist\.xlsx$", r"^Denial_ID$"
RAQ, RAQ_H = r"PBC_RA_Queue\.xlsx$", r"^Queue_ID$"

# Expected end state per claim / denial (column -> value); other columns of these rows stay as seeded.
REG_WANT = {
    WO_CLAIM: {"Claim_Status": "Written Off", "Billed_Amount": "285", "Paid_Amount": "285", "Adjustment_Amount": "0"},
    PFR_CLAIM: {"Claim_Status": "On Hold"},
}
WL_WANT = {
    "DNL-2026-002": {"Recovery_Action": "Write Off", "Recovery_Status": "Written Off"},
    "DNL-2026-001": {"Recovery_Action": "Route to PFR", "Recovery_Status": "In Progress"},
}
# CLM-2026-0065 / DNL-2026-005 (CO-50, Q-2026-003 In Progress) is not an Open item; changes there are not judged.
UNJUDGED_CLAIMS = {"CLM-2026-0065"}
UNJUDGED_DENIALS = {"DNL-2026-005"}

INITIAL_FILES = {"ERA_20260207_001.xlsx", "ERA_20260303_001.xlsx", "PBC_Claim_Register.xlsx",
                 "PBC_Denial_Worklist.xlsx", "PBC_Eligibility_Responses.xlsx", "PBC_Fee_Schedule.xlsx",
                 "PBC_RA_Queue.xlsx", "Pathfinder_SOP.docx"}
ECOSYSTEM = re.compile(r"^(PBC_[A-Za-z_]+|ERA_[\w-]+)\.xlsx$")  # Appendix A operational files

R_SA = ("2.2", "Any time a Resolution Auditor or RCM Manager uses their authorization level", "§2.2 special-authorization post")
R_RA_AUTH = ("2.2", "Authorization Level: The Resolution Auditor is authorized to apply", "§2.2 RA write-off authority (Orange Alert)")
R_SBWO = ("5.1", "When an SBWO is applied, update PBC_Claim_Register.xlsx", "§5.1 SBWO register update")
R_CO45 = ("6.2", "2. Case Review: If the payment matches the contracted rate", "§6.2 CO-45 case review")
R_CO27 = ("6.2", "3. Update PBC_Denial_Worklist.xlsx : Set Recovery Action to Route to PFR", "§6.2 CO-27 step 3")
R_RESUB = ("6.2", "PBC_Claim_Register.xlsx that references the original Claim ID", "§6.2 resubmission = new register row")
R_TRIAGE = ("6.1", "When a denial is identified (Triggers: CO-, PR-, OA-)", "§6.1 denial routing")
R_ACTIONS = ("1", "Correct and Resubmit · Update COB and Resubmit", "Appendix B Denial Recovery Action")
R_RSTATUS = ("1", "Pending Review · In Progress · Resubmitted", "Appendix B Denial Recovery Status")
R_COMM = ("10", "All external communication must be professional", "§10 claim references in messages")
R_DISPOSAL = ("11.3", "Data Disposal | Temporary audit files", "§11.3 data disposal")
R_RAQ = ("13.4", "PBC_RA_Queue.xlsx | Resolution Auditor's open items", "Appendix A RA queue")
R_FEE = ("13.4", "PBC_Fee_Schedule.xlsx | Contracted rates", "Appendix A fee schedule")
R_ELIG = ("13.4", "PBC_Eligibility_Responses.xlsx | Eligibility verification", "Appendix A eligibility")
R_ERA = ("13.4", "ERA_[BatchID].xlsx | Inbound payment file", "Appendix A ERA files")

CLAIM_STATUSES = ["New", "Submitted", "Acknowledged", "Denied", "In Recovery", "Resubmitted", "Appealed",
                  "Paid - Full", "Paid - Partial", "On Hold", "Closed", "Written Off", "Route to PFR"]
PAYER_RX = {"united healthcare": r"united\s?health\s?care|\bUHC\b",
            "aetna": r"aetna",
            "bluecross blueshield": r"blue\s?cross\s?blue\s?shield|\bBCBS\b"}


# ---- helpers ---------------------------------------------------------------------------------------

def _cell(w: World, r: dict, col: str) -> str:
    return w.col(r, rf"^{col}$")


def _row_checks(w: World, name_rx, header_rx, key_col, want: dict, skip: set, what: str, refs_for):
    """Expected cells for the rows in ``want``; every other column of those rows and every other row unchanged;
    no rows added or removed."""
    init = w.rows(name_rx, header_rx, "initial")
    cur = w.rows(name_rx, header_rx, "current")
    if not init:
        return
    cur_by = {}
    for r in cur:
        cur_by.setdefault(_cell(w, r, key_col), []).append(r)
    for r0 in init:
        key = _cell(w, r0, key_col)
        rows = cur_by.get(key, [])
        if key in skip:
            continue
        if not rows:
            yield False, f"{what}: the row for {key} is missing; restore it.", refs_for(key)
            continue
        r = rows[0]
        exp = want.get(key, {})
        bad = [f"{c} = \"{v}\" (now \"{_cell(w, r, c)}\")" for c, v in exp.items() if not same(_cell(w, r, c), v)]
        if bad:
            yield False, f"{what} {key}: set " + "; ".join(bad) + ".", refs_for(key)
        changed = [f"{c} (seed \"{_cell(w, r0, c)}\", now \"{_cell(w, r, c)}\")" for c in r0
                   if c != "__row__" and c not in exp and not same(_cell(w, r, c), _cell(w, r0, c) or None)]
        if changed:
            note = "only the columns listed by the SOP change for this item" if exp else \
                "this row is not one of the Open RA queue items and needs no change"
            yield False, (f"{what} {key}: {note}; restore " + "; ".join(changed) + "."), refs_for(key)
    keys0 = {_cell(w, r, key_col) for r in init}
    for r in cur:
        k = _cell(w, r, key_col)
        if k not in keys0 or len(cur_by.get(k, [])) > 1:
            yield False, (f"{what}: row {k or '(blank id)'} (sheet row {r['__row__']}) was added; no SOP trigger in "
                          "this case adds a row here - remove it."), refs_for(None)
            break


def _claims(w: World) -> dict[str, dict]:
    return {_cell(w, r, "Claim_ID"): r for r in w.rows(REG, REG_H, "initial")}


def _dos_rx(iso: str) -> str:
    d = dt.date.fromisoformat(iso)
    mon, mon3 = d.strftime("%B"), d.strftime("%b")
    alts = [rf"{d:%Y-%m-%d}", rf"0?{d.month}/0?{d.day}/(?:{d.year}|{d.year % 100})",
            rf"(?:{mon}|{mon3}\.?)\s+0?{d.day}(?:st|nd|rd|th)?,?\s+{d.year}", rf"0?{d.day}\s+(?:{mon}|{mon3}\.?),?\s+{d.year}"]
    return "|".join(f"(?:{a})" for a in alts)


def _is_sa_template(w: World, a) -> bool:
    return (a.kind == "slack_post" and w.is_channel(a.channel, "special-authorization")) or \
        bool(re.search(r"special action authori[sz]ed", a.text or "", re.I))


# ---- messages --------------------------------------------------------------------------------------

def _specs(ctx: Context) -> list[Comm]:
    w = world(ctx)

    def other_claims(a) -> list[str]:
        return sorted(set(re.findall(r"CLM-\d{4}-\d{4}", text_of(a))) - {WO_CLAIM})

    return [
        Comm("sa_0062", "slack_post",
             lambda a: _is_sa_template(w, a) and WO_CLAIM in text_of(a) and not other_claims(a),
             f"special-authorization notice for the {WO_CLAIM} write-off", [R_SA, R_RA_AUTH],
             channel="special-authorization", exact=re.escape(SA_POST) + r"\.?", exact_hint=SA_POST),
        Comm("sa_other", "slack_post",
             lambda a: _is_sa_template(w, a) and bool(other_claims(a)),
             "special-authorization notice for a claim without a special action", [R_SA, R_CO27],
             forbidden=(f"Only {WO_CLAIM} received an authorization-level action (the Orange Alert write-off). "
                        f"{PFR_CLAIM} (CO-27) is routed to the PFR under the standard recovery plan, which is not a "
                        "special action - do not post a special-authorization notice for it or any other claim.")),
    ]


def _claim_fields(ctx: Context, a) -> str | None:
    """P0283: a message referencing a claim carries Claim ID, Patient ID, DOS, CPT, Payer and Claim Status."""
    if a.kind not in COMM_KINDS:
        return None
    w = world(ctx)
    if _is_sa_template(w, a):
        return None  # the §2.2 template fixes its own wording
    tag = "[claim-fields]"
    if prior_denials(ctx, tag) >= 2:
        return None
    text = nh(text_of(a))
    claims = _claims(w)
    out = []
    for cid in sorted(set(re.findall(r"CLM-\d{4}-\d{4}", text)) & set(claims)):
        r0 = claims[cid]
        cur = w.find(REG, REG_H, r"^Claim_ID$", cid) or r0
        pid, dos, cpt = _cell(w, r0, "Patient_ID"), _cell(w, r0, "Date_Of_Service"), _cell(w, r0, "CPT_Code")
        payer, status = _cell(w, r0, "Payer_Name"), _cell(w, cur, "Claim_Status")
        miss = []
        if pid not in text:
            miss.append(f"Patient ID {pid}")
        if not re.search(_dos_rx(dos), text, re.I):
            miss.append(f"DOS {dos}")
        if not re.search(rf"\b{cpt}\b", text):
            miss.append(f"CPT {cpt}")
        if not re.search(PAYER_RX.get(norm(payer), re.escape(payer)), text, re.I):
            miss.append(f"Payer {payer}")
        statuses = [status] + CLAIM_STATUSES
        if not any(re.search(rf"\b{re.escape(s)}\b", text, re.I) for s in statuses if s):
            miss.append(f"current Claim Status \"{status}\"")
        if miss:
            out.append(f"{cid} is missing " + ", ".join(miss))
    if not out:
        return None
    return (f"{tag} Every communication that references a claim must include Claim ID, Patient ID, DOS, CPT "
            "code(s), Payer and the current Claim Status from the register: " + "; ".join(out) + ".")


# ---- end state -------------------------------------------------------------------------------------

def _register(ctx: Context):
    w = world(ctx)

    def refs(key):
        return {WO_CLAIM: [R_RA_AUTH, R_CO45, R_SBWO], PFR_CLAIM: [R_CO27]}.get(key, [R_RESUB])
    yield from _row_checks(w, REG, REG_H, "Claim_ID", REG_WANT, UNJUDGED_CLAIMS, "PBC_Claim_Register.xlsx", refs)


def _worklist(ctx: Context):
    w = world(ctx)

    def refs(key):
        return {"DNL-2026-002": [R_RA_AUTH, R_CO45, R_ACTIONS, R_RSTATUS],
                "DNL-2026-001": [R_CO27]}.get(key, [R_TRIAGE])
    yield from _row_checks(w, WL, WL_H, "Denial_ID", WL_WANT, UNJUDGED_DENIALS, "PBC_Denial_Worklist.xlsx", refs)


def _ra_queue(ctx: Context):
    """Queue rows stay (Status / Priority_Level may be updated); no routing trigger adds a row in this case."""
    w = world(ctx)
    init, cur = w.rows(RAQ, RAQ_H, "initial"), w.rows(RAQ, RAQ_H, "current")
    if not init:
        return
    fixed = ("Queue_ID", "Date_Added", "Claim_ID", "Work_Item_Type")
    key = lambda r: tuple(norm(_cell(w, r, c))[:10] if c == "Date_Added" else norm(_cell(w, r, c)) for c in fixed)
    cur_keys = [key(r) for r in cur]
    for r0 in init:
        if key(r0) not in cur_keys:
            yield False, (f"PBC_RA_Queue.xlsx: queue item {_cell(w, r0, 'Queue_ID')} ({_cell(w, r0, 'Claim_ID')}, "
                          f"{_cell(w, r0, 'Work_Item_Type')}) was removed or its identifying cells changed; restore it "
                          "(only Status may be updated)."), [R_RAQ]
    extra = len(cur) - len(init)
    if extra > 0:
        yield False, ("PBC_RA_Queue.xlsx: rows were added. Routing to the RA means adding a queue row, and nothing in "
                      "this case needs routing to the RA; remove the added row(s)."), [R_RAQ]


def _reference_files(ctx: Context):
    w = world(ctx)
    for name, ref in ((r"PBC_Fee_Schedule\.xlsx$", R_FEE), (r"PBC_Eligibility_Responses\.xlsx$", R_ELIG),
                      (r"^ERA_[\w-]+\.xlsx$", R_ERA)):
        for f in w.changed_files():
            if re.search(name, f.split("/")[-1]):
                yield False, f"{f} is source/reference data for this work and must not be modified; restore it.", [ref]


def _temp_files(ctx: Context):
    w = world(ctx)
    left = sorted(f for f in w.files() if not any(p.startswith(".") for p in f.split("/"))
                  and f.split("/")[-1] not in INITIAL_FILES and not ECOSYSTEM.match(f.split("/")[-1])
                  and "__pycache__" not in f)
    if left:
        yield False, ("Temporary working files are still in the workspace: " + ", ".join(left[:8]) +
                      ". Temporary audit files must be permanently deleted on task completion."), [R_DISPOSAL]


RULES: list[Rule] = [
    *comm_rules("sa", _specs),
    *pre_rule("comms.claim_fields", _claim_fields, [R_COMM],
              "Add the missing claim fields (Claim ID, Patient ID, DOS, CPT, Payer, current Claim Status) and send again."),
    *no_placeholders([R_COMM]),
    *state_rule("register.state", _register, "Edit PBC_Claim_Register.xlsx as listed."),
    *state_rule("worklist.state", _worklist, "Edit PBC_Denial_Worklist.xlsx as listed."),
    *state_rule("ra_queue.rows", _ra_queue, "Fix PBC_RA_Queue.xlsx as listed."),
    *state_rule("reference.unchanged", _reference_files, "Restore the file to its original content."),
    *state_rule("files.temp_deleted", _temp_files, "Delete the temporary files."),
]
