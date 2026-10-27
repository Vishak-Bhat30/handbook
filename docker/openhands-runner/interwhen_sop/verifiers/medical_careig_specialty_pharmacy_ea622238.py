"""CareIG Specialty Pharmacy - intake day 2026-09-28 (task ea622238), acting for Mia Hamilton (Patient Rep).

Seed situation (derived from the SOP + seed data only):
- CIG_2026_1024 Yellen: signed consent arrived 09/26, but an attorney records request arrived today ->
  SOP 12.1 legal STOP: post "[LEGAL] CIG_2026_1024" in #compliance, forward the attorney email to
  legal@careig.com and the Director of Operations (lmurphy@careig.com), do not respond, do not modify case files.
- CIG_2026_1025 Vasquez: patient reached 09/25, consent still Pending -> email Template 4 consent form,
  log "<date> <time> — Email" in Contact_Attempt_Log, Consent_Status = Form Sent.
- New referral Thompson -> CIG_2026_1026: copy intake_blank.xlsx, populate, Consent_Status = Pending,
  log Referral Received; Physician NPI missing -> "[INTAKE HOLD] CIG_2026_1026 — Physician NPI missing." in
  #intake-alerts + Template 8 to abriggs@buffaloheme.com; do not proceed (no consent form to the patient).
"""

from __future__ import annotations

import os
import re

from ..kit import (Comm, World, append_only, attachments, blank, book_eq, comm_rules, forbid_writes, nh,
                   no_placeholders, norm, num, state_rule, text_of, world)

Y, V, T = "CIG_2026_1024", "CIG_2026_1025", "CIG_2026_1026"
TODAY = "2026-09-28"
ATTORNEY_DOMAIN = "whitfieldlaw.com"

# ---- SOP references (section, paragraph prefix, label) -------------------------------------------
R_LEGAL = ("12.1", "Legal threat or attorney communication", "12.1 Escalation - legal threat / attorney communication")
R_NORESP = ("4.3", "Do not respond to legal threats", "4.3 Prohibited Actions")
R_STOP = ("4.2", "When a validation condition fails", "4.2 Stop Protocol")
R_AUDIT = ("4.1", "Append one row to auditlog.xlsx", "4.1 Audit Logging")
R_APPEND = ("3", "audit_log.xlsx | Global audit trail", "3 File System Structure (audit_log append-only)")
R_TEMPL = ("3", "Template files | Blank form masters", "3 File System Structure (templates)")
R_JC = ("3", "jcodes.xlsx | J-codes", "3 File System Structure (jcodes read-only)")
R_ID = ("3", "infusion_duration.xlsx | Estimated", "3 File System Structure (infusion_duration read-only)")
R_COPY = ("6.1", "Copy intake_blank.xlsx", "6.1 Case Setup")
R_POP = ("6.1", "Populate intake.xlsx from the referral", "6.1 Case Setup")
R_PAT = ("6.1", "PatientLastName, First_Name, DOB", "6.1 Case Setup (patient fields)")
R_PHYS = ("6.1", "PhysicianName, PhysicianNPI", "6.1 Case Setup (physician fields)")
R_DX = ("6.1", "Diagnosis_ICD10 | Diagnosis field", "6.1 Case Setup (diagnosis)")
R_DRUG = ("6.1", "DrugName, DrugDoseGrams", "6.1 Case Setup (drug)")
R_INS = ("6.1", "PrimaryInsuranceName, MemberID", "6.1 Case Setup (insurance)")
R_CONTRA = ("6.1", "Contraindications | Allergies", "6.1 Case Setup (contraindications)")
R_PEND = ("6.1", "Consent_Status | Set to: Pending", "6.1 Case Setup (Consent_Status)")
R_NPI = ("6.1", "If Physician_NPI is blank after referral entry", "6.1 Physician NPI missing")
R_RR = ("6.1", "Log to auditlog.xlsx: Action = Referral Received", "6.1 Case Setup (audit)")
R_CASEID = ("4.5", "CASEID: CIGyyyy####", "4.5 Formatting (CASEID)")
R_CONSENT = ("6.2", "When patient is reached", "6.2 Patient Contact (consent form)")
R_BVS = ("6.2", "Assign BVS.", "6.2 Patient Contact (BVS assignment)")
R_NOBV = ("6.2", "If BVS attempts BV", "6.2 Patient Contact (consent missing)")
R_BVSLOG = ("6.2", "Log to audit_log.xlsx: Action = BVS Assigned", "6.2 Patient Contact (audit)")
R_T4 = ("6", "TO: [Patient_First_Name] [Patient_Last_Name]", "Template 4 (Consent Form email)")
R_T8 = ("6", "DATE: [today] TO: Dr. [Physician_Name]", "Template 8 (Incomplete Referral email)")
R_T8L = ("6", "[List missing fields", "Template 8 (missing fields)")
R_BILL = ("4.3", "Do not bill any IVIG drug J-code", "4.3 Prohibited Actions (billing)")

CHECKPOINTS = ("referral received", "bvs assigned", "bv complete", "pa submitted", "pa approved", "pa denied",
               "visit note signed", "claim submitted", "appeal submitted", "out-of-scope access")
SEED_1024 = {"intake_CIG_2026_1024.xlsx", "signed_consent_form_yellen.pdf"}


def crx(case: str) -> str:
    return case.replace("_", "_?")


# ---- message helpers -------------------------------------------------------------------------------

def _seed_sender(w: World, a) -> str:
    eid = str(a.args.get("email_id") or a.args.get("message_id") or "")
    e = next((e for e in w.seed_emails if str(e.get("email_id")) == eid), None)
    return norm((e or {}).get("from_addr") or "") if e else ""


def dest(w: World, a) -> set[str]:
    """Recipients of an email call; a reply goes to the sender of the replied-to seed email."""
    out = {x.lower() for x in a.recipients} | {x.lower() for x in a.cc}
    if "reply" in a.tool:
        s = _seed_sender(w, a)
        if s:
            out.add(s)
    return out


def about_yellen(a) -> bool:
    return bool(re.search(rf"yellen|{crx(Y)}|whitfield", text_of(a), re.I))


def fwd_of_attorney(w: World, a) -> bool:
    eid = str(a.args.get("email_id") or a.args.get("message_id") or "")
    e = next((e for e in w.seed_emails if str(e.get("email_id")) == eid), None)
    return e is None or ATTORNEY_DOMAIN in norm(e.get("from_addr"))


def _legal_fwd(w: World, addr: str):
    def about(a) -> bool:
        if a.kind != "email_send" or addr not in dest(w, a):
            return False
        return fwd_of_attorney(w, a) if "forward" in a.tool else about_yellen(a)
    return about


def specs(ctx) -> list[Comm]:
    w = world(ctx)
    consent_att = lambda a: any(re.search(r"consent", f, re.I) for f in attachments(a))
    return [
        Comm("legal_post", "slack_post",
             lambda a: a.kind == "slack_post" and (bool(re.search(r"\[LEGAL\]", a.text))
                                                   or (w.is_channel(a.channel, "compliance") and about_yellen(a))),
             f"[LEGAL] alert for {Y} (attorney records request) in #compliance", [R_LEGAL, R_NORESP],
             channel="compliance",
             body=[(rf"\[LEGAL\]\s*{crx(Y)}", f"the tag \"[LEGAL] {Y}\"")]),
        Comm("legal_fwd_legal", "forward", _legal_fwd(w, "legal@careig.com"),
             "forward the attorney's records request (from rwhitfield@whitfieldlaw.com) to legal@careig.com",
             [R_LEGAL], cc=["legal@careig.com"], exact_to=False),
        Comm("legal_fwd_ops", "forward", _legal_fwd(w, "lmurphy@careig.com"),
             "forward the attorney's records request (from rwhitfield@whitfieldlaw.com) to the Director of "
             "Operations, Liam Murphy (lmurphy@careig.com)", [R_LEGAL], cc=["lmurphy@careig.com"], exact_to=False),
        Comm("attorney_reply", "email",
             lambda a: a.kind == "email_send" and any(r.endswith(ATTORNEY_DOMAIN) for r in dest(w, a)),
             "message to the attorney (Whitfield & Associates)", [R_NORESP, R_LEGAL],
             forbidden=f"Do not respond to attorney communications. For {Y} post \"[LEGAL] {Y}\" in #compliance "
                       "and forward the email to legal@careig.com and lmurphy@careig.com instead."),
        Comm("yellen_stop", "email",
             lambda a: (a.kind == "email_send" and "syellen58@aol.com" in dest(w, a))
             or (a.kind in ("slack_post", "slack_dm") and bool(re.search(r"BVS ASSIGNED", a.text, re.I))
                 and about_yellen(a)),
             f"message advancing {Y} (Yellen)", [R_LEGAL],
             forbidden=f"{Y} is on legal STOP (attorney communication received): do not advance the case "
                       "(no BVS assignment, no patient correspondence) until Legal / the Director of Operations "
                       "clear it."),
        Comm("premature_bvs", "slack_post",
             lambda a: a.kind in ("slack_post", "slack_dm") and bool(re.search(r"BVS ASSIGNED", a.text, re.I))
             and bool(re.search(rf"{crx(V)}|{crx(T)}|vasquez|thompson", a.text, re.I)),
             "BVS ASSIGNED post", [R_BVS, R_NOBV],
             forbidden="Consent_Status is not Signed for this case; a BVS is assigned only after the signed "
                       "consent is received."),
        Comm("vasquez_consent", "email",
             lambda a: a.kind == "email_send" and "evasquez79@gmail.com" in dest(w, a)
             and (bool(re.search(r"consent", text_of(a), re.I)) or consent_att(a)),
             f"Template 4 consent-form email for {V} (Elena Vasquez)", [R_CONSENT, R_T4],
             to=["evasquez79@gmail.com"], subject=r"CareIG – Consent Form Required \| Vasquez",
             subject_hint="CareIG — Consent Form Required | Vasquez",
             body=[(r"Dear Elena", "the greeting \"Dear Elena,\""),
                   (r"Dr\.? Nair", "the referring physician \"Dr. Nair\""),
                   (r"\(888\) 555-0147", "the CareIG fax/phone (888) 555-0147")],
             attach=[(r"^(?!.*sign).*consent.*\.pdf$", "the blank consent form (consent_form.pdf)")]),
        Comm("thompson_hold_post", "slack_post",
             lambda a: a.kind == "slack_post" and (bool(re.search(r"INTAKE HOLD", a.text, re.I))
                                                   or (bool(re.search(rf"{crx(T)}|thompson", a.text, re.I))
                                                       and bool(re.search(r"\bNPI\b", a.text)))),
             f"intake hold alert for {T} (Physician NPI missing) in #intake-alerts", [R_NPI, R_STOP],
             channel="intake-alerts",
             body=[(rf"\[INTAKE HOLD\]\s*{crx(T)}\s*[–-]\s*Physician NPI missing",
                    f"the text \"[INTAKE HOLD] {T} — Physician NPI missing.\"")]),
        Comm("thompson_t8", "email",
             lambda a: a.kind == "email_send" and ("abriggs@buffaloheme.com" in dest(w, a)
                                                   or bool(re.search(r"Incomplete Referral", a.subject, re.I))),
             f"Template 8 Incomplete Referral email for {T} (Marcus Thompson) to Dr. Alan Briggs", [R_NPI, R_T8, R_T8L],
             to=["abriggs@buffaloheme.com"], exact_to=False, subject=r"Incomplete Referral \| Thompson",
             subject_hint="Incomplete Referral | Thompson",
             body=[(r"Dear Dr\.? Briggs", "the greeting \"Dear Dr. Briggs,\""),
                   (r"Marcus Thompson", "the patient name Marcus Thompson"),
                   (r"Physician NPI", "the missing field \"Physician NPI\"")]),
        Comm("thompson_consent", "email",
             lambda a: a.kind == "email_send" and "mthompson65@yahoo.com" in dest(w, a)
             and (consent_att(a) or bool(re.search(r"Consent Form Required", a.subject, re.I))),
             f"consent form to Marcus Thompson ({T})", [R_NPI],
             forbidden=f"{T} is on INTAKE HOLD (Physician NPI missing): SOP 6.1 says do not proceed - do not "
                       "send the consent form until the physician supplies the NPI."),
    ]


# ---- workbook helpers (intake files are label/value forms) ------------------------------------------

def _find(grid: list[list[str]], label: str) -> tuple[int, int] | None:
    want = norm(label)
    for i, row in enumerate(grid):
        for j, c in enumerate(row):
            if norm(c) == want:
                return i, j
    return None


def below(grid, label: str, n: int = 1) -> list[str]:
    pos = _find(grid, label)
    if not pos:
        return []
    i, j = pos
    return [nh(grid[k][j]) if j < len(grid[k]) else "" for k in range(i + 1, min(i + 1 + n, len(grid)))]


def right(grid, label: str) -> str:
    pos = _find(grid, label)
    if not pos:
        return ""
    i, j = pos
    return next((nh(c) for c in grid[i][j + 1:] if not blank(c)), "")


def cell(grid, label: str) -> str:
    # not kit.blank(): the literal text "None" is a real value here (Contraindications = None)
    v = below(grid, label)
    return v[0] if v else ""


def contact_log(grid) -> list[str]:
    return [v for v in below(grid, "Contact_Attempt_Log", 6) if not blank(v)]


# ---- completion checks --------------------------------------------------------------------------------

def audit_rows(w: World) -> list[dict]:
    return w.new_rows(r"audit_log", r"^CASE_ID$")


def is_case(v, case: str) -> bool:
    return bool(re.fullmatch(crx(case), nh(v), re.I))


def audit_referral(ctx):
    w = world(ctx)
    rows = [r for r in audit_rows(w) if is_case(w.col(r, r"^CASE_ID$"), T)
            and norm(w.col(r, r"^Action$")) == "referral received"]
    want = (f"Date_Time \"{TODAY} h:mm AM/PM\" | CASE_ID \"{T}\" | Action \"Referral Received\" | File_Updated "
            f"\"intake_{T}.xlsx\" | Field_Updated blank | New_Value blank | Staff_User \"Mia Hamilton\" | Result")
    if not rows:
        yield False, f"audit_log.xlsx has no Referral Received row for the new case {T}. Append: {want}.", \
            [R_RR, R_AUDIT, R_CASEID]
        return
    r = rows[-1]
    probs = []
    if not blank(w.col(r, r"^Field_Updated$")) or not blank(w.col(r, r"^New_Value$")):
        probs.append("leave Field_Updated and New_Value blank")
    if not re.search(rf"intake_{crx(T)}", w.col(r, r"^File_Updated$"), re.I):
        probs.append(f"File_Updated must be intake_{T}.xlsx")
    if not w.col(r, r"^Date_Time$").startswith(TODAY):
        probs.append(f"Date_Time must be today ({TODAY} h:mm AM/PM)")
    if "hamilton" not in norm(w.col(r, r"^Staff_User$")):
        probs.append("Staff_User must be Mia Hamilton")
    yield not probs, f"audit_log.xlsx Referral Received row for {T} (row {r['__row__']}): " + "; ".join(probs) + \
        f". Expected: {want}.", [R_RR, R_AUDIT]


def audit_scope(ctx):
    """New SUCCESS rows: only the SOP checkpoint that actually happens today (Referral Received for the new case)."""
    w = world(ctx)
    for r in audit_rows(w):
        if not norm(w.col(r, r"^Result$")).startswith("success"):
            continue
        case, action = w.col(r, r"^CASE_ID$"), w.col(r, r"^Action$")
        tag = f"audit_log.xlsx row {r['__row__']} ({case} | {action} | SUCCESS)"
        if is_case(case, Y):
            yield False, f"{tag}: {Y} is on legal STOP - no workflow step may be logged as done for it. " \
                         "Remove the row (a STOP note with Result = STOP is allowed).", [R_LEGAL]
        elif not any(norm(action).startswith(c) for c in CHECKPOINTS):
            yield False, f"{tag}: \"{action}\" is not an SOP audit checkpoint - only log the checkpoints each " \
                         "section calls out (today: Referral Received for the new case). Remove the row, or use " \
                         "Result = STOP if it records a hold.", [R_AUDIT]
        elif not (norm(action) == "referral received" and is_case(case, T)):
            yield False, f"{tag}: this checkpoint did not happen today (Referral Received is already logged for " \
                         f"{Y}/{V}; no BVS can be assigned without signed consent). Remove the row.", \
                [R_AUDIT, R_BVSLOG, R_NOBV]


def case_1024(ctx):
    w = world(ctx)
    ok = book_eq(w.current.get("intake_CIG_2026_1024.xlsx"), w.initial.get("intake_CIG_2026_1024.xlsx"))
    yield ok, f"intake_{Y}.xlsx was modified. {Y} is on legal STOP (attorney communication): do not modify any " \
              "file related to the case - restore it exactly as it was.", [R_LEGAL]
    files = {os.path.basename(f): f for f in w.files()}
    extra = sorted(f for f in files if re.search(r"1024|yellen", f, re.I) and f not in SEED_1024)
    yield not extra, f"New file(s) for {Y} were created ({', '.join(extra)}). The case is on legal STOP - do " \
                     "not save/rename case documents; remove them.", [R_LEGAL]
    yield "signed_consent_form_yellen.pdf" in files, \
        "signed_consent_form_yellen.pdf is no longer in the workspace - restore it unchanged (legal STOP).", [R_LEGAL]


def case_1025(ctx):
    w = world(ctx)
    g = w.sheet(r"intake_CIG_2026_1025\.xlsx$")
    g0 = w.sheet(r"intake_CIG_2026_1025\.xlsx$", which="initial")
    status = cell(g, "Consent_Status")
    yield norm(status) == "form sent", f"intake_{V}.xlsx Consent_Status is \"{status}\" - after emailing the " \
        "consent form set it to \"Form Sent\" (cell under Consent_Status).", [R_CONSENT]
    log, log0 = contact_log(g), contact_log(g0)
    lost = [e for e in log0 if e not in log]
    yield not lost, f"intake_{V}.xlsx Contact_Attempt_Log entries were changed/removed ({lost}); keep them and " \
                    "add the new entry below.", [R_CONSENT]
    new = [e for e in log if e not in log0]
    yield any(TODAY in e and re.search(r"\bemail\b", e, re.I) for e in new), \
        f"intake_{V}.xlsx Contact_Attempt_Log has no entry for the consent email - add \"{TODAY} h:mm AM — Email\" " \
        "in the next empty Contact_Attempt_Log row.", [R_CONSENT]
    bvs = cell(g, "BVS_Assigned")
    yield blank(bvs), f"intake_{V}.xlsx BVS_Assigned is \"{bvs}\" but consent is not signed - leave it blank.", \
        [R_BVS, R_NOBV]


def _digits(s) -> str:
    return re.sub(r"\D", "", str(s or ""))


def case_1026(ctx):
    w = world(ctx)
    name, g = w.book(rf"(^|/)intake_{crx(T)}\.xlsx$")
    if not name:
        yield False, f"No intake file for the new referral (Marcus Thompson). Copy intake_blank.xlsx to " \
                     f"intake_{T}.xlsx (CASE_ID {T}) and populate it from the referral; leave Physician_NPI blank " \
                     "(the referral has no NPI) and set Consent_Status = Pending.", [R_COPY, R_POP, R_CASEID]
        return
    g = next(iter(g.values()))
    f = f"intake_{T}.xlsx"
    addr = " ".join(below(g, "Patient_Address", 2))
    contact = " ".join(below(g, "Patient_Phone | Patient_Email", 2))
    dob = right(g, "DOB:")
    npi = cell(g, "Physician_NPI")
    dose = re.sub(r"\s*g(rams?)?\s*$", "", cell(g, "Drug_Dose_Grams"), flags=re.I)
    checks = [
        (norm(cell(g, "CASE_ID")) == norm(T), f"CASE_ID = {T}", R_CASEID),
        (norm(cell(g, "Patient_Last_Name, Patient_First_Name")) == "thompson, marcus",
         "Patient_Last_Name, Patient_First_Name = Thompson, Marcus", R_PAT),
        ("88 oakdale ave" in norm(addr) and "buffalo, ny 14216" in norm(addr),
         "Patient_Address = 88 Oakdale Ave / Buffalo, NY 14216", R_PAT),
        ("(716) 482-9031" in contact and "mthompson65@yahoo.com" in norm(contact),
         "Patient_Phone = (716) 482-9031 and Patient_Email = mthompson65@yahoo.com", R_PAT),
        ("1965-03-22" in dob or "03/22/1965" in dob, "DOB = 1965-03-22", R_PAT),
        ("alan briggs" in norm(cell(g, "Physician_Name")), "Physician_Name = Alan Briggs", R_PHYS),
        (not re.search(r"\d", npi) and norm(npi) != "npi",
         "Physician_NPI blank (the referral gives no NPI - do not enter \"NPI\" or a number)", R_NPI),
        (norm(cell(g, "Physician_Email")) == "abriggs@buffaloheme.com", "Physician_Email = abriggs@buffaloheme.com",
         R_PHYS),
        (norm(cell(g, "Diagnosis_ICD10")) == "d80.1", "Diagnosis_ICD10 = D80.1", R_DX),
        ("empire bluecross ppo" in norm(cell(g, "Primary_Insurance_Name")),
         "Primary_Insurance_Name = Empire BlueCross PPO", R_INS),
        (norm(cell(g, "Primary_Member_ID")) == "ebc-441987320", "Primary_Member_ID = EBC-441987320", R_INS),
        (norm(cell(g, "Group_Number")) == "grp-7815", "Group_Number = GRP-7815", R_INS),
        (cell(g, "Primary_Payer_Phone") == "(800) 553-9603", "Primary_Payer_Phone = (800) 553-9603", R_INS),
        ("privigen" in norm(cell(g, "Drug_Name")), "Drug_Name = Privigen 10%", R_DRUG),
        (num(dose) == 25, "Drug_Dose_Grams = 25g", R_DRUG),
        (bool(re.search(r"3\s*-?\s*weeks?|q3w", cell(g, "Drug_Frequency"), re.I)), "Drug_Frequency = every 3 weeks",
         R_DRUG),
        (bool(re.search(r"none|no known", cell(g, "Contraindications"), re.I)), "Contraindications = None",
         R_CONTRA),
        (norm(cell(g, "Consent_Status")) == "pending", "Consent_Status = Pending (case is on INTAKE HOLD)", R_PEND),
        (blank(cell(g, "BVS_Assigned")), "BVS_Assigned blank (no signed consent)", R_BVS),
    ]
    for ok, want, ref in checks:
        yield ok, f"{f}: expected {want}.", [ref]


def no_downstream(ctx):
    w = world(ctx)
    bad = [b for b in w.created_books()
           if re.match(r"(benefits|auth|clinical|visit_?note|claim|appeals?_?log|denial)", os.path.basename(b), re.I)]
    yield not bad, f"Created {', '.join(bad)} - no case may go past intake today ({Y} legal STOP, {V} consent not " \
                   f"signed, {T} INTAKE HOLD). Remove the file(s).", [R_NOBV, R_LEGAL, R_NPI, R_BILL]


def templates_unchanged(ctx):
    w = world(ctx)
    for f, ref in (("intake_blank.xlsx", R_TEMPL), ("benefits_blank.xlsx", R_TEMPL), ("jcodes.xlsx", R_JC),
                   ("infusion_duration.xlsx", R_ID)):
        if f in w.initial:
            yield book_eq(w.current.get(f), w.initial[f]), f"{f} was modified - it must stay unchanged " \
                "(templates are copied, never edited in place; reference tables are read-only). Restore it.", [ref]


RULES = (
    comm_rules("comms", specs)
    + no_placeholders([R_T4, R_T8], literal=["[LEGAL]", "[INTAKE HOLD]"])
    + forbid_writes("case1024.no_writes", r"1024|yellen",
                    f"{Y} is on legal STOP (attorney communication) - do not modify any file related to the case.",
                    [R_LEGAL])
    + forbid_writes("files.read_only", r"^(intake_blank|benefits_blank|jcodes|infusion_duration)\.xlsx$|^consent_form\.pdf$",
                    "templates are copied before use, never edited in place; jcodes/infusion_duration are read-only.",
                    [R_TEMPL, R_JC, R_ID])
    + append_only("audit.append_only", r"audit_log", r"^CASE_ID$", "audit_log.xlsx", [R_APPEND])
    + state_rule("audit.referral_1026", audit_referral, "Append the audit row exactly as described.")
    + state_rule("audit.checkpoints_only", audit_scope, "Remove the listed audit row(s).")
    + state_rule("case1024.untouched", case_1024, "Undo the change; the case stays on legal STOP.")
    + state_rule("case1025.consent_sent", case_1025, "Update intake_CIG_2026_1025.xlsx as listed.")
    + state_rule("case1026.intake", case_1026, "Fix intake_CIG_2026_1026.xlsx as listed.")
    + state_rule("files.no_downstream", no_downstream, "Remove the premature workflow file(s).")
    + state_rule("files.templates_unchanged", templates_unchanged, "Restore the file from its original content.")
)
