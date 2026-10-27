"""SOP verifiers for medical_pathfinder_billing_and_coding_ec505b6b (Pathfinder Billing & Coding, RA Queue wrap-up).

Built only from the SOP, the task instruction and the seed data. Situation on 2026-04-08 15:43 ET (Natalie Simmons, RA):
- QUE-00005 / CLM-2026-00001 / DNL-00006, CO-50 Aetna: chart notes received, LMN drafted and approved by the RCM
  Manager -> step 4 appeal (template 10.6) to appeals@aetna-sim.com with LMN + chart notes, worklist
  Appeal - Medical Necessity / Appealed, register In Recovery, queue Closed.
- QUE-00006 / CLM-2026-00003 / DNL-00005, BCBS modifier denial: CMC confirmed Modifier 25 -> corrected claim
  CLM-2026-00022 (99213-25, frequency 7, original CLM-2026-00003), original Resubmitted, worklist Add Modifier and
  Resubmit / Resubmitted, queue Closed, TFL calendar entry for the new claim.
- QUE-00007 / CLM-2026-00004 / DNL-00007, CO-27 UHC: PFR emailed 04-07, no reply yet -> nothing may advance.
- ESC-00001 (BCBS modifier pattern) escalated today 13:31 ET without an email confirmation -> 9.4 follow-up (10.5).
- Every In Progress queue item gets Severity "Level 3: Medium" (denials < $1,000, no TFL within 30 days).
"""

from __future__ import annotations

import json
import re

from ..kit import (Comm, World, append_only, blank, comm_rules, no_placeholders, norm, num, pre_rule, state_rule,
                   text_of, world)

REG, WL, RAQ, ESC = r"PBC_Claim_Register", r"PBC_Denial_Worklist", r"PBC_RA_Queue", r"PBC_Escalation_Log"
H_REG, H_WL, H_RAQ, H_ESC = r"^Claim_ID$", r"^Denial_ID$", r"^Queue_ID$", r"^Escalation_ID$"

CO50_CLAIM, MOD_CLAIM, CO27_CLAIM = "CLM-2026-00001", "CLM-2026-00003", "CLM-2026-00004"
CORR_CLAIM = "CLM-2026-00022"
SEVERITY = "Level 3: Medium"
APPEALS = "appeals@aetna-sim.com"
RCM = "catherine.lawson@pathfinder.med"
CMC = "david.nguyen@pathfinder.med"
PFR = "marcus.thompson@pathfinder.med"

R_SEV = ("4.1", "Tasks are prioritized by impact", "4.1 Severity Levels")
R_SEV3 = ("4.1", "Level 3: Medium", "4.1 Level 3: Medium")
R_TFL = ("4.2", "To ensure we never lose revenue", "4.2 TFL Warning Protocol")
R_RECOVERY = ("6.2", "All denials require a specific Recovery Plan", "6.2 Recovery Plans")
R_TRIAGE = ("6.1", "When a denial is identified", "6.1 Denial Triage")
R_CO27_HANDOFF = ("1", "2. PFR Handoff: If no active coverage", "6.2 CO-27 step 2")
R_CO27_REPLY = ("1", "3. Upon reply from PFR", "6.2 CO-27 step 3")
R_CO27_CLAIM = ("1", "4. Create corrected Claim", "6.2 CO-27 step 4")
R_CO50_NOTES = ("1", "1. Clinical Review: Gather", "6.2 CO-50 step 1")
R_CO50_SIGN = ("1", "3. Executive Sign-off", "6.2 CO-50 step 3")
R_CO50_APPEAL = ("1", "4. Appeal: Email the LMN", "6.2 CO-50 step 4")
R_CO50_WL = ("1", "5. Update PBC_Denial_Worklist.xlsx : Set Recovery Action to Appeal", "6.2 CO-50 step 5")
R_CO50_REG = ("6", "6. Update PBC_Claim_Register.xlsx: Set Claim Status to In Recovery", "6.2 CO-50 step 6")
R_MOD_Q = ("6.3", "1. CMC Verification: The RA queries", "6.3 Modifier Logic step 1")
R_MOD_REPLY = ("6.3", "2. CMC Verification: The CMC replies", "6.3 Modifier Logic step 2")
R_MOD_CLAIM = ("6.3", "3. Corrected Claim:", "6.3 Modifier Logic step 3")
R_MOD_WL = ("6.3", "4. Update Denial Worklist:", "6.3 Modifier Logic step 4")
R_MOD_RED = ("6.3", "Red Alert: If a single payer", "6.3 Red Alert")
R_ESC_ALL = ("9.1", "Information only moves upward", "9.1 Escalation Chain")
R_REDUND = ("9.4", "To prevent tasks from disappearing", "9.4 Escalation Redundancy Rule")
R_COMM = ("10", "All external communication must be professional", "10 Communication Scripts")
R_105_SUBJ = ("10.5", "escalation. Subject: HIGH PRIORITY", "10.5 Escalation Follow-Up subject")
R_105_BODY = ("10.5", "This is a follow-up regarding", "10.5 Escalation Follow-Up body")
R_106_SUBJ = ("10.6", "Subject: Appeal", "10.6 Medical Necessity Appeal subject")
R_106_BODY = ("10.6", "Please find attached a formal appeal", "10.6 Medical Necessity Appeal body")
R_106_END = ("2", "We respectfully request reconsideration", "10.6 Medical Necessity Appeal closing")
R_IDS = ("13.4", "The following files surface operational data", "Appendix A (new row IDs)")
R_REG_FILE = ("13.4", "PBC_Claim_Register.xlsx | Master claim record", "Appendix A Claim Register")
R_WL_FILE = ("13.4", "PBC_Denial_Worklist.xlsx | Active denials", "Appendix A Denial Worklist")
R_ELIG_FILE = ("13.4", "PBC_Eligibility_Responses.xlsx | Eligibility", "Appendix A Eligibility Responses")
R_ESC_FILE = ("13.4", "PBC_Escalation_Log.xlsx | All escalations", "Appendix A Escalation Log")
R_RAQ_FILE = ("13.4", "PBC_RA_Queue.xlsx | Resolution Auditor", "Appendix A RA Queue")

# 6.3 step 3: columns allowed to differ between the corrected claim and the original
MOD_EXEMPT = {"Claim_ID", "Claim_Status", "CPT_Code", "Date_Submitted", "Claim_Frequency_Code", "Original_Claim_ID",
              "Paid_Amount", "Adjustment_Amount", "Patient_Responsibility"}
CORR_SET = {"Claim_ID": CORR_CLAIM, "Claim_Status": "New", "CPT_Code": "99213-25", "Date_Submitted": None,
            "Claim_Frequency_Code": "7", "Original_Claim_ID": MOD_CLAIM}


# ---- helpers -------------------------------------------------------------------------------------

def cell_eq(got, want) -> bool:
    if want is None:
        return blank(got)
    g, w = str(got if got is not None else "").strip(), str(want).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[ T]00:00:00)?", w):
        return g[:10] == w[:10] and g[10:].strip(" T") in ("", "00:00:00")
    a, b = num(g), num(w)
    if a is not None and b is not None:
        return abs(a - b) < 0.006
    return norm(g) == norm(w)


def keyed(w: World, book: str, header: str, key: str, which: str = "current") -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in w.rows(book, header, which):
        k = World.col(r, rf"^{key}$")
        if k and k not in out:
            out[k] = r
    return out


def val(r: dict | None, column: str) -> str:
    return World.col(r, rf"^{column}$") if r else ""


def diff(before: dict, after: dict | None, skip: set[str] = frozenset()) -> list[str]:
    """Columns of an initial row whose value changed (initial columns only)."""
    if after is None:
        return ["(row removed)"]
    return [k for k in before if k != "__row__" and k not in skip and not cell_eq(val(after, k), before[k] or None)]


def marcus_replied(ctx) -> bool:
    return any(PFR in e.sender and CO27_CLAIM in f"{e.subject}\n{e.body}" for e in ctx.state.emails)


def corrected_rows(w: World) -> list[dict]:
    init = keyed(w, REG, H_REG, "Claim_ID", "initial")
    return [r for k, r in keyed(w, REG, H_REG, "Claim_ID").items()
            if k not in init and (val(r, "Original_Claim_ID") == MOD_CLAIM or k == CORR_CLAIM)]


# ---- messages ------------------------------------------------------------------------------------

def _to(a, addr: str) -> bool:
    return addr in [x.lower() for x in a.recipients + a.cc]


def specs(ctx) -> list[Comm]:
    w = world(ctx)
    is_mail = lambda a: a.kind == "email_send"

    appeal = Comm(
        "co50_appeal", "email",
        lambda a: is_mail(a) and (any(x.endswith("@aetna-sim.com") for x in a.recipients + a.cc) or bool(
            re.search(r"^\s*appeal\b", a.subject, re.I) and CO50_CLAIM in a.subject
            and re.search(r"medical necessity", a.subject, re.I))),
        f"formal CO-50 Medical Necessity appeal for {CO50_CLAIM} to Aetna Appeals (template 10.6)",
        [R_CO50_APPEAL, R_106_SUBJ, R_106_BODY, R_106_END, R_COMM],
        to=[APPEALS], exact_to=False,
        subject=rf"Appeal\s*[-–]\s*{CO50_CLAIM}\s*[-–]\s*Medical Necessity",
        subject_hint=f"Appeal — {CO50_CLAIM} — Medical Necessity",
        body=[(r"To the Appeals Department", "the salutation \"To the Appeals Department,\""),
              (r"Please find attached a formal appeal for the above-referenced claim, denied under reason code CO-50",
               "\"Please find attached a formal appeal for the above-referenced claim, denied under reason code "
               "CO-50.\""),
              (rf"Claim ID:\s*{CO50_CLAIM}", f"\"Claim ID: {CO50_CLAIM}\""),
              (r"Date of Service:\s*2026-03-18", "\"Date of Service: 2026-03-18\""),
              (r"Letter of Medical Necessity", "the attachment list item \"1. Letter of Medical Necessity\""),
              (r"Clinical chart notes for the date of service",
               "the attachment list item \"2. Clinical chart notes for the date of service\""),
              (r"We respectfully request reconsideration and reprocessing of this claim",
               "\"We respectfully request reconsideration and reprocessing of this claim.\""),
              (r"Thank you,?\s*Natalie Simmons", "the sign-off \"Thank you, Natalie Simmons\""),
              (r"Pathfinder Billing and Coding", "\"Pathfinder Billing and Coding\" under the signature"),
              (r"Patient ID:?\s*PAT-10342", "the claim field \"Patient ID: PAT-10342\" (Section 10)"),
              (r"CPT[^:\n]{0,12}:?\s*99214", "the claim field \"CPT Code(s): 99214\" (Section 10)"),
              (r"Payer:?\s*Aetna", "the claim field \"Payer: Aetna\" (Section 10)"),
              (r"Claim Status:?\s*(Denied|In Recovery|Appealed)",
               "the claim field \"Claim Status: <current status from the claim register>\" (Section 10)")],
        attach=[(r"LMN_CLM-2026-00001", "LMN_CLM-2026-00001.txt (the RCM-approved LMN)"),
                (r"ChartNotes_PAT-10342", "ChartNotes_PAT-10342_2026-03-18.txt (chart notes received from the CMC)")])

    followup = Comm(
        "esc_followup", "email",
        lambda a: is_mail(a) and bool(re.search(r"ESC-00001|Escalation Follow", text_of(a), re.I)),
        "9.4 escalation follow-up for ESC-00001 to the RCM Manager (no email confirmation within 2 Business Hours "
        "of the 2026-04-08 13:31 escalation; template 10.5)",
        [R_REDUND, R_105_SUBJ, R_105_BODY],
        to=[RCM], exact_to=False,
        subject=r"HIGH PRIORITY\s*[-–]\s*Escalation Follow-Up\s*[-–]\s*ESC-00001",
        subject_hint="HIGH PRIORITY - Escalation Follow-Up - ESC-00001",
        body=[(r"Hi Catherine", "the greeting \"Hi Catherine,\""),
              (r"This is a follow-up regarding ESC-00001, which was escalated to you on 2026-04-08 at 13:31",
               "\"This is a follow-up regarding ESC-00001, which was escalated to you on 2026-04-08 at 13:31.\""),
              (r"I have not yet received email confirmation that this escalation is active",
               "\"I have not yet received email confirmation that this escalation is active.\""),
              (r"Please reply to confirm receipt and acknowledge the escalation at your earliest convenience",
               "\"Please reply to confirm receipt and acknowledge the escalation at your earliest convenience.\""),
              (r"Thank you,?\s*Natalie", "the sign-off \"Thank you, Natalie\"")])

    out = [appeal, followup]
    appeal_sent = any(appeal.about(a) and APPEALS in a.recipients for a in w.comms())

    def to_person(a, addr: str, name: str) -> bool:
        return (a.kind in ("email_send", "email_draft") and _to(a, addr)) or (
            a.kind in ("slack_dm", "slack_post") and w.is_dm_to(a, name))

    if not appeal_sent:
        out.append(Comm(
            "co50_signoff_again", "email",
            lambda a: to_person(a, RCM, "Catherine Lawson") and "ESC-00001" not in text_of(a)
            and bool(re.search(rf"{CO50_CLAIM}|\bLMN\b|medical necessity", text_of(a), re.I))
            and bool(re.search(r"sign[- ]?off|approv|review", text_of(a), re.I)),
            f"repeat LMN sign-off request for {CO50_CLAIM}", [R_CO50_SIGN, R_CO50_APPEAL],
            forbidden=(f"Catherine Lawson (RCM Manager) already reviewed and approved the LMN for {CO50_CLAIM} on "
                       "2026-04-07 (inbox: \"Re: LMN Approval Request — CLM-2026-00001\" - \"Approved.\"). CO-50 step 3 "
                       f"is complete; do not ask again. Next step 4: email the formal appeal (template 10.6) to {APPEALS} "
                       "with LMN_CLM-2026-00001.txt and ChartNotes_PAT-10342_2026-03-18.txt attached.")))
        out.append(Comm(
            "co50_notes_again", "email",
            lambda a: to_person(a, CMC, "David Nguyen")
            and bool(re.search(rf"{CO50_CLAIM}|PAT-10342", text_of(a), re.I))
            and bool(re.search(r"chart|notes?\b|operation report|op[- ]?r(e)?p(or)?t|documentation", text_of(a), re.I)),
            f"repeat chart-notes request for {CO50_CLAIM}", [R_CO50_NOTES],
            forbidden=("David Nguyen (CMC) already sent the chart notes for PAT-10342 / DOS 2026-03-18 on 2026-04-06 "
                       "(ChartNotes_PAT-10342_2026-03-18.txt is in /workdir). CO-50 step 1 is complete; do not ask again.")))
    if not corrected_rows(w):
        out.append(Comm(
            "modifier_query_again", "email",
            lambda a: to_person(a, CMC, "David Nguyen")
            and bool(re.search(rf"{MOD_CLAIM}|PAT-10587", text_of(a), re.I))
            and bool(re.search(r"modifier|\b25\b|\b59\b", text_of(a), re.I)),
            f"repeat modifier verification request for {MOD_CLAIM}", [R_MOD_Q, R_MOD_REPLY, R_MOD_CLAIM],
            forbidden=(f"David Nguyen (CMC) already replied on 2026-04-07 that Modifier 25 is supported for {MOD_CLAIM} "
                       "(inbox: \"Re: Modifier Verification Request — CLM-2026-00003\"). 6.3 steps 1-2 are complete; do "
                       f"not query again. Next step 3: add corrected claim {CORR_CLAIM} (CPT 99213-25, Claim Frequency "
                       f"Code 7, Original_Claim_ID {MOD_CLAIM}) to PBC_Claim_Register.xlsx.")))
    return out


# ---- RA queue ------------------------------------------------------------------------------------

def ra_severity(ctx):
    w = world(ctx)
    cur = keyed(w, RAQ, H_RAQ, "Queue_ID")
    for q in ("QUE-00005", "QUE-00006", "QUE-00007"):
        got = val(cur.get(q), "Severity_Level")
        yield (got == SEVERITY,
               f"PBC_RA_Queue.xlsx {q}: Severity_Level is \"{got}\" - it must not be blank; set it to exactly "
               f"\"{SEVERITY}\" (denial under $1,000, more than 30 days to TFL).", [R_SEV, R_SEV3])


def ra_status(ctx):
    w = world(ctx)
    cur = keyed(w, RAQ, H_RAQ, "Queue_ID")
    for q, claim, what in (("QUE-00005", CO50_CLAIM, "the Aetna appeal is sent and DNL-00006 / the claim register "
                                                     "are updated"),
                           ("QUE-00006", MOD_CLAIM, f"corrected claim {CORR_CLAIM} is added and DNL-00005 is updated")):
        got = val(cur.get(q), "Status")
        yield (got == "Closed",
               f"PBC_RA_Queue.xlsx {q} ({claim}): Status is \"{got}\"; set it to \"Closed\" once {what} (all "
               "recovery-plan actions taken).", [R_RAQ_FILE])


def ra_unchanged(ctx):
    w = world(ctx)
    init, cur = keyed(w, RAQ, H_RAQ, "Queue_ID", "initial"), keyed(w, RAQ, H_RAQ, "Queue_ID")
    for q, r0 in init.items():
        skip = {"Severity_Level", "Status"} if q in ("QUE-00005", "QUE-00006", "QUE-00007") else set()
        bad = diff(r0, cur.get(q), skip)
        yield (not bad, f"PBC_RA_Queue.xlsx {q}: unrequested change to {', '.join(bad)}; restore the original "
                        "values.", [R_RAQ_FILE])
    for q in cur:
        if q not in init:
            yield (False, f"PBC_RA_Queue.xlsx: unrequested new row {q}; no new denial or escalation is routed to the "
                          "RA in this task - remove it.", [R_RAQ_FILE, R_TRIAGE])


# ---- claim register ------------------------------------------------------------------------------

def reg_co50(ctx):
    w = world(ctx)
    got = val(keyed(w, REG, H_REG, "Claim_ID").get(CO50_CLAIM), "Claim_Status")
    yield (got == "In Recovery",
           f"PBC_Claim_Register.xlsx {CO50_CLAIM}: Claim_Status is \"{got}\"; set it to \"In Recovery\" (CO-50 step 6).",
           [R_CO50_REG])


def reg_modifier(ctx):
    w = world(ctx)
    init, cur = keyed(w, REG, H_REG, "Claim_ID", "initial"), keyed(w, REG, H_REG, "Claim_ID")
    got = val(cur.get(MOD_CLAIM), "Claim_Status")
    yield (got == "Resubmitted",
           f"PBC_Claim_Register.xlsx {MOD_CLAIM}: Claim_Status is \"{got}\"; set the original claim to \"Resubmitted\".",
           [R_RECOVERY])
    orig = init.get(MOD_CLAIM) or {}
    want = {k: (orig[k] or None) for k in orig if k != "__row__" and k not in MOD_EXEMPT}
    want.update(CORR_SET)
    spec = "; ".join(f"{k}={'(blank)' if v is None else v}" for k, v in want.items())
    rows = corrected_rows(w)
    if not rows:
        yield (False, f"PBC_Claim_Register.xlsx: corrected claim for {MOD_CLAIM} (Modifier 25 confirmed by the CMC) is "
                      f"missing. Append one row: {spec}.", [R_MOD_CLAIM, R_RECOVERY, R_IDS, R_REG_FILE])
        return
    if len(rows) > 1:
        yield (False, f"PBC_Claim_Register.xlsx: {len(rows)} corrected claims reference {MOD_CLAIM}; keep exactly one "
                      f"({CORR_CLAIM}).", [R_MOD_CLAIM])
    r = rows[0]
    bad = [f"{k} should be {'(blank)' if v is None else repr(v)} (got {val(r, k)!r})"
           for k, v in want.items() if not cell_eq(val(r, k), v)]
    yield (not bad, f"PBC_Claim_Register.xlsx corrected claim {val(r, 'Claim_ID')}: " + "; ".join(bad) + ".",
           [R_MOD_CLAIM, R_IDS, R_REG_FILE])


def reg_unchanged(ctx):
    w = world(ctx)
    init, cur = keyed(w, REG, H_REG, "Claim_ID", "initial"), keyed(w, REG, H_REG, "Claim_ID")
    for k, r0 in init.items():
        if k == CO27_CLAIM:
            continue
        bad = diff(r0, cur.get(k), {"Claim_Status"} if k in (CO50_CLAIM, MOD_CLAIM) else set())
        yield (not bad, f"PBC_Claim_Register.xlsx {k}: unrequested change to {', '.join(bad)}; restore the original "
                        "values.", [R_REG_FILE])
    for k, r in cur.items():
        if k in init or val(r, "Original_Claim_ID") in (MOD_CLAIM, CO27_CLAIM) or k == CORR_CLAIM:
            continue
        yield (False, f"PBC_Claim_Register.xlsx: unrequested new claim row {k}; the only new claim in this task is the "
                      f"Modifier 25 correction {CORR_CLAIM} - remove it.", [R_REG_FILE])


# ---- denial worklist -----------------------------------------------------------------------------

def _wl_expect(ctx, dnl: str, action: str, status: str, refs):
    w = world(ctx)
    r = keyed(w, WL, H_WL, "Denial_ID").get(dnl)
    got = (val(r, "Recovery_Action"), val(r, "Recovery_Status"))
    yield (got == (action, status),
           f"PBC_Denial_Worklist.xlsx {dnl}: Recovery_Action/Recovery_Status are \"{got[0]}\"/\"{got[1]}\"; set them "
           f"to exactly \"{action}\" / \"{status}\".", refs)


def wl_co50(ctx):
    yield from _wl_expect(ctx, "DNL-00006", "Appeal - Medical Necessity", "Appealed", [R_CO50_WL])


def wl_modifier(ctx):
    yield from _wl_expect(ctx, "DNL-00005", "Add Modifier and Resubmit", "Resubmitted", [R_MOD_WL, R_RECOVERY])


def wl_unchanged(ctx):
    w = world(ctx)
    init, cur = keyed(w, WL, H_WL, "Denial_ID", "initial"), keyed(w, WL, H_WL, "Denial_ID")
    for k, r0 in init.items():
        if k == "DNL-00007":
            continue
        skip = {"Recovery_Action", "Recovery_Status"} if k in ("DNL-00005", "DNL-00006") else set()
        bad = diff(r0, cur.get(k), skip)
        yield (not bad, f"PBC_Denial_Worklist.xlsx {k}: unrequested change to {', '.join(bad)}; restore the original "
                        "values.", [R_WL_FILE])
    for k in cur:
        if k not in init:
            yield (False, f"PBC_Denial_Worklist.xlsx: unrequested new row {k}; no new denial exists in this task - "
                          "remove it.", [R_WL_FILE, R_TRIAGE])


# ---- CO-27: waiting for the PFR ------------------------------------------------------------------

def co27_wait(ctx):
    if marcus_replied(ctx):
        return
    w = world(ctx)
    why = ("the PFR (Marcus Thompson) has not replied to the 2026-04-07 handoff email \"Patient Contact Needed — "
           "CLM-2026-00004\"; CO-27 steps 3-4 start only upon his reply")
    wl0, wl = keyed(w, WL, H_WL, "Denial_ID", "initial").get("DNL-00007"), keyed(w, WL, H_WL, "Denial_ID").get("DNL-00007")
    if wl0:
        bad = diff(wl0, wl)
        yield (not bad, f"PBC_Denial_Worklist.xlsx DNL-00007 ({CO27_CLAIM}) changed ({', '.join(bad)}) but {why}. "
                        "Restore Recovery_Status \"In Progress\" and a blank Recovery_Action.", [R_CO27_REPLY])
    init, cur = keyed(w, REG, H_REG, "Claim_ID", "initial"), keyed(w, REG, H_REG, "Claim_ID")
    if CO27_CLAIM in init:
        bad = diff(init[CO27_CLAIM], cur.get(CO27_CLAIM))
        yield (not bad, f"PBC_Claim_Register.xlsx {CO27_CLAIM} changed ({', '.join(bad)}) but {why}. Restore the "
                        "original row.", [R_CO27_REPLY, R_CO27_CLAIM])
    extra = [k for k, r in cur.items() if k not in init and val(r, "Original_Claim_ID") == CO27_CLAIM]
    yield (not extra, f"PBC_Claim_Register.xlsx: corrected claim {', '.join(extra)} for {CO27_CLAIM} was created but "
                      f"{why}. Remove it.", [R_CO27_CLAIM])
    q = val(keyed(w, RAQ, H_RAQ, "Queue_ID").get("QUE-00007"), "Status")
    yield (q == "In Progress", f"PBC_RA_Queue.xlsx QUE-00007 ({CO27_CLAIM}): Status is \"{q}\" but {why}. Keep it "
                               "\"In Progress\".", [R_CO27_HANDOFF, R_RAQ_FILE])


# ---- escalation log ------------------------------------------------------------------------------

def esc_no_new(ctx):
    w = world(ctx)
    init, cur = keyed(w, ESC, H_ESC, "Escalation_ID", "initial"), keyed(w, ESC, H_ESC, "Escalation_ID")
    for k, r in cur.items():
        if k in init:
            continue
        yield (False, f"PBC_Escalation_Log.xlsx: unrequested new escalation {k} ({val(r, 'Escalation_Reason')}). "
                      "ESC-00001 already logs the BCBS Modifier 25 Pattern Recurrence (escalated 2026-04-08 13:31) - "
                      "send the 10.5 follow-up email instead of logging it again; the CO-50 LMN was already approved by "
                      "the RCM Manager and no claim exceeds $5,000. Remove the row.", [R_ESC_ALL, R_MOD_RED, R_REDUND])


# ---- calendar: TFL of the corrected claim --------------------------------------------------------

TFL_HINT = (f"summary \"TFL - {CORR_CLAIM}\", all-day on 2026-09-19 (end date 2026-09-20), description \"Timely Filing "
            f"Limit for {CORR_CLAIM}. Payer: Blue Cross Blue Shield (180 days). DOS: 2026-03-23.\"")


def _tfl_event(a) -> bool:
    return a.kind == "calendar_create" and CORR_CLAIM in a.subject and bool(re.search(r"\bTFL\b|Timely Filing",
                                                                                         a.subject, re.I))


def _tfl_date_ok(a) -> bool:
    return "2026-09-19" in json.dumps(a.args.get("start") or a.args.get("start_time") or a.args.get("startTime") or "")


def tfl_calendar(ctx):
    w = world(ctx)
    if not corrected_rows(w):
        yield (False, f"TFL calendar entry for corrected claim {CORR_CLAIM} is missing (create it after adding the "
                      f"claim): {TFL_HINT}.", [R_TFL])
        return
    ok = any(_tfl_event(a) and _tfl_date_ok(a) for a in w.calls("calendar_create"))
    yield (ok, f"TFL calendar entry for corrected claim {CORR_CLAIM} is missing: create it with {TFL_HINT}.", [R_TFL])


def tfl_pre(ctx, a):
    if _tfl_event(a) and not _tfl_date_ok(a):
        return (f"The TFL for {CORR_CLAIM} (BCBS, 180 days from DOS 2026-03-23) is 2026-09-19 - same as the original "
                f"claim's calendar entry. Use {TFL_HINT}.")
    return None


# ---- reference data ------------------------------------------------------------------------------

def reference_unchanged(ctx):
    w = world(ctx)
    for f in w.changed_files():
        if re.search(r"Eligibility_Responses|Payer_Contact", f, re.I):
            yield (False, f"{f} is reference data and must not be changed in this task; restore it.", [R_ELIG_FILE])


RULES = [
    *comm_rules("comms", specs),
    *state_rule("ra_queue.severity", ra_severity, "Fill Severity_Level for the In Progress queue items."),
    *state_rule("ra_queue.status", ra_status, "Close the queue item once every recovery-plan action is done."),
    *state_rule("ra_queue.unchanged", ra_unchanged, "Restore the RA Queue rows listed."),
    *state_rule("register.co50_status", reg_co50, "Update the claim register as listed."),
    *state_rule("register.modifier_resubmission", reg_modifier, "Update the claim register as listed."),
    *state_rule("register.unchanged", reg_unchanged, "Restore the claim register rows listed."),
    *state_rule("worklist.co50", wl_co50, "Update the denial worklist as listed."),
    *state_rule("worklist.modifier", wl_modifier, "Update the denial worklist as listed."),
    *state_rule("worklist.unchanged", wl_unchanged, "Restore the denial worklist rows listed."),
    *state_rule("co27.await_pfr", co27_wait, "Undo the CO-27 changes until the PFR replies."),
    *state_rule("escalation_log.no_new_rows", esc_no_new, "Remove the new escalation row."),
    *append_only("escalation_log.append_only", ESC, H_ESC, "PBC_Escalation_Log.xlsx", [R_ESC_FILE]),
    *state_rule("calendar.tfl_corrected_claim", tfl_calendar, "Create the TFL calendar entry."),
    *pre_rule("calendar.tfl_date", tfl_pre, [R_TFL], "Create the TFL event with the date listed."),
    *state_rule("files.reference_unchanged", reference_unchanged, "Restore the reference workbook."),
    *no_placeholders([R_105_BODY, R_106_BODY]),
]
