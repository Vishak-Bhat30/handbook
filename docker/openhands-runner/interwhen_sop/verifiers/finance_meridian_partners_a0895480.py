"""SOP verifiers for finance_meridian_partners_a0895480 (Meridian Partners AP, SOP-FIN-AP-004).

Situation (today 2026-04-08, acting as AP Clerk, mailbox ap@meridianpartners.com):
- Nine Invoice Register rows are PENDING (INV-018..INV-026). All validate: the four PO invoices pass the
  three-way match exactly, the two recurring invoices are within their active agreements, and the three non-PO
  invoices carry the approvals their tier requires. Each is approved and queued (ACH) in the Payment Queue;
  the two <= $2,500 PO invoices are self-approved with a SELF-APPROVED post in #ap-approvals. The instruction
  forbids requesting approval for the newly queued payments.
- The one unread email is Cascade Cleaning invoice CC-2026-0168 under recurring agreement RA-2026-001, which
  expired 2026-03-31: STOP, enter it on APPR hold (not queued) and email the Approving Manager (T. Okonkwo)
  with the Appendix A "Expired Recurring Agreement" template.
"""

from __future__ import annotations

import re

from ..kit import (COMM_KINDS, Action, Comm, Context, append_only, blank, comm_rules, dashes, no_placeholders,
                   norm, num, pre_rule, same, state_rule, world)

TODAY = "2026-04-08"
LEDGER = r"(^|/)ap_ledger\.xlsx$"
VMASTER = r"(^|/)vendor_master\.xlsx$"
RECUR = r"(^|/)recurring_agreements\.xlsx$"
MLOG_Q1 = r"(^|/)match_log_2026_Q1\.xlsx$"
MLOG_Q2 = r"(^|/)match_log_2026_Q2\.xlsx$"

# ---- SOP references ------------------------------------------------------------------------------
R_HOLD = ("2", "Hold Status | An invoice flagged", "§2 Hold Status")
R_ADHOC = ("3", "All AP staff must use the following systems", "§3")
R_FILES = ("3.2", "All AP files must be stored", "§3.2")
R_INVDIR = ("3.2", "Invoices/YYYY-MM/ |", "§3.2 Invoices/")
R_SLACK = ("3.3", "Use the following Slack channels", "§3.3")
R_CH_EXC = ("3.3", "#ap-exceptions |", "§3.3 #ap-exceptions")
R_CH_APPR = ("3.3", "#ap-approvals |", "§3.3 #ap-approvals")
R_CH_ESC = ("3.3", "#ap-escalations |", "§3.3 #ap-escalations")
R_CH_PAY = ("3.3", "#ap-payments |", "§3.3 #ap-payments")
R_CH_ME = ("3.3", "#finance-month-end |", "§3.3 #finance-month-end")
R_INTAKE = ("4", "All invoices arrive through one of three channels", "§4")
R_CL_PO = ("4.3", "PO Invoice | Invoice references a valid PO", "§4.3 PO Invoice")
R_CL_NPO = ("4.3", "Non-PO Invoice | No PO number referenced", "§4.3 Non-PO Invoice")
R_CL_REC = ("4.3", "Recurring Invoice | Invoice matches any recurring", "§4.3 Recurring Invoice")
R_MATCH = ("5.1", "For every PO invoice, the AP clerk must verify", "§5.1")
R_TOL_PRICE = ("5.1.1", "Unit Price Variance |", "§5.1.1 Unit Price")
R_TOL_QTY = ("5.1.1", "Quantity Variance |", "§5.1.1 Quantity")
R_TOL_TOTAL = ("5.1.1", "Total Invoice Amount |", "§5.1.1 Total")
R_DUPL = ("5.2", "Before entering any invoice into the Invoice Register", "§5.2")
R_NPO = ("5.3", "Invoices without a valid PO require retroactive approval", "§5.3")
R_NPO_T2 = ("5.3", "$500.01 – $5,000.00 |", "§5.3 $500.01-$5,000 tier")
R_NPO_T3 = ("5.3", "$5,000.01 – $25,000.00 |", "§5.3 $5,000.01-$25,000 tier")
R_REC1 = ("5.4", "Step 1: Verify the agreement has not expired", "§5.4 Step 1")
R_REC2 = ("5.4", "Step 2: Compare the invoice amount to the Expected Amount", "§5.4 Step 2")
R_REC3 = ("5.4", "Step 3: If within tolerance and not expired", "§5.4 Step 3")
R_QUEUE = ("7", "After an invoice has been matched (or approved as non-PO)", "§7")
R_T1 = ("7.1", "$0.01 – $2,500 |", "§7.1 $0.01-$2,500 tier")
R_T2 = ("7.1", "$2,500.01 – $10,000 |", "§7.1 $2,500.01-$10,000 tier")
R_T3 = ("7.1", "$10,000.01 – $50,000 |", "§7.1 $10,000.01-$50,000 tier")
R_ESC = ("13", "Escalations must be posted to the correct Slack channel", "§13")
R_BANK1 = ("13.2", "Step 1: Do NOT update vendor_master.xlsx", "§13.2 Step 1")
R_BANK5 = ("13.2", "Step 5: Only after receiving written verification", "§13.2 Step 5")
R_ESC_FMT = ("13.3", "All escalation Slack messages must follow these exact formats", "§13.3")
R_BATCH = ("15.1", "Meridian Partners processes payments in batch", "§15.1")
R_NOHOLD = ("15.2", "2. No invoices in the batch have an active hold status", "§15.2 item 2")
R_NOIC = ("15.2", "4. No intercompany invoices", "§15.2 item 4")
R_ACH = ("15.3", "ACH | Default for all domestic vendors", "§15.3 ACH")
R_AUDIT = ("16", "All AP transactions are subject to internal and external audit", "§16")
R_APX_A = ("16.2", "The following email templates supplement", "Appendix A")
R_EXP_TO = ("16.2", "To: [Approving Manager from recurring_agreements.xlsx]", "Appendix A To")
R_EXP_CC = ("16.2", "CC: ap@meridianpartners.com", "Appendix A CC")
R_EXP_SUBJ = ("16.2", "Subject: Meridian Partners - Expired Recurring Agreement", "Appendix A Subject")
R_EXP_DEAR = ("16.2", "Dear [Approving Manager Name],", "Appendix A greeting")
R_EXP_B1 = ("16.2", "A recurring invoice has been received for a vendor whose agreement has expired", "Appendix A body")
R_EXP_B2 = ("16.2", "Vendor: [VENDOR NAME] ([VENDOR ID]). Invoice: [INVOICE NUMBER]", "Appendix A body")
R_EXP_B3 = ("16.2", "Please reply RENEWED or TERMINATED", "Appendix A body")
R_EXP_SIGN = ("16.2", "Meridian Partners Accounts Payable", "Appendix A sign-off")
R_SA_WHO = ("16.2", "Posted By: AP Clerk (after three-way match)", "Appendix B posted by")
R_SA_WHEN = ("16.2", "When to Post: Immediately after self-approving", "Appendix B when")
R_SA_FMT = ("16.2", "SELF-APPROVED: [VENDOR NAME], [VENDOR ID]", "Appendix B format")

# ---- seed facts (Invoice Register / PO Register / recurring_agreements / vendor_master) --------------
PENDING = {
    "INV-018": dict(num="INV-2026-10041", vid="V-000042", vname="Apex Office Supply", date="2026-03-25",
                    due="2026-04-25", terms="Net 30", amt=620.0, cat="PO", po="PO-2026-00531", unit=62.0, qty=10),
    "INV-019": dict(num="TS-10168", vid="V-000015", vname="TechStream IT Services Inc", date="2026-04-01",
                    due="2026-05-01", terms="Net 30", amt=8750.0, cat="REC", ra="RA-2026-002"),
    "INV-020": dict(num="KCA-2026-007", vid="V-000110", vname="Kovacs Consulting LLC", date="2026-03-22",
                    due="2026-05-08", terms="Net 45", amt=2800.0, cat="NPO"),
    "INV-021": dict(num="BWT-2026-0041", vid="V-000117", vname="Blackwood Technologies Inc", date="2026-03-22",
                    due="2026-04-22", terms="Net 30", amt=4500.0, cat="PO", po="PO-2026-00544", unit=4500.0, qty=1),
    "INV-022": dict(num="SP-2026-03", vid="V-000091", vname="Solaris Properties", date="2026-03-31",
                    due="2026-04-30", terms="Net 30", amt=14000.0, cat="REC", ra="RA-2026-003"),
    "INV-023": dict(num="FHR-2026-012", vid="V-000145", vname="Ferndale HR Consulting", date="2026-04-01",
                    due="2026-05-01", terms="Net 30", amt=3200.0, cat="NPO"),
    "INV-024": dict(num="RPM-0233", vid="V-000104", vname="Redwood Print & Media", date="2026-03-28",
                    due="2026-04-27", terms="Net 30", amt=1050.0, cat="PO", po="PO-2026-00558", unit=175.0, qty=6),
    "INV-025": dict(num="HAP-2026-003", vid="V-000124", vname="Hargrove & Associates PC", date="2026-04-01",
                    due="2026-05-01", terms="Net 30", amt=5500.0, cat="NPO"),
    "INV-026": dict(num="VCS-0119-26", vid="V-000019", vname="Vertex Cloud Solutions LLC", date="2026-04-01",
                    due="2026-04-16", terms="Net 15", amt=5200.0, cat="PO", po="PO-2026-00519", unit=5200.0, qty=1),
}
SELF_TIER = ("INV-018", "INV-024")
CASCADE = dict(num="CC-2026-0168", vid="V-000031", vname="Cascade Cleaning Co", amt=2200.0)
MGR_EMAIL = "t.okonkwo@meridianpartners.com"
AP_EMAIL = "ap@meridianpartners.com"


def _tier(amt: float) -> tuple[str, tuple]:
    if amt <= 2500:
        return "AP Clerk self-approval", R_T1
    if amt <= 10000:
        return "AP Manager (Tanya Okonkwo)", R_T2
    if amt <= 50000:
        return "AP Manager AND Controller (Rachel Whitfield)", R_T3
    return "Controller AND CFO", R_T3


def _ids(key: str) -> tuple[str, str]:
    return key, PENDING[key]["num"]


def _mentions(text: str, token: str) -> bool:
    return bool(re.search(rf"(?<![\w-]){re.escape(token)}(?![\w-])", text or "", re.I))


def _row_has(row: dict, token: str) -> bool:
    return any(k != "__row__" and norm(v) == norm(token) for k, v in row.items())


def _money(v: float) -> str:
    return f"${v:,.2f}"


def _num_ok(got, want: float) -> bool:
    """Numeric cell equals ``want``; an unevaluated formula is accepted (cannot be computed here)."""
    return str(got).strip().startswith("=") or same(got, want)


def _date_ok(got, want: str) -> bool:
    import datetime as dt
    s = str(got or "").strip()
    if s.startswith(want):
        return True
    d = dt.date.fromisoformat(want)
    for fmt in ("%m/%d/%Y", "%-m/%-d/%Y", "%B %-d, %Y", "%b %-d, %Y", "%d-%b-%Y"):
        if s.lower().startswith(d.strftime(fmt).lower()):
            return True
    return False


def _books(w, name_rx: str) -> list[str]:
    return [k for k in w.books(name_rx) if isinstance((w.current or {}).get(k), dict)]


def _rows_in(w, path: str, header_rx: str, which: str = "current", sheet_rx: str | None = None) -> list[dict]:
    return w.rows("^" + re.escape(path) + "$", header_rx, which, sheet_rx)


# ---- messages ------------------------------------------------------------------------------------------

APPROVAL_REQ = re.compile(
    r"\bapproval\s+(?:is\s+)?(?:required|requested|request|needed)\b"
    r"|\b(?:request(?:ing|s)?|need(?:s|ed)?|require(?:s|d)?|seek(?:ing)?)\s+(?:your\s+|the\s+)?(?:[\w.&+]+\s+){0,3}?"
    r"(?:approval|sign-?\s?off|authori[sz]ation)\b"
    r"|\bplease\s+(?:review\s+and\s+)?(?:approve|authori[sz]e|sign\s?off)\b", re.I)


def _self_approved_text(key: str) -> str:
    p = PENDING[key]
    return (f"SELF-APPROVED: {p['vname']}, {p['vid']}, Invoice {p['num']}, Amount {_money(p['amt'])}, "
            f"PO {p['po']}, Match Status: PASS, Approved by AP Clerk")


def _self_approved_rx(key: str) -> str:
    p = PENDING[key]
    whole = f"{int(p['amt']):,}".replace(",", ",?")
    vname = re.escape(p["vname"]).replace("\\&", "(?:&|&amp;|and)")
    return (rf"SELF-APPROVED: {vname}, {p['vid']}, Invoice {re.escape(p['num'])}, Amount \${whole}(?:\.00)?, "
            rf"PO {p['po']}, Match Status: PASS, Approved by [^\n\[\]]+")


def _about_self(key: str):
    def about(a: Action) -> bool:
        return a.kind in COMM_KINDS and re.search(r"SELF[-\s]?APPROVED", a.text or "", re.I) is not None \
            and any(_mentions(a.text, t) for t in _ids(key))
    return about


def _about_expired(a: Action) -> bool:
    if a.kind not in ("email_send", "email_draft"):
        return False
    txt = f"{a.subject}\n{a.text}"
    return (_mentions(txt, CASCADE["num"]) and MGR_EMAIL in a.recipients) or \
        re.search(r"Expired Recurring Agreement", a.subject or "", re.I) is not None


def _about_request(key: str):
    def about(a: Action) -> bool:
        if a.kind not in COMM_KINDS or re.match(r"\s*[*_]*SELF[-\s]?APPROVED", a.text or "", re.I):
            return False
        txt = f"{a.subject}\n{a.text}"
        return any(_mentions(txt, t) for t in _ids(key)) and APPROVAL_REQ.search(dashes(txt)) is not None
    return about


DATE_0401 = r"(?:2026-04-01|0?4/0?1/2026|April 0?1,? 2026|Apr\.? 0?1,? 2026|1 April 2026)"
DATE_0331 = r"(?:2026-03-31|0?3/31/2026|March 31,? 2026|Mar\.? 31,? 2026|31 March 2026)"


def _specs(ctx: Context) -> list[Comm]:
    out: list[Comm] = []
    for key in SELF_TIER:
        p = PENDING[key]
        out.append(Comm(
            key=f"selfapproved_{key}", kind="slack_post", about=_about_self(key), channel="ap-approvals",
            what=f"self-approval confirmation for {key} / {p['num']} ({p['vname']}, {_money(p['amt'])}, "
                 f"three-way match PASS on {p['po']})",
            refs=[R_T1, R_SA_WHO, R_SA_WHEN, R_SA_FMT],
            exact=_self_approved_rx(key), exact_hint=_self_approved_text(key)))
    for key, p in PENDING.items():
        if key in SELF_TIER:
            continue
        who, ref = _tier(p["amt"])
        out.append(Comm(
            key=f"no_selfapproval_{key}", kind="slack_post", about=_about_self(key),
            what=f"self-approval of {key} / {p['num']}", refs=[R_T1, ref],
            forbidden=f"{p['num']} is {_money(p['amt'])}, above the $2,500 AP Clerk self-approval tier; its payment "
                      f"sign-off belongs to the {who}. Do not post a SELF-APPROVED message for it."))
    out.append(Comm(
        key="no_selfapproval_cascade", kind="slack_post",
        about=lambda a: a.kind in COMM_KINDS and re.search(r"SELF[-\s]?APPROVED", a.text or "", re.I) is not None
        and _mentions(a.text, CASCADE["num"]),
        what="self-approval of CC-2026-0168", refs=[R_REC1],
        forbidden="CC-2026-0168 falls under recurring agreement RA-2026-001, which expired 2026-03-31: it must stay on "
                  "APPR hold and must not be approved."))
    for key, p in PENDING.items():
        who, ref = _tier(p["amt"])
        out.append(Comm(
            key=f"no_approval_request_{key}", kind="slack_post", about=_about_request(key),
            what=f"approval request for newly queued payment {key} / {p['num']}", refs=[ref, R_QUEUE],
            forbidden=f"The task instruction says not to directly request approval for newly queued payments - the "
                      f"{who} is contacted automatically when the Payment Queue is updated. Just queue {key}."))
    body = [
        (r"\bDear (?:T\.? ?Okonkwo|Tanya(?: Okonkwo)?)\b", "the greeting \"Dear T. Okonkwo,\""),
        (r"A recurring invoice has been received for a vendor whose agreement has expired\.\s*The invoice has been "
         r"placed on APPR hold and cannot be processed until the agreement is renewed or confirmed\.",
         "the sentences \"A recurring invoice has been received for a vendor whose agreement has expired. The invoice "
         "has been placed on APPR hold and cannot be processed until the agreement is renewed or confirmed.\""),
        (rf"Vendor: Cascade Cleaning Co\.? \(V-000031\)\.\s*Invoice: CC-2026-0168, dated {DATE_0401}\.\s*"
         rf"Amount: \$2,?200(?:\.00)?\.\s*Service Description: Monthly office cleaning[^\[\]]{{0,160}}?\s*"
         rf"GL Code: 6500-001-xxxx\.\s*Agreement Expiration Date: {DATE_0331}\.?",
         "the line \"Vendor: Cascade Cleaning Co (V-000031). Invoice: CC-2026-0168, dated 2026-04-01. Amount: "
         "$2,200.00. Service Description: Monthly office cleaning – all floors, common areas, and restrooms. GL Code: "
         "6500-001-xxxx. Agreement Expiration Date: 2026-03-31.\""),
        (r"Please reply RENEWED or TERMINATED within 5 business days\.\s*If renewed, provide the new expiration date "
         r"so we can update recurring_agreements\.xlsx\.\s*If no response is received within 5 business days, the "
         r"invoice will remain on hold and the vendor will be notified of the delay\.",
         "the paragraph \"Please reply RENEWED or TERMINATED within 5 business days. If renewed, provide the new "
         "expiration date so we can update recurring_agreements.xlsx. If no response is received within 5 business "
         "days, the invoice will remain on hold and the vendor will be notified of the delay.\""),
        (r"Thank you,?\s*Meridian Partners Accounts Payable", "the sign-off \"Thank you, Meridian Partners Accounts "
                                                             "Payable\""),
    ]
    out.append(Comm(
        key="expired_agreement", kind="email", about=_about_expired,
        what="Expired Recurring Agreement email to the Approving Manager for Cascade Cleaning invoice CC-2026-0168 "
             "(RA-2026-001 expired 2026-03-31)",
        refs=[R_REC1, R_APX_A, R_EXP_TO, R_EXP_CC, R_EXP_SUBJ, R_EXP_DEAR, R_EXP_B1, R_EXP_B2, R_EXP_B3, R_EXP_SIGN],
        to=[MGR_EMAIL], cc=[AP_EMAIL],
        subject=r"Meridian Partners [-–] Expired Recurring Agreement [-–] Cascade Cleaning Co\.? [-–] "
                r"Invoice CC-2026-0168",
        subject_hint="Meridian Partners - Expired Recurring Agreement - Cascade Cleaning Co - Invoice CC-2026-0168",
        body=body))
    return out


# ---- Slack / email routing ------------------------------------------------------------------------------

TAG_CHANNEL = {
    "SELF-APPROVED": "ap-approvals", "NEW VENDOR ADDED": "ap-approvals",
    "DUPLICATE DETECTED": "ap-exceptions", "PRICE VARIANCE": "ap-exceptions", "VENDOR OVERPAYMENT": "ap-exceptions",
    "OFF-CYCLE REQUEST": "ap-payments", "BATCH COMPLETE": "ap-payments", "PAYMENT FAILURE": "ap-payments",
    "FRAUD ALERT": "ap-escalations", "LEGAL THREAT": "ap-escalations", "VENDOR DISPUTE": "ap-escalations",
    "BANK CHANGE REQUEST": "ap-escalations", "POTENTIAL BEC FRAUD": "ap-escalations",
    "DUPLICATE VENDOR SUSPECTED": "ap-escalations", "DUPLICATE PAYMENT FOUND": "ap-escalations",
    "AUDIT HOLD APPLIED": "ap-escalations",
    "AP ACCRUALS POSTED": "finance-month-end", "AP RECONCILIATION COMPLETE": "finance-month-end",
    "INTERCOMPANY SETTLED": "finance-month-end", "AP CLOSE COMPLETE": "finance-month-end",
}
ESCALATION_TAGS = ("FRAUD ALERT", "LEGAL THREAT", "VENDOR DISPUTE", "PAYMENT FAILURE", "BANK CHANGE REQUEST",
                   "POTENTIAL BEC FRAUD", "DUPLICATE VENDOR SUSPECTED", "DUPLICATE PAYMENT FOUND", "AUDIT HOLD APPLIED")
TAG_RX = re.compile(r"\b(" + "|".join(sorted(map(re.escape, TAG_CHANNEL), key=len, reverse=True)) + r")\s*:")


def _lead_tag(text: str) -> str | None:
    m = re.match(r"[\s*_>`]*(" + "|".join(sorted(map(re.escape, TAG_CHANNEL), key=len, reverse=True)) + r")\s*[*_]*:",
                 text or "")
    return m.group(1) if m else None


def _tag_problem(ctx: Context, a: Action) -> str | None:
    if a.kind not in ("slack_post", "slack_dm"):
        return None
    w = world(ctx)
    text = a.text or ""
    tags = TAG_RX.findall(text)
    if not tags:
        return None
    if w.dm_recipients(a) or a.kind == "slack_dm":
        return (f"[slack-dm] {tags[0]} messages need an audit trail - post them in #{TAG_CHANNEL[tags[0]]}, "
                "not as a direct message.")
    lead = _lead_tag(text)
    if lead == "BATCH COMPLETE" or "BATCH COMPLETE" in tags:
        return ("[batch] BATCH COMPLETE is posted only after the AP Manager runs the Tuesday/Thursday 2:00 PM batch; "
                "no batch has been run - just leave the invoices queued (Status PENDING) in the Payment Queue.")
    if lead is None:
        esc = [t for t in tags if t in ESCALATION_TAGS]
        if esc:
            return (f"[format] Escalation messages must follow the exact format with no greetings or commentary: start "
                    f"the message with \"{esc[0]}:\" and post it in #{TAG_CHANNEL[esc[0]]}.")
        return None
    want = TAG_CHANNEL[lead]
    if not w.is_channel(a.channel, want):
        return f"[channel] {lead} messages go in #{want} (got #{w.channel_name(a.channel)})."
    if lead in ESCALATION_TAGS and re.search(r"^\W*(hi|hello|hey|dear|team)\b|\b(thanks|thank you|regards|cheers)\b",
                                             text, re.I):
        return (f"[format] {lead} escalations use the exact SOP format - no greetings, sign-offs or additional "
                "commentary.")
    return None


INVOICE_TOKEN = re.compile(r"\bINV-\d{3}\b|\bPO-\d{4}-\d{5}\b|\b(?:invoice|payment|credit memo)s?\b", re.I)


def _dm_problem(ctx: Context, a: Action) -> str | None:
    if a.kind not in ("slack_post", "slack_dm"):
        return None
    w = world(ctx)
    if not (a.kind == "slack_dm" or w.dm_recipients(a)):
        return None
    txt = a.text or ""
    tokens = [t for k, p in PENDING.items() for t in (k, p["num"]) if _mentions(txt, t)]
    if _mentions(txt, CASCADE["num"]) or tokens or INVOICE_TOKEN.search(txt):
        return ("[slack-dm] AP invoice/payment matters need an audit trail - use the SOP channel (#ap-approvals, "
                "#ap-exceptions, #ap-escalations or #ap-payments), not a direct message.")
    return None


def _email_esc_problem(ctx: Context, a: Action) -> str | None:
    if a.kind not in ("email_send", "email_draft"):
        return None
    for t in ESCALATION_TAGS:
        if re.match(rf"[\s*_]*(?:(?:re|fwd?):\s*)*{re.escape(t)}\s*:", a.subject or "", re.I) or \
                re.match(rf"[\s*_]*{re.escape(t)}\s*:", a.text or ""):
            return (f"[escalation-email] {t} escalations are posted in Slack #{TAG_CHANNEL[t]}, not emailed (email only "
                    "during a Slack outage).")
    return None


# ---- end state: Invoice Register --------------------------------------------------------------------------

REG = dict(sheet_rx=r"^Invoice Register$")
REG_H = r"^Invoice ID$"
HOLD_RX = re.compile(r"hold|\bMATCH\b|\bAPPR\b|\bDUPL\b|\bDISP\b|\bAUDIT\b", re.I)


def _status_ok(s: str) -> bool:
    n = norm(s)
    if n in ("", "pending", "none") or HOLD_RX.search(s or "") or n in ("paid", "cleared", "rejected"):
        return False
    return bool(re.search(r"approv|queue|schedul|pending payment|awaiting payment", n))


def _register_pending(ctx: Context):
    w = world(ctx)
    rows = w.rows(LEDGER, REG_H, **REG)
    if not rows:
        return
    for key, p in PENDING.items():
        row = next((r for r in rows if norm(w.col(r, r"^Invoice ID$")) == norm(key)), None)
        refs = {"PO": [R_CL_PO, R_MATCH, R_TOL_PRICE, R_TOL_QTY, R_TOL_TOTAL, R_QUEUE],
                "REC": [R_CL_REC, R_REC2, R_REC3, R_QUEUE], "NPO": [R_CL_NPO, R_NPO, R_QUEUE]}[p["cat"]]
        if p["cat"] == "PO":
            why = f"three-way match against {p['po']} passes exactly ({p['qty']} x {_money(p['unit'])}, GR qty {p['qty']})"
        elif p["cat"] == "REC":
            why = f"recurring agreement {p['ra']} is active and the amount equals the Expected Amount"
        else:
            why = "the approvals its §5.3 amount tier requires are documented in its Notes"
        if row is None:
            yield False, f"{key} ({p['num']}) is missing from the Invoice Register - restore the row.", refs
            continue
        status, hold = w.col(row, r"^Status$"), w.col(row, r"^Hold Code$")
        mstat = w.col(row, r"^Match Status$")
        bad = []
        if not _status_ok(status):
            bad.append(f"Status \"APPROVED\" (got \"{status}\")")
        if not blank(hold):
            bad.append(f"Hold Code blank (got \"{hold}\")")
        if p["cat"] == "PO" and "pass" not in norm(mstat):
            bad.append(f"Match Status \"MATCH-PASS\" (got \"{mstat}\")")
        yield not bad, (f"{key} ({p['vname']} {p['num']}, {_money(p['amt'])}) is still not brought current in the "
                        f"Invoice Register: {why}, so it is approved and queued. Set " + "; ".join(bad) + "."), refs


def _cascade_hold(ctx: Context):
    w = world(ctx)
    rows = w.rows(LEDGER, REG_H, **REG)
    init = w.rows(LEDGER, REG_H, "initial", **REG)
    if not init:
        return
    refs = [R_INTAKE, R_REC1, R_HOLD]
    hits = [r for r in rows if _row_has(r, CASCADE["num"])]
    full = ("add one Invoice Register row: Invoice ID INV-027, Vendor ID V-000031, Vendor Name Cascade Cleaning Co, "
            "Invoice Number CC-2026-0168, Invoice Date 2026-04-01, Received Date 2026-04-02, Due Date 2026-05-01, "
            "Invoice Amt 2200, Tax Amt 0, Payment Terms Net 30, GL Code 6500-001-xxxx, Category Recurring Invoice, "
            "Status ON HOLD, Hold Code APPR, Hold Reason \"Recurring agreement RA-2026-001 expired 2026-03-31 - "
            "renewal requested from Approving Manager\", Match Status RECURRING, Credit Applied 0")
    if not hits:
        yield False, ("Cascade Cleaning invoice CC-2026-0168 (unread email, $2,200.00) is not in the Invoice Register. "
                      "Its recurring agreement RA-2026-001 expired 2026-03-31, so it must not be processed but placed on "
                      f"APPR hold: {full}. Do not queue it for payment."), refs
        return
    if len(hits) > 1:
        yield False, f"CC-2026-0168 is entered {len(hits)} times in the Invoice Register - keep exactly one row.", \
            refs + [R_DUPL]
    r = hits[0]
    bad = []
    if norm(w.col(r, r"^Vendor ID$")) != norm(CASCADE["vid"]):
        bad.append("Vendor ID V-000031")
    if not _num_ok(w.col(r, r"^Invoice Amt"), CASCADE["amt"]):
        bad.append("Invoice Amt 2200")
    hold, status = w.col(r, r"^Hold Code$"), w.col(r, r"^Status$")
    if norm(hold) != "appr" and not re.search(r"\bAPPR\b", status, re.I):
        bad.append(f"Hold Code APPR (got \"{hold}\")")
    if not re.search(r"hold|appr", status, re.I):
        bad.append(f"Status ON HOLD (got \"{status}\")")
    yield not bad, ("CC-2026-0168 (RA-2026-001 expired 2026-03-31) must sit on APPR hold in the Invoice Register; set "
                    + "; ".join(bad) + "."), refs


REG_KEYS = (r"^Vendor ID$", r"^Invoice Number$", r"^Invoice Amt", r"^Status$", r"^Hold Code$", r"^Credit Applied")


def _register_scope(ctx: Context):
    w = world(ctx)
    init = w.rows(LEDGER, REG_H, "initial", **REG)
    cur = w.rows(LEDGER, REG_H, **REG)
    if not init or not cur:
        return
    refs = [R_AUDIT, R_HOLD, R_NOHOLD]
    by_id = {}
    for r in cur:
        by_id.setdefault(norm(w.col(r, r"^Invoice ID$")), r)
    for r in init:
        iid = w.col(r, r"^Invoice ID$")
        if iid in PENDING:
            continue
        now = by_id.get(norm(iid))
        if now is None:
            yield False, f"Invoice Register row {iid} ({w.col(r, r'^Invoice Number$')}) was removed - restore it.", refs
            continue
        diff = [f"{k.strip('^$')}: \"{w.col(r, k)}\" -> \"{w.col(now, k)}\"" for k in REG_KEYS
                if not same(w.col(now, k), w.col(r, k) or None)]
        yield not diff, (f"Invoice Register row {iid} is not one of the pending invoices of this task but was changed "
                         f"({'; '.join(diff)}). Restore the original values."), refs
    init_ids = {norm(w.col(r, r"^Invoice ID$")) for r in init}
    for r in cur:
        if norm(w.col(r, r"^Invoice ID$")) in init_ids or _row_has(r, CASCADE["num"]):
            continue
        yield False, (f"New Invoice Register row {w.col(r, r'^Invoice ID$')} / {w.col(r, r'^Invoice Number$')} does not "
                      "correspond to any invoice received in this task (only CC-2026-0168 is new). Remove it."), \
            [R_INTAKE, R_DUPL]


# ---- end state: match log -------------------------------------------------------------------------------

ML_H = r"^Match ID$"


def _match_rows(w) -> list[dict]:
    out = []
    for path in _books(w, MLOG_Q2):
        out += _rows_in(w, path, ML_H)
    return out


def _match_log(ctx: Context):
    w = world(ctx)
    if not _books(w, MLOG_Q2) and not w.books(MLOG_Q2, "initial"):
        return
    rows = _match_rows(w)
    for key, p in PENDING.items():
        if p["cat"] != "PO":
            continue
        refs = [R_MATCH, R_TOL_PRICE, R_TOL_QTY, R_TOL_TOTAL]
        total = p["unit"] * p["qty"]
        expect = (f"Invoice ID {key}, PO Number {p['po']}, Vendor ID {p['vid']}, Vendor Name {p['vname']}, Invoice Date "
                  f"{p['date']}, Match Date {TODAY}, PO Unit Price {p['unit']:g}, Invoice Unit Price {p['unit']:g}, "
                  f"Price Variance 0, Price Variance % 0, PO Qty {p['qty']}, GR Qty {p['qty']}, Invoice Qty {p['qty']}, "
                  f"Qty Variance 0, PO Total {total:g}, Invoice Total {p['amt']:g}, Total Variance 0, Total Variance % 0, "
                  "Match Result MATCH-PASS, Hold Placed No, Exception ID N/A")
        hits = [r for r in rows if any(_row_has(r, t) for t in _ids(key))]
        if not hits:
            yield False, (f"No match attempt for PO invoice {key} ({p['num']}) in match_log_2026_Q2.xlsx (current "
                          f"quarter). Append a row: Match ID ML-2026-Q2-NNN (next number), {expect}."), refs
            continue
        r = hits[-1]
        checks = [(r"^PO Number$", p["po"], "text"), (r"^PO Unit Price", p["unit"], "n"),
                  (r"^Invoice Unit Price", p["unit"], "n"), (r"^PO Qty$", p["qty"], "n"), (r"^GR Qty$", p["qty"], "n"),
                  (r"^Invoice Qty$", p["qty"], "n"), (r"^PO Total", total, "n"), (r"^Invoice Total", p["amt"], "n")]
        bad = []
        for col, want, kind in checks:
            got = w.col(r, col)
            ok = norm(got) == norm(want) if kind == "text" else _num_ok(got, want)
            if not ok:
                bad.append(f"{col.strip('^$')} {want if kind == 'text' else format(want, 'g')} (got \"{got}\")")
        res = w.col(r, r"^Match Result$")
        if "pass" not in norm(res):
            bad.append(f"Match Result MATCH-PASS (got \"{res}\")")
        md = w.col(r, r"^Match Date$")
        if not _date_ok(md, TODAY):
            bad.append(f"Match Date {TODAY} (got \"{md}\")")
        hp = w.col(r, r"^Hold Placed$")
        if not blank(hp) and norm(hp) not in ("no", "n"):
            bad.append(f"Hold Placed No (got \"{hp}\")")
        yield not bad, f"Match log row for {key} ({p['num']}) has wrong values - set " + "; ".join(bad) + ".", refs


def _match_scope(ctx: Context):
    w = world(ctx)
    refs = [R_MATCH]
    q1 = w.rows(MLOG_Q1, ML_H, "initial")
    if q1:
        added = w.new_rows(MLOG_Q1, ML_H)
        yield not added, (f"{len(added)} row(s) were added to or edited in match_log_2026_Q1.xlsx. Match attempts made "
                          f"today ({TODAY}) belong in the current-quarter log match_log_2026_Q2.xlsx; leave the Q1 log "
                          "unchanged."), refs
    allowed = {t for k, p in PENDING.items() if p["cat"] in ("PO", "REC") for t in _ids(k)} | {CASCADE["num"]}
    npo = {t: k for k, p in PENDING.items() if p["cat"] == "NPO" for t in _ids(k)}
    for r in _match_rows(w):
        if any(_row_has(r, t) for t in allowed):
            continue
        hit = next((k for t, k in npo.items() if _row_has(r, t)), None)
        label = w.col(r, r"^Match ID$") or w.col(r, r"^Invoice ID$")
        why = (f"{hit} is a non-PO invoice (approved under §5.3, no three-way match)" if hit else
               "it does not belong to an invoice matched in this task")
        yield False, f"Match log row {label} should not be there: {why}. Remove it.", refs + [R_CL_NPO]


# ---- end state: Payment Queue --------------------------------------------------------------------------

PQ = dict(sheet_rx=r"^Payment Queue$")
PQ_H = r"^Payment ID$"


def _pq_key(w, r: dict) -> str | None:
    for key, p in PENDING.items():
        if norm(w.col(r, r"^Invoice ID$")) == norm(key) or norm(w.col(r, r"^Invoice Number$")) == norm(p["num"]):
            return key
    return None


def _payment_queue(ctx: Context):
    w = world(ctx)
    rows = w.rows(LEDGER, PQ_H, **PQ)
    if not w.rows(LEDGER, PQ_H, "initial", **PQ):
        return
    for key, p in PENDING.items():
        who, tref = _tier(p["amt"])
        refs = [R_QUEUE, tref, R_ACH]
        hits = [r for r in rows if _pq_key(w, r) == key]
        expect = (f"Payment ID PMT-00NN (next number), Invoice ID {key}, Vendor ID {p['vid']}, Vendor Name {p['vname']}, "
                  f"Invoice Number {p['num']}, Invoice Amt {p['amt']:g}, Payment Amt {p['amt']:g}, Payment Terms "
                  f"{p['terms']}, Invoice Date {p['date']}, Due Date {p['due']}, Payment Method ACH, Batch ID/Batch Date "
                  f"blank (next batch is set by the AP Manager), Status PENDING, Auth Level per §7.1 ({who})")
        if not hits:
            yield False, f"Approved invoice {key} ({p['vname']} {p['num']}) is not queued. Add a Payment Queue row: " \
                         f"{expect}.", refs
            continue
        if len(hits) > 1:
            yield False, f"{key} is queued {len(hits)} times in the Payment Queue - keep exactly one row.", refs
        r = hits[0]
        bad = []
        if norm(w.col(r, r"^Vendor ID$")) != norm(p["vid"]):
            bad.append(f"Vendor ID {p['vid']}")
        for col in (r"^Invoice Amt", r"^Payment Amt"):
            if not _num_ok(w.col(r, col), p["amt"]):
                bad.append(f"{col.strip('^')} {p['amt']:g} (got \"{w.col(r, col)}\")")
        meth = w.col(r, r"^Payment Method$")
        if norm(meth) != "ach":
            bad.append(f"Payment Method ACH - {p['vname']} has bank details on file (got \"{meth}\")")
        st = w.col(r, r"^Status$")
        if norm(st) in ("paid", "cleared", "sent", "processed"):
            bad.append(f"Status PENDING - nothing has been paid yet (got \"{st}\")")
        yield not bad, f"Payment Queue row for {key} ({p['num']}): set " + "; ".join(bad) + ".", refs


PQ_KEYS = (r"^Invoice ID$", r"^Payment Amt", r"^Status$")


def _queue_scope(ctx: Context):
    w = world(ctx)
    init = w.rows(LEDGER, PQ_H, "initial", **PQ)
    cur = w.rows(LEDGER, PQ_H, **PQ)
    if not init or not cur:
        return
    by_pid: dict[str, list[dict]] = {}
    for r in cur:
        by_pid.setdefault(norm(w.col(r, r"^Payment ID$")), []).append(r)
    init_pids = set()
    for r in init:
        pid = w.col(r, r"^Payment ID$")
        init_pids.add(norm(pid))
        now = (by_pid.get(norm(pid)) or [None])[0]
        if now is None:
            yield False, f"Payment Queue row {pid} was removed - restore it.", [R_AUDIT, R_BATCH]
            continue
        diff = [f"{k.strip('^$')}: \"{w.col(r, k)}\" -> \"{w.col(now, k)}\"" for k in PQ_KEYS
                if not same(w.col(now, k), w.col(r, k) or None)]
        yield not diff, (f"Existing Payment Queue row {pid} was changed ({'; '.join(diff)}); batch runs and payment "
                         "status are the AP Manager's. Restore it."), [R_AUDIT, R_BATCH]
    for r in cur:
        pid = norm(w.col(r, r"^Payment ID$"))
        if pid in init_pids and len(by_pid.get(pid, [])) == 1:
            continue
        if _pq_key(w, r):
            continue
        txt = " ".join(str(v) for k, v in r.items() if k != "__row__")
        label = f"{w.col(r, r'^Payment ID$')} ({w.col(r, r'^Invoice ID$')} {w.col(r, r'^Invoice Number$')})"
        if _mentions(txt, CASCADE["num"]):
            yield False, (f"Payment Queue row {label} queues CC-2026-0168, whose recurring agreement RA-2026-001 expired "
                          "2026-03-31: it must stay on APPR hold and not be paid. Remove the row."), [R_REC1, R_NOHOLD]
        else:
            yield False, (f"Payment Queue row {label} is not one of the nine pending invoices brought current in this "
                          "task (held, intercompany, paid or already-queued invoices must not be queued). Remove it."), \
                [R_NOHOLD, R_NOIC, R_QUEUE]


# ---- end state: other records ----------------------------------------------------------------------------

def _vendor_bank(ctx: Context):
    w = world(ctx)
    init = w.rows(VMASTER, r"^Vendor ID$", "initial", r"^Vendor Master$")
    cur = {norm(w.col(r, r"^Vendor ID$")): r for r in w.rows(VMASTER, r"^Vendor ID$", "current", r"^Vendor Master$")}
    for r in init:
        vid = w.col(r, r"^Vendor ID$")
        now = cur.get(norm(vid))
        if now is None:
            continue
        diff = [k.strip("^$") for k in (r"^Bank Name$", r"^Bank Routing$", r"^Bank Account$", r"^Bank Verified Date$")
                if not same(w.col(now, k), w.col(r, k) or None)]
        yield not diff, (f"Bank details of {vid} ({w.col(r, r'^Vendor Name$')}) were changed in vendor_master.xlsx "
                         f"({', '.join(diff)}). The AP Clerk may never update bank details - restore the original "
                         "values."), [R_BANK1, R_BANK5]


def _recurring(ctx: Context):
    w = world(ctx)
    r0 = w.find(RECUR, r"^Agreement ID$", r"^Agreement ID$", "RA-2026-001", "initial")
    if r0 is None:
        return
    r1 = w.find(RECUR, r"^Agreement ID$", r"^Agreement ID$", "RA-2026-001")
    if r1 is None:
        yield False, "Recurring agreement RA-2026-001 was removed from recurring_agreements.xlsx - restore it.", \
            [R_REC1, R_EXP_B3]
        return
    diff = [k.strip("^$") for k in (r"^Expected Amount", r"^Agreement Expiration Date$", r"^Auto-Renew$", r"^Status$")
            if not same(w.col(r1, k), w.col(r0, k) or None)]
    yield not diff, (f"RA-2026-001 was changed in recurring_agreements.xlsx ({', '.join(diff)}). It stays Expired "
                     "(2026-03-31) until the Approving Manager replies RENEWED with a new expiration date - restore it."), \
        [R_REC1, R_EXP_B3]


ALLOWED_NEW_BOOK = re.compile(r"^(PO_Matching/match_log_\d{4}_Q[1-4]|Exceptions/exceptions_tracker_\d{4}|"
                              r"Vendor_Master/vendor_master)\.xlsx$")


def _files(ctx: Context):
    w = world(ctx)
    for b in w.created_books():
        yield bool(ALLOWED_NEW_BOOK.match(b)), (f"New spreadsheet {b} is an ad hoc file outside the SOP's designated "
                                                "files (and batch files are the AP Manager's). Delete it and keep the "
                                                "records in the existing workbooks."), [R_ADHOC, R_FILES, R_BATCH]
    for f in w.files():
        if not f.replace("\\", "/").startswith("Invoices/"):
            continue
        ok = re.fullmatch(r"Invoices/\d{4}-\d{2}/INV-(?:V|IC)-\d{6}-[A-Za-z0-9-]+\.pdf", f) is not None
        yield ok, (f"{f} does not follow the invoice image naming Invoices/YYYY-MM/INV-[VendorID]-[InvoiceNumber].pdf "
                   "(e.g. Invoices/2026-04/INV-V-000031-CC-2026-0168.pdf)."), [R_INVDIR]


RULES = (
    comm_rules("comms", _specs)
    + no_placeholders([R_APX_A, R_SA_FMT])
    + pre_rule("slack.tag_routing", _tag_problem, [R_SLACK, R_CH_EXC, R_CH_APPR, R_CH_ESC, R_CH_PAY, R_CH_ME,
                                                   R_ESC, R_ESC_FMT, R_BATCH],
               "Post the SOP message in its channel, in the exact format.")
    + pre_rule("slack.no_dm_audit", _dm_problem, [R_SLACK], "Use the SOP Slack channel instead of a DM.")
    + pre_rule("email.no_escalation_email", _email_esc_problem, [R_ESC], "Post the escalation in Slack instead.")
    + state_rule("state.register_pending", _register_pending, "Update the Invoice Register row as listed.")
    + state_rule("state.cascade_hold", _cascade_hold, "Enter CC-2026-0168 on APPR hold as listed.")
    + state_rule("state.register_scope", _register_scope, "Restore / remove the listed Invoice Register rows.")
    + state_rule("state.match_log", _match_log, "Record the match attempt in match_log_2026_Q2.xlsx as listed.")
    + state_rule("log.match_scope", _match_scope, "Fix the match logs as listed.")
    + state_rule("state.payment_queue", _payment_queue, "Queue the invoice in the Payment Queue as listed.")
    + state_rule("state.queue_scope", _queue_scope, "Restore / remove the listed Payment Queue rows.")
    + append_only("log.gl_append_only", LEDGER, r"^Entry ID$", "GL Postings", [R_AUDIT], sheet_rx=r"^GL Postings$")
    + state_rule("state.vendor_bank", _vendor_bank, "Restore the vendor bank details.")
    + state_rule("state.recurring_agreement", _recurring, "Restore RA-2026-001.")
    + state_rule("files.designated", _files, "Fix the files as listed.")
)
