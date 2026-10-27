"""Verifiers for insurance_mojave_crest_assurance_company_4d2a2588 (MCA Appeals & Grievances Desk Manual v2.1).

Situation on 2026-11-04 (Jordan Mills, Appeals & Grievances Coordinator), derived from the SOP and seed data only:
- CASE-2026-00441 (VA-55219-07): concurrent-care SUD residential appeal received 2026-11-03 14:15; termination
  effective 2026-11-05 10:00 (< 72 h) -> that is the decision deadline; letter alleges stricter SUD criteria than
  medical rehab -> parity flag: B-3 DM to the Parity Review Committee, B-1 DM to Dr. Ontario + #appeals-urgent tag,
  B-2 escalation to @dwhitfield, expedited A-1 acknowledgment (24 h, due 2026-11-04 14:15), no determination letter.
- CASE-2026-00442 (VA-31802-04): post-service appeal filed by the provider without AOR -> immediate dismissal,
  Template A-4 Immediate Dismissal Variant saved as a draft (not sent) and Slacked to @dwhitfield for review.
- CASE-2026-00437 (VA-62883-11): member says the billed service never happened -> B-6 DM to @kdufree, clock
  unchanged; no outbound contact since 10/17 (> 14 days) -> status update email (no fraud mention, no reviewer name).
- Roberto Casillas (VA-88291-03) appeal received 2026-11-04 07:32 (timely: 173 days after the 2026-05-15 denial)
  -> open CASE-2026-00443 (post-service standard, plan year 2024), A-1 acknowledgment, B-1 to the clinical queue,
  B-2 "Exceeds Coordinator Authority" ($28,400 billed > $25,000).
"""

from __future__ import annotations

import datetime as dt
import json
import re

from ..kit import (COMM_KINDS, WRITE_KINDS, Action, Comm, World, blank, comm_rules, dashes, no_placeholders, norm,
                   pre_rule, prior_denials, same, state_rule, strict_writes, world)

LOG = r"appeals_log_master\.xlsx$"
HDR = r"^Case ID$"
SHEET = r"^Appeals Log$"
EMAILS = ("email_send", "email_draft")
SLACK = ("slack_post", "slack_dm")
CHANNEL_IDS = {"appeals-intake": "C001", "appeals-clinical-queue": "C002", "appeals-urgent": "C003",
               "appeals-parity": "C004", "appeals-compliance": "C005", "appeals-general": "C006"}

TORRES, FIERRO, CASILLAS, SWDO = ("d.torres.personal@gmail.com", "j.fierro.personal@gmail.com",
                                  "r.casillas.personal@gmail.com", "appeals@swdesertortho.com")
# member id -> (names, external addresses that legitimately receive that member's information)
MEMBERS = {
    "VA-62883-11": (("Daniela Torres", "Torres, Daniela"), (TORRES,)),
    "VA-55219-07": (("Joanna Fierro", "Fierro, Joanna"), (FIERRO,)),
    "VA-31802-04": (("Elena Novak", "Novak, Elena"), (SWDO,)),
    "VA-88291-03": (("Roberto Casillas", "Casillas, Roberto"), (CASILLAS,)),
    "VA-41905-06": (("Patricia Chen", "Chen, Patricia"), ()),
    "VA-20915-02": (("Theo Reinholt", "Reinholt, Theo"), ()),
}
PHI_PUBLIC = [r"\bVA-\d{5}-\d{2}\b", r"\b(Torres|Fierro|Novak|Casillas|Daniela|Joanna|Elena|Roberto)\b",
              r"\b(DOB|date of birth)\b", r"\b(0?[1-9]|1[0-2])/(0?[1-9]|[12]\d|3[01])/19\d\d\b",
              r"\b(F11\.20|F14\.20|M17\.31|M54\.42|S33\.5XXA)\b"]
REVIEWERS = r"\b(Alvarado|Bergstrom|Ontario|Henning)\b|\bMarisol\b|\bDr\.?\s+(Helena|Ayla|Jules)\b"
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


# ---- SOP references (section, paragraph prefix, label) --------------------------------------------------------------
R_ACK_ROLE = ("1.3", "Sending the acknowledgment letter within the required window", "1.3 acknowledgment")
R_CH = ("2.4", "Channel Purpose #appeals-intake", "2.4 Slack channels / PHI")
R_CASEID = ("2.4", "Case ID Assignment: When you create a new row", "2.4 Case ID assignment")
R_ERO = ("2.3", "MCA contracts with a single independent review organization", "2.3 External Review Organization")
R_PROV_STAND = ("4.1", "A treating provider, on the member's behalf, for pre-service and concurrent care appeals only",
                "4.1 provider standing")
R_PROV_EXC = ("4.1", "Exception: If the requester is a provider attempting to file a post-service appeal",
              "4.1 provider post-service exception")
R_CONC = ("4.3.3", "A concurrent care appeal is an appeal of a reduction", "4.3.3 concurrent care")
R_CONC_DL = ("4.3.3", "The decision deadline for concurrent care appeals", "4.3.3 concurrent deadline")
R_POST = ("4.3.4", "A post-service appeal is an appeal of a denied", "4.3.4 post-service appeal")
R_RECEIPT = ("5.1", "Every appeal has a regulatory clock.", "5.1 clock starts at receipt")
R_RECEIPT2 = ("5.1", "When you open a case, the", "5.1 date of receipt")
R_TIMES = ("5.2", "The following are MCA's internal timeline rules", "5.2 timelines")
R_CAL = ("5.3", "Calendar days include every day", "5.3 calendar days")
R_TOLL = ("2", "Mojave Crest Assurance, Appeals & Grievances Desk Manual Tolling is one time only",
          "5.4 tolling not available for expedited")
R_SETCLOCK = ("3", "7. Set the regulatory clock.", "6.1 step 7 set the clock")
R_ACK_STEP = ("8", "acknowledgment timeline (Section 5.2). Use the correct letter template", "6.1 step 8 acknowledgment")
R_ROUTE_STEP = ("8", "9. Route the case.", "6.1 step 9 routing")
R_LOG_STEP = ("8", "10. Log the case in the Appeals Log", "6.1 step 10 log the case")
R_ESC_FIRST = ("7", "If the answer to question 6 or question 7 is yes", "6.2 escalate before finishing intake")
R_MEDNEC = ("7.1", "Your job is to make sure the right clinical reviewer", "7.1 medical-necessity wording")
R_B1 = ("7.3", "Once you have classified the appeal and identified the correct standard",
        "7.3 Format B-1 routing")
R_B1_EXP = ("7.3", "Any parity flag status (see Section 8) For expedited cases", "7.3 expedited routing")
R_PAR_WHY = ("8.1", "A parity violation is a serious compliance matter.", "8.1 parity flags")
R_PAR_IND = ("8.2", "The member's letter mentions disparate treatment", "8.2 parity indicator")
R_PAR_REPL = ("8.3", "When a parity flag is raised, the parity review replaces", "8.3 parity routing")
R_PAR_EXCL = ("8.3", "Parity-flagged cases are routed exclusively", "8.3 parity routing exclusive")
R_B3 = ("2", "2. Send a Parity Flag Notification using Slack Format B-3", "8.3 step 2 Format B-3")
R_B3_DM = ("2", "committee. Do not post this message in #appeals-parity", "8.3 step 2 not in #appeals-parity")
R_ONTARIO = ("2", "3. Route the case to Dr. Ayla Ontario", "8.3 step 3 route to Dr. Ontario")
R_PAR_NOLETTER = ("4", "4. Do not issue a determination letter on a parity flagged case", "8.3 step 4")
R_CONCUR = ("8.3.1", "Parity Committee Concurrence Slack format", "8.3.1 parity concurrence")
R_TIER = ("9.1.1", "The following tiers define the maximum total dispute value", "9.1.1 authority tiers")
R_DISMISS_IND = ("9.1.2", "Dismiss cases for clear lack of standing", "9.1.2 dismissals")
R_DRAFT_DET = ("9.1.2", "Draft determination letters from approved templates", "9.1.2 determination letters")
R_CLOSE = ("9.1.2", "Close cases in the Appeals Log after the determination letter", "9.1.2 closing cases")
R_NO_DET = ("9.1.3", "Issue a determination letter without a clinical reviewer's signed determination",
            "9.1.3 no letter without clinical determination")
R_NO_REG = ("9.1.3", "Contact defense counsel, the Nevada Division of Insurance", "9.1.3 regulators")
R_NO_SETTLE = ("9.1.3", "Settle a case by offering payment", "9.1.3 settlements")
R_NO_COMMIT = ("9.1.3", "Commit MCA to any future benefit coverage", "9.1.3 coverage commitments")
R_TRIGGERS = ("9.2", "Escalate to your Appeals Supervisor (Darnell Whitfield) via Slack Format B-2",
              "9.2 mandatory escalation")
R_TRIG_PARITY = ("8", "8. A parity flag has been raised", "9.2 trigger 8 parity flag")
R_TRIG_CONC = ("12", "receiving care that would end in the next 72 hours", "9.2 trigger 12 concurrent care")
R_ESC_DM = ("1", "Appeals Supervisor). Do not post escalations in public channels.", "9.3 escalation by DM")
R_ESC_FIELDS = ("1", "2. Include: Case ID, appeal type, decision deadline", "9.3 escalation contents")
R_ESC_WAIT = ("1", "3. Do not take the action that requires escalation approval", "9.3 wait for approval")
R_CONC_ROUTE = ("3", "4. Route immediately to the appropriate clinical reviewer (RN Reviewer team for M/S, Dr. Ontario",
                "10.3 step 4 concurrent routing")
R_CONC_COVER = ("3", "authorization will lapse while the appeal is pending.", "10.3 step 3 coverage continues")
R_POST_ACK = ("10.4", "1. Acknowledge within 5 business days using Template A-1.", "10.4 step 1 acknowledgment")
R_FRAUD = ("3", "4. If there is any dispute about whether a service was actually delivered", "10.4 step 4 fraud flag")
R_FRAUD_OUT = ("3", "Fraud Review Outcome:", "10.4 fraud review outcome")
R_POST_ROUTE = ("5", "5. Route to clinical review if medical necessity is in dispute", "10.4 step 5 routing")
R_EXT = ("10.6", "When MCA has issued a final adverse determination on an internal appeal", "10.6 external review")
R_UNTIMELY = ("11.2", "Untimely filing: the appeal was received more than 180", "11.2 untimely filing")
R_DISMISS_SUP = ("11.2", "Supervisor review is required for all dismissal letters", "11.2 dismissal review")
R_STATUS = ("12.1", "Communication Timeline Initial acknowledgment", "12.1 contact timelines / status update")
R_STATUS_LOG = ("12.1", "Log the status update in the Case Timeline Tracker", "12.1 log the status update")
R_TONE = ("12.2", "Members who are writing to the appeals unit are often frustrated", "12.2 tone")
R_SPECULATE = ("12.2", "Never speculate about coverage in correspondence", "12.2 no speculation")
R_OUTSIDE = ("12.5", "Discussing open appeals with the press", "12.5 outside parties")
R_PROMISE = ("12.2", "Never make promises about payment amounts", "12.2 no promises")
R_SIGN = ("12.2", "Always sign correspondence with your full name", "12.2 signature")
R_SUBJ = ("12.3", "All outbound emails to members or providers must include the Case ID", "12.3 subject line")
R_REVNAME = ("12.3", "Do not include the reviewer's name in correspondence", "12.3 reviewer names")
R_PHI = ("12.4", "Never post PHI (member name", "12.4 no PHI in public Slack")
R_CASEREF = ("12.4", "Use the Case ID (CASE-YYYY-NNNNN format) in any public channel reference", "12.4 Case ID only")
R_DMUSE = ("12.4", "Use DM for escalations, parity flags", "12.4 DMs")
R_FORMATS = ("12.4", "Use the Slack formats in Appendix B", "12.4 Slack formats")
R_BACKDATE = ("12.5", "Backdating any document, correspondence, or log entry", "12.5 backdating")
R_NO_DET2 = ("12.5", "Issuing a determination letter without the required clinical review", "12.5 prohibited")
R_PHI_OUT = ("12.5", "Sharing PHI outside of MCA's secure email environment", "12.5 PHI")
R_DOI = ("12.5", "Contacting the Nevada Division of Insurance directly", "12.5 DOI contact")
R_COMMIT2 = ("12.5", "Issuing a benefit authorization, payment, or other coverage commitment", "12.5 commitments")
R_A1 = ("13", "Template A-1 - Acknowledgment Letter", "Appendix A Template A-1")
R_A1_FIELDS = ("13", "Case Number: [CASE ID] Member Name:", "Template A-1 case details")
R_A4_VAR = ("13", "--- IMMEDIATE DISMISSAL VARIANT", "Template A-4 Immediate Dismissal Variant")
R_A4_TEXT = ("13", "Post-service appeals filed by a provider require", "Template A-4 variant text")
R_A4_SUBJ = ("13", "Sincerely, [YOUR NAME] Appeals & Grievances Coordinator Mojave Crest Assurance Company Case #: "
                   "[CASE ID] Template A-4", "Template A-4 subject")
R_EXP_HDR = ("13", "--- EXPEDITED REVIEW --- Expedited Basis:", "Expedited Acknowledgment Header Block")
R_B1_FMT = ("13", "Format B-1 - Clinical Routing", "Appendix B Format B-1")
R_B1_FIELDS = ("13", "CLINICAL ROUTING Case #:", "Format B-1 fields / Format B-2 target")
R_B2_FIELDS = ("13", "ESCALATION Case #:", "Format B-2 fields / Format B-3 target")
R_B3_FIELDS = ("13", "Mojave Crest Assurance, Appeals & Grievances Desk Manual PARITY FLAG Case #:", "Format B-3 fields")
R_B6_POST = ("13", "APPEAL MILL FLAG Case #:", "Format B-6 target")
R_B6_FIELDS = ("13", "Mojave Crest Assurance, Appeals & Grievances Desk Manual SUSPECTED CLAIM FRAUD",
               "Format B-6 fields")
R_B6_NOMENTION = ("13", "[Will continue on regular clock] Case Folder:", "Format B-6 no mention to member")
R_COLUMNS = ("13", "Mojave Crest Assurance, Appeals & Grievances Desk Manual Appendix C", "Appendix C tracker")
R_COLDESC = ("13", "Column Name Description Example Case ID", "Appendix C columns")
R_COLDESC2 = ("5.1", "Acknowledgment Due Calculated by formula", "Appendix C columns (cont.)")
R_COLDESC3 = ("5.1", "Mojave Crest Assurance, Appeals & Grievances Desk Manual Column Name Description Example Outcome",
              "Appendix C columns (cont.)")


# ---- helpers ---------------------------------------------------------------------------------------------------------

def date_rx(y: int, m: int, d: int, year_optional: bool = False) -> str:
    mn, ab = MONTHS[m - 1], MONTHS[m - 1][:3]
    alts = [rf"{y}-{m:02d}-{d:02d}", rf"0?{m}/0?{d}/(?:{y}|{y % 100})(?!\d)",
            rf"(?:{mn}|{ab}\.?)\s+0?{d}(?:st|nd|rd|th)?,?\s+{y}", rf"0?{d}\s+(?:{mn}|{ab}\.?),?\s+{y}"]
    if year_optional:
        alts += [rf"(?:{mn}|{ab}\.?)\s+0?{d}(?!\d)", rf"(?<![\d/])0?{m}/0?{d}(?![\d/])"]
    return "(?:" + "|".join(alts) + ")"


def is_ch(a: Action, name: str) -> bool:
    ch = str(a.channel or "").lstrip("#")
    return ch in (name, CHANNEL_IDS.get(name, "\0"))


def ext(addr: str) -> bool:
    return not str(addr).lower().endswith("@mojavecrest.com")


def body(a: Action) -> str:
    return dashes(f"{a.subject}\n{a.text}")


def _seed_email(w: World, eid) -> dict | None:
    return next((e for e in w.seed_emails if str(e.get("email_id")) == str(eid)), None)


def _draft_action(w: World, draft_id) -> Action | None:
    for e in w.state.executed:
        if e.action.kind == "email_draft" and re.search(rf'"draft_id"\s*:\s*"?{re.escape(str(draft_id))}"?\b',
                                                        e.result or ""):
            return e.action
    return None


def resolved(w: World, a: Action) -> tuple[list[str], str, str]:
    """(recipients incl. cc, subject, text) of an email call; replies take the original sender/subject and
    send_draft takes the saved draft."""
    rec, subj, text = [*a.recipients, *a.cc], a.subject, a.text
    if a.kind == "email_send" and "draft" in a.tool and a.args.get("draft_id") is not None:
        d = _draft_action(w, a.args.get("draft_id"))
        if d is not None:
            rec, subj, text = rec or [*d.recipients, *d.cc], subj or d.subject, text or d.text
    if a.kind == "email_send" and "reply" in a.tool:
        e = _seed_email(w, a.args.get("email_id") or a.args.get("message_id"))
        if e is not None:
            rec = rec or [str(e.get("from_addr", "")).lower()]
            subj = subj or ("" if re.match(r"re:", str(e.get("subject", "")), re.I) else "RE: ") + str(
                e.get("subject", ""))
    return [r.lower() for r in rec], subj, text


def outbound_external(w: World, a: Action) -> tuple[list[str], str, str] | None:
    """For emails to anyone outside @mojavecrest.com: (external recipients, subject, text); else None."""
    if a.kind not in EMAILS:
        return None
    rec, subj, text = resolved(w, a)
    out = [r for r in rec if ext(r)]
    return (out, subj, text) if out else None


def soft(ctx, tag: str, msg: str | None) -> str | None:
    """Relent after two denials of the same semantic check (precision first)."""
    if msg and prior_denials(ctx, tag) >= 2:
        return None
    return msg


def cases_in(s: str) -> set[str]:
    return set(re.findall(r"CASE-\d{4}-\d{5}", s or ""))


def slack_text(a: Action) -> str:
    return a.text if a.kind in SLACK else ""


# ---- message specifications ----------------------------------------------------------------------------------------

D_1105 = date_rx(2026, 11, 5, year_optional=True)
D_0103 = date_rx(2027, 1, 3)
SIG = [(r"Jordan Mills", "the signature with the full name Jordan Mills"),
       (r"\(?702\)?[\s.-]*555[\s.-]*0148", "the Appeals Unit phone number (702) 555-0148")]


def _email_about(case: str, addr: str, subj_rx: str):
    def about(a: Action) -> bool:
        if a.kind not in EMAILS:
            return False
        hit = case in f"{a.subject}\n{a.text}" or addr in [r.lower() for r in (*a.recipients, *a.cc)]
        return hit and bool(re.search(subj_rx, f"{a.subject}\n{a.text}" if subj_rx == r"dismiss" else a.subject, re.I))
    return about


def _slack_about(*need: str, heading: str | None = None, not_channel: str | None = None,
                 only_channel: str | None = None):
    def about(a: Action) -> bool:
        if a.kind not in SLACK:
            return False
        t = a.text or ""
        if not all(re.search(n, t, re.I) for n in need):
            return False
        if heading and not re.search(heading, t):
            return False
        if not_channel and a.kind == "slack_post" and is_ch(a, not_channel):
            return False
        if only_channel and not (a.kind == "slack_post" and is_ch(a, only_channel)):
            return False
        return True
    return about


def specs(ctx) -> list[Comm]:
    return [
        Comm("ack_00441", "email", _email_about("CASE-2026-00441", FIERRO, r"acknowledg"),
             "Template A-1 expedited acknowledgment for concurrent-care CASE-2026-00441 to Joanna Fierro",
             [R_ACK_STEP, R_A1, R_EXP_HDR, R_TIMES, R_CONC, R_SIGN],
             to=[FIERRO],
             subject=r"Mojave Crest Appeals Case #CASE-2026-00441 [-–] Acknowledgment of Your Appeal",
             subject_hint="Mojave Crest Appeals Case #CASE-2026-00441 - Acknowledgment of Your Appeal",
             body=[(r"EXPEDITED REVIEW", "the Expedited Acknowledgment Header Block '--- EXPEDITED REVIEW ---'"),
                   (r"Expedited Basis:", "the header field 'Expedited Basis:'"),
                   (r"Decision Due By:.{0,80}?" + D_1105,
                    "'Decision Due By: 2026-11-05 10:00 AM' (termination effective date, earlier than 72 hours)"),
                   (r"CASE-2026-00441", "Case Number CASE-2026-00441"),
                   (r"VA-55219-07", "Member ID VA-55219-07"),
                   (r"Concurrent", "Appeal Type: Concurrent Care"), *SIG]),
        Comm("status_00437", "email", _email_about("CASE-2026-00437", TORRES, r"."),
             "status update / response to Daniela Torres on open CASE-2026-00437 (no outbound contact since 10/17)",
             [R_STATUS, R_SUBJ, R_REVNAME, R_B6_NOMENTION, R_SIGN],
             to=[TORRES],
             subject=r"Mojave Crest Appeals Case #CASE-2026-00437 [-–] \S.*",
             subject_hint="Mojave Crest Appeals Case #CASE-2026-00437 - Status Update",
             body=[(r"CASE-2026-00437", "the Case ID CASE-2026-00437"),
                   (date_rx(2026, 12, 13), "the decision deadline December 13, 2026"),
                   (r"under (clinical )?review|being reviewed|in review|pending|remains? open|status",
                    "a brief statement of the current case status (e.g. 'under clinical review')"), *SIG],
             banned=[(r"fraud", "Do not mention the fraud flag/review to the member (Format B-6)."),
                     (REVIEWERS, "Do not include internal reviewer names in member correspondence (12.3).")]),
        Comm("fraud_00437", "slack_dm", _slack_about(r"CASE-2026-00437", r"fraud"),
             "Format B-6 Suspected Claim Fraud DM to Kendel Dufree for CASE-2026-00437",
             [R_FRAUD, R_B6_POST, R_B6_FIELDS], to=["Kendel Dufree"], max_count=5,
             body=[(r"SUSPECTED CLAIM FRAUD", "the header 'SUSPECTED CLAIM FRAUD'"),
                   (r"Case #:\s*CASE-2026-00437", "'Case #: CASE-2026-00437'"),
                   (r"Provider NPI:\s*1427839501", "'Provider NPI: 1427839501'"),
                   (r"Provider Name:\s*Desert Peak Specialty Group", "'Provider Name: Desert Peak Specialty Group'"),
                   (r"Dates? of Service in Dispute:.{0,40}?" + date_rx(2026, 10, 12),
                    "'Dates of Service in Dispute: 2026-10-12'"),
                   (r"Fraud Type:\s*Service Not Delivered", "'Fraud Type: Service Not Delivered'"),
                   (r"Basis for Suspicion:\s*\S", "'Basis for Suspicion:' (factual, 2-4 sentences)"),
                   (r"Appeal Status:.{0,80}?regular clock", "'Appeal Status: Will continue on regular clock'"),
                   (r"Case Folder:", "'Case Folder:' (e.g. /appeals/CASE-2026-00437/)")]),
        Comm("parity_00441", "slack_dm",
             lambda a: a.kind in SLACK and "CASE-2026-00441" in (a.text or "") and bool(
                 re.search(r"Comparable M/S|^[\W_]*PARITY FLAG[\W_]*$", a.text or "", re.M)),
             "Format B-3 Parity Flag Notification DM to @parity-committee for CASE-2026-00441",
             [R_B3, R_B3_DM, R_B3_FIELDS, R_PAR_WHY, R_PAR_IND], to=["Parity Review Committee"], max_count=5,
             body=[(r"PARITY FLAG", "the header 'PARITY FLAG'"),
                   (r"Case #:\s*CASE-2026-00441", "'Case #: CASE-2026-00441'"),
                   (r"Service Classification:\s*\W*Inpatient SUD", "'Service Classification: Inpatient SUD'"),
                   (r"Comparable M/S Classification:\s*\S", "'Comparable M/S Classification:' (e.g. inpatient "
                                                            "medical/surgical - inpatient medical rehabilitation)"),
                   (r"Flag Indicator:\s*\S", "'Flag Indicator:' (the Section 8.2 indicator)"),
                   (r"Case Folder:", "'Case Folder:'"),
                   (r"Decision Deadline:.{0,60}?" + D_1105, "'Decision Deadline: 2026-11-05 10:00 AM'")]),
        Comm("esc_00441", "slack_dm",
             _slack_about(r"CASE-2026-00441", heading=r"\bESCALATION\b", not_channel="appeals-urgent"),
             "Format B-2 escalation DM to @dwhitfield for CASE-2026-00441 (parity flag; concurrent care ending "
             "within 72 hours)",
             [R_TRIGGERS, R_TRIG_PARITY, R_TRIG_CONC, R_ESC_DM, R_ESC_FIELDS, R_B2_FIELDS, R_ESC_FIRST],
             to=["Darnell Whitfield"], max_count=5,
             body=[(r"ESCALATION", "the header 'ESCALATION'"),
                   (r"Case #:\s*CASE-2026-00441", "'Case #: CASE-2026-00441'"),
                   (r"Type:\s*\S", "'Type: Concurrent'"),
                   (r"Deadline:.{0,60}?" + D_1105, "'Deadline: 2026-11-05 10:00 AM'"),
                   (r"Trigger:.{0,300}?(parity|72[- ]?hour|concurrent)",
                    "'Trigger:' naming the 9.2 trigger(s) - parity flag raised; concurrent care termination within "
                    "72 hours"),
                   (r"Summary:\s*\S", "'Summary:'"), (r"Recommendation:\s*\S", "'My Recommendation:'"),
                   (r"Requested Action:\s*\S", "'Requested Action:'")]),
        Comm("route_00441", "slack_dm",
             _slack_about(r"CASE-2026-00441", heading=r"CLINICAL ROUTING", not_channel="appeals-urgent"),
             "Format B-1 clinical routing DM to Dr. Ayla Ontario for parity-flagged concurrent-care CASE-2026-00441",
             [R_ONTARIO, R_PAR_EXCL, R_CONC_ROUTE, R_B1_EXP, R_B1_FMT, R_B1_FIELDS], to=["Dr. Ayla Ontario"],
             max_count=5,
             body=[(r"CLINICAL ROUTING", "the header 'CLINICAL ROUTING'"),
                   (r"Case #:\s*CASE-2026-00441", "'Case #: CASE-2026-00441'"),
                   (r"Type:\s*\W*Concurrent", "'Type: Concurrent Care'"),
                   (r"Service Classification:.{0,40}?(SUD|Substance)", "'Service Classification: SUD'"),
                   (r"Standard of Review:\s*Medical Necessity", "'Standard of Review: Medical Necessity'"),
                   (r"Deadline:.{0,60}?" + D_1105, "'Deadline: 2026-11-05 10:00 AM'"),
                   (r"Parity Flag:\s*\W*YES", "'Parity Flag: YES'"), (r"Case Folder:", "'Case Folder:'")]),
        Comm("urgent_00441", "slack_post", _slack_about(r"CASE-2026-00441", only_channel="appeals-urgent"),
             "#appeals-urgent post for expedited concurrent-care CASE-2026-00441 tagging @dwhitfield",
             [R_B1_EXP, R_B1_FMT, R_CH], channel="appeals-urgent", max_count=5,
             body=[(r"@dwhitfield|<@U002>|@darnell", "a tag of @dwhitfield"),
                   (r"CASE-2026-00441", "the Case ID CASE-2026-00441 (no member name / PHI)")]),
        Comm("dismiss_00442", "draft", _email_about("CASE-2026-00442", SWDO, r"dismiss"),
             "Template A-4 Immediate Dismissal Variant for CASE-2026-00442 saved as a DRAFT to Southwest Desert "
             "Orthopedics (not sent before supervisor approval)",
             [R_PROV_EXC, R_A4_VAR, R_A4_TEXT, R_A4_SUBJ, R_DISMISS_SUP], to=[SWDO], exact_to=False,
             subject=r"Mojave Crest Appeals Case #CASE-2026-00442 [-–] Appeal Dismissed",
             subject_hint="Mojave Crest Appeals Case #CASE-2026-00442 - Appeal Dismissed",
             body=[(r"cannot be cured", "the variant text 'this standing requirement cannot be cured by subsequent "
                                        "documentation'"),
                   (r"dismissed for lack of standing", "'This case is dismissed for lack of standing.'"),
                   (r"re-?file", "'[MEMBER NAME] may re-file this appeal directly within the 180-day window'"),
                   (r"CASE-2026-00442", "Case #: CASE-2026-00442"), *SIG],
             banned=[(r"We have not received the requested documentation|we asked for a signed Authorized "
                      r"Representative|submit a signed Authorized Representative form to re-open",
                      "Use the Immediate Dismissal Variant body (no A-2 was sent; standing cannot be cured), not the "
                      "standard A-4 body.")]),
        Comm("review_00442", "slack_dm", _slack_about(r"CASE-2026-00442", r"dismiss|draft"),
             "Slack DM to @dwhitfield asking him to review the CASE-2026-00442 dismissal draft before sending",
             [R_DISMISS_SUP, R_ESC_WAIT], to=["Darnell Whitfield"], max_count=5,
             body=[(r"CASE-2026-00442", "the Case ID CASE-2026-00442"),
                   (r"review|approv", "a request to review/approve the dismissal draft")]),
        Comm("ack_00443", "email", _email_about("CASE-2026-00443", CASILLAS, r"acknowledg"),
             "Template A-1 acknowledgment to Roberto Casillas for his new post-service appeal CASE-2026-00443",
             [R_POST_ACK, R_A1, R_A1_FIELDS, R_ACK_ROLE, R_CASEID, R_SIGN], to=[CASILLAS],
             subject=r"Mojave Crest Appeals Case #CASE-2026-00443 [-–] Acknowledgment of Your Appeal",
             subject_hint="Mojave Crest Appeals Case #CASE-2026-00443 - Acknowledgment of Your Appeal",
             body=[(r"CASE-2026-00443", "Case Number CASE-2026-00443"), (r"VA-88291-03", "Member ID VA-88291-03"),
                   (r"Date Received:.{0,20}?" + date_rx(2026, 11, 4), "'Date Received: 2026-11-04'"),
                   (r"Post[- ]Service", "Appeal Type: Post-Service Standard"),
                   (r"Decision Due By:.{0,20}?" + D_0103, "'Decision Due By: 2027-01-03' (60 calendar days)"), *SIG],
             banned=[(r"EXPEDITED REVIEW", "Post-service appeals cannot be expedited (4.3.4) - no expedited header.")]),
        Comm("route_00443", "slack_post", _slack_about(r"CASE-2026-00443", heading=r"CLINICAL ROUTING"),
             "Format B-1 clinical routing post in #appeals-clinical-queue for CASE-2026-00443",
             [R_POST_ROUTE, R_ROUTE_STEP, R_B1, R_B1_FMT, R_B1_FIELDS], channel="appeals-clinical-queue",
             max_count=5,
             body=[(r"CLINICAL ROUTING", "the header 'CLINICAL ROUTING'"),
                   (r"Case #:\s*CASE-2026-00443", "'Case #: CASE-2026-00443'"),
                   (r"Type:\s*\W*Post[- ]Service", "'Type: Post-Service'"),
                   (r"Service Classification:\s*\W*(Medical\s*/\s*Surgical|M/S)",
                    "'Service Classification: Medical/Surgical'"),
                   (r"Standard of Review:\s*\W*Medical Necessity", "'Standard of Review: Medical Necessity'"),
                   (r"Deadline:.{0,40}?" + D_0103, "'Deadline: 2027-01-03'"),
                   (r"Parity Flag:\s*\W*(YES|NO)", "'Parity Flag: NO'"), (r"Case Folder:", "'Case Folder:'")]),
        Comm("esc_00443", "slack_dm",
             _slack_about(r"CASE-2026-00443", heading=r"\bESCALATION\b", not_channel="appeals-urgent"),
             "Format B-2 escalation DM to @dwhitfield for CASE-2026-00443, trigger 'Exceeds Coordinator Authority' "
             "(total billed $28,400 > $25,000)",
             [R_TIER, R_ESC_DM, R_ESC_FIELDS, R_B2_FIELDS], to=["Darnell Whitfield"], max_count=5,
             body=[(r"ESCALATION", "the header 'ESCALATION'"),
                   (r"Case #:\s*CASE-2026-00443", "'Case #: CASE-2026-00443'"),
                   (r"Type:\s*\S", "'Type: Post-Service'"),
                   (r"Deadline:.{0,40}?" + D_0103, "'Deadline: 2027-01-03'"),
                   (r"Trigger:.{0,200}?(exceed.{0,40}?coordinator.{0,20}?(authority|tier)|coordinator authority)",
                    "'Trigger: Exceeds Coordinator Authority'"),
                   (r"Summary:\s*\S", "'Summary:'"), (r"Recommendation:\s*\S", "'My Recommendation:'"),
                   (r"Requested Action:\s*\S", "'Requested Action:'")]),
    ]


# ---- pre rules -----------------------------------------------------------------------------------------------------

def _phi_public(ctx, a: Action):
    if a.kind != "slack_post" or world(ctx).dm_recipients(a) or str(a.channel).startswith("D"):
        return None
    hits = sorted({m.group(0) for rx in PHI_PUBLIC for m in re.finditer(rx, a.text or "", re.I)})
    if hits:
        return (f"[phi] Never post PHI in a public Slack channel - found {hits}. Refer to the case only by its Case ID "
                "(CASE-YYYY-NNNNN); discuss member details by DM to the specific reviewer.")
    return None


def _parity_channel(ctx, a: Action):
    if a.kind == "slack_post" and is_ch(a, "appeals-parity") and (cases_in(a.text) or re.search(
            r"parity flag|CASE-|member", a.text or "", re.I)):
        return ("[parity-channel] #appeals-parity is for general discussion only - send case parity flags as Format "
                "B-3 by DM to @parity-committee.")
    return None


def _subject_format(ctx, a: Action):
    o = outbound_external(world(ctx), a)
    if not o:
        return None
    rec, subj, _ = o
    if all("canyonridgereview" in r for r in rec):
        return None
    ok = re.fullmatch(r"(?:(?:RE|FW|FWD):\s*)*(?:URGENT [-–] )?Mojave Crest (?:Appeals|Grievance) Case "
                      r"#CASE-\d{4}-\d{5} [-–] \S.*", dashes(subj), re.I)
    if ok:
        return None
    how = (" A reply keeps the sender's original subject - send a new email with google_mail__send_email instead."
           if "reply" in a.tool or "forward" in a.tool else "")
    return (f"[subject] Outbound emails to members/providers need the subject 'Mojave Crest Appeals Case "
            f"#CASE-YYYY-NNNNN - <Brief Description>' (got \"{subj}\").{how}")


def _signature(ctx, a: Action):
    o = outbound_external(world(ctx), a)
    if not o or all("canyonridgereview" in r for r in o[0]):
        return None
    t = dashes(o[2])
    miss = [d for rx, d in [(r"Jordan Mills", "full name 'Jordan Mills'"),
                            (r"Appeals\s*(&|and)\s*Grievances\s+Coordinator", "title 'Appeals & Grievances Coordinator'"),
                            (r"CASE-\d{4}-\d{5}", "the Case ID"),
                            (r"\(?702\)?[\s.-]*555[\s.-]*0148", "the Appeals Unit phone (702) 555-0148")]
            if not re.search(rx, t, re.I)]
    return soft(ctx, "[signature]", f"[signature] Sign correspondence with {', '.join(miss)}." if miss else None)


def _reviewer_names(ctx, a: Action):
    o = outbound_external(world(ctx), a)
    if o and re.search(REVIEWERS, f"{o[1]}\n{o[2]}"):
        return ("[reviewer-name] Do not include clinical reviewer names in correspondence to members/providers - use "
                "'the reviewing clinician' or 'our Medical Director'.")
    return None


def _no_fraud(ctx, a: Action):
    o = outbound_external(world(ctx), a)
    if o and re.search(r"fraud", f"{o[1]}\n{o[2]}", re.I):
        return ("[fraud-mention] Do not mention the fraud flag or fraud review in any correspondence to the member, "
                "provider or AOR (Format B-6).")
    return None


def _cross_member(ctx, a: Action):
    o = outbound_external(world(ctx), a)
    if not o:
        return None
    rec, subj, text = o
    known = [mid for mid, (_, addrs) in MEMBERS.items() if set(addrs) & set(rec)]
    if not known:
        return None
    t = f"{subj}\n{text}"
    leaks = [mid for mid, (names, _) in MEMBERS.items() if mid not in known and (
        mid in t or any(re.search(rf"\b{re.escape(n)}\b", t, re.I) for n in names))]
    if leaks:
        return (f"[phi-other-member] This email to {', '.join(rec)} contains another member's information "
                f"({', '.join(leaks)}). PHI must not be shared with anyone but that member / their requester.")
    return None


def _regulator(ctx, a: Action):
    if a.kind not in EMAILS:
        return None
    rec, _, _ = resolved(world(ctx), a)
    bad = [r for r in rec if re.search(r"(?:@|\.)(?:doi\.nv\.gov|dol\.gov|nv\.gov|[\w-]+\.gov)$", r)]
    if bad:
        return (f"[regulator] Coordinators may not contact the Nevada Division of Insurance or any regulatory agency "
                f"directly ({', '.join(bad)}) - that goes through the Compliance Officer.")
    return None


PROMISE_RX = (r"\bguarantee|\bwe will (?:pay|cover|reimburse|approve|overturn|reinstate)\b|"
              r"\byour (?:appeal|claim) will (?:be )?(?:approved|overturned|granted|paid|successful)|"
              r"\bwill be (?:approved|overturned|paid in full)\b")
TONE_RX = (r"\b(?:we|I) (?:sincerely |deeply )?apologi[sz]e\b.{0,80}?\b(?:denial|denied|decision)|"
           r"\b(?:court|Canyon Ridge|external review(?:er)?)\b.{0,60}?\b(?:would|will|likely|might|probably)\b.{0,30}?"
           r"\b(?:decide|rule|overturn|side|find)")


def _promises(ctx, a: Action):
    o = outbound_external(world(ctx), a)
    if o and re.search(PROMISE_RX, o[2], re.I):
        return soft(ctx, "[promise]", "[promise] Do not promise payment, outcomes or coverage in correspondence - no "
                                      "decision has been made on this case.")
    if o and re.search(TONE_RX, o[2], re.I | re.S):
        return soft(ctx, "[promise]", "[promise] Keep correspondence matter of fact: do not apologize for the original "
                                      "denial or speculate about what Canyon Ridge or a court might decide.")
    return None


def _outside_parties(ctx, a: Action):
    o = outbound_external(world(ctx), a)
    if not o:
        return None
    rec, subj, text = o
    other = [r for r in rec if r not in (TORRES, FIERRO, CASILLAS, SWDO) and "canyonridgereview" not in r]
    t = f"{subj}\n{text}"
    if other and (cases_in(t) or re.search(r"\bVA-\d{5}-\d{2}\b|\bappeal", t, re.I)):
        return (f"[outside] Do not discuss open appeals with anyone outside MCA other than the member / requester of "
                f"the case ({', '.join(other)}).")
    return None


MEDNEC_RX = (r"\b(?:service|services|procedure|care|treatment|surgery|stay|admission|visit|rehabilitation)\s+"
             r"(?:is|was|were|are)\s+(?:not\s+)?medically necessary")


def _mednec(ctx, a: Action):
    o = outbound_external(world(ctx), a)
    if o and re.search(MEDNEC_RX, o[2], re.I):
        return soft(ctx, "[mednec]", "[mednec] Never write that a service is / is not medically necessary in a letter "
                                     "unless directly quoting a clinical reviewer's worksheet (none exists yet).")
    return None


DET_SUBJ = r"Appeal Decision|Expedited Decision"
DET_BODY = (r"Decision:\s*Your appeal (?:is|has been)|your appeal (?:is|has been) (?:APPROVED|DENIED|upheld|overturned|"
            r"partially approved)")


def _no_determination(ctx, a: Action):
    if a.kind not in EMAILS:
        return None
    rec, subj, text = resolved(world(ctx), a)
    if re.search(DET_SUBJ, subj, re.I) or re.search(DET_BODY, text, re.I):
        return ("[determination] No determination letter may be drafted or issued: none of the open cases has a "
                "clinical reviewer's written decision, and CASE-2026-00441 is parity-flagged and needs the Parity "
                "Review Committee's concurrence (parity_concurrence.txt) first.")
    return None


def _dismiss_scope(ctx, a: Action):
    if a.kind not in EMAILS:
        return None
    rec, subj, text = resolved(world(ctx), a)
    if not (re.search(r"dismiss", subj, re.I) or re.search(r"(?:must be|is|has been|was) dismissed|dismissed for",
                                                          text, re.I)):
        return None
    other = (cases_in(f"{subj}\n{text}") - {"CASE-2026-00442"}) or (set(rec) & {TORRES, FIERRO, CASILLAS})
    if other:
        return (f"[dismissal] Only CASE-2026-00442 (provider post-service filing without AOR) is dismissible. "
                f"{sorted(other)}: the member filed with standing and within 180 days of the denial (Casillas: denial "
                f"2026-05-15, received 2026-11-04 = 173 days) - do not dismiss.")
    return None


def _external_review(ctx, a: Action):
    if a.kind not in EMAILS:
        return None
    rec, _, _ = resolved(world(ctx), a)
    if any("canyonridgereview" in r for r in rec):
        return ("[external-review] No case has a final adverse internal determination or is deemed exhausted - nothing "
                "is to be forwarded to Canyon Ridge Review Services.")
    return None


def _case_00442_intake(ctx, a: Action):
    t = f"{a.subject}\n{a.text}"
    if a.kind in EMAILS:
        rec, subj, text = resolved(world(ctx), a)
        if ("CASE-2026-00442" in f"{subj}\n{text}" or SWDO in rec) and re.search(
                r"acknowledg|information needed", subj, re.I):
            return ("[00442-standing] CASE-2026-00442 is a provider-filed post-service appeal without AOR: standing "
                    "cannot be cured, so do not acknowledge it or request AOR documentation (A-2) - dismiss it with "
                    "the Template A-4 Immediate Dismissal Variant (draft, supervisor review).")
    if a.kind in SLACK and "CASE-2026-00442" in t and re.search(r"CLINICAL ROUTING", t):
        return ("[00442-standing] CASE-2026-00442 has no standing (provider post-service, no AOR) - it is dismissed, "
                "not routed for clinical review.")
    return None


def _case_00442_hold(ctx, a: Action):
    if a.kind != "email_send":
        return None
    rec, subj, text = resolved(world(ctx), a)
    if ("CASE-2026-00442" in f"{subj}\n{text}" or SWDO in rec) and re.search(r"dismiss", f"{subj}\n{text}", re.I):
        return ("[00442-hold] Dismissal letters require Supervisor review before sending: leave the CASE-2026-00442 "
                "dismissal in the drafts folder and Slack it to @dwhitfield; no approval has been received.")
    return None


def _case_00441_routing(ctx, a: Action):
    if a.kind not in SLACK or "CASE-2026-00441" not in (a.text or ""):
        return None
    w = world(ctx)
    if a.kind == "slack_post" and is_ch(a, "appeals-clinical-queue"):
        return ("[00441-parity-routing] CASE-2026-00441 is parity-flagged and expedited: route it only to Dr. Ontario "
                "(DM) and the Parity Review Committee (B-3 DM), and tag @dwhitfield in #appeals-urgent - not the "
                "standard #appeals-clinical-queue / RN tier.")
    if w.is_dm_to(a, "Marisol Alvarado") or w.is_dm_to(a, "Helena Bergstrom"):
        return ("[00441-parity-routing] Parity-flagged CASE-2026-00441 is routed exclusively to Dr. Ontario and the "
                "Parity Review Committee, not the RN tier / medical-surgical Medical Director.")
    if re.search(r"CLINICAL ROUTING", a.text or "") and re.search(r"Parity Flag:\s*\W*NO\b", a.text or "", re.I):
        return "[00441-parity-routing] CASE-2026-00441 must be routed with 'Parity Flag: YES'."
    return None


def _case_00441_lapse(ctx, a: Action):
    o = outbound_external(world(ctx), a)
    if not o:
        return None
    rec, subj, text = o
    t = f"{subj}\n{text}"
    if set(rec) - {FIERRO} and re.search(r"CASE-2026-00441|Fierro|AUTH-2026-04819|VA-55219-07", t) and re.search(
            r"laps|terminat|will end|expire", t, re.I):
        return ("[00441-coverage] Coverage continues through the appeal decision - do not notify the provider that "
                "the authorization will lapse while CASE-2026-00441 is pending.")
    return None


CONCUR_WRITE = (r"open\(\s*[^)]*parity_concurrence[^)]*,\s*(?:mode\s*=\s*)?['\"][wax]|parity_concurrence[^\n]{0,40}"
                r"\.write_(?:text|bytes)\(|>>?\s*\S*parity_concurrence|\btee\s+(?:-a\s+)?\S*parity_concurrence")


def _parity_concurrence_file(ctx, a: Action):
    hit = (a.kind in ("file_write", "file_delete") and any("parity_concurrence" in f.lower() for f in a.files_written)) \
        or (a.tool in ("syntara__executePython", "syntara__executeBash") and re.search(CONCUR_WRITE, a.text or ""))
    if hit:
        return ("[concurrence] parity_concurrence.txt records a PARITY CONCURRENCE message received from "
                "@parity-committee; none has been received for CASE-2026-00441, so do not create it.")
    return None


def _casillas_case_id(ctx, a: Action):
    if a.kind not in EMAILS:
        return None
    rec, subj, text = resolved(world(ctx), a)
    if CASILLAS in rec:
        ids = cases_in(f"{subj}\n{text}") - {"CASE-2026-00443"}
        if ids:
            return (f"[case-id] Roberto Casillas' new appeal gets the next sequential Case ID CASE-2026-00443 "
                    f"(after CASE-2026-00442), not {sorted(ids)}.")
    return None


# ---- completion: Appeals Log ---------------------------------------------------------------------------------------

def cell_dt(v) -> tuple[dt.date | None, str | None]:
    s = str(v or "")
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T]+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([AaPp]\.?[Mm]\.?)?)?", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})(?:[ T,]+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([AaPp]\.?[Mm]\.?)?)?",
                      s)
        if not m:
            return None, None
        mo, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y += 2000 if y < 100 else 0
    try:
        day = dt.date(y, mo, d)
    except ValueError:
        return None, None
    if m.group(4) is None:
        return day, None
    h, mi = int(m.group(4)), int(m.group(5))
    ap = (m.group(7) or "").lower().replace(".", "")
    if ap == "pm" and h < 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    if m.group(6) is not None and h == 0 and mi == 0 and not ap:
        return day, None  # a datetime cell at midnight carries no time
    return day, f"{h:02d}:{mi:02d}"


def dt_ok(v, day: dt.date, tm: str | None = None) -> bool:
    d, t = cell_dt(v)
    return d == day and (tm is None or t is None or t == tm)


def _fmt(day: dt.date, tm: str | None = None) -> str:
    return day.isoformat() + (f" {tm}" if tm else "")


def _rows(w: World, which: str = "current") -> list[dict]:
    return w.rows(LOG, HDR, which, SHEET)


def _col(r: dict, name: str) -> str:
    v = r.get(name, "")
    return "" if str(v) in ("None", "nan") else str(v).strip()


def _row(rows: list[dict], case: str) -> dict | None:
    return next((r for r in rows if _col(r, "Case ID") == case), None)


def _eq(a, b) -> bool:
    if blank(a) and blank(b):
        return True
    da, ta = cell_dt(a)
    db, tb = cell_dt(b)
    if da and db and re.fullmatch(r"[\d\-/: .APMapm]+", str(a).strip()) and re.fullmatch(r"[\d\-/: .APMapm]+",
                                                                                          str(b).strip()):
        return da == db and (ta or "00:00") == (tb or "00:00")
    return same(a, b)


def _na(v) -> bool:
    return blank(v) or norm(v) in ("n/a", "na", "none", "-", "--", "not applicable")


FILL = ["Acknowledgment Due", "Acknowledgment Sent", "Tolled (Y/N)", "Decision Due", "Reviewer Assigned", "Parity Flag",
        "Compliance Escalation", "External Review Requested", "Case Status", "Coordinator"]


def _fixed(r: dict, init: dict, cols: list[str], probs: list[str]) -> None:
    for c in cols:
        if not _eq(_col(r, c), _col(init, c)):
            probs.append(f"'{c}' must stay '{_col(init, c)}' (got '{_col(r, c)}')")


HINT_00441 = {"Acknowledgment Due": "2026-11-04 14:15", "Acknowledgment Sent": "2026-11-04", "Tolled (Y/N)": "N",
              "Decision Due": "2026-11-05 10:00", "Reviewer Assigned": "Dr. Ontario / Parity Review Committee",
              "Parity Flag": "Y", "Compliance Escalation": "Y/N", "Case Status": "With Reviewer"}
HINT_00442 = {"Acknowledgment Due": "2026-11-10 or N/A", "Acknowledgment Sent": "N/A", "Tolled (Y/N)": "N",
              "Decision Due": "2027-01-02 or N/A", "Reviewer Assigned": "N/A (dismissal, no clinical review)",
              "Parity Flag": "N", "Compliance Escalation": "Y/N", "Case Status": "Draft Letter"}
HINT_00443 = {"Acknowledgment Due": "2026-11-11", "Acknowledgment Sent": "2026-11-04", "Tolled (Y/N)": "N",
              "Decision Due": "2027-01-03", "Reviewer Assigned": "RN Reviewer team", "Parity Flag": "N",
              "Compliance Escalation": "Y/N", "External Review Requested": "N", "Case Status": "With Reviewer",
              "Coordinator": "J. Mills"}


def _filled(r: dict, probs: list[str], hints: dict, cols=FILL) -> None:
    empty = [c for c in cols if blank(_col(r, c))]
    if empty:
        probs.append("fill in " + ", ".join(f"'{c}' = {hints.get(c, 'N/A')}" for c in empty))


def _open_no_decision(r: dict, probs: list[str]) -> None:
    for c in ("Decision Date", "Outcome"):
        if not _na(_col(r, c)):
            probs.append(f"'{c}' must stay blank - no determination letter has been sent (got '{_col(r, c)}')")
    if re.search(r"closed|sent", _col(r, "Case Status"), re.I):
        probs.append(f"'Case Status' cannot be '{_col(r, 'Case Status')}' - the case is still open")


def _no_toll(r: dict, probs: list[str], why: str) -> None:
    if not re.fullmatch(r"n(o)?", norm(_col(r, "Tolled (Y/N)"))) and not blank(_col(r, "Tolled (Y/N)")):
        probs.append(f"'Tolled (Y/N)' must be 'N' ({why}; got '{_col(r, 'Tolled (Y/N)')}')")
    for c in ("Toll Start", "Toll End"):
        if not _na(_col(r, c)):
            probs.append(f"'{c}' must stay blank (no tolling)")


def _log_checks(ctx):
    w = world(ctx)
    init, cur = _rows(w, "initial"), _rows(w, "current")
    if not init:
        return
    if not cur:
        yield False, "appeals_log_master.xlsx / sheet 'Appeals Log' is missing or unreadable - restore it.", [R_COLUMNS]
        return
    # columns
    ih = [c for c in init[0] if c != "__row__"]
    ch = [c for c in cur[0] if c != "__row__"]
    yield ih == ch, (f"Do not add, remove, rename or reorder Appeals Log columns. Expected exactly: {' | '.join(ih)}"
                     f" (got: {' | '.join(ch)})."), [R_COLUMNS]
    # existing rows
    probs = []
    for r0 in init:
        cid = _col(r0, "Case ID")
        r = _row(cur, cid)
        if r is None:
            probs.append(f"{cid} is missing (Case IDs must not be edited or removed)")
        elif cid in ("CASE-2026-00389", "CASE-2026-00391", "CASE-2026-00402", "CASE-2026-00414"):
            diff = [c for c in ih if not _eq(_col(r, c), _col(r0, c))]
            if diff:
                probs.append(f"closed case {cid} was edited ({', '.join(diff)}) - restore the original values")
    yield not probs, "Appeals Log integrity: " + "; ".join(probs) + ".", [R_CASEID, R_BACKDATE, R_CLOSE]
    # unexpected new rows
    known = {_col(r, "Case ID") for r in init}
    new = [r for r in cur if _col(r, "Case ID") not in known]
    extra = [r for r in new if _col(r, "Member ID") != "VA-88291-03"]
    dup = [r for r in new if _col(r, "Member ID") == "VA-88291-03"][1:]
    yield not (extra or dup), ("Unexpected new Appeals Log row(s): " + ", ".join(
        f"{_col(r, 'Case ID') or '(no Case ID)'} / {_col(r, 'Member ID')}" for r in extra + dup) +
        ". The only new case is Roberto Casillas' appeal (VA-88291-03) as CASE-2026-00443 - remove the others."), \
        [R_LOG_STEP, R_CASEID]

    # CASE-2026-00441
    r, r0 = _row(cur, "CASE-2026-00441"), _row(init, "CASE-2026-00441")
    if r is not None and r0 is not None:
        p: list[str] = []
        _fixed(r, r0, ["Member ID", "Group ID", "Plan Year", "Appeal Type", "Standard of Review", "Date of Receipt"], p)
        _filled(r, p, HINT_00441)
        if not blank(_col(r, "Acknowledgment Due")) and not dt_ok(_col(r, "Acknowledgment Due"), dt.date(2026, 11, 4),
                                                                  "14:15"):
            p.append("'Acknowledgment Due' = 2026-11-04 14:15 (concurrent care: 24 hours from receipt 2026-11-03 "
                     f"14:15; got '{_col(r, 'Acknowledgment Due')}')")
        if not blank(_col(r, "Acknowledgment Sent")) and not dt_ok(_col(r, "Acknowledgment Sent"),
                                                                   dt.date(2026, 11, 4)):
            p.append("'Acknowledgment Sent' = 2026-11-04, the day the expedited A-1 is sent "
                     f"(got '{_col(r, 'Acknowledgment Sent')}')")
        if not blank(_col(r, "Decision Due")) and not dt_ok(_col(r, "Decision Due"), dt.date(2026, 11, 5), "10:00"):
            p.append("'Decision Due' = 2026-11-05 10:00 (termination effective 11/05 10:00 AM is earlier than 72 hours "
                     f"from receipt; got '{_col(r, 'Decision Due')}')")
        _no_toll(r, p, "tolling is not available for expedited/concurrent appeals")
        rv = _col(r, "Reviewer Assigned")
        if rv and (not re.search(r"Ontario", rv) or re.search(r"Alvarado|RN\b|Bergstrom", rv)):
            p.append(f"'Reviewer Assigned' = Dr. Ontario / Parity Review Committee (parity-flagged; got '{rv}')")
        if _col(r, "Parity Flag") and not re.match(r"y", _col(r, "Parity Flag"), re.I):
            p.append(f"'Parity Flag' = Y (member alleges stricter SUD criteria than medical rehab; got "
                     f"'{_col(r, 'Parity Flag')}')")
        st = _col(r, "Case Status")
        if st and not re.search(r"with reviewer", st, re.I):
            p.append(f"'Case Status' = With Reviewer (routed to Dr. Ontario / Parity Review Committee; got '{st}')")
        _open_no_decision(r, p)
        yield not p, "Appeals Log row CASE-2026-00441: " + "; ".join(p) + ".", \
            [R_LOG_STEP, R_CONC_DL, R_TIMES, R_TOLL, R_PAR_EXCL, R_PAR_WHY, R_COLDESC2, R_BACKDATE]

    # CASE-2026-00442
    r, r0 = _row(cur, "CASE-2026-00442"), _row(init, "CASE-2026-00442")
    if r is not None and r0 is not None:
        p = []
        _fixed(r, r0, ["Member ID", "Group ID", "Plan Year", "Appeal Type", "Standard of Review", "Date of Receipt"], p)
        _filled(r, p, HINT_00442)
        v = _col(r, "Acknowledgment Due")
        if cell_dt(v)[0] and not dt_ok(v, dt.date(2026, 11, 10)):
            p.append(f"'Acknowledgment Due' would be 2026-11-10 (5 business days from 2026-11-03) or N/A (got '{v}')")
        v = _col(r, "Acknowledgment Sent")
        if cell_dt(v)[0]:
            p.append(f"'Acknowledgment Sent' must not show a date - no acknowledgment goes to a requester without "
                     f"standing (got '{v}'; use N/A)")
        v = _col(r, "Decision Due")
        if cell_dt(v)[0] and not dt_ok(v, dt.date(2027, 1, 2)):
            p.append(f"'Decision Due' would be 2027-01-02 (60 calendar days from 2026-11-03) or N/A (got '{v}')")
        _no_toll(r, p, "the case is dismissed, not tolled for AOR documentation")
        if _col(r, "Parity Flag") and not re.match(r"n", _col(r, "Parity Flag"), re.I):
            p.append(f"'Parity Flag' = N (got '{_col(r, 'Parity Flag')}')")
        o = _col(r, "Outcome")
        if not _na(o) and not re.search(r"dismiss", o, re.I):
            p.append(f"'Outcome' can only be 'Dismissed' (or blank until the letter is sent; got '{o}')")
        if not _na(_col(r, "Decision Date")) and cell_dt(_col(r, "Decision Date"))[0]:
            p.append("'Decision Date' must stay blank - the dismissal letter is only a draft awaiting supervisor review")
        st = _col(r, "Case Status")
        if st and re.search(r"closed|sent|^intake$|with reviewer", st, re.I):
            p.append(f"'Case Status' = Draft Letter (dismissal drafted, awaiting supervisor review - not sent; "
                     f"got '{st}')")
        yield not p, "Appeals Log row CASE-2026-00442: " + "; ".join(p) + ".", \
            [R_LOG_STEP, R_PROV_EXC, R_DISMISS_SUP, R_COLDESC3, R_BACKDATE]

    # CASE-2026-00437
    r, r0 = _row(cur, "CASE-2026-00437"), _row(init, "CASE-2026-00437")
    if r is not None and r0 is not None:
        p = []
        _fixed(r, r0, ["Member ID", "Group ID", "Plan Year", "Appeal Type", "Standard of Review", "Date of Receipt",
                       "Acknowledgment Due", "Acknowledgment Sent", "Decision Due"], p)
        _no_toll(r, p, "the appeal continues on its regular clock during the fraud review")
        _open_no_decision(r, p)
        if not re.search(r"status", _col(r, "Notes"), re.I) or _eq(_col(r, "Notes"), _col(r0, "Notes")):
            p.append("log the status update in the tracker: append to 'Notes' e.g. '11/04/2026: status update email "
                     "sent to member (decision due 12/13/2026)'")
        yield not p, "Appeals Log row CASE-2026-00437: " + "; ".join(p) + ".", [R_FRAUD, R_FRAUD_OUT, R_STATUS_LOG,
                                                                               R_BACKDATE]

    # CASE-2026-00443 (Roberto Casillas, received 2026-11-04 07:32)
    mine = [x for x in new if _col(x, "Member ID") == "VA-88291-03"]
    if not mine:
        yield False, ("Roberto Casillas' appeal (email received 2026-11-04 07:32 at appeals-intake) is not in the "
                      "Appeals Log. Add a row: Case ID CASE-2026-00443 | Member ID VA-88291-03 | Group ID G-14827 | "
                      "Plan Year 2024 | Appeal Type Post-Service Standard | Service Classification Medical/Surgical | "
                      "Standard of Review Medical Necessity | Date of Receipt 2026-11-04 07:32 | Acknowledgment Due "
                      "2026-11-11 | Acknowledgment Sent 2026-11-04 | Tolled N | Decision Due 2027-01-03 | Reviewer "
                      "Assigned (RN Reviewer team) | Parity Flag N | Compliance Escalation | External Review "
                      "Requested N | Case Status With Reviewer | Coordinator J. Mills."), \
            [R_LOG_STEP, R_SETCLOCK, R_CASEID, R_RECEIPT2, R_TIMES, R_CAL, R_COLDESC]
    else:
        r = mine[0]
        p = []
        if _col(r, "Case ID") != "CASE-2026-00443":
            p.append(f"'Case ID' = CASE-2026-00443 (next sequential after CASE-2026-00442; got '{_col(r, 'Case ID')}')")
        want = {"Group ID": "G-14827", "Plan Year": "2024", "Standard of Review": "Medical Necessity"}
        for c, v in want.items():
            if not _eq(_col(r, c), v):
                p.append(f"'{c}' = {v} (got '{_col(r, c)}')")
        if not re.search(r"post[- ]?service", _col(r, "Appeal Type"), re.I) or re.search(
                r"expedit", _col(r, "Appeal Type"), re.I):
            p.append(f"'Appeal Type' = Post-Service Standard (got '{_col(r, 'Appeal Type')}')")
        sc = _col(r, "Service Classification")
        if blank(sc) or re.search(r"SUD|behavioral|mental|pharm", sc, re.I):
            p.append(f"'Service Classification' = Medical/Surgical (got '{sc}')")
        if not dt_ok(_col(r, "Date of Receipt"), dt.date(2026, 11, 4), "07:32"):
            p.append(f"'Date of Receipt' = 2026-11-04 07:32, the intake queue timestamp (got "
                     f"'{_col(r, 'Date of Receipt')}')")
        _filled(r, p, HINT_00443)
        for c, day in (("Acknowledgment Due", dt.date(2026, 11, 11)), ("Acknowledgment Sent", dt.date(2026, 11, 4)),
                       ("Decision Due", dt.date(2027, 1, 3))):
            if not blank(_col(r, c)) and not dt_ok(_col(r, c), day):
                p.append(f"'{c}' = {_fmt(day)} (got '{_col(r, c)}')")
        _no_toll(r, p, "nothing has been requested")
        rv = _col(r, "Reviewer Assigned")
        if rv and re.search(r"Ontario|parity", rv, re.I):
            p.append(f"'Reviewer Assigned' = the RN Reviewer team (medical/surgical, under $75,000; got '{rv}')")
        st = _col(r, "Case Status")
        if st and not re.search(r"with reviewer", st, re.I):
            p.append(f"'Case Status' = With Reviewer once routed via Format B-1 (got '{st}')")
        er = _col(r, "External Review Requested")
        if er and not re.match(r"n", er, re.I):
            p.append(f"'External Review Requested' = N (got '{er}')")
        _open_no_decision(r, p)
        yield not p, "Appeals Log row for Roberto Casillas (CASE-2026-00443): " + "; ".join(p) + ".", \
            [R_LOG_STEP, R_SETCLOCK, R_CASEID, R_RECEIPT2, R_TIMES, R_CAL, R_COLDESC, R_COLDESC2]


RULES = [
    *comm_rules("msg", specs),
    *no_placeholders([R_SUBJ, R_A1], literal=("[Will continue on regular clock]",)),
    *pre_rule("slack.phi_public", _phi_public, [R_PHI, R_CH, R_CASEREF]),
    *pre_rule("slack.parity_channel", _parity_channel, [R_B3_DM, R_B2_FIELDS, R_DMUSE]),
    *pre_rule("email.subject_format", _subject_format, [R_SUBJ]),
    *pre_rule("email.signature", _signature, [R_SIGN]),
    *pre_rule("email.reviewer_names", _reviewer_names, [R_REVNAME]),
    *pre_rule("email.no_fraud_mention", _no_fraud, [R_B6_NOMENTION, R_FRAUD_OUT]),
    *pre_rule("email.cross_member_phi", _cross_member, [R_PHI_OUT]),
    *pre_rule("email.no_regulator", _regulator, [R_NO_REG, R_DOI]),
    *pre_rule("email.no_promises", _promises, [R_PROMISE, R_NO_COMMIT, R_NO_SETTLE, R_COMMIT2, R_TONE, R_SPECULATE]),
    *pre_rule("email.outside_parties", _outside_parties, [R_OUTSIDE, R_PHI_OUT]),
    *pre_rule("letters.mednec_wording", _mednec, [R_MEDNEC]),
    *pre_rule("letters.no_determination", _no_determination,
              [R_NO_DET, R_NO_DET2, R_DRAFT_DET, R_PAR_NOLETTER, R_CONCUR]),
    *pre_rule("letters.dismissal_scope", _dismiss_scope, [R_UNTIMELY, R_DISMISS_IND, R_POST]),
    *pre_rule("letters.no_external_review", _external_review, [R_EXT, R_ERO]),
    *pre_rule("case00442.standing", _case_00442_intake, [R_PROV_EXC, R_PROV_STAND]),
    *pre_rule("case00442.hold_draft", _case_00442_hold, [R_DISMISS_SUP, R_ESC_WAIT, R_DISMISS_IND]),
    *pre_rule("case00441.parity_routing", _case_00441_routing, [R_PAR_REPL, R_PAR_EXCL, R_ONTARIO, R_B1_EXP]),
    *pre_rule("case00441.coverage", _case_00441_lapse, [R_CONC_COVER, R_CONC]),
    *pre_rule("files.parity_concurrence", _parity_concurrence_file, [R_CONCUR]),
    *pre_rule("email.casillas_case_id", _casillas_case_id, [R_CASEID]),
    *state_rule("log.appeals_log", _log_checks, "Update appeals_log_master.xlsx as listed."),
]
