"""Mojave Crest Assurance - fax of May 12, 2026 (2a800bf7).

The fax is an INITIAL pharmacy exception request (brand Humalog) from Dr. Avery Solis for member Jules Arden
(KPX658320914) - not an appeal of the May 4 Toujeo denial. Per SOP 4.3.5 / 10.5 step 3 it gets no appeals case
and no acknowledgment, only intake steps 1-3. The AOR form naming Dr. Solis expired 5/6/2026, so standing is not
established (6.1 step 3): Template A-2 asking for AOR documentation goes to both the requestor and the member.
Dr. Solis signed a Paperless form (email asolis@griffinmedical.org); the member did not, so the member's letter
is a mailed PDF 20260512_KPX658320914_Correspondence.pdf with date, name and address at the top.
Not enforced (ambiguous while standing is open): routing the request to Dr. Henning.
"""

from __future__ import annotations

import re

from ..kit import (Action, Comm, Context, World, comm_rules, dashes, nh, no_placeholders, pdf_text,
                   docx_text, pre_rule, same, state_rule, world)
from .. import config

MEMBER_ID = "KPX658320914"
SOLIS = "asolis@griffinmedical.org"
MEMBER_EMAIL = "j.arden.71@gmail.com"
LOG = r"appeals_log_master\.xlsx$"
HDR = r"^Case ID$"
LETTER = "20260512_KPX658320914_Correspondence.pdf"
LETTER_RX = r"(^|/)20260512_KPX658320914_Correspondence(_[\w-]+)?\.pdf$"
A2_SUBJECT = "Mojave Crest Request KPX658320914 - Information Needed"
INITIAL_FILES = {
    "20260504_Denial_KPX658320914.pdf", "Member_Profile_KPX658320914.pdf", "2026.5.1 - KPX658320914.pdf",
    "2026.5.12 - KPX658320914.pdf", "MP_418_v2.1_20200224.pdf", "Mojave_Crest_Appeals_SOP.pdf",
    "EOC_238714_2026.pdf", "AOR_KPX658320914.pdf", "Paperless_Communication_Consent_Form_Avery_Solis.pdf",
    "appeals_log_master.xlsx"}

# Member identifiers that are PHI (12.4) - name, member ID, DOB, diagnosis, address, personal email.
PHI_RX = (r"KPX658320914|Jules\s+Arden|\bArden\b|\b0?11/0?9/(19)?71\b|1971-11-09|\bE11\.9\b|Westwind|"
          r"j\.arden\.71")
THIS_REQUEST_RX = r"KPX658320914|\bArden\b|Humalog|lispro|Avery\s+Solis|Dr\.?\s+Solis"

R_INITIAL = ("4.3.5", "Initial Pharmacy Exception Requests:", "4.3.5 Initial Pharmacy Exception Requests")
R_RX_TYPE = ("4.3.5", "Prescription drug exception requests are a special category", "4.3.5 pharmacy exceptions")
R_ONLY_13 = ("3", "denial. Only the latter is subject to the formal appeal process", "10.5 step 3")
R_STANDING = ("3", "requestor is anyone other than the member, you must confirm standing", "6.1 step 3 (standing)")
R_WHO = ("4.1", "An Authorized Representative (AOR) designated in writing", "4.1 Who Can File (AOR)")
R_MAIL = ("12.3", "All letters to members or providers must be sent via physical mail", "12.3 Paperless / mail")
R_PDF = ("12.3", "All letters sent by mail must include the date", "12.3 mailed letter format")
R_CC = ("12.3", "If the patient has an AOR, all letters must be sent to both", "12.3 AOR copies")
R_TPL = ("12.3", "Use the templates in Appendix A", "12.3 templates")
R_REVIEWER = ("12.3", "Do not include the reviewer", "12.3 reviewer names")
R_COMBINE = ("12.3", "Do not combine a coverage decision", "12.3 no combined decision")
R_SIGN = ("12.2", "Always sign correspondence with your full name", "12.2 signature")
R_PROMISE = ("12.2", "Never make promises about payment amounts", "12.2 no promises")
R_SPECULATE = ("12.2", "Never speculate about coverage", "12.2 no speculation")
R_A2_SUBJ = ("13", "Sincerely, [YOUR FULL NAME] Appeals & Grievances Coordinator Mojave Crest Assurance Company Case #: [CASE ID] Template A-2", "Template A-2 subject line")
R_A2_BODY = ("13", "Mojave Crest Assurance, Appeals & Grievances Desk Manual Dear [FULL NAME], In order to complete",
             "Template A-2 body")
R_A2_LIST = ("13", "[LIST OF SPECIFIC DOCUMENTS OR INFORMATION NEEDED]", "Template A-2 body")
R_A2_RESP = ("13", "You may respond by email with attachments", "Template A-2 body")
R_A2_DISM = ("13", "If the requested information is not received within 15 days", "Template A-2 body")
R_A2_SIGN = ("13", "Sincerely, [YOUR FULL NAME] Appeals & Grievances Coordinator Mojave Crest Assurance Company Phone: (702) 555-0148 Template A-3", "Template A-2 closing")
R_PHI_CH = ("2.4", "Mojave Crest Assurance, Appeals & Grievances Desk Manual Never post member protected health",
            "2.4 no PHI in channels")
R_PHI = ("12.4", "Never post PHI", "12.4 no PHI in public channels")
R_CASEREF = ("12.4", "Use the Case ID (CASE-YYYY-NNNNN format)", "12.4 Case ID in channels")
R_DM = ("12.4", "Use DM for escalations, parity flags", "12.4 DM for PHI")
R_QUEUE = ("4", "5. Route to Dr. Henning via DM. Do not post pharmacy cases", "10.5 step 5")
R_ROUTE = ("2.2", "Service Type Routes To Medical", "2.2 routing table (pharmacy -> Dr. Henning)")
R_SHARE = ("12.5", "Sharing PHI outside of MCA", "12.5 prohibited: PHI outside MCA")
R_OUTSIDE = ("12.5", "Discussing open appeals with the press", "12.5 prohibited: outside discussion")
R_DOI = ("12.5", "Contacting the Nevada Division of Insurance directly", "12.5 prohibited: DOI contact")
R_REG = ("9.1.3", "Contact defense counsel, the Nevada Division of Insurance", "9.1.3 no regulator contact")
R_COMMIT = ("12.5", "Issuing a benefit authorization, payment", "12.5 prohibited: coverage commitment")
R_NOCOMMIT = ("9.1.3", "Commit MCA to any future benefit coverage", "9.1.3 no coverage commitment")
R_LOG = ("13", "Mojave Crest Assurance, Appeals & Grievances Desk Manual Appendix C", "Appendix C Appeals Log")
R_FORMULA = ("13", "Mojave Crest Assurance, Appeals & Grievances Desk Manual Column Name Description Example Outcome",
             "Appendix C formulas")
R_B2_DM = ("1", "Appeals Supervisor). Do not post escalations in public channels", "9.3 step 1")
R_B2_FIELDS = ("1", "2. Include: Case ID, appeal type, decision deadline", "9.3 step 2")
R_B2 = ("13", "ESCALATION Case #:", "Format B-2")
R_B2_POST = ("13", "CLINICAL ROUTING Case #:", "Format B-2 post to: DM to @dwhitfield")
R_SLACKFMT = ("12.4", "Use the Slack formats in Appendix B", "12.4 Slack formats")
R_APPB = ("13", "Mojave Crest Assurance, Appeals & Grievances Desk Manual Appendix B", "Appendix B: no PHI in public channels")
R_NOSTAND = ("4.1", "A common error is assuming", "4.1 provider without AOR has no standing")
R_MEDNEC = ("7.1", "Your job is to make sure the right clinical reviewer", "7.1 never write medically necessary")
R_SETTLE = ("9.1.3", "Settle a case by offering payment", "9.1.3 no settlement offers")
R_TONE = ("12.2", "Mojave Crest Assurance, Appeals & Grievances Desk Manual Members who are writing", "12.2 tone")
R_BACKDATE = ("12.5", "Backdating any document", "12.5 no backdating")
R_APPA = ("13", "Mojave Crest Assurance, Appeals & Grievances Desk Manual Appendix A - Letter Templates",
          "Appendix A required elements")

A2_REFS = [R_STANDING, R_A2_SUBJ, R_A2_BODY, R_A2_LIST, R_A2_RESP, R_A2_DISM, R_A2_SIGN, R_TPL, R_SIGN, R_APPA,
           R_NOSTAND, R_MEDNEC, R_SETTLE, R_TONE]
NO_CASE_REFS = [R_INITIAL, R_RX_TYPE, R_ONLY_13, R_STANDING]


def _rx(*words: str) -> str:
    return r"\s+".join(re.escape(w) for w in words)


def _sentence(s: str) -> str:
    return _rx(*s.split())


# A-2 body text printed by the template (outside square brackets) - kept verbatim, whitespace-tolerant.
A2_BODY = [
    (_sentence("In order to complete our review of your request, I need the following additional information"),
     "the A-2 opening \"In order to complete our review of your request, I need the following additional "
     "information:\""),
    (r"Authori[sz]ed\s+Representative|\bAOR\b",
     "the requested item: a current, signed Authorized Representative (AOR) form - the AOR on file for "
     "Dr. Avery Solis expired 5/6/2026"),
    (_sentence("Please provide the requested information within 15 calendar days of the date of this letter"),
     "\"Please provide the requested information within 15 calendar days of the date of this letter.\""),
    (_sentence("Your request will remain on hold until we receive the required documentation"),
     "\"Your request will remain on hold until we receive the required documentation.\""),
    (_sentence("The review period will begin once valid authorization documentation is received"),
     "\"The review period will begin once valid authorization documentation is received.\""),
    (_sentence("You may respond by email with attachments, by mail, or by submitting documents through the "
               "secure member portal at portal.mojavecrest.com"),
     "\"You may respond by email with attachments, by mail, or by submitting documents through the secure "
     "member portal at portal.mojavecrest.com.\""),
    (_sentence("If the requested information is not received within 15 days, your request will be dismissed"),
     "\"If the requested information is not received within 15 days, your request will be dismissed.\""),
    (r"Ari\s+Costa", "signature with your full name Ari Costa"),
    (_sentence("Appeals & Grievances Coordinator"), "title \"Appeals & Grievances Coordinator\""),
    (_sentence("Mojave Crest Assurance Company"), "\"Mojave Crest Assurance Company\" in the closing"),
    (r"\(702\)\s*555-0148", "the Appeals Unit phone \"Phone: (702) 555-0148\""),
]
A2_BANNED = [
    (r"\b(has|have)\s+been\s+(approved|authori[sz]ed)\b|\b(your|the|this)\s+(request|exception|prescription|Humalog)"
     r"\s+(is|has\s+been|will\s+be)\s+(approved|authori[sz]ed|covered|denied)\b",
     "Do not state or promise a coverage outcome in the information request - no decision has been made "
     "(12.3 / 12.5)."),
    (r"\b(is|are)\s+(not\s+)?medically\s+necessary\b",
     "Do not write that a service \"is / is not medically necessary\" - only a clinical reviewer decides that (7.1)."),
    (r"\b(we|MCA|Mojave\s+Crest)\s+(will|can|would)\s+(pay|reimburse|cover)\b",
     "Do not offer payment or commit MCA to coverage in the information request (9.1.3 / 12.5)."),
    (r"\b(I|we)\s+(sincerely\s+|truly\s+)?apologi[sz]e\b|\b(I|we)\s+are\s+(so\s+|very\s+)?sorry\b",
     "Keep the letter matter-of-fact - do not apologize for the original denial (12.2)."),
    (r"CASE-\d{4}-\d{5}", "Do not assign or quote a Case ID - an initial pharmacy exception request gets no "
                          "appeals case (4.3.5)."),
    (r"Acknowledg(e)?ment\s+of\s+Your\s+Appeal", "This is not an acknowledgment - initial exception requests get "
                                                 "no acknowledgment letter (4.3.5)."),
]
REVIEWER_RX = r"Henning|Bergstrom|Ontario|Alvarado"


def _related(a: Action) -> bool:
    addrs = {x.lower() for x in a.recipients + a.cc}
    return bool(addrs & {SOLIS, MEMBER_EMAIL}) or bool(re.search(THIS_REQUEST_RX, f"{a.subject}\n{a.text}", re.I))


def _specs(ctx: Context) -> list[Comm]:
    return [
        Comm("a2_requestor", "email", lambda a: a.kind == "email_send" and SOLIS in a.recipients + a.cc,
             "Template A-2 Missing Information Request to the requestor Dr. Avery Solis (paperless: email)",
             A2_REFS + [R_WHO, R_MAIL, R_CC, R_COMBINE, R_COMMIT, R_NOCOMMIT, R_PROMISE, R_SPECULATE],
             to=[SOLIS], exact_to=False,
             subject=re.escape(dashes(A2_SUBJECT)), subject_hint=A2_SUBJECT,
             body=[(r"Dear\s+(Dr\.?\s+)?(Avery\s+)?Solis", "salutation \"Dear Dr. Avery Solis,\" (A-2: Dear [FULL NAME])")]
             + A2_BODY + [(r"\bCC\s*:\s*Jules\s+Arden", "\"CC: Jules Arden\" at the bottom (copy goes to the member)")],
             banned=A2_BANNED),
        Comm("ack_forbidden", "email",
             lambda a: a.kind == "email_send" and _related(a)
             and bool(re.search(r"Acknowledg(e)?ment\s+of\s+Your\s+(Appeal|Request)", f"{a.subject}\n{a.text}", re.I)
                      or ({x.lower() for x in a.recipients + a.cc} & {SOLIS, MEMBER_EMAIL}
                          and re.search(r"acknowledg", a.subject, re.I))),
             "Acknowledgment letter for the May 12 Humalog fax", NO_CASE_REFS,
             forbidden="The fax is an initial pharmacy exception request (brand Humalog), not an appeal: SOP 4.3.5 - "
                       "no appeals case file and no acknowledgment letter; and standing is not established (AOR expired "
                       "5/6/2026), so 6.1 step 3 also says do not send the acknowledgment. Send Template A-2 instead."),
        Comm("member_not_paperless", "email",
             lambda a: a.kind == "email_send" and MEMBER_EMAIL in a.recipients + a.cc,
             "Email to the member Jules Arden", [R_MAIL, R_PDF],
             forbidden=f"Jules Arden has not signed a Paperless Enrollment form, so letters to the member go by physical "
                       f"mail: save the A-2 letter as {LETTER} (date, full name and mailing address 2675 Westwind "
                       f"Terrace, Las Vegas, NV 89146 at the top). Do not email {MEMBER_EMAIL}."),
        Comm("escalation_b2", "slack_dm",
             lambda a: a.kind in ("slack_dm", "slack_post") and "ESCALATION" in a.text
             and world(ctx).is_dm_to(a, "Darnell Whitfield"),
             "Escalation to the Appeals Supervisor (Format B-2)", [R_B2_DM, R_B2_FIELDS, R_B2, R_B2_POST, R_SLACKFMT],
             to=["Darnell Whitfield"], required=False, max_count=10,
             body=[(r"Case\s*#\s*:", "\"Case #:\""), (r"Type\s*:", "\"Type:\""), (r"Deadline\s*:", "\"Deadline:\""),
                   (r"Trigger\s*:", "\"Trigger:\" (trigger from 9.2)"), (r"Summary\s*:", "\"Summary:\""),
                   (r"My\s+Recommendation\s*:", "\"My Recommendation:\""),
                   (r"Requested\s+Action\s*:", "\"Requested Action:\"")]),
    ]


# ---- pre rules -----------------------------------------------------------------------------------

def _public_phi(ctx: Context, a: Action):
    if a.kind != "slack_post" or world(ctx).dm_recipients(a):
        return None
    m = re.search(PHI_RX, a.text, re.I)
    if not m:
        return None
    ch = world(ctx).channel_name(a.channel)
    return (f"[phi] This post in #{ch} contains member PHI (\"{m.group(0)}\"). Never post member name, member ID, "
            "DOB, diagnosis or address in a public channel; use a direct message to the specific reviewer.")


def _clinical_queue(ctx: Context, a: Action):
    w = world(ctx)
    if a.kind != "slack_post" or w.dm_recipients(a) or not w.is_channel(a.channel, "appeals-clinical-queue"):
        return None
    if re.search(r"Humalog|lispro|insulin|pharmacy|formulary|KPX658320914|Solis", a.text, re.I):
        return ("[queue] Pharmacy exception requests are not posted in #appeals-clinical-queue - they go to "
                "Dr. Henning (Pharmacy Director) by direct message.")
    return None


def _external_email(ctx: Context, a: Action):
    if a.kind != "email_send":
        return None
    addrs = {x.lower() for x in a.recipients + a.cc}
    doi = sorted(x for x in addrs if re.search(r"(@|\.)doi\.nv\.gov$|@doi\.", x))
    if doi:
        return f"[doi] Coordinators may not contact the Nevada Division of Insurance directly ({', '.join(doi)})."
    outside = sorted(x for x in addrs if not x.endswith("@mojavecrest.com") and x not in (SOLIS, MEMBER_EMAIL))
    m = re.search(PHI_RX, f"{a.subject}\n{a.text}", re.I)
    if outside and m:
        return (f"[phi] This email to {', '.join(outside)} contains member PHI (\"{m.group(0)}\"). PHI must not leave "
                f"MCA's secure email environment; only the requestor (Dr. Avery Solis, {SOLIS}) receives "
                "correspondence about this request by email.")
    return None


def _log_write(ctx: Context, a: Action):
    if a.kind != "workbook_write" or not any(re.search(LOG, f, re.I) for f in a.files_written):
        return None
    src = f"{a.text}\n{a.code}"
    if (re.search(r"KPX658320914|CASE-2026-0071[6-9]|Humalog|Arden", src, re.I)
            and re.search(r"\.append\(|\.cell\(|\.value\s*=|insert_rows|to_excel\(|\]\s*=", src)):
        return ("[log] Do not open a case in the Appeals Log for the May 12 fax: it is an initial pharmacy exception "
                "request (SOP 4.3.5 - no appeals case file), and standing is not established (6.1 step 3 - do not open "
                "the case until standing is established). Leave appeals_log_master.xlsx unchanged.")
    return None


# ---- completion rules ----------------------------------------------------------------------------

def _log_checks(ctx: Context):
    w = world(ctx)
    init = w.rows(LOG, HDR, "initial")
    if not init:
        return
    cur = w.rows(LOG, HDR, "current")
    if not cur:
        yield (False, "appeals_log_master.xlsx (Appeals Log) is missing or unreadable - restore it unchanged.",
               [R_LOG, R_FORMULA])
        return
    by_id = {}
    for r in cur:
        by_id.setdefault(w.col(r, r"^Case ID$"), []).append(r)
    new = [r for r in cur if w.col(r, r"^Case ID$") not in {w.col(x, r"^Case ID$") for x in init}]
    yield (not new, f"The Appeals Log has {len(new)} new row(s) (e.g. {w.col(new[0], r'^Case ID$') if new else ''} / "
                    f"{w.col(new[0], r'^Member ID$') if new else ''}). The May 12 fax is an initial pharmacy exception "
                    "request with standing not established: no appeals case is opened. Remove the added row(s).",
           NO_CASE_REFS)
    edited = []
    for r in init:
        cid = w.col(r, r"^Case ID$")
        hits = by_id.get(cid) or []
        if not hits:
            edited.append(f"{cid} (removed)")
            continue
        c = hits[0]
        diff = [k for k in r if k != "__row__" and not same(c.get(k, ""), r[k] if str(r[k]).strip() else None)]
        if diff:
            edited.append(f"{cid} ({', '.join(diff[:3])}: \"{r[diff[0]]}\" -> \"{c.get(diff[0], '')}\")")
    yield (not edited, f"Existing Appeals Log rows were changed: {'; '.join(edited[:4])}. Nothing in the log changes "
                       "for this fax, and the Acknowledgment Due / Decision Due formulas must not be overwritten - "
                       "restore the original values/formulas.", [R_LOG, R_FORMULA] + NO_CASE_REFS)


def _new_files(w: World) -> list[str]:
    return [f for f in w.files() if f.split("/")[-1] not in INITIAL_FILES and not f.split("/")[-1].startswith(".")]


def _text(path) -> str:
    p = str(path).lower()
    if p.endswith(".pdf"):
        return pdf_text(path)
    if p.endswith(".docx"):
        return docx_text(path)
    if p.endswith((".txt", ".md", ".html", ".eml")):
        try:
            return open(path, errors="ignore").read()
        except OSError:
            return ""
    return ""


def _file_checks(ctx: Context):
    w = world(ctx)
    root = config.workdir()
    new = _new_files(w)
    texts = {f: dashes(_text(root / f)) for f in new}
    case_files = [f for f in new if re.search(r"CASE-\d{4}-\d{5}", f)]
    acks = [f for f, t in texts.items() if re.search(r"Acknowledg(e)?ment\s+of\s+Your\s+Appeal", t, re.I)
            and re.search(THIS_REQUEST_RX, t, re.I)]
    yield (not case_files and not acks,
           f"Case file / acknowledgment documents were created for the May 12 fax ({', '.join((case_files + acks)[:4])}). "
           "An initial pharmacy exception request gets no appeals case file and no acknowledgment letter; remove them.",
           NO_CASE_REFS)

    letters = [f for f in new if re.search(LETTER_RX, f, re.I)]
    best: list[str] | None = None
    for f in letters:
        probs = _letter_problems(texts.get(f, ""))
        if best is None or len(probs) < len(best):
            best = probs
        if not probs:
            break
    if best is None:
        best = [f"no file named {LETTER} exists in /workdir"]
    yield (not best, "The member Jules Arden has not received Template A-2 (Missing Information Request asking for AOR "
                     "documentation). She has no Paperless Enrollment form, so the letter goes by physical mail: save it "
                     f"as a PDF named {LETTER} with the date (May 12, 2026), her full name and mailing address "
                     "(Jules Arden, 2675 Westwind Terrace, Las Vegas, NV 89146) at the top, \"Dear Jules Arden,\", the "
                     "A-2 body text verbatim, the Ari Costa / Appeals & Grievances Coordinator / Mojave Crest Assurance "
                     "Company / Phone: (702) 555-0148 closing and \"CC: Dr. Avery Solis\" at the bottom. Problems: "
                     + "; ".join(best[:6]) + ".",
           A2_REFS + [R_WHO, R_MAIL, R_PDF, R_CC, R_REVIEWER, R_COMMIT, R_PROMISE, R_BACKDATE])


def _letter_problems(text: str) -> list[str]:
    t = nh(text)
    if not t:
        return ["the PDF has no extractable text"]
    out = []
    head = t[:t.find("Dear")] if "Dear" in t else t[:600]
    if not re.search(r"May\s+12,?\s+2026|2026-05-12|\b0?5/12/(20)?26\b|12\s+May\s+2026", head, re.I):
        out.append("date (May 12, 2026) missing at the top")
    if not re.search(r"Jules\s+Arden", head, re.I):
        out.append("addressee full name Jules Arden missing at the top")
    if not (re.search(r"2675\s+Westwind\s+Terrace", head, re.I) and re.search(r"Las\s+Vegas,?\s+NV,?\s+89146", head, re.I)):
        out.append("mailing address 2675 Westwind Terrace, Las Vegas, NV 89146 missing at the top")
    if not re.search(r"Dear\s+(\w{2,4}\.?\s+)?Jules\s+Arden", t, re.I):
        out.append("salutation \"Dear Jules Arden,\" missing")
    for rx, desc in A2_BODY:
        if not re.search(rx, t, re.I | re.S):
            out.append(f"missing {desc}")
    if not re.search(r"\bCC\s*:\s*(Dr\.?\s+)?Avery\s+Solis", t, re.I):
        out.append("\"CC: Dr. Avery Solis\" missing at the bottom")
    for rx, why in A2_BANNED:
        if re.search(rx, t, re.I):
            out.append(why.rstrip("."))
    m = re.search(REVIEWER_RX, t)
    if m:
        out.append(f"clinical reviewer name \"{m.group(0)}\" must not appear in member correspondence")
    if re.search(r"\[[A-Z][A-Z /&'-]{2,}\]", t):
        out.append("unfilled [TEMPLATE FIELD] placeholders remain")
    return out


RULES = (
    comm_rules("mojave_2a800bf7.comms", _specs)
    + pre_rule("mojave_2a800bf7.public_phi", _public_phi, [R_PHI_CH, R_PHI, R_CASEREF, R_DM, R_APPB],
               "Remove the PHI and refer to the matter without member identifiers, or DM the specific reviewer.")
    + pre_rule("mojave_2a800bf7.no_clinical_queue", _clinical_queue, [R_QUEUE, R_ROUTE, R_INITIAL],
               "Do not post this in #appeals-clinical-queue.")
    + pre_rule("mojave_2a800bf7.external_email", _external_email, [R_SHARE, R_OUTSIDE, R_DOI, R_REG],
               "Do not send this email.")
    + pre_rule("mojave_2a800bf7.no_log_case", _log_write, NO_CASE_REFS + [R_LOG],
               "Do not add a row for this fax to the Appeals Log.")
    + state_rule("mojave_2a800bf7.log_unchanged", _log_checks, "Restore appeals_log_master.xlsx as listed.")
    + state_rule("mojave_2a800bf7.member_letter", _file_checks, "Fix the correspondence files as listed.")
    + no_placeholders([R_TPL])
)
