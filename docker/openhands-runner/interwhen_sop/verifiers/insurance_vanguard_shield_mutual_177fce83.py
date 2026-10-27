"""Vanguard Shield Mutual - T&E expense review (§6.2) for the five OPS-HR-TE reports submitted 2026-05-11.

The user asked for the SOP outcome as an Excel file (expense_reports.xlsx, one sheet per employee) instead of
Jira updates, plus the SOP's Slack notifications. Facts come from the Jira seed, the receipts in the workspace,
the calendar (GCM conference, Chicago, May 6-9), Shopify carts and People Directory.xlsx.

Only outcomes that follow unambiguously from the SOP and seed data are enforced:
- Priya Natarajan (OPS-39): every receipt is in Fort Wayne, IN, while the only calendar event is in Chicago, so
  every line is invalid (step 3a) -> report Denied -> one Template B-2 flag to her manager Layla Zahra.
- Carlos Mendez (OPS-32): the Art Institute admission is staff leisure (step 5j) -> denied with the standard note.
- Leila Rahimi (OPS-50): escape room for 8 units with 5 listed attendees -> 3 units denied (step 5h).
- Reports of Amina Hassan, Carlos Mendez and Hiroshi Tanaka cannot reach $200 of denials -> no B-2 flag.
Leila Rahimi's final status (lodging-per-night reading) and Amina/Hiroshi line decisions are left to the agent;
only internal consistency (amount split, totals, status, comment, manager flag) is checked for them.
"""

from __future__ import annotations

import datetime as dt
import re

from ..kit import (Action, Comm, Context, comm_rules, forbid_writes, money_rx, no_placeholders, norm, num,
                   pre_rule, state_rule, world)

# ---- SOP references (section, paragraph prefix, label) ---------------------------------------------------
R_REVIEW = ("1", "YYYYMM-DD] for each expense report with status Submitted", "§6.2 step 1 (review submissions)")
R_CATEG = ("1", "2. Categorize each expense", "§6.2 step 2 (categorize)")
R_TIME = ("3", "a. For each expense tied to a specific date", "§6.2 step 3 (time-specific expenses)")
R_RETAIL = ("4", "a. For each purchase of retail goods", "§6.2 step 4 (retail purchases via Shopify)")
R_SHARED = ("1", "For expenses that apply to multiple staff members", "§6.2 step 2 (shared expenses)")
R_POLICY = ("4", "5. Validate expenses", "§6.2 step 5 (T&E policy)")
R_POLICY2 = ("4", "Vanguard Shield Mutual — Core Operations SOP g. Client gifts", "§6.2 step 5 g-k (T&E policy)")
R_LINE = ("6", "For each line item, update the", "§6.2 step 6 (approved / denied amounts)")
R_TOTALS = ("7", "Name]-[Date of Submission]): Add together", "§6.2 step 7 (report totals)")
R_ALL_OK = ("8", "a. Add the comment", "§6.2 step 8 (all approved)")
R_PARTIAL = ("9", "a. Add the comment", "§6.2 step 9 (denials under $200)")
R_DENIED = ("10", "Vanguard Shield Mutual — Core Operations SOP a. Add the comment", "§6.2 step 10 (denials over $200)")
R_B2 = ("7.3", "Vanguard Shield Mutual — Core Operations SOP Template B-2", "Template B-2")
R_B2_END = ("7.3", "Action Taken: Expenses report", "Template B-2 (end)")
R_FIELDS = ("1.3", "OPS-HR-TE custom fields", "§1.3 OPS-HR-TE fields")
R_DIRECTORY = ("1.2", "People Directory.xlsx", "§1.2 People Directory")

BOOK_RX = r"(^|/)expense_reports\.xlsx$"
HEADER = ["Jira Key", "Date of Purchase", "Merchant", "Amount", "Expense Category", "Approved Amount",
          "Denied Amount", "Denial Reason"]
SUMMARY = ["Jira Key", "Total Approved", "Total Denied", "Final Status", "Manager Notified", "Comments"]
CATEGORIES = ("staff expense", "client relations expense")
MBJ = "Missing business justification. Please submit personal reimbursement."
MILE_RATE = 0.725

# Line items per report from the Jira seed: key -> amount in USD, or ("miles", n) for self-reported mileage.
REPORTS = {
    "Amina Hassan": ("OPS-18", {
        "OPS-1": 43.89, "OPS-2": 63.18, "OPS-3": 46.86, "OPS-4": 389.75, "OPS-5": 24.75, "OPS-6": 27.01,
        "OPS-7": 541.33, "OPS-8": 24.75, "OPS-9": 18.74, "OPS-10": 45.75, "OPS-11": 24.48, "OPS-12": 28.67,
        "OPS-13": 747.49, "OPS-14": 59.80, "OPS-15": 22.55, "OPS-16": 33.02, "OPS-17": 2098.94}),
    "Priya Natarajan": ("OPS-39", {
        "OPS-33": 16.59, "OPS-34": ("miles", 200), "OPS-35": 21.40, "OPS-36": 16.05, "OPS-37": 20.33,
        "OPS-38": 1471.96}),
    "Leila Rahimi": ("OPS-57", {
        "OPS-40": 119.54, "OPS-41": 47.96, "OPS-42": 384.40, "OPS-43": 10.69, "OPS-44": 21.72, "OPS-45": 12.40,
        "OPS-46": 28.94, "OPS-47": 37.76, "OPS-48": 12.35, "OPS-49": 24.81, "OPS-50": 308.61, "OPS-51": 12.13,
        "OPS-52": 26.13, "OPS-53": 49.06, "OPS-54": 1916.99, "OPS-55": 57.00, "OPS-56": 11.85}),
    "Hiroshi Tanaka": ("OPS-74", {
        "OPS-58": 38.59, "OPS-59": ("miles", 357), "OPS-60": 9.10, "OPS-61": 21.22, "OPS-62": 45.20,
        "OPS-63": 10.47, "OPS-64": 26.40, "OPS-65": 33.07, "OPS-66": 11.02, "OPS-67": 26.13, "OPS-68": 11.85,
        "OPS-69": 25.63, "OPS-70": 39.69, "OPS-71": 1916.99, "OPS-72": 11.30, "OPS-73": ("miles", 360)}),
    "Carlos Mendez": ("OPS-32", {
        "OPS-19": 384.40, "OPS-20": 46.86, "OPS-21": 28.11, "OPS-22": 48.23, "OPS-23": 32.00, "OPS-24": 24.25,
        "OPS-25": 46.86, "OPS-26": 21.22, "OPS-27": 43.55, "OPS-28": 13.73, "OPS-29": 36.93, "OPS-30": 43.55,
        "OPS-31": 1916.99}),
}
# Clients present (or merchant Shopify) -> Client Relations Expense; other unambiguous lines -> Staff Expense.
CLIENT_RELATIONS = {"OPS-1", "OPS-7", "OPS-13", "OPS-40", "OPS-50"}
CATEGORY_UNSURE = {"OPS-23"}
# Receipt dates that differ from the Jira line item (step 1e: correct the line item to the receipt).
RECEIPT_DATES = {"OPS-3": (dt.date(2026, 5, 6), "Blackstone Chophouse receipt is dated 05/06/2026"),
                 "OPS-13": (dt.date(2026, 5, 7), "Melody Bistro receipt is dated Thursday, May 7, 2026")}
PRIYA_DENIED = (1691.33, 1546.33)  # with / without the 200-mile mileage line ($145.00)
SHOPIFY = {"OPS-1": "Shopify cart c1001 (2026-04-23, Amina Hassan, Custom Pens, $43.89)",
           "OPS-40": "Shopify cart c1002 (2026-04-21, Leila Rahimi, Engraved Leather Notebooks, $119.54)"}
NOT_DENIED_WHY = {
    "Amina Hassan": "the client dinners are within the $150-per-participant client dinner limit (Asgard $541.33 / 4 "
                    "= $135.33; Melody Bistro $747.49 / 6 = $124.58), the Hyatt stay ($2,098.94 / 3 nights) is "
                    "within the $700/night Partner limit and the other items are within the staff limits",
    "Carlos Mendez": "only the Art Institute of Chicago admission ($32.00, staff leisure without clients) is denied; "
                     "every other item is a Chicago conference expense within the staff limits",
    "Hiroshi Tanaka": "every item is a Chicago conference expense within policy (mileage 357 and 360 miles are each "
                      "under the 500 miles/day cap on the day before / after the event; meals under $100/day)",
}


# ---- workbook parsing ---------------------------------------------------------------------------------------

def _num(v):
    s = str(v or "").strip()
    if s.startswith("="):
        return "formula"
    s = re.sub(r"\s*(?:miles?|mi)\.?$", "", s, flags=re.I)
    return num(s) if s else None


def _date(v) -> dt.date | None:
    s = str(v or "").strip()
    for rx, order in ((r"^(\d{4})-(\d{1,2})-(\d{1,2})", "ymd"), (r"^(\d{1,2})/(\d{1,2})/(\d{2,4})", "mdy")):
        m = re.match(rx, s)
        if m:
            a, b, c = (int(x) for x in m.groups())
            y, mo, d = (a, b, c) if order == "ymd" else (c if c > 99 else 2000 + c, a, b)
            try:
                return dt.date(y, mo, d)
            except ValueError:
                return None
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%A, %B %d, %Y"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _dollars(spec) -> float:
    return round(spec[1] * MILE_RATE, 2) if isinstance(spec, tuple) else spec


def _parse(grid: list[list[str]]) -> dict:
    """Line-item rows and Report Summary values of one employee sheet."""
    rows = [[str(c or "").strip() for c in r] for r in grid]
    out = {"header": None, "lines": {}, "line_rows": [], "summary_row": None, "summary": {}, "dupes": []}
    h = next((i for i, r in enumerate(rows) if r and norm(r[0]) == "jira key" and len([c for c in r if c]) > 2), None)
    if h is None:
        return out
    out["header"] = rows[h][:len(HEADER)]
    i = h + 1
    while i < len(rows) and any(rows[i]):
        r = rows[i] + [""] * len(HEADER)
        key = r[0].upper().replace(" ", "")
        if re.fullmatch(r"OPS-\d+", key):
            if key in out["lines"]:
                out["dupes"].append(key)
            out["lines"][key] = dict(zip(HEADER, r[:len(HEADER)]))
            out["line_rows"].append(i)
        i += 1
    lab = lambda c: norm(c).rstrip(":").strip()
    s = next((j for j in range(h + 1, len(rows)) if rows[j] and lab(rows[j][0]) == "report summary"), None)
    out["summary_row"] = s
    if s is not None:
        for r in rows[s + 1:]:
            if r and lab(r[0]) in [norm(x) for x in SUMMARY] and lab(r[0]) not in out["summary"]:
                out["summary"][lab(r[0])] = r[1] if len(r) > 1 else ""
    return out


def _sheets(ctx: Context) -> tuple[str | None, dict]:
    return ctx.memo("t177.sheets", lambda: _load(ctx))


def _load(ctx: Context):
    path, book = world(ctx).book(BOOK_RX)
    if not book or "__error__" in book:
        return path, {}
    return path, {norm(name): (name, _parse(grid)) for name, grid in book.items()}


def _employee_sheets(ctx: Context):
    _, sheets = _sheets(ctx)
    for emp, (report, items) in REPORTS.items():
        hit = sheets.get(norm(emp))
        if hit:
            yield emp, report, items, hit[1]


# ---- completion checks ----------------------------------------------------------------------------------------

def file_checks(ctx: Context):
    path, book = world(ctx).book(BOOK_RX)
    if not path:
        yield (False, "expense_reports.xlsx has not been created yet. Per the user's instruction it must hold, for "
                      "each of the 5 reports submitted today (OPS-18 Amina Hassan, OPS-39 Priya Natarajan, OPS-57 "
                      "Leila Rahimi, OPS-74 Hiroshi Tanaka, OPS-32 Carlos Mendez), the final state of every Jira "
                      "field and comment after following SOP §6.2: one worksheet per employee named "
                      "\"First Last\", line-item columns " + " | ".join(HEADER) + ", then one blank row, "
                      "\"Report Summary\" in column A and the rows " + ", ".join(SUMMARY) + " (label in A, value in B).",
               [R_LINE, R_TOTALS])
        return
    if "__error__" in (book or {}):
        yield (False, f"{path} cannot be opened as a workbook: {book['__error__']}", [R_LINE])
        return
    names = list(book)
    want = {norm(e): e for e in REPORTS}
    missing = [e for k, e in want.items() if k not in {norm(n) for n in names}]
    extra = [n for n in names if norm(n) not in want]
    yield (not missing, f"{path}: missing worksheet(s) {missing}. The user asked for one worksheet per employee named "
                        "with the employee's first and last name (e.g. \"Priya Natarajan\").", [R_LINE])
    yield (not extra, f"{path}: worksheet(s) {extra} are not employee sheets. The user asked for exactly one "
                      f"worksheet per employee ({', '.join(REPORTS)}); remove or rename the others.", [R_LINE])


def line_checks(ctx: Context):
    for emp, report, items, p in _employee_sheets(ctx):
        if p["header"] is None:
            yield (False, f"Sheet \"{emp}\": no line-item header row starting with \"Jira Key\". Use the columns "
                          + " | ".join(HEADER) + " (columns A-H).", [R_LINE])
            continue
        got = [norm(x) for x in p["header"]]
        yield (got == [norm(x) for x in HEADER],
               f"Sheet \"{emp}\": line-item header must be exactly " + " | ".join(HEADER)
               + f" in columns A-H (got {' | '.join(p['header'])}).", [R_LINE])
        lines = p["lines"]
        miss = [k for k in items if k not in lines]
        extra = [k for k in lines if k not in items]
        yield (not miss, f"Sheet \"{emp}\": no row for line item(s) {', '.join(miss)} of {report}. Add one row per "
                         f"line-item subtask ({', '.join(items)}).", [R_REVIEW, R_LINE])
        yield (not extra, f"Sheet \"{emp}\": {', '.join(extra)} are not line items of {report} (expected "
                          f"{', '.join(items)}).", [R_LINE])
        yield (not p["dupes"], f"Sheet \"{emp}\": line item(s) {', '.join(p['dupes'])} appear more than once; "
                               "one row per line item.", [R_LINE])
        for key, spec in items.items():
            row = lines.get(key)
            if not row:
                continue
            usd = _dollars(spec)
            amt, ap, de = _num(row["Amount"]), _num(row["Approved Amount"]), _num(row["Denied Amount"])
            if isinstance(spec, tuple):
                ok_amt = amt == "formula" or (isinstance(amt, float) and min(abs(amt - usd), abs(amt - spec[1])) < 0.011)
                want_amt = f"{spec[1]} miles (= ${usd:,.2f} at 72.5 cents/mile)"
            else:
                ok_amt = amt == "formula" or (isinstance(amt, float) and abs(amt - usd) < 0.006)
                want_amt = f"${usd:,.2f}"
            yield (ok_amt, f"Sheet \"{emp}\" {key}: Amount must be {want_amt} as on the line item / receipt "
                           f"(got \"{row['Amount']}\").", [R_REVIEW])
            yield (ap is not None and de is not None,
                   f"Sheet \"{emp}\" {key}: fill both Approved Amount and Denied Amount - the field that does not "
                   "apply is set to 0, never left blank.", [R_LINE])
            if isinstance(ap, float) and isinstance(de, float):
                yield (abs(ap + de - usd) < 0.011,
                       f"Sheet \"{emp}\" {key}: Approved Amount + Denied Amount must equal the item amount "
                       f"${usd:,.2f}" + (f" ({spec[1]} miles x $0.725)" if isinstance(spec, tuple) else "")
                       + f" (got {ap:,.2f} + {de:,.2f}).", [R_LINE])
                reason = row["Denial Reason"]
                if de > 0.004:
                    yield (bool(reason.strip()), f"Sheet \"{emp}\" {key}: ${de:,.2f} is denied but Denial Reason is "
                                                 "blank. State the violated policy, or the standard note \"" + MBJ
                                                 + "\".", [R_LINE])
                else:
                    yield (not reason.strip(), f"Sheet \"{emp}\" {key}: the item is fully approved, so Denial Reason "
                                               f"must be blank (got \"{reason}\").", [R_LINE])
            r = norm(row["Denial Reason"])
            if "missing business justification" in r:
                yield (norm(MBJ) in r, f"Sheet \"{emp}\" {key}: the standard note must read exactly \"{MBJ}\" "
                                       f"(got \"{row['Denial Reason']}\").", [R_LINE])
            cat = norm(row["Expense Category"])
            yield (cat in CATEGORIES, f"Sheet \"{emp}\" {key}: Expense Category must be \"Staff Expense\" or "
                                      f"\"Client Relations Expense\" (got \"{row['Expense Category']}\").", [R_CATEG])


def decision_checks(ctx: Context):
    for emp, report, items, p in _employee_sheets(ctx):
        lines = p["lines"]
        for key in items:
            row = lines.get(key)
            if not row:
                continue
            cat = norm(row["Expense Category"])
            if key in CLIENT_RELATIONS:
                yield (cat == "client relations expense",
                       f"Sheet \"{emp}\" {key}: Expense Category must be \"Client Relations Expense\" "
                       "(clients are listed on the expense, or the merchant is Shopify).", [R_CATEG])
            elif key not in CATEGORY_UNSURE and cat in CATEGORIES:
                yield (cat == "staff expense", f"Sheet \"{emp}\" {key}: Expense Category must be \"Staff Expense\" "
                                               "(no clients on this expense; meals/travel/lodging/mileage for staff).",
                       [R_CATEG])
            if key in RECEIPT_DATES:
                want, why = RECEIPT_DATES[key]
                got = _date(row["Date of Purchase"])
                yield (got == want, f"Sheet \"{emp}\" {key}: Date of Purchase must be corrected to the receipt: "
                                    f"{want.month}/{want.day}/{want.year} ({why}; Jira shows a different date).",
                       [R_REVIEW])
            if key in SHOPIFY:
                de = _num(row["Denied Amount"])
                if isinstance(de, float):
                    yield (de < 0.005, f"Sheet \"{emp}\" {key}: the purchase matches {SHOPIFY[key]}, so it is "
                                       "verified and within policy - approve the full amount (Denied Amount 0).",
                           [R_RETAIL, R_LINE])
        if emp == "Priya Natarajan":
            for key, spec in items.items():
                row = lines.get(key)
                ap = _num(row["Approved Amount"]) if row else None
                if isinstance(ap, float):
                    yield (ap < 0.005,
                           f"Sheet \"{emp}\" {key}: must be fully denied (Approved Amount 0, Denied Amount "
                           f"${_dollars(spec):,.2f}). Priya cancelled her conference travel (email 'Out', May 4) and "
                           "all her receipts are in Fort Wayne, IN; the only calendar event (GCM conference) is in "
                           "Chicago, so no business event matches the date and city.", [R_TIME, R_LINE])
        if emp == "Carlos Mendez" and lines.get("OPS-23"):
            row = lines["OPS-23"]
            ap, de = _num(row["Approved Amount"]), _num(row["Denied Amount"])
            ok = isinstance(ap, float) and isinstance(de, float) and ap < 0.005 and abs(de - 32.0) < 0.006
            yield (ok and norm(MBJ) in norm(row["Denial Reason"]),
                   f"Sheet \"{emp}\" OPS-23 (Art Institute of Chicago, $32.00): staff leisure/cultural activity "
                   f"without clients is not reimbursable - Approved 0, Denied 32.00, Denial Reason \"{MBJ}\".",
                   [R_POLICY2, R_LINE])
        if emp == "Leila Rahimi" and lines.get("OPS-50"):
            row = lines["OPS-50"]
            ap, de = _num(row["Approved Amount"]), _num(row["Denied Amount"])
            ok = isinstance(ap, float) and isinstance(de, float) and abs(ap - 192.88) < 0.03 and abs(de - 115.73) < 0.03
            yield (ok, f"Sheet \"{emp}\" OPS-50 (Lock & Lantern, 8 units at $38.58 incl. tax, $308.61): 5 listed "
                       "attendees (submitter Leila Rahimi + Hiroshi Tanaka + Mona Ashford, Larry Ashford, Mei Lin) "
                       "-> Approved $192.88, the 3 extra units are denied at the per-unit rate -> Denied $115.73 "
                       f"(got approved \"{row['Approved Amount']}\", denied \"{row['Denied Amount']}\").",
                   [R_POLICY2, R_SHARED, R_LINE])
        if emp in NOT_DENIED_WHY:
            den = [_num(r["Denied Amount"]) for r in lines.values()]
            if den and all(isinstance(x, float) for x in den):
                yield (sum(den) < 200, f"Sheet \"{emp}\": {report} totals ${sum(den):,.2f} denied, but its denials "
                                       f"cannot reach $200: {NOT_DENIED_WHY[emp]}. Re-check the denied items.",
                       [R_POLICY, R_POLICY2])


def _status_for(denied: float) -> str | None:
    if denied < 0.005:
        return "Approved"
    if denied < 200:
        return "Partially Approved"
    return "Denied" if denied > 200 else None


def summary_checks(ctx: Context):
    for emp, report, items, p in _employee_sheets(ctx):
        if p["summary_row"] is None:
            yield (False, f"Sheet \"{emp}\": add \"Report Summary\" in column A one blank row after the last line "
                          "item, followed by the rows " + ", ".join(SUMMARY) + " (label in column A, value in B).",
                   [R_TOTALS])
            continue
        if p["line_rows"]:
            last = max(p["line_rows"])
            yield (p["summary_row"] == last + 2,
                   f"Sheet \"{emp}\": \"Report Summary\" must be in column A exactly one blank row after the last "
                   f"line item (row {last + 3}; found in row {p['summary_row'] + 1}).", [R_TOTALS])
        s = p["summary"]
        miss = [x for x in SUMMARY if norm(x) not in s]
        yield (not miss, f"Sheet \"{emp}\": Report Summary is missing row(s) {miss} (label in column A, value in "
                         "column B).", [R_TOTALS])
        if "jira key" in s:
            yield (s["jira key"].strip().upper() == report,
                   f"Sheet \"{emp}\": Report Summary Jira Key must be the expense report issue {report} "
                   f"(got \"{s['jira key']}\").", [R_TOTALS])
        lines = p["lines"]
        aps = [_num(r["Approved Amount"]) for r in lines.values()]
        des = [_num(r["Denied Amount"]) for r in lines.values()]
        exact = lines and all(isinstance(x, float) for x in aps + des)
        ta, td = _num(s.get("total approved")), _num(s.get("total denied"))
        if exact and isinstance(ta, float):
            yield (abs(ta - sum(aps)) < 0.011, f"Sheet \"{emp}\": Total Approved must be the sum of the line-item "
                                               f"Approved Amounts ${sum(aps):,.2f} (got {s.get('total approved')}).",
                   [R_TOTALS])
        if exact and isinstance(td, float):
            yield (abs(td - sum(des)) < 0.011, f"Sheet \"{emp}\": Total Denied must be the sum of the line-item "
                                               f"Denied Amounts ${sum(des):,.2f} (got {s.get('total denied')}).",
                   [R_TOTALS])
        denied = sum(des) if exact else (td if isinstance(td, float) else None)
        if denied is None:
            continue
        status = _status_for(denied)
        if status is None:
            continue
        ref = {"Approved": R_ALL_OK, "Partially Approved": R_PARTIAL, "Denied": R_DENIED}[status]
        if "final status" in s:
            yield (norm(s["final status"]) == norm(status),
                   f"Sheet \"{emp}\": total denials ${denied:,.2f} -> Final Status must be \"{status}\" "
                   f"(got \"{s['final status']}\").", [ref])
        if "comments" in s:
            c = norm(s["comments"])
            if status == "Approved":
                want, ok = "T&E review complete. All expenses approved.", "t&e review complete. all expenses approved" in c
            elif status == "Partially Approved":
                want = "T&E review complete. Expenses approved except where noted."
                ok = "t&e review complete. expenses approved except where noted" in c
            else:
                want = f"T&E review complete. Denied expenses: ${denied:,.2f}."
                ok = bool(re.search(r"t&e review complete\. denied expenses:\s*" + money_rx(denied), c))
            yield (ok, f"Sheet \"{emp}\": Comments must carry the parent-ticket comment \"{want}\" "
                       f"(got \"{s['comments']}\").", [ref])
        if "manager notified" in s:
            yn = norm(s["manager notified"])
            want_yn = "Y" if status == "Denied" else "N"
            yield (yn in ({"y", "yes"} if want_yn == "Y" else {"n", "no"}),
                   f"Sheet \"{emp}\": Manager Notified must be {want_yn} - the B-2 manager flag in #finance-approvals "
                   f"is sent only for Denied reports (status here: {status}).", [R_DENIED])


def directory_unchanged(ctx: Context):
    changed = world(ctx).changed_files(keep_rx=BOOK_RX)
    yield (not changed, f"{', '.join(changed)} was modified. Source files (People Directory.xlsx) are read-only "
                        "for this task; restore it.", [R_DIRECTORY])


# ---- Slack: Template B-2 ----------------------------------------------------------------------------------------

def _slack(a: Action) -> bool:
    return a.kind in ("slack_post", "slack_dm")


def _in_fin(a: Action) -> bool:
    return str(a.channel or "").lstrip("#").lower() in ("c001", "finance-approvals")


def _about(name_rx: str):
    def about(a: Action) -> bool:
        t = a.text or ""
        return _slack(a) and bool(re.search(name_rx, t, re.I)) and bool(
            re.search(r"review flag", t, re.I) or (_in_fin(a) and re.search(r"\bdenied\b", t, re.I)))
    return about


def specs(ctx: Context) -> list[Comm]:
    denied_rx = "(?:" + "|".join(money_rx(v) for v in PRIYA_DENIED) + ")"
    out = [Comm(
        key="b2_natarajan", kind="slack_post", about=_about(r"Priya\s+Natarajan|\bOPS-39(?!\d)"),
        what="Template B-2 T&E Review Flag for Priya Natarajan's Denied report OPS-39",
        refs=[R_DENIED, R_B2, R_B2_END], channel="finance-approvals",
        body=[(r"(?:@\s*(?:Layla\s+Zahra|l_zahra)\b|<@U072>)",
               "addressed to her Reporting Manager per People Directory.xlsx: @Layla Zahra (l_zahra)"),
              (r"T&E Review Flag\s*[-–—]\s*Priya Natarajan", "\"T&E Review Flag - Priya Natarajan\""),
              (r"Expense Date\(s\):", "\"Expense Date(s): <dates>\""),
              (r"Total Amount Approved:\s*\$?\s*0(?:\.0{1,2})?(?![\d.,]*\d)",
               "\"Total Amount Approved: $0.00\" (every OPS-39 line is invalid: Fort Wayne receipts, no business "
               "event there)"),
              (r"Total Amount Denied:\s*" + denied_rx,
               "\"Total Amount Denied: $1,691.33\" (receipts $1,546.33 + 200 miles x $0.725 = $145.00)"),
              (r"Merchant\(s\):(?:(?!Details:).)*mileage reimbursement",
               "\"mileage reimbursement\" listed under Merchant(s) (denied self-drive mileage, Template B-2 note)"),
              (r"Details:\s*Expense\(s\) submitted without business justification",
               "\"Details: Expense(s) submitted without business justification.\""),
              (r"Action Taken:\s*Expenses report\s*(?:OPS-39|OPS-HR-TE-Natarajan\S*)\s*denied\.?\s*"
               r"Please review with your direct report",
               "\"Action Taken: Expenses report OPS-39 denied. Please review with your direct report.\"")],
        max_count=1)]
    for emp, why in NOT_DENIED_WHY.items():
        report = REPORTS[emp][0]
        out.append(Comm(
            key=f"b2_{emp.split()[-1].lower()}", kind="slack_post",
            about=_about(re.escape(emp).replace(r"\ ", r"\s+") + rf"|\b{report}(?!\d)"),
            what=f"Template B-2 flag for {emp} ({report})", refs=[R_DENIED, R_PARTIAL, R_B2],
            forbidden=f"Template B-2 goes to #finance-approvals only for reports whose total denials exceed $200 "
                      f"(status Denied). {emp}'s report {report} is not Denied: {why}. Do not post a B-2 flag for it.",
            required=False))
    return out


# ---- pre rules ----------------------------------------------------------------------------------------------------

def _jira_write(ctx: Context, a: Action):
    if not a.kind.startswith("jira_"):
        return None
    return ("[no Jira updates] The user asked you NOT to update the Jira issues (fields, comments, statuses). Record "
            "the final state each SOP §6.2 update would produce in expense_reports.xlsx instead; reading Jira is fine.")


RULES = (
    state_rule("report.file", file_checks, "Create / fix expense_reports.xlsx as described.")
    + state_rule("report.lines", line_checks, "Fix the listed line-item cells in expense_reports.xlsx.")
    + state_rule("report.decisions", decision_checks, "Correct the listed decisions in expense_reports.xlsx.")
    + state_rule("report.summary", summary_checks, "Fix the Report Summary section as listed.")
    + state_rule("files.directory_unchanged", directory_unchanged, "Restore the original file.")
    + comm_rules("slack.b2", specs)
    + no_placeholders([R_B2])
    + pre_rule("jira.no_updates", _jira_write, [R_LINE, R_TOTALS, R_FIELDS],
               "Do not call Jira write tools; put the values in expense_reports.xlsx.")
    # People Directory.xlsx is checked at completion only: unresolved .save() targets fall back to every
    # referenced workbook, which would wrongly attribute a write to it.
    + forbid_writes("files.no_source_edits", r"^SOP\.pdf$|^OPS-HR-TE-.*\.pdf$",
                    "the SOP and the receipt PDFs are source documents and stay unchanged.", [R_REVIEW])
)
