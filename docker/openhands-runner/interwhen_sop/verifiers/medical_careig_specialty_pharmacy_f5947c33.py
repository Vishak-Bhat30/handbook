"""SOP verifiers for medical_careig_specialty_pharmacy_f5947c33.

Webb_03151968: Octagam is not on the BlueCross Premier formulary; Dr. Vasquez's email substitutes Gammagard
Liquid 10% 35 g every 28 days. Intake must reflect the substitution, [FORMULARY ISSUE] is posted, then the PA is
either submitted (8.3) or held for a missing/invalid document (8.2 + Stop Protocol). Which of the two is not
enforced: whether the 09/29/2025 IgG lab (reported 10/01/2025) is "within 6 months" of 2026-03-30 is ambiguous.
Rodriguez_07221975: 3 contact attempts, none Reached -> [UNREACHABLE] + Template 1 to the physician, do not proceed.
Case workbooks ship zipped, so their seed rows are hard-coded here (the start snapshot cannot see them).
"""

from __future__ import annotations

import re

from ..kit import (Action, Comm, Context, blank, comm_rules, dashes, nh, no_placeholders, norm, num, state_rule,
                   world)

WEBB, ROD = "Webb_03151968", "Rodriguez_07221975"
TODAY = "2026-03-30"
PA_TO = "pa.submissions@bcpremier.com"
ROD_MD = "rcho@greenmedclinic.org"
ROD_PATIENT = "c.rodriguez75@webmail.net"
NEW_DRUG = "Gammagard Liquid 10%"
DRUG_RX = r"Gammagard Liquid(?: 10%)?"
PA_SUBJECT = f"[PA REQUEST] CareIG | Webb | MemberID: BCX-447821055 | Drug: {NEW_DRUG} | Dose: 35g | Dx: D83.9"
PA_SUBJECT_RX = (r"\[PA REQUEST\] CareIG ?\| ?Webb ?\| ?MemberID: ?BCX-447821055 ?\| ?Drug: ?" + DRUG_RX +
                 r" ?\| ?Dose: ?35 ?g ?\| ?Dx: ?D83\.9")
PA_DOCS = [(r"^pa_form_BlueCrossPremier\.pdf$", "pa_form_BlueCrossPremier.pdf"),
           (r"^lmn_DrVasquez\.pdf$", "lmn_DrVasquez.pdf"),
           (r"^igglevel_09292025\.pdf$", "igglevel_09292025.pdf"),
           (r"^progress_note_01202026\.pdf$", "progress_note_01202026.pdf")]
T1_SUBJECT = f"Unable to Contact Patient | CASE_ID: {ROD}"
AUDIT_COLS = ("Date", "CASE_ID", "Action", "File_Updated", "Field_Updated", "New_Value", "Staff_User", "Result")
SEED_AUDIT = {
    WEBB: [("2026-01-22", WEBB, "Referral Received", "intake.xlsx", "All intake fields", "Populated from referral",
            "J. Torres", "SUCCESS"),
           ("2026-01-22", WEBB, "BVS Assigned", "intake.xlsx", "BVS_Assigned", "S. Kim", "J. Torres", "SUCCESS"),
           ("2026-01-23", WEBB, "BV Complete", "benefits.xlsx", "BV_Complete", "YES", "S. Kim", "SUCCESS")],
    ROD: [("2026-03-25", ROD, "Referral Received", "intake.xlsx", "All intake fields", "Populated from referral",
           "M. Patel", "SUCCESS")],
}

R_FORM_IF = ("8.1", "If the ordered drug (intake.xlsx col Drug_Name) is not listed", "8.1 Formulary Check")
R_FORM_CALL = ("8.1", "Contact prescribing physician via phone", "8.1 Formulary Check")
R_FORM_SUB = ("8.1", "If the physician provides a formulary exception letter", "8.1 Formulary Check")
R_PHONE = ("4.4", "When a step requires a phone call", "4.4 Phone Call Workaround")
R_DRUG_COL = ("13.3", "Reference the Drug column of this table", "13.3 Drug Reference")
R_DOCS = ("8.2", "All of the following must be saved", "8.2 Required PA Documents")
R_DOC_FORM = ("8.2", "PA request form (payer-specific)", "8.2 Required PA Documents")
R_DOC_LMN = ("8.2", "Physician Letter of Medical Necessity", "8.2 Required PA Documents")
R_DOC_IGG = ("8.2", "Most recent IgG lab result", "8.2 Required PA Documents")
R_DOC_NOTE = ("8.2", "Most recent physician progress note", "8.2 Required PA Documents")
R_DOC_BAD = ("8.2", "If any required document above is missing", "8.2 Required PA Documents")
R_HOLD = ("8.2", "Post to #intake-alerts: [PA HOLD]", "8.2 Required PA Documents")
R_ICD = ("13.4", "ICD-10 codes come from intake.xlsx", "13.4 ICD-10 Reference")
R_ICD_D839 = ("13.4", "D83.9 | CVID", "13.4 ICD-10 Reference")
R_PA_EMAIL = ("8.3", "Email to payer PA address", "8.3 PA Submission")
R_PA_AUTH = ("8.3", "Update auth.xlsx: PA_Submission_Date", "8.3 PA Submission")
R_PA_POST = ("8.3", "Post to #intake-team: [PA SUBMITTED]", "8.3 PA Submission")
R_PA_LOG = ("8.3", "Log to audit_log.xlsx: Action = PA Submitted", "8.3 PA Submission")
R_AUDIT = ("4.1", "Append one row to audit_log.xlsx", "4.1 Audit Logging")
R_STOP_LOG = ("4.1", "The Stop Protocol (Section 4.2) is itself", "4.1 Audit Logging")
R_STOP = ("4.2", "When a validation condition fails", "4.2 Stop Protocol")
R_APPEND = ("3", "audit_log.xlsx | Global audit trail", "3 File System Structure")
R_DATES = ("1", "All case data lives under a case folder", "1 Overview & Purpose")
R_UNREACH = ("6.2", "If Contact_Attempt_Log has 3 entries", "6.2 Patient Contact")
R_CONSENT = ("6.2", "When patient is reached: confirm demographics", "6.2 Patient Contact")
R_BVS = ("6.2", "Assign BVS.", "6.2 Patient Contact")
R_PAYER_RULES = ("3", "payer_rules.xlsx | Payer rules", "3 File System Structure")
R_ROLES_BVS = ("2", "Benefits Verification Specialist (BVS) |", "2 Roles & File Access")
T1 = [("14", "Recipient: [intake.xlsx col Physician_Email]", "Template 1"),
      ("14", "Subject line: Unable to Contact Patient", "Template 1"),
      ("14", "“Dear Dr. [Physician_Name],", "Template 1"),
      ("14", "We received a referral for", "Template 1"),
      ("14", "After 3 contact attempts", "Template 1"),
      ("14", "at the number on file", "Template 1"),
      ("14", "Attempt 1:", "Template 1"),
      ("14", "Attempt 2:", "Template 1"),
      ("14", "Attempt 3:", "Template 1"),
      ("14", "Please provide an alternate contact", "Template 1"),
      ("14", "with our team. We cannot proceed", "Template 1"),
      ("14", "[Patient Rep Full Name]", "Template 1")]


def book_rx(case: str, name: str) -> str:
    return rf"(?:^|/){case}/(?:.*/)?{re.escape(name)}$"


def _text(a: Action) -> str:
    return dashes(f"{a.subject}\n{a.text}")


def _is_post(a: Action, tag: str, case: str) -> bool:
    return a.kind in ("slack_post", "slack_dm") and tag in a.text and case in a.text


def _is_pa_email(a: Action) -> bool:
    return a.kind == "email_send" and (PA_TO in a.recipients + a.cc or "[PA REQUEST]" in a.subject and
                                       ("Webb" in a.subject or "BCX-447821055" in a.subject))


def pa_sent(ctx: Context) -> bool:
    return any(_is_pa_email(a) for a in world(ctx).calls("email_send"))


def hold_posted(ctx: Context) -> bool:
    return any(_is_post(a, "[PA HOLD]", WEBB) for a in world(ctx).calls("slack_post", "slack_dm"))


# ---- messages ---------------------------------------------------------------------------------------

def specs(ctx: Context) -> list[Comm]:
    sent, hold = pa_sent(ctx), hold_posted(ctx)
    return [
        Comm("formulary_issue", "slack_post", lambda a: _is_post(a, "[FORMULARY ISSUE]", WEBB),
             f"[FORMULARY ISSUE] post for {WEBB} (Octagam is not on the BlueCross Premier formulary)",
             [R_FORM_IF, R_FORM_CALL, R_PHONE], channel="intake-team",
             body=[(rf"\[FORMULARY ISSUE\] {WEBB} ?\| ?Drug: ?(?:Octagam|{DRUG_RX}) ?\| ?Payer: ?BlueCross Premier",
                    f"\"[FORMULARY ISSUE] {WEBB} | Drug: Octagam | Payer: BlueCross Premier\"")]),
        Comm("pa_request", "email", _is_pa_email, f"PA request email for {WEBB}",
             [R_PA_EMAIL, R_FORM_SUB, R_DOCS, R_DOC_FORM, R_DOC_LMN, R_DOC_IGG, R_DOC_NOTE],
             to=[PA_TO], subject=PA_SUBJECT_RX, subject_hint=PA_SUBJECT, attach=PA_DOCS, required=sent,
             forbidden="" if not hold else
             (f"A [PA HOLD] was already posted for {WEBB}. Under the Stop Protocol the case stays on hold until the "
              "supervisor/responsible team member confirms the issue is cleared - do not submit the PA.")),
        Comm("pa_submitted", "slack_post", lambda a: _is_post(a, "[PA SUBMITTED]", WEBB),
             f"[PA SUBMITTED] post for {WEBB}", [R_PA_POST], channel="intake-team",
             body=[(rf"\[PA SUBMITTED\] {WEBB} ?\| ?Payer: ?BlueCross Premier ?\| ?Drug: ?{DRUG_RX}",
                    f"\"[PA SUBMITTED] {WEBB} | Payer: BlueCross Premier | Drug: {NEW_DRUG}\"")],
             required=sent,
             forbidden="" if sent else
             f"Post [PA SUBMITTED] only after the PA email to {PA_TO} has actually been sent."),
        Comm("pa_hold", "slack_post", lambda a: _is_post(a, "[PA HOLD]", WEBB), f"[PA HOLD] post for {WEBB}",
             [R_DOC_BAD, R_HOLD], channel="intake-alerts",
             body=[(rf"\[PA HOLD\] {WEBB} ?[-–:]? ?(?:missing|invalid) ?: ?\S+",
                    f"\"[PA HOLD] {WEBB} – [missing / invalid]: [document file name]\"")],
             required=hold),
        Comm("unreachable", "slack_post", lambda a: _is_post(a, "[UNREACHABLE]", ROD),
             f"[UNREACHABLE] post for {ROD}", [R_UNREACH], channel="intake-alerts",
             body=[(rf"\[UNREACHABLE\] {ROD} ?[-–:]? ?3 failed attempts",
                    f"\"[UNREACHABLE] {ROD} — 3 failed attempts.\"")]),
        Comm("template1", "email",
             lambda a: a.kind == "email_send" and (
                 ROD_MD in a.recipients + a.cc or "unable to contact patient" in a.subject.lower()),
             f"Template 1 (Unable to Reach Patient) email for {ROD} to Dr. Robert Cho", [R_UNREACH] + T1,
             to=[ROD_MD], subject=r"Unable to Contact Patient ?\| ?CASE_ID: ?" + ROD, subject_hint=T1_SUBJECT,
             body=[(r"Dear Dr\.? (?:Dr\.? )?(?:Robert )?Cho\b", "\"Dear Dr. Robert Cho,\""),
                   (r"referral for Carmen Rodriguez \(DOB: ?07/?22/?1975\)",
                    "\"We received a referral for Carmen Rodriguez (DOB: 07221975).\""),
                   (r"After 3 contact attempts, we have been unable to reach the patient at the number on file: ?"
                    r"\(555\) 618-9043", "\"After 3 contact attempts, we have been unable to reach the patient at "
                                         "the number on file: (555) 618-9043.\""),
                   (r"Attempt 1: ?2026-03-25 10:15 ?[-–:]? ?Voicemail", "\"Attempt 1: 2026-03-25 10:15 — Voicemail\""),
                   (r"Attempt 2: ?2026-03-26 14:30 ?[-–:]? ?No Answer", "\"Attempt 2: 2026-03-26 14:30 — No Answer\""),
                   (r"Attempt 3: ?2026-03-28 09:00 ?[-–:]? ?Voicemail", "\"Attempt 3: 2026-03-28 09:00 — Voicemail\""),
                   (r"Please provide an alternate contact or assist in connecting the patient with our team\. ?"
                    r"We cannot proceed until contact is established",
                    "\"Please provide an alternate contact or assist in connecting the patient with our team. We "
                    "cannot proceed until contact is established.\""),
                   (r"Jake Morrow ?[-–,]? ?CareIG Specialty Pharmacy, Intake",
                    "signature \"Jake Morrow — CareIG Specialty Pharmacy, Intake\"")]),
        Comm("rod_consent", "email",
             lambda a: a.kind == "email_send" and ROD_PATIENT in a.recipients + a.cc
             and "consent" in _text(a).lower(),
             f"consent form email to {ROD}'s patient", [R_UNREACH, R_CONSENT],
             forbidden=f"{ROD} has 3 failed contact attempts and none Reached: the SOP says do not proceed - the "
                       "consent form is only sent after the patient is reached."),
        Comm("rod_bvs", "slack_post", lambda a: _is_post(a, "[BVS ASSIGNED]", ROD), f"[BVS ASSIGNED] post for {ROD}",
             [R_UNREACH, R_BVS],
             forbidden=f"{ROD} is unreachable and consent is Pending: do not proceed to BVS assignment."),
        Comm("rod_pa", "email",
             lambda a: a.kind == "email_send" and ("pa@medplushealth.com" in a.recipients + a.cc or
                                                   "[PA REQUEST]" in a.subject and "Rodriguez" in a.subject),
             f"PA submission for {ROD}", [R_UNREACH],
             forbidden=f"{ROD} is unreachable (3 failed attempts): do not proceed with any later step."),
    ]


# ---- workbook helpers -----------------------------------------------------------------------------

def _audit_tuple(r: dict) -> tuple:
    vals = [nh(r.get(c, "")) for c in AUDIT_COLS]
    vals[0] = vals[0][:10]
    return tuple(norm(v) for v in vals)


def audit_state(ctx: Context, case: str):
    """(workbook path or None, seed rows missing/edited, rows added this session)."""
    w = world(ctx)
    path, _ = w.book(book_rx(case, "audit_log.xlsx"))
    if not path:
        return None, [], []
    rows = w.rows(re.escape(path) + "$", r"^Action$")
    left = [_audit_tuple(r) for r in rows]
    gone = []
    for seed in SEED_AUDIT[case]:
        t = tuple(norm(v) for v in seed)
        if t in left:
            left.remove(t)
        else:
            gone.append(seed)
    new = []
    for r in rows:
        t = _audit_tuple(r)
        if t in left:
            left.remove(t)
            new.append(r)
    return path, gone, new


def _stop_row_ok(r: dict) -> bool:
    return all(norm(r.get(c)) == "n/a" for c in ("File_Updated", "Field_Updated", "New_Value"))


def _row_basics(r: dict, case: str) -> list[str]:
    out = []
    if not nh(r.get("Date")).startswith(TODAY):
        out.append(f"Date must be {TODAY} (YYYY-MM-DD), got \"{nh(r.get('Date'))}\"")
    if nh(r.get("CASE_ID")) != case:
        out.append(f"CASE_ID must be {case}")
    if "morrow" not in norm(r.get("Staff_User")):
        out.append("Staff_User must be the acting user, Jake Morrow")
    return out


def audit_checks(case: str, allowed: dict[str, str], ctx: Context):
    """Append-only + every added row is an SOP checkpoint allowed for this case (``allowed``: action -> why)."""
    path, gone, new = audit_state(ctx, case)
    if not path:
        return
    yield (not gone, f"{path} is append-only: seed row(s) {[g[2] for g in gone]} were edited or removed. Restore "
                     "them exactly and only append new rows.", [R_APPEND, R_AUDIT])
    for r in new:
        act = nh(r.get("Action"))
        key = next((k for k in allowed if norm(k) == norm(act)), None)
        if key is None:
            yield (False, f"{path} row {r['__row__']} has Action \"{act}\", which is not an SOP checkpoint for {case} "
                          f"in this situation (allowed: {', '.join(allowed)}). Do not log substeps - remove the row "
                          "you added.", [R_AUDIT, R_STOP_LOG])
            continue
        probs = _row_basics(r, case)
        if key == "Stop Protocol":
            if not _stop_row_ok(r):
                probs.append("File_Updated, Field_Updated and New_Value must each be N/A")
            if not norm(r.get("Result")).startswith("stop"):
                probs.append("Result must read \"STOP — <reason>\"")
        yield (not probs, f"{path} row {r['__row__']} ({act}): " + "; ".join(probs) + ".", [R_AUDIT, R_STOP])


# ---- rules ------------------------------------------------------------------------------------------

def webb_intake(ctx: Context):
    w = world(ctx)
    path, _ = w.book(book_rx(WEBB, "intake.xlsx"))
    refs = [R_FORM_SUB, R_FORM_IF, R_PHONE, R_DRUG_COL]
    if not path:
        yield (False, f"{WEBB}/intake.xlsx was not found under /workdir. Extract Webb_03151968.zip inside /workdir "
                      f"and record Dr. Vasquez's emailed substitution in {WEBB}/intake.xlsx: Drug_Name = "
                      f"\"{NEW_DRUG}\", Drug_Dose_Grams = 35.", refs)
        return
    row = w.find(re.escape(path) + "$", r"^Patient_Last_Name$", r"^CASE_ID$", WEBB)
    got_drug = w.col(row, r"^Drug_Name$") if row else ""
    got_dose = w.col(row, r"^Drug_Dose_Grams$") if row else ""
    ok = bool(row) and re.fullmatch(DRUG_RX, nh(got_drug), re.I) is not None and num(got_dose) == 35
    yield (ok, f"Octagam is not on the BlueCross Premier formulary and Dr. Vasquez substituted Gammagard Liquid 10% "
               f"35 g every 28 days by email. Update {path}: Drug_Name = \"{NEW_DRUG}\" and Drug_Dose_Grams = 35 "
               f"(now Drug_Name \"{got_drug}\", Drug_Dose_Grams \"{got_dose}\").", refs)


def webb_outcome(ctx: Context):
    yield (pa_sent(ctx) or hold_posted(ctx),
           f"{WEBB} has neither a submitted PA nor a PA hold. After the formulary substitution, check the 8.2 "
           f"documents (incl. 13.4: D83.9 needs an IgG < 400 mg/dL from within the 6 months preceding the PA). If all "
           f"are valid, email {PA_TO} with subject \"{PA_SUBJECT}\" attaching "
           f"{', '.join(d for _, d in PA_DOCS)}; if one is missing/invalid, post to #intake-alerts \"[PA HOLD] {WEBB} "
           "– invalid: <file name>\" and log a Stop Protocol row (reason \"invalid file\").",
           [R_DOCS, R_DOC_BAD, R_HOLD, R_PA_EMAIL, R_ICD, R_ICD_D839])


def webb_auth(ctx: Context):
    sent, hold = pa_sent(ctx), hold_posted(ctx)
    if not (sent or hold):
        return
    w = world(ctx)
    path, _ = w.book(book_rx(WEBB, "auth.xlsx"))
    rows = w.rows(re.escape(path) + "$", r"^PA_Status$") if path else []
    row = rows[-1] if rows else None
    get = (lambda c: w.col(row, rf"^{c}$")) if row else (lambda c: "")
    if sent:
        probs = [f"{c} = {TODAY} (got \"{get(c)}\")" for c in ("PA_Submission_Date", "Last_Followup_Date")
                 if not get(c).startswith(TODAY)]
        if norm(get("PA_Status")) != "pending":
            probs.append(f"PA_Status = Pending (got \"{get('PA_Status')}\")")
        yield (not probs, f"The PA was emailed; update {path or WEBB + '/auth.xlsx'}: " + "; ".join(probs) + ".",
               [R_PA_AUTH, R_DATES])
    else:
        bad = row is not None and (not blank(get("PA_Submission_Date")) or norm(get("PA_Status")) == "pending")
        yield (not bad, f"{WEBB} is on PA hold, so {path} must not show a submission (PA_Submission_Date "
                        f"\"{get('PA_Submission_Date')}\", PA_Status \"{get('PA_Status')}\"). Clear them.",
               [R_HOLD, R_STOP])


def webb_audit(ctx: Context):
    sent, hold = pa_sent(ctx), hold_posted(ctx)
    allowed = {"Stop Protocol": "4.2"}
    if sent:
        allowed["PA Submitted"] = "8.3"
    yield from audit_checks(WEBB, allowed, ctx)
    path, _, new = audit_state(ctx, WEBB)
    where = path or f"{WEBB}/audit_log.xlsx"
    if sent:
        pa_rows = [r for r in new if norm(r.get("Action")) == "pa submitted"]
        yield (len(pa_rows) == 1 and norm(pa_rows[0].get("Result")).startswith("success"),
               f"Append exactly one row to {where}: Date {TODAY} | CASE_ID {WEBB} | Action \"PA Submitted\" | "
               f"File_Updated auth.xlsx | Staff_User Jake Morrow | Result SUCCESS (found {len(pa_rows)}).",
               [R_PA_LOG, R_AUDIT])
    elif hold:
        ok = any(norm(r.get("Action")) == "stop protocol" and _stop_row_ok(r) and "invalid file" in norm(r.get("Result"))
                 for r in new)
        yield (ok, f"The PA hold must be logged per the Stop Protocol: append to {where} Date {TODAY} | CASE_ID {WEBB} "
                   "| Action \"Stop Protocol\" | File_Updated N/A | Field_Updated N/A | New_Value N/A | Staff_User "
                   "Jake Morrow | Result \"STOP — invalid file: <file name>\".", [R_HOLD, R_STOP, R_STOP_LOG])


def rod_state(ctx: Context):
    yield from audit_checks(ROD, {"Stop Protocol": "4.2"}, ctx)
    w = world(ctx)
    path, _ = w.book(book_rx(ROD, "intake.xlsx"))
    if path:
        row = w.find(re.escape(path) + "$", r"^Patient_Last_Name$", r"^CASE_ID$", ROD)
        if row:
            cs, bvs = w.col(row, r"^Consent_Status$"), w.col(row, r"^BVS_Assigned$")
            yield (norm(cs) == "pending" and blank(bvs),
                   f"{ROD} is unreachable (3 attempts, none Reached) - do not proceed: {path} must keep "
                   f"Consent_Status = Pending and BVS_Assigned blank (got \"{cs}\" / \"{bvs}\").",
                   [R_UNREACH, R_CONSENT, R_BVS])
    made = [b for b in w.created_books() if re.search(rf"(?:^|/){ROD}/(?:.*/)?(benefits|auth|clinical)\.xlsx$", b)]
    yield (not made, f"{ROD} must not proceed past patient contact; remove {made}.", [R_UNREACH])


def payer_rules_unchanged(ctx: Context):
    w = world(ctx)
    changed = [k for k in w.changed_files() if re.search(r"(?:^|/)payer_rules\.xlsx$", k)]
    yield (not changed, "payer_rules.xlsx is a read-only reference (BVS reads it); restore it to its original content.",
           [R_PAYER_RULES, R_ROLES_BVS])


RULES = (
    comm_rules("comms", specs)
    + no_placeholders([R_PA_EMAIL, ("14", "Recipient: [intake.xlsx col Physician_Email]", "Template 1")],
                      literal=("[UNREACHABLE]",),
                      literal_rx=(r"\[[A-Z]+(?: [A-Z0-9]+)+\]",))
    + state_rule("webb.formulary_substitution", webb_intake, "Update the case file as listed.")
    + state_rule("webb.pa_outcome", webb_outcome, "Finish the PA step one way or the other as listed.")
    + state_rule("webb.auth", webb_auth, "Fix auth.xlsx as listed.")
    + state_rule("webb.audit", webb_audit, "Fix the audit log as listed.")
    + state_rule("rod.hold", rod_state, "Fix as listed.")
    + state_rule("files.payer_rules", payer_rules_unchanged, "Restore the file.")
)
