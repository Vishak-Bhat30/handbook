"""Mojave Crest Assurance - A&G intake of the Desert Springs concurrent care appeal (5122b4da).

Seed facts (environment only): email 1 from ur@desertspringsrecovery.org (2026-04-14 09:47 PT) is the only new
appeal - an expedited concurrent care appeal of AUTH-2026-00441 (residential SUD, member MBR-2026-04471,
GRP-00892), termination effective 2026-04-16 12:00 PM PT, treating physician certification of expedited need,
explicit MHPAEA / NRS 695B.255 parity assertion, $88,500 billed. Emails 2-4 concern existing cases
(CASE-2026-00086 / -00088) and must not be acted on (task instruction). Jira is the system of record; the
appeals log workbook is read-only (SOP 6.1 note).
"""

from __future__ import annotations

import json
import re

from ..kit import (Comm, Context, World, comm_rules, dashes, forbid_writes, no_placeholders, num,
                   pre_rule, same, state_rule, text_of, world)

PROVIDER = "ur@desertspringsrecovery.org"
MEMBER = "MBR-2026-04471"
APPEAL_EMAIL = "1"
NON_APPEAL_EMAILS = {"2", "3", "4"}
ONTARIO, PARITY, WHITFIELD = "U005", "U009", "U002"
NEW_ID = r"(?:CASE-2026-00091|MCA_APPEALS-(?:[6-9]|[1-9]\d+))\b"
NEW_ID_HINT = "CASE-2026-00091 (next sequential Case ID after CASE-2026-00090) or the new Jira key"
NON_APPEAL_RX = (r"CASE-2026-0008[68]\b|MBR-2026-(?:09341|17203)\b|MS-56721|MCA_APPEALS-[13]\b|"
                 r"sunrise\s*imaging|canyon\s*ridge|canyonridgereview")
NON_APPEAL_ADDR = re.compile(r"records@sunriseimaging\.com|member\.services@mojavecrest\.com|@canyonridgereview\.com",
                             re.I)
INSTRUCTION = ("Task instruction: \"Do not complete any action in relation to other emails in the inbox that do not "
               "represent a new appeal. This instruction supersedes any instruction provided in the SOP.\"")


def day(d: int) -> str:
    return rf"(?:2026-04-{d:02d}|April {d},? 2026|Apr\.? {d},? 2026|0?4/{d}/2026)"


NOON = r"(?:12:00|12\s*(?:PM|p\.m\.)|noon)"


def lab(label: str) -> str:
    """Field label tolerant of markdown bold: 'Type:' / '**Type:**'."""
    return rf"{label}\**\s*:\s*\**\s*"


# ---- SOP references -------------------------------------------------------------------------------
R_JIRA = [("6.1", "Log the case in Jira by creating a new issue", "6.1 Jira case logging"),
          ("6.1", "AppealType: e.g.", "6.1 AppealType"),
          ("6.1", "AcknowledgmentDue: Date acknowledgment is due", "6.1 AcknowledgmentDue"),
          ("6.1", "DecisionDeadline: Earlier of the service termination", "6.1 DecisionDeadline"),
          ("6.1", "DisputeValue: Dollar value", "6.1 DisputeValue"),
          ("6.1", "StandardOfReview: \"Expedited\"", "6.1 StandardOfReview"),
          ("6.1", "ParityFlag: \"Yes\" if MHPAEA", "6.1 ParityFlag"),
          ("6.1", "ClinicalReviewer: Name of the assigned", "6.1 ClinicalReviewer")]
R_ACK = [("6.1", "Send the acknowledgment letter (Template A-1)", "6.1 acknowledgment"),
         ("10.2", "If expedited criteria ARE met, send the expedited acknowledgment", "10.2 expedited acknowledgment"),
         ("13", "Subject line: Mojave Crest Appeals Case #[CASE ID] - Acknowledgment", "Template A-1 subject"),
         ("13", "Case Number: [CASE ID] Member Name:", "Template A-1 case details"),
         ("13", "Insert at the top of Template A-1", "Expedited Acknowledgment Header Block"),
         ("13", "Certain appeal types require a specific header block", "Header Block Variants"),
         ("12.2", "Always sign correspondence with your full name", "12.2 signature")]
R_ROUTE = [("8.3", "Route the case to Dr. Ayla Ontario", "8.3 route to Dr. Ontario"),
           ("8.3", "Parity-flagged cases are routed exclusively", "8.3 exclusive parity routing"),
           ("7.3", "For expedited cases, also send a direct Slack message", "7.3 expedited routing"),
           ("13", "For expedited cases: DM the on-call reviewer", "Format B-1 posting"),
           ("13", "CLINICAL ROUTING Case #:", "Format B-1")]
R_URGENT = [("7.3", "For expedited cases, also send a direct Slack message", "7.3 expedited routing"),
            ("10.2", "Route immediately in #appeals-urgent", "10.2 urgent routing"),
            ("13", "For expedited cases: DM the on-call reviewer", "Format B-1 posting")]
R_PARITY = [("8.3", "Send a Parity Flag Notification using Slack Format B-3", "8.3 parity flag notification"),
            ("8.2", "The member is appealing a denial of inpatient SUD residential", "8.2 parity indicator"),
            ("13", "Post to: DM to @parity-committee", "Format B-3 posting"),
            ("13", "Case #: [CASE ID] Service Classification: [Outpatient BH", "Format B-3")]
R_ESC = [("9.2", "Escalate to your Appeals Supervisor (Darnell Whitfield)", "9.2 mandatory escalation"),
         ("9.2", "A parity flag has been raised", "9.2 parity trigger"),
         ("9.2", "The case involves a concurrent care termination", "9.2 concurrent care trigger"),
         ("9.2", "The total dispute value exceeds the Coordinator's", "9.2 authority trigger"),
         ("9.1.1", "If a case exceeds your tier", "9.1.1 Exceeds Coordinator Authority"),
         ("9.3", "Send a direct Slack message to @dwhitfield", "9.3 escalation by DM")]
R_B2 = [("9.3", "Include: Case ID, appeal type", "9.3 escalation contents"),
        ("13", "Trigger: [Specific trigger from Section 9.2]", "Format B-2")]
R_PARITY_CH = [("8.3", "Send a Parity Flag Notification using Slack Format B-3", "8.3 not in #appeals-parity"),
               ("2.4", "#appeals-parity | General parity policy", "2.4 #appeals-parity")]
R_PHI = [("2.4", "Never post member protected health information", "2.4 no PHI in channels"),
         ("12.4", "Never post PHI", "12.4 no PHI in public channels")]
R_SUBJ = [("12.3", "All outbound emails to members or providers must include the Case ID", "12.3 subject line")]
R_REVIEWER = [("12.3", "Do not include the reviewer's name", "12.3 reviewer names confidential")]
R_LAPSE = [("10.3", "Coverage must continue through the appeal decision", "10.3 continuation of coverage")]
R_MEDNEC = [("7.1", "Your job is to make sure the right clinical reviewer", "7.1 no medical necessity statements")]
R_PROMISE = [("12.2", "Never make promises about payment amounts", "12.2 no promises")]
R_REGULATOR = [("9.1.3", "Contact defense counsel", "9.1.3 no regulator contact"),
               ("12.5", "Contacting the Nevada Division of Insurance", "12.5 no DOI contact")]
R_LOG = [("6.1", "Note: appealslogmaster.xlsx is a read-only", "6.1 Appeals Log read-only")]
R_BOOKS = R_LOG + [("12.5", "Issuing a benefit authorization", "12.5 no coverage commitment")]
R_TPL = [("13", "These are the approved letter templates", "Appendix A templates")]

RULES = []


# ---- helpers ------------------------------------------------------------------------------------
def external(a) -> list[str]:
    return [r for r in list(a.recipients) + list(a.cc) if not r.lower().endswith("@mojavecrest.com")]


def is_dm(w: World, a, uid: str) -> bool:
    return a.kind in ("slack_dm", "slack_post") and uid in w.dm_recipients(a)


def public_post(w: World, a) -> bool:
    if a.kind != "slack_post" or w.dm_recipients(a):
        return False
    ch = w.channels.get(str(a.channel).lstrip("#"), {})
    return not ch.get("is_im")


# ---- 1. non-appeal emails (task instruction) --------------------------------------------------------
def _non_appeal(ctx: Context, a):
    hit = ""
    blob = json.dumps(a.args, ensure_ascii=False)
    if a.kind in ("email_send", "email_draft"):
        bad = [r for r in list(a.recipients) + list(a.cc) if NON_APPEAL_ADDR.search(r)]
        if bad:
            hit = f"it is addressed to {', '.join(bad)}"
        elif str(a.args.get("email_id") or "") in NON_APPEAL_EMAILS:
            hit = f"it replies to / forwards email {a.args.get('email_id')}"
        elif re.search(NON_APPEAL_RX, text_of(a), re.I):
            hit = "it refers to an existing case from those emails"
    elif a.kind in ("email_move", "email_mark", "email_delete"):
        ids = set(a.recipients) & NON_APPEAL_EMAILS
        if ids:
            hit = f"it changes email(s) {', '.join(sorted(ids))}"
    elif a.kind in ("slack_post", "slack_dm", "calendar_create", "calendar_update"):
        if re.search(NON_APPEAL_RX, a.text, re.I):
            hit = "it refers to an existing case from those emails"
    elif a.kind.startswith("jira_"):
        if re.search(r"MCA_APPEALS-[13]\b", blob) or re.search(NON_APPEAL_RX, f"{a.subject}\n{a.text}", re.I):
            hit = "it touches the existing case of one of those emails"
    if not hit:
        return None
    return (f"[non-appeal] Emails 2-4 (Canyon Ridge acknowledgment for CASE-2026-00086, Member Services status "
            f"inquiry for CASE-2026-00088, Sunrise supplemental records for CASE-2026-00086) are not new appeals; "
            f"this call acts on them ({hit}). {INSTRUCTION} Only process the new Desert Springs appeal (email 1).")


RULES += pre_rule("mca.non_appeal_emails", _non_appeal, [], "Do not act on emails 2-4 or their cases.")


# ---- 2. Jira case record (6.1) ----------------------------------------------------------------------
JIRA_FIELDS = [
    # field, label regex, check, expected
    ("MemberID", r"Member\s*_?ID", lambda v: MEMBER in v.upper(), MEMBER),
    ("AppealType", r"Appeal\s*_?Type",
     lambda v: bool(re.search(r"concurrent", v, re.I) and re.search(r"expedited", v, re.I)),
     "Concurrent Care – Expedited"),
    ("DateOfReceipt", r"Date\s*_?Of\s*_?Receipt", lambda v: first_date(v) == 14, "2026-04-14"),
    ("AcknowledgmentDue", r"Acknowledge?ment\s*_?Due", lambda v: first_date(v) == 15,
     "2026-04-15 (24 hours after the 2026-04-14 09:47 PT receipt)"),
    ("DecisionDeadline", r"Decision\s*_?Deadline", lambda v: first_date(v) == 16,
     "2026-04-16 (termination effective 2026-04-16 12:00 PM PT, earlier than 72 hours from receipt)"),
    ("DisputeValue", r"Dispute\s*_?Value", lambda v: first_amount(v) == 88500, "88500 ($88,500.00 billed charges)"),
    ("StandardOfReview", r"Standard\s*_?Of\s*_?Review", lambda v: "expedited" in v.lower(), "Expedited"),
    ("PlanYear", r"Plan\s*_?Year", lambda v: "2026" in v, "2026"),
    ("ParityFlag", r"Parity\s*_?Flag", lambda v: bool(re.match(r"\s*(yes|true|y)\b", v, re.I)), "Yes"),
    ("AssignedCoordinator", r"Assigned\s*_?Coordinator",
     lambda v: bool(v.strip()) and not re.search(r"\[|^\(?none\)?$|^n/?a$", v.strip(), re.I), "your name or coordinator ID"),
    ("ClinicalReviewer", r"Clinical\s*_?Reviewer", lambda v: "ontario" in v.lower(), "Dr. Ayla Ontario"),
]


def first_date(v: str):
    m = re.search(r"2026-04-(\d{2})|April (\d{1,2}),? 2026|0?4/(\d{1,2})/2026", v)
    return int(next(g for g in m.groups() if g)) if m else None


def first_amount(v: str):
    m = re.search(r"\d[\d,]*(?:\.\d+)?", v.replace("$", ""))
    return num(m.group(0)) if m else None


def _as_dict(v) -> dict:
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except ValueError:
            return {}
    return v if isinstance(v, dict) else {}


def jira_values(args: dict) -> dict[str, str]:
    """Field values set by a Jira create/update call: structured fields first, then 'Field: value' lines."""
    merged = {**_as_dict(args.get("additional_fields")), **_as_dict(args.get("fields"))}
    flat = {re.sub(r"[^a-z]", "", k.lower()): v for k, v in {**args, **merged}.items()}
    desc = args.get("description") or merged.get("description") or args.get("comment") or ""
    desc = desc if isinstance(desc, str) else json.dumps(desc)
    out = {}
    for f, label, _, _ in JIRA_FIELDS:
        v = flat.get(f.lower())
        if isinstance(v, dict):
            v = v.get("value") or v.get("name") or json.dumps(v)
        if v is not None and str(v).strip() != "":
            out[f] = str(v)
            continue
        m = re.search(rf"(?im)^[\s\-*•]*\**\s*{label}\s*\**\s*[:=]\s*\**\s*(.*?)\s*$", desc)
        if m:
            out[f] = m.group(1)
    return out


def is_case_issue(a) -> bool:
    return a.kind == "jira_create" and ("04471" in json.dumps(a.args) or re.search(NEW_ID, json.dumps(a.args)))


def jira_problems(vals: dict[str, str]) -> list[str]:
    out = []
    for f, _, ok, want in JIRA_FIELDS:
        if f not in vals:
            out.append(f"{f} missing (expected {want})")
        elif not ok(vals[f]):
            out.append(f"{f} = '{vals[f][:60]}' (expected {want})")
    return out


def created_issues(w: World) -> list[tuple[str, dict]]:
    out = []
    for e in w.state.executed:
        if is_case_issue(e.action) and w.ok(e):
            m = re.search(r'"key"\s*:\s*"([A-Z][A-Z0-9_]*-\d+)"', e.result or "")
            out.append((m.group(1) if m else "", e.action.args))
    return out


def _jira_pre(ctx: Context, a):
    if not is_case_issue(a):
        return None
    w = world(ctx)
    done = created_issues(w)
    if done:
        key = done[0][0] or "the issue already created"
        return (f"[jira] The new appeal is already logged in Jira as {key}; do not create a duplicate issue. "
                f"Update {key} instead if a field needs correcting.")
    probs = jira_problems(jira_values(a.args))
    if probs:
        return ("[jira] The Jira case for the new concurrent care appeal must populate every SOP 6.1 field "
                "correctly: " + "; ".join(probs) + ". Put each as its own field or as a 'Field: value' line in the "
                "description (MemberID, AppealType, DateOfReceipt, AcknowledgmentDue, DecisionDeadline, "
                "DisputeValue, StandardOfReview, PlanYear, ParityFlag, RelatedCaseID, AssignedCoordinator, "
                "ClinicalReviewer).")
    return None


RULES += pre_rule("mca.jira_case_pre", _jira_pre, R_JIRA, "Create the Jira issue with the listed field values.")


def _jira_done(ctx: Context):
    w = world(ctx)
    done = created_issues(w)
    if not done:
        yield (False, "The new appeal (Desert Springs, member MBR-2026-04471) is not logged in Jira. Create a new "
                      "issue with MemberID: MBR-2026-04471; AppealType: Concurrent Care – Expedited; DateOfReceipt: "
                      "2026-04-14; AcknowledgmentDue: 2026-04-15; DecisionDeadline: 2026-04-16; DisputeValue: 88500; "
                      "StandardOfReview: Expedited; PlanYear: 2026; ParityFlag: Yes; RelatedCaseID; "
                      "AssignedCoordinator: <you>; ClinicalReviewer: Dr. Ayla Ontario.", R_JIRA)
        return
    key, args = done[0]
    vals = jira_values(args)
    for e in w.state.executed:
        a = e.action
        if key and a.kind == "jira_update" and a.channel == key and w.ok(e):
            vals.update(jira_values(a.args))
    probs = jira_problems(vals)
    yield (not probs, f"Jira issue {key or '(new appeal)'} has wrong or missing SOP 6.1 fields: " + "; ".join(probs)
           + ". Update the issue.", R_JIRA)


RULES += state_rule("mca.jira_case", _jira_done, "Create/update the Jira issue as listed.")


# ---- 3. required messages ---------------------------------------------------------------------------
def _specs(ctx: Context) -> list[Comm]:
    w = world(ctx)
    ack_about = lambda a: (a.kind in ("email_send", "email_draft")
                           and (PROVIDER in [r.lower() for r in a.recipients + a.cc]
                                or str(a.args.get("email_id") or "") == APPEAL_EMAIL)
                           and bool(re.search(r"acknowledg|has received your|confirms?\b.{0,80}receiv", text_of(a),
                                              re.I | re.S)))
    header = ("--- EXPEDITED REVIEW --- / Expedited Basis: Treating Physician Certification / "
              "Decision Due By: 2026-04-16 12:00 PM PT")
    return [
        Comm("ack", "email", ack_about,
             "Template A-1 expedited acknowledgment to the requesting provider (ur@desertspringsrecovery.org)",
             R_ACK, to=[PROVIDER], exact_to=False,
             subject=rf"Mojave Crest Appeals Case #{NEW_ID} – Acknowledgment of Your Appeal",
             subject_hint="Mojave Crest Appeals Case #CASE-2026-00091 - Acknowledgment of Your Appeal (send it with "
                          "google_mail__send_email so the subject is set; Case ID = " + NEW_ID_HINT + ")",
             body=[(rf"Dear\b.{{0,160}}?[,:]\s*-{{2,}}\s*EXPEDITED REVIEW\s*-{{2,}}",
                    "the Expedited Acknowledgment Header Block inserted immediately after the salutation line "
                    f"(\"Dear ...,\") and before the main body text: {header}"),
                   (r"Expedited Basis\**\s*:\s*\**\s*Treating Physician Certification",
                    "header line 'Expedited Basis: Treating Physician Certification'"),
                   (rf"Decision Due By\**\s*:\s*\**\s*{day(16)}.{{0,12}}?{NOON}",
                    "'Decision Due By: 2026-04-16 12:00 PM PT' (termination effective time, earlier than 72 hours)"),
                   (rf"Case Number\**\s*:\s*\**\s*{NEW_ID}", "'Case Number: CASE-2026-00091' (the new Case ID)"),
                   (rf"Member ID\**\s*:\s*\**\s*{MEMBER}", f"'Member ID: {MEMBER}'"),
                   (rf"Date Received\**\s*:\s*\**\s*{day(14)}", "'Date Received: 2026-04-14' (intake queue timestamp)"),
                   (r"Appeal Type\**\s*:\s*\**\s*Concurrent Care", "'Appeal Type: Concurrent Care – Expedited'"),
                   (r"\(?702\)?[\s.-]*555[\s.-]*0148", "the Appeals Unit phone number (702) 555-0148"),
                   (r"Appeals (?:&|and) Grievances Coordinator", "the signature title 'Appeals & Grievances Coordinator'")]),
        Comm("route_ontario", "slack_dm",
             lambda a: is_dm(w, a, ONTARIO) and bool(re.search(r"CLINICAL ROUTING|Parity Flag\**\s*:|Standard of Review",
                                                               a.text, re.I)),
             "Format B-1 clinical routing DM to Dr. Ayla Ontario (parity-flagged expedited concurrent care case)",
             R_ROUTE, to=["Dr. Ayla Ontario"],
             body=[(r"CLINICAL ROUTING", "the Format B-1 header 'CLINICAL ROUTING'"),
                   (rf"Case\s*#?\**\s*:?\s*\**\s*{NEW_ID}", "'Case #: CASE-2026-00091'"),
                   (lab("Type") + r"Concurrent Care", "'Type: Concurrent Care'"),
                   (lab("Service Classification") + r"(?:[^:]{0,20}\b)?(?:SUD|Substance Use)",
                    "'Service Classification: SUD'"),
                   (lab("Standard of Review") + r"Medical Necessity", "'Standard of Review: Medical Necessity'"),
                   (lab("Deadline") + rf"{day(16)}.{{0,12}}?{NOON}", "'Deadline: 2026-04-16 12:00 PM PT'"),
                   (lab("Parity Flag") + r"YES", "'Parity Flag: YES'")]),
        Comm("parity_b3", "slack_dm", lambda a: is_dm(w, a, PARITY),
             "Format B-3 Parity Flag Notification DM to @parity-committee", R_PARITY, to=["Parity Review Committee"],
             body=[(r"PARITY FLAG", "the Format B-3 header 'PARITY FLAG'"),
                   (rf"Case\s*#?\**\s*:?\s*\**\s*{NEW_ID}", "'Case #: CASE-2026-00091'"),
                   (lab("Service Classification") + r"Inpatient SUD", "'Service Classification: Inpatient SUD'"),
                   (lab(r"Comparable M/S Classification") + r"[^:]{0,40}?Inpatient",
                    "'Comparable M/S Classification: Inpatient, in-network (M/S) ...'"),
                   (lab("Flag Indicator"), "'Flag Indicator: <specific Section 8.2 indicator>'"),
                   (lab("Decision Deadline") + day(16), "'Decision Deadline: 2026-04-16 12:00 PM PT'")]),
        Comm("urgent", "slack_post", lambda a: public_post(w, a) and w.is_channel(a.channel, "appeals-urgent"),
             "expedited routing post in #appeals-urgent tagging @dwhitfield", R_URGENT, channel="appeals-urgent",
             max_count=3,
             body=[(NEW_ID, "the Case ID CASE-2026-00091 (no PHI)"),
                   (r"@dwhitfield|<@U002>", "a tag of @dwhitfield"),
                   (day(16), "the decision deadline 2026-04-16 12:00 PM PT")]),
    ]


RULES += comm_rules("mca.comms", _specs)


# ---- 4. escalation to the Appeals Supervisor (9.2 / 9.3 / Format B-2) -------------------------------------
B2_LABELS = [("Case #", rf"Case\s*#?\**\s*:?\s*\**\s*{NEW_ID}", "Case #: CASE-2026-00091"),
             ("Type", lab("Type") + r"Concurrent", "Type: Concurrent"),
             ("Deadline", lab("Deadline") + day(16), "Deadline: 2026-04-16 12:00 PM PT"),
             ("Trigger", lab("Triggers?"), "Trigger: <Section 9.2 trigger(s)>"),
             ("Summary", lab("Summary"), "Summary: <2-3 sentences>"),
             ("My Recommendation", lab("My Recommendation"), "My Recommendation: <what should happen>"),
             ("Requested Action", lab("Requested Action"), "Requested Action: <Approval / Guidance / Takeover>")]
TRIGGERS = [("parity", r"parity", "Parity flag raised"),
            ("authority", r"(?:exceed|above|over|beyond)[^.;\n]{0,60}(?:\$?25,?000|coordinator)|coordinator\s+(?:authority|tier)",
             "Exceeds Coordinator Authority ($88,500 > $25,000)"),
            ("concurrent", r"72[\s-]*hours?|within\s+(?:the\s+next\s+)?72",
             "Concurrent care termination with care ending within the next 72 hours")]


def _b2_pre(ctx: Context, a):
    w = world(ctx)
    if a.kind not in ("slack_post", "slack_dm") or not re.match(r"\W*ESCALATION\b", a.text):
        return None
    if public_post(w, a) and not w.is_channel(a.channel, "appeals-urgent"):
        return ("[escalation] Escalations go by direct message to @dwhitfield (Format B-2), not in a public channel "
                f"(got #{w.channel_name(a.channel)}).")
    if not is_dm(w, a, WHITFIELD):
        return None
    miss = [want for _, rx, want in B2_LABELS if not re.search(rx, dashes(a.text), re.I | re.S)]
    if miss:
        return "[escalation] The Format B-2 escalation must contain every field: missing/incorrect " + "; ".join(miss) + "."
    return None


RULES += pre_rule("mca.escalation_format", _b2_pre, R_B2 + R_ESC[-1:], "Send the escalation in Format B-2 by DM.")


def _esc_done(ctx: Context):
    w = world(ctx)
    msgs = [dashes(a.text) for a in w.comms() if is_dm(w, a, WHITFIELD) and re.search(NEW_ID, a.text)]
    if not any(re.search(r"ESCALATION", m) for m in msgs):
        yield (False, "No Format B-2 escalation DM to @dwhitfield (Darnell Whitfield) for the new appeal. Send "
                      "'ESCALATION / Case #: CASE-2026-00091 / Type: Concurrent / Deadline: 2026-04-16 12:00 PM PT / "
                      "Trigger: Parity flag raised; Exceeds Coordinator Authority ($88,500 > $25,000); Concurrent care "
                      "termination with care ending within 72 hours / Summary / My Recommendation / Requested Action'.",
               R_ESC)
        return
    blob = "\n".join(msgs)
    miss = [desc for _, rx, desc in TRIGGERS if not re.search(rx, blob, re.I)]
    yield (not miss, "The escalation DM(s) to @dwhitfield do not name every mandatory trigger present: "
           + "; ".join(miss) + ".", R_ESC)


RULES += state_rule("mca.escalation", _esc_done, "DM @dwhitfield a Format B-2 escalation naming each trigger.")


# ---- 5. channel / PHI / correspondence prohibitions ----------------------------------------------------
def _parity_channel(ctx: Context, a):
    w = world(ctx)
    if not (public_post(w, a) and w.is_channel(a.channel, "appeals-parity")):
        return None
    if re.search(r"CASE-\d{4}-\d{5}|MCA_APPEALS-\d+|PARITY FLAG|AUTH-2026-00441|Desert Springs|MBR-", a.text, re.I):
        return ("[parity channel] Parity flag notifications go by DM to @parity-committee (Format B-3); "
                "#appeals-parity is for general discussion only - do not post case flags there.")
    return None


RULES += pre_rule("mca.parity_channel", _parity_channel, R_PARITY_CH, "DM @parity-committee instead.")


def _public_phi(ctx: Context, a):
    w = world(ctx)
    if not public_post(w, a):
        return None
    m = re.search(r"MBR-\d{4}-\d{5}|Member\s*ID", a.text, re.I)
    if m:
        return (f"[PHI] Public Slack channels must not carry member PHI (found '{m.group(0)}'). Refer to the case only "
                "by its Case ID (CASE-2026-00091); use a DM for anything needing PHI.")
    return None


RULES += pre_rule("mca.public_phi", _public_phi, R_PHI, "Remove the PHI and use the Case ID only.")


def _regulator(ctx: Context, a):
    if a.kind not in ("email_send", "email_draft"):
        return None
    bad = [r for r in list(a.recipients) + list(a.cc) if re.search(r"(?:^|[@.])(?:doi\.)?nv\.gov$|dol\.gov$", r, re.I)]
    if bad:
        return (f"[regulator] Coordinators may not contact the Nevada Division of Insurance or any regulatory agency "
                f"directly ({', '.join(bad)}).")
    return None


RULES += pre_rule("mca.no_regulator", _regulator, R_REGULATOR, "Do not send this.")

EXT_BANNED = [
    (r"\b(?:Ontario|Bergstrom|Alvarado|Henning)\b",
     "Do not name the clinical reviewer in outbound correspondence - say 'the reviewing clinician' or 'our Medical "
     "Director'.", R_REVIEWER),
    (r"(?:authori[sz]ation|coverage|benefits?)\s+(?:will|is going to|is set to|shall)\s+(?:lapse|end|terminate|expire|cease|stop)"
     r"|\blapse[sd]?\b",
     "Do not tell the provider the authorization will lapse while the appeal is pending - coverage continues "
     "through the appeal decision.", R_LAPSE),
    (r"\b(?:service|treatment|care|stay|admission|residential treatment)\s+(?:is|was|remains)\s+(?:not\s+)?medically\s+necessary",
     "Do not state that the service is (or is not) medically necessary - that is the clinical reviewer's decision.",
     R_MEDNEC),
    (r"\b(?:your appeal|the appeal|this appeal|the authori[sz]ation|the denial|the termination)\s+(?:will|shall)\s+be\s+"
     r"(?:approved|overturned|reinstated|granted|reversed)",
     "Do not promise an outcome you cannot guarantee.", R_PROMISE),
    (r"\bsettle(?:ment)?\b|\boffer(?:ing)?\s+(?:to\s+pay|(?:a\s+)?payment)",
     "Coordinators may not settle a case or offer payment or other consideration.",
     [("9.1.3", "Settle a case by offering payment", "9.1.3 no settlement")]),
]


def _external_email(ctx: Context, a):
    if a.kind not in ("email_send", "email_draft") or not (external(a) or a.args.get("email_id")):
        return None
    if any(NON_APPEAL_ADDR.search(r) for r in external(a)) or str(a.args.get("email_id") or "") in NON_APPEAL_EMAILS:
        return None
    probs = []
    if not re.search(rf"Mojave Crest Appeals Case #{NEW_ID}", a.subject or ""):
        probs.append("Subject must carry the Case ID as 'Mojave Crest Appeals Case #CASE-2026-00091 - <Brief "
                     f"Description>' (got \"{a.subject}\"; a reply cannot set it - use google_mail__send_email).")
    body = dashes(a.text)
    probs += [why for rx, why, _ in EXT_BANNED if re.search(rx, body, re.I)]
    return "[outbound email] " + " ".join(probs) if probs else None


def _ext_refs():
    seen, out = set(), []
    for r in R_SUBJ + [x for _, _, refs in EXT_BANNED for x in refs]:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


RULES += pre_rule("mca.external_email", _external_email, _ext_refs(), "Fix the email as listed.")

R_NODET = [("8.3", "Do not issue a determination letter on a parity flagged case", "8.3 Parity Committee concurrence"),
           ("9.1.3", "Issue a determination letter without a clinical reviewer", "9.1.3 no determination without review"),
           ("12.5", "Issuing a determination letter without the required clinical review", "12.5 prohibited")]


def _no_determination(ctx: Context, a):
    if a.kind not in ("email_send", "email_draft") or not (external(a) or a.args.get("email_id")):
        return None
    subj, body = dashes(a.subject), dashes(a.text)
    if (re.search(r"Expedited Decision|Appeal\s+Decision|Appeal\s+Dismissed", subj, re.I)
            or re.search(r"Decision\**\s*:\s*\**\s*Your appeal (?:is|has been)|your appeal (?:is|has been) "
                         r"(?:approved|denied|partially approved|upheld|overturned|dismissed)", body, re.I)):
        return ("[determination] No determination or dismissal may be issued at intake: the case is parity-flagged "
                "and has no clinical reviewer decision or Parity Review Committee concurrence yet.")
    return None


RULES += pre_rule("mca.no_determination", _no_determination, R_NODET, "Do not send a determination now.")
# Bracketed concrete IDs (e.g. the SOP's EOC[GRP-00892][2026].pdf naming) are filled values, not placeholders.
RULES += no_placeholders(R_TPL, literal_rx=[r"\[[A-Z][A-Z_]{1,15}(?:-\d+)+\]"])


# ---- 6. workbooks --------------------------------------------------------------------------------------
RULES += forbid_writes("mca.log_readonly", r"appeals_log_master",
                       "appeals_log_master.xlsx is a read-only legacy reference - do not add or change entries; "
                       "Jira is the system of record for new cases.", R_LOG)


def _grid_same(a, b) -> bool:
    a, b = a or {}, b or {}
    if set(a) != set(b):
        return False
    for sh in a:
        ga, gb = a[sh] or [], b[sh] or []
        n = max(len(ga), len(gb))
        for i in range(n):
            ra = ga[i] if i < len(ga) else []
            rb = gb[i] if i < len(gb) else []
            for j in range(max(len(ra), len(rb))):
                x = ra[j] if j < len(ra) else None
                y = rb[j] if j < len(rb) else None
                if not same(x, None if y in (None, "", "None") else y):
                    return False
    return True


def _books_done(ctx: Context):
    w = world(ctx)
    for name in sorted(w.initial or {}):
        if not isinstance(w.initial[name], dict):
            continue
        ok = _grid_same((w.current or {}).get(name), w.initial[name])
        yield (ok, f"{name} was modified. The seed workbooks are reference data (the Appeals Log is read-only; "
                   "authorizations/claims are not changed at intake). Restore the original content.", R_BOOKS)


RULES += state_rule("mca.workbooks_unchanged", _books_done, "Restore the workbook.")
