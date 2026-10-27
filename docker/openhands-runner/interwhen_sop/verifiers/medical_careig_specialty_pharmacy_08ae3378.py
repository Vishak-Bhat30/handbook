"""SOP verifiers for medical_careig_specialty_pharmacy_08ae3378.

Situation (seed data): case CIG_2026_0341 (Margaret Thornton, Privigen, Sunflower Health Commercial PPO) has a
signed visit note for DOS 2026-10-05; no claim exists yet. The acting user is Julio Martinez (Billing
Specialist), today 2026-10-08. Next SOP step = Section 10: pre-billing validation (all conditions pass), build
claim_CIG_2026_0341.xlsx from claim_blank.xlsx (partial infusion: 35.8 g of 40 g), email it to the payer
claims address with Template 7, set Submission_Date / Claim_Status, post CLAIM SUBMITTED in #billing and append
one audit row (Action = Claim Submitted). Every expected value is derived from the initial workbooks.
"""

from __future__ import annotations

import datetime as dt
import math
import re

from ..kit import (Comm, Context, Rule, World, append_only, attachments, comm_rules, dashes, money_rx, nh, no_placeholders,
                   norm, num, pre_rule, prior_denials, same, state_rule, world)

CASE = "CIG_2026_0341"
TODAY = "2026-10-08"            # system prompt
STAFF = "Julio Martinez"        # instruction: acting user
CLAIM = f"claim_{CASE}.xlsx"    # 4.4 File names: [filename]_[Case_ID]
CLAIM_RX = rf"(^|/){re.escape(CLAIM)}$"

# ---- SOP references ---------------------------------------------------------------------------------------------
R_ROLE = ("2", "Billing Specialist | claim.xlsx", "2 Roles & File Access")
R_APPEND = ("3", "audit_log.xlsx | Global audit trail", "3 File System Structure")
R_JCODES_RO = ("3", "jcodes.xlsx | J-codes and nursing codes (read-only)", "3 File System Structure")
R_DUR_RO = ("3", "infusion_duration.xlsx | Estimated visit length", "3 File System Structure")
R_TEMPLATES = ("3", "Template files | Blank form masters", "3 File System Structure")
R_AUDIT = ("4.1", "Append one row to audit_log.xlsx at each major checkpoint", "4.1 Audit Logging")
R_NO_DRUG_OON = ("4.3", "Do not bill any IVIG drug J-code when", "4.3 Prohibited Actions")
R_PREMED_DOC = ("4.3", "Do not bill pre-medication J-codes unless", "4.3 Prohibited Actions")
R_ADMIN_DOSE = ("4.3", "Do not use ordered dose for unit calculations", "4.3 Prohibited Actions")
R_DUP = ("4.3", "Do not submit a claim when claim.xlsx already has", "4.3 Prohibited Actions")
R_DATE = ("4.4", "Date: yyyy-mm-dd", "4.4 Formatting conventions")
R_TIME = ("4.4", "Time: h:mm AM/PM", "4.4 Formatting conventions")
R_FNAME = ("4.4", "File names: [filename]_[Case_ID]", "4.4 Formatting conventions")
R_WF9 = ("1", "9 | Billing validates", "5 Workflow Summary step 9")
R_VALID = ("10.1", "Before building claim.xlsx, confirm every condition", "10.1 Pre-Billing Validation")
R_COPY = ("10.2", "Copy claim_blank.xlsx to create the claim file", "10.2 Claim Construction")
R_JCODE = ("10.2", "Drug J-Code | Look up J-code in jcodes.xlsx", "10.2 Drug J-Code")
R_NURSE = ("10.2", "Nursing Code | If Visit_Duration_Minutes", "10.2 Nursing Code")
R_SALINE = ("10.2", "Saline | J7030", "10.2 Saline")
R_PREMED = ("10.2", "Pre-Medications | Parse visit_note.xlsx", "10.2 Pre-Medications")
R_SUPPLY = ("10.2", "Supplies | A4221", "10.2 Supplies")
R_HEADER = ("10.2", "Header / Auth Fields |", "10.2 Header / Auth Fields")
R_SPLIT = ("10.2", "Split-Bill (OON partner) |", "10.2 Split-Bill")
R_FREQ = ("10.2", "Claim_Frequency_Code | Enter 1", "10.2 Claim_Frequency_Code")
R_MOD = ("10.2", "Modifier | Read visit_note.xlsx col Route", "10.2 Modifier")
R_EMAIL = ("10.3", "Email to payer billing address", "10.3 Claim Submission")
R_UPDATE = ("10.3", "Update claim.xlsx: Submission_Date = today", "10.3 Claim Submission")
R_POST = ("10.3", "Post to #billing: CLAIM SUBMITTED", "10.3 Claim Submission")
R_LOG = ("10.3", "Log to audit_log.xlsx: Action = Claim Submitted", "10.3 Claim Submission")
R_TIMELY = ("12.2", "(today − claim.xlsx col DOS)", "12.2 Workflow Monitoring")
R_TOTAL = ("13.1", "Source: jcodes.xlsx. Always use", "13.1 HCPCS / J-Code Reference")
R_A4222 = ("13.1", "A4222 | Infusion pump supplies", "13.1 HCPCS / J-Code Reference")
R_PARTIAL = ("13.2", "Partial: ordered 30g, administered 20g", "13.2 Unit Calculation Examples")
R_T7_SUBJ = ("6", "SUBJECT: CLAIM SUBMISSION CareIG NPI:", "Template 7 subject")
R_T7_BODY = ("6", "Please find attached the claim for the following", "Template 7 body")
R_T7_SIGN = ("6", "[Billing Specialist Full Name]", "Template 7 sign-off")


# ---- facts from the initial workbooks ---------------------------------------------------------------------------

def _case_row(w: World, file_rx: str) -> dict:
    return w.find(file_rx, r"^CASE_ID$", r"^CASE_ID$", CASE, "initial") or {}


def _date(v) -> str:
    return str(v or "").strip()[:10]


def _num_rx(v: float) -> str:
    s = f"{v:g}"
    return re.escape(s) + ("0*" if "." in s else r"(?:\.0+)?")


def facts(ctx: Context) -> dict:
    def build():
        w = world(ctx)
        c = World.col
        intake, auth = _case_row(w, r"intake_CIG"), _case_row(w, r"auth_CIG")
        ben, clin, vn = _case_row(w, r"benefits_CIG"), _case_row(w, r"clinical_CIG"), _case_row(w, r"visit_note_CIG")
        payer_name = c(intake, r"^Primary_Insurance_Name$")
        payer = w.find(r"payer_rules", r"^Payer_Name$", r"^Payer_Name$", payer_name, "initial") or {}
        org = {c(r, r"^Field$"): c(r, r"^Value$") for r in w.rows(r"org_identifiers", r"^Field$", "initial")}
        fee = {c(r, r"^HCPCS_Code$"): num(c(r, r"^Billed_Rate$")) for r in w.rows(r"fee_schedule", r"^HCPCS_Code$", "initial")}
        trade = c(vn, r"^Drug_Name_Trade$")
        jrow = next((r for r in w.rows(r"jcodes", r"^HCPCS_Code$", "initial") if norm(c(r, r"^Drug_Name$")) == norm(trade)), {})
        given, ordered = num(c(vn, r"^Dose_Administered_Grams$")), num(c(vn, r"^Dose_Ordered_Grams$"))
        minutes = int(num(c(vn, r"^Visit_Duration_Minutes$")) or 0)
        drug_source = c(clin, r"^Drug_Source$")

        lines: dict[str, int] = {}
        drug_code = c(jrow, r"^HCPCS_Code$")
        if norm(drug_source) == "careig" and drug_code:
            lines[drug_code] = math.floor(given * 1000 / num(c(jrow, r"^Unit_Size_mg$")) + 1e-9)
        pref = c(ben, r"^Nursing_Code_Pref$")
        if pref in ("", "99600"):
            lines["99600"] = 1
            if minutes > 60:
                lines["99603"] = (minutes - 60) // 60
        if num(c(vn, r"^NS_500mL_Bags_Used$")):
            lines["J7030"] = int(num(c(vn, r"^NS_500mL_Bags_Used$")))
        if num(c(vn, r"^NS_250mL_Bags_Used$")):
            lines["J7050"] = int(num(c(vn, r"^NS_250mL_Bags_Used$")))
        premed = c(vn, r"^Premeds_Administered$")
        documented = re.search(r"\d+\s*mg\s+(IV|IM|PO|SQ|SC)\b.*\bat\s+\d{1,2}:\d{2}\s*(AM|PM)\s+for\s+\w", premed, re.I)
        m = re.search(r"Diphenhydramine\s+(\d+(?:\.\d+)?)\s*mg", premed, re.I)
        if m and documented:
            lines["J0171"] = int(float(m.group(1)) // 50)
        m = re.search(r"Promethazine\s+(\d+(?:\.\d+)?)\s*mg", premed, re.I)
        if m and documented:
            lines["J2550"] = int(float(m.group(1)) // 25)
        lines["A4221"] = 1
        if norm(c(vn, r"^Pump_Used$")) == "yes":
            lines["A4222"] = 1
        total = round(sum(u * fee[k] for k, u in lines.items()), 2)

        dos = _date(c(vn, r"^Visit_Date$"))
        header = {
            "CASE_ID": (CASE, R_HEADER), "DOS": (dos, R_HEADER),
            "Patient_Last_Name": (c(intake, r"^Patient_Last_Name$"), R_HEADER),
            "Patient_First_Name": (c(intake, r"^Patient_First_Name$"), R_HEADER),
            "Patient_DOB": (_date(c(intake, r"^DOB$")), R_HEADER),
            "Member_ID": (c(intake, r"^Primary_Member_ID$"), R_HEADER),
            "Group_Number": (c(intake, r"^Group_Number$"), R_HEADER),
            "Payer_Name": (payer_name, R_HEADER), "Payer_Type": (c(ben, r"^Payer_Type$"), R_HEADER),
            "PA_Number": (c(auth, r"^PA_Number$"), R_HEADER),
            "Physician_NPI": (c(intake, r"^Physician_NPI$"), R_HEADER),
            "CareIG_NPI": (c(payer, r"^CareIG_NPI$"), R_HEADER),
            "CareIG_Tax_ID": (c(payer, r"^CareIG_Tax_ID$"), R_HEADER),
            "CareIG_Taxonomy_Code": (org.get("CareIG_Taxonomy_Code", ""), R_HEADER),
            "Diagnosis_ICD10": (c(intake, r"^Diagnosis_ICD10$"), R_HEADER),
            "Drug_Source": (drug_source, R_SPLIT),
            "Billing_Model": (None if norm(drug_source) == "careig" else "Split", R_SPLIT),
            "Drug_Modifier": (None if norm(c(vn, r"^Route$")) == "iv" else "SC", R_MOD),
            "Claim_Frequency_Code": ("1", R_FREQ),
            "Total_Billed": (f"{total:.2f}", R_TOTAL),
        }
        note = note_rx = None
        if given is not None and ordered is not None and given < ordered:
            note = f"Ordered {ordered:g}g, administered {given:g}g. Billed on administered dose."
            note_rx = (rf"^Ordered\s*{_num_rx(ordered)}\s*g\s*,?\s*administered\s*{_num_rx(given)}\s*g\s*[.;,]?\s*"
                       r"Billed on administered dose\.?$")

        # 10.1 conditions, evaluated on the seed (all TRUE here -> no BILLING HOLD applies)
        cov_from, cov_to = _date(c(ben, r"^Coverage_Effective_Date$")), _date(c(ben, r"^Coverage_Term_Date$"))
        holds = {
            "BILLING HOLD — UNSIGNED NOTE": bool(c(vn, r"^Nurse_Signature$")),
            "BILLING HOLD — NO PA APPROVAL": norm(c(auth, r"^PA_Status$")) == "approved",
            "BILLING HOLD — PA NUMBER MISSING": bool(c(auth, r"^PA_Number$")),
            "BILLING HOLD — PA EXPIRED ON DOS": _date(c(auth, r"^PA_Expiration_Date$")) >= dos,
            "BILLING HOLD — DRUG MISMATCH": norm(c(auth, r"^PA_Approved_Drug$")) == norm(trade),
            "BILLING HOLD — DOSE EXCEEDS PA": (num(c(auth, r"^PA_Approved_Dose$")) or 0) >= (given or 0),
            "BILLING HOLD — ICD10 INCONSISTENT": norm(c(auth, r"^Diagnosis_ICD10$")) in ("", norm(c(intake, r"^Diagnosis_ICD10$"))),
            "BILLING HOLD — DOSE NOT DOCUMENTED": (given or 0) > 0,
            "DUPLICATE CLAIM RISK": not w.books(r"(^|/)claim_CIG", "initial"),
            "BILLING HOLD — COVERAGE NOT CONFIRMED": bool(cov_from) and cov_from <= dos <= cov_to,
        }
        return {"lines": lines, "fee": fee, "total": total, "header": header, "note": note, "note_rx": note_rx,
                "dos": dos, "drug_code": drug_code, "claims_to": c(payer, r"^Claim_Submission_Email$").lower(),
                "payer": payer_name, "intake": intake, "org": org, "holds": holds,
                "timely_days": num(c(payer, r"^Timely_Filing_Days$"))}
    return ctx.memo("careig08.facts", build)


# ---- claim file -------------------------------------------------------------------------------------------------

def claim_problems(ctx: Context, submitted: bool) -> list[tuple[str, list]]:
    """(problem, refs) for claim_CIG_2026_0341.xlsx; ``submitted`` adds the 10.3 Submission_Date / Claim_Status."""
    f, w = facts(ctx), world(ctx)
    if not w.book(CLAIM_RX)[0]:
        return [(f"{CLAIM} does not exist yet. Copy claim_blank.xlsx to {CLAIM} and fill the Claim Header and Claim "
                 f"Lines sheets (expected lines: {_lines_hint(f)}; Total_Billed {f['total']:.2f}).", [R_COPY, R_FNAME])]
    out: list[tuple[str, list]] = []
    heads = w.rows(CLAIM_RX, r"^Total_Billed$", sheet_rx="Header")
    rows = [r for r in heads if norm(World.col(r, r"^CASE_ID$")) == norm(CASE)]
    if len(rows) != 1 or len(heads) != 1:
        out.append((f"{CLAIM} sheet 'Claim Header' must hold exactly one data row for {CASE} "
                    f"(found {len(rows)} for the case, {len(heads)} non-empty in total).", [R_COPY]))
    if rows:
        h = rows[0]
        exp = dict(f["header"])
        if submitted:
            exp["Submission_Date"] = (TODAY, R_UPDATE)
            exp["Claim_Status"] = ("Submitted", R_UPDATE)
        for col, (want, ref) in exp.items():
            got = World.col(h, rf"^{col}$")
            if col in ("DOS", "Patient_DOB", "Submission_Date"):
                ok = _date(got) == want
            else:
                ok = same(got, want)
            if not ok:
                out.append((f"Claim Header {col} must be {want if want is not None else '(blank)'!s} (got "
                            f"'{got}').", [ref] + ([R_DATE] if col in ("DOS", "Patient_DOB", "Submission_Date") else [])))
        got = nh(World.col(h, r"^Partial_Infusion_Note$"))
        if f["note"] and not re.match(f["note_rx"], got, re.I):
            out.append((f"Claim Header Partial_Infusion_Note must read: {f['note']} (got '{got}').", [R_PARTIAL]))
        if not f["note"] and got:
            out.append(("Partial_Infusion_Note must stay blank (full dose administered).", [R_PARTIAL]))

    lines = [r for r in w.rows(CLAIM_RX, r"^HCPCS_Code$", sheet_rx="Lines") if World.col(r, r"^HCPCS_Code$")]
    seen: dict[str, list[dict]] = {}
    for r in lines:
        seen.setdefault(World.col(r, r"^HCPCS_Code$").upper().split(".")[0], []).append(r)
    refs_of = {f["drug_code"]: [R_JCODE, R_ADMIN_DOSE], "99600": [R_NURSE], "99603": [R_NURSE], "J7030": [R_SALINE],
               "J7050": [R_SALINE], "J0171": [R_PREMED, R_PREMED_DOC], "J2550": [R_PREMED, R_PREMED_DOC],
               "A4221": [R_SUPPLY], "A4222": [R_SUPPLY, R_A4222]}
    for code, units in f["lines"].items():
        rs = seen.get(code, [])
        rate = f["fee"][code]
        if len(rs) != 1:
            out.append((f"Claim Lines needs exactly one {code} line with Units {units}, Billed_Rate {rate:.2f}, "
                        f"Line_Total {units * rate:.2f} (found {len(rs)}).", refs_of.get(code, [R_COPY])))
            continue
        r = rs[0]
        got_u, got_r, got_t = (World.col(r, rx) for rx in (r"^Units$", r"^Billed_Rate$", r"^Line_Total$"))
        if not same(got_u, units):
            out.append((f"Claim line {code}: Units must be {units} (got '{got_u}').", refs_of.get(code, [R_COPY])))
        if got_r and not same(got_r, rate):
            out.append((f"Claim line {code}: Billed_Rate must be {rate:.2f} from fee_schedule.xlsx (got '{got_r}').",
                        [R_TOTAL]))
        if got_t and not same(got_t, units * rate):
            out.append((f"Claim line {code}: Line_Total must be {units * rate:.2f} (got '{got_t}').", [R_TOTAL]))
        if code == f["drug_code"] and not same(World.col(r, r"^Modifier$"), f["header"]["Drug_Modifier"][0]):
            out.append((f"Claim line {code}: Modifier must be blank for Route IV.", [R_MOD]))
    for code, rs in seen.items():
        if code not in f["lines"] and any((num(World.col(r, r"^Units$")) or 0) > 0 for r in rs):
            why = {"J1459": [R_NO_DRUG_OON], "J2550": [R_PREMED_DOC], "G0153": [R_NURSE], "99603": [R_NURSE]}
            out.append((f"Claim line {code} is not billable for this visit; remove it (bill only: {_lines_hint(f)}).",
                        why.get(code, [R_COPY])))
    return out


def _lines_hint(f: dict) -> str:
    return ", ".join(f"{k} x {u}" for k, u in f["lines"].items())


def _claim_state(ctx: Context):
    for prob, refs in claim_problems(ctx, submitted=True):
        yield False, prob, refs


# ---- messages ---------------------------------------------------------------------------------------------------

def _is_claim_email(f: dict, a) -> bool:
    return a.kind == "email_send" and bool(
        re.search(r"\bclaim", a.subject, re.I) or f["claims_to"] in a.recipients
        or any(re.search(r"^claim", x, re.I) for x in attachments(a)))


def _is_claim_post(a) -> bool:
    return a.kind in ("slack_post", "slack_dm") and "CLAIM SUBMITTED" in a.text


HOLD_RX = r"BILLING HOLD|DUPLICATE CLAIM RISK|TIMELY FILING RISK"


def specs(ctx: Context) -> list[Comm]:
    f = facts(ctx)
    i = f["intake"]
    c = World.col
    last, member, npi = c(i, r"^Patient_Last_Name$"), c(i, r"^Primary_Member_ID$"), f["header"]["CareIG_NPI"][0]
    bar = r"\s*\|\s*"
    subject = bar.join([rf"CLAIM SUBMISSION CareIG NPI:\s*{re.escape(npi)}", re.escape(last),
                        rf"MemberID:\s*{re.escape(member)}", rf"DOS:\s*{re.escape(f['dos'])}"])
    subject_hint = f"CLAIM SUBMISSION CareIG NPI: {npi} | {last} | MemberID: {member} | DOS: {f['dos']}"
    vals = [(member, "Member ID " + member), (f["dos"], "Date of Service " + f["dos"]),
            (_date(c(i, r"^DOB$")), "DOB " + _date(c(i, r"^DOB$"))), (c(i, r"^Group_Number$"), "Group " + c(i, r"^Group_Number$")),
            (f["header"]["PA_Number"][0], "PA Number " + f["header"]["PA_Number"][0]),
            (npi, "NPI " + npi), (f["header"]["CareIG_Tax_ID"][0], "Tax ID " + f["header"]["CareIG_Tax_ID"][0]),
            (f["org"].get("CareIG_Taxonomy_Code", ""), "Taxonomy " + f["org"].get("CareIG_Taxonomy_Code", "")),
            (c(i, r"^Physician_NPI$"), "Referring Physician NPI " + c(i, r"^Physician_NPI$")),
            (c(i, r"^Diagnosis_ICD10$"), "Diagnosis " + c(i, r"^Diagnosis_ICD10$")),
            (STAFF, f"sign-off {STAFF}")]
    body = [(re.escape(v), d) for v, d in vals if v]
    body.append((rf"Total Billed:\s*{money_rx(f['total'])}", f"Total Billed: ${f['total']:,.2f}"))
    post = (rf"CLAIM SUBMITTED {CASE}{bar}DOS:\s*{re.escape(f['dos'])}{bar}Payer:\s*{re.escape(f['payer'])}{bar}"
            rf"Billed:\s*{money_rx(f['total'])}")
    post_hint = f"CLAIM SUBMITTED {CASE} | DOS: {f['dos']} | Payer: {f['payer']} | Billed: {f['total']:,.2f}"
    out = [
        Comm("claim_email", "email", lambda a: _is_claim_email(f, a),
             "Claim submission email to the payer (Template 7)", [R_EMAIL, R_T7_SUBJ, R_T7_BODY, R_WF9, R_DUP],
             to=[f["claims_to"]], subject=subject, subject_hint=subject_hint, body=body,
             attach=[(rf"^{re.escape(CLAIM)}$", CLAIM)], exact_to=False),
        Comm("claim_posted", "slack_post", _is_claim_post, "CLAIM SUBMITTED post in #billing", [R_POST, R_WF9],
             channel="billing", body=[(post, post_hint)]),
    ]
    clear = [k for k, ok in f["holds"].items() if ok]
    try:
        days = (dt.date.fromisoformat(TODAY) - dt.date.fromisoformat(f["dos"])).days
    except ValueError:
        days = None
    if len(clear) == len(f["holds"]) and days is not None and f["timely_days"] and days < 0.8 * f["timely_days"]:
        out.append(Comm("no_hold", "slack_post", lambda a: a.kind in ("slack_post", "slack_dm", "email_send")
                        and bool(re.search(HOLD_RX, a.text + " " + a.subject, re.I)),
                        "Billing hold / duplicate / timely-filing alert", [R_VALID, R_TIMELY],
                        forbidden=("Every 10.1 pre-billing condition is TRUE for this case (note signed, PA "
                                   f"{f['header']['PA_Number'][0]} approved and valid on DOS {f['dos']}, Privigen "
                                   "matches, administered dose within the approved dose, ICD-10 consistent, coverage "
                                   f"active, no prior claim) and only {days} of {f['timely_days']:g} filing days have "
                                   "elapsed, so no hold/risk alert applies. Build and submit the claim instead."),
                        required=False))
    return out


def _post_before_submit(ctx: Context, a) -> str | None:
    if not _is_claim_post(a) or prior_denials(ctx, "[post-order]") >= 2:
        return None
    f, w = facts(ctx), world(ctx)
    if any(_is_claim_email(f, e) for e in w.comms()):
        return None
    return ("[post-order] Post CLAIM SUBMITTED only after the claim email has actually been sent to "
            f"{f['claims_to']} (10.3 order: email the claim, update claim.xlsx, then post).")


def _claim_not_ready(ctx: Context, a) -> str | None:
    f = facts(ctx)
    if not _is_claim_email(f, a) or prior_denials(ctx, "[claim-not-ready]") >= 2:
        return None
    probs = claim_problems(ctx, submitted=False)
    if not probs:
        return None
    return ("[claim-not-ready] The claim file must be complete and correct before it is emailed to the payer: "
            + " ".join(p for p, _ in probs[:8]))


# ---- audit log + file scope -------------------------------------------------------------------------------------

def _audit(ctx: Context):
    w, f = world(ctx), facts(ctx)
    c = World.col
    new = w.new_rows(r"audit_log", r"^CASE_ID$")
    want = (f"{TODAY} h:mm AM/PM | {CASE} | Claim Submitted | {CLAIM} | Claim_Status | Submitted | {STAFF} | SUCCESS")
    hits = [r for r in new if norm(c(r, r"^Action$")) == "claim submitted"]
    yield bool(hits), f"audit_log.xlsx has no Claim Submitted row. Append exactly: {want}", [R_LOG, R_AUDIT]
    yield len(hits) <= 1, (f"audit_log.xlsx has {len(hits)} Claim Submitted rows; the checkpoint gets exactly one "
                           f"row ({want}). Remove the extra row(s)."), [R_AUDIT, R_LOG]
    for r in hits[:1]:
        checks = [(norm(c(r, r"^CASE_ID$")) == norm(CASE), "CASE_ID", CASE, [R_AUDIT]),
                  (bool(re.fullmatch(rf"{TODAY} \d{{1,2}}:\d{{2}} (AM|PM)", nh(c(r, r"^Date")))), "Date_Time",
                   f"{TODAY} h:mm AM/PM (e.g. {TODAY} 9:30 AM)", [R_AUDIT, R_DATE, R_TIME]),
                  (bool(re.fullmatch(rf"claim(_{CASE})?\.xlsx", nh(c(r, r"^File_Updated$")), re.I)), "File_Updated", CLAIM, [R_AUDIT]),
                  (norm(c(r, r"^Field_Updated$")) == "claim_status", "Field_Updated", "Claim_Status", [R_LOG]),
                  (norm(c(r, r"^New_Value$")) == "submitted", "New_Value", "Submitted", [R_AUDIT]),
                  (norm(c(r, r"^Staff_User$")) == norm(STAFF), "Staff_User", STAFF, [R_AUDIT]),
                  (norm(c(r, r"^Result$")) == "success", "Result", "SUCCESS", [R_AUDIT])]
        for ok, col, val, refs in checks:
            yield ok, f"Claim Submitted audit row: {col} must be {val} (got '{c(r, '^' + col.split('_')[0])}').", refs
    extra = [r for r in new if norm(c(r, r"^Action$")) not in ("claim submitted", "out-of-scope access")]
    yield not extra, ("audit_log.xlsx has row(s) that are not an SOP checkpoint for this step "
                      f"(Action = {', '.join(repr(c(r, '^Action$')) for r in extra)}); only log the Claim Submitted "
                      "checkpoint - remove them."), [R_AUDIT]


def _scope(ctx: Context):
    w = world(ctx)
    changed = w.changed_files(keep_rx=rf"(^|/)audit_log\.xlsx$|{CLAIM_RX}")
    yield not changed, (f"These files must not be modified in the billing step (Billing Specialist writes only "
                        f"{CLAIM} and the audit log; templates and reference tables are never edited): "
                        f"{', '.join(changed)}. Restore their original content."), [R_ROLE, R_TEMPLATES, R_JCODES_RO, R_DUR_RO]
    extra = [b for b in w.created_books() if not re.search(CLAIM_RX, b)]
    yield not extra, (f"Unrequested new workbook(s) {', '.join(extra)}: the only new file for this step is {CLAIM}. "
                      "Remove them."), [R_COPY, R_FNAME]


RULES: list[Rule] = [
    *comm_rules("billing", specs),
    *pre_rule("billing.claim_ready", _claim_not_ready, [R_COPY, R_EMAIL], "Fix the claim file first, then send."),
    *pre_rule("billing.post_after_submit", _post_before_submit, [R_EMAIL, R_POST], "Send the claim email first."),
    *no_placeholders([R_T7_SIGN]),
    *state_rule("billing.claim_file", _claim_state, "Correct the claim file as listed."),
    *state_rule("audit.claim_submitted", _audit, "Fix audit_log.xlsx as listed."),
    *append_only("audit.append_only", r"audit_log", r"^CASE_ID$", "audit_log.xlsx", [R_APPEND]),
    *state_rule("files.scope", _scope, "Restore / remove the files listed."),
]
