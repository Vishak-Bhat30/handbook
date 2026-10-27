"""Verifiers for finance_sunshine_set_6b9398f4 (Sunshine & Set Automotive accounting SOP).

Task: Jasmine Patel finishes posting Deal 4821 (Mitchell, 2025 Honda Accord EX-L, N-2547, Ally Financial),
logs it in the funding tracker for CIT follow-up, routes the funding package to Noah Alvarez and starts title
work with Priya Bennett. Expected values come from the seed deal jacket (buyer's order, RIC, desk recap,
Ally stip sheet) and the SOP: total gross $5,640 > $5,000 -> high-gross notice in #acct-deal-posting tagging
@marcus.hale before the deal-log status update (2.1) and a 2-business-day expected funding window (2.2).
"""

from __future__ import annotations

import datetime as dt
import re

from ..kit import (COMM_KINDS, WRITE_KINDS, Action, Comm, Context, blank, book_eq, comm_rules, dashes,
                   forbid_writes, nh, no_placeholders, num, pdf_text, pre_rule, state_rule, strict_writes, world)
from .. import config

DEAL = "4821"
TODAY = dt.date(2026, 4, 14)
UNKNOWN = object()
BAD = object()

R_COMM = ("1.5", "Use the correct Slack channel for routine internal questions.", "1.5 Communication Rules")
R_JACKET = ("2.1", "Compile the deal jacket into a single PDF document.", "2.1 Deal Jacket Intake and Posting")
R_RECORD = ("2.1", "Record the deal in the deal log.", "2.1 Deal Jacket Intake and Posting")
R_TIE = ("2.1", "Tie deal gross to the approved desking", "2.1 Deal Jacket Intake and Posting")
R_NOTICE = ("2.1", "In addition, for any deal where total approved gross exceeds $5,000",
            "2.1 high-gross confirmation notice")
R_TPL_A = ("2.1", "When a deal gross variance requires Sales or F&I correction", "2.1 Template A")
R_ROUTE = ("2.2", "After posting, route funding documents", "2.2 Funding and Contracts in Transit")
R_WINDOW = ("2.2", "When calculating the expected funding date", "2.2 expected funding date")
R_TPL_B = ("2.2", "When submitting a lender funding package, send a cover email using Template B", "2.2 Template B")
R_REMIND = ("2.2", "Set a Calendar reminder for the expected funding date", "2.2 funding reminder")
R_TITLE = ("2.3", "Separate title work from funding work", "2.3 Titles and Registration")
R_AUDIT = ("9.4", "Every accounting process must leave an audit trail", "9.4 File and Naming Standards")
R_TAX = ("10.1", "Sales tax is calculated on the net purchase price", "10.1 Florida Sales Tax")
R_DOC = ("10.3", "The dealership charges a flat documentation fee", "10.3 Doc Fee")
R_TPLS = ("10.5", "The following email templates are referenced", "Appendix A")
R_TPL_B_TEXT = ("10.5", "Subject: Funding Package", "Template B")
R_TPL_A_TEXT = ("10.5", "Subject: Deal Gross Variance", "Template A")

MARCUS_TAG = r"@marcus[ ._]?hale|<@U002>"
NOAH_TAG = r"@noah[ ._]?alvarez|<@U004>"
PRIYA_TAG = r"@priya[ ._]?bennett|<@U005>"
JACKET_NAME = "20260414_4821_Mitchell_112847.pdf"
JACKET_RX = r"20260414[\W_]*4821[\W_]*mitchell[\W_]*112847[^/]*\.pdf$"
JACKET_DOCS = [(r"TOTAL PURCHASE PRICE", "01 buyer's order"), (r"TRUTH IN LENDING", "02 retail installment contract"),
               (r"COVERAGE SUMMARY", "04 proof of insurance"),
               (r"PHYSICAL DELIVERY ITEMS", "05 delivery checklist"), (r"PRODUCTS PRESENTED", "06 F&I menu"),
               (r"STIPULATION STATUS", "07 Ally stip sheet")]


# ---- helpers -------------------------------------------------------------------------------------

def _letters(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _date(v):
    s = str(v or "").strip()
    if not s or s in ("None", "nan"):
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return dt.date(*map(int, m.groups()))
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2,4})$", s)
    if m:
        y = int(m.group(3))
        return dt.date(y + 2000 if y < 100 else y, int(m.group(1)), int(m.group(2)))
    try:
        return dt.datetime.strptime(s, "%B %d, %Y").date()
    except ValueError:
        pass
    try:
        return dt.datetime.strptime(s, "%b %d, %Y").date()
    except ValueError:
        pass
    n = num(s)
    if n is not None and 40000 < n < 60000:
        return dt.date(1899, 12, 30) + dt.timedelta(days=int(n))
    return UNKNOWN if s.startswith("=") else BAD


def add_bd(d: dt.date, n: int, holidays=frozenset()) -> dt.date:
    while n:
        d += dt.timedelta(days=1)
        if d.weekday() < 5 and d not in holidays:
            n -= 1
    return d


class Table:
    """First sheet of a workbook as rows keyed by header, with a same-sheet formula evaluator."""

    def __init__(self, key: str, sheets: dict):
        self.key = key
        grid = next(iter(sheets.values()), []) if isinstance(sheets, dict) else []
        self.grid = grid
        self.header, self.start = [], len(grid)
        for i, row in enumerate(grid):
            if any(nh(c) == "Deal #" for c in row):
                self.header, self.start = [nh(c) for c in row], i + 1
                break

    def rows(self) -> list[dict]:
        out = []
        for j, r in enumerate(self.grid[self.start:], start=self.start + 1):
            if any(str(c).strip() not in ("", "None") for c in r):
                d = dict(zip(self.header, (str(c) for c in r)))
                d["__row__"] = j
                out.append(d)
        return out

    def deal_rows(self, deal: str) -> list[dict]:
        return [r for r in self.rows() if num(str(r.get("Deal #", "")).lstrip("=")) == float(deal)]

    def cell(self, ref: str):
        m = re.fullmatch(r"\$?([A-Z]{1,3})\$?(\d+)", ref)
        col = 0
        for ch in m.group(1):
            col = col * 26 + ord(ch) - 64
        r = int(m.group(2)) - 1
        row = self.grid[r] if 0 <= r < len(self.grid) else []
        return row[col - 1] if col - 1 < len(row) else ""

    def value(self, row: dict, col: str, depth: int = 0):
        """Numeric value of a cell (formulas of +,-,*,/ and IF(x="","",expr) evaluated); None = blank."""
        v = str(row.get(col, "")).strip()
        return self._eval(v, depth)

    def _eval(self, v: str, depth: int = 0):
        if blank(v):
            return None
        if not v.startswith("="):
            n = num(v)
            return n if n is not None else BAD
        if depth > 5:
            return UNKNOWN
        expr = v[1:].strip()
        m = re.fullmatch(r'IF\(\s*(\$?[A-Z]{1,3}\$?\d+)\s*=\s*""\s*,\s*""\s*,\s*(.+)\)', expr, re.I)
        if m:
            if blank(self.cell(m.group(1).upper())):
                return None
            expr = m.group(2)
        bad = False

        def sub(mm):
            nonlocal bad
            x = self._eval(str(self.cell(mm.group(0).upper())), depth + 1)
            if x is UNKNOWN or x is BAD:
                bad = True
                return "0"
            return repr(float(x or 0))
        expr = re.sub(r"\$?[A-Za-z]{1,3}\$?\d+", sub, expr)
        if bad or not re.fullmatch(r"[\d.+\-*/() eE]+", expr):
            return UNKNOWN
        try:
            return float(eval(expr, {"__builtins__": {}}, {}))  # noqa: S307 - digits/operators only
        except Exception:
            return UNKNOWN


def _pick(ctx: Context, base_rx: str) -> Table | None:
    """The workbook the agent maintains: the original if edited, else a newly saved copy (e.g. *_v2)."""
    w = world(ctx)
    cur, init = w.current or {}, w.initial or {}
    keys = sorted(k for k in cur if re.search(base_rx, k.split("/")[-1], re.I) and isinstance(cur[k], dict)
                  and "__error__" not in cur[k])
    if not keys:
        return None
    changed = [k for k in keys if k in init and not book_eq(cur[k], init[k])]
    created = sorted((k for k in keys if k not in init), reverse=True)
    cands = [Table(k, cur[k]) for k in changed + created]
    for t in cands:
        rows = t.deal_rows(DEAL)
        if rows and not blank(rows[0].get("Post Date", "x")):
            return t
    if cands:
        return cands[0]
    orig = next((k for k in keys if k in init), keys[0])
    return Table(orig, cur[orig])


def _initial(ctx: Context, name: str) -> Table | None:
    init = world(ctx).initial or {}
    return Table(name, init[name]) if isinstance(init.get(name), dict) else None


def _num_ok(t: Table, row: dict, col: str, want: float, tol: float = 0.006) -> bool:
    v = t.value(row, col)
    return v is UNKNOWN or (isinstance(v, float) and abs(v - want) < tol)


def _show(row: dict, col: str) -> str:
    return f"\"{row.get(col, '')}\""


def _cal_date(a: Action) -> str:
    s = a.args.get("start")
    if isinstance(s, dict):
        s = s.get("date") or s.get("dateTime") or ""
    return str(s or "")[:10]


def expected_funding(ctx: Context) -> dt.date:
    """Package sent today (Ally SecureLink deadline EOB 4/14) + 2 business days (gross $5,640 > $5,000)."""
    return add_bd(TODAY, 2, frozenset(ctx.sop.holidays))


def _is_notice_post(ctx: Context, a: Action) -> bool:
    return (a.kind == "slack_post" and world(ctx).is_channel(a.channel, "acct-deal-posting")
            and DEAL in a.text and bool(re.search(MARCUS_TAG, a.text, re.I)))


def _is_notice(ctx: Context, a: Action) -> bool:
    """A high-gross notice attempt: deal-posting channel post or DM to Marcus about 4821's high gross."""
    w = world(ctx)
    if a.kind not in ("slack_post", "slack_dm") or DEAL not in a.text:
        return False
    where = (w.is_dm_to(a, "Marcus Hale") if w.dm_recipients(a) else
             a.kind == "slack_post" and w.is_channel(a.channel, "acct-deal-posting"))
    what = re.search(r"high[- ]?gross (confirmation|notice)", a.text, re.I) or (
        re.search(MARCUS_TAG, a.text, re.I) and re.search(r"5,?640|high[- ]?gross", a.text, re.I))
    return bool(where and what)


# ---- deal log ------------------------------------------------------------------------------------

DEAL_NUMS = [("Sell Price", 34500, "buyer's order selling price"), ("Doc Fee", 899, "SOP 10.3 doc fee"),
             ("Tax", 2301, "6.5% Orange County on selling price + doc fee, per buyer's order / RIC"),
             ("F&I Products", 2590, "GAP $895 + VSC $1,695"), ("Reserve", 1050, "RIC / Ally reserve"),
             ("Down Pmt", 8625, "check #4492"), ("Amt Financed", 31665, "RIC amount financed"),
             ("Term (mo)", 72, "RIC term"), ("Front Gross", 2000, "desk recap"), ("Back Gross", 3640, "desk recap"),
             ("Total Gross", 5640, "desk recap total approved gross"), ("Desk Recap", 5640, "approved desk recap"),
             ("Variance", 0, "posted gross ties to the desk recap")]


def deal_log_checks(ctx: Context):
    t = _pick(ctx, r"^DealLog")
    refs = [R_RECORD, R_TIE]
    if t is None:
        yield False, "The deal log workbook DealLog_April2026.xlsx is missing.", refs
        return
    rows = t.deal_rows(DEAL)
    if not rows:
        yield False, f"{t.key}: the Deal #4821 row is missing.", refs
        return
    r = rows[0]
    bad = []
    for col, want, why in DEAL_NUMS:
        tol = 1.0 if col == "Tax" else 0.006
        if not _num_ok(t, r, col, want, tol):
            raw, v = str(r.get(col, "")), t.value(r, col)
            got = f"\"{raw}\"" + (f" = {'blank' if v is None else f'{v:g}'}" if raw.startswith("=") else "")
            bad.append(f"{col} = {want:g} ({why}; got {got})")
    apr = t.value(r, "APR")
    if not (apr is UNKNOWN or (isinstance(apr, float) and (abs(apr - 0.0699) < 1e-4 or abs(apr - 6.99) < 0.005))):
        bad.append(f"APR = 0.0699 (6.99% sell rate; got {_show(r, 'APR')})")
    for col, rx, want in (("Stock #", r"^N-?2547$", "N-2547"), ("VIN", r"^1HGCV1F34PA112847$", "1HGCV1F34PA112847"),
                          ("Customer", r"mitchell", "Mitchell, Sarah"), ("Lender", r"^ally", "Ally Financial")):
        if not re.search(rx, nh(r.get(col, "")), re.I):
            bad.append(f"{col} = {want} (got {_show(r, col)})")
    if _date(r.get("Post Date")) not in (TODAY, UNKNOWN):
        bad.append(f"Post Date = 2026-04-14 (got {_show(r, 'Post Date')})")
    if blank(r.get("Posted By")) or isinstance(_date(r.get("Posted By")), dt.date) or num(r.get("Posted By")) is not None:
        bad.append(f"Posted By = J. Patel (got {_show(r, 'Posted By')})")
    fs = nh(r.get("Funding Status", ""))
    if not re.search(r"\bCIT\b|transit|pending fund|awaiting fund|unfunded|routed|submitted", fs, re.I) \
            or re.search(r"pending posting|^funded$", fs, re.I):
        bad.append(f"Funding Status = CIT (contract in transit, not yet funded; got {_show(r, 'Funding Status')})")
    if not blank(r.get("Funding Date")):
        bad.append(f"Funding Date blank (not funded yet; got {_show(r, 'Funding Date')})")
    ts = nh(r.get("Title Status", ""))
    if blank(ts) or re.search(r"not started", ts, re.I) or isinstance(_date(ts), dt.date) or len(ts) > 60:
        bad.append(f"Title Status showing title work started, e.g. \"In Progress\" (got {_show(r, 'Title Status')})")
    if bad:
        yield False, (f"{t.key} row {r['__row__']} (Deal #4821) is not posted per the deal jacket: set "
                      + "; ".join(bad) + "."), refs + ([R_TAX, R_DOC] if any(b.startswith(("Tax", "Doc")) for b in bad) else [])


def deal_log_integrity(ctx: Context):
    t, t0 = _pick(ctx, r"^DealLog"), _initial(ctx, "DealLog_April2026.xlsx")
    if t is None or t0 is None:
        return
    strip = lambda r: tuple(v for k, v in r.items() if k != "__row__")
    cur = [strip(r) for r in t.rows() if not t.deal_rows(DEAL) or r not in t.deal_rows(DEAL)]
    gone = []
    for r in t0.rows():
        if num(str(r.get("Deal #", ""))) == float(DEAL):
            continue
        s = strip(r)
        if s in cur:
            cur.remove(s)
        else:
            gone.append(r.get("Deal #", "?"))
    yield (not gone, f"{t.key}: rows of other deals were changed or removed (Deal # {', '.join(gone)}). Only the "
                     "Deal #4821 row is updated; restore the others exactly.", [R_AUDIT])
    extra = [r.get("Deal #") for r in t.rows() if num(str(r.get("Deal #", "")).lstrip("=")) not in
             {num(str(x.get("Deal #", ""))) for x in t0.rows()}]
    yield (not extra, f"{t.key}: unexpected new deal-log rows (Deal # {', '.join(map(str, extra))}). Deal 4821 already "
                      "has its row (row 8); fill that row instead of adding one.", [R_RECORD])


# ---- funding tracker -----------------------------------------------------------------------------

def tracker_checks(ctx: Context):
    t = _pick(ctx, r"^FundingTracker")
    refs = [R_ROUTE]
    if t is None:
        yield False, "The funding tracker FundingTracker_April2026.xlsx is missing.", refs
        return
    rows = t.deal_rows(DEAL)
    exp = expected_funding(ctx)
    if not rows:
        yield (False, "FundingTracker_April2026.xlsx has no row for Deal #4821. Add it for CIT follow-up: Deal # 4821 | "
                      "Customer Mitchell, Sarah | Stock # N-2547 | VIN 1HGCV1F34PA112847 | Lender Ally Financial | "
                      "Contract Value 31665 | Reserve Est. 1050 | Pkg Sent Date 2026-04-14 | Exp. Funding Date "
                      f"{exp.isoformat()} (2 business days: total gross $5,640 > $5,000) | Days CIT 0 | Missing Stips "
                      "None — all cleared | Fund Confirmed / Fund Amount blank | Exception Status (open, e.g. CIT).",
               refs + [R_WINDOW])
        return
    if len(rows) > 1:
        yield False, f"{t.key}: Deal #4821 is logged {len(rows)} times; keep one row.", refs
    r = rows[0]
    bad = []
    for col, rx, want in (("Customer", r"mitchell", "Mitchell, Sarah"), ("Stock #", r"^N-?2547$", "N-2547"),
                          ("VIN", r"^1HGCV1F34PA112847$", "1HGCV1F34PA112847"), ("Lender", r"^ally", "Ally Financial")):
        if not re.search(rx, nh(r.get(col, "")), re.I):
            bad.append(f"{col} = {want} (got {_show(r, col)})")
    for col, want in (("Contract Value", 31665), ("Reserve Est.", 1050)):
        if not _num_ok(t, r, col, want):
            bad.append(f"{col} = {want} (got {_show(r, col)})")
    sent = _date(r.get("Pkg Sent Date"))
    if sent is not UNKNOWN and sent != TODAY:
        bad.append(f"Pkg Sent Date = 2026-04-14 (Ally SecureLink submission due today; got {_show(r, 'Pkg Sent Date')})")
    got = _date(r.get("Exp. Funding Date"))
    if got is not UNKNOWN and got != exp:
        bad.append(f"Exp. Funding Date = {exp.isoformat()} (package sent date + 2 business days because total gross "
                   f"$5,640 exceeds $5,000 - not Ally's 3-day April 17; got {_show(r, 'Exp. Funding Date')})")
    d = t.value(r, "Days CIT")
    if d is not UNKNOWN and d not in (None, 0):
        bad.append(f"Days CIT = 0 (got {_show(r, 'Days CIT')})")
    if not re.search(r"none|cleared|n/?a", nh(r.get("Missing Stips", "")), re.I):
        bad.append(f"Missing Stips = None — all cleared (Ally cleared 5 of 5; got {_show(r, 'Missing Stips')})")
    for col in ("Fund Confirmed", "Fund Amount"):
        if not blank(r.get(col)):
            bad.append(f"{col} blank (not funded yet; got {_show(r, col)})")
    ex = nh(r.get("Exception Status", ""))
    if blank(ex) or re.search(r"^closed|^funded", ex, re.I):
        bad.append(f"Exception Status = an open CIT status (got {_show(r, 'Exception Status')})")
    if bad:
        yield False, f"{t.key} row {r['__row__']} (Deal #4821): set " + "; ".join(bad) + ".", refs + [R_WINDOW]


def tracker_integrity(ctx: Context):
    t, t0 = _pick(ctx, r"^FundingTracker"), _initial(ctx, "FundingTracker_April2026.xlsx")
    if t is None or t0 is None:
        return
    strip = lambda r: tuple(v for k, v in r.items() if k != "__row__")
    cur = [strip(r) for r in t.rows()]
    gone = []
    for r in t0.rows():
        s = strip(r)
        if s in cur:
            cur.remove(s)
        else:
            gone.append(str(r.get("Deal #", "?")))
    yield (not gone, f"{t.key}: existing tracker rows were changed or removed (Deal # {', '.join(gone)}). Restore them "
                     "and only append the Deal #4821 row.", [R_AUDIT, R_ROUTE])
    extra = sorted({str(r.get("Deal #")) for r in t.rows()
                    if num(str(r.get("Deal #", "")).lstrip("=")) not in {4821.0, 4820.0}
                    and strip(r) not in [strip(x) for x in t0.rows()]})
    yield (not extra, f"{t.key}: rows for deals outside this task were added (Deal # {', '.join(extra)}); remove them.",
           [R_ROUTE])


def calendar_checks(ctx: Context):
    w = world(ctx)
    exp = expected_funding(ctx).isoformat()
    ok = any(DEAL in a.text and re.search(r"fund", a.text, re.I) and _cal_date(a) == exp
             for a in w.calls("calendar_create", "calendar_update"))
    yield (ok, f"No Calendar reminder for Deal #4821's expected funding date. Create one on {exp} (e.g. \"Expected "
               "Funding — Deal #4821 Mitchell / Ally Financial\"; if no funding confirmation by then, start daily "
               "follow-up).", [R_REMIND, R_WINDOW])


def calendar_pre(ctx: Context, a: Action):
    if a.kind not in ("calendar_create", "calendar_update") or DEAL not in a.text or not re.search(r"fund", a.text, re.I):
        return None
    d = _cal_date(a)
    if not d or str(a.args.get("eventId") or a.args.get("event_id") or "") == "cal_002":
        return None
    exp = expected_funding(ctx).isoformat()
    if d == "2026-04-17" or (a.kind == "calendar_create" and re.search(r"expect|funding (date|reminder|follow)",
                                                                        a.text, re.I) and d != exp):
        return (f"The expected funding date for Deal #4821 is {exp}: the package is submitted 2026-04-14 and total gross "
                f"$5,640 exceeds $5,000, so the 2-business-day window applies (Ally's 3-day April 17 does not). "
                f"Got {d}.")
    return None


# ---- hand-offs and messages ----------------------------------------------------------------------

def _to_person(w, a: Action, email: str, name: str, tag_rx: str) -> bool:
    if a.kind in ("email_send",):
        return email in {x.lower() for x in a.recipients + a.cc}
    if a.kind in ("slack_dm", "slack_post") and w.dm_recipients(a):
        return w.is_dm_to(a, name)
    return a.kind == "slack_post" and bool(re.search(tag_rx, a.text, re.I))


def handoff_checks(ctx: Context):
    w = world(ctx)
    sent = w.comms()
    noah = any(_to_person(w, a, "noah.alvarez@sunshineandsetauto.com", "Noah Alvarez", NOAH_TAG)
               and DEAL in f"{a.subject}\n{a.text}" and re.search(r"fund|package|posted", f"{a.subject}\n{a.text}", re.I)
               for a in sent)
    yield (noah, "The Deal #4821 funding package has not been routed to Noah Alvarez (Funding & Contracts Clerk). After "
                 "posting, email noah.alvarez@sunshineandsetauto.com (or tag @noah.alvarez in #acct-contracts-funding) "
                 "that Deal #4821 / Mitchell / Ally Financial is posted and the funding package is ready, with the "
                 "documents.", [R_ROUTE])
    priya = any(_to_person(w, a, "priya.bennett@sunshineandsetauto.com", "Priya Bennett", PRIYA_TAG)
                and DEAL in f"{a.subject}\n{a.text}" and re.search(r"title", f"{a.subject}\n{a.text}", re.I)
                for a in sent)
    yield (priya, "Title work for Deal #4821 has not been started with Priya Bennett (Titles & Billing). Send her the "
                  "title kickoff (Deal #4821, Mitchell, Stock N-2547 / VIN 1HGCV1F34PA112847, lienholder Ally "
                  "Financial, no trade) by email to priya.bennett@sunshineandsetauto.com or Slack.", [R_TITLE])


def _lender_bound(a: Action) -> bool:
    return any(not x.endswith("@sunshineandsetauto.com") for x in a.recipients + a.cc)


def comm_specs(ctx: Context) -> list[Comm]:
    full = lambda a: dashes(f"{a.subject}\n{a.text}")
    return [
        Comm("high_gross_notice", "slack_post", lambda a: _is_notice(ctx, a),
             "high-gross confirmation notice for Deal #4821 (total gross $5,640 > $5,000)", [R_NOTICE],
             channel="acct-deal-posting",
             body=[(MARCUS_TAG, "a tag of @marcus.hale"), (r"#?\s?4821", "deal number 4821"),
                   (r"5,?640", "total gross $5,640.00"),
                   (r"\bti(e|es|ed|ing)\b|tie[- ]?out|\bmatch", "the desk recap tie-out result (ties to the approved "
                                                                "desk recap)"),
                   (r"variance[^\n]{0,40}?(\$\s?0(\.00)?(?![\d,])|\bzero\b|\bnone\b|\b0(\.00)?\b)|(\$\s?0(\.00)?|zero|no)"
                    r"\s+variance", "variance amount $0.00")]),
        Comm("template_a", "email", lambda a: DEAL in full(a) and bool(re.search(r"Deal Gross Variance", full(a), re.I)),
             "Template A deal gross variance email", [R_TPL_A, R_TPL_A_TEXT],
             forbidden="Deal #4821 has no gross variance (posted $5,640.00 ties to the approved desk recap $5,640.00), "
                       "so no Template A correction request applies."),
        Comm("funding_package_cover", "email",
             lambda a: a.kind == "email_send" and bool(re.match(r"\s*Funding Package\b", a.subject, re.I))
             and DEAL in full(a) and (_lender_bound(a) or bool(re.search(r"find the attached funding package",
                                                                         a.text, re.I))),
             "Template B funding package cover email for Deal #4821", [R_TPL_B, R_TPL_B_TEXT, R_TPLS],
             exact_to=False, required=False, max_count=5,
             subject=r"Funding Package – Deal #4821 / Mitchell / Ally( Financial)?",
             subject_hint="Funding Package — Deal #4821 / Mitchell / Ally Financial",
             body=[(r"Deal #:?\s*4821", "Deal #: 4821"), (r"Customer:?\s*Sarah (E\.? )?Mitchell", "Customer: Sarah E. Mitchell"),
                   (r"VIN:?\s*1HGCV1F34PA112847", "VIN: 1HGCV1F34PA112847"),
                   (r"Contract Date:?\s*(April 14,? 2026|0?4/14/(20)?26|2026-04-14)", "Contract Date: April 14, 2026"),
                   (r"Amount Financed:?\s*\$?\s?31,?665(\.00)?", "Amount Financed: $31,665.00"),
                   (r"Reserve:?\s*\$?\s?1,?050(\.00)?", "Reserve: $1,050.00")]),
    ]


def notice_first(ctx: Context, a: Action):
    if a.kind not in WRITE_KINDS or not any(re.search(r"DealLog", f, re.I) for f in strict_writes(a)):
        return None
    if any(_is_notice_post(ctx, x) for x in world(ctx).calls("slack_post")):
        return None
    return ("Deal #4821's total approved gross is $5,640.00 (> $5,000): before updating the deal log status fields, "
            "post the high-gross confirmation notice in #acct-deal-posting tagging @marcus.hale with the deal number, "
            "total gross $5,640.00, the desk recap tie-out result and the variance $0.00.")


def slack_format(ctx: Context, a: Action):
    if a.kind != "slack_post" or world(ctx).dm_recipients(a) or DEAL not in a.text:
        return None
    miss = []
    if not re.search(r"mitchell", a.text, re.I):
        miss.append("customer last name Mitchell")
    if not re.search(r"N-?2547|1HGCV1F34PA112847|112847", a.text, re.I):
        miss.append("the VIN 1HGCV1F34PA112847 or stock number N-2547")
    if not re.search(r"<@U\w+>|@[a-z]+[._][a-z]+", a.text, re.I):
        miss.append("a tag of the responsible person (e.g. @noah.alvarez, @marcus.hale, @priya.bennett)")
    return ("Slack posts about a deal must tag the responsible person and include the deal number, customer last name "
            "and VIN or stock number. Missing: " + "; ".join(miss) + ".") if miss else None


def jacket_checks(ctx: Context):
    w = world(ctx)
    hits = sorted(f for f in w.files() if re.search(JACKET_RX, f.split("/")[-1], re.I))
    if not hits:
        yield False, (f"The Deal #4821 deal jacket has not been compiled into a single PDF. Merge 01_BuyersOrder.pdf ... "
                      f"07_AllyStips.pdf (in order) into one PDF saved in /workdir as {JACKET_NAME} (deal packet name "
                      "YYYYMMDD_Deal#_CustomerLast_VINlast6); keep the source PDFs unchanged."), [R_JACKET, R_AUDIT]
        return
    text = pdf_text(config.workdir() / hits[0])
    if text.strip():
        miss = [d for rx, d in JACKET_DOCS if not re.search(rx, text, re.I)]
        yield (not miss, f"{hits[0]} is missing deal jacket documents: {', '.join(miss)}. Include every jacket PDF "
                         "(01-07).",
               [R_JACKET])


RULES = (
    comm_rules("comms", comm_specs)
    + pre_rule("deal.notice_first", notice_first, [R_NOTICE],
               "Post the high-gross confirmation notice first, then update the deal log.")
    + pre_rule("slack.post_format", slack_format, [R_COMM], "Add the missing details and post again.")
    + pre_rule("funding.calendar_date", calendar_pre, [R_WINDOW, R_REMIND], "Use the SOP expected funding date.")
    + forbid_writes("files.source_readonly",
                    r"^0[1-7]_\w+\.pdf$|^CashierLog_20260414\.xlsx$|^Sunshine And Set SOP\.docx$",
                    "source documents must not be overwritten - save revised versions under a new name.", [R_AUDIT])
    + no_placeholders([R_TPLS])
    + state_rule("deal.log_row", deal_log_checks, "Update the Deal #4821 row with exactly these values.")
    + state_rule("deal.log_integrity", deal_log_integrity, "Restore the other rows unchanged.")
    + state_rule("deal.jacket_pdf", jacket_checks, "Compile and save the deal jacket PDF.")
    + state_rule("funding.tracker_row", tracker_checks, "Log Deal #4821 in the funding tracker with these values.")
    + state_rule("funding.tracker_integrity", tracker_integrity, "Restore the existing tracker rows.")
    + state_rule("funding.calendar_reminder", calendar_checks, "Create the calendar reminder.")
    + state_rule("handoff.routing", handoff_checks, "Send the hand-off message.")
)
