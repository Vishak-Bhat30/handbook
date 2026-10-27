"""Meridian Partners AP (SOP-FIN-AP-004) - process the five unread emails of 2025-09-16.

Unread mail, oldest first (SOP 4): #63 Cascade credit memo CM-38720 ($2,000.00 > INV-38720 $1,950.00 -> 8.1 Step 2),
#61 Pinnacle bank change from a non-matching address (13.2 Step 4, BEC), #64 Apex INV-2025-09745 and #65 Redwood
RF-8125 (second partial invoices on PO-2025-00123 / PO-2025-00124 -> 6.2 partial, self-approve <= $2,500, 7.1),
#62 SecureNet legal threat on SNC-2025-001, which is on AUDIT hold (16.2, 13.1).
"""

from __future__ import annotations

import dataclasses
import re

from ..kit import (COMM_KINDS, WRITE_KINDS, Comm, Context, World, cites, comm_rules, dashes, no_placeholders, nh,
                   norm, pre_rule, prior_denials, same, state_rule, strict_writes, text_of, world)

TODAY = "2025-09-16"
LEDGER, MATCH, EXC, VM = (r"(^|/)ap_ledger\.xlsx$", r"(^|/)match_log_2025_Q3\.xlsx$",
                          r"(^|/)exceptions_tracker_2025\.xlsx$", r"(^|/)vendor_master\.xlsx$")
SNC, SNC_PO = "SNC-2025-001", "PO-2025-00120"

# ---- SOP references -------------------------------------------------------------------------------
R_ORDER = ("4", "When multiple invoices are awaiting processing", "4 (oldest first)")
R_PO_CLASS = ("4.3", "PO Invoice | Invoice references a valid PO", "4.3 PO Invoice")
R_3WAY = ("5.1", "For every PO invoice, the AP clerk must verify", "5.1 Three-Way Match")
R_DUP_NEVER = ("5.2", "Two invoices with different invoice numbers", "5.2")
R_REQ_FIELDS = ("4.1", "Before processing, verify the invoice contains", "4.1 Required Invoice Fields")
R_PARTIAL = ("6.2", "If Invoice Qty < GR Qty: This is a partial invoice", "6.2 partial invoice")
R_QUEUE = ("7", "After an invoice has been matched", "7")
R_SELF = ("7.1", "$0.01 – $2,500 | AP Clerk", "7.1 Authorization Matrix")
R_APPR_FMT = ("7.1", "INVOICE APPROVED: [VENDOR NAME]", "7.1 Slack format")
R_CH_APPR = ("3.2", "#approvals | Approval requests", "3.2 Slack channels")
R_CH_VM = ("3.2", "#vendor-management | Escalations to Controller", "3.2 Slack channels")
R_NO_DM = ("3.2", "Use the following Slack channels for all AP communications", "3.2")
R_CM = ("8", "Credit memos reduce the amount owed", "8")
R_CM2 = ("8.1", "Step 2: Verify the credit amount does not exceed", "8.1 Step 2")
R_DATES = ("2.1", "Dates: YYYY-MM-DD", "2.1 Data Entry Standards")
R_IDS = ("2.1", "Sequential IDs", "2.1 Data Entry Standards")
R_RESULT = ("2.1", "Match Log — Result: Pass or Flag", "2.1 allowed values")
R_CAT = ("2.1", "Invoice Register — Category:", "2.1 allowed values")
R_NAMES = ("2.1", "Name fields (Entered By", "2.1 name fields")
R_NOTES = ("2.1", "Notes fields: Leave blank unless", "2.1 Notes fields")
R_ADHOC = ("3", "All AP staff must use the following systems", "3")
R_ESC = ("13", "Escalations must be posted to the correct Slack channel", "13")
R_FRAUD = ("13.1", "Suspected fraud (fake invoice", "13.1 Escalation routing")
R_LEGAL = ("13.1", "Vendor legal threat or lawsuit", "13.1 Escalation routing")
R_BANKREQ = ("13.1", "Vendor requests payment method change", "13.1 Escalation routing")
R_LEGAL_FMT = ("13.1.1", "Legal threat / lawsuit notice:", "13.1.1 Escalation formats")
R_BANK = ("13.2", "This is the highest risk fraud scenario", "13.2")
R_BANK1 = ("13.2", "Step 1: Do NOT update vendor_master.xlsx", "13.2 Step 1")
R_BANK2 = ("13.2", "Step 2: Post to #vendor-management: BANK CHANGE REQUEST", "13.2 Step 2")
R_BANK3 = ("13.2", "Step 3: Verify that the sender", "13.2 Step 3")
R_BANK4 = ("13.2", "Step 4: If the email address does not match", "13.2 Step 4")
R_BANK5 = ("13.2", "Step 5: If the email address matches", "13.2 Step 5")
R_AUD = ("16.2", "If Internal Audit or the Controller places", "16.2 Audit Hold")
R_AUD_PAY = ("16.2", "Do NOT process payment under any circumstances", "16.2 Audit Hold")
R_AUD_CONTACT = ("16.2", "Do NOT contact the vendor about the hold", "16.2 Audit Hold")
R_AUD_MOD = ("16.2", "Do NOT modify any records related to the invoice", "16.2 Audit Hold")
R_AUD_DIRECT = ("16.2", "Direct all inquiries about the invoice to the Controller", "16.2 Audit Hold")
R_AUD_RELEASE = ("16.2", "Only the Controller or CFO may release an AUDIT hold", "16.2 Audit Hold")
R_BATCH_ID = ("15.1", "Payment Queue Batch ID format", "15.1")
R_ACH = ("15.3", "ACH | Default for all domestic vendors", "15.3 Payment Method Rules")
R_HOLD = ("15.2", "No invoices in the batch have an active hold status", "15.2 Pre-Batch Checklist")


# ---- helpers ------------------------------------------------------------------------------------

def dstr(v) -> str:
    s = nh(v)
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})(?:[ T]00:00(?::00)?)?", s)
    return m.group(1) if m else s


def ir(w: World, which="current"):
    return w.rows(LEDGER, r"^Inv Reg ID$", which, "Invoice Register")


def po(w: World, which="current"):
    return w.rows(LEDGER, r"^PO Number$", which, "PO Register")


def pq(w: World, which="current"):
    return w.rows(LEDGER, r"^Payment ID$", which, "Payment Queue")


def gl(w: World, which="current"):
    return w.rows(LEDGER, r"^Posting ID$", which, "GL Postings")


def ml(w: World, which="current"):
    return w.rows(MATCH, r"^Match ID$", which)


def ex(w: World, which="current"):
    return w.rows(EXC, r"^Exception ID$", which)


def vm(w: World, which="current"):
    return w.rows(VM, r"^Vendor ID$", which)


def c(row: dict, name: str) -> str:
    return World.col(row, rf"^{re.escape(name)}$")


def strip(row: dict) -> tuple:
    return tuple(v for k, v in row.items() if k != "__row__")


def by(rows, col: str, value: str) -> list[dict]:
    return [r for r in rows if norm(c(r, col)) == norm(value)]


def check_fields(row: dict, want: dict, dates=()) -> list[str]:
    bad = []
    for k, v in want.items():
        got = c(row, k)
        ok = dstr(got) == v if k in dates else same(got, v)
        if not ok:
            bad.append(f"{k} must be {v} (got \"{got}\")")
    return bad


# ---- expected end state (derived from the seed workbooks, invoices and SOP) ---------------------

IR_COLS = ["Vendor ID", "Vendor Name", "Invoice Date", "PO Number", "Category", "Amount", "GL Code", "Status",
           "Payment Terms", "Due Date", "Entered By", "Entered Date", "Approved By", "Approved Date"]
IR_DATES = ("Invoice Date", "Due Date", "Entered Date", "Approved Date")
NEW_IR = {
    "INV-2025-09745": dict(zip(IR_COLS, ["V-00001", "Apex Office Supply", "2025-09-12", "PO-2025-00123", "PO", 742.5,
                                         "1000-100-6200", "Approved", "Net 30", "2025-10-12", "T. Okonkwo", TODAY,
                                         "T. Okonkwo", TODAY])),
    "RF-8125": dict(zip(IR_COLS, ["V-00021", "Redwood Furniture Co", "2025-09-11", "PO-2025-00124", "PO", 1900.0,
                                  "1000-100-6500", "Approved", "Net 45", "2025-10-26", "T. Okonkwo", TODAY,
                                  "T. Okonkwo", TODAY])),
}
ML_COLS = ["Match Date", "PO Number", "Vendor ID", "Vendor Name", "PO Unit Price", "Invoice Unit Price",
           "Unit Price Variance %", "PO Qty", "Invoice Qty", "GR Qty", "PO Total", "Invoice Total", "Result"]
NEW_ML = {
    "INV-2025-09745": (dict(zip(ML_COLS, [TODAY, "PO-2025-00123", "V-00001", "Apex Office Supply", 4.95, 4.95, 0, 300,
                                          150, 300, 1485, 742.5, "Pass"])), 300, 150),
    "RF-8125": (dict(zip(ML_COLS, [TODAY, "PO-2025-00124", "V-00021", "Redwood Furniture Co", 380, 380, 0, 10, 5, 10,
                                   3800, 1900, "Pass"])), 10, 5),
}
CM_NOTE = "Placed on DISP-HOLD on 09/16/2025 — CM-38720.pdf"
CM_NOTE_RX = r"Placed on DISP-HOLD on 09/16/2025 ?[—–-] ?CM-38720\.pdf"
CATEGORIES = {"po", "non-po", "recurring", "intercompany", "credit memo", "employee expense"}


# ---- messages ---------------------------------------------------------------------------------------

# Senders of the unread emails (seed mailbox), so replies without an explicit "to" resolve to the vendor.
SENDERS = {"61": "bmatthews@pinnacleprintsvc.com", "62": "billing@securenetcompliance.com",
           "63": "ar@cascadeit.com", "64": "invoices@apexoffice.com", "65": "billing@redwoodfurniture.com"}


def _mail(a) -> bool:
    return a.kind in ("email_send", "email_draft")


def _src_id(a) -> str:
    return str(a.args.get("email_id") or a.args.get("message_id") or a.args.get("reply_to_email_id") or "")


def _with_reply_to(a):
    """The action with the original sender added as recipient when it is a reply to a seed email."""
    if "reply" not in a.tool or _src_id(a) not in SENDERS:
        return a
    s = SENDERS[_src_id(a)]
    return a if s in a.recipients else dataclasses.replace(a, recipients=list(a.recipients) + [s])


def _to(a, rx: str) -> bool:
    a = _with_reply_to(a)
    return any(re.search(rx, x, re.I) for x in a.recipients + a.cc)


class RComm(Comm):
    """Comm whose recipient checks treat a reply to a seed email as addressed to that email's sender."""

    def problems(self, a, w):
        return super().problems(_with_reply_to(a), w)


def _slack(a) -> bool:
    return a.kind in ("slack_post", "slack_dm")


def _email_rx(addr: str) -> str:
    e = re.escape(addr)
    return rf"(?:<mailto:{e}\|)?{e}>?"


CM_BODY = [
    (r"Dear Brian Choi\b", "greeting \"Dear Brian Choi,\" (Cascade contact in vendor_master.xlsx)"),
    (r"We received credit memo CM-38720 dated (?:September 11, 2025|2025-09-11|09/11/2025) for \$2,000\.00\.",
     "\"We received credit memo CM-38720 dated September 11, 2025 for $2,000.00.\""),
    (r"This amount exceeds the original invoice INV-38720 totaling \$1,950\.00\.",
     "\"This amount exceeds the original invoice INV-38720 totaling $1,950.00.\""),
    (r"We are unable to apply this credit until clarification is received\.",
     "\"We are unable to apply this credit until clarification is received.\""),
    (r"Please provide a corrected credit memo or written explanation\.",
     "\"Please provide a corrected credit memo or written explanation.\""),
    (r"Meridian Partners Accounts Payable", "sign-off \"Meridian Partners Accounts Payable\""),
]
BANK_TXT = "BANK CHANGE REQUEST: Pinnacle Print Services, V-00003, Requested by Brian Matthews, " \
           "Email bmatthews@pinnacleprintsvc.com"
BEC_TXT = "POTENTIAL BEC FRAUD: Pinnacle Print Services, V-00003, Sender email bmatthews@pinnacleprintsvc.com, " \
          "on-file email bmatthews@pinnacleprint.com"
LEGAL_TXT = "LEGAL THREAT: SecureNet Compliance, V-00011, Invoice SNC-2025-001"
APEX_TXT = "INVOICE APPROVED: Apex Office Supply, V-00001, Invoice INV-2025-09745, Amount $742.50, PO-2025-00123"
RF_TXT = "INVOICE APPROVED: Redwood Furniture Co, V-00021, Invoice RF-8125, Amount $1,900.00, PO-2025-00124"
CASE_RX = r"SNC-2025-001|SecureNet|Pinnacle|CM-38720|INV-38720|INV-2025-09745|RF-8125|BEC|bank change"


def specs(ctx: Context | None = None) -> list[Comm]:
    return [
        RComm("cm_clarify", "email",
             lambda a: _mail(a) and _to(a, r"cascadeit\.com") and bool(re.search(r"CM-38720|credit memo", text_of(a), re.I)),
             "credit memo CM-38720 exceeds INV-38720 - clarification email to Cascade IT Hardware",
             [R_CM2], to=["ar@cascadeit.com"], body=CM_BODY, exact_to=False),
        Comm("bank_change", "slack_post", lambda a: _slack(a) and bool(re.search(r"BANK CHANGE", a.text, re.I)),
             "BANK CHANGE REQUEST post for the Pinnacle Print Services bank change email", [R_BANK2, R_BANKREQ],
             channel="vendor-management",
             exact=r"BANK CHANGE REQUEST: Pinnacle Print Services, V-00003, Requested by Brian Matthews, Email "
                   + _email_rx("bmatthews@pinnacleprintsvc.com") + r"\.?", exact_hint=BANK_TXT),
        Comm("bec", "slack_post",
             lambda a: _slack(a) and bool(re.search(r"\bBEC\b|POTENTIAL .*FRAUD", a.text, re.I)),
             "POTENTIAL BEC FRAUD post (sender address does not match the on-file contact email)",
             [R_BANK3, R_BANK4, R_FRAUD], channel="vendor-management",
             exact=r"POTENTIAL BEC FRAUD: Pinnacle Print Services, V-00003, Sender email "
                   + _email_rx("bmatthews@pinnacleprintsvc.com") + r", on-file email "
                   + _email_rx("bmatthews@pinnacleprint.com") + r"\.?", exact_hint=BEC_TXT),
        Comm("apex_approved", "slack_post",
             lambda a: _slack(a) and bool(re.search(r"INVOICE APPROVED|APPROVAL REQUEST", a.text)
                                          and re.search(r"INV-2025-09745", a.text)),
             "self-approval confirmation for Apex INV-2025-09745 ($742.50, partial invoice on PO-2025-00123)",
             [R_SELF, R_APPR_FMT, R_CH_APPR], channel="approvals", exact=re.escape(APEX_TXT) + r"\.?",
             exact_hint=APEX_TXT),
        Comm("redwood_approved", "slack_post",
             lambda a: _slack(a) and bool(re.search(r"INVOICE APPROVED|APPROVAL REQUEST", a.text)
                                          and re.search(r"RF-8125", a.text)),
             "self-approval confirmation for Redwood RF-8125 ($1,900.00, partial invoice on PO-2025-00124)",
             [R_SELF, R_APPR_FMT, R_CH_APPR], channel="approvals", exact=re.escape(RF_TXT) + r"\.?",
             exact_hint=RF_TXT),
        Comm("legal_threat", "slack_post",
             lambda a: _slack(a) and bool(re.search(r"LEGAL THREAT", a.text, re.I)
                                          or (re.search(r"SNC-2025-001|SecureNet", a.text, re.I)
                                              and re.search(r"legal|lawsuit|attorney|counsel", a.text, re.I))),
             "LEGAL THREAT escalation for SecureNet Compliance (invoice SNC-2025-001 is on AUDIT hold)",
             [R_LEGAL, R_LEGAL_FMT, R_ESC, R_AUD_DIRECT], channel="vendor-management",
             exact=re.escape(LEGAL_TXT) + r"\.?", exact_hint=LEGAL_TXT),
        Comm("no_contact_securenet", "email", lambda a: _mail(a) and _to(a, r"securenet"),
             "email to SecureNet Compliance", [R_AUD_CONTACT, R_AUD_DIRECT],
             forbidden="SNC-2025-001 is on AUDIT hold: do NOT contact the vendor about the hold (even under legal "
                       "threat); the Controller handles it - post the LEGAL THREAT escalation in #vendor-management "
                       "instead."),
        Comm("no_reply_pinnacle", "email", lambda a: _mail(a) and _to(a, r"pinnacleprint"),
             "email to Pinnacle Print Services", [R_BANK4],
             forbidden="The bank change request came from bmatthews@pinnacleprintsvc.com, which does not match the "
                       "on-file email bmatthews@pinnacleprint.com: do NOT respond to the email; the Controller will "
                       "handle all further communication."),
        Comm("no_email_bank_change", "email",
             lambda a: _mail(a) and not _to(a, r"pinnacleprint") and (
                 ("forward" in a.tool and _src_id(a) == "61") or bool(
                     re.search(r"Pinnacle", text_of(a), re.I)
                     and re.search(r"bank|routing|BEC|SouthState|account number|fraud", text_of(a), re.I))),
             "email about the Pinnacle bank change request", [R_BANK4, R_BANK5, R_ESC],
             forbidden="The sender email does not match the on-file email, so the SOP stops at Step 4 (do not "
                       "forward to the AP Manager; the Controller handles all further communication) and "
                       "escalations go to Slack, not email. Post the BANK CHANGE REQUEST and POTENTIAL BEC FRAUD "
                       "lines in #vendor-management only."),
        Comm("no_duplicate_flag", "slack_post",
             lambda a: _slack(a) and bool(re.search(r"DUPLICATE", a.text, re.I)
                                          and re.search(r"INV-2025-09745|RF-8125", a.text, re.I)),
             "DUPLICATE notification for INV-2025-09745 / RF-8125", [R_DUP_NEVER],
             forbidden="INV-2025-09745 and RF-8125 have different invoice numbers from INV-2025-09510 / RF-8010, so "
                       "they are never duplicates: they are the second partial invoices on PO-2025-00123 / "
                       "PO-2025-00124 and are processed normally."),
        Comm("no_incomplete_return", "email",
             lambda a: _mail(a) and bool(re.search(r"Incomplete Invoice", text_of(a), re.I)
                                         and re.search(r"INV-2025-09745|RF-8125", text_of(a), re.I)),
             "Incomplete Invoice return for INV-2025-09745 / RF-8125", [R_REQ_FIELDS],
             forbidden="The attached invoice PDFs (INV-2025-09745.pdf, RF-8125.pdf) contain every required field "
                       "(vendor name and address, invoice number and date, PO, line item with qty and unit price, "
                       "total, terms): they are complete and must not be returned."),
        Comm("no_dm", "slack_dm",
             lambda a: (a.kind == "slack_dm" or (a.kind == "slack_post" and str(a.channel).startswith("D")))
             and bool(re.search(CASE_RX, a.text, re.I)),
             "direct message about an AP case", [R_NO_DM],
             forbidden="Do not use direct messages for issues that require an audit trail; post in the SOP channel "
                       "(#vendor-management / #approvals)."),
    ]


ORDER = [("cm_clarify", "the Cascade IT credit memo CM-38720 (email received 09/11 14:05): clarification email to "
                        "ar@cascadeit.com"),
         ("bank_change", "the Pinnacle bank change email (09/12 09:17): BANK CHANGE REQUEST post"),
         ("bec", "the Pinnacle bank change email (09/12 09:17): POTENTIAL BEC FRAUD post"),
         ("apex_approved", "Apex INV-2025-09745 (09/12 10:30): INVOICE APPROVED post"),
         ("redwood_approved", "Redwood RF-8125 (09/13 08:45): INVOICE APPROVED post"),
         ("legal_threat", "SecureNet SNC-2025-001 (09/15 11:42): LEGAL THREAT post")]


def order_problem(ctx: Context, a) -> str | None:
    if a.kind not in COMM_KINDS:
        return None
    w = world(ctx)
    sp = {s.key: s for s in specs(ctx)}
    idx = next((i for i, (k, _) in enumerate(ORDER) if sp[k].about(a)), None)
    if idx is None:
        return None
    sent = lambda s: any(s.about(x) and not s.problems(x, w) for x in w.comms())
    if sent(sp[ORDER[idx][0]]):
        return None
    todo = [d for k, d in ORDER[:idx] if not sent(sp[k])]
    tag = f"[order:{ORDER[idx][0]}]"
    if not todo or prior_denials(ctx, tag) >= 1:
        return None
    return (f"{tag} Unread emails are processed in order of receipt, oldest first. Finish the earlier item(s) "
            f"first: {'; '.join(todo)}.")


# ---- pre rules ---------------------------------------------------------------------------------

def bank_write_problem(ctx: Context, a) -> str | None:
    if a.kind not in WRITE_KINDS:
        return None
    writes_vm = any(re.search(r"vendor_master", f, re.I) for f in strict_writes(a)) or (
        a.kind == "workbook_write" and re.search(r"vendor_master", a.text or "", re.I))
    if writes_vm and re.search(r"053201814|7742-0085-1193|SouthState", a.text or a.code or "", re.I):
        return ("Do NOT update vendor_master.xlsx with the bank details from the Pinnacle email (SouthState Bank "
                "053201814 / 7742-0085-1193): the request came from a non-matching address (possible BEC fraud) and "
                "only the AP Manager may ever update bank details.")
    return None


# ---- completion rules --------------------------------------------------------------------------

def cm_checks(ctx: Context):
    w = world(ctx)
    rows = ir(w)
    cands = [r for r in rows if c(r, "Invoice Number").upper() in ("INV-38720", "CM-38720")]
    held = [r for r in cands if norm(c(r, "Status")) == "disp-hold"]
    noted = [r for r in held if re.fullmatch(CM_NOTE_RX, nh(c(r, "Notes")))]
    if not held:
        yield (False, "Credit memo CM-38720 ($2,000.00) exceeds the original invoice INV-38720 ($1,950.00) but nothing "
                      "is on DISP-HOLD in the Invoice Register. Set Status \"DISP-HOLD\" on the INV-38720 row "
                      f"(Inv Reg ID 1030) and write Notes \"{CM_NOTE}\" (or enter CM-38720 as a Credit Memo row "
                      "with that Status and Notes); do not apply the credit.", [R_CM2])
    elif not noted:
        yield (False, f"The DISP-HOLD row for CM-38720/INV-38720 must have Notes exactly \"{CM_NOTE}\" (got "
                      f"\"{c(held[0], 'Notes')}\").", [R_CM2, R_NOTES])
    orig = by(rows, "Invoice Number", "INV-38720")
    if orig and not same(c(orig[0], "Credit Applied") or 0, 0):
        yield (False, "Do not apply credit memo CM-38720 while it is on DISP-HOLD: Credit Applied on INV-38720 must "
                      f"stay 0 (got \"{c(orig[0], 'Credit Applied')}\").", [R_CM2])
    v = by(vm(w), "Vendor ID", "V-00020")
    if v and not same(c(v[0], "Outstanding Credit") or 0, 0):
        yield (False, "Do not record CM-38720 as Outstanding Credit for Cascade IT Hardware (V-00020) while it is on "
                      "DISP-HOLD; set it back to 0.", [R_CM2])
    paid = [r for r in pq(w) if c(r, "Invoice Number").upper() in ("INV-38720", "CM-38720")]
    if paid:
        yield (False, "INV-38720 / CM-38720 is on DISP-HOLD and must not be in the Payment Queue; remove the row.",
               [R_CM2, R_HOLD])


def ir_checks(ctx: Context):
    w = world(ctx)
    rows = ir(w)
    for inv, want in NEW_IR.items():
        hit = by(rows, "Invoice Number", inv)
        refs = [R_PO_CLASS, R_DUP_NEVER, R_PARTIAL, R_SELF, R_DATES, R_NAMES]
        if not hit:
            vals = ", ".join(f"{k}={v}" for k, v in want.items())
            yield (False, f"{inv} is not in the Invoice Register. It is a complete PO invoice (different invoice "
                          f"number, so not a duplicate) and a partial invoice that passes the match: add a row with "
                          f"Inv Reg ID = next number, Invoice Number={inv}, {vals}, Credit Applied=0, Notes blank.",
                   refs)
            continue
        if len(hit) > 1:
            yield (False, f"{inv} was entered {len(hit)} times in the Invoice Register; keep one row.", refs)
        bad = check_fields(hit[0], want, IR_DATES)
        if c(hit[0], "Credit Applied") not in ("", "0", "0.0"):
            bad.append(f"Credit Applied must be 0 (got \"{c(hit[0], 'Credit Applied')}\")")
        if c(hit[0], "Notes"):
            bad.append(f"Notes must be blank (got \"{c(hit[0], 'Notes')}\")")
        yield (not bad, f"Invoice Register row for {inv}: " + "; ".join(bad) + ".", refs + [R_NOTES])


def ml_checks(ctx: Context):
    w = world(ctx)
    rows = ml(w)
    for inv, (want, gr, q) in NEW_ML.items():
        hit = by(rows, "Invoice Number", inv)
        note = f"Partial invoice – {gr} units received, {q} units invoiced. Remaining units: [Z]"
        refs = [R_3WAY, R_PARTIAL, R_RESULT, R_DATES]
        if not hit:
            vals = ", ".join(f"{k}={v}" for k, v in want.items())
            yield (False, f"No match log row in match_log_2025_Q3.xlsx for {inv}. Record the match attempt: Match ID = "
                          f"next number, Invoice Number={inv}, {vals}, Notes \"{note}\" (Z = units still not "
                          f"invoiced).", refs)
            continue
        if len(hit) > 1:
            yield (False, f"{inv} has {len(hit)} match log rows; keep one.", refs)
        bad = check_fields(hit[0], want, ("Match Date",))
        if not re.fullmatch(rf"Partial invoice ?[-–—] ?{gr} units received, {q} units invoiced\. Remaining units: "
                            rf"\d+\.?", dashes(c(hit[0], "Notes"))):
            bad.append(f"Notes must be \"{note}\" (got \"{c(hit[0], 'Notes')}\")")
        yield (not bad, f"Match log row for {inv}: " + "; ".join(bad) + ".", refs)


def pq_checks(ctx: Context):
    w = world(ctx)
    rows = pq(w)
    for inv, want in NEW_IR.items():
        hit = by(rows, "Invoice Number", inv)
        refs = [R_QUEUE, R_SELF, R_BATCH_ID, R_ACH]
        exp = (f"Vendor ID={want['Vendor ID']}, Vendor Name={want['Vendor Name']}, Invoice Number={inv}, "
               f"Amount={want['Amount']:.2f}, Payment Method=ACH, Payment Date/Batch ID = next batch run "
               f"(2025-09-16 / BAT-2025-0916 or 2025-09-18 / BAT-2025-0918), Status=Pending")
        if not hit:
            yield (False, f"Approved invoice {inv} has not entered the Payment Queue. Add a Payment Queue row: Payment "
                          f"ID = next PAY number, {exp}.", refs)
            continue
        if len(hit) > 1:
            yield (False, f"{inv} is in the Payment Queue {len(hit)} times; keep one row.", refs)
        r = hit[0]
        bad = check_fields(r, {"Vendor ID": want["Vendor ID"], "Amount": want["Amount"], "Payment Method": "ACH",
                               "Status": "Pending"})
        m = re.fullmatch(r"BAT-2025-09(16|18)", nh(c(r, "Batch ID")))
        if not m:
            bad.append(f"Batch ID must be the next batch run, BAT-2025-0916 or BAT-2025-0918 (got \"{c(r, 'Batch ID')}\")")
        elif dstr(c(r, "Payment Date")) != f"2025-09-{m.group(1)}":
            bad.append(f"Payment Date must be the batch date 2025-09-{m.group(1)} (got \"{c(r, 'Payment Date')}\")")
        yield (not bad, f"Payment Queue row for {inv}: " + "; ".join(bad) + ".", refs + [R_DATES])


def _new_ids(rows_now, rows_init, col: str) -> list[str]:
    init = {nh(c(r, col)) for r in rows_init}
    return [nh(c(r, col)) for r in rows_now if nh(c(r, col)) not in init]


def _seq(new: list[str], start: int, rx: str, fmt) -> str | None:
    nums = []
    for x in new:
        m = re.fullmatch(rx, x)
        if not m:
            return f"\"{x}\" is not in the ID format (expected {fmt(start)})"
        nums.append(int(float(m.group(1))))
    if sorted(nums) != list(range(start, start + len(nums))):
        return f"got {', '.join(new)}; expected {', '.join(fmt(start + i) for i in range(len(new)))}"
    return None


def id_checks(ctx: Context):
    w = world(ctx)
    for what, now, init, col, start, rx, fmt in [
        ("Inv Reg ID", ir(w), ir(w, "initial"), "Inv Reg ID", 1046, r"(\d+)(?:\.0)?", str),
        ("Match ID", ml(w), ml(w, "initial"), "Match ID", 24, r"MTH-Q3-(\d{3})", lambda n: f"MTH-Q3-{n:03d}"),
        ("Payment ID", pq(w), pq(w, "initial"), "Payment ID", 29, r"PAY-(\d{4})", lambda n: f"PAY-{n:04d}"),
        ("Exception ID", ex(w), ex(w, "initial"), "Exception ID", 6, r"EXC-2025-(\d{3})", lambda n: f"EXC-2025-{n:03d}"),
    ]:
        new = _new_ids(now, init, col)
        if not new:
            continue
        prob = _seq(new, start, rx, fmt)
        yield (prob is None, f"New {what} values must increment the highest existing ID by 1: {prob}.", [R_IDS])
        # emails are processed oldest first: CM-38720 (09/11), INV-2025-09745 (09/12), RF-8125 (09/13)
        new_set = set(new)
        pos = {}
        for r in now:
            m = re.search(r"(\d+)(?:\.0)?$", nh(c(r, col)))
            inv = c(r, "Invoice Number").upper()
            if nh(c(r, col)) in new_set and m and inv in ("CM-38720", "INV-2025-09745", "RF-8125"):
                pos[inv] = int(m.group(1))
        seq = [pos[k] for k in ("CM-38720", "INV-2025-09745", "RF-8125") if k in pos]
        yield (seq == sorted(seq), f"New {what} values are out of email receipt order: process oldest first - "
                                   "CM-38720 (received 09/11), then INV-2025-09745 (09/12), then RF-8125 (09/13); "
                                   "number the new rows in that order.", [R_ORDER, R_IDS])


def _snc_related(r: dict) -> bool:
    return any(norm(v) in (norm(SNC), norm(SNC_PO)) for k, v in r.items() if k != "__row__")


def audit_checks(ctx: Context):
    w = world(ctx)
    refs = [R_AUD, R_AUD_MOD, R_AUD_RELEASE]
    for what, now, init in [("Invoice Register", ir(w), ir(w, "initial")), ("PO Register", po(w), po(w, "initial")),
                            ("match log", ml(w), ml(w, "initial")), ("exceptions tracker", ex(w), ex(w, "initial"))]:
        before = sorted(strip(r) for r in init if _snc_related(r))
        after = sorted(strip(r) for r in now if _snc_related(r))
        yield (before == after, f"SNC-2025-001 is on AUDIT hold: do NOT modify any records related to it - restore its "
                                f"{what} row(s) exactly as they were (only the Controller or CFO may release the "
                                f"hold).", refs)
    if any(_snc_related(r) for r in pq(w)):
        yield (False, "SNC-2025-001 is on AUDIT hold: do NOT process payment under any circumstances, even under legal "
                      "threat - remove it from the Payment Queue.", [R_AUD_PAY, R_HOLD])
    for name in w.created_books():
        if SNC in str((w.current or {}).get(name)):
            yield (False, f"{name} includes SNC-2025-001, which is on AUDIT hold; it must not be paid or batched.",
                   [R_AUD_PAY, R_HOLD])


def vm_checks(ctx: Context):
    w = world(ctx)
    gone = w.missing_rows(VM, r"^Vendor ID$")
    added = w.new_rows(VM, r"^Vendor ID$")
    v3 = [r for r in gone if c(r, "Vendor ID") == "V-00003"]
    if v3:
        yield (False, "Pinnacle Print Services (V-00003) must stay unchanged in vendor_master.xlsx: the bank change "
                      "request came from a non-matching address (BEC) - do NOT update any records. Restore the "
                      "original bank details (Truliant Federal Credit Union, 253175494, 0082-1147-3355).",
               [R_BANK1, R_BANK4, R_BANK5])
    other = [c(r, "Vendor ID") for r in gone if c(r, "Vendor ID") != "V-00003"]
    yield (not other and not added, "vendor_master.xlsx has unrequested changes (no vendor record needs updating "
                                    f"for these emails): restore {', '.join(other) or 'the original rows'}"
                                    f"{' and remove the added rows' if added else ''}.", [R_ADHOC])


ALLOWED_IR_NEW = {"INV-2025-09745", "RF-8125", "CM-38720"}
ALLOWED_PQ_NEW = {"INV-2025-09745", "RF-8125"}


def integrity_checks(ctx: Context):
    w = world(ctx)
    # Invoice Register: existing rows unchanged except INV-38720 Status/Notes (DISP-HOLD for CM-38720).
    init, now = ir(w, "initial"), ir(w)
    cur = {nh(c(r, "Inv Reg ID")): r for r in now}
    changed = []
    for r in init:
        if _snc_related(r):
            continue
        rid = nh(c(r, "Inv Reg ID"))
        n = cur.get(rid)
        if n is None:
            changed.append(f"{rid} ({c(r, 'Invoice Number')}) removed")
            continue
        skip = ("Status", "Notes") if c(r, "Invoice Number") == "INV-38720" else ()
        diff = [k for k in r if k not in ("__row__",) + skip and nh(r[k]) != nh(n.get(k, ""))]
        if diff:
            changed.append(f"{rid} ({c(r, 'Invoice Number')}): {', '.join(diff)}")
        if skip and norm(c(n, "Status")) not in ("entered", "disp-hold"):
            changed.append(f"{rid} (INV-38720): Status may only become DISP-HOLD")
    yield (not changed, "Existing Invoice Register rows were changed (only INV-38720 may change, to DISP-HOLD with the "
                        f"SOP note): {'; '.join(changed[:6])}. Restore them.", [R_CM2, R_ADHOC])
    new_ids = set(_new_ids(now, init, "Inv Reg ID"))
    extra = [c(r, "Invoice Number") for r in now if nh(c(r, "Inv Reg ID")) in new_ids
             and c(r, "Invoice Number").upper() not in ALLOWED_IR_NEW]
    yield (not extra, f"Unrequested Invoice Register rows {extra}: only the new invoices INV-2025-09745 and RF-8125 "
                      "(and optionally the credit memo CM-38720) come from the unread emails.", [R_ADHOC])
    badcat = [f"{c(r, 'Invoice Number')}={c(r, 'Category')}" for r in now if nh(c(r, "Inv Reg ID")) in new_ids
              and norm(c(r, "Category")) not in CATEGORIES]
    yield (not badcat, f"Category must be one of PO, Non-PO, Recurring, Intercompany, Credit Memo, Employee Expense "
                       f"(got {badcat}).", [R_CAT])
    # PO Register: unchanged except Status of the two now fully invoiced POs.
    poi, pon = po(w, "initial"), {nh(c(r, "PO Number")): r for r in po(w)}
    pchg = []
    for r in poi:
        if _snc_related(r):
            continue
        n = pon.get(nh(c(r, "PO Number")))
        skip = ("Status",) if c(r, "PO Number") in ("PO-2025-00123", "PO-2025-00124") else ()
        if n is None or any(nh(r[k]) != nh(n.get(k, "")) for k in r if k not in ("__row__",) + skip):
            pchg.append(c(r, "PO Number"))
    if len(po(w)) != len(poi):
        pchg.append("rows added/removed")
    yield (not pchg, f"PO Register rows changed ({', '.join(pchg)}): the PO and GR data are not to be edited for "
                     "these invoices (GR Qty is updated only by the requesting department). Restore them.", [R_ADHOC])
    # Append-only logs with only the SOP-required new rows.
    for what, init_rows, now_rows, idcol, allowed in [
        ("Payment Queue", pq(w, "initial"), pq(w), "Payment ID", ALLOWED_PQ_NEW),
        ("match log", ml(w, "initial"), ml(w), "Match ID", ALLOWED_PQ_NEW),
        ("exceptions tracker", ex(w, "initial"), ex(w), "Exception ID", {"INV-38720", "CM-38720"}),
        ("GL Postings", gl(w, "initial"), gl(w), "Posting ID", None),
    ]:
        left = [strip(r) for r in now_rows]
        lost = []
        for r in init_rows:
            if _snc_related(r):
                continue
            s = strip(r)
            if s in left:
                left.remove(s)
            else:
                lost.append(" | ".join(s[:5]))
        yield (not lost, f"The {what} is append-only: existing row(s) were edited or removed ({'; '.join(lost[:3])}). "
                         "Restore them.", [R_ADHOC])
        if allowed is not None:
            ids = {nh(c(r, idcol)) for r in init_rows}
            bad = [c(r, "Invoice Number") or c(r, idcol) for r in now_rows if nh(c(r, idcol)) not in ids
                   and c(r, "Invoice Number").upper() not in allowed and not _snc_related(r)]
            yield (not bad, f"Unrequested {what} rows for {bad}: the unread emails only add "
                            f"{', '.join(sorted(allowed))} here.", [R_ADHOC])
    # Other workbooks are not touched by these emails.
    other = w.changed_files(r"ap_ledger|match_log|exceptions_tracker|vendor_master")
    yield (not other, f"Unrequested changes to {', '.join(other)}: none of these files is updated for the unread "
                      "emails; restore them.", [R_ADHOC])
    adhoc = [b for b in w.created_books() if not re.search(r"(^|/)batch_\d{4}-\d{2}-\d{2}\.xlsx$", b)]
    yield (not adhoc, f"Do not create ad hoc spreadsheets ({', '.join(adhoc)}); record everything in the "
                      "designated AP workbooks and delete the new file(s).", [R_ADHOC])


RULES = (
    comm_rules("msg", specs)
    + no_placeholders([R_CM2, R_APPR_FMT])
    + pre_rule("order.oldest_first", order_problem, [R_ORDER], "Handle the earlier email first, then retry.")
    + pre_rule("bank.no_vendor_update", bank_write_problem, [R_BANK, R_BANK1, R_BANK4, R_BANK5],
               "Leave vendor_master.xlsx unchanged.")
    + state_rule("state.cm_disp_hold", cm_checks, "Fix the credit memo records as listed.")
    + state_rule("state.invoice_register", ir_checks, "Enter / correct the Invoice Register row as listed.")
    + state_rule("state.match_log", ml_checks, "Add / correct the match log row as listed.")
    + state_rule("state.payment_queue", pq_checks, "Add / correct the Payment Queue row as listed.")
    + state_rule("state.sequential_ids", id_checks, "Renumber the new rows as listed.")
    + state_rule("state.audit_hold", audit_checks, "Undo the change to the AUDIT-hold invoice.")
    + state_rule("state.vendor_master", vm_checks, "Restore vendor_master.xlsx.")
    + state_rule("state.integrity", integrity_checks, "Restore the records as listed.")
)
