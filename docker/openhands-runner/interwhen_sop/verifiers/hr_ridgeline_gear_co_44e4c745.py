"""Verifiers for hr_ridgeline_gear_co_44e4c745: Ridgeline Leave Coordinator inbox, 04/03/2026 9am MT.

Built only from the SOP (Revised SOP.html), the instruction and the seed data. The seven inbox emails and the
SOP outcome derived for each:
  1 Jacquelyn Stuart "Family Illness" - mentions an attorney (18.5): no reply, #legal-review post, email to
    General Counsel with subject "LEGAL THREAT — Jacquelyn Stuart" carrying the thread.
  2 Joseph Monroe "Approval RDG-7894" - payroll transaction (5.5): no reply, forward to Teresa Vang by email.
  3 jbray1@yahoo.com "PTO Check" - address not in the roster (9.1 Step 1): #unknown-senders-hr post, forward
    to Renata Okafor, no reply.
  4 Kirsten Saunders "FMLA Request" - 1,100 hours < 1,250 (12.1/12.7/18.2): Template 3 cc Renata, #leave-intake.
  5 Russ Herbert (personal email on roster) "Request PTO Balance" - PTO balance (Section 1): email to Teresa.
  6 Lorenzo Keith "Funeral" - requests personal unpaid leave specifically (9.1 Step 3, 16.4): Template 26 reply,
    Template 27 forward to Marissa Carlson + Daniel Whitfield, #hr-escalations post with TBD dates.
  7 Jimmy Rustler "Dollars" - payroll calculation question (15.3): Template 16 to Jimmy, forward to Teresa.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Callable

from ..kit import (MAX_DENIALS_PER_TAG, Action, Context, Finding, Ref, Rule, World, cites, dashes, forbid_writes,
                   no_placeholders, prior_denials, registry, state_rule, world)

# ---- people / addresses (employee_roster.xlsx, SOP Section 4) -------------------------------------------------
GC = "evelyn.marchetti@ridgelineholdings.com"
RENATA = "renata.okafor@ridgelinegear.com"
TERESA = "teresa.vang@ridgelinegear.com"
DANIEL = "daniel.whitfield@ridgelinegear.com"
MARISSA = "marissa.carlson@ridgelinegear.com"   # Lorenzo Keith's manager of record
KIRSTEN = "kirsten.saunders@ridgelinegear.com"
LORENZO = "lorenzo.keith@ridgelinegear.com"
JIMMY = "jimmy.rustler@ridgelinegear.com"
JACQ_ADDRS = {"jacquelyn.stuart@ridgelinegear.com", "jstuart_personal@hotmail.com"}
JOSEPH_ADDRS = {"joseph.monroe@ridgelinegear.com", "jmonroe@yahoo.com"}
UNKNOWN = "jbray1@yahoo.com"
KIRSTEN_ADDRS = {KIRSTEN, "ksaunders22@gmail.com"}
LORENZO_ADDRS = {LORENZO, "lkeith_new@gmail.com"}
JIMMY_ADDRS = {JIMMY, "jrustler.sales@hotmail.com"}
# SOP 19.2 HR team (HR Director, Benefits Manager, HR Generalists, Payroll Lead, Safety Coordinator, General
# Counsel) plus the Leaves / escalations inboxes.
HR_TEAM = {DANIEL, RENATA, TERESA, GC, "meera.patel@ridgelinegear.com", "jordan.briggs@ridgelinegear.com",
           "luis.arredondo@ridgelinegear.com", "leaves@ridgelinegear.com", "benefits@ridgelinegear.com"}
NON_HR_HANDLES = {
    "edna.little", "robbie.perry", "cliff.emery", "erik.maldonado", "jacquelyn.stuart", "ernie.cowan",
    "gabriel.ford", "wendy.sheridan", "russ.herbert", "marissa.carlson", "julian.robbins", "dora.bower",
    "terri.glenn", "janis.cummings", "marian.ramirez", "sammy.lowery", "jon.riggs", "rickey.hanna",
    "christian.dalton", "gloria.ferguson", "lucas.clayton", "clara.fuentes", "joseph.monroe", "tracie.avery",
    "kirsten.saunders", "holly.velez", "sherry.gibbs", "jimmy.rustler", "paula.wise", "julio.bray",
    "lorenzo.keith", "cecelia.post", "dominic.lindsay", "leanne.johnston", "amy.byrd"}
SEED_FILES = r"(employee_roster|hours_worked_log|famli_coordination_log|hfwa_balance_tracker)\.xlsx|Revised SOP\.html"

# Medical details present in the seed emails (Jacquelyn's father's diagnosis, Jimmy's injury).
MEDICAL = re.compile(r"\bcancer\b|\bdiagnos(?:is|ed|es)\b|months to live|terminal(?:ly)? ill|head injur|"
                     r"\bconcussion\b|brain injur", re.I)
SPECULATION = [
    (r"\b(likely|unlikely|probably|good chance|chances? (?:are|of)|most requests|usually|generally)\b[^.\n]{0,60}"
     r"\b(approv|grant|den(?:y|ied))", "Do not speculate about whether the request will be approved (16.4 Step 5)."),
    (r"\b(often|typically|usually|normally)\s+(?:get\s+|be\s+|are\s+|is\s+)?(approved|granted|denied)\b",
     "Do not speculate about whether the request will be approved (16.4 Step 5)."),
]

# ---- SOP references (section, paragraph prefix, label) --------------------------------------------------------
R_PTO = ("1", "PTO balance questions (escalate to Teresa Vang via email)", "§1 Out of Scope")
R_PAYROLL_OOS = ("1", "Payroll processing, tax withholding", "§1 Out of Scope")
R_ATTY_GC = ("5.4", "Any employee communication mentioning an attorney", "§5.4")
R_GINA_GC = ("5.4", "Any GINA-related concern", "§5.4")
R_MED_DISCLOSE = ("5.5", "Disclose any employee medical information", "§5.5")
R_EXTERNAL = ("5.5", "Confirm or deny whether an employee is on any type of leave", "§5.5")
R_PAYROLL_TXN = ("5.5", "Discuss one employee's leave with another employee", "§5.5")
R_NO_MED = ("5.5", "Include medical details, diagnoses, or protected health information", "§5.5")
R_SLACK_DM = ("7", "All internal communications about leave cases must use the designated Slack channels", "§7")
R_PAYROLL_CH = ("7", "#payroll-coordination | Payroll handoffs only", "§7 #payroll-coordination")
R_LEGAL_CH = ("7", "#legal-review |", "§7 #legal-review")
R_UNK_CH = ("7", "#unknown-senders-hr |", "§7 #unknown-senders-hr")
R_SLACK_MED = ("7", "Never post medical details, diagnoses", "§7")
R_STEP1 = ("9.1", "Step 1 : Verify the sender is an active employee", "§9.1 Step 1")
R_STEP1_FMT = ("9.1", "address, not display name.", "§9.1 Step 1")
R_STEP1_FWD = ("9.1", "Line], and forward the email to the Benefits Manager", "§9.1 Step 1")
R_STEP3 = ("9.1", "Step 3 : Identify every leave type", "§9.1 Step 3")
R_STEP6 = ("9.1", "Step 6 : Act per the relevant section", "§9.1 Step 6")
R_ELIG = ("12.1", "Step 1. Open employee_roster.xlsx", "§12.1 Procedure")
R_INELIG_HOURS = ("12.7", "Ineligibility due to insufficient hours", "§12.7")
R_DENIAL_CC = ("12.7", "Step 2 . For LC-level, apply section 18.2", "§12.7 Step 2")
R_PAY_HANDOFF = ("15", "Leave Coordinator's role in these areas is strictly notification and handoff", "§15")
R_PAYQ = ("15.3", "When an employee asks the Leave Coordinator any of the following", "§15.3")
R_PAYQ_CALC = ("15.3", "Any question involving a dollar amount", "§15.3")
R_T16_RULE = ("15.3", "The Template 16 explicitly tells the employee", "§15.3")
R_PTO_ROUTE = ("16.2", "The Leave Coordinator handles company PTO only when", "§16.2")
R_PL_STEP1 = ("16.4", "Step 1 : Pre-intake FMLA check", "§16.4 Step 1")
R_PL_STEP2 = ("16.4", "Step 2 : Same-business-day acknowledgment using Template 26", "§16.4 Step 2")
R_PL_STEP3 = ("16.4", "explicitly states that personal leave is discretionary", "§16.4 Step 3")
R_PL_STEP4 = ("16.4", "Step 4 : Post to #hr-escalations", "§16.4 Step 4")
R_PL_STEP5 = ("16.4", "Step 5 : Do NOT communicate with the employee about the outcome", "§16.4 Step 5")
R_DENY_182_2 = ("18.2", "Step 2 : Send the denial using Template 3", "§18.2 Step 2")
R_DENY_182_3 = ("18.2", "Step 3 : Post to #leave-intake: FMLA DENIED", "§18.2 Step 3")
R_LEGAL_TRIG = ("18.5", "Mention of an attorney, lawyer", "§18.5")
R_LEGAL_1 = ("18.5", "Step 1 : DO NOT reply to the email", "§18.5 Step 1")
R_LEGAL_2 = ("18.5", "Step 2 : Post to #legal-review", "§18.5 Step 2")
R_LEGAL_3 = ("18.5", "Step 3 : Forward the email thread to General Counsel", "§18.5 Step 3")
R_EMAIL_MED = ("19.2", "Never include medical details, diagnoses, or protected health information in the body",
               "§19.2")
R_CC = ("19.2", "Never CC anyone outside the HR team", "§19.2")
R_FWD_MED = ("19.2", "Never forward an email thread containing medical information beyond the HR team", "§19.2")
R_QUOTE_MED = ("19.2", "If an employee sends an email containing more medical detail than needed", "§19.2")
R_PERSONAL = ("19.2", "Never use the employee's personal email", "§19.2")
R_SLACK_MED2 = ("19.3", "Never post medical details", "§19.3")
R_TAG = ("19.3", "Never tag managers or non-HR roles", "§19.3")
R_DM = ("19.3", "Direct messages about cases are prohibited", "§19.3")
R_EXT2 = ("19.4", "Never confirm or deny leave status to external callers", "§19.4")
R_DELETE = ("19.5", "Do not delete any case file", "§19.5")
R_TPL_ASIS = ("21", "Use templates as written", "§21")
R_TPL_PH = ("21", "Replace all [bracketed] placeholders", "§21")
R_TPL_MED = ("21", "Do not add medical details", "§21")
R_TPL_SECT = ("21", "Do not delete sections of a template", "§21")
R_TPL_SIG = ("21", "All employee-facing templates close with the standard signature block", "§21")
R_T3 = ("21", "Thank you for submitting your FMLA leave request. I have reviewed your eligibility against",
        "§21 Template 3")
R_T16 = ("21", "Thank you for your question about [topic", "§21 Template 16")
R_T26 = ("21", "Thank you for your personal unpaid leave request.", "§21 Template 26")
R_T27 = ("21", "I am routing a personal unpaid leave request", "§21 Template 27")

# ---- SOP template text (Section 21), filled for this task ---------------------------------------------------
SIG = "Best regards,\nRidgeline Gear Co. — Leave Coordinator\nleaves@ridgelinegear.com"
SIG_RX = (r"Best regards,\s*Ridgeline Gear Co\.\s*[-–—]\s*Leave Coordinator\s*leaves@ridgelinegear\.com",
          'the standard signature block "Best regards," / "Ridgeline Gear Co. — Leave Coordinator" / '
          '"leaves@ridgelinegear.com"')
T3_PARAS = [
    "Thank you for submitting your FMLA leave request. I have reviewed your eligibility against the federal FMLA "
    "criteria and unfortunately must inform you that you are NOT currently eligible for FMLA leave for the "
    "following reason:",
    "Even though you are not eligible for FMLA, you may still be eligible for leave under Colorado FAMLI, which "
    "has different eligibility criteria (no tenure requirement, no minimum hours requirement). If you would "
    "like, I can review your FAMLI eligibility for the same leave reason — please reply to this email to let me "
    "know.",
    "If you believe this FMLA determination is in error, please reply to this email and I will review.",
]
T3_HOURS = ("Hours: FMLA requires at least 1,250 hours worked in the 12 months immediately preceding the leave "
            "start date. Your hours worked in that period are 1,100, which is below the threshold.")
T3_BODY = f"Hi Kirsten,\n\n{T3_PARAS[0]}\n\n{T3_HOURS}\n\n{T3_PARAS[1]}\n\n{T3_PARAS[2]}\n\n{SIG}"
T16_PARAS = [
    "Thank you for your question about",
    "Questions about pay, benefits, deductions, premium billing, and tax matters during leave (outside the remit "
    "of simple balance check requests) are handled by our Payroll Lead, Teresa Vang.",
    "I have forwarded your question to Teresa, and she will respond to you directly within 1–2 business days. "
    "You can also reach her at teresa.vang@ridgelinegear.com.",
    "any questions about the leave process itself, as opposed to pay or benefits.",
]
T16_BODY = ("Hi Jimmy,\n\nThank you for your question about payroll calculations. " + T16_PARAS[1] + "\n\n"
            + T16_PARAS[2] + "\n\nIn the meantime, your leave case is moving forward as planned. Please let me "
            "know if you have " + T16_PARAS[3] + "\n\n" + SIG)
T26_PARAS = [
    "Thank you for your personal unpaid leave request. I want to be transparent with you about how this process "
    "works.",
    "Personal unpaid leave under Ridgeline policy (Handbook §4.8) is discretionary and is not guaranteed. It "
    "requires approval from BOTH your direct manager AND our HR Director. I have forwarded your request to both "
    "for review.",
    "While you wait for a decision, please note:",
    "Personal leave is unpaid.",
    "If approved, your health benefits will continue only if you pay the full premium during the leave "
    "(including the portion normally paid by Ridgeline). Our Payroll Lead can provide details if your leave is "
    "approved.",
    "The maximum personal leave duration under our policy is 30 calendar days.",
    "I will contact you as soon as I have a decision from both approvers — typically within 3–5 business days. "
    "In the meantime, if your situation involves a medical reason for you or a family member, military service, "
    "or another protected leave reason, please let me know. You may be eligible for FMLA, FAMLI, or another "
    "protected leave that I have not yet evaluated for your case.",
]
T26_BODY = ("Hi Lorenzo,\n\n" + T26_PARAS[0] + "\n\n" + T26_PARAS[1] + "\n\n" + T26_PARAS[2] + "\n\n• "
            + T26_PARAS[3] + "\n• " + T26_PARAS[4] + "\n• " + T26_PARAS[5] + "\n\n" + T26_PARAS[6] + "\n\n" + SIG)
T27_PARAS = [
    "I am routing a personal unpaid leave request for your review and decision. Both your approvals are required "
    "per the Leave Coordinator SOP.",
    "Please reply to this email with your decision (approve / deny) at your earliest convenience. I have informed "
    "the employee that approval is not guaranteed and that they should expect a response within 3–5 business "
    "days.",
    "If you need additional information to make your decision, please let me know and I will request it from the "
    "employee.",
]
T27_BODY = ("Hi Marissa and Daniel,\n\n" + T27_PARAS[0] + "\n\nEmployee: Lorenzo Keith\nRequested dates: TBD\n"
            "Total: TBD\n\n" + T27_PARAS[1] + "\n\n" + T27_PARAS[2] + "\n\n" + SIG)
LEGAL_POST = "LEGAL THREAT: Jacquelyn Stuart, Family Illness — do not reply."
LEGAL_SUBJECT = "LEGAL THREAT — Jacquelyn Stuart"
UNK_POST = "UNRECOGNIZED SENDER: Julio Bray, jbray1@yahoo.com, PTO Check"
DENIAL_POST = "FMLA DENIED (INELIGIBILITY): Kirsten Saunders, Hours (1,100 of 1,250 required)"
PL_POST = "PERSONAL LEAVE REQUEST: Lorenzo Keith, TBD — routed for approval."


def trx(sentence: str) -> str:
    """Whitespace/bullet/dash/quote tolerant regex for a literal SOP sentence."""
    parts = []
    for tok in sentence.replace(" / ", "/").split():
        e = re.escape(tok).replace("\\-", "-")
        e = re.sub(r"[-–—]", "[-–—]", e)
        e = e.replace("'", "['’]").replace("’", "['’]").replace("/", r"\s*/\s*")
        parts.append(e)
    return r"[\s•*▪]+".join(parts)


def paras(items: list[str]) -> list[tuple[str, str]]:
    return [(trx(p), f'the template text "{p}"') for p in items]


# ---- action helpers -------------------------------------------------------------------------------------------

def seed_email(w: World, eid: str) -> dict | None:
    return next((e for e in w.seed_emails if str(e.get("email_id")) == eid), None)


def src_id(a: Action) -> str:
    return str(a.args.get("email_id") or "") if ("reply" in a.tool or "forward" in a.tool) else ""


def fill(a: Action, w: World) -> Action:
    """Replies/forwards: add the implied recipient (original sender) and subject the mail server sets."""
    if a.kind not in ("email_send", "email_draft"):
        return a
    eid = src_id(a)
    src = seed_email(w, eid) if eid else None
    if not src:
        return a
    subj = str(src.get("subject") or "")
    if "reply" in a.tool:
        return replace(a, recipients=sorted(set(a.recipients) | {str(src.get("from_addr") or "").lower()}),
                       subject=a.subject or f"Re: {subj}")
    return replace(a, subject=a.subject or f"Fwd: {subj}")


def addrs(a: Action) -> set[str]:
    return set(a.recipients) | set(a.cc)


def is_email(a: Action) -> bool:
    return a.kind == "email_send"


def need_email(a: Action, to: list[str], cc: list[str] = (), exact: bool = False) -> list[str]:
    if a.kind != "email_send":
        return ["Send this as an email."]
    out = []
    miss_to = [x for x in to if x not in a.recipients]
    if miss_to:
        out.append(f"To must include {', '.join(miss_to)}.")
    miss_cc = [x for x in cc if x not in addrs(a)]
    if miss_cc:
        tip = " (the reply tool cannot add CC - use send_email with cc)" if "reply" in a.tool else ""
        out.append(f"CC must include {', '.join(miss_cc)}{tip}.")
    extra = sorted(addrs(a) - set(to) - set(cc))
    if exact and extra:
        out.append(f"Remove recipients the SOP does not route this to: {', '.join(extra)}.")
    return out


def need_post(w: World, a: Action, channel: str) -> list[str]:
    if a.kind != "slack_post" or w.dm_recipients(a) or str(a.channel).startswith("D"):
        return [f"Post this in #{channel}, not as a direct message."]
    if not w.is_channel(a.channel, channel):
        return [f"Post this in #{channel} (got #{w.channel_name(a.channel)})."]
    return []


def need_text(a: Action, items: list[tuple[str, str]]) -> list[str]:
    body = dashes(a.text)
    return [f"Missing {d}." for rx, d in items if not re.search(rx, body, re.I | re.S)]


def banned(a: Action, items: list[tuple[str, str]]) -> list[str]:
    body = dashes(a.text)
    return [why for rx, why in items if re.search(rx, body, re.I | re.S)]


def sent(w: World) -> list[Action]:
    return [fill(b, w) for b in w.calls("email_send", "slack_post", "slack_dm")]


# ---- SOP-prescribed messages ------------------------------------------------------------------------------------

@dataclass
class Msg:
    key: str
    what: str
    refs: list[Ref]
    about: Callable[[Action], bool]
    check: Callable[[Action], list[str]]
    hint: str
    pre: bool = True        # vet matching calls before they run (False: completion-only obligation)
    max_count: int = 1


def specs(ctx: Context) -> list[Msg]:
    w = world(ctx)
    tagged = lambda rx: (lambda a: a.kind in ("slack_post", "slack_dm") and bool(re.search(rx, a.text, re.I)))
    to_teresa = lambda a: is_email(a) and TERESA in addrs(a)

    def gc_check(a: Action) -> list[str]:
        out = need_email(a, [GC])
        if "forward" in a.tool:
            return out + [f'The forward tool cannot set the required subject. Use send_email to {GC} with subject '
                          f'"{LEGAL_SUBJECT}" and paste the original email (From/Date/Subject/body) into the body.']
        if not re.fullmatch(r"(?:(?:Fwd?|FW):\s*)?LEGAL THREAT\s*[-–—]\s*Jacquelyn Stuart", dashes(a.subject), re.I):
            out.append(f'Subject must be exactly "{LEGAL_SUBJECT}" (got "{a.subject}").')
        out += need_text(a, [(r"advance notice of a family situation|My father was recently diagnosed",
                              "the forwarded email thread (paste Jacquelyn Stuart's original 'Family Illness' "
                              "message below your note)")])
        return out

    def t3_check(a: Action) -> list[str]:
        return (need_email(a, [KIRSTEN], [RENATA], exact=True)
                + need_text(a, paras(T3_PARAS[:1]) + [
                    (r"\b1,?250\b", f'the failed criterion "{T3_HOURS}"'),
                    (r"\b1,?100\b", f'the failed criterion "{T3_HOURS}"')] + paras(T3_PARAS[1:]) + [SIG_RX]))

    def t26_check(a: Action) -> list[str]:
        # The opening "Thank you for ..." courtesy line is not enforced word for word.
        required = ["I want to be transparent with you about how this process works."] + T26_PARAS[1:]
        return (need_email(a, [LORENZO])
                + need_text(a, paras(required) + [SIG_RX])
                + banned(a, SPECULATION + [
                    (r"not able to approve bereavement|falls outside the policy'?s coverage|bereavement leave "
                     r"policy \(Handbook",
                     "Lorenzo explicitly requested personal unpaid leave; per 9.1 Step 3 ignore other leave types "
                     "(do not send Template 30) and acknowledge with Template 26.")]))

    def t27_check(a: Action) -> list[str]:
        out = need_email(a, [MARISSA, DANIEL])
        out += need_text(a, paras(T27_PARAS[:1]) + [
            (r"Employee:\s*Lorenzo Keith", 'the line "Employee: Lorenzo Keith"'),
            (r"Requested dates:\s*TBD", 'the line "Requested dates: TBD"'),
            (r"Total:\s*TBD", 'the line "Total: TBD"')] + paras(T27_PARAS[1:]) + [SIG_RX])
        if src_id(a) != "6" and not re.search(r"childhood family friend", a.text, re.I):
            out.append("Forward Lorenzo Keith's original 'Funeral' email (forward_email email_id 6) with Template "
                       "27 as the message.")
        return out

    def t16_check(a: Action) -> list[str]:
        out = need_email(a, [JIMMY])
        if "reply" in a.tool and src_id(a) == "7":
            out.append("Do not reply in the thread: the reply quotes Jimmy's medical detail (head injury). Send "
                       f"Template 16 as a new email (send_email to {JIMMY}, subject \"Re: Dollars\").")
        out += need_text(a, paras(T16_PARAS) + [SIG_RX])
        out += banned(a, [(r"\b(?:100|one hundred|a hundred)\s+cents\b|\bcents in a dollar\b[^.\n]{0,20}\b100\b",
                           "Do not answer the payroll calculation question (no partial answer) - Teresa Vang "
                           "responds directly.")])
        return out

    return [
        Msg("legal_slack", "legal-threat post for Jacquelyn Stuart's 'Family Illness' email",
            [R_LEGAL_TRIG, R_LEGAL_2, R_LEGAL_CH], tagged(r"LEGAL THREAT"),
            lambda a: need_post(w, a, "legal-review") + need_text(a, [(
                r"LEGAL THREAT:\s*Jacquelyn Stuart,\s*Family Illness\s*[-–—]+\s*do not reply",
                f'the line "{LEGAL_POST}"')]),
            f'Post in #legal-review exactly: "{LEGAL_POST}"'),
        Msg("legal_gc", "forward of Jacquelyn Stuart's email thread to General Counsel",
            [R_LEGAL_TRIG, R_LEGAL_3, R_ATTY_GC, R_GINA_GC],
            lambda a: is_email(a) and GC in addrs(a) and (bool(re.search(r"LEGAL THREAT|Jacquelyn", a.subject + a.text,
                                                                         re.I)) or src_id(a) == "1"),
            gc_check,
            f'send_email to {GC}, subject "{LEGAL_SUBJECT}", body: a short routing note plus the full original '
            "'Family Illness' email from jacquelyn.stuart@ridgelinegear.com (From/Date/Subject/body)"),
        Msg("payroll_txn_fwd", "forward of Joseph Monroe's payroll transaction request RDG-7894 to Teresa Vang",
            [R_PAYROLL_TXN], lambda a: to_teresa(a) and (src_id(a) == "2" or bool(re.search(
                r"RDG-7894|Joseph Monroe", a.subject + a.text, re.I))), lambda a: [],
            f"forward_email email_id 2 ('Approval RDG-7894') to {TERESA}; do not reply to Joseph Monroe", pre=False),
        Msg("unknown_slack", "unrecognized-sender post for jbray1@yahoo.com", [R_STEP1, R_STEP1_FMT, R_UNK_CH],
            tagged(r"UNRECOGNIZED SENDER"),
            lambda a: need_post(w, a, "unknown-senders-hr") + need_text(a, [(
                r"UNRECOGNIZED SENDER:\s*Julio Bray,\s*jbray1@yahoo\.com,\s*PTO Check", f'the line "{UNK_POST}"')]),
            f'Post in #unknown-senders-hr: "{UNK_POST}"'),
        Msg("unknown_fwd", "forward of the unrecognized-sender email 'PTO Check' to the Benefits Manager",
            [R_STEP1_FMT, R_STEP1_FWD],
            lambda a: is_email(a) and RENATA in addrs(a) and (src_id(a) == "3" or bool(re.search(
                r"jbray1@yahoo\.com", a.text, re.I))), lambda a: [],
            f"forward_email email_id 3 ('PTO Check' from {UNKNOWN}) to {RENATA}; no reply to the sender", pre=False),
        Msg("kirsten_t3", "Template 3 FMLA Ineligibility Notice to Kirsten Saunders (cc Benefits Manager)",
            [R_ELIG, R_INELIG_HOURS, R_DENIAL_CC, R_DENY_182_2, R_T3, R_TPL_ASIS, R_TPL_SIG, R_PERSONAL],
            lambda a: is_email(a) and bool(addrs(a) & KIRSTEN_ADDRS), t3_check,
            f'send_email to {KIRSTEN}, cc {RENATA}, subject "Re: FMLA Request", body exactly:\n{T3_BODY}'),
        Msg("kirsten_slack", "FMLA ineligibility denial post for Kirsten Saunders", [R_DENY_182_3],
            tagged(r"FMLA DENIED"),
            lambda a: need_post(w, a, "leave-intake") + need_text(a, [(
                r"FMLA DENIED \(INELIGIBILITY\):\s*Kirsten Saunders,\s*[^\n]{0,80}\bhours?\b",
                f'the line "{DENIAL_POST}" (failed criterion = hours)')]),
            f'Post in #leave-intake: "{DENIAL_POST}"'),
        Msg("russ_fwd", "PTO balance inquiry from Russ Herbert escalated to Teresa Vang by email",
            [R_PTO, R_PTO_ROUTE],
            lambda a: to_teresa(a) and (src_id(a) == "5" or bool(re.search(
                r"Russ Herbert|herbrusshr|R-2309", a.subject + a.text, re.I))), lambda a: [],
            f"forward_email email_id 5 ('Request PTO Balance') to {TERESA}", pre=False),
        Msg("lorenzo_t26", "Template 26 Personal Leave Acknowledgment to Lorenzo Keith",
            [R_STEP3, R_PL_STEP1, R_PL_STEP2, R_PL_STEP5, R_T26, R_TPL_ASIS, R_TPL_SIG],
            lambda a: is_email(a) and bool(addrs(a) & LORENZO_ADDRS) and not re.search(
                r"To open your case, I need a few additional details", a.text, re.I),
            t26_check, f'reply to email_id 6 (or send_email to {LORENZO}), body exactly:\n{T26_BODY}'),
        Msg("lorenzo_t27", "Template 27 routing of Lorenzo Keith's request to his manager and the HR Director",
            [R_PL_STEP3, R_T27, R_TPL_ASIS, R_TPL_SIG],
            lambda a: is_email(a) and bool(addrs(a) & {MARISSA, DANIEL}) and (src_id(a) == "6" or bool(
                re.search(r"Lorenzo", a.subject + a.text, re.I))),
            t27_check, f'forward_email email_id 6 to "{MARISSA}, {DANIEL}" with body exactly:\n{T27_BODY}'),
        Msg("lorenzo_slack", "personal leave routing post for Lorenzo Keith", [R_PL_STEP4],
            tagged(r"PERSONAL LEAVE REQUEST"),
            lambda a: need_post(w, a, "hr-escalations") + need_text(a, [(
                r"PERSONAL LEAVE REQUEST:\s*Lorenzo Keith,\s*TBD\s*[-–—]+\s*routed for approval",
                f'the line "{PL_POST}"')]),
            f'Post in #hr-escalations: "{PL_POST}"'),
        Msg("jimmy_t16", "Template 16 Payroll Handoff to Jimmy Rustler",
            [R_PAYQ, R_PAYQ_CALC, R_T16_RULE, R_PAY_HANDOFF, R_T16, R_QUOTE_MED, R_TPL_ASIS],
            lambda a: is_email(a) and bool(addrs(a) & JIMMY_ADDRS), t16_check,
            f'send_email to {JIMMY}, subject "Re: Dollars" (new email, not a reply that quotes his medical detail), '
            f"body:\n{T16_BODY}"),
        Msg("jimmy_fwd", "Jimmy Rustler's payroll calculation question forwarded to Teresa Vang",
            [R_PAYQ, R_PAYROLL_OOS],
            lambda a: to_teresa(a) and (src_id(a) == "7" or bool(re.search(
                r"Jimmy Rustler|R-2328|jimmy\.rustler", a.subject + a.text, re.I))), lambda a: [],
            f"forward_email email_id 7 ('Dollars') to {TERESA} (your note must not mention his injury)", pre=False),
    ]


def message_rules() -> list[Rule]:
    rules: list[Rule] = []
    rule = registry(rules)

    @rule("comms.messages", "pre", [])
    def pre(ctx: Context, action: Action) -> list[Finding]:
        if action.kind not in ("email_send", "slack_post", "slack_dm"):
            return []
        w = world(ctx)
        a = fill(action, w)
        out = []
        for m in specs(ctx):
            if not m.pre or not m.about(a):
                continue
            tag = f"[msg:{m.key}]"
            if prior_denials(ctx, tag) >= MAX_DENIALS_PER_TAG:
                continue
            probs = m.check(a)
            if not probs and sum(1 for b in sent(w) if m.about(b) and not m.check(b)) >= m.max_count:
                probs = [f"This message ({m.what}) was already sent; do not send it again."]
            if probs:
                out.append(Finding("comms.messages", cites(ctx, m.refs), f"{tag} {m.what}: " + " ".join(probs),
                                   ["Fix the message as listed and send it again."]))
        return out

    @rule("comms.messages_sent", "completion", [])
    def done(ctx: Context) -> list[Finding]:
        w = world(ctx)
        msgs = sent(w)
        return [Finding("comms.messages_sent", cites(ctx, m.refs), f"Not yet done per the SOP: {m.what}.",
                        [m.hint]) for m in specs(ctx) if not any(m.about(b) and not m.check(b) for b in msgs)]

    return rules


# ---- prohibitions -------------------------------------------------------------------------------------------------

NO_REPLY = [
    (JACQ_ADDRS, "Jacquelyn Stuart's 'Family Illness' email mentions an attorney, so it is handled as a legal "
                 "threat: do not reply to her under any circumstances, even to acknowledge receipt. Only post to "
                 "#legal-review and forward the thread to General Counsel.", [R_LEGAL_TRIG, R_LEGAL_1]),
    (JOSEPH_ADDRS, "Joseph Monroe asked for approval of payroll transaction RDG-7894: do not reply to requests of "
                   f"this nature - forward the request to Teresa Vang ({TERESA}) by email.", [R_PAYROLL_TXN]),
    ({UNKNOWN}, f"{UNKNOWN} is not in employee_roster.xlsx (match on email address, not display name): do not "
                "reply to the sender until the Benefits Manager instructs you. Post to #unknown-senders-hr and "
                f"forward the email to {RENATA}.", [R_STEP1_FMT, R_STEP1_FWD, R_EXT2, R_EXTERNAL]),
]


def no_reply_rules() -> list[Rule]:
    rules: list[Rule] = []
    rule = registry(rules)

    @rule("comms.no_reply", "pre", [])
    def check(ctx: Context, action: Action) -> list[Finding]:
        if action.kind != "email_send":
            return []
        a = fill(action, world(ctx))
        return [Finding("comms.no_reply", cites(ctx, refs), why, ["Do not send this email."])
                for who, why, refs in NO_REPLY if addrs(a) & who]

    return rules


def _no_dm(ctx: Context, a: Action):
    w = world(ctx)
    if a.kind == "slack_dm" or (a.kind == "slack_post" and (w.dm_recipients(a) or str(a.channel).startswith("D"))):
        return ("Direct messages are not permitted for case-related communication (they cannot be audited). "
                "Post in the designated channel (#leave-intake, #benefits-team, #hr-escalations, "
                "#payroll-coordination, #legal-review, #unknown-senders-hr) or email instead.")
    return None


def _cc_hr_only(ctx: Context, action: Action):
    if action.kind not in ("email_send", "email_draft"):
        return None
    outside = sorted(set(action.cc) - HR_TEAM)
    return (f"Do not CC anyone outside the HR team on a case-related email (remove CC: {', '.join(outside)}). "
            "Managers get their own notification email." if outside else None)


def _no_medical(ctx: Context, action: Action):
    w = world(ctx)
    a = fill(action, w)
    if a.kind in ("slack_post", "slack_dm"):
        m = MEDICAL.search(a.text)
        return (f'Never post medical details or diagnoses in Slack (found "{m.group(0)}"). Remove it.' if m else None)
    if a.kind not in ("email_send", "email_draft"):
        return None
    if GC in a.recipients:
        return None  # 18.5 Step 3: the legal-threat thread goes to General Counsel as is
    if "forward" in a.tool and src_id(a) in ("1", "7") and addrs(a) - HR_TEAM:
        return ("This email thread contains medical information; never forward it beyond the HR team "
                f"(remove {', '.join(sorted(addrs(a) - HR_TEAM))}).")
    m = MEDICAL.search(a.subject + "\n" + a.text)
    return (f'Never include medical details or diagnoses in an email (found "{m.group(0)}"). Remove it - the '
            "recipient only needs the routing facts." if m else None)


def _no_tag(ctx: Context, a: Action):
    if a.kind != "slack_post":
        return None
    tags = sorted({h for h in re.findall(r"@([a-z]+\.[a-z]+)", a.text.lower()) if h in NON_HR_HANDLES})
    return (f"Never tag managers or non-HR employees in Slack (remove @{', @'.join(tags)})." if tags else None)


def _payroll_scope(ctx: Context, a: Action):
    if a.kind != "slack_post" or not world(ctx).is_channel(a.channel, "payroll-coordination"):
        return None
    if re.search(r"Jacquelyn|Stuart|Julio|jbray1|Kirsten|Saunders|Lorenzo|LEGAL THREAT|UNRECOGNIZED SENDER|"
                 r"FMLA DENIED|PERSONAL LEAVE REQUEST", a.text, re.I):
        return ("#payroll-coordination is for payroll handoffs only (leave start/end, unpaid status, return "
                "dates). None of today's legal, unknown-sender, FMLA-denial or pending personal-leave cases has a "
                "payroll event - use the designated channel instead.")
    return None


def _pre(rule_id: str, fn, refs: list[Ref], fix: str) -> list[Rule]:
    rules: list[Rule] = []
    rule = registry(rules)

    @rule(rule_id, "pre", [])
    def check(ctx: Context, action: Action) -> list[Finding]:
        msg = fn(ctx, action)
        return [Finding(rule_id, cites(ctx, refs), msg, [fix])] if msg else []

    return rules


def _files_unchanged(ctx: Context):
    changed = world(ctx).changed_files()
    yield (not changed, f"Workbooks were modified although no SOP step for today's emails writes to them: "
                        f"{', '.join(changed)}. Restore the original content.", [R_ELIG, R_DELETE])


RULES: list[Rule] = (
    message_rules()
    + no_reply_rules()
    + _pre("comms.no_dm", _no_dm, [R_SLACK_DM, R_DM], "Use the designated Slack channel or email.")
    + _pre("comms.cc_hr_only", _cc_hr_only, [R_CC], "Remove the non-HR CC.")
    + _pre("comms.no_medical", _no_medical,
           [R_MED_DISCLOSE, R_NO_MED, R_SLACK_MED, R_EMAIL_MED, R_FWD_MED, R_SLACK_MED2, R_TPL_MED],
           "Remove the medical detail.")
    + _pre("comms.no_tag_managers", _no_tag, [R_TAG], "Remove the @-mention.")
    + _pre("comms.payroll_channel_scope", _payroll_scope, [R_PAYROLL_CH], "Post in the designated channel.")
    + no_placeholders([R_TPL_PH])
    + forbid_writes("files.no_writes", SEED_FILES,
                    "no SOP step for today's emails writes to the roster, hours log, FAMLI log, HFWA tracker or SOP "
                    "(do not recalculate or impute data; do not delete case files).", [R_ELIG, R_DELETE])
    + state_rule("files.unchanged", _files_unchanged, "Restore the workbook.")
)
