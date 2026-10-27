"""SOP verifiers for medical_careig_specialty_pharmacy_d3e312a5.

Situation (seed data, today = 04/07/2026): intake.xlsx, benefits.xlsx, clinical.xlsx and audit_log.xlsx of case
Vasquez_03151971 were deleted and must be rebuilt from the referral, call transcripts, consent, mail and Slack.
The case is at "PA submitted, pending" (auth.xlsx). Expected values below are derived from those sources.
"""

from __future__ import annotations

import re

from ..kit import (Comm, Context, comm_rules, no_placeholders, nh, norm, num, state_rule, text_of, world)

CASE = "Vasquez_03151971"
STAFF = "Teresa Rodriguez"
BOOK = {k: rf"(^|/){k}\.xlsx$" for k in ("intake", "benefits", "clinical", "audit_log")}
TEMPLATE_INTAKE = r"(^|/)intake_blank\.xlsx$"

# ---- SOP references (section, paragraph prefix, label) -----------------------------------------
P_CASEID = ("1", "CASE_ID (format: LastName_DOBMMDDYYYY)", "1 CASE_ID")
P_TEMPLATES = ("3", "Template files | Blank form masters", "3 Template files")
P_JCODES = ("3", "jcodes.xlsx | J-codes and nursing codes (read-only)", "3 jcodes.xlsx")
P_ROSTER = ("3", "staff_roster.xlsx | Contains a list", "3 staff_roster.xlsx")
P_SCOPE = ("2", "Any file access outside the above scope", "2 Roles & File Access")
P_FORMAT = ("4", "Unless specified, all dates should be written", "4 Global Rules formats")
P_AUDIT = ("4.1", "Append one row to audit_log.xlsx at each major checkpoint", "4.1 Audit Logging")
P_AUDIT_STOP = ("4.1", "The Stop Protocol (Section 4.2) is itself a checkpoint", "4.1 Audit Logging")
P_COPY_INTAKE = ("6.1", "Copy intake_blank.xlsx to create intake.xlsx", "6.1 Case Setup")
P_POPULATE = ("6.1", "Populate intake.xlsx from the referral document", "6.1 Case Setup")
P_PAT = ("6.1", "Patient_Last_Name, First_Name, DOB", "6.1 patient fields")
P_PHYS = ("6.1", "Physician_Name, Physician_NPI, Physician_Email", "6.1 physician fields")
P_DX = ("6.1", "Diagnosis_ICD10 | Diagnosis field", "6.1 diagnosis")
P_DRUG = ("6.1", "Drug_Name, Drug_Dose_Grams, Drug_Frequency", "6.1 drug fields")
P_INS = ("6.1", "Primary_Insurance_Name, Member_ID, Group_Number", "6.1 insurance fields")
P_CONTRA = ("6.1", "Contraindications | Allergies", "6.1 contraindications")
P_LOG_REFERRAL = ("6.1", "Log to audit_log.xlsx: Action = Referral Received", "6.1 Case Setup")
P_ATTEMPT = ("6.2", "Log each attempt in intake.xlsx col Contact_Attempt_Log", "6.2 Patient Contact")
P_CONSENT_EMAIL = ("6.2", "When patient is reached: confirm demographics", "6.2 Patient Contact")
P_SIGNED = ("6.2", "When signed consent is received", "6.2 Patient Contact")
P_BVS = ("6.2", "Assign BVS. Set intake.xlsx col BVS_Assigned", "6.2 Patient Contact")
P_LOG_BVS = ("6.2", "Log to audit_log.xlsx: Action = BVS Assigned", "6.2 Patient Contact")
P_BV = ("7.1", "BVS calls the payer at intake.xlsx col Primary_Payer_Phone", "7.1 Benefits Verification")
P_BV_COLS = ("7.1", "benefits.xlsx Column | How to Obtain", "7.1 benefits.xlsx columns")
P_BV_HIC = ("7.1", "Home_Infusion_Covered |", "7.1 Home_Infusion_Covered")
P_BV_TYPE = ("7.1", "Benefit_Type |", "7.1 Benefit_Type")
P_BV_PA = ("7.1", "PA_Required, PA_Phone, PA_Submission_Email", "7.1 PA fields")
P_BV_SP = ("7.1", "Specialty_Pharmacy_Requir", "7.1 specialty pharmacy")
P_BV_NET = ("7.1", "CareIG_Network_Status |", "7.1 network status")
P_BV_DED = ("7.1", "Deductible_Individual, Deductible_Met_YTD", "7.1 deductible")
P_BV_OOP = ("7.1", "OOP_Max_Individual, OOP_Max_Met_YTD", "7.1 OOP max")
P_BV_COINS = ("7.1", "Coinsurance_Pct, Copay_Amount", "7.1 coinsurance/copay")
P_BV_PLAN = ("7.1", "Plan_Year_Type |", "7.1 plan year")
P_BV_PAYER = ("7.1", "Payer_Type | Classify", "7.1 payer type")
P_BV_NURS = ("7.1", "Nursing_Code_Pref | Determine from payer_rules.xlsx", "7.1 nursing code")
P_BV_COV = ("7.1", "Coverage_Effective_Date, Coverage_Term_Date", "7.1 coverage dates")
P_BV_CALL = ("7.1", "BV_Call_Date, BV_Rep_Name, BV_Call_Ref_Number", "7.1 BV call")
P_BV_DONE = ("7.1", "BV_Complete | Set YES only after", "7.1 BV_Complete")
P_LOG_BV = ("7.1", "Log to audit_log.xlsx: Action = BV Complete", "7.1 Benefits Verification")
P_SOURCE = ("7.2", "Immediately after BV, write the drug source", "7.2 Drug Source Decision")
P_SOURCE_CAREIG = ("7.2", "CareIG_Network_Status = In-Network AND Specialty_Pharmacy_Required = NO", "7.2 Drug Source")
P_FC_LOG = ("7.3", "Log call in benefits.xlsx col Financial_Counseling_Log", "7.3 Financial Counseling")
P_FORMULARY_POST = ("8.1", "Post to #intake-alerts: [FORMULARY ISSUE]", "8.1 Formulary Check")
P_LOG_FORMULARY = ("8.1", "Log to audit_log.xlsx: Action = Formulary Stop", "8.1 Formulary Check")
P_PA_EMAIL = ("8.3", "Combine all documents into pa_submission_packet", "8.3 PA Submission")
P_PA_POST = ("8.3", "Post to #intake-team: [PA SUBMITTED]", "8.3 PA Submission")
P_LOG_PA = ("8.3", "Log to audit_log.xlsx: Action = PA Submitted", "8.3 PA Submission")
P_PA_DELAY = ("8.4", "If still Pending after 5 days from PA_Submission_Date", "8.4 PA Follow-Up")
P_HANDOFF = ("8.6", "Update clinical.xlsx: Handoff_Status = Received", "8.6 Clinical Handoff")
P_CHECKLIST = ("9.1", "clinical.xlsx Column | Requirement", "9.1 Supply Checklist")
P_SCHEDULE = ("9.2", "Update clinical.xlsx: Visit_Date, Visit_Time, Nurse_Assigned", "9.2 Nurse Scheduling")
P_DRUG_ISSUE = ("12.1", "Wrong drug lot/dose from partner pharmacy", "12.1 Escalation Paths")
P_MONITOR = ("12.2", "The intake supervisor, billing supervisor", "12.2 Workflow Monitoring")
P_TEMPLATE_REF = ("14", "letter_cover_blank.docx | All outbound document transmissions", "14 Appendix A templates")

# ---- expected content --------------------------------------------------------------------------
BEN_HEADERS = ["Home_Infusion_Covered", "Benefit_Type", "PA_Required", "PA_Phone", "PA_Submission_Email",
               "Specialty_Pharmacy_Required", "Specialty_Pharmacy_Name", "CareIG_Network_Status",
               "Deductible_Individual", "Deductible_Met_YTD", "OOP_Max_Individual", "OOP_Max_Met_YTD",
               "Coinsurance_Pct", "Copay_Amount", "Plan_Year_Type", "Payer_Type", "Nursing_Code_Pref",
               "Coverage_Effective_Date", "Coverage_Term_Date", "BV_Call_Date", "BV_Rep_Name", "BV_Call_Ref_Number",
               "BV_Complete", "Financial_Counseling_Log"]
CHECKLIST_HEADERS = ["Drug_Order_Placed", "Drug_Delivery_Confirmed", "Drug_Lot_Number", "Drug_NDC",
                     "NS_500mL_Qty_Ordered", "Filter_Tubing_Ordered", "Benadryl_Available", "Supplies_Other",
                     "Supply_Checklist_Complete"]
CLIN_HEADERS = ["Drug_Source", "Handoff_Status", "PA_Number", "PA_Expiration_Date", *CHECKLIST_HEADERS,
                "Visit_Date", "Visit_Time", "Nurse_Assigned", "Drug_Issue_Notes"]
AUDIT_HEADERS = ["Date/Time", "CASE_ID", "Action", "File_Updated", "Staff_User", "Result"]

AUDIT_ROWS = [  # (Action, File_Updated (None = blank), Result, SOP ref) in chronological order
    ("Referral Received", "intake.xlsx", "SUCCESS", P_LOG_REFERRAL),
    ("BVS Assigned", "intake.xlsx", "SUCCESS", P_LOG_BVS),
    ("BV Complete", "benefits.xlsx", "SUCCESS", P_LOG_BV),
    ("Formulary Stop", None, "STOP", P_LOG_FORMULARY),
    ("PA Submitted", "auth.xlsx", "SUCCESS", P_LOG_PA),
]


def _exact(want: str):
    return lambda v: norm(v) == norm(want)


def _rx(pattern: str):
    return lambda v: bool(re.search(pattern, nh(v), re.I))


def _amount(want: float):
    return lambda v: num(v) is not None and abs(num(v) - want) < 0.006


def _pct(want: float):
    return lambda v: num(v) is not None and (abs(num(v) - want) < 1e-6 or abs(num(v) * 100 - want) < 1e-6)


def _no_copay(v) -> bool:
    return (num(v) is not None and abs(num(v)) < 0.006) or bool(re.fullmatch(r"\$?0(\.00)?|none|n/?a", norm(v)))


# column -> (check, expected text for feedback, ref)
INTAKE = {
    "CASE_ID": (_exact(CASE), CASE, P_CASEID),
    "Patient_Last_Name": (_exact("Vasquez"), "Vasquez", P_PAT),
    "Patient_First_Name": (_exact("Maria Elena"), "Maria Elena", P_PAT),
    "Patient_DOB": (_exact("03/15/1971"), "03/15/1971", P_FORMAT),
    "Patient_Address": (_rx(r"^4821 SW 112th Ave(nue|\.)?,? Miami,? FL,? 33165$"),
                        "4821 SW 112th Avenue, Miami, FL 33165", P_PAT),
    "Patient_Phone": (_exact("(305) 555-4892"), "(305) 555-4892", P_FORMAT),
    "Patient_Email": (_exact("m.vasquez1971@gmail.com"), "m.vasquez1971@gmail.com", P_PAT),
    "Physician_Name": (_rx(r"harrington"), "James T. Harrington (referring physician on the referral)", P_PHYS),
    "Physician_NPI": (_exact("1073541867"), "1073541867", P_PHYS),
    "Physician_Email": (_exact("j.harrington@miamineurology.com"), "j.harrington@miamineurology.com", P_PHYS),
    "Diagnosis_ICD10": (_exact("D83.9"), "D83.9", P_DX),
    "Drug_Name": (_rx(r"^privigen\s*10\s*%$"), "Privigen 10%", P_DRUG),
    "Drug_Dose_Grams": (_rx(r"^35(\.0+)?\s*(g|grams?)?$"), "35", P_DRUG),
    "Drug_Frequency": (_rx(r"4\s*weeks|q\s?4\s?w|28\s*days"), "Every 4 weeks", P_DRUG),
    "Primary_Insurance_Name": (_exact("Aetna PPO"), "Aetna PPO", P_INS),
    "Primary_Member_ID": (_exact("AET847392018"), "AET847392018", P_INS),
    "Primary_Group_Number": (_exact("GRP29341"), "GRP29341", P_INS),
    "Primary_Payer_Phone": (_exact("(800) 555-2940"), "(800) 555-2940", P_INS),
    "Contraindications": (_rx(r"\bNKDA\b|no known (drug )?allerg"),
                          "NKDA. Patient denies history of hyperprolinemia. No prior IVIG adverse reactions.", P_CONTRA),
    "Consent_Status": (_exact("Signed"), "Signed", P_SIGNED),
    "Contact_Attempt_Log": (lambda v: bool(re.search(r"03/30/2026\s+10:22\s*[-–—:|]?\s*Voicemail", v, re.I)
                                           and re.search(r"03/31/2026\s+14:05\s*[-–—:|]?\s*Reached", v, re.I)),
                            "both attempts: 03/30/2026 10:22 — Voicemail and 03/31/2026 14:05 — Reached", P_ATTEMPT),
    "BVS_Assigned": (_exact("YES"), "YES", P_BVS),
    "Financial_Hardship": (lambda v: norm(v) != "yes", "not YES (patient reported no hardship on the 04/03 call)",
                           P_FC_LOG),
}

BENEFITS = {
    "Home_Infusion_Covered": (_exact("YES"), "YES", P_BV_HIC),
    "Benefit_Type": (_rx(r"^medical( benefit)?$"), "Medical", P_BV_TYPE),
    "PA_Required": (_exact("YES"), "YES", P_BV_PA),
    "PA_Phone": (_exact("(800) 555-7221"), "(800) 555-7221", P_BV_PA),
    "PA_Submission_Email": (_exact("pa@aetna.com"), "pa@aetna.com", P_BV_PA),
    "Specialty_Pharmacy_Required": (_exact("NO"), "NO", P_BV_SP),
    "CareIG_Network_Status": (_rx(r"^in[- ]?network$"), "In-Network", P_BV_NET),
    "Deductible_Individual": (_amount(1500), "$1,500", P_BV_DED),
    "Deductible_Met_YTD": (_amount(750), "$750", P_BV_DED),
    "OOP_Max_Individual": (_amount(5000), "$5,000", P_BV_OOP),
    "OOP_Max_Met_YTD": (_amount(750), "$750", P_BV_OOP),
    "Coinsurance_Pct": (_pct(20), "20%", P_BV_COINS),
    "Copay_Amount": (_no_copay, "$0 (no per-visit copay)", P_BV_COINS),
    "Plan_Year_Type": (_rx(r"^calendar( year)?$"), "Calendar", P_BV_PLAN),
    "Payer_Type": (_exact("Commercial PPO"), "Commercial PPO", P_BV_PAYER),
    "Nursing_Code_Pref": (_amount(99600), "99600", P_BV_NURS),
    "Coverage_Effective_Date": (_exact("01/01/2026"), "01/01/2026", P_BV_COV),
    "Coverage_Term_Date": (_exact("12/31/2026"), "12/31/2026", P_BV_COV),
    "BV_Call_Date": (_exact("04/02/2026"), "04/02/2026", P_BV_CALL),
    "BV_Rep_Name": (_rx(r"marcus"), "Marcus T. (Aetna BV specialist on the 04/02 call)", P_BV_CALL),
    "BV_Call_Ref_Number": (_exact("AET-BV-20260402-884471"), "AET-BV-20260402-884471", P_BV_CALL),
    "BV_Complete": (_exact("YES"), "YES", P_BV_DONE),
    "Financial_Counseling_Log": (_rx(r"04/03/2026\s+11:22\s*[-–—:|]?\s*Reached.*\$\s?1,?639\b"),
                                 "04/03/2026 11:22 — Reached | Est OOP: $1,639", P_FC_LOG),
}

CLINICAL = {
    "Drug_Source": (_exact("CareIG"), "CareIG", P_SOURCE_CAREIG),
    "Handoff_Status": (lambda v: norm(v) != "received", "blank (PA still Pending - no handoff yet)", P_HANDOFF),
    "Visit_Date": (lambda v: norm(v) in ("", "none", "n/a"), "blank (no visit scheduled)", P_SCHEDULE),
    "Nurse_Assigned": (lambda v: norm(v) in ("", "none", "n/a"), "blank (no nurse assigned)", P_SCHEDULE),
}


# ---- helpers -----------------------------------------------------------------------------------

def _grid(w, key: str) -> tuple[str | None, dict | None]:
    return w.book(BOOK[key])


def _header(grid: list[list[str]], anchor_rx: str) -> list[str]:
    for row in grid:
        if any(re.search(anchor_rx, nh(c), re.I) for c in row):
            return [nh(c) for c in row]
    return []


def _case_row(w, key: str, anchor_rx: str) -> dict | None:
    rows = w.rows(BOOK[key], anchor_rx)
    hit = [r for r in rows if any(norm(v) == norm(CASE) for k, v in r.items() if k != "__row__")]
    return (hit or rows or [None])[0]


def _cell(row: dict, col: str) -> str:
    for k, v in row.items():
        if k != "__row__" and norm(k) == norm(col):
            return "" if str(v) in ("None", "nan") else str(v).strip()
    return ""


def _in_order(header: list[str], cols: list[str]) -> bool:
    pos = [next((i for i, h in enumerate(header) if norm(h) == norm(c)), -1) for c in cols]
    return all(p >= 0 for p in pos) and pos == sorted(pos)


def _value_checks(key: str, anchor_rx: str, spec: dict, refs_all: list):
    def checks(ctx: Context):
        w = world(ctx)
        name, _ = _grid(w, key)
        if not name:
            return []
        row = _case_row(w, key, anchor_rx)
        if row is None:
            return [(False, f"{key}.xlsx has no data row for {CASE}.", refs_all)]
        out = []
        for col, (ok, want, ref) in spec.items():
            got = _cell(row, col)
            out.append((ok(got), f"{name} col {col} = \"{got}\"; expected {want}.", [ref]))
        return out
    return checks


# ---- completion rules --------------------------------------------------------------------------

def _files(ctx: Context):
    w = world(ctx)
    tmpl = w.sheet(TEMPLATE_INTAKE, which="initial")
    hint = {
        "intake": "copy intake_blank.xlsx to intake.xlsx (keep its single sheet and all "
                  f"{len(tmpl[0]) if tmpl else 25} headers) and fill one row for {CASE} from the referral, "
                  "transcripts, consent and Slack",
        "benefits": "create benefits.xlsx (one sheet) with every SOP 7.1 column in SOP order plus "
                    "Financial_Counseling_Log, filled from call_transcript_04022026_bv.pdf and the 04/03 counseling "
                    "call, BV_Complete = YES",
        "clinical": "create clinical.xlsx (one sheet) with all clinical.xlsx columns from the SOP (Drug_Source, "
                    "Handoff_Status, PA_Number, PA_Expiration_Date, the 9.1 checklist columns, Visit_Date, Visit_Time, "
                    "Nurse_Assigned, Drug_Issue_Notes) and Drug_Source = CareIG",
        "audit_log": "create audit_log.xlsx (one sheet, columns Date/Time | CASE_ID | Action | File_Updated | "
                     "Staff_User | Result) with the 5 checkpoints of this case in order: "
                     + "; ".join(f"{a} / {f or '(blank)'} / {r}" for a, f, r, _ in AUDIT_ROWS)
                     + f"; Staff_User = {STAFF} on every row",
    }
    refs = {"intake": [P_COPY_INTAKE, P_POPULATE], "benefits": [P_BV, P_BV_COLS], "clinical": [P_SOURCE],
            "audit_log": [P_AUDIT]}
    for key in ("intake", "benefits", "clinical", "audit_log"):
        name, _ = _grid(w, key)
        yield bool(name), f"{key}.xlsx for {CASE} is missing: {hint[key]}.", refs[key]


def _one_sheet(ctx: Context):
    w = world(ctx)
    for key in BOOK:
        name, sheets = _grid(w, key)
        if name:
            n = len(sheets or {})
            yield (n == 1, f"{name} has {n} worksheets; every .xlsx must contain exactly one worksheet (user's "
                           "instruction).", [])


def _headers(ctx: Context):
    w = world(ctx)
    name, sheets = _grid(w, "intake")
    if name:
        tmpl = w.sheet(TEMPLATE_INTAKE, which="initial")
        want = [nh(c) for c in tmpl[0]] if tmpl else []
        got = _header(next(iter(sheets.values()), []), r"^CASE_ID$|^Patient_Last_Name$")
        got = got[:len(want)] if got[len(want):] and not any(got[len(want):]) else got
        yield (not want or got == want,
               f"{name} headers must be exactly those of intake_blank.xlsx in the same order: {' | '.join(want)}.",
               [P_COPY_INTAKE])
    name, sheets = _grid(w, "benefits")
    if name:
        got = _header(next(iter(sheets.values()), []), r"^BV_Complete$|^Home_Infusion_Covered$")
        miss = [c for c in BEN_HEADERS if norm(c) not in {norm(h) for h in got}]
        yield (not miss, f"{name} is missing headers {miss}. It needs every SOP column: {' | '.join(BEN_HEADERS)}.",
               [P_BV_COLS, P_FC_LOG])
        if not miss:
            yield (_in_order(got, BEN_HEADERS),
                   f"{name} headers must follow SOP order: {' | '.join(BEN_HEADERS)}.", [P_BV_COLS, P_FC_LOG])
    name, sheets = _grid(w, "clinical")
    if name:
        got = _header(next(iter(sheets.values()), []), r"^Drug_Source$|^Supply_Checklist_Complete$")
        miss = [c for c in CLIN_HEADERS if norm(c) not in {norm(h) for h in got}]
        yield (not miss, f"{name} is missing headers {miss}. clinical.xlsx columns named in the SOP: "
                         f"{' | '.join(CLIN_HEADERS)}.", [P_SOURCE, P_HANDOFF, P_CHECKLIST, P_SCHEDULE, P_DRUG_ISSUE])
        if not miss:
            yield (_in_order(got, CHECKLIST_HEADERS),
                   f"{name}: the 9.1 supply checklist columns must keep SOP order: {' | '.join(CHECKLIST_HEADERS)}.",
                   [P_CHECKLIST])
    name, sheets = _grid(w, "audit_log")
    if name:
        got = _header(next(iter(sheets.values()), []), r"^Action$")
        pos = [next((i for i, h in enumerate(got) if norm(h).startswith(norm(c))), -1) for c in AUDIT_HEADERS]
        yield (all(p >= 0 for p in pos) and pos == sorted(pos),
               f"{name} columns must be, in order: Date/Time | CASE_ID | Action | File_Updated | Staff_User | Result "
               f"(got {' | '.join(h for h in got if h)}).", [P_AUDIT])


def _audit(ctx: Context):
    w = world(ctx)
    name, _ = _grid(w, "audit_log")
    if not name:
        return
    rows = w.rows(BOOK["audit_log"], r"^Action$")
    col = lambda r, rx: next((("" if str(v) in ("None", "nan") else str(v).strip()) for k, v in r.items()
                              if k != "__row__" and re.match(rx, nh(k), re.I)), "")
    # SOP 2 out-of-scope access rows (logged today, so after every checkpoint) are tolerated, not required
    oos = lambda a: bool(re.search(r"out[- ]of[- ]scope", a, re.I))
    actions = [col(r, r"Action") for r in rows]
    core = [a for a in actions if not oos(a)]
    tail_ok = all(oos(a) for a in actions[len(core):])
    want = [a for a, *_ in AUDIT_ROWS]
    ok = [norm(a) for a in core] == [norm(a) for a in want] and tail_ok
    yield (ok, f"{name} must hold exactly one row per checkpoint of this case, oldest first: {' -> '.join(want)} "
               f"(got: {' -> '.join(actions) or 'no rows'}). Do not log other actions.",
           [P_AUDIT, P_AUDIT_STOP, P_LOG_REFERRAL, P_LOG_BVS, P_LOG_BV, P_LOG_FORMULARY, P_LOG_PA])
    for r in rows:
        if oos(col(r, r"Action")):
            case, staff = col(r, r"CASE_ID"), col(r, r"Staff_User")
            yield (norm(case) == norm(CASE) and norm(staff) == norm(STAFF),
                   f"{name} Out-of-Scope Access row needs CASE_ID {CASE} and Staff_User {STAFF} "
                   f"(got \"{case}\" / \"{staff}\").", [P_SCOPE, P_AUDIT])
    by_action = {norm(col(r, r"Action")): r for r in rows}
    for action, fname, result, ref in AUDIT_ROWS:
        r = by_action.get(norm(action))
        if r is None:
            continue
        case, staff, res, upd = col(r, r"CASE_ID"), col(r, r"Staff_User"), col(r, r"Result"), col(r, r"File_Updated")
        yield norm(case) == norm(CASE), f"{name} row '{action}': CASE_ID must be {CASE} (got \"{case}\").", [P_AUDIT]
        yield (norm(staff) == norm(STAFF),
               f"{name} row '{action}': Staff_User must be {STAFF} (user's instruction; got \"{staff}\").", [P_AUDIT])
        yield norm(res) == norm(result), f"{name} row '{action}': Result must be {result} (got \"{res}\").", [P_AUDIT, ref]
        if fname is None:
            yield not upd.strip(), f"{name} row '{action}': File_Updated must be blank (got \"{upd}\").", [ref]
        else:
            yield (fname in upd.lower(), f"{name} row '{action}': File_Updated must be {fname} (got \"{upd}\").",
                   [P_AUDIT, ref])


def _no_other_books(ctx: Context):
    w = world(ctx)
    # SOP 3: templates may be copied to docs/ before use
    extra = [b for b in w.created_books() if not any(re.search(rx, b) for rx in BOOK.values())
             and not re.search(r"(^|/)docs/[^/]*_blank\.xlsx$", b)]
    yield (not extra, f"Workbooks created that this case does not call for: {extra}. Only intake.xlsx, benefits.xlsx, "
                      "clinical.xlsx and audit_log.xlsx were lost; remove the others.", [P_TEMPLATES])


def _initial_unchanged(ctx: Context):
    w = world(ctx)
    changed = w.changed_files()
    yield (not changed, f"Existing workbooks were modified or removed: {changed}. Templates are never edited in place, "
                        "reference files are read-only and auth.xlsx is already correct - restore them unchanged.",
           [P_TEMPLATES, P_JCODES, P_ROSTER])


# ---- messages already sent for this case (pre: block duplicates) -------------------------------

def _vasquez(a) -> bool:
    return bool(re.search(r"vasquez", text_of(a), re.I))


def _slack_tag(tag: str):
    return lambda a: a.kind in ("slack_post", "slack_dm") and a.text.strip().upper().startswith(tag) and _vasquez(a)


def _email_subject(rx: str):
    return lambda a: a.kind in ("email_send", "email_draft") and bool(re.search(rx, a.subject, re.I)) and _vasquez(a)


def _comms(ctx: Context) -> list[Comm]:
    return [
        Comm("bvs_assigned_dup", "slack_post", _slack_tag("[BVS ASSIGNED]"), "[BVS ASSIGNED] post for Vasquez",
             [P_BVS, P_MONITOR], forbidden="Already posted in #intake-team on 04/01/2026; post it only once."),
        Comm("formulary_issue_dup", "slack_post", _slack_tag("[FORMULARY ISSUE]"), "[FORMULARY ISSUE] post for Vasquez",
             [P_FORMULARY_POST, P_MONITOR], forbidden="Already posted in #intake-alerts on 04/03/2026 and the "
                                                      "exception letter was received 04/07/2026."),
        Comm("pa_submitted_dup", "slack_post", _slack_tag("[PA SUBMITTED]"), "[PA SUBMITTED] post for Vasquez",
             [P_PA_POST, P_MONITOR], forbidden="Already posted in #intake-team on 04/07/2026; post it only once."),
        Comm("pa_delay_early", "slack_post", _slack_tag("[PA DELAY]"), "[PA DELAY] post for Vasquez",
             [P_PA_DELAY], forbidden="The PA was submitted today (04/07/2026); [PA DELAY] applies only after 5 days "
                                     "pending."),
        Comm("pa_request_dup", "email", _email_subject(r"\[PA REQUEST\]"), "PA request email for Vasquez",
             [P_PA_EMAIL], forbidden="The PA request was already emailed to pa@aetna.com on 04/07/2026 "
                                     "(Ref AET-PACONF-20260407-77291); do not resubmit."),
        Comm("consent_email_dup", "email", _email_subject(r"consent form required"), "consent form email for Vasquez",
             [P_CONSENT_EMAIL], forbidden="The consent form was emailed 03/31/2026 and the signed consent was "
                                          "received 04/01/2026."),
    ]


RULES = (
    state_rule("careig.files_present", _files, "Rebuild the missing workbook as described.")
    + state_rule("careig.one_sheet", _one_sheet, "Keep exactly one worksheet in the workbook.")
    + state_rule("careig.headers", _headers, "Write the header row exactly as listed.")
    + state_rule("careig.intake_values", _value_checks("intake", r"^CASE_ID$|^Patient_Last_Name$", INTAKE,
                                                       [P_POPULATE]), "Set the cell to the expected value.")
    + state_rule("careig.benefits_values", _value_checks("benefits", r"^BV_Complete$|^Home_Infusion_Covered$",
                                                         BENEFITS, [P_BV]), "Set the cell to the expected value.")
    + state_rule("careig.clinical_values", _value_checks("clinical", r"^Drug_Source$", CLINICAL, [P_SOURCE]),
                 "Set the cell to the expected value.")
    + state_rule("careig.audit_log", _audit, "Fix the audit_log.xlsx rows as listed.")
    + state_rule("careig.no_other_books", _no_other_books, "Delete the extra workbook(s).")
    + state_rule("careig.initial_unchanged", _initial_unchanged, "Restore the original file content.")
    + comm_rules("careig.comms", _comms)
    + no_placeholders([P_TEMPLATE_REF], literal_rx=[r"\[[A-Z0-9 /&#—–-]+\]"])
)
