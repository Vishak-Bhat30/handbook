"""CareIG IVIG SOP v6.0 - QA spot check of CASE-1001 from Section 9 onward (task d4619b8b).

Situation (seed data): CASE-1001 (Thompson, Michael; BlueCross Commercial PPO; Privigen 10% 30g every 4 weeks;
PA BC-2026-44821 valid to 2026-09-15) had its first visit on 2026-03-15 (29.7g administered, 195 min, Diphenhydramine
75mg IV, 2x NS 500 + 1x NS 250, pump used). The claim (submitted 2026-03-16, freq 1, $4,340.25) used the ordered
dose and wrong unit counts, and the next recurring visit was never scheduled. Today is 2026-04-02.

Expected values (derived from SOP + seed):
- Claim (SOP 10.2/13.1, fee_schedule): J1459 floor(29.7*1000/500)=59; 99600x1 + 99603xfloor((195-60)/60)=2;
  J7030x2, J7050x1; J0171 ceil(75/50)=2; A4221x1, A4222x1 -> Total 59*58+265+2*135+2*12.5+8.75+2*6.5+95+55=4153.75.
  Corrected claim per 11.1: same row, Claim_Frequency_Code 7, re-export + resubmit per 10.3 (Submission_Date
  2026-04-02, Claim_Status Submitted), #billing post, audit "Claim Submitted".
- Next visit (9.3 -> 9.2 steps 2-7): 2026-03-15 + 4 weeks = Sun 2026-04-12; window 04-09..04-15; zip 90212 nurses
  Jane Smith (RN, Mon-Fri from 04-01) / Maria Garcia (LPN, Mon-Thu). With 30-min buffers and 3 h duration
  (infusion_duration: Privigen 10% 16-30g = 3 h) the only feasible slot is Tue 2026-04-14 12:00-15:00, Jane Smith.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from zoneinfo import ZoneInfo

from ..kit import (COMM_KINDS, Action, Comm, Context, Ref, World, append_only, blank, comm_rules, dashes,
                   forbid_writes, money_rx, nh, no_placeholders, norm, pre_rule, same, state_rule, text_of, world)

CASE = "CASE-1001"
TODAY = dt.date(2026, 4, 2)
DOS = dt.date(2026, 3, 15)
NEXT_DATE = dt.date(2026, 4, 14)
NEXT_START, NEXT_END = dt.time(12, 0), dt.time(15, 0)
NURSE = "Jane Smith"
NURSE_EMAIL = "j.smith@careig.com"
PATIENT_EMAIL = "m.thompson@email.com"
CLAIMS_EMAIL = "claims@bluecross-ppo.example.com"
SIGNER = "Angela Torres"
EVENT_SUMMARY = "IVIG Infusion - Thompson, Michael (CASE-1001)"
CLAIM_SUBJECT = "[CLAIM SUBMISSION] CareIG NPI: 1234567893 | Thompson | MemberID: BCX-998712 | DOS: 2026-03-15"
TOTAL = 4153.75
LA = ZoneInfo("America/Los_Angeles")

CLAIM_BOOK = r"(^|/)claim_CASE-1001\.xlsx$"
CLIN_BOOK = r"(^|/)clinical_CASE-1001\.xlsx$"
AUDIT_BOOK = r"(^|/)audit_log\.xlsx$"
ABOUT_CASE = re.compile(r"CASE-1001|Thompson|BCX-998712", re.I)
OTHER_CASE = re.compile(r"CASE-(?!1001\b)\d{3,4}\b|Rivera|Okafor|Washington,\s*Denise|Denise\s+Washington|"
                        r"Park,\s*James|James\s+Park|1EG4-TE5-MK72|W901-HK-228819|UHC-MA-5578201|BCX-441295", re.I)
SEED_EVENT_1001 = "evt-1001"

# ---- SOP references (section, paragraph text prefix, label) --------------------------------------
R_FILES = ("3", "CareIG Specialty Pharmacy | IVIG Home Infusion Billing SOP | v6.0 | Effective: March 23, 2026 auth.xlsx",
           "§3 File System Structure")
R_NEWFILE = ("3", "All files which are created per case have a blank template", "§3")
R_AUDIT = ("4.1", "Append one row to audit_log.xlsx at each major checkpoint", "§4.1 Audit Logging")
R_DRUGSRC = ("4.3", "Do not bill any IVIG drug J-code when", "§4.3")
R_PREMED_DOC = ("4.3", "Do not bill pre-medication J-codes unless", "§4.3")
R_ORDERED = ("4.3", "Do not use ordered dose for unit calculations", "§4.3")
R_NODUP = ("4.3", "Do not submit a claim when claim.xlsx already has Submission_Date", "§4.3")
R_ICD = ("4.3", "Do not assign an ICD-10 code not supported", "§4.3")
R_PHONE1 = ("4.4", "1. Check whether the required information is already documented", "§4.4 step 1")
R_PHONE2 = ("4.4", "2. If the information is not available, send an email", "§4.4 step 2")
R_SUPPLY_HOLD = ("9.1", "CareIG Specialty Pharmacy | IVIG Home Infusion Billing SOP | v6.0 | Effective: March 23, 2026 Supplies_Other",
                 "§9.1")
R_SUPPLY_POST = ("9.1", "Post to #clinical-scheduling: [SUPPLY HOLD]", "§9.1")
R_NURSE_SEL = ("9.2", "2. Select nurse (nurses.xlsx) matching patient zip code", "§9.2 step 2")
R_HOURS = ("9.2", "Schedule visits between 08:00 and 17:00 only", "§9.2")
R_BUFFER = ("9.2", "Check the calendar for the assigned nurse's existing appointments", "§9.2")
R_EVENT = ("9.2", "3. Create calendar event: summary should be IVIG Infusion", "§9.2 step 3")
R_DURATION = ("9.2", "4. Set duration using the estimated infusion times", "§9.2 step 4")
R_CONFIRM = ("5", '"Hello [Patient Name], this is [Your Name] from CareIG. Your insurance has approved', "§9.2 step 5")
R_SCHEDULED = ("5", "6. Update clinical.xlsx: Visit_Date, Visit_Time, Nurse_Assigned.", "§9.2 step 6")
R_NURSE_MAIL = ("5", "7. Email assigned nurse. Subject: [VISIT ASSIGNMENT]", "§9.2 step 7")
R_NM_ADDR = ("5", "Address: [Patient_Address from intake.xlsx]", "§9.2 step 7")
R_NM_DRUG = ("5", "Drug: [Drug_Name from intake.xlsx]", "§9.2 step 7")
R_NM_DOSE = ("5", "Dose: [Drug_Dose_Grams from intake.xlsx]", "§9.2 step 7")
R_NM_LOT = ("5", "Lot Number: [Drug_Lot_Number from clinical.xlsx]", "§9.2 step 7")
R_NM_NDC = ("5", "NDC: [Drug_NDC from clinical.xlsx]", "§9.2 step 7")
R_NM_RATE = ("5", "Infusion Rate: [Infusion_Start_Rate_mL_hr from intake.xlsx]", "§9.2 step 7")
R_NM_PREMED = ("5", "Pre-med Orders: [Premeds_Administered", "§9.2 step 7")
R_NM_PHONE = ("5", "Emergency Contact: [Patient_Phone from intake.xlsx]", "§9.2 step 7")
R_NM_CONTRA = ("5", "Contraindications: [Contraindications from intake.xlsx]", "§9.2 step 7")
R_CARRY_I = ("9.3", "intake.xlsx — reuse existing patient record", "§9.3")
R_CARRY_B = ("9.3", "benefits.xlsx — reuse unless the payer", "§9.3")
R_CARRY_A = ("9.3", "auth.xlsx — reuse the current PA", "§9.3")
R_UPDATED = ("9.3", "clinical.xlsx Visit_Date, Visit_Time, Nurse_Assigned", "§9.3")
R_ONECLAIM = ("9.3", "claim.xlsx — one new row per visit", "§9.3")
R_NEXT = ("9.3", "Scheduling subsequent visits: After each completed visit", "§9.3")
R_PREBILL = ("10.1", "Before building claim.xlsx, confirm every condition below is TRUE", "§10.1")
R_PREBILL_T1 = ("10.1", "Condition If FALSE — Post to #billing", "§10.1")
R_PREBILL_T2 = ("10.1", "CareIG Specialty Pharmacy | IVIG Home Infusion Billing SOP | v6.0 | Effective: March 23, 2026 to #billing",
                "§10.1")
R_JCODE = ("10.2", "Copy claim_blank.xlsx to create claim.xlsx", "§10.2 Drug J-Code")
R_UNITS = ("10.2", "Units = (Dose_Administered_Grams × 1000) ÷ unit size", "§10.2 Units")
R_NURSING = ("10.2", "Nursing Code Read payer_rules.xlsx col Nursing_Code_Pref", "§10.2 Nursing Code")
R_NURS_GT60 = ("10.2", "If Visit_Duration_Minutes > 60: bill 99600", "§10.2")
R_SALINE = ("10.2", "Saline J7030 × NS_500mL_Bags_Used", "§10.2 Saline")
R_PREMED = ("10.2", "Pre-Medications Parse visit_note.xlsx col Premeds_Administered", "§10.2 Pre-Medications")
R_SUPPLY = ("10.2", "Supplies Bill A4221 × 1 per visit", "§10.2 Supplies")
R_PUMP = ("10.2", "If Pump_Used = YES: also A4222 × 1", "§10.2")
R_HEADER = ("10.2", "CareIG Specialty Pharmacy | IVIG Home Infusion Billing SOP | v6.0 | Effective: March 23, 2026 Header",
            "§10.2 Header / Auth Fields")
R_SPLIT = ("10.2", "Split-Bill (OON partner)", "§10.2 Split-Bill")
R_FREQ = ("10.2", "Claim_Frequency_Code Enter 1 for all original", "§10.2 Claim_Frequency_Code")
R_MOD = ("10.2", "Modifier Read visit_note.xlsx col Route", "§10.2 Modifier")
R_TOTAL = ("10.2", "Total Billed Sum of all line item amounts", "§10.2 Total Billed")
R_TOTAL13 = ("13.1", "Source: jcodes.xlsx. Always use visit_note.xlsx col Dose_Administered_Grams", "§13.1")
R_EXPORT = ("10.3", "1. Export claim.xlsx to PDF", "§10.3 step 1")
R_SUBMIT = ("10.3", "2. Email to payer billing address", "§10.3 step 2")
R_SUBFIELDS = ("10.3", "3. Update claim.xlsx: Submission_Date = today", "§10.3 step 3")
R_BILLPOST = ("10.3", "4. Post to #billing: [CLAIM SUBMITTED]", "§10.3 step 4")
R_AUDIT_CLAIM = ("10.3", "Log to audit_log.xlsx: Action = Claim Submitted", "§10.3")
R_CORR = ("11.1", "These steps should also be followed if details of a Claim Submission", "§11.1")
R_CORR1 = ("11.1", "1. Correct the identified issue in the existing claim.xlsx row.", "§11.1 step 1")
R_CORR2 = ("11.1", "2. Set Claim_Frequency_Code = 7", "§11.1 step 2")
R_CORR3 = ("11.1", "3. Re-export and submit per §10.3.", "§11.1 step 3")
R_NOROW = ("11.1", "Do not create a new row. Do not delete the original submission history", "§11.1")
R_T6 = ("10", "[Staff Name] — CareIG Specialty Pharmacy, Intake intake@careig.com Template 6", "Appendix A Template 6")
R_INSTR: Ref = ("0", "__instruction__", "task instruction (CASE-1001 only; sign correspondence as Angela Torres)")


# ---- helpers ------------------------------------------------------------------------------------------

def as_date(v) -> dt.date | None:
    s = nh(v)
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d", "%m-%d-%Y"):
        try:
            return dt.datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None


def as_time(v) -> dt.time | None:
    s = nh(v).lower()
    m = re.match(r"^(\d{1,2}):(\d{2})(?::\d{2})?\s*(am|pm|a\.m\.|p\.m\.)?$", s)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2)), (m.group(3) or "").replace(".", "")
    if ap == "pm" and h < 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    return dt.time(h, mi) if h < 24 else None


def local_dt(v) -> dt.datetime | None:
    """Calendar start/end (dict or ISO string) as naive America/Los_Angeles time."""
    if isinstance(v, dict):
        v = v.get("dateTime") or v.get("date_time") or v.get("date")
    if not v:
        return None
    try:
        d = dt.datetime.fromisoformat(str(v).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return d.astimezone(LA).replace(tzinfo=None) if d.tzinfo else d


def claim_rows(w: World, which: str = "current") -> list[dict]:
    return w.rows(CLAIM_BOOK, r"^Drug_JCode$", which)


def claim_row(w: World) -> dict | None:
    rows = [r for r in claim_rows(w) if norm(w.col(r, r"^CASE_ID$")) == norm(CASE)]
    return rows[0] if rows else None


def clinical_row(w: World) -> dict | None:
    return w.find(CLIN_BOOK, r"^Supply_Checklist_Complete$", r"^CASE_ID$", CASE)


# Claim cells: column -> (expected value or None for blank, refs). Line items per §10.2 from the visit note.
CLAIM_LINES: dict[str, tuple[str | None, list[Ref], str]] = {
    "Drug_JCode": ("J1459", [R_JCODE, R_DRUGSRC], "Privigen 10% -> J1459 (Drug_Source = CareIG, route IV matches)"),
    "Drug_Units": ("59", [R_UNITS, R_ORDERED], "29.7 g administered x 1000 / 500 = 59.4 -> 59 (never the 30 g ordered)"),
    "Drug_Modifier": (None, [R_MOD], "route IV -> no modifier"),
    "Nursing_Code": ("99600", [R_NURSING, R_NURS_GT60], "payer Nursing_Code_Pref 99600"),
    "Nursing_Units": ("1", [R_NURS_GT60], "99600 x 1"),
    "Nursing_Code_Addl": ("99603", [R_NURS_GT60], "195 min > 60 -> 99603"),
    "Nursing_Units_Addl": ("2", [R_NURS_GT60], "floor((195 - 60) / 60) = 2"),
    "Saline_Code_500": ("J7030", [R_SALINE], "J7030"),
    "Saline_Units_500": ("2", [R_SALINE], "NS_500mL_Bags_Used = 2"),
    "Saline_Code_250": ("J7050", [R_SALINE], "J7050"),
    "Saline_Units_250": ("1", [R_SALINE], "NS_250mL_Bags_Used = 1"),
    "Premed_Code_1": ("J0171", [R_PREMED, R_PREMED_DOC], "Diphenhydramine (documented in Premeds_Administered)"),
    "Premed_Units_1": ("2", [R_PREMED], "75 mg / 50 = 1.5 -> round up to 2"),
    "Premed_Code_2": (None, [R_PREMED], "no second pre-med"),
    "Premed_Units_2": (None, [R_PREMED], "no second pre-med"),
    "Supply_Code_A4221": ("A4221", [R_SUPPLY], "A4221"),
    "Supply_Units_A4221": ("1", [R_SUPPLY], "A4221 x 1 per visit"),
    "Supply_Code_A4222": ("A4222", [R_PUMP], "Pump_Used = YES -> A4222"),
    "Supply_Units_A4222": ("1", [R_PUMP], "A4222 x 1"),
    "ICD10": ("D80.1", [R_HEADER, R_ICD], "intake Diagnosis_ICD10 = PA approved ICD-10"),
    "PA_Number": ("BC-2026-44821", [R_HEADER], "auth PA_Number"),
    "Physician_NPI": ("1122334455", [R_HEADER], "intake Physician_NPI"),
    "CareIG_NPI": ("1234567893", [R_HEADER], "CareIG NPI"),
    "CareIG_Tax_ID": ("47-3821056", [R_HEADER], "CareIG EIN"),
    "CareIG_Taxonomy": ("333600000X", [R_HEADER], "org_identifiers Taxonomy_Code"),
    "Billing_Model": ("Standard", [R_SPLIT], "Drug_Source = CareIG -> not Split"),
    "Claim_Frequency_Code": ("7", [R_FREQ, R_CORR2], "corrected (replacement) claim -> 7"),
    "Total_Billed": (f"{TOTAL:.2f}", [R_TOTAL, R_TOTAL13],
                     "59x58 + 265 + 2x135 + 2x12.50 + 8.75 + 2x6.50 + 95 + 55 = 4153.75"),
}
FIX_COLS = ("Drug_Units", "Nursing_Units_Addl", "Premed_Units_1", "Claim_Frequency_Code", "Total_Billed")


def claim_mismatches(w: World, cols=None) -> list[tuple[str, str, str | None, list[Ref], str]]:
    row = claim_row(w)
    if row is None:
        return []
    out = []
    for col, (want, refs, why) in CLAIM_LINES.items():
        if cols and col not in cols:
            continue
        got = w.col(row, rf"^{col}$")
        if not same(got, want):
            out.append((col, got, want, refs, why))
    return out


# ---- claim: corrected row, submission fields, no new row/file --------------------------------------

def _claim_lines(ctx: Context):
    w = world(ctx)
    row = claim_row(w)
    if row is None:
        yield (False, f"claim_CASE-1001.xlsx has no row for {CASE}; correct the existing row (do not recreate it).",
               [R_CORR1, R_NOROW])
        return
    for col, got, want, refs, why in claim_mismatches(w):
        yield (False, f"claim_CASE-1001.xlsx {col} is \"{got}\" but must be "
                      f"{'blank' if want is None else repr(want)} ({why}).", refs)


def _claim_submission(ctx: Context):
    w = world(ctx)
    row = claim_row(w)
    if row is None:
        return
    sd = as_date(w.col(row, r"^Submission_Date$"))
    yield (sd == TODAY, f"claim_CASE-1001.xlsx Submission_Date must be today, {TODAY.isoformat()}, after the corrected "
                        f"claim is resubmitted (got \"{w.col(row, r'^Submission_Date$')}\").", [R_SUBFIELDS, R_CORR3])
    yield (not blank(w.col(row, r"^Submission_Ref_Number$")),
           "claim_CASE-1001.xlsx Submission_Ref_Number must hold the confirmation ID of the resubmission email.",
           [R_SUBFIELDS])
    yield (same(w.col(row, r"^Claim_Status$"), "Submitted"),
           f"claim_CASE-1001.xlsx Claim_Status must be \"Submitted\" (got \"{w.col(row, r'^Claim_Status$')}\").",
           [R_SUBFIELDS])


def _claim_structure(ctx: Context):
    w = world(ctx)
    n = len(claim_rows(w))
    yield (n <= 1, f"claim_CASE-1001.xlsx must keep a single row for DOS {DOS.isoformat()} ({n} rows now): correct the "
                   "existing row, do not add a new one.", [R_NOROW, R_ONECLAIM])
    extra = [b for b in w.created_books() if re.search(r"(^|/)claim[^/]*\.xlsx$", b, re.I)]
    yield (not extra, f"New claim workbook(s) {extra}: when correcting and resubmitting, update the existing "
                      "claim_CASE-1001.xlsx - do not create a new file.", [R_NEWFILE, R_NOROW])


def _submit_problem(ctx: Context, a: Action) -> str | None:
    if a.kind != "email_send" or not is_claim_mail(a):
        return None
    w = world(ctx)
    bad = claim_mismatches(w, FIX_COLS + ("Drug_JCode", "Nursing_Units", "Saline_Units_500", "Saline_Units_250",
                                          "Supply_Units_A4221", "Supply_Units_A4222", "ICD10", "PA_Number"))
    if not bad:
        return None
    lst = "; ".join(f"{c} = {w_!r} (now \"{g}\")" for c, g, w_, _, _ in bad)
    return (f"[claim] Do not submit the claim for DOS {DOS.isoformat()} until the existing claim_CASE-1001.xlsx row is "
            f"corrected (a claim with Submission_Date already set may only be resubmitted as a corrected claim, "
            f"Claim_Frequency_Code 7). Fix first: {lst}. Then re-export claim_2026-03-15.pdf and send it.")


# ---- clinical.xlsx next visit --------------------------------------------------------------------

def _clinical(ctx: Context):
    w = world(ctx)
    row = clinical_row(w)
    if row is None:
        return
    vd, vt, na = w.col(row, r"^Visit_Date$"), w.col(row, r"^Visit_Time$"), w.col(row, r"^Nurse_Assigned$")
    refs = [R_SCHEDULED, R_UPDATED, R_NEXT]
    yield (as_date(vd) == NEXT_DATE, f"clinical_CASE-1001.xlsx Visit_Date must be the next visit, "
                                      f"{NEXT_DATE.isoformat()} (got \"{vd}\").", refs)
    yield (as_time(vt) == NEXT_START, f"clinical_CASE-1001.xlsx Visit_Time must be 12:00 (got \"{vt}\").", refs)
    yield (norm(na).startswith(norm(NURSE)), f"clinical_CASE-1001.xlsx Nurse_Assigned must be {NURSE} "
                                             f"(got \"{na}\").", refs + [R_NURSE_SEL])


# ---- calendar ------------------------------------------------------------------------------------

def _payload(text: str):
    text = re.sub(r"^\s*\[Tool '[^']*' executed\.\]\s*", "", text or "")
    i = text.find("{")
    if i < 0:
        return None
    try:
        return json.JSONDecoder().raw_decode(text[i:])[0]
    except ValueError:
        return None


def made_events(ctx: Context) -> list[dict]:
    """Events as created/updated by the agent (tool result if it echoes the event, else the call arguments)."""
    out = []
    for e in ctx.state.executed:
        if e.action.kind not in ("calendar_create", "calendar_update"):
            continue
        p = _payload(e.result)
        # an empty tool result is no evidence the event exists (seen in baseline runs where the create did not land)
        if not isinstance(p, dict):
            continue
        ev = p.get("event") if isinstance(p.get("event"), dict) else None
        out.append(ev or e.action.args)
    return out


def event_problems(ev: dict, partial: bool = False) -> list[str]:
    out = []
    summary, desc = ev.get("summary"), ev.get("description")
    start, end = local_dt(ev.get("start")), local_dt(ev.get("end"))
    if summary is not None or not partial:
        if dashes(summary) != dashes(EVENT_SUMMARY):
            out.append(f"summary (the event title) must be exactly \"{EVENT_SUMMARY}\" (got \"{summary}\")")
    if desc is not None or not partial:
        if NURSE.lower() not in str(desc or "").lower():
            out.append(f"the description must name the nurse, {NURSE}")
    if ev.get("start") is not None or not partial:
        if start != dt.datetime.combine(NEXT_DATE, NEXT_START):
            out.append(f"start must be {NEXT_DATE.isoformat()} 12:00 America/Los_Angeles (got {ev.get('start')})")
    if ev.get("end") is not None or not partial:
        if end != dt.datetime.combine(NEXT_DATE, NEXT_END):
            out.append(f"end must be {NEXT_DATE.isoformat()} 15:00 America/Los_Angeles - 3 h for Privigen 10% 30 g "
                       f"(got {ev.get('end')})")
    return out


EVENT_FIX = (f"Create the next-visit event: summary \"{EVENT_SUMMARY}\", start {NEXT_DATE.isoformat()}T12:00:00-07:00, "
             f"end {NEXT_DATE.isoformat()}T15:00:00-07:00 (America/Los_Angeles), description naming the nurse "
             f"{NURSE}. (Every 4 weeks from 2026-03-15 = Sun 04-12; Jane Smith no longer works weekends; with 30-min "
             "buffers the earliest feasible slot in the +/-3-day window for a 90212 nurse is Tue 04-14 12:00.)")
EVENT_REFS = [R_NEXT, R_NURSE_SEL, R_HOURS, R_BUFFER, R_EVENT, R_DURATION]


def _calendar(ctx: Context):
    ok = any(not event_problems(ev) for ev in made_events(ctx))
    yield (ok, "The next recurring visit for CASE-1001 is not on the calendar. " + EVENT_FIX, EVENT_REFS)


def seed_event_ids(w: World) -> set[str]:
    return {str(e.get("id")) for e in w.seed_events if e.get("id")}


def _calendar_pre(ctx: Context, a: Action) -> str | None:
    w = world(ctx)
    if a.kind in ("calendar_update", "calendar_delete"):
        eid = str(a.args.get("eventId") or a.args.get("event_id") or a.args.get("id") or "")
        if eid in seed_event_ids(w) and eid != SEED_EVENT_1001:
            return (f"[calendar] Event {eid} is another patient's / nurse's existing appointment; the task is a spot "
                    "check of CASE-1001 only - leave it unchanged.")
        if eid == SEED_EVENT_1001:
            s = local_dt(a.args.get("start"))
            if a.kind == "calendar_delete" or (s and s.date() != DOS):
                return ("[calendar] evt-1001 is the record of the completed 2026-03-15 visit; do not move or delete "
                        "it - create a new event for the next visit. " + EVENT_FIX)
            return None
        if a.kind == "calendar_delete":
            return None
    if a.kind not in ("calendar_create", "calendar_update"):
        return None
    if not ABOUT_CASE.search(json.dumps(a.args)):
        return None
    probs = event_problems(a.args, partial=a.kind == "calendar_update")
    if probs:
        return "[calendar] CASE-1001 next-visit event: " + "; ".join(probs) + ". " + EVENT_FIX
    if a.kind == "calendar_create" and any(not event_problems(ev) for ev in made_events(ctx)):
        return "[calendar] The CASE-1001 2026-04-14 event already exists; do not create a duplicate."
    return None


# ---- audit log -------------------------------------------------------------------------------------

ALLOWED_ACTIONS = {"claim submitted", "out-of-scope access"}


def _audit(ctx: Context):
    w = world(ctx)
    new = w.new_rows(AUDIT_BOOK, r"^CASE_ID$")
    col = w.col
    good = [r for r in new if norm(col(r, r"^CASE_ID$")) == norm(CASE) and norm(col(r, r"^Action$")) == "claim submitted"
            and as_date(col(r, r"Date")) == TODAY and norm(col(r, r"^Result$")).startswith("success")
            and "claim" in norm(col(r, r"^File_Updated$"))]
    yield (bool(good), f"audit_log.xlsx needs one appended row for the resubmitted claim: Date_Time {TODAY.isoformat()} "
                       f"HH:MM | CASE_ID {CASE} | Action \"Claim Submitted\" | File_Updated claim_CASE-1001.xlsx | "
                       "Field_Updated / New_Value = the fields changed, comma-separated in spreadsheet column order | "
                       "Staff_User | Result SUCCESS.", [R_AUDIT_CLAIM, R_AUDIT])
    for r in new:
        act, res, case = col(r, r"^Action$"), col(r, r"^Result$"), col(r, r"^CASE_ID$")
        if norm(case) != norm(CASE):
            yield (False, f"audit_log.xlsx row {r['__row__']} logs case \"{case}\"; this task covers {CASE} only - "
                          "remove it.", [R_AUDIT, R_INSTR])
        elif norm(act) not in ALLOWED_ACTIONS and not norm(res).startswith("stop"):
            yield (False, f"audit_log.xlsx row {r['__row__']} (Action \"{act}\") is not an SOP checkpoint - only "
                          "checkpoints are logged (here: Action = \"Claim Submitted\" for the resubmitted claim). "
                          "Remove the row or merge it into the Claim Submitted row.", [R_AUDIT])


# ---- unchanged files -------------------------------------------------------------------------------

UNCHANGED = {
    r"(^|/)intake_CASE-1001\.xlsx$": [R_CARRY_I, R_INSTR],
    r"(^|/)benefits_CASE-1001\.xlsx$": [R_CARRY_B, R_INSTR],
    r"(^|/)auth_CASE-1001\.xlsx$": [R_CARRY_A, R_INSTR],
    r"(^|/)(payer_rules|fee_schedule|nurses|infusion_duration|org_identifiers)\.xlsx$": [R_FILES, R_INSTR],
}


def _unchanged(ctx: Context):
    w = world(ctx)
    changed = w.changed_files()
    for rx, refs in UNCHANGED.items():
        hit = [f for f in changed if re.search(rx, f)]
        yield (not hit, f"{', '.join(hit)} changed: it was verified correct (intake/benefits/auth carry forward "
                        "unchanged; reference tables are read-only). Restore the original content.", refs)


# ---- messages ------------------------------------------------------------------------------------

def _emails(a: Action) -> bool:
    return a.kind in ("email_send", "email_draft")


def is_claim_mail(a: Action) -> bool:
    return _emails(a) and ("CLAIM SUBMISSION" in a.subject.upper() or CLAIMS_EMAIL in a.recipients) \
        and bool(ABOUT_CASE.search(text_of(a)))


def specs(ctx: Context) -> list[Comm]:
    w = world(ctx)
    crow = clinical_row(w) or {}
    lot, ndc = w.col(crow, r"^Drug_Lot_Number$"), w.col(crow, r"^Drug_NDC$")
    sign = (re.escape(SIGNER), f"sign-off with {SIGNER}")
    nurse_body = [
        (r"742 Evergreen Terrace", "Address: 742 Evergreen Terrace, Beverly Hills, CA 90212"),
        (r"Privigen 10\s*%", "Drug: Privigen 10%"),
        (r"\b30(\.0)?\s*g\b", "Dose: 30g"),
        (r"Rate\W{0,3}\s*30\b", "Infusion Rate: 30 mL/hr"),
        (r"Diphenhydramine 75\s*mg", "Pre-med Orders: Diphenhydramine 75mg IV"),
        (r"\(?310\)?[\s.-]*555[\s.-]*0147", "Emergency Contact: (310) 555-0147"),
        (r"Contraindications\W{0,3}\s*None", "Contraindications: None"),
        (r"12:00", "Time: 12:00"),
        sign,
    ]
    if lot:
        nurse_body.append((re.escape(lot), f"Lot Number: {lot}"))
    if ndc:
        nurse_body.append((re.escape(ndc), f"NDC: {ndc}"))
    out = [
        Comm("claim_resubmission", "email", is_claim_mail,
             "corrected claim (frequency code 7) resubmitted to BlueCross per §11.1 / §10.3",
             [R_CORR, R_CORR3, R_SUBMIT, R_EXPORT, R_NODUP], to=[CLAIMS_EMAIL],
             subject=re.escape(CLAIM_SUBJECT), subject_hint=CLAIM_SUBJECT,
             attach=[(r"^claim_.*(2026-?03-?15|03-?15-?2026).*\.pdf$",
                      "the re-exported corrected claim PDF named claim_[DOS].pdf, e.g. claim_2026-03-15.pdf")],
             body=[sign]),
        Comm("billing_post", "slack_post",
             lambda a: a.kind in ("slack_post", "slack_dm") and "[CLAIM SUBMITTED]" in a.text.upper()
             and bool(ABOUT_CASE.search(a.text)),
             "#billing [CLAIM SUBMITTED] post for the corrected claim", [R_BILLPOST], channel="billing",
             body=[(r"\[CLAIM SUBMITTED\]\s*CASE-1001", "[CLAIM SUBMITTED] CASE-1001"),
                   (r"DOS:\s*2026-03-15", "DOS: 2026-03-15"),
                   (r"Payer:\s*BlueCross Commercial PPO", "Payer: BlueCross Commercial PPO"),
                   (r"Billed:\s*" + money_rx(TOTAL), "Billed: $4,153.75")]),
        Comm("scheduled_post", "slack_post",
             lambda a: a.kind in ("slack_post", "slack_dm") and "[SCHEDULED]" in a.text.upper()
             and bool(ABOUT_CASE.search(a.text)),
             "#clinical-scheduling [SCHEDULED] post for the next visit", [R_SCHEDULED, R_NEXT],
             channel="clinical-scheduling",
             body=[(r"\[SCHEDULED\]\s*CASE-1001", "[SCHEDULED] CASE-1001"),
                   (r"Date:\s*2026-04-14", "Date: 2026-04-14"), (r"Nurse:\s*Jane Smith", "Nurse: Jane Smith")]),
        Comm("nurse_assignment", "email",
             lambda a: _emails(a) and ("VISIT ASSIGNMENT" in a.subject.upper() or NURSE_EMAIL in a.recipients)
             and bool(ABOUT_CASE.search(text_of(a)) or "VISIT ASSIGNMENT" in a.subject.upper()),
             "visit assignment email to the assigned nurse", [R_NURSE_MAIL, R_NM_ADDR, R_NM_DRUG, R_NM_DOSE, R_NM_LOT,
                                                              R_NM_NDC, R_NM_RATE, R_NM_PREMED, R_NM_PHONE,
                                                              R_NM_CONTRA, R_NEXT],
             to=[NURSE_EMAIL], subject=r"\[VISIT ASSIGNMENT\] CASE-1001 \| (2026-04-14|04/14/2026)",
             subject_hint="[VISIT ASSIGNMENT] CASE-1001 | 2026-04-14", body=nurse_body),
        Comm("patient_confirmation", "email",
             lambda a: _emails(a) and (PATIENT_EMAIL in a.recipients or (
                 "APPOINTMENT" in a.subject.upper() and bool(ABOUT_CASE.search(text_of(a))))),
             "Template 6 appointment confirmation to the patient (email instead of the phone script)",
             [R_CONFIRM, R_T6, R_PHONE1, R_PHONE2, R_NEXT], to=[PATIENT_EMAIL],
             subject=r"CareIG – IVIG Infusion Appointment \| 2026-04-14",
             subject_hint="CareIG — IVIG Infusion Appointment | 2026-04-14",
             body=[(r"2026-04-14", "Date: 2026-04-14"), (r"12:00\s*(pm|p\.m\.)", "Time: 12:00 pm"),
                   (r"\b3(\.0)?\s*(hours|hrs)\b", "Approximate Duration: 3 hours"), sign]),
        Comm("other_cases", "email", lambda a: a.kind in COMM_KINDS and bool(OTHER_CASE.search(text_of(a))),
             "correspondence about another case", [R_INSTR],
             forbidden="The request is a spot check of CASE-1001 only; do not send messages about other cases or "
                       "patients."),
        Comm("billing_hold", "slack_post",
             lambda a: a.kind in COMM_KINDS and "[BILLING HOLD" in a.text.upper() and bool(ABOUT_CASE.search(a.text)),
             "false [BILLING HOLD] for CASE-1001", [R_PREBILL, R_PREBILL_T1, R_PREBILL_T2],
             forbidden="Every §10.1 pre-billing condition holds for CASE-1001 (note signed; PA Approved, "
                       "BC-2026-44821, expires 2026-09-15 >= DOS; Privigen 10% matches; 30 g >= 29.7 g; D80.1 = PA "
                       "ICD-10; dose > 0; coverage 2025-01-01..2026-12-31) - no billing hold applies."),
    ]
    if norm(w.col(crow, r"^Supply_Checklist_Complete$")) == "yes":
        out.append(Comm("supply_hold", "slack_post",
                        lambda a: a.kind in COMM_KINDS and "[SUPPLY HOLD]" in a.text.upper()
                        and bool(ABOUT_CASE.search(a.text)),
                        "[SUPPLY HOLD] for CASE-1001", [R_SUPPLY_HOLD, R_SUPPLY_POST],
                        forbidden="clinical_CASE-1001.xlsx Supply_Checklist_Complete = YES, so the [SUPPLY HOLD] "
                                  "trigger (checklist incomplete) does not apply; schedule the visit."))
    return out


def _signature(ctx: Context, a: Action) -> str | None:
    if a.kind in ("email_send", "email_draft") and SIGNER.lower() not in a.text.lower():
        return f"[signature] Sign off every email with \"{SIGNER}\" as the user asked."
    return None


RULES = (
    state_rule("claim.lines", _claim_lines, "Correct the existing claim_CASE-1001.xlsx row to the values listed.")
    + state_rule("claim.submission", _claim_submission, "Update the claim row after resubmitting.")
    + state_rule("claim.structure", _claim_structure, "Keep one claim row in the existing claim_CASE-1001.xlsx.")
    + pre_rule("claim.submit_corrected_first", _submit_problem, [R_CORR1, R_CORR2, R_CORR3, R_NODUP],
               "Correct the claim row (and set Claim_Frequency_Code 7) before sending the claim.")
    + state_rule("clinical.next_visit", _clinical, "Update clinical_CASE-1001.xlsx for the next visit.")
    + state_rule("calendar.next_visit", _calendar, "Create the calendar event as described.")
    + pre_rule("calendar.event", _calendar_pre, EVENT_REFS, "Fix the event fields as described.")
    + state_rule("audit.entries", _audit, "Fix audit_log.xlsx as described.")
    + append_only("audit.append_only", AUDIT_BOOK, r"^CASE_ID$", "audit_log.xlsx", [R_FILES, R_AUDIT])
    + forbid_writes("files.read_only", r"^(jcodes\.xlsx|.*_blank\.xlsx)$",
                    "jcodes.xlsx is read-only and blank templates are never edited in place (copy them instead).",
                    [R_FILES])
    + state_rule("files.unchanged", _unchanged, "Restore the file.")
    + comm_rules("comms", specs)
    + pre_rule("comms.signature", _signature, [R_INSTR], f"Add the sign-off \"{SIGNER}\".")
    + no_placeholders([R_NM_ADDR], literal_rx=[r"\[[A-Z0-9 &/#'.,()\-–—]+\]"])
)
