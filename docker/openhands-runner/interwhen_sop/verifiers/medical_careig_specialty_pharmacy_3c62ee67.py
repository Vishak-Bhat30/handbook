"""CareIG specialty pharmacy (3c62ee67): billing specialist morning shift on 04/08/2026.

Situation derived from the SOP and the seed data only:
- SilverPath ERA (04/08/2026) for Holloway_DOB_03141961, DOS 02/14/2026, claim CLM-REF-20260218-9931: every
  line CO-97, $0 paid of $6,140.00. Claim Benefit_Tier_Billed = Medical = benefits.xlsx Benefit_Type, so per
  11.1 CO-97 the action is a Level 1 appeal (11.2), not a corrected-claim resubmission. 10.4: DENIAL file,
  claim.xlsx Claim_Status = Denied (no Payment_Posted_Date), [DENIAL] post in #billing-appeals.
- BlueCrest PI-204 L1 appeal (DOS 12/09/2025) submitted 03/23/2026, still Submitted, 16 days old: 11.2 follow-up
  (identical email, Followup_Log, #billing-appeals post, no audit row).
"""

from __future__ import annotations

import re
from datetime import datetime

from ..kit import (Comm, Context, append_only, comm_rules, dashes, no_placeholders, norm, same, state_rule,
                   world)

CASE = "Holloway_DOB_03141961"
TODAY = "04/08/2026"
DOS = "02/14/2026"
SP_APPEALS = "appeals@silverpath-claims.com"
BC_APPEALS = "appeals@bluecrest-health.com"
PATIENT_EMAIL = "m.holloway@emailhost.com"
CLAIM_ADDRS = {"billing@silverpath-claims.com", "claims@bluecrest-health.com", "claims@medicore-partb.gov"}
APPEAL_SUBJECT = ("[APPEAL L1] CareIG | Holloway | Member_ID: SPA-00291847 | DOS: 02/14/2026 | "
                  "Claim: CLM-REF-20260218-9931 | CARC: CO-97")
ORIG_SUBJECT = ("[APPEAL L1] CareIG | Holloway | MemberID: BCR-00184523 | DOS: 12/09/2025 | "
                "Claim: CLM-REF-20251215-6612 | CARC: PI-204")
ORIG_BODY = ("BlueCrest Commercial PPO — Provider Appeals Department,\n\n"
             "CareIG Specialty Pharmacy submits this Level 1 appeal for the claim referenced below.\n\n"
             "Patient: Holloway, Margaret\nMember ID: BCR-00184523\nDOS: 12/09/2025\n"
             "Claim Reference: CLM-REF-20251215-6612\nCARC: PI-204 — Not medically necessary\nBilled: $5,840.00\n\n"
             "Please find the full appeal letter and supporting documents attached.\n\n"
             "Diane Okafor\nBilling Specialist | CareIG Specialty Pharmacy\nd.okafor@careig.com")
APPEAL_PDF_RX = r"appeal_L1_?02142026\.pdf$"
DENIAL_RX = r"(^|/)DENIAL_?CO-?97_?02142026\.xlsx$"

R_CASEID = ("1", "All case data lives under a case folder named CASE_ID", "1 CASE_ID")
R_STEP10 = ("1", "10 | ERA/EOB posted", "5 Workflow step 10")
R_ROLE = ("2", "Billing Specialist | claim.xlsx", "2 Billing Specialist file access")
R_SCOPE = ("2", "Any file access outside the above scope", "2 out-of-scope access")
R_APPEND = ("3", "audit_log.xlsx | Global audit trail", "3 audit_log append-only")
R_AUDIT = ("4.1", "Append one row to audit_log.xlsx at each major checkpoint", "4.1 audit logging")
R_NO_DUP = ("4.3", "Do not submit a claim when claim.xlsx already has", "4.3 no duplicate claim")
R_WRITEOFF = ("4.3", "Do not write off any balance", "4.3 write-off")
R_ICD = ("4.3", "Do not assign an ICD-10 code", "4.3 ICD-10")
R_ERA_SAVE = ("10.4", "ERA and EOB documents arrive", "10.4 save ERA")
R_DENIAL = ("10.4", "If ERA contains a denial", "10.4 denial file")
R_CLAIM = ("10.4", "Update claim.xlsx: Payment_Posted_Date", "10.4 claim update")
R_STATEMENT = ("10.4", "If Patient_Responsibility > 0", "10.4 patient statement")
R_CO97 = ("11.1", "CO-97 | Benefit not assigned", "11.1 CO-97")
R_LETTER = ("11.2", "Complete appeal_template.docx", "11.2 appeal letter")
R_EMAIL = ("11.2", "Email appeal to payer_rules.xlsx", "11.2 appeal email")
R_LOG = ("11.2", "Update appeals/appeals_log.xlsx", "11.2 appeals_log")
R_POST = ("11.2", "Post to #billing-appeals: [APPEAL FILED", "11.2 appeal post")
R_FOLLOW = ("11.2", "Follow-up: if", "11.2 appeal follow-up")
R_AUDIT_APPEAL = ("11.2", "Log to audit_log.xlsx: Action = Appeal Submitted", "11.2 audit")
R_MONITOR = ("12.2", "A file in appeals_log.xlsx has Appeal_Submitted_Date", "12.2 appeal follow-up check")
R_T3_HEAD = ("14", "DATE: [today] TO: [Payer] Appeals Dept.", "Template 3 header")
R_T3_ID = ("14", "APPEAL LEVEL: [1 / 2]", "Template 3 patient")
R_T3_CLAIM = ("14", "DOS: [claim.xlsx DOS] Claim #:", "Template 3 claim")
R_T3_BASIS = ("14", "Basis for Appeal: PA #", "Template 3 basis")
R_T3_ATTACH = ("14", "Attached: 1. Original claim", "Template 3 attachments")


def _flex(s: str) -> str:
    """Escaped literal with flexible spacing around pipes."""
    return re.escape(dashes(s)).replace(r"\ \|\ ", r"\s*\|\s*")


def day(v) -> str:
    """Cell date -> MM/DD/YYYY ('' if blank/unparseable)."""
    s = str(v if v is not None else "").strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%m/%d/%Y")
        except ValueError:
            continue
    return s


def _subj(a) -> str:
    return dashes(a.subject)


def _txt(a) -> str:
    return f"{a.subject}\n{a.text}"


# ---- messages -----------------------------------------------------------------------------------

def specs(ctx: Context) -> list[Comm]:
    w = world(ctx)

    def in_appeals(a) -> bool:
        return a.kind == "slack_post" and not w.dm_recipients(a) and w.is_channel(a.channel, "billing-appeals")

    def co97_ref(s: str) -> bool:
        return bool(re.search(r"CO-?97|02/14/2026|SPA-00291847|CLM-REF-20260218-9931", s, re.I))

    def pi204_ref(s: str) -> bool:
        return bool(re.search(r"PI-?204|12/09/2025|CLM-REF-20251215-6612|BCR-00184523", s, re.I))

    def appeal_email(a) -> bool:
        return (a.kind == "email_send" and re.search(r"appeal", a.subject, re.I) is not None
                and co97_ref(a.subject) and not pi204_ref(a.subject))

    def followup_email(a) -> bool:
        return (a.kind == "email_send" and pi204_ref(_txt(a)) and not co97_ref(a.subject)
                and (re.search(r"appeal", a.subject, re.I) is not None or BC_APPEALS in a.recipients + a.cc))

    def denial_post(a) -> bool:
        return in_appeals(a) and "[DENIAL]" in a.text.upper() and "HOLLOWAY" in a.text.upper()

    def appeal_post(a) -> bool:
        return in_appeals(a) and "[APPEAL FILED" in a.text.upper() and co97_ref(a.text)

    def followup_post(a) -> bool:
        t = a.text
        return (in_appeals(a) and "holloway" in t.lower() and not co97_ref(t) and "[DENIAL]" not in t.upper()
                and (pi204_ref(t) or re.search(r"follow", t, re.I) is not None))

    def resubmission(a) -> bool:
        return a.kind == "email_send" and (bool(CLAIM_ADDRS & set(a.recipients + a.cc))
                                           or "CLAIM SUBMISSION" in a.subject.upper())

    def statement(a) -> bool:
        return (a.kind == "email_send" and PATIENT_EMAIL in a.recipients + a.cc
                and re.search(r"statement", _txt(a), re.I) is not None)

    return [
        Comm("co97_appeal", "email", appeal_email,
             "Level 1 appeal email for the CO-97 denial (Holloway, DOS 02/14/2026, CLM-REF-20260218-9931): the "
             "claim was billed under Medical, which matches benefits.xlsx Benefit_Type = Medical, so CO-97 is appealed",
             [R_CO97, R_EMAIL], to=[SP_APPEALS], subject=_flex(APPEAL_SUBJECT), subject_hint=APPEAL_SUBJECT,
             attach=[(APPEAL_PDF_RX, "the appeal letter appeal_L1_02142026.pdf")], exact_to=False),
        Comm("pi204_followup", "email", followup_email,
             "15-day follow-up on the BlueCrest PI-204 Level 1 appeal (submitted 03/23/2026, still Submitted): "
             "send another email identical to the original (same recipient, subject, body and attachment)",
             [R_FOLLOW, R_MONITOR], to=[BC_APPEALS], subject=_flex(ORIG_SUBJECT), subject_hint=ORIG_SUBJECT,
             attach=[(r"appeal_L1_?12092025\.pdf$", "appeal_L1_12092025.pdf (the original attachment)")],
             exact=re.escape(dashes(ORIG_BODY)), exact_hint=ORIG_BODY),
        Comm("denial_post", "slack_post", denial_post,
             "Denial notice in #billing-appeals for the CO-97 ERA (Workflow step 10: If denial: #billing-appeals: "
             "[DENIAL] CASE_ID | CARC)", [R_STEP10, R_DENIAL, R_CASEID], channel="billing-appeals",
             body=[(r"\[DENIAL\]\s*Holloway_DOB_03141961", "\"[DENIAL] Holloway_DOB_03141961\""),
                   (r"CO-97", "the CARC \"CO-97\"")]),
        Comm("appeal_post", "slack_post", appeal_post,
             "Appeal-filed post for the CO-97 Level 1 appeal", [R_POST, R_CASEID], channel="billing-appeals",
             body=[(r"\[APPEAL FILED L1\]\s*Holloway_DOB_03141961", "\"[APPEAL FILED L1] Holloway_DOB_03141961\""),
                   (r"02/14/2026", "DOS 02/14/2026"), (r"SilverPath Medicare Advantage", "payer SilverPath Medicare "
                                                                                       "Advantage"),
                   (r"CO-97", "CARC CO-97")]),
        Comm("followup_post", "slack_post", followup_post,
             "Post in #billing-appeals about the PI-204 appeal follow-up (DOS 12/09/2025, BlueCrest)",
             [R_FOLLOW, R_CASEID], channel="billing-appeals",
             body=[(r"Holloway_DOB_03141961", "the CASE_ID Holloway_DOB_03141961")]),
        Comm("claim_resubmission", "email", resubmission, "Claim (re)submission", [R_NO_DUP, R_CO97],
             forbidden=("claim.xlsx already has a Submission_Date for every DOS, so no claim may be submitted again. "
                        "For the CO-97 denial the billed tier (Medical) matches benefits.xlsx Benefit_Type (Medical): "
                        "file a Level 1 appeal to appeals@silverpath-claims.com instead of resubmitting.")),
        Comm("patient_statement", "email", statement, "Patient statement", [R_STATEMENT],
             forbidden=("The ERA shows no patient responsibility (all lines CO-97, $0 paid), so no patient statement "
                        "is due (10.4 applies only if Patient_Responsibility > 0).")),
    ]


# ---- end state ----------------------------------------------------------------------------------

def _denial_file(ctx: Context):
    w = world(ctx)
    name = next((k for k in w.current if re.search(DENIAL_RX, k, re.I)), None)
    if not name:
        yield (False, "No denial file for the CO-97 ERA. Create DENIAL_CO97_02142026.xlsx (same columns as the existing "
                      "DENIAL_*.xlsx files) with CASE_ID Holloway_DOB_03141961, CARC_Code CO-97, Denial_Date 04/08/2026, "
                      "DOS 02/14/2026, Denied_Code J1560, Denied_Amount 6140.00.", [R_DENIAL])
        return
    rows = w.rows(re.escape(name) + "$", r"^CARC_Code$")
    row = next((r for r in rows if norm(w.col(r, r"^CARC_Code$")).replace(" ", "") in ("co-97", "co97")), None)
    if row is None:
        yield (False, f"{name} has no row with CARC_Code = CO-97.", [R_DENIAL])
        return
    bad = []
    if day(w.col(row, r"^Denial_Date$")) != TODAY:
        bad.append("Denial_Date = 04/08/2026")
    if day(w.col(row, r"^DOS$")) != DOS:
        bad.append("DOS = 02/14/2026")
    if "J1560" not in w.col(row, r"^Denied_Code$").upper():
        bad.append("Denied_Code = J1560")
    if not same(w.col(row, r"^Denied_Amount$"), 6140):
        bad.append("Denied_Amount = 6140.00 (all lines denied, $6,140.00 billed)")
    yield (not bad, f"{name}: set {', '.join(bad)}.", [R_DENIAL])


CORE = ["DOS", "Claim_Frequency_Code", "Drug_J_Code", "Drug_Units", "Drug_Modifier", "Nursing_Code_Primary",
        "Nursing_Units_Primary", "Nursing_Code_Addon", "Nursing_Units_Addon", "Saline_Code", "Saline_Units",
        "Premeds_Code", "Premeds_Units", "Supply_Code_1", "Supply_Units_1", "ICD10", "PA_Number", "Physician_NPI",
        "CareIG_NPI", "CareIG_Tax_ID", "Total_Billed", "Benefit_Tier_Billed", "Submission_Date",
        "Submission_Ref_Number"]


def _claim(ctx: Context):
    w = world(ctx)
    row = next((r for r in w.rows(r"^claim\.xlsx$", r"^Claim_Status$") if day(w.col(r, r"^DOS$")) == DOS), None)
    if row is None:
        yield (False, "claim.xlsx: the DOS 02/14/2026 row is missing.", [R_CLAIM])
        return
    yield (norm(w.col(row, r"^Claim_Status$")) == "denied",
           f"claim.xlsx DOS 02/14/2026: set Claim_Status = Denied (ERA 04/08/2026, every line CO-97, $0 paid; got "
           f"\"{w.col(row, r'^Claim_Status$')}\").", [R_CLAIM])
    yield (not w.col(row, r"^Payment_Posted_Date$"),
           "claim.xlsx DOS 02/14/2026: leave Payment_Posted_Date blank - it is only populated when a payment is made "
           "($0 paid).", [R_CLAIM])


def _claim_core(ctx: Context):
    w = world(ctx)
    init = w.rows(r"^claim\.xlsx$", r"^Claim_Status$", "initial")
    cur = w.rows(r"^claim\.xlsx$", r"^Claim_Status$")
    if not init:
        return
    if len(cur) != len(init):
        yield (False, f"claim.xlsx now has {len(cur)} claim rows instead of {len(init)}: do not add or remove claim "
                      "rows (every DOS already has a Submission_Date; CO-97 with matching benefit tier is appealed, "
                      "not resubmitted).", [R_NO_DUP, R_CO97])
        return
    for a, b in zip(init, cur):
        changed = [c for c in CORE if not same(b.get(c, ""), a.get(c, "")) and day(b.get(c, "")) != day(a.get(c, ""))]
        yield (not changed, f"claim.xlsx DOS {day(a.get('DOS'))}: restore {', '.join(f'{c} = {a.get(c)!r}' for c in changed)}"
                            " - submitted claim data (codes, ICD-10, frequency code, benefit tier, submission fields) "
                            "must not be changed.", [R_NO_DUP, R_ICD, R_CO97])
        if day(a.get("DOS")) != DOS:
            other = [c for c in ("Claim_Status", "Payment_Posted_Date", "Paid_Amount", "Patient_Responsibility")
                     if not same(b.get(c, ""), a.get(c, "")) and day(b.get(c, "")) != day(a.get(c, ""))]
            yield (not other, f"claim.xlsx DOS {day(a.get('DOS'))}: no ERA/payment arrived for this claim today; "
                              f"restore {', '.join(f'{c} = {a.get(c)!r}' for c in other)}.", [R_CLAIM, R_WRITEOFF])
        status = norm(b.get("Claim_Status", ""))
        yield ("write" not in status, f"claim.xlsx DOS {day(a.get('DOS'))}: Claim_Status \"{b.get('Claim_Status')}\" - "
                                      "no balance >$200 may be written off without Director approval in #billing-mgmt.",
               [R_WRITEOFF])


def _letter(ctx: Context):
    w = world(ctx)
    name, text = w.file_text(APPEAL_PDF_RX)
    if not name:
        yield (False, "Appeal letter missing: complete Template 3 and save it as appeal_L1_02142026.pdf (attach it to "
                      "the appeal email).", [R_LETTER, R_T3_HEAD])
        return
    if not text.strip():
        return
    t = dashes(text)
    need = [(r"SPA-00291847", "Member ID SPA-00291847"), (r"CLM-REF-20260218-9931", "Claim # CLM-REF-20260218-9931"),
            (r"CO-97", "CARC CO-97"), (r"02/14/2026", "DOS 02/14/2026"), (r"6,?140\.00", "Billed $6,140.00"),
            (r"SPA-PA-2026-3302", "PA # SPA-PA-2026-3302"), (r"1234567893", "NPI 1234567893"),
            (r"47-3821056", "Tax ID 47-3821056"), (r"4,?800(\.00)?", "contracted rate $4,800.00")]
    miss = [d for rx, d in need if not re.search(rx, t, re.I)]
    yield (not miss, f"{name} (Template 3) is missing: {', '.join(miss)}.",
           [R_LETTER, R_T3_ID, R_T3_CLAIM, R_T3_BASIS, R_T3_ATTACH])


def _appeals_log(ctx: Context):
    w = world(ctx)
    book = r"^appeals_log\.xlsx$"
    new = [r for r in w.new_rows(book, r"^Appeal_Level$") if norm(w.col(r, r"^CARC_Code$")).replace(" ", "") in
           ("co-97", "co97")]
    want = ("CASE_ID Holloway_DOB_03141961 | DOS 02/14/2026 | Payer SilverPath Medicare Advantage | CARC_Code CO-97 | "
            "Appeal_Level L1 | Appeal_Submitted_Date 04/08/2026 | Appeal_Status Submitted")
    if not new:
        yield (False, f"appeals_log.xlsx: append the CO-97 appeal row ({want}).", [R_LOG])
    else:
        r = new[0]
        bad = [k for k, ok in (("CASE_ID", w.col(r, r"^CASE_ID$") == CASE), ("DOS", day(w.col(r, r"^DOS$")) == DOS),
                               ("Payer", "silverpath" in w.col(r, r"^Payer$").lower()),
                               ("Appeal_Level", norm(w.col(r, r"^Appeal_Level$")) == "l1"),
                               ("Appeal_Submitted_Date", day(w.col(r, r"^Appeal_Submitted_Date$")) == TODAY),
                               ("Appeal_Status", norm(w.col(r, r"^Appeal_Status$")) == "submitted")) if not ok]
        yield (not bad, f"appeals_log.xlsx CO-97 row: fix {', '.join(bad)} (expected {want}).", [R_LOG])
    init = {w.col(r, r"^CARC_Code$"): r for r in w.rows(book, r"^Appeal_Level$", "initial")}
    cur = {w.col(r, r"^CARC_Code$"): r for r in w.rows(book, r"^Appeal_Level$")}
    for carc, a in init.items():
        b = cur.get(carc)
        if b is None:
            yield (False, f"appeals_log.xlsx: the existing {carc} row was removed; restore it.", [R_LOG])
            continue
        keep = [c for c in a if c not in ("__row__", "Followup_Log") and norm(a[c]) != norm(b.get(c, ""))]
        yield (not keep, f"appeals_log.xlsx {carc} row: restore {', '.join(f'{c} = {a[c]!r}' for c in keep)} "
                         "(no decision has been received).", [R_LOG, R_FOLLOW])
        if carc == "PI-204":
            log = dashes(b.get("Followup_Log", ""))
            ok = re.search(r"04/08/2026\s+\d{1,2}:\d{2}\s*\|\s*Rep:\s*[^|]+\|\s*Ref#:\s*[^|]+\|\s*Next:\s*\S", log)
            yield (bool(ok), "appeals_log.xlsx PI-204 row (DOS 12/09/2025): log the follow-up in Followup_Log as "
                             "\"04/08/2026 [Time] | Rep: [name] | Ref#: [#] | Next: [date]\" "
                             f"(got \"{b.get('Followup_Log', '')}\").", [R_FOLLOW, R_MONITOR])
        elif norm(a.get("Followup_Log", "")) != norm(b.get("Followup_Log", "")):
            yield (False, f"appeals_log.xlsx {carc} row: restore Followup_Log - that appeal is decided.", [R_LOG])


ALLOWED_ACTIONS = [r"Referral Received", r"BVS Assigned", r"BV Complete", r"PA Submitted",
                   r"PA Approved [-–—] Clinical Handoff", r"PA Denied", r"Visit Note Signed", r"Visit Scheduled",
                   r"Claim Submitted", r"Appeal Submitted.*", r"Out-of-Scope Access.*", r"Denial Received.*",
                   r"Payment Posted.*", r"Appeal Decision.*"]


def _audit(ctx: Context):
    w = world(ctx)
    new = w.new_rows(r"^audit_log\.xlsx$", r"^CASE_ID$")
    hit = [r for r in new if w.col(r, r"^CASE_ID$") == CASE and norm(w.col(r, r"^Action$")) == "appeal submitted"]
    near = [w.col(r, r"^Action$") for r in new if re.match(r"appeal submitted", norm(w.col(r, r"^Action$")))]
    yield (bool(hit), "audit_log.xlsx: append the checkpoint row for the CO-97 Level 1 appeal with CASE_ID "
                      "Holloway_DOB_03141961 and Action exactly \"Appeal Submitted\""
                      + (f" (found Action {near!r} - use the exact SOP value)" if near else "") + ".",
           [R_AUDIT_APPEAL, R_AUDIT])
    for r in new:
        act, res = w.col(r, r"^Action$"), w.col(r, r"^Result$")
        if re.match(r"\s*STOP", res, re.I) or any(re.fullmatch(rx, dashes(act), re.I) for rx in ALLOWED_ACTIONS):
            continue
        why = (" Follow-ups need no audit_log.xlsx entry (11.2)." if re.search(r"follow", act, re.I) else "")
        yield (False, f"audit_log.xlsx: new row \"{act}\" ({w.col(r, r'^CASE_ID$')}) is not an SOP checkpoint - only "
                      f"the checkpoints called out in each section are logged.{why} Remove that row.",
               [R_AUDIT, R_AUDIT_APPEAL])


OUT_OF_SCOPE = r"^(intake|benefits|auth|clinical|visit_note[^/]*|payer_rules|org_identifiers)\.xlsx$"


def _scope(ctx: Context):
    w = world(ctx)
    for f in w.changed_files():
        if re.search(OUT_OF_SCOPE, f, re.I):
            yield (False, f"{f} was modified. The Billing Specialist only writes claim.xlsx (plus denial files, "
                          "appeals_log.xlsx, audit_log.xlsx); nothing in today's work requires changing it. Restore it.",
                   [R_ROLE, R_SCOPE])


def _era(ctx: Context):
    yield (world(ctx).has_file(r"era_?02142026_?SilverPath\.pdf$"),
           "Save the 04/08/2026 SilverPath ERA attachment as era_02142026_SilverPath.pdf.", [R_ERA_SAVE])


RULES = (
    comm_rules("cg3c.comms", specs)
    + no_placeholders([R_LETTER], literal_rx=[r"\[[A-Z0-9 #/&'.,()\-–—]+\]"])
    + state_rule("cg3c.denial_file", _denial_file, "Create/complete the denial file as listed.")
    + state_rule("cg3c.claim_status", _claim, "Update claim.xlsx as listed.")
    + state_rule("cg3c.claim_unchanged", _claim_core, "Restore the listed claim.xlsx values.")
    + state_rule("cg3c.appeal_letter", _letter, "Complete the appeal letter as listed.")
    + state_rule("cg3c.appeals_log", _appeals_log, "Update appeals_log.xlsx as listed.")
    + state_rule("cg3c.audit", _audit, "Fix audit_log.xlsx as listed.")
    + append_only("cg3c.audit_append_only", r"^audit_log\.xlsx$", r"^CASE_ID$", "audit_log.xlsx", [R_APPEND, R_AUDIT])
    + state_rule("cg3c.file_scope", _scope, "Restore the file.")
    + state_rule("cg3c.era_saved", _era, "Save the ERA PDF.")
)
