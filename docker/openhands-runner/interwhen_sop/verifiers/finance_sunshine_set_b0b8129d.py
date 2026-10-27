"""Verifiers for finance_sunshine_set_b0b8129d - Sunshine & Set, SOP Section 5 (Inventory and Floorplan).

Situation (04/16/2026, acting user Darius Kim, Inventory Accountant): reconcile the JM Family floorplan statement
of 04/16/2026 (10 units, $319,750) to the floorplan worksheet and the inventory schedules, then reply to Marcus
Hale's request (email 9). Facts derived from the seed data:
- N2041 (Deal 4501, Robert Chen, sold 03/31/2026, funded 04/10/2026) is still on the statement with $185 late
  payoff interest -> sold-not-paid: 3-business-day deadline 04/03/2026, 9 business days past due; concurrent
  $2,000 NSF returned check 04/13/2026 (deal log + cash exception log).
- N2048 curtailment due 02/11/2026 (statement), unpaid -> aged curtailment, 64 days past due, 94 days on floor.
- N2043 (Deal 4505 unwound 04/16) is on the statement ($40,100, advance 04/02/2026) but not on the worksheet ->
  reinstate. N2049 (new Tundra SR5, VIN 5TFDY5F10RX904516, invoice $34,600, advance 04/15/2026) is on the
  statement but in neither the worksheet nor the new-vehicle inventory schedule -> add (pack $500).
- U1090 book cost $31,150 > expected retail $29,500 and recon $5,200 > $5,000 -> escalate to Elena Brooks.
Workbook edits may be made in place or in a revised copy (e.g. *_v2.xlsx, SOP 9.4); the checks read the revised
copy when one exists.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..kit import (Action, Comm, Context, World, blank, book_eq, comm_rules, dashes, forbid_writes, nh,
                   no_placeholders, num, pre_rule, state_rule, text_of, world)

TASK = "finance_sunshine_set_b0b8129d"
MARCUS = "marcus.hale@sunshineandsetauto.com"
ELENA = "elena.brooks@sunshineandsetauto.com"
DATE = r"\d{2}/\d{2}/\d{4}"

# ---- SOP references (section, paragraph prefix, label) ----------------------------------------------------------
R_ROLE = ("1.2", "Darius Kim | Inventory Accountant", "1.2 Team Directory (Darius Kim: floorplan, inventory schedules)")
R_RULES = ("1.1", "Spreadsheets — working schedules", "1.1 Tools (Rules tab templates, use exactly)")
R_UNWIND = ("2.5", "1. Reverse the original deal posting", "2.5 Unwind step 2 (reinstate on the floorplan worksheet)")
R_INV = ("5.1", "Reconcile new and used vehicle inventory daily", "5.1 Vehicle Inventory")
R_PACK = ("5.2", "New vehicle pack is a fixed $500", "5.2 Pack Calculation")
R_RECON1 = ("5.3", "All reconditioning charges", "5.3 Reconditioning Cost Capitalization")
R_RECON2 = ("5.3", "to a stock number and posted", "5.3 Recon limits / escalation to Elena Brooks")
R_FP_WS = ("5.6", "Maintain a daily floor plan worksheet", "5.6 Floorplan worksheet")
R_FP_REC = ("5.6", "Reconcile the floor plan statement", "5.6 Floorplan reconciliation")
R_FP_VAR = ("5.6", "The daily floorplan balance in the inventory tracker", "5.6 Variances / exception log")
R_FP_SOLD = ("5.6", "For sold units, verify immediate payoff timing", "5.6 Sold units")
R_FP_ESC = ("5.6", "Any potential out-of-trust exposure", "5.6 Escalation: Slack template, then email")
R_SLK_AC = ("5.6", "[STOCK]: Aged curtailment.", "5.6 Aged curtailment Slack template")
R_SLK_SNP = ("5.6", "[STOCK]: Sold-not-paid.", "5.6 Sold-not-paid Slack template")
R_EMAIL_TPL = ("5.6", "The escalation email to Marcus Hale and Elena Brooks", "5.6 Email template I or J")
R_CONC = ("5.6", "Before sending a sold-not-paid escalation", "5.6 Concurrent collection issue")
R_FACTS = ("9.3", "Collect the five required facts", "9.3 Five required facts")
R_DOC = ("9.3", "Document every step in the exception log", "9.3 Document in the exception log")
R_SAME_DAY = ("9.3", "Escalate the same day if the discrepancy affects", "9.3 Same-day escalation")
R_TRAIL = ("9.4", "Every accounting process must leave an audit trail", "9.4 File and Naming Standards")
R_TPL_I = [("10.5", "Subject: Aged Curtailment for [STOCK]", "Template I"),
           ("10.5", "Stock [STOCK], [YEAR MAKE MODEL TRIM]", "Template I"),
           ("10.5", "Aged curtailment. Curtailment due", "Template I"),
           ("10.5", "Slack notification sent to #acct-floorplan.", "Template I/J")]
R_TPL_J = [("10.5", "Subject: Sold-not-paid for [STOCK]", "Template J"),
           ("10.5", "Stock [STOCK], [YEAR MAKE MODEL]. Deal", "Template J"),
           ("10.5", "Sold-not-paid. Payoff not sent. Deadline", "Template J"),
           ("10.5", "Late payoff interest:", "Template J")]

# ---- seed facts ------------------------------------------------------------------------------------------------
STATEMENT = {"N2041": 28250, "N2043": 40100, "N2046": 31200, "N2047": 38400, "N2048": 48200, "N2049": 34600,
             "U1087": 22500, "U1090": 25200, "U1092": 21800, "U1093": 29500}  # JM Family statement 04/16/2026
NEW_FP_ROWS = {
    "N2043": "Stock# N2043 | VIN 5TDJZRAH0RS504505 | Vehicle 2026 Toyota Highlander XLE | Lender JM Family "
             "Enterprises | Advance Date 04/02/2026 | Principal Balance 40100 | Status Reinstated | Days on Floor 14 | "
             "Lot Status On lot | Notes \"Reinstated after Deal 4505 unwind. Effective 04/16/2026.\"",
    "N2049": "Stock# N2049 | VIN 5TFDY5F10RX904516 | Vehicle 2026 Toyota Tundra SR5 | Lender JM Family Enterprises | "
             "Advance Date 04/15/2026 | Principal Balance 34600 | Status In Stock | Days on Floor 1 | Lot Status On lot | "
             "Notes \"Advance date 04/15/2026. Invoice $34,600.\"",
}
# (stock, column, fullmatch regex, exact value to write)
FP_CELLS = [
    ("N2041", "Status", r"Sold — not paid off FP", "Sold — not paid off FP"),
    ("N2041", "Notes", r"Deal 4501, sold 03/31/2026\. Payoff not sent\. 3-business-day deadline: 04/03/2026\. "
                       r"9 business days past due\. Late interest: \$185(\.00)? per lender statement\.",
     "Deal 4501, sold 03/31/2026. Payoff not sent. 3-business-day deadline: 04/03/2026. 9 business days past due. "
     "Late interest: $185 per lender statement."),
    ("N2048", "Curtailment Due Date", r"02/11/2026", "02/11/2026"),
    ("N2048", "Status", r"Aged Curtailment — Immediate Escalation", "Aged Curtailment — Immediate Escalation"),
    ("N2048", "Notes", r"Aged curtailment\. Due 02/11/2026\. 64 days past due\. Escalated to Marcus Hale and "
                       r"Elena Brooks\.",
     "Aged curtailment. Due 02/11/2026. 64 days past due. Escalated to Marcus Hale and Elena Brooks."),
    ("N2043", "VIN", r"5TDJZRAH0RS504505", "5TDJZRAH0RS504505"),
    ("N2043", "Lender", r"JM Family Enterprises|JM Family", "JM Family Enterprises"),
    ("N2043", "Advance Date", r"04/02/2026", "04/02/2026"),
    ("N2043", "Status", r"Reinstated", "Reinstated"),
    ("N2043", "Notes", r"Reinstated after Deal 4505 unwind\. Effective 04/1[46]/2026\.",
     "Reinstated after Deal 4505 unwind. Effective 04/16/2026."),
    ("N2049", "VIN", r"5TFDY5F10RX904516", "5TFDY5F10RX904516"),
    ("N2049", "Lender", r"JM Family Enterprises|JM Family", "JM Family Enterprises"),
    ("N2049", "Advance Date", r"04/15/2026", "04/15/2026"),
    ("N2049", "Status", r"In Stock", "In Stock"),
    ("N2049", "Notes", r"Advance date 04/15/2026\. Invoice \$34,600(\.00)?\.", "Advance date 04/15/2026. Invoice $34,600."),
]
N2049_INV = [  # New Inventory row for N2049 (Lakewood purchase; pack $500; book = invoice + pack + recon)
    ("VIN", r"5TFDY5F10RX904516", "5TFDY5F10RX904516"), ("Year", r"2026(\.0)?", "2026"), ("Make", r"Toyota", "Toyota"),
    ("Model", r"Tundra", "Tundra"), ("Trim", r"SR5", "SR5"),
    ("In-Stock Date", r"04/1[56]/2026", "04/16/2026 (arrived on lot 04/16; purchase completed 04/15)"),
    ("Invoice Cost", None, 34600), ("Pack", None, 500), ("Recon", r"0(\.0)?|", "0"), ("Book Cost", None, 35100),
    ("Status", r"In Stock", "In Stock"), ("Floorplan", r"Y", "Y"), ("FP Lender", r"JM Family( Enterprises)?", "JM Family"),
    ("Notes", r"Stocked 04/1[56]/2026\. Invoice \$34,600(\.00)?\.", "Stocked 04/16/2026. Invoice $34,600."),
]
OTHER_BOOKS = r"(^|/)(AP_Queue|Bank_Rec|Cash_Exception_Log|Chargeback_Tracker|CommSheet_|Commission_Sheet|Deal_Log|" \
              r"Funding_Tracker|Payoff_Control_Log)[^/]*\.xlsx$"
FP_BOOK, NEW_BOOK, USED_BOOK = (r"(^|/)Floorplan_Worksheet[^/]*\.xlsx$", r"(^|/)Inventory_New[^/]*\.xlsx$",
                                r"(^|/)Inventory_Used[^/]*\.xlsx$")
SOURCE_DOCS = r"^(Invoice_SBP\d+|Payoff_Letter_\w+|\d{8}_Deal\d+_\w+|W9_\w+|DR123_\w+|Vendor_Statement_\w+)\.pdf$|" \
              r"^Sunshine_Set_Automotive_SOP\.docx$"

# Rules-tab vocabularies
FP_STATUSES = {"In Stock", "Aged Curtailment — Immediate Escalation", "Reinstated", "Sold — not paid off FP",
               "Sold, funded", "Sold, unfunded"}
FP_NOTES = ["Advance date [MM/DD/YYYY]. Invoice $[amount].",
            "Aged curtailment. Due [MM/DD/YYYY]. [N] days past due. Escalated to Marcus Hale and Elena Brooks.",
            "Payoff confirmed by lender [MM/DD/YYYY] per [Lender Name] statement.",
            "Reinstated after Deal [#] unwind. Effective [MM/DD/YYYY].",
            "Deal [#], sold [MM/DD/YYYY]. Payoff not sent. 3-business-day deadline: [MM/DD/YYYY]. [N] business days "
            "past due. Late interest: $[amount] per lender statement.",
            "Deal [#], day [N] unfunded."]
INV_STATUS = r"In Stock|Sold \d{2}/\d{2}/\d{4}|In Stock \(returned from unwind\)|Pending Arrival|Wholesale"
INV_NOTES_COMMON = ["Sold [MM/DD/YYYY], funded [MM/DD/YYYY]. Floorplan paid off [MM/DD/YYYY].",
                    "Sold [MM/DD/YYYY], funded [MM/DD/YYYY or N/A]. Floorplan payoff NOT sent. Day [N].",
                    "Returned from Deal [#] unwind. Effective [MM/DD/YYYY]. Back on lot.", "Non-Floored"]
INV_NOTES = {"new": ["Stocked [MM/DD/YYYY]. Invoice $[amount]."] + INV_NOTES_COMMON,
             "used": ["Stocked [MM/DD/YYYY]. ACV $[amount].",
                      "Recon posted [MM/DD/YYYY]. Invoice [#], $[amount]. Book Cost updated to $[amount]."]
                     + INV_NOTES_COMMON}
EXC_CLASSES = {"Data Entry", "Missing Document", "Timing", "Accounting Error"}
PH = {"[MM/DD/YYYY]": DATE, "[MM/DD/YYYY or N/A]": rf"(?:{DATE}|N/A)", "[amount]": r"[\d,]+(?:\.\d{2})?",
      "[N]": r"\d+", "[#]": r"[\w-]+", "[Lender Name]": r"[A-Z][\w&.,' -]*?"}


def tpl_rx(templates: list[str]) -> str:
    alts = []
    for t in templates:
        parts = re.split(r"(\[[^\]]+\])", t)
        alts.append("".join(PH.get(p, re.escape(p)) if p.startswith("[") else re.escape(p) for p in parts))
    one = "(?:" + "|".join(alts) + ")"
    return rf"{one}(?:\s+{one})*"


FP_NOTES_RX = tpl_rx(FP_NOTES)
INV_NOTES_RX = {k: tpl_rx(v) for k, v in INV_NOTES.items()}


# ---- workbook helpers --------------------------------------------------------------------------------------------

def live_book(w: World, rx: str) -> tuple[str | None, str | None]:
    """(original key, key holding the agent's current version): a changed revised copy wins over the original."""
    orig = next(iter(sorted(k for k in (w.initial or {}) if re.search(rx, k, re.I))), None)
    copies = [k for k in w.created_books() if re.search(rx, k, re.I)
              and not book_eq((w.current or {}).get(k), (w.initial or {}).get(orig))]
    return orig, (sorted(copies)[-1] if copies else orig)


def exact(key: str) -> str:
    return "^" + re.escape(key) + "$"


def table(w: World, key: str | None, sheet_rx: str, header_rx: str, which: str = "current") -> list[dict]:
    return w.rows(exact(key), header_rx, which, sheet_rx) if key else []


def by_stock(rows: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(nh(World.col(r, r"^Stock#$")).upper(), []).append(r)
    return out


def cell(r: dict, col: str) -> str:
    return nh(World.col(r, "^" + re.escape(col) + "$"))


def fp_rows(w: World, which: str = "current") -> tuple[str | None, list[dict]]:
    orig, key = live_book(w, FP_BOOK)
    key = orig if which == "initial" else key
    return key, table(w, key, r"Floorplan Tracking", r"^Stock#$", which)


def exc_rows(w: World, which: str = "current") -> list[dict]:
    orig, key = live_book(w, FP_BOOK)
    return table(w, orig if which == "initial" else key, r"Exception Log", r"^Date Identified$", which)


def inv_rows(w: World, kind: str, which: str = "current") -> tuple[str | None, list[dict]]:
    orig, key = live_book(w, NEW_BOOK if kind == "new" else USED_BOOK)
    key = orig if which == "initial" else key
    return key, table(w, key, r"New Inventory" if kind == "new" else r"Used Inventory", r"^Stock#$", which)


def changed_rows(cur: list[dict], init: list[dict]) -> list[tuple[dict, dict | None]]:
    """(current row, initial row with the same Stock# or None) for rows that are new or differ."""
    first = {s: rs[0] for s, rs in by_stock(init).items()}
    out = []
    for r in cur:
        old = first.get(nh(World.col(r, r"^Stock#$")).upper())
        if old is None or any(nh(v) != nh(old.get(k, "")) for k, v in r.items() if k != "__row__"):
            out.append((r, old))
    return out


# ---- completion: floorplan worksheet ------------------------------------------------------------------------------

def fp_statement_checks(ctx: Context):
    w = world(ctx)
    key, rows = fp_rows(w)
    if not rows:
        return
    stocks = by_stock(rows)
    for stock, amount in STATEMENT.items():
        hits = stocks.get(stock, [])
        if not hits:
            yield (False, f"{key} / Floorplan Tracking: {stock} is on the JM Family statement of 04/16/2026 "
                          f"(${amount:,}) but not on the floorplan worksheet. Add the row: {NEW_FP_ROWS.get(stock, '')}",
                   [R_FP_REC, R_FP_WS, R_UNWIND] if stock == "N2043" else [R_FP_REC, R_FP_WS])
        elif len(hits) > 1:
            yield (False, f"{key} / Floorplan Tracking: {stock} appears {len(hits)} times; keep exactly one row.",
                   [R_FP_WS])
        else:
            got = num(cell(hits[0], "Principal Balance"))
            yield (got is not None and abs(got - amount) < 0.01,
                   f"{key} / Floorplan Tracking: {stock} Principal Balance is {cell(hits[0], 'Principal Balance')!r}; "
                   f"the JM Family statement of 04/16/2026 shows {amount} - set Principal Balance to {amount}.",
                   [R_FP_REC, R_FP_VAR])


def fp_cell_checks(ctx: Context):
    w = world(ctx)
    key, rows = fp_rows(w)
    stocks = by_stock(rows)
    for stock, col, rx, want in FP_CELLS:
        hits = stocks.get(stock)
        if not hits:
            continue  # the missing row is reported by fp.statement_units
        got = cell(hits[0], col)
        refs = {"N2041": [R_FP_SOLD, R_FP_VAR, R_RULES], "N2048": [R_FP_ESC, R_FP_WS, R_RULES],
                "N2043": [R_UNWIND, R_FP_WS, R_RULES], "N2049": [R_FP_REC, R_FP_WS, R_RULES]}[stock]
        yield (bool(re.fullmatch(rx, got)),
               f"{key} / Floorplan Tracking {stock} column '{col}' is {got!r}; per the Rules tab and the 04/16/2026 "
               f"statement it must be exactly: {want}", refs)


def fp_format_checks(ctx: Context):
    w = world(ctx)
    key, cur = fp_rows(w)
    _, init = fp_rows(w, "initial")
    for r, old in changed_rows(cur, init):
        stock = cell(r, "Stock#")
        status = cell(r, "Status")
        yield (status in FP_STATUSES or blank(status),
               f"{key} / Floorplan Tracking {stock}: Status {status!r} is not a Rules-tab value. Use exactly one of: "
               + " | ".join(sorted(FP_STATUSES)), [R_RULES])
        for col in ("Advance Date", "Curtailment Due Date"):
            v = cell(r, col)
            if old is not None and v == cell(old, col):
                continue
            yield (blank(v) or bool(re.fullmatch(DATE, v)),
                   f"{key} / Floorplan Tracking {stock}: {col} {v!r} must be written as text in MM/DD/YYYY format "
                   "(Rules tab: all dates, including date columns).", [R_RULES])
        notes = cell(r, "Notes")
        if not blank(notes) and (old is None or notes != cell(old, "Notes")):
            yield (bool(re.fullmatch(FP_NOTES_RX, notes)),
                   f"{key} / Floorplan Tracking {stock}: Notes {notes!r} do not follow a Rules-tab template. Copy the "
                   "template and fill the brackets only: " + " | ".join(FP_NOTES), [R_RULES])


def exception_checks(ctx: Context):
    w = world(ctx)
    init = exc_rows(w, "initial")
    cur = exc_rows(w)
    seen = [tuple(nh(v) for k, v in r.items() if k != "__row__") for r in cur]
    for r in init:
        t = tuple(nh(v) for k, v in r.items() if k != "__row__")
        yield (t in seen, "Floorplan Exception Log is append-only: the existing entry "
                          f"{' | '.join(t[:4])} was edited or removed. Restore it and only append new rows.", [R_DOC])
    old = [tuple(nh(v) for k, v in r.items() if k != "__row__") for r in init]
    new = []
    for r in cur:
        t = tuple(nh(v) for k, v in r.items() if k != "__row__")
        if t in old:
            old.remove(t)
        else:
            new.append(r)
    facts = ["Deal/Invoice #", "Customer/Vendor", "VIN/Stock #", "Variance Amount", "Source Document"]
    for r in new:
        tag = f"Exception Log row {r['__row__']} ({cell(r, 'VIN/Stock #') or cell(r, 'Deal/Invoice #')})"
        d = cell(r, "Date Identified")
        yield (bool(re.fullmatch(DATE, d)), f"{tag}: Date Identified {d!r} must be MM/DD/YYYY text (04/16/2026).",
               [R_RULES])
        c = cell(r, "Classification")
        yield (c in EXC_CLASSES, f"{tag}: Classification {c!r} must be exactly one of: "
                                 + " | ".join(sorted(EXC_CLASSES)), [R_RULES, R_FACTS])
        miss = [f for f in facts if blank(cell(r, f))]
        yield (not miss, f"{tag}: missing required fact(s) {', '.join(miss)} (all five facts per Section 9.3).",
               [R_FACTS, R_FP_VAR])
    has41 = any(re.search(r"N2041", cell(r, "VIN/Stock #")) or re.search(r"\b4501\b", cell(r, "Deal/Invoice #"))
                for r in new)
    yield (has41, "Floorplan Exception Log has no entry for the N2041 sold-not-paid discrepancy. Append a row: "
                  "Date Identified 04/16/2026 | Deal/Invoice # 4501 | Customer/Vendor Robert Chen | VIN/Stock # N2041 | "
                  "Variance Amount $28,250.00 | Source Document JM Family floorplan statement 04/16/2026 | "
                  "Classification (one of Data Entry, Missing Document, Timing, Accounting Error) | Contact Marcus Hale; "
                  "Elena Brooks | Follow-up | Expected Resolution (MM/DD/YYYY) | Status | Notes.",
           [R_FP_VAR, R_FACTS, R_DOC])


# ---- completion: inventory schedules ------------------------------------------------------------------------------

def inv_new_unit_checks(ctx: Context):
    w = world(ctx)
    key, rows = inv_rows(w, "new")
    if key is None:
        return
    hits = by_stock(rows).get("N2049")
    if not hits:
        spec = " | ".join(f"{c} {v}" for c, _, v in N2049_INV)
        yield (False, f"{key} / New Inventory: N2049 (2026 Toyota Tundra SR5 from Lakewood Toyota, invoice $34,600 per "
                      f"AP LT-2026-0416, arrived on lot 04/16/2026, floored with JM Family) is missing. Add: "
                      f"Stock# N2049 | {spec}", [R_INV, R_PACK, R_FP_REC])
        return
    r = hits[0]
    for col, rx, want in N2049_INV:
        got = cell(r, col)
        ok = (num(got) is not None and abs(num(got) - want) < 0.01) if rx is None else bool(re.fullmatch(rx, got))
        yield (ok, f"{key} / New Inventory N2049 column '{col}' is {got!r}; it must be {want}.",
               [R_INV, R_PACK, R_RULES])


def inv_n2041_checks(ctx: Context):
    w = world(ctx)
    key, rows = inv_rows(w, "new")
    hits = by_stock(rows).get("N2041")
    if not hits:
        return
    got = cell(hits[0], "Notes")
    yield (bool(re.fullmatch(r"Sold 03/31/2026, funded 04/10/2026\. Floorplan payoff NOT sent\. Day \d+\.", got)),
           f"{key} / New Inventory N2041 Notes are {got!r}, but the floorplan payoff was never sent (JM Family still "
           "carries N2041 with $185 late interest). Use the Rules-tab template 'Sold - floorplan not paid': "
           "\"Sold 03/31/2026, funded 04/10/2026. Floorplan payoff NOT sent. Day 16.\" (Day = days since the sale).",
           [R_INV, R_FP_SOLD, R_RULES])


def inv_format_checks(ctx: Context):
    w = world(ctx)
    for kind in ("new", "used"):
        key, cur = inv_rows(w, kind)
        _, init = inv_rows(w, kind, "initial")
        for r, old in changed_rows(cur, init):
            stock = cell(r, "Stock#")
            st = cell(r, "Status")
            if old is None or st != cell(old, "Status"):
                yield (bool(re.fullmatch(INV_STATUS, st)),
                       f"{key} {stock}: Status {st!r} is not a Rules-tab value (In Stock | Sold MM/DD/YYYY | "
                       "In Stock (returned from unwind) | Pending Arrival | Wholesale).", [R_RULES, R_INV])
            for col in ("In-Stock Date", "FP Paid Date"):
                v = cell(r, col)
                if old is not None and v == cell(old, col):
                    continue
                yield (blank(v) or bool(re.fullmatch(DATE, v)),
                       f"{key} {stock}: {col} {v!r} must be MM/DD/YYYY text (Rules tab).", [R_RULES])
            notes = cell(r, "Notes")
            if not blank(notes) and (old is None or notes != cell(old, "Notes")):
                yield (bool(re.fullmatch(INV_NOTES_RX[kind], notes)),
                       f"{key} {stock}: Notes {notes!r} do not follow a Rules-tab template. Copy one and fill the "
                       "brackets only: " + " | ".join(INV_NOTES[kind]), [R_RULES])


def inv_cost_checks(ctx: Context):
    w = world(ctx)
    for kind in ("new", "used"):
        key, cur = inv_rows(w, kind)
        _, init = inv_rows(w, kind, "initial")
        now = by_stock(cur)
        for old in init:
            stock = cell(old, "Stock#")
            hit = now.get(stock.upper())
            if not hit:
                yield (False, f"{key}: {stock} was removed from the inventory schedule. Restore the row (record "
                              "disposals by status/notes, do not delete units).", [R_INV])
                continue
            for col in ("Invoice Cost", "ACV", "Pack", "Recon", "Book Cost"):
                if col not in old:
                    continue
                a, b = num(cell(old, col)), num(cell(hit[0], col))
                yield (a == b, f"{key} {stock}: {col} changed from {cell(old, col)} to {cell(hit[0], col)!r}. Costs "
                               f"of existing units are already posted; restore {col} = {cell(old, col)} (pack changes "
                               "need Elena Brooks approval; added recon beyond retail needs escalation first).",
                       [R_PACK, R_RECON1, R_RECON2, R_INV])


# ---- completion: escalation of U1090 recon --------------------------------------------------------------------------

def reaches_elena(w: World, a: Action) -> bool:
    if a.kind == "email_send":
        return ELENA in a.recipients or ELENA in a.cc
    if a.kind == "slack_dm":
        return w.is_dm_to(a, "Elena Brooks")
    if a.kind == "slack_post":
        return bool(re.search(r"elena|<@U001>", a.text, re.I)) or w.is_dm_to(a, "Elena Brooks")
    return False


def u1090_checks(ctx: Context):
    w = world(ctx)
    ok = any(re.search(r"U1090|SBP-?4821", text_of(a), re.I) and reaches_elena(w, a) for a in w.comms())
    yield (ok, "U1090: book cost $31,150 (ACV $25,200 + pack $750 + recon $5,200) exceeds the expected retail ask of "
               "$29,500, and total recon $5,200 (Invoice SBP-4821) exceeds the $5,000 limit that needs Marcus Hale's "
               "written approval. Escalate to Elena Brooks (email elena.brooks@sunshineandsetauto.com, cc "
               "marcus.hale@sunshineandsetauto.com, or tag @elena.brooks in Slack) naming U1090 / SBP-4821.",
           [R_RECON2])


# ---- completion: scope ---------------------------------------------------------------------------------------------

def scope_checks(ctx: Context):
    w = world(ctx)
    for k in w.changed_files():
        if re.search(OTHER_BOOKS, k, re.I):
            yield (False, f"{k} was modified. The task is the Inventory and Floorplan section (floorplan worksheet and "
                          "inventory schedules); this workbook belongs to another process owner. Restore it to its "
                          "original content.", [R_ROLE, R_INV])


# ---- messages --------------------------------------------------------------------------------------------------------

MENTIONS = r"(?:@marcus\.hale|<@U002>)\s*(?:@elena\.brooks|<@U001>)"
CONC = r"Concurrent collection issue: \$2,?000(?:\.00)? (?:NSF|returned check|NSF returned check|returned check \(NSF\)|" \
       r"NSF check|returned check/NSF|NSF/returned check), 04/13/2026\."
CONC_HINT = "Concurrent collection issue: $2,000 NSF, 04/13/2026."
SLACK_48 = ("N2048: Aged curtailment. 94 days on floor. Curtailment past due since 02/11/2026 (64 days past due). "
            "@marcus.hale @elena.brooks")
SLACK_41 = f"N2041: Sold-not-paid. Deal 4501, Robert Chen. Payoff not sent. @marcus.hale @elena.brooks {CONC_HINT}"


def lit(s: str) -> str:
    """Literal SOP text as a regex tolerant to line wrapping."""
    return r"\s+".join(re.escape(p) for p in s.split())


@dataclass
class Escalation(Comm):
    """Template email to Marcus Hale and Elena Brooks (To or CC), sent only after its Slack notification."""
    slack: Comm | None = None

    def problems(self, a: Action, w: World) -> list[str]:
        to, cc = self.to, self.cc
        self.to, self.cc = [], list(to) + list(cc)
        try:
            out = [p.replace("CC must include", "To/CC must include") for p in super().problems(a, w)]
        finally:
            self.to, self.cc = to, cc
        if self.slack is not None and not any(self.slack.about(x) and not self.slack.problems(x, w) for x in w.comms()):
            out.append(f"Send the #acct-floorplan Slack notification first - the escalation email follows it "
                       f"(SOP 5.6). Post exactly: {self.slack.exact_hint}")
        return out


def specs(ctx: Context) -> list[Comm]:
    w = world(ctx)

    def channel_post(a: Action, unit: str, kw: str) -> bool:
        if a.kind != "slack_post" or w.dm_recipients(a):
            return False
        t = a.text.strip()
        other = "N2048" if unit == "N2041" else "N2041"
        if t.startswith(unit + ":"):
            return True
        return (w.is_channel(a.channel, "acct-floorplan") and unit in t and other not in t
                and bool(re.search(kw, t, re.I)))

    def email_about(a: Action, unit: str, kw: str) -> bool:
        if a.kind != "email_send" or re.search(r"reconciliation", a.subject, re.I):
            return False
        if "reply" in a.tool and str(a.args.get("email_id")) == "9":
            return False
        return bool(re.search(kw, a.subject, re.I) or unit in a.subject)

    slack48 = Comm("slack_n2048", "slack_post", lambda a: channel_post(a, "N2048", r"curtail"),
                   "N2048 aged-curtailment Slack notification in #acct-floorplan", [R_FP_ESC, R_SLK_AC],
                   channel="acct-floorplan",
                   exact=lit("N2048: Aged curtailment. 94 days on floor. Curtailment past due since 02/11/2026 "
                             "(64 days past due).") + r"\s*" + MENTIONS,
                   exact_hint=SLACK_48)
    slack41 = Comm("slack_n2041", "slack_post", lambda a: channel_post(a, "N2041", r"sold.?not.?paid|not paid|payoff"),
                   "N2041 sold-not-paid Slack notification in #acct-floorplan", [R_FP_ESC, R_SLK_SNP, R_CONC],
                   channel="acct-floorplan",
                   exact=lit("N2041: Sold-not-paid. Deal 4501, Robert Chen. Payoff not sent.") + r"\s*(?:"
                   + MENTIONS + r"\s*" + CONC + "|" + CONC + r"\s*" + MENTIONS + ")",
                   exact_hint=SLACK_41)
    email48 = Escalation("email_n2048", "email", lambda a: email_about(a, "N2048", r"aged curtailment"),
                         "Template I aged-curtailment email for N2048 to Marcus Hale and Elena Brooks",
                         [R_FP_ESC, R_EMAIL_TPL] + R_TPL_I, to=[MARCUS, ELENA], exact_to=False,
                         subject=r"Aged Curtailment for N2048", subject_hint="Aged Curtailment for N2048",
                         body=[(lit("Stock N2048, 2026 Toyota Highlander Platinum. Principal balance:") + r"\s+\$48,200(\.00)?\.",
                                "\"Stock N2048, 2026 Toyota Highlander Platinum. Principal balance: $48,200.\""),
                               (lit("Aged curtailment. Curtailment due 02/11/2026, 64 days past due. 94 days on floor."),
                                "\"Aged curtailment. Curtailment due 02/11/2026, 64 days past due. 94 days on floor.\""),
                               (lit("Slack notification sent to #acct-floorplan."),
                                "\"Slack notification sent to #acct-floorplan.\"")],
                         slack=slack48)
    email41 = Escalation("email_n2041", "email", lambda a: email_about(a, "N2041", r"sold.?not.?paid"),
                         "Template J sold-not-paid email for N2041 to Marcus Hale and Elena Brooks",
                         [R_FP_ESC, R_EMAIL_TPL, R_CONC] + R_TPL_J, to=[MARCUS, ELENA], exact_to=False,
                         subject=r"Sold-not-paid for N2041", subject_hint="Sold-not-paid for N2041",
                         body=[(r"Stock\s+N2041,\s+2026\s+Toyota\s+Camry(\s+LE)?\.\s+Deal\s+4501,\s+Robert\s+Chen\.\s+"
                                r"Principal\s+balance:\s+\$28,250(\.00)?\.",
                                "\"Stock N2041, 2026 Toyota Camry LE. Deal 4501, Robert Chen. Principal balance: $28,250.\""),
                               (lit("Sold-not-paid. Payoff not sent. Deadline 04/03/2026, 9 business days past due."),
                                "\"Sold-not-paid. Payoff not sent. Deadline 04/03/2026, 9 business days past due.\""),
                               (r"Late\s+payoff\s+interest:\s+\$185(\.00)?\s+per\s+lender\s+statement\.",
                                "\"Late payoff interest: $185 per lender statement.\""),
                               (lit("Slack notification sent to #acct-floorplan."),
                                "\"Slack notification sent to #acct-floorplan.\""),
                               (CONC.replace(" ", r"\s+"), f"\"{CONC_HINT}\" (Deal 4501 NSF returned check)")],
                         slack=slack41)

    def reply_about(a: Action) -> bool:
        if a.kind != "email_send":
            return False
        if "reply" in a.tool and str(a.args.get("email_id")) == "9":
            return True
        return MARCUS in a.recipients and bool(re.search(r"daily floorplan reconciliation", a.subject, re.I))

    reply = Comm("reply_marcus", "email", reply_about,
                 "reply to Marcus Hale's 'Daily Floorplan Reconciliation - April 16' email (email 9) with the "
                 "reconciliation summary of exceptions and escalations", [R_FP_VAR, R_SAME_DAY], exact_to=False,
                 body=[(r"N2041", "the N2041 / Deal 4501 sold-not-paid exception"),
                       (r"N2048", "the N2048 aged-curtailment exception")])
    return [slack48, slack41, email48, email41, reply]


ESCALATION_UNITS = {"sold-not-paid": "N2041", "aged curtailment": "N2048"}


def wrong_unit(ctx: Context, a: Action) -> str | None:
    """A sold-not-paid / aged-curtailment notification for a unit the 04/16 statement does not put in that state."""
    if a.kind not in ("email_send", "slack_post", "slack_dm"):
        return None
    hits = [(m.group(2), m.group(1)) for m in re.finditer(r"^\s*([NU]\d{4}):\s*(Sold-not-paid|Aged curtailment)\b",
                                                           dashes(a.text), re.I | re.M)]
    m = re.fullmatch(r"\s*(Sold-not-paid|Aged Curtailment) for ([NU]\d{4})\s*", dashes(a.subject), re.I)
    if m:
        hits.append((m.group(1), m.group(2)))
    for kind, unit in hits:
        want = ESCALATION_UNITS[kind.lower()]
        if unit.upper() != want:
            return (f"{unit.upper()} is not a {kind.lower()} unit: per the JM Family statement of 04/16/2026 and the "
                    f"deal log, the only {kind.lower()} unit is {want} (N2049 is a new purchase advanced 04/15/2026, "
                    "N2043 was returned to stock by the Deal 4505 unwind, U1090's 3-business-day payoff window runs "
                    "to 04/17/2026, U1087's payoff was received by JM Family 04/10).")
    return None


RULES = (
    state_rule("fp.statement_units", fp_statement_checks, "Make the floorplan worksheet tie to the lender statement.")
    + state_rule("fp.unit_annotations", fp_cell_checks, "Write the exact Rules-tab Status / Notes / dates listed.")
    + state_rule("fp.format", fp_format_checks, "Use the Rules-tab values and MM/DD/YYYY dates.")
    + state_rule("fp.exception_log", exception_checks, "Fix the Exception Log as listed.")
    + state_rule("inv.n2049_stock_in", inv_new_unit_checks, "Add/fix the N2049 row in the new-vehicle schedule.")
    + state_rule("inv.n2041_note", inv_n2041_checks, "Update the N2041 inventory note with the Rules-tab template.")
    + state_rule("inv.format", inv_format_checks, "Use the Rules-tab values and MM/DD/YYYY dates.")
    + state_rule("inv.costs_unchanged", inv_cost_checks, "Restore the posted costs.")
    + state_rule("recon.u1090_escalation", u1090_checks, "Send the escalation.")
    + state_rule("scope.other_workbooks", scope_checks, "Restore the workbook.")
    + comm_rules("fp.comms", specs)
    + pre_rule("fp.escalation_units", wrong_unit, [R_FP_ESC, R_SLK_SNP, R_SLK_AC, R_FP_SOLD],
               "Send sold-not-paid / aged-curtailment notifications only for N2041 / N2048; report other "
               "statement differences as ordinary exceptions.")
    + forbid_writes("files.source_docs", SOURCE_DOCS,
                    "source documents must not be overwritten or deleted - save revised versions with a suffix "
                    "such as v2 (SOP 9.4).", [R_TRAIL])
    + no_placeholders([R_FP_ESC])
)
