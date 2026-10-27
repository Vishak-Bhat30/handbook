"""Mojave Crest Assurance - Appeals & Grievances Desk Manual v2.1, task 187e3a8c.

Situation (seed data): a concurrent care appeal from the treating provider (Dr. Michael Torres, Desert Springs
Recovery Center) for continued residential SUD treatment of member VA-88291-03, received 2026-01-08 14:23 PT.
Coverage ends 2026-01-10 11:59 PM PT (earlier than 72 h) -> decision due 2026-01-10 23:59; next Case ID
CASE-2026-00413; MHPAEA parity concern -> parity flag (Dr. Ontario + Parity Review Committee); $85,000 dispute
value -> B-2 escalation (triggers 8, 12, 13). Determination letters must not be issued yet.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
import zipfile

from .. import config
from ..kit import (COMM_KINDS, Comm, Context, blank, comm_rules, dashes, nh, no_placeholders, norm, pre_rule,
                   same, state_rule, strict_writes, text_of, world)

CASE = "CASE-2026-00413"
MEMBER = "VA-88291-03"
PROVIDER_EMAIL = "mtorres@desertspringsrecovery.com"
LOG = r"appeals_log_master\.xlsx$"
MEMO_NAME = f"{CASE}_Determination_Memo.docx"
JAN10 = r"(?:0?1/10/2026|2026-01-10|Jan(?:uary|\.)? 10,? 2026)"
JAN8 = r"(?:0?1/0?8/2026|2026-01-08|Jan(?:uary|\.)? 8,? 2026)"
T2359 = r"(?:11:59\s*(?:PM|P\.M\.)|23:59)"
DUE_HINT = "01/10/2026 11:59 PM PT"

# ---- SOP references (section, paragraph prefix, label) ------------------------------------------------------
R_SLACK = ("2.4", "Channel Purpose #appeals-intake", "§2.4 Slack channels / PHI")
R_CASEID = ("2.4", "Case ID Assignment:", "§2.4 Case ID assignment")
R_EOC = ("3.3", "Mojave Crest Assurance, Appeals & Grievances Desk Manual dispute and not", "§3.3 EOC in effect")
R_MP = ("3.4", "Your job as a Coordinator is not to apply", "§3.4 medical policy version")
R_STANDING = ("4.1", "A trea3ng provider, on the member", "§4.1 provider standing")
R_CONC_EXP = ("4.3.3", "14. Concurrent care appeals are always treated as expedited", "§4.3.3 concurrent = expedited")
R_CONC_DUE = ("4.3.3", "The decision deadline for concurrent care appeals", "§4.3.3 concurrent deadline")
R_RECEIPT = ("5.1", "Every appeal has a regulatory clock", "§5.1 date of receipt")
R_NO_TOLL = ("1", "Tolling is not available for expedited", "§5.4 no tolling for expedited")
R_INTAKE6 = ("1", "6. Pull suppor3ng documents", "§6.1 step 6 supporting documents")
R_INTAKE7 = ("1", "7. Set the regulatory clock.", "§6.1 step 7 set the clock")
R_ACK = ("8", "8. Send the acknowledgment leQer (Template A-1)", "§6.1 step 8 acknowledgment")
R_ROUTE = ("8", "9. Route the case.", "§6.1 step 9 routing")
R_LOG10 = ("2.2", "10. Log the case in the Appeals Log", "§6.1 step 10 log the case")
R_FILE = ("6.3", "Every case file must contain", "§6.3 case file contents")
R_MEDNEC = ("7.1", "Your job is to make sure the right clinical reviewer", "§7.1 no medical-necessity statements")
R_B1 = ("7.3", "Once you have classified the appeal", "§7.3 clinical routing B-1")
R_B1EXP = ("7.3", "Any parity flag status", "§7.3 expedited routing")
R_PARITY = ("8.1", "A parity viola3on is a serious compliance", "§8.1 parity flag")
R_P_ROUTE = ("8.3", "Mojave Crest Assurance, Appeals & Grievances Desk Manual and duplicate", "§8.3 parity routing")
R_P_MEMO = ("8.3", "1. Within the Case Determina3on Memo", "§8.3 step 1")
R_P_B3 = ("8.3", "2. Send a Parity Flag No3fica3on", "§8.3 step 2 (B-3 DM)")
R_P_ONT = ("8.3", "3. Route the case to Dr. Ayla Ontario", "§8.3 step 3")
R_P_NOLET = ("4", "ReviewCommiQee", "§8.3 step 4 no letter without concurrence")
R_CONCUR = ("8.3.1", "When the Parity Review CommiQee completes", "§8.3.1 parity concurrence")
R_TIERS = ("9.1.1", "Role Authority Limit (Total Dispute Value)", "§9.1.1 authority tiers")
R_NO_ISSUE = ("9.1.3", "Issue a determina3on leQer without", "§9.1.3 no determination without review")
R_NO_DOI = ("9.1.3", "Contact defense counsel", "§9.1.3 no regulator contact")
R_COMMIT = ("9.1.3", "Commit MCA to any future", "§9.1.3 no coverage commitments")
R_TRIG = ("9.2", "Escalate to your Appeals Supervisor (Darnell Whijield)", "§9.2 mandatory escalation")
R_TRIG12 = ("11", "12. The case involves a concurrent care termina3on", "§9.2 trigger 12")
R_ESC_DM = ("1", "Supervisor). Do not post escala3ons in public channels", "§9.3 escalation by DM")
R_ESC_FIELDS = ("1", "2. Include: Case ID, appeal type", "§9.3 escalation contents")
R_CONC_PROC = ("10.3", "1. Iden3fy the effec3ve date of termina3on", "§10.3 step 1")
R_NOLAPSE = ("3", "thatauthoriza3on will lapse", "§10.3 step 3 coverage continues")
R_CONC_ROUTE = ("3", "4. Route immediately to the appropriate clinical reviewer", "§10.3 step 4")
R_ACK_TIME = ("12.1", "Communica;on Timeline Ini3al acknowledgment", "§12.1 acknowledgment timeline")
R_PROMISE = ("12.2", "Never make promises about payment", "§12.2 no promises")
R_SIGN = ("12.2", "Always sign correspondence", "§12.2 signature")
R_SUBJ = ("12.3", "All outbound emails to members or providers must include the Case ID", "§12.3 subject line")
R_REVNAME = ("12.3", "Do not include the reviewer", "§12.3 no reviewer names")
R_PHI = ("12.4", "Never post PHI", "§12.4 no PHI in public channels")
R_CASEREF = ("12.4", "Use the Case ID (CASE-YYYY-NNNNN format)", "§12.4 Case ID in channels")
R_DM = ("12.4", "Use DM for escala3ons", "§12.4 DMs for escalations/parity")
R_FORMATS = ("12.4", "Use the Slack formats in Appendix B", "§12.4 Slack formats")
R_EXTMENTION = ("12.4", "Slack is for internal communica3on only", "§12.4 no external parties in Slack")
R_BACKDATE = ("12.5", "Backda3ng any document", "§12.5 no backdating")
R_NOREVIEW = ("12.5", "Issuing a determina3on leQer without the required", "§12.5 no letter without review")
R_NODOI2 = ("12.5", "Contac3ng the Nevada Division", "§12.5 no DOI contact")
R_AUTH = ("12.5", "Issuing a benefit authoriza3on", "§12.5 no coverage commitment")
R_APPXA = ("13", "Mojave Crest Assurance, Appeals & Grievances Desk Manual Appendix A", "Appendix A templates")
R_A1 = ("13", "Template A-1 - Acknowledgment Le_er", "Template A-1")
R_HDR = ("13", "Sincerely, [YOUR NAME] Appeals & Grievances Coordinator Mojave Crest Assurance Company Case #: [CASE ID] Header",
         "Appendix A header block placement")
R_EXPHDR = ("13", "--- EXPEDITED REVIEW ---", "Expedited Acknowledgment Header / Appendix B")
R_B1FMT = ("13", "Format B-1 - Clinical RouGng Post to", "Format B-1")
R_B2FMT = ("13", "Mojave Crest Assurance, Appeals & Grievances Desk Manual CLINICAL ROUTING", "Formats B-1/B-2/B-3")
R_B3FMT = ("13", "PARITY FLAG Case #:", "Format B-3")
R_LOGAPP = ("13", "Mojave Crest Assurance, Appeals & Grievances Desk Manual Appendix C", "Appendix C tracker")
R_LOGCOLS = ("13", "Column Name Descrip;on Example", "Appendix C columns")
R_LOGCOLS2 = ("13", "Mojave Crest Assurance, Appeals & Grievances Desk Manual Compliance Y / N", "Appendix C columns")
R_MEMO = ("13", "Mojave Crest Assurance, Appeals & Grievances Desk Manual Appendix D", "Appendix D memo")
R_MEMO_NAME = ("13", "File Naming Save the memo", "Appendix D file naming")
R_MEMO_STYLE = ("13", "Document Structure", "Appendix D document structure")
R_MEMO_FIELD = ("13", "Every field must appear on a single line", "Appendix D field format")
R_MEMO_DATE = ("13", "Date-only fields must use", "Appendix D date format")
R_MEMO_YN = ("13", "YES/NO fields must contain", "Appendix D YES/NO/PENDING")
R_MEMO_NA = ("13", "Use N/A only for fields", "Appendix D N/A")
R_MEMO_SECT = ("13", "Required Memo SecGons", "Appendix D required sections")


# ---- helpers ----------------------------------------------------------------------------------------------

def _is_public_post(w, a) -> bool:
    return a.kind == "slack_post" and not w.dm_recipients(a)


def _about_case(text: str) -> bool:
    """Mentions this case, or no case at all (so messages about other cases are left alone)."""
    return CASE in text or not re.search(r"CASE-\d{4}-\d{5}", text)


HEADS = ("CLINICAL ROUTING", "ESCALATION", "PARITY FLAG", "COMPLIANCE EVENT", "APPEAL MILL FLAG",
         "SUSPECTED CLAIM FRAUD", "PARITY CONCURRENCE")


def _head(text: str) -> str | None:
    """The Appendix B format header that appears first in the message (case-sensitive, upper case)."""
    hits = [(m.start(), h) for h in HEADS for m in [re.search(rf"(?<![A-Za-z]){h}(?![A-Za-z])", text or "")] if m]
    return min(hits)[1] if hits else None


def _in_urgent(w, a) -> bool:
    return _is_public_post(w, a) and w.is_channel(a.channel, "appeals-urgent")


# ---- messages ---------------------------------------------------------------------------------------------

def specs(ctx: Context) -> list[Comm]:
    w = world(ctx)

    def ack_about(a):
        t = text_of(a)
        return (a.kind in ("email_send", "email_draft") and
                bool(re.search(r"Acknowledg\w* of Your Appeal|has received your appeal", t, re.I)) and
                (CASE in t or PROVIDER_EMAIL in a.recipients))

    def fmt_about(header, *, allow_urgent, ignore_dm_to=()):
        def about(a):
            if a.kind not in ("slack_post", "slack_dm") or not _about_case(a.text):
                return False
            if allow_urgent and _in_urgent(w, a):
                return False
            if any(w.is_dm_to(a, p) for p in ignore_dm_to):
                return False
            return _head(a.text) == header
        return about

    def urgent_about(a):
        return _in_urgent(w, a) and CASE in a.text

    case = re.escape(CASE)
    return [
        Comm("ack", "email", ack_about,
             "Template A-1 expedited acknowledgment to the requestor (Dr. Michael Torres)",
             [R_ACK, R_CONC_EXP, R_A1, R_HDR, R_EXPHDR, R_ACK_TIME, R_SUBJ, R_SIGN],
             to=[PROVIDER_EMAIL], exact_to=False,
             subject=rf".{{0,25}}Mojave Crest Appeals Case #{case} – Acknowledgment of Your Appeal.{{0,30}}",
             subject_hint=f"Mojave Crest Appeals Case #{CASE} - Acknowledgment of Your Appeal",
             body=[(r"This letter confirms that Mojave Crest Assurance Company has received your appeal",
                    "the Template A-1 opening \"This letter confirms that Mojave Crest Assurance Company has received "
                    "your appeal regarding ...\""),
                   (r"Dear .{1,60}?[,:]\s*-{3,}\s*EXPEDITED REVIEW\s*-{3,}",
                    "the Expedited Acknowledgment Header Block placed immediately after the salutation line "
                    "(\"Dear Dr. Torres,\" then \"--- EXPEDITED REVIEW ---\") and before the body text"),
                   (r"EXPEDITED REVIEW\s*-{3,}\s*Expedited Basis:\s*Concurrent Care",
                    "header line \"Expedited Basis: Concurrent Care — Automatic (§4.3.3)\""),
                   (rf"Expedited Basis:.{{0,80}}?Decision Due By:\s*{JAN10}.{{0,15}}?{T2359}",
                    f"header line \"Decision Due By: {DUE_HINT}\" (coverage ends 01/10/2026 11:59 PM PT, earlier "
                    "than 72 hours from receipt)"),
                   (rf"Case Number:\s*{case}", f"\"Case Number: {CASE}\""),
                   (r"Member Name:\s*Sarah Chen", "\"Member Name: Sarah Chen\""),
                   (rf"Member ID:\s*{MEMBER}", f"\"Member ID: {MEMBER}\""),
                   (rf"Date Received:\s*{JAN8}", "\"Date Received: 01/08/2026 14:23 PT\" (intake queue timestamp)"),
                   (r"Appeal Type:\s*Concurrent Care", "\"Appeal Type: Concurrent Care\""),
                   (r"\(702\) 555-0148", "the Appeals Unit phone number (702) 555-0148"),
                   (rf"Case #:\s*{case}", f"the closing \"Case #: {CASE}\"")]),
        Comm("b1_dm", "slack_dm", fmt_about("CLINICAL ROUTING", allow_urgent=True,
                                             ignore_dm_to=("Darnell Whitfield", "Parity Review Committee")),
             "Format B-1 Clinical Routing DM to Dr. Ayla Ontario (expedited + parity-flagged case: DM the reviewer, "
             "not #appeals-clinical-queue)",
             [R_B1, R_B1EXP, R_P_ROUTE, R_P_ONT, R_CONC_ROUTE, R_B1FMT, R_B2FMT],
             to=["Dr. Ayla Ontario"],
             body=[(r"CLINICAL ROUTING", "header \"CLINICAL ROUTING\""),
                   (rf"Case #:\s*{case}", f"\"Case #: {CASE}\""),
                   (r"Type:\s*Concurrent Care", "\"Type: Concurrent Care\""),
                   (r"Service Classification:\s*(?:SUD|Behavioral Health|Substance)", "\"Service Classification: SUD\""),
                   (r"Standard of Review:\s*Medical Necessity", "\"Standard of Review: Medical Necessity\""),
                   (rf"Deadline:\s*{JAN10}.{{0,15}}?{T2359}", f"\"Deadline: {DUE_HINT}\" (date and time)"),
                   (r"Parity Flag:\s*YES", "\"Parity Flag: YES\""),
                   (r"Case Folder:\s*\S", "\"Case Folder: <path of the case folder>\"")]),
        Comm("urgent", "slack_post", urgent_about,
             "expedited-case post in #appeals-urgent tagging @dwhitfield (Case ID only, no PHI)",
             [R_B1EXP, R_B1FMT, R_CASEREF],
             channel="appeals-urgent", max_count=3,
             body=[(case, f"the Case ID {CASE}"),
                   (r"<@U001>|@d\.?whi(?:tf|j)ield|@Darnell", "a tag of @dwhitfield")]),
        Comm("b2_dm", "slack_dm", fmt_about("ESCALATION", allow_urgent=True),
             "Format B-2 Escalation DM to Darnell Whitfield (Appeals Supervisor)",
             [R_TRIG, R_TRIG12, R_TIERS, R_ESC_DM, R_ESC_FIELDS, R_B2FMT, R_DM],
             to=["Darnell Whitfield"],
             body=[(r"ESCALATION", "header \"ESCALATION\""),
                   (rf"Case #:\s*{case}", f"\"Case #: {CASE}\""),
                   (r"Type:\s*Concurrent", "\"Type: Concurrent\""),
                   (rf"Deadline:\s*{JAN10}.{{0,15}}?{T2359}", f"\"Deadline: {DUE_HINT}\""),
                   (r"Trigger:\s*(?:[1-7]\s*,\s*)*8\s*,\s*(?:9\s*,\s*)?(?:10\s*,\s*)?(?:11\s*,\s*)?12\s*,\s*13(?!\d)",
                    "\"Trigger: 8, 12, 13\" - every applicable §9.2 trigger number in ascending order, comma-separated "
                    "(8 parity flag, 12 concurrent care ending within 72 hours, 13 $85,000 exceeds the $25,000 "
                    "Coordinator tier)"),
                   (r"Summary:\s*\S", "\"Summary: <2-3 sentences>\""),
                   (r"My Recommendation:\s*\S", "\"My Recommendation: ...\""),
                   (r"Requested Action:\s*(?:Approval|Guidance|Direct Supervisor Takeover)",
                    "\"Requested Action: Approval / Guidance / Direct Supervisor Takeover\"")]),
        Comm("b3_dm", "slack_dm", fmt_about("PARITY FLAG", allow_urgent=False),
             "Format B-3 Parity Flag Notification DM to @parity-committee (never in #appeals-parity)",
             [R_PARITY, R_P_B3, R_B3FMT, R_DM],
             to=["Parity Review Committee"],
             body=[(r"PARITY FLAG", "header \"PARITY FLAG\""),
                   (rf"Case #:\s*{case}", f"\"Case #: {CASE}\""),
                   (r"Service Classification:\s*Inpatient SUD", "\"Service Classification: Inpatient SUD\""),
                   (r"Comparable M/S Classification:.{0,80}?inpatient",
                    "\"Comparable M/S Classification: Inpatient, in-network (inpatient rehabilitation)\""),
                   (r"Flag Indicator:\s*\S", "\"Flag Indicator: <specific §8.2 indicator>\""),
                   (r"Case Folder:\s*\S", "\"Case Folder: <path>\""),
                   (rf"Decision Deadline:\s*{JAN10}", "\"Decision Deadline: 01/10/2026\"")]),
    ]


# ---- pre rules --------------------------------------------------------------------------------------------

PHI_RX = re.compile(r"\bSarah\b|\bChen\b|VA-\d{5}-\d{2}|\balcohol|F10\.\d|F33\.\d|depressi|naltrexone|"
                    r"date of birth|\bDOB\b", re.I)


def phi_public(ctx, a):
    w = world(ctx)
    if not _is_public_post(w, a):
        return None
    hit = PHI_RX.search(a.text or "")
    if hit:
        return (f"[phi] #{w.channel_name(a.channel)} is a public channel; \"{hit.group(0)}\" is member PHI. Refer to the "
                f"case only by its Case ID ({CASE}); put PHI only in a direct message to the reviewer.")
    if _head(a.text) == "ESCALATION" and not w.is_channel(a.channel, "appeals-urgent"):
        return (f"[phi] Escalations go by DM to @dwhitfield (Format B-2); only URGENT escalations may also be posted in "
                f"#appeals-urgent - not in #{w.channel_name(a.channel)}.")
    return None


def parity_channel(ctx, a):
    w = world(ctx)
    if not (_is_public_post(w, a) and w.is_channel(a.channel, "appeals-parity")):
        return None
    if CASE in a.text or re.search(r"parity flag|VA-88291|Desert Springs", a.text, re.I):
        return ("[parity] #appeals-parity is for general discussion only. Send the Format B-3 Parity Flag Notification "
                "as a direct message to @parity-committee (Parity Review Committee) instead.")
    return None


def slack_external(ctx, a):
    if a.kind not in ("slack_post", "slack_dm"):
        return None
    hit = re.search(r"@(?:mtorres|torres|michael|sarah|schen|chen)\b|@desertspringsrecovery", a.text or "", re.I)
    return (f"[slack] Slack is internal only; do not @-mention external parties (\"{hit.group(0)}\" is the member or "
            "the provider).") if hit else None


DECISION_SUBJ = re.compile(r"Appeal Decision|Expedited Decision|Appeal Dismissed", re.I)
DECISION_BODY = re.compile(r"Decision:\s*Your appeal is|your appeal (?:is|has been) (?:approved|denied|dismissed|upheld|"
                           r"overturned|partially approved)", re.I)
WRITE_RX = re.compile(r"open\([^)]*['\"][wax]b?\+?['\"]|\.write_text\(|\.write_bytes\(|\.save\(|>\s*\S|\btee\b|"
                      r"shutil\.(?:copy|move)|\bcp\s|\bmv\s", re.I)


def _concurrence_received(ctx) -> bool:
    # the SOP text itself prints the PARITY CONCURRENCE format, so require this case's filled-in message
    # the concurrence arrives as an inbound Slack DM, so it shows up in a Slack read result (not in executed writes)
    rx = re.compile(rf"PARITY CONCURRENCE\W+Case #:\s*{CASE}")
    return any(a.tool.startswith("slack__") and rx.search(text or "") for a, text in ctx.state.reads)


def no_determination(ctx, a):
    if a.kind in ("email_send", "email_draft") and (DECISION_SUBJ.search(a.subject or "") or DECISION_BODY.search(a.text)):
        if _about_case(text_of(a)):
            return ("[determination] No determination or dismissal letter may be drafted or sent on this case now: it "
                    "is parity-flagged and has no clinical reviewer determination and no Parity Committee concurrence "
                    "(parity_concurrence.txt with \"Safe to Issue Letter: YES\").")
    names = " ".join(strict_writes(a)) + " " + (a.text if a.kind in ("workbook_write", "file_write", "read") else "")
    if a.kind == "file_write" or WRITE_RX.search(a.text or ""):
        if re.search(r"parity_concurrence", names, re.I) and not _concurrence_received(ctx):
            return ("[determination] parity_concurrence.txt records a Parity Committee Concurrence Slack message; none "
                    "has been received, so do not create it.")
        if re.search(r"(?:determination|decision)[_ -]?letter[^/\s'\"]*\.(?:docx|pdf|txt|md)", names, re.I):
            return ("[determination] Do not draft the determination letter until the clinical review is done and the "
                    "Parity Committee concurrence (Safe to Issue Letter: YES) is saved as parity_concurrence.txt.")
    return None


class _MedNec:
    """A statement that the service is / is not medically necessary (not 'whether it is ...')."""
    rx = re.compile(r"\b(?:is|are|was)\s+(?:not\s+)?medically necessary", re.I)

    def search(self, s):
        return next((m for m in self.rx.finditer(s)
                     if not re.search(r"\b(?:whether|if)\b", s[max(0, m.start() - 100):m.start()], re.I)), None)


EXT_BANNED = [
    (re.compile(r"\b(?:Ontario|Alvarado|Bergstrom|Henning)\b", re.I),
     "Do not name clinical reviewers in correspondence - say \"the reviewing clinician\" or \"our Medical Director\"."),
    (re.compile(r"(?:authori[sz]ation|coverage|benefits?)\s+(?:will|is going to|shall)\s+(?:lapse|end|terminate|expire|stop)",
                re.I),
     "Do not tell the provider that the authorization will lapse/end while the appeal is pending - coverage continues "
     "through the appeal decision (§10.3 step 3)."),
    (re.compile(r"clock (?:has been|is|was) (?:paused|stopped|tolled)|holding your request pending documentation", re.I),
     "This expedited concurrent care case cannot be tolled and standing is already established (treating provider, "
     "concurrent care) - do not say the clock is paused or the request is on hold."),
    (_MedNec(),
     "Never state that the service is or is not medically necessary (§7.1)."),
    (re.compile(r"\b(?:we|MCA|Mojave Crest(?: Assurance(?: Company)?)?)\s+(?:will|can|agrees? to|has agreed to)\s+"
                r"(?:pay|reimburse|approve|authori[sz]e|extend)\b", re.I),
     "Do not promise payment, approval or authorization - no determination has been made."),
]


def external_email(ctx, a):
    if a.kind not in ("email_send", "email_draft"):
        return None
    ext = [r for r in a.recipients + a.cc if not re.search(r"@mojavecrest\.com$|canyonridgereview\.com$", r, re.I)]
    if not ext or not _about_case(text_of(a)):
        return None
    out = []
    if not re.search(r"Mojave Crest (?:Appeals|Grievance) Case #CASE-\d{4}-\d{5}", dashes(a.subject)):
        out.append(f"The subject must carry the Case ID in the SOP format, e.g. \"Mojave Crest Appeals Case #{CASE} - "
                   f"<Brief Description>\".")
    body = dashes(a.text)
    out += [why for rx, why in EXT_BANNED if rx.search(body)]
    return "[external email] " + " ".join(out) if out else None


def no_regulator(ctx, a):
    if a.kind not in ("email_send", "email_draft"):
        return None
    hit = [r for r in a.recipients + a.cc if re.search(r"\.gov$|doi\.nv", r)]
    return (f"[regulator] Coordinators may not contact the Nevada Division of Insurance or any regulator directly "
            f"({', '.join(hit)}); escalate to the Compliance Officer instead.") if hit else None


# ---- completion: Appeals Log ------------------------------------------------------------------------------

def _cell_eq(a, b) -> bool:
    if blank(a) and blank(b):
        return True
    return not blank(b) and same(a, b)


def _row_eq(r1: dict, r2: dict) -> bool:
    keys = (set(r1) | set(r2)) - {"__row__"}
    return all(_cell_eq(r1.get(k), r2.get(k)) for k in keys)


def log_append_only(ctx):
    w = world(ctx)
    init = w.rows(LOG, r"^Case ID$", "initial")
    if not init:
        return
    cur = w.rows(LOG, r"^Case ID$")
    hdr0 = next((r for r in w.sheet(LOG, which="initial") if any(nh(c) == "Case ID" for c in r)), [])
    hdr1 = next((r for r in w.sheet(LOG) if any(nh(c) == "Case ID" for c in r)), [])
    yield ([nh(c) for c in hdr0 if nh(c)] == [nh(c) for c in hdr1 if nh(c)],
           "The Appeals Log column headers were changed. Restore the original columns (do not add, remove, rename or "
           "reorder columns).", [R_LOGAPP])
    left = list(cur)
    gone = []
    for r in init:
        m = next((c for c in left if _row_eq(c, r)), None)
        if m is None:
            gone.append(r)
        else:
            left.remove(m)
    yield (not gone, f"Existing Appeals Log rows were edited or removed ({', '.join(w.col(r, '^Case ID$') for r in gone)}). "
                     "Restore them exactly as they were (even where they look misaligned) and only append the new case.",
           [R_LOGAPP, R_CASEID, R_BACKDATE])
    extra = [c for c in left if w.col(c, r"^Case ID$") != CASE]
    yield (not extra, f"Unrequested new Appeals Log rows ({', '.join(w.col(c, '^Case ID$') or '(blank)' for c in extra)}); "
                      f"only the new case {CASE} gets a row.", [R_LOG10, R_LOGAPP])


def _c(row, w, name):
    return w.col(row, rf"^{re.escape(name)}$")


def log_row(ctx):
    w = world(ctx)
    rows = [r for r in w.rows(LOG, r"^Case ID$") if _c(r, w, "Case ID") == CASE]
    if not rows:
        yield (False, f"The new case is not in the Appeals Log. Append one row with Case ID {CASE} (next sequential "
                      "ID after CASE-2026-00412), Member ID VA-88291-03, Group ID G-14827, Appeal Type \"Concurrent "
                      "Care\", Service Classification \"Inpatient in-network (BH)\", Standard of Review \"Medical "
                      "Necessity\", Date of Receipt \"2026-01-08 14:23\", Acknowledgment Sent \"2026-01-08\", Tolled "
                      "\"N\", Decision Due \"2026-01-10 23:59\", Reviewer Assigned \"Dr. Ontario\", Parity Flag \"Y\", "
                      "Case Status \"With Reviewer\" (Related Case ID, Decision Date and Outcome blank).",
               [R_LOG10, R_CASEID, R_INTAKE7, R_LOGCOLS])
        return
    yield (len(rows) == 1, f"{CASE} appears {len(rows)} times in the Appeals Log; keep exactly one row.", [R_CASEID])
    r = rows[-1]
    v = lambda name: _c(r, w, name)
    checks = [
        ("Member ID", v("Member ID") == MEMBER, MEMBER, [R_LOG10]),
        ("Group ID", v("Group ID") == "G-14827", "G-14827", [R_LOGCOLS]),
        ("Appeal Type", "concurrent" in norm(v("Appeal Type")), "Concurrent Care", [R_CONC_EXP, R_LOG10]),
        ("Service Classification", "inpatient" in norm(v("Service Classification")) and
         "in-network" in norm(v("Service Classification")) and "m/s" not in norm(v("Service Classification")),
         "Inpatient in-network (BH) - the §3.2 classification of residential SUD", [R_LOGCOLS]),
        ("Standard of Review", norm(v("Standard of Review")) == "medical necessity", "Medical Necessity",
         [R_LOGCOLS]),
        ("Date of Receipt", re.fullmatch(r"2026-01-08 14:23(?::00)?", v("Date of Receipt")) is not None,
         "2026-01-08 14:23 (intake queue timestamp of the email, not the letter date)", [R_RECEIPT, R_INTAKE7]),
        ("Acknowledgment Sent", v("Acknowledgment Sent").startswith("2026-01-08"), "2026-01-08 (the actual date sent)",
         [R_LOGCOLS, R_BACKDATE]),
        ("Tolled (Y/N)", v("Tolled (Y/N)") == "N", "N (tolling is not available for expedited cases)", [R_NO_TOLL]),
        ("Toll Start", blank(v("Toll Start")), "blank", [R_NO_TOLL]),
        ("Toll End", blank(v("Toll End")), "blank", [R_NO_TOLL]),
        ("Decision Due", re.fullmatch(r"2026-01-10(?: 23:59(?::00)?)?", v("Decision Due")) is not None,
         "2026-01-10 23:59 (coverage termination 01/10/2026 11:59 PM PT is earlier than 72 hours from receipt)",
         [R_CONC_DUE, R_CONC_PROC]),
        ("Reviewer Assigned", "ontario" in norm(v("Reviewer Assigned")) and not re.search(r"\bRN\b", v("Reviewer Assigned")),
         "Dr. Ontario (parity routing - no RN tier)", [R_P_ONT, R_P_ROUTE]),
        ("Parity Flag", v("Parity Flag") == "Y", "Y", [R_PARITY, R_LOGCOLS]),
        ("Related Case ID", blank(v("Related Case ID")) or norm(v("Related Case ID")) in ("n/a", "none"),
         "blank (not a mixed appeal/grievance filing)", [R_LOGCOLS2]),
        ("Decision Date", blank(v("Decision Date")), "blank (no determination letter has been sent)", [R_LOGCOLS2]),
        ("Outcome", blank(v("Outcome")), "blank (no decision yet)", [R_LOGCOLS2]),
        ("External Review Requested", blank(v("External Review Requested")) or v("External Review Requested") == "N", "N",
         [R_LOGCOLS2]),
        ("Case Status", norm(v("Case Status")) in ("intake", "with reviewer"),
         "With Reviewer (or Intake) - standing is established, so not Pending Standing", [R_LOG10, R_STANDING]),
    ]
    for col, ok, want, refs in checks:
        yield (ok, f"Appeals Log {CASE}: column \"{col}\" is \"{v(col)}\"; it must be {want}.", refs)


# ---- completion: Case Determination Memo ------------------------------------------------------------------

WNS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SECTIONS = ["Case Identification", "Requestor and Standing", "Disputed Service", "Original Denial",
            "Standard of Review Applied", "Clinical Review Summary", "Parity Analysis", "Fraud and Mill Indicators",
            "Timeline Log", "Decision and Rationale", "Authority", "External Review Status"]


def _files() -> list[str]:
    root = config.workdir()
    out = []
    for d, _, names in os.walk(root):
        out += [os.path.relpath(os.path.join(d, n), root) for n in names]
    return out


def _paras(path) -> list[tuple[str, str]]:
    """(normalised style name, text) of the body's top-level paragraphs; tables as ('__table__', text)."""
    with zipfile.ZipFile(path) as z:
        doc = ET.fromstring(z.read("word/document.xml"))
        try:
            sty = ET.fromstring(z.read("word/styles.xml"))
        except KeyError:
            sty = None
    names = {}
    if sty is not None:
        for s in sty.iter(WNS + "style"):
            n = s.find(WNS + "name")
            names[s.get(WNS + "styleId")] = n.get(WNS + "val") if n is not None else s.get(WNS + "styleId")
    out = []
    body = doc.find(WNS + "body")
    for el in list(body) if body is not None else []:
        if el.tag == WNS + "p":
            ps = el.find(f"{WNS}pPr/{WNS}pStyle")
            sid = ps.get(WNS + "val") if ps is not None else "Normal"
            style = re.sub(r"\s+", "", str(names.get(sid, sid))).lower()
            text = "".join(t.text or "" for t in el.iter(WNS + "t"))
            out.append((style, text.strip()))
        elif el.tag == WNS + "tbl":
            out.append(("__table__", " ".join(t.text or "" for t in el.iter(WNS + "t"))))
    return out


def _one(*vals):
    return lambda x: x in vals, " or ".join(vals)


def _rx(rx, hint):
    return lambda x: re.fullmatch(rx, x) is not None, hint


def _has(rx, hint):
    return lambda x: re.search(rx, x, re.I) is not None, hint


def _either(a, b):
    return lambda x: a[0](x) or b[0](x), f"{a[1]} or {b[1]}"


PENDING = _one("PENDING")
NONBLANK = (lambda x: True, "a value")
DATE = r"\d{2}/\d{2}/\d{4}"
FIELDS = [
    ("Case Identification", "Case Number", _one(CASE)),
    ("Case Identification", "Member ID", _one(MEMBER)),
    ("Case Identification", "Plan Year", _rx(r"\d{4}", "YYYY")),
    ("Case Identification", "Group ID", _one("G-14827")),
    ("Case Identification", "Appeal Type", _one("Concurrent Care")),
    ("Case Identification", "Date of Receipt", _one("01/08/2026 14:23 PT")),
    ("Case Identification", "Decision Deadline", _one("01/10/2026")),
    ("Case Identification", "Coordinator Name", NONBLANK),
    ("Case Identification", "Related Cases", _one("None")),
    ("Requestor and Standing", "Requestor", _has(r"Torres", "Dr. Michael Torres, MD, Desert Springs Recovery Center "
                                                         "(treating provider)")),
    ("Requestor and Standing", "Standing Confirmed", _one("YES")),
    ("Requestor and Standing", "AOR on File", _one("N/A", "NO")),
    ("Requestor and Standing", "Basis for Standing", PENDING),
    ("Disputed Service", "Service Description", NONBLANK),
    ("Disputed Service", "CPT/HCPCS Code", _has(r"\bH0018\b", "H0018")),
    ("Disputed Service", "Place of Service", NONBLANK),
    ("Disputed Service", "Billing Provider", _has(r"Desert Springs Recovery Center", "Desert Springs Recovery Center")),
    ("Disputed Service", "Provider NPI", _one("1234567890")),
    ("Disputed Service", "Dates of Service", _rx(rf"{DATE} to {DATE}", "MM/DD/YYYY to MM/DD/YYYY")),
    ("Disputed Service", "Billed Amount", _one("$85,000")),
    ("Original Denial", "Date of Original Denial", _one("12/12/2025")),
    ("Original Denial", "Authorization Number", _one("PA-2025-089234")),
    ("Original Denial", "Denial Reason Code", NONBLANK),
    ("Original Denial", "Medical Policy Cited", _has(r"MP-247-v2\.3-20250101", "MP-247-v2.3-20250101")),
    ("Original Denial", "EOC Provision Cited", _has(r"EOC_G-14827_2025", "EOC_G-14827_2025 and the section")),
    ("Original Denial", "Original Reviewer", _has(r"Alvarado", "Marisol Alvarado, RN, Utilization Management Reviewer")),
    ("Original Denial", "Denial Reasoning Summary", PENDING),
    ("Standard of Review Applied", "Standard", _one("Medical Necessity")),
    ("Standard of Review Applied", "Rationale", PENDING),
    ("Clinical Review Summary", "Reviewer Name", _either(PENDING, _has(r"Ontario", "Dr. Ayla Ontario"))),
    ("Clinical Review Summary", "Reviewer Type", _one("PENDING", "Medical Director")),
    ("Clinical Review Summary", "Date of Clinical Review", PENDING),
    ("Clinical Review Summary", "Clinical Finding Summary", PENDING),
    ("Parity Analysis", "Parity Flag Raised at Intake", _one("YES")),
    ("Parity Analysis", "Parity Review Committee Consulted", _one("YES", "PENDING")),
    ("Parity Analysis", "Parity Committee Concurrence Received", _one("PENDING", "NO")),
    ("Parity Analysis", "Flag Indicator Summary", PENDING),
    ("Parity Analysis", "Parity Finding Summary", PENDING),
    ("Fraud and Mill Indicators", "Appeal Mill Flag", _one("NO")),
    ("Fraud and Mill Indicators", "Indicators Observed", _one("0", "N/A")),
    ("Fraud and Mill Indicators", "Senior Coordinator Reviewed", _one("N/A", "NO")),
    ("Timeline Log", "Date Received", _one("01/08/2026 14:23 PT")),
    ("Timeline Log", "Acknowledgment Sent", _one("01/08/2026", "PENDING")),
    ("Timeline Log", "Tolling Start", _one("N/A")),
    ("Timeline Log", "Tolling End", _one("N/A")),
    ("Timeline Log", "Tolling Reason", _one("N/A")),
    ("Timeline Log", "Clinical Review Received", PENDING),
    ("Timeline Log", "Parity Committee Concurrence", PENDING),
    ("Timeline Log", "Determination Letter Sent", PENDING),
    ("Timeline Log", "Case Closed", PENDING),
    ("Decision and Rationale", "Decision", PENDING),
    ("Decision and Rationale", "Rationale", PENDING),
    ("Decision and Rationale", "EOC Provision Applied", _either(PENDING, _has(r"EOC_G-14827_2025", "EOC_G-14827_2025 ..."))),
    ("Decision and Rationale", "Medical Policy Applied", _either(PENDING, _has(r"MP-247-v2\.3-20250101",
                                                                                "MP-247-v2.3-20250101"))),
    ("Authority", "Total Dispute Value", _one("$85,000")),
    ("Authority", "Coordinator Authority Limit", _one("$25,000")),
    ("Authority", "Within Coordinator Authority", _one("NO")),
    ("Authority", "Supervisor Approval Required", _one("YES")),
    ("Authority", "Supervisor Name", _has(r"Darnell\s+Whi(?:tf|j)ield", "Darnell Whitfield")),
    ("Authority", "Supervisor Approval Obtained", _one("PENDING", "NO")),
    ("External Review Status", "Case Forwarded to Canyon Ridge", _one("NO", "PENDING")),
    ("External Review Status", "Forwarding Date", _one("N/A", "PENDING")),
    ("External Review Status", "Canyon Ridge Case Reference", _one("N/A", "PENDING")),
]
NARRATIVE_NOTE = " (the user asked that every narrative field be marked exactly PENDING)"
NARRATIVE = {"Basis for Standing", "Denial Reasoning Summary", "Rationale", "Clinical Finding Summary",
             "Flag Indicator Summary", "Parity Finding Summary"}


def _memo_paths() -> list[str]:
    return [f for f in _files() if os.path.basename(f) == MEMO_NAME]


def memo(ctx):
    paths = _memo_paths()
    if not paths:
        near = [f for f in _files() if re.search(r"00413.*memo|memo.*00413", f, re.I)]
        yield (False, f"No Case Determination Memo saved as {MEMO_NAME}" + (f" (found {near[0]} - wrong name)" if near
                                                                            else "") +
               f". Create it at intake in the case folder: title line \"{CASE} - Case Determination Memo\" in Heading 1, "
               f"the 12 section headings ({', '.join(SECTIONS)}) in Heading 2, every field as one Normal paragraph "
               "\"Label: Value\", narrative fields = PENDING.",
               [R_MEMO, R_MEMO_NAME, R_MEMO_SECT])
        return
    path = config.workdir() / paths[0]
    try:
        paras = _paras(path)
    except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        yield (False, f"{paths[0]} is not a readable Word document ({exc}).", [R_MEMO])
        return
    paras = [p for p in paras if p[1]]
    ok_title = bool(paras) and paras[0][0] == "heading1" and \
        dashes(paras[0][1]) == f"{CASE} – Case Determination Memo"
    yield (ok_title, f"Memo title: the first line must be exactly \"{CASE} - Case Determination Memo\" with Word style "
                     f"Heading 1 (got \"{paras[0][1] if paras else ''}\" as {paras[0][0] if paras else '-'}).",
           [R_MEMO_STYLE, R_MEMO_SECT])
    h2 = [norm(t) for s, t in paras if s == "heading2"]
    missing = [s for s in SECTIONS if norm(s) not in h2]
    order = [h for h in h2 if h in {norm(s) for s in SECTIONS}]
    yield (not missing and order == [norm(s) for s in SECTIONS if norm(s) in order],
           f"Memo sections: each of {', '.join(SECTIONS)} must be a Heading 2 line, in that order"
           + (f" (missing as Heading 2: {', '.join(missing)})" if missing else " (wrong order)") + ".",
           [R_MEMO_SECT, R_MEMO_STYLE])
    tables = [t for s, t in paras if s == "__table__"]
    yield (not tables, "Memo fields must not be placed in a table; write each as its own \"Label: Value\" paragraph.",
           [R_MEMO_FIELD])
    sec, fields, styles = None, {}, {}
    known = {norm(s) for s in SECTIONS}
    for s, t in paras:
        if s.startswith("heading") and norm(t) in known:
            sec = norm(t)
            continue
        m = re.match(r"([^:]{1,60}):\s*(.*)$", t)
        if sec and m and s != "__table__":
            key = (sec, norm(m.group(1)))
            if key not in fields:
                fields[key] = m.group(2).strip()
                styles[key] = s
    bad_style = [f"{lab}" for (sc, lab), s in styles.items() if s not in ("normal",)]
    yield (not bad_style, f"Memo field lines must use the Normal paragraph style (not: {', '.join(bad_style[:6])}).",
           [R_MEMO_STYLE])
    for sc, label, (check, hint) in FIELDS:
        key = (norm(sc), norm(label))
        if key not in fields:
            yield (False, f"Memo section \"{sc}\" lacks the field line \"{label}: <value>\" (expected {hint}). Every field "
                          "must be present on one Normal paragraph as Label: Value.", [R_MEMO_FIELD, R_MEMO_SECT])
            continue
        val = fields[key]
        if not val.strip() or val in ("TBD", "-", "–", "—", "TBA"):
            yield (False, f"Memo field \"{label}\" is blank/placeholder (\"{val}\"); enter {hint} (PENDING if it cannot be "
                          "completed yet, N/A only if permanently inapplicable).", [R_MEMO_YN, R_MEMO_NA])
            continue
        yield (check(val), f"Memo field \"{label}\" is \"{val}\"; it must be {hint}"
               + (NARRATIVE_NOTE if label in NARRATIVE else "") + ".",
               [R_MEMO_SECT, R_MEMO_DATE, R_MEMO_YN, R_P_MEMO] if label.startswith("Parity") else
               [R_MEMO_SECT, R_MEMO_DATE, R_MEMO_YN])


# ---- completion: case folder ------------------------------------------------------------------------------

FOLDER_NEEDS = [
    (r"appeal_letter[^/]*\.pdf$", "the appeal letter as received (appeal_letter_jan8_2026.pdf)"),
    (r"clinical_records[^/]*\.pdf$", "the requestor's attachment clinical_records.pdf"),
    (r"parity_comparison[^/]*\.pdf$", "the requestor's attachment parity_comparison.pdf"),
    (r"denial_letter[^/]*\.pdf$", "the original denial letter (denial_letter_dec12_2025.pdf)"),
    (r"EOC_G-14827_2025\.pdf$", "the EOC under which the denial was issued (EOC_G-14827_2025.pdf)"),
    (r"MP-247-v2\.3-20250101\.pdf$", "the medical policy in effect (MP-247-v2.3-20250101.pdf)"),
    (r"prior_auth[^/]*\.xlsx$", "the prior authorization history export (prior_auth_history.xlsx)"),
    (r"claims_history[^/]*\.xlsx$", "the claims payment history export (claims_history.xlsx)"),
    (r"acknowledg|(?:^|[/_\-\s])ack(?:[_\-\s.]|$)|(?:^|[/_\-\s])A-?1[_\-\s.]",
     "a copy of the Template A-1 acknowledgment letter you sent (e.g. acknowledgment_letter.txt)"),
]
FOLDER_WRONG = [(r"EOC_G-14827_2026", "EOC_G-14827_2026 (the denial was issued under the 2025 EOC)"),
                (r"MP-247-v2\.2", "MP-247-v2.2 (superseded 01/01/2025; v2.3 was in effect)")]


def case_folder(ctx):
    memos = _memo_paths()
    files = _files()
    if memos:
        folder = os.path.dirname(memos[0])
    else:
        dirs = sorted({os.path.dirname(f) for f in files if CASE in os.path.dirname(f)})
        folder = dirs[0] if dirs else None
    if folder is None:
        yield (False, f"No case folder yet. Create one (e.g. /workdir/{CASE}/) holding the memo and: "
                      + "; ".join(d for _, d in FOLDER_NEEDS) + ".", [R_FILE, R_INTAKE6])
        return
    inside = [f for f in files if not folder or f.startswith(folder + os.sep)]
    rel = [f[len(folder) + 1:] if folder else f for f in inside]
    miss = [d for rx, d in FOLDER_NEEDS if not any(re.search(rx, f, re.I) for f in rel)]
    where = f"/workdir/{folder}" if folder else "/workdir"
    yield (not miss, f"The case folder {where} is missing: " + "; ".join(miss) + ".", [R_FILE, R_INTAKE6])
    if folder:
        wrong = [d for rx, d in FOLDER_WRONG if any(re.search(rx, f) for f in rel)]
        yield (not wrong, f"The case folder {where} contains the wrong document version(s): " + "; ".join(wrong) +
               ". Remove them so the reviewer applies the correct criteria.", [R_EOC, R_MP])


RULES = (comm_rules("mca.comms", specs)
         + pre_rule("mca.phi_public", phi_public, [R_PHI, R_SLACK, R_CASEREF, R_ESC_DM],
                    "Use only the Case ID in public channels; send PHI and escalations by DM.")
         + pre_rule("mca.parity_channel", parity_channel, [R_P_B3, R_B3FMT], "DM @parity-committee instead.")
         + pre_rule("mca.slack_external", slack_external, [R_EXTMENTION], "Remove the @-mention of the external party.")
         + pre_rule("mca.no_determination", no_determination, [R_P_NOLET, R_CONCUR, R_NO_ISSUE, R_NOREVIEW],
                    "Do not draft or send a determination now.")
         + pre_rule("mca.external_email", external_email, [R_SUBJ, R_REVNAME, R_NOLAPSE, R_MEDNEC, R_PROMISE, R_AUTH,
                                                            R_COMMIT],
                    "Fix the email as listed.")
         + pre_rule("mca.no_regulator", no_regulator, [R_NO_DOI, R_NODOI2], "Do not email regulators.")
         + no_placeholders([R_APPXA])
         + state_rule("mca.log_row", log_row, "Fix the Appeals Log row as listed.")
         + state_rule("mca.log_append_only", log_append_only, "Restore the log and append only the new case.")
         + state_rule("mca.memo", memo, "Fix the Case Determination Memo as listed.")
         + state_rule("mca.case_folder", case_folder, "Complete the case folder as listed."))
