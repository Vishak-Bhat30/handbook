"""Verifiers for finance_meridian_partners_19d57538 (three-way match of Northgate invoice INV-NGO-4471).

Facts (seed data): PO-2025-00884 (V-00229) is 20 x $97.50 = $1,950.00, GR 20. Invoice INV-NGO-4471 dated
2025-05-19, received 2025-05-21, 20 x $101.50 = $2,030.00, Net 30. Unit price variance +$4.00 / 4.10% is within
"±5% OR ±$25" -> Pass; total variance +$80.00 / 4.10% is outside "±$50 AND ±2%" -> Fail -> MATCH hold (5.1.1),
Section 6.1. No price increase / rate change email from northgateoffice.com in the inbox -> Step 2b (vendor email
with the exact subject) and Step 3 (#ap-exceptions PRICE VARIANCE post). No GL posting / payment while on hold.
"""

from __future__ import annotations

import datetime as dt
import re

from ..kit import (Comm, World, append_only, comm_rules, no_placeholders, norm, num, same, state_rule, world)

INV = "INV-NGO-4471"
VENDOR, VID = "Northgate Office Solutions", "V-00229"
PO = "PO-2025-00884"
VENDOR_EMAIL = "jlowe@northgateoffice.com"
LEDGER, MLOG, VMASTER = r"(^|/)ap_ledger\.xlsx$", r"(^|/)match_log_2025_Q2\.xlsx$", r"(^|/)vendor_master\.xlsx$"
RESULT_FILE = r"(^|/)match_result_INV-NGO-4471\.txt$"
SLACK_POST = ("PRICE VARIANCE: Northgate Office Solutions, V-00229, Invoice INV-NGO-4471, PO Price $97.50, "
              "Invoice Price $101.50, Variance 4.1%")
SUBJECT = "Meridian Partners - Price Discrepancy on Invoice INV-NGO-4471"

R_PURPOSE = ("1", "This document defines the end-to-end procedures", "1 Purpose & Scope")
R_NO_ADHOC = ("3", "All AP staff must use the following systems", "3 Tools, Systems & File Locations")
R_HOLD = ("2", "Hold Status |", "2 Hold Status")
R_TERMS = ("2", "Payment Terms |", "2 Payment Terms")
R_CLASS_PO = ("4.3", "PO Invoice |", "4.3 PO Invoice")
R_MATCHLOG = ("5.1", "For every PO invoice, the AP clerk", "5.1 Three-Way Match")
R_TOL_PRICE = ("5.1.1", "Unit Price Variance |", "5.1.1 Unit Price Variance")
R_TOL_QTY = ("5.1.1", "Quantity Variance |", "5.1.1 Quantity Variance")
R_TOL_TOTAL = ("5.1.1", "Total Invoice Amount |", "5.1.1 Total Invoice Amount")
R_DUP = ("5.2", "Before entering any invoice", "5.2 Duplicate Invoice Detection")
R_61 = ("6.1", "When unit price variance or total", "6.1 Price Variance Exceptions")
R_61_S1 = ("6.1", "Step 1: Check if the vendor", "6.1 Step 1")
R_61_2A = ("6.1", "Step 2a", "6.1 Step 2a")
R_61_2B = ("6.1", "Step 2b", "6.1 Step 2b")
R_61_S3 = ("6.1", "Step 3: Post to #ap-exceptions", "6.1 Step 3")
R_SLACK_NO_DM = ("3.3", "Use the following Slack channels", "3.3 Slack Channels")
R_CH_EXC = ("3.3", "#ap-exceptions |", "3.3 #ap-exceptions")
R_CH_APPR = ("3.3", "#ap-approvals |", "3.3 #ap-approvals")
R_7 = ("7", "After an invoice has been matched", "7 Payment Approval")
R_AUTH = ("7.1", "$0.01 – $2,500 |", "7.1 Payment Authorization Matrix")
R_BATCH_HOLD = ("15.2", "2. No invoices in the batch have an active hold", "15.2 Pre-Batch Checklist")
R_42_TPL = ("4.2", "When an invoice is missing required fields", "4.2 Returning Incomplete Invoices")


# ---- helpers -------------------------------------------------------------------------------------

def day(v) -> str:
    """ISO date of a cell ('2025-05-19', '2025-05-19 00:00:00', '05/19/2025'); else the normalised text."""
    s = str(v or "").strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return norm(s)


def cell_eq(a, b) -> bool:
    if same(a, b):
        return True
    return day(a) == day(b)


def get(row: dict, name: str) -> str:
    for k, v in row.items():
        if k != "__row__" and norm(k) == norm(name):
            return "" if str(v) in ("None", "nan") else str(v).strip()
    return ""


def row_eq(a: dict, b: dict) -> bool:
    keys = [k for k in a if k != "__row__"]
    return all(cell_eq(a.get(k, ""), b.get(k, "")) for k in keys) and \
        all(k in a for k in b if k != "__row__" and str(b[k]).strip() not in ("", "None"))


def diff_rows(w: World, book: str, header_rx: str, sheet_rx: str | None = None) -> tuple[list[dict], list[dict]]:
    """(initial rows no longer present, current rows that are not initial rows), cell-tolerant."""
    cur = list(w.rows(book, header_rx, "current", sheet_rx))
    gone = []
    for r in w.rows(book, header_rx, "initial", sheet_rx):
        hit = next((c for c in cur if row_eq(r, c)), None)
        if hit is None:
            gone.append(r)
        else:
            cur.remove(hit)
    return gone, cur


def mentions_inv(text: str) -> bool:
    return bool(re.search(r"INV[-\s]?NGO[-\s]?4471", text or "", re.I))


def pct_ok(v) -> bool:
    n = num(v)
    return n is not None and (abs(n - 4.1026) < 0.006 or abs(n - 0.041026) < 0.00006)


# ---- Invoice Register --------------------------------------------------------------------------------

INV_FIELDS = [  # (column, expected, display, refs)
    ("Vendor ID", VID, VID, [R_CLASS_PO]),
    ("Vendor Name", VENDOR, VENDOR, [R_CLASS_PO]),
    ("Invoice Date", "2025-05-19", "2025-05-19", [R_CLASS_PO]),
    ("Received Date", "2025-05-21", "2025-05-21", [R_CLASS_PO]),
    ("PO Number", PO, PO, [R_CLASS_PO]),
    ("Invoice Amount", "2030", "$2,030.00", [R_TOL_TOTAL]),
    ("GL Code", "6200-010-2200", "6200-010-2200 (GL code of PO-2025-00884)", [R_CLASS_PO]),
    ("Due Date", "2025-06-18", "2025-06-18 (Net 30 from the 2025-05-19 invoice date)", [R_TERMS]),
]
INV_HINT = (f"Invoice Register row: Invoice Number {INV} | Vendor ID {VID} | Vendor Name {VENDOR} | Invoice Date "
            f"2025-05-19 | Received Date 2025-05-21 | PO Number {PO} | Invoice Amount $2,030.00 | Status On Hold | "
            "Hold Code MATCH | GL Code 6200-010-2200 | Due Date 2025-06-18 | Notes (price variance, vendor "
            "clarification requested)")


def invoice_register_checks(ctx):
    w = world(ctx)
    rows = [r for r in w.rows(LEDGER, r"^Invoice Number$", "current", r"Invoice Register")
            if mentions_inv(get(r, "Invoice Number"))]
    if not rows:
        yield False, (f"{INV} is not entered in the Invoice Register of ap_ledger.xlsx. It is a PO invoice that fails "
                      "the Total Invoice Amount tolerance (+$80.00 / 4.10% vs ±$50 AND ±2%), so it must be entered "
                      f"on MATCH hold. Expected {INV_HINT}."), [R_CLASS_PO, R_TOL_TOTAL, R_HOLD]
        return
    if len(rows) > 1:
        yield False, (f"{INV} appears {len(rows)} times in the Invoice Register; keep exactly one entry "
                      "(no duplicate entries)."), [R_DUP]
    r = rows[-1]
    for colname, want, shown, refs in INV_FIELDS:
        got = get(r, colname)
        if not cell_eq(got, want):
            yield False, f"Invoice Register {INV}: {colname} must be {shown} (got \"{got}\").", refs
    status, code = get(r, "Status"), get(r, "Hold Code")
    if not re.match(r"on hold\b", norm(status)):
        yield False, (f"Invoice Register {INV}: Status must be \"On Hold\" - the total amount is outside tolerance, "
                      f"so the invoice is placed on MATCH hold (got \"{status}\")."), [R_TOL_TOTAL, R_HOLD]
    if norm(code) != "match":
        yield False, (f"Invoice Register {INV}: Hold Code must be \"MATCH\" (matching discrepancy) "
                      f"(got \"{code}\")."), [R_TOL_TOTAL, R_HOLD]


# ---- match log ----------------------------------------------------------------------------------------

ML_HINT = (f"Match log row: Match Date 2025-05-21 | PO Number {PO} | Vendor ID {VID} | Vendor Name {VENDOR} | "
           f"Invoice Number {INV} | PO Amount $1,950.00 | Invoice Amount $2,030.00 | Unit Price (PO) $97.50 | "
           "Unit Price (Invoice) $101.50 | Price Variance % 4.1% | Price Variance $ $4.00 | Qty (PO) 20 | "
           "Qty (Invoice) 20 | Total Variance $ $80.00 | Total Variance % 4.1% | Unit Price Result Pass | "
           "Total Amount Result Fail | Overall Result MATCH Hold | Hold Code MATCH | Notes")
ML_FIELDS = [  # (column, check, expected display, refs)
    ("Match Date", lambda v: day(v) == "2025-05-21", "2025-05-21", [R_MATCHLOG]),
    ("PO Number", lambda v: norm(v) == norm(PO), PO, [R_MATCHLOG]),
    ("Vendor ID", lambda v: norm(v) == norm(VID), VID, [R_MATCHLOG]),
    ("Vendor Name", lambda v: norm(v) == norm(VENDOR), VENDOR, [R_MATCHLOG]),
    ("PO Amount", lambda v: same(v, 1950), "$1,950.00", [R_MATCHLOG]),
    ("Invoice Amount", lambda v: same(v, 2030), "$2,030.00", [R_MATCHLOG]),
    ("Unit Price (PO)", lambda v: same(v, 97.5), "$97.50", [R_MATCHLOG]),
    ("Unit Price (Invoice)", lambda v: same(v, 101.5), "$101.50", [R_MATCHLOG]),
    ("Price Variance %", pct_ok, "4.1%", [R_TOL_PRICE]),
    ("Price Variance $", lambda v: same(v, 4), "$4.00", [R_TOL_PRICE]),
    ("Qty (PO)", lambda v: same(v, 20), "20", [R_TOL_QTY]),
    ("Qty (Invoice)", lambda v: same(v, 20), "20", [R_TOL_QTY]),
    ("Total Variance $", lambda v: same(v, 80), "$80.00", [R_TOL_TOTAL]),
    ("Total Variance %", pct_ok, "4.1%", [R_TOL_TOTAL]),
    ("Unit Price Result", lambda v: bool(re.match(r"pass\b", norm(v))),
     "Pass ($4.00 / 4.10% is within ±5% OR ±$25, whichever is greater)", [R_TOL_PRICE]),
    ("Total Amount Result", lambda v: bool(re.match(r"fail\b", norm(v))),
     "Fail (+$80.00 / 4.10% is outside ±$50 AND ±2%)", [R_TOL_TOTAL]),
    ("Overall Result", lambda v: bool(re.search(r"match", norm(v)) and re.search(r"hold", norm(v))),
     "MATCH Hold", [R_TOL_TOTAL, R_HOLD]),
    ("Hold Code", lambda v: norm(v) in ("", "match"), "MATCH", [R_HOLD]),
]


def match_log_checks(ctx):
    w = world(ctx)
    new = w.new_rows(MLOG, r"^Match Date$")
    mine = [r for r in new if mentions_inv(get(r, "Invoice Number"))]
    others = [r for r in new if r not in mine]
    if others:
        yield False, (f"match_log_2025_Q2.xlsx has {len(others)} new row(s) for other invoices "
                      f"(e.g. {get(others[0], 'Invoice Number') or 'blank'}); this task records only the {INV} "
                      "match attempt. Remove them."), [R_MATCHLOG, R_PURPOSE]
    if not mine:
        yield False, (f"The {INV} match attempt is not recorded in match_log_2025_Q2.xlsx. Append {ML_HINT}."), \
            [R_MATCHLOG, R_TOL_PRICE, R_TOL_TOTAL]
        return
    r = mine[-1]
    for colname, ok, shown, refs in ML_FIELDS:
        got = get(r, colname)
        if not ok(got):
            yield False, f"Match log {INV}: {colname} must be {shown} (got \"{got}\").", refs


# ---- untouched records ------------------------------------------------------------------------------

def records_checks(ctx):
    w = world(ctx)
    sheets = [("Invoice Register", r"^Invoice Number$"), ("PO Register", r"^PO Number$"),
              ("Payment Queue", r"^Invoice Number$"), ("GL Postings", r"^Journal Entry")]
    for sheet, hdr in sheets:
        gone, added = diff_rows(w, LEDGER, hdr, sheet)
        if gone:
            key = get(gone[0], "PO Number" if sheet == "PO Register" else "Invoice Number")
            refs = [R_61_2A, R_61_2B] if sheet == "PO Register" else [R_PURPOSE]
            why = (" The PO price is updated only when a vendor price increase notification is found (Step 2a); "
                   "none exists from Northgate, so PO-2025-00884 stays at $97.50 x 20."
                   if sheet == "PO Register" else " This task only adds the INV-NGO-4471 entry.")
            yield False, (f"ap_ledger.xlsx / {sheet}: {len(gone)} existing row(s) were changed or removed "
                          f"(e.g. {key}). Restore them exactly as they were.{why}"), refs
        if sheet == "Invoice Register":
            added = [r for r in added if not mentions_inv(get(r, "Invoice Number"))]
            if added:
                yield False, (f"ap_ledger.xlsx / Invoice Register: new row(s) for other invoices "
                              f"({get(added[0], 'Invoice Number') or 'blank'}); only {INV} is processed here. "
                              "Remove them."), [R_PURPOSE]
        elif added:
            ours = any(mentions_inv(" ".join(str(v) for v in r.values())) for r in added)
            if sheet in ("Payment Queue", "GL Postings") and ours:
                yield False, (f"ap_ledger.xlsx / {sheet}: {INV} must not be added - it is on MATCH hold (total "
                              "outside tolerance), so it is not auto-approved, posted to GL or queued for payment. "
                              "Remove the row."), [R_TOL_TOTAL, R_7, R_BATCH_HOLD]
            else:
                refs = [R_61_2A, R_61_2B] if sheet == "PO Register" else [R_PURPOSE]
                yield False, (f"ap_ledger.xlsx / {sheet}: {len(added)} unrequested new row(s) were added. "
                              "Remove them."), refs
    gone, added = diff_rows(w, VMASTER, r"^Vendor ID$")
    if gone or added:
        yield False, ("vendor_master.xlsx was changed. The contracted rate is updated only after a vendor price "
                      "increase notification is found (6.1 Step 2a); Northgate sent none, so vendor_master.xlsx "
                      "must stay unchanged. Restore it."), [R_61_2A, R_61_2B]
    extra = [b for b in w.created_books()]
    if extra:
        yield False, (f"New spreadsheet(s) created: {', '.join(extra)}. Do not create ad hoc spreadsheets; record "
                      "the match in ap_ledger.xlsx and match_log_2025_Q2.xlsx only. Delete them."), [R_NO_ADHOC]


def result_file_checks(ctx):
    w = world(ctx)
    path, text = w.file_text(RESULT_FILE)
    if not path:
        yield False, ("The instruction requires a new file /workdir/match_result_INV-NGO-4471.txt with a brief "
                      "explanation of the determination (MATCH hold: total +$80.00 / 4.10% outside ±$50 AND ±2%; "
                      "unit price and quantity pass) and next steps (vendor clarification requested, PRICE "
                      "VARIANCE posted to #ap-exceptions, no payment while on hold)."), [R_61]
    elif not re.search(r"\bhold\b", text, re.I):
        yield False, ("match_result_INV-NGO-4471.txt must state the determination: the invoice is placed on MATCH "
                      "hold (total amount outside tolerance)."), [R_TOL_TOTAL, R_HOLD]


# ---- messages -----------------------------------------------------------------------------------------

def specs(ctx) -> list[Comm]:
    w = world(ctx)
    email_kinds = ("email_send", "email_draft")
    return [
        Comm("price_discrepancy_email", "email",
             lambda a: a.kind in email_kinds and (
                 any(x.lower().endswith("@northgateoffice.com") for x in a.recipients + a.cc)
                 or bool(re.search(r"price discrepancy", a.subject or "", re.I))),
             "Price discrepancy email to Northgate (6.1 Step 2b: no price increase notification on file)",
             [R_61_2B, R_61_S1], to=[VENDOR_EMAIL], exact_to=False,
             subject=r"Meridian Partners [-–—] Price Discrepancy on Invoice INV-NGO-4471",
             subject_hint=SUBJECT,
             body=[(r"\$?\s?97\.50?(?!\d)", "the PO price $97.50"),
                   (r"\$?\s?101\.50?(?!\d)", "the invoiced price $101.50"),
                   (r"4\.1\d{0,3}\s?%", "the variance percentage 4.1%"),
                   (r"corrected invoice|written justification",
                    "a request for a corrected invoice or written justification"),
                   (r"\b(5|five)\s+business\s+days", "the 5 business day response window")]),
        Comm("price_variance_post", "slack_post",
             lambda a: a.kind in ("slack_post", "slack_dm") and "PRICE VARIANCE" in (a.text or "").upper(),
             "PRICE VARIANCE notification in #ap-exceptions (6.1 Step 3)", [R_61_S3, R_CH_EXC],
             channel="ap-exceptions",
             exact=(r"PRICE VARIANCE: Northgate Office Solutions, V-00229, Invoice INV-NGO-4471, PO Price \$97\.50, "
                    r"Invoice Price \$101\.50, Variance 4\.1\d{0,3}%\.?"),
             exact_hint=SLACK_POST),
        Comm("no_dm", "slack_dm",
             lambda a: (a.kind == "slack_dm" or bool(w.dm_recipients(a)))
             and (mentions_inv(a.text) or "northgate" in (a.text or "").lower()),
             "Direct message about the INV-NGO-4471 exception", [R_SLACK_NO_DM],
             forbidden=("Exceptions need an audit trail: do not use direct messages. The SOP notification is the "
                        f"#ap-exceptions post: {SLACK_POST}")),
        Comm("no_payment_confirmation", "slack_post",
             lambda a: a.kind == "slack_post" and mentions_inv(a.text)
             and (w.is_channel(a.channel, "ap-payments")
                  or (w.is_channel(a.channel, "ap-approvals")
                      and re.search(r"confirm|approved|release|payment", a.text or "", re.I)
                      and not re.search(r"\bhold\b|variance|discrepan", a.text or "", re.I))),
             "Payment confirmation / payment post for INV-NGO-4471", [R_7, R_AUTH, R_TOL_TOTAL, R_BATCH_HOLD],
             forbidden=(f"{INV} failed the three-way match (total +$80.00 / 4.10% outside ±$50 AND ±2%) and is on "
                        "MATCH hold, so it is not matched/approved and must not be confirmed or queued for payment.")),
    ]


RULES = (
    state_rule("ngo.invoice_register", invoice_register_checks, f"Fix the Invoice Register entry: {INV_HINT}.")
    + state_rule("ngo.match_log", match_log_checks, f"Fix the match log: {ML_HINT}.")
    + append_only("ngo.match_log_append_only", MLOG, r"^Match Date$", "match_log_2025_Q2.xlsx", [R_MATCHLOG])
    + state_rule("ngo.records_unchanged", records_checks, "Restore the records as described.")
    + state_rule("ngo.result_file", result_file_checks, "Write match_result_INV-NGO-4471.txt as described.")
    + comm_rules("ngo", specs)
    + no_placeholders([R_42_TPL, R_61_2B])
)
