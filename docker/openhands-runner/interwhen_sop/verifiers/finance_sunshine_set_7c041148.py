"""Verifiers for finance_sunshine_set_7c041148 (Sunshine & Set Automotive accounting SOP).

Situation (seed data, today 03/26/2027): three unread emails.
- Marcus Bell: post the Ortiz deal #10099. The F&I recap total gross is $8,224 vs $8,220 in the deal log ($4
  variance; front gross $2,165 vs $2,161). Total gross > $5,000, so SOP 2.1 requires Marcus Hale review before
  posting: do not post (Posting Date stays blank) and escalate to Marcus Hale.
- Priya Bennett: returned check RTN-2027-03892, Patricia Morris, $2,300, deposited 03/12/2027, returned 03/25/2027,
  R02 Account Closed -> deal #10091 (Q1 2027, delivered 03/13/2027, Title Status 'In Progress'). SOP 3.3: log it in
  the cash exception log, Title Status 'Held - Returned Check', email the customer, report to Marcus Hale and
  Elena Brooks (> $1,000, same quarter so Talia is not required), hold notice in #acct-titles-billing. SOP 3.1:
  notify Renee Lawson of the returned item.
- Marcus Hale: Flores #10057 desk recap ($7,500) was in error, deal log $6,700 stands. SOP 2.1 (a)+(b): document
  the decision in the deal log and send Template A to Sales/F&I to correct the desk recap.
Workbook updates are accepted in the deal log / cash exception log or a revised copy (deal_log_v2.xlsx etc.).
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

from ..kit import (COMM_KINDS, Action, Comm, Context, World, blank, comm_rules, dashes, forbid_writes, nh, no_placeholders,
                   num, pre_rule, state_rule, text_of, world)

DOM = "@sunshineandsetauto.com"
MARCUS, ELENA, RENEE = f"marcus.hale{DOM}", f"elena.brooks{DOM}", f"renee.lawson{DOM}"
OLIVIA, SOFIA = f"olivia.mercer{DOM}", f"sofia.ramirez{DOM}"
CUSTOMER = "patricia2000@aol.com"
SALES_FI = {OLIVIA, SOFIA}

DEAL_LOG = r"(^|/)deal_log[^/]*\.xlsx$"
CASH_LOG = r"(^|/)cash_exception_log[^/]*\.xlsx$"
HELD = "Held - Returned Check"
ALLOWED_DEALS = {10091, 10057, 10099}

# ---- SOP references -------------------------------------------------------------------------------------------
R_TOOLS = ("1.1", "All accounting work is performed using the following tools", "1.1 Tools")
R_COMM = ("1.5", "Use the correct Slack channel for routine internal questions", "1.5 Communication Rules")
R_TIE = ("2.1", "Tie deal gross to the approved desking or F&I recap", "2.1 Deal posting")
R_GROSS = ("2.1", "If the posted deal gross differs from the approved desk recap", "2.1 Deal gross variance")
R_TPL_A = ("2.1", "When a deal gross variance requires Sales or F&I correction", "2.1 Template A")
R_EXC = ("3.1", "Match deposit totals to the cashiering log", "3.1 Exception log")
R_NSF = ("3.3", "When the bank returns a deposited check", "3.3 Returned checks")
R_NSF2 = ("3.3", "Notify the customer by email within 1 business day", "3.3 Returned checks")
R_MX_CASH = ("9.2", "Cash difference or deposit issue", "9.2 Escalation Matrix")
R_MX_DEAL = ("9.2", "Deal gross discrepancy or posting issue", "9.2 Escalation Matrix")
R_MX_DEAL2 = ("9.2", "$500 or total gross >$5000 escalate directly", "9.2 Escalation Matrix")
R_STOP = ("9.3", "Stop the workflow at the point the discrepancy is identified", "9.3 Discrepancy Resolution")
R_FIVE = ("9.3", "Collect the five required facts before contacting anyone", "9.3 Discrepancy Resolution")
R_DOC = ("9.3", "Document every step in the exception log or tracker", "9.3 Discrepancy Resolution")
R_SAMEDAY = ("9.3", "Escalate the same day if the discrepancy affects", "9.3 Discrepancy Resolution")
R_FILES = ("9.4", "Every accounting process must leave an audit trail", "9.4 File and Naming Standards")
R_DOCFEE = ("10.3", "The dealership charges a flat documentation fee", "10.3 Doc Fee")
R_A_SUBJ = ("10.5", "Subject: Deal Gross Variance", "Template A")
R_A_GROSS = ("10.5", "Approved gross:", "Template A")
R_A_SRC = ("10.5", "Source of difference:", "Template A")
R_A_CONF = ("10.5", "Please confirm the correct figure", "Template A")
R_TPL = ("10.5", "The following email templates are referenced", "Appendix A")

DATE_RX = (r"\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}\b"
           r"|\b20\d\d-\d\d-\d\d\b")
ISO_DATE = re.compile(r"\b20\d\d-[01]\d-[0-3]\d\b")

PEOPLE = {
    "Marcus Hale": (MARCUS, r"marcus[ ._]hale|<@U013>|\bHale\b"),
    "Elena Brooks": (ELENA, r"elena[ ._]brooks|<@U012>|\bBrooks\b"),
    "Renee Lawson": (RENEE, r"renee[ ._]lawson|<@U019>|\bRenee\b|\bLawson\b"),
}


# ---- helpers ---------------------------------------------------------------------------------------------------

def _date(v) -> dt.date | None:
    s = nh(v)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _canon(c) -> str:
    # The seed workbooks store floats (1.0) that an openpyxl round trip rewrites as ints (1).
    s = "" if str(c) in ("None", "nan") else str(c)
    if re.fullmatch(r"-?\d+(?:\.\d+)?", s.strip()):
        f = float(s)
        return str(int(f)) if f == int(f) else repr(f)
    return s


def _trim(r) -> tuple:
    """Row without trailing blank cells (a cell written in a new column pads every row of the dump)."""
    r = [_canon(c) for c in r]
    while r and not r[-1].strip():
        r.pop()
    return tuple(r)


def _table(grid: list[list[str]], header_rx: str) -> tuple[list[str], list[tuple[int, tuple]]]:
    for i, row in enumerate(grid or []):
        if any(re.search(header_rx, nh(c), re.I) for c in row):
            return [nh(c) for c in row], [(j, _trim(r)) for j, r in enumerate(grid[i + 1:], start=i + 2)
                                          if any(str(c).strip() not in ("", "None") for c in r)]
    return [], []


def _cell(header: list[str], row: list[str], name_rx: str) -> str:
    for k, v in zip(header, row):
        if re.search(name_rx, k, re.I):
            return "" if str(v) in ("None", "nan") else str(v).strip()
    return ""


def _sheet(sheets: dict, name: str, pos: int) -> list[list[str]] | None:
    if not isinstance(sheets, dict):
        return None
    if name in sheets:
        return sheets[name]
    vals = [v for k, v in sheets.items() if not k.startswith("__")]
    return vals[pos] if pos < len(vals) else None


def _deal_rows(sheets: dict, deal: int, sheet_rx: str = r".") -> list[tuple[list[str], list[str]]]:
    out = []
    for name, grid in (sheets or {}).items():
        if not re.search(sheet_rx, name, re.I) or not isinstance(grid, list):
            continue
        hdr, rows = _table(grid, r"^Deal #$")
        out += [(hdr, r) for _, r in rows if num(_cell(hdr, r, r"^Deal #$")) == deal]
    return out


def _books(w: World, rx: str) -> list[tuple[str, dict]]:
    return [(k, v) for k, v in sorted((w.current or {}).items()) if re.search(rx, k, re.I) and isinstance(v, dict)]


def _initial(w: World, rx: str) -> dict:
    return next((v for k, v in sorted((w.initial or {}).items()) if re.search(rx, k, re.I) and isinstance(v, dict)), {})


def _reply_sender(w: World, a: Action) -> str:
    eid = str(a.args.get("email_id") or a.args.get("message_id") or "")
    for e in w.seed_emails:
        if str(e.get("email_id") or e.get("id") or "") == eid:
            return str(e.get("from_addr") or e.get("from") or "").lower()
    return ""


def reaches(w: World, a: Action, person: str, channels: set[str] | None = None) -> bool:
    """The (executed) message reaches ``person``: email to/cc, reply to their email, Slack DM, or a channel post
    that tags/names them (only in ``channels`` when given)."""
    email, rx = PEOPLE[person]
    if a.kind == "email_send":
        rec = {x.lower() for x in a.recipients + a.cc}
        if "reply" in a.tool and not a.recipients:
            rec.add(_reply_sender(w, a))
        return email in rec
    if a.kind in ("slack_dm", "slack_post"):
        if w.dm_recipients(a):
            return w.is_dm_to(a, person)
        if a.kind == "slack_post" and (channels is None or any(w.is_channel(a.channel, c) for c in channels)):
            return bool(re.search(rx, a.text, re.I))
    return False


# ---- messages (pre + completion) -------------------------------------------------------------------------------

@dataclass
class AnyToComm(Comm):
    """A Comm whose To must include at least one of ``any_to``."""
    any_to: tuple = ()
    any_to_hint: str = ""

    def problems(self, a: Action, w: World) -> list[str]:
        out = super().problems(a, w)
        if not self.forbidden and self.any_to and a.kind in ("email_send", "email_draft") \
                and not {x.lower() for x in a.recipients} & set(self.any_to):
            out.append(f"Address it To {self.any_to_hint}.")
        return out


def _is_template_a(a: Action) -> bool:
    if a.kind not in ("email_send", "email_draft") or not re.search(r"10057|Flores", text_of(a), re.I):
        return False
    return bool(re.search(r"gross variance", a.subject, re.I)) or bool({x.lower() for x in a.recipients + a.cc} & SALES_FI)


def _is_title_hold(w: World):
    return lambda a: (a.kind == "slack_post" and not w.dm_recipients(a) and w.is_channel(a.channel, "acct-titles-billing")
                      and bool(re.search(r"10091|Morris", a.text, re.I)))


def _is_customer_notice(a: Action) -> bool:
    return a.kind in ("email_send", "email_draft") and CUSTOMER in {x.lower() for x in a.recipients + a.cc}


TPL_A_SUBJECT = "Deal Gross Variance — Deal #10057 / Flores"


def specs(ctx: Context) -> list[Comm]:
    w = world(ctx)
    return [
        AnyToComm(
            "flores_template_a", "email", _is_template_a,
            "Template A desk-recap correction request to Sales/F&I for Deal #10057 (Flores)",
            [R_TPL_A, R_GROSS, R_A_SUBJ, R_A_GROSS, R_A_SRC, R_A_CONF],
            subject=r"(?:(?:re|fwd?)\s*:\s*)?Deal Gross Variance\s*–\s*Deal #\s?10057\s*/\s*Flores",
            subject_hint=TPL_A_SUBJECT,
            body=[(r"Deal #\s?10057", "Deal #10057"),
                  (r"Stock #\s?N16028", "Stock #N16028"),
                  (r"VIN ending\s*:?\s*9342FK", "VIN ending 9342FK"),
                  (r"does not tie to the approved desk recap", "the line \"The posted deal gross for Deal #10057 "
                   "(Flores, Stock #N16028, VIN ending 9342FK) does not tie to the approved desk recap.\""),
                  (r"Approved gross\s*:?\s*\$?\s?7,?500(?:\.00)?(?![\d,])",
                   "Approved gross: $7,500 (the desk recap total gross)"),
                  (r"Posted gross\s*:?\s*\$?\s?6,?700(?:\.00)?(?![\d,])", "Posted gross: $6,700 (deal log total gross)"),
                  (r"Variance\s*:?\s*[-(]?\s*\$?\s?[-(]?800(?:\.00)?(?![\d,])", "Variance: $800"),
                  (r"Source of difference\s*:", "Source of difference: other — incorrect accessory charge on the desk "
                   "recap"),
                  (r"Please confirm the correct figure or provide an updated approval",
                   "the line \"Please confirm the correct figure or provide an updated approval so the deal can be "
                   "finalized.\"")],
            exact_to=False, max_count=3,
            any_to=tuple(sorted(SALES_FI)),
            any_to_hint=f"the Sales/F&I owner of the desk recap: {OLIVIA} (Sales Manager, New Vehicles) and/or "
                        f"{SOFIA} (F&I Director)"),
        Comm(
            "title_hold_notice", "slack_post", _is_title_hold(w),
            "returned-check title hold notification for Deal #10091 (Morris) in #acct-titles-billing",
            [R_NSF2], channel="acct-titles-billing",
            body=[(r"10091", "deal number #10091"),
                  (r"Morris", "customer name Patricia Morris"),
                  (r"returned|NSF|account closed", "hold reason: returned check $2,300 (R02 – Account Closed)"),
                  (DATE_RX, "the date (MM/DD/YYYY, e.g. 03/26/2027)")],
            max_count=5),
        Comm(
            "customer_returned_check_notice", "email", _is_customer_notice,
            "email to the customer Patricia Morris about her returned check",
            [R_NSF2], to=[CUSTOMER],
            body=[(r"2,?300", "the returned check amount $2,300.00"),
                  (r"return", "that the check was returned unpaid (R02 – Account Closed)")],
            exact_to=False, max_count=5),
    ]


# ---- completion rules ------------------------------------------------------------------------------------------

def _ortiz_hold(ctx: Context):
    w = world(ctx)
    for name, sheets in _books(w, DEAL_LOG):
        for hdr, r in _deal_rows(sheets, 10099):
            pd = _cell(hdr, r, r"^Posting Date$")
            yield (blank(pd),
                   f"Deal #10099 (Ortiz) was posted in {name} (Posting Date '{pd}'). Its total gross ($8,224 F&I recap / "
                   "$8,220 deal log) exceeds $5,000, so the $4 variance must be reviewed by Marcus Hale before posting. "
                   "Clear the Posting Date for 10099 and leave the deal unposted until Marcus Hale resolves it.",
                   [R_GROSS, R_TIE, R_STOP])


def _ortiz_escalation(ctx: Context):
    w = world(ctx)
    var = r"\$\s?4(?:\.00)?(?![\d,.])|\b4(?:\.00)?\s?(?:dollars|USD)\b|8,?224|2,?165"
    ok = any(reaches(w, a, "Marcus Hale", {"acct-deal-posting"}) and re.search(r"10099", a.text + a.subject)
             and re.search(r"Ortiz", text_of(a), re.I) and re.search(r"N26043|6D030D", text_of(a), re.I)
             and re.search(var, dashes(a.text), re.I) for a in w.comms())
    yield (ok, "Deal #10099 (Ortiz) has a $4 gross variance on a deal with total gross over $5,000: escalate it to "
               f"Marcus Hale for review before posting (email {MARCUS}, Slack DM, or #acct-deal-posting tagging "
               "@marcus.hale) with the five facts: Deal #10099; customer Andrew Ortiz; Stock #N26043 / VIN "
               "18TD0REAP8F6D030D; variance $4 (F&I recap total deal gross $8,224 vs deal log $8,220 - front gross "
               "$2,165 vs $2,161); source: deal jacket 20270321_10099_Ortiz_6D030D.pdf vs deal log.",
           [R_GROSS, R_MX_DEAL, R_MX_DEAL2, R_FIVE, R_COMM])


def _flores_note(ctx: Context):
    w = world(ctx)
    rows = [(n, h, r) for n, s in _books(w, DEAL_LOG) for h, r in _deal_rows(s, 10057)]
    ok = any(re.search(r"hale|marcus|approv|desk recap|recap", _cell(h, r, r"^Notes$"), re.I) for _, h, r in rows)
    yield (ok, "Document Marcus Hale's decision on Deal #10057 (Flores) in the deal log: in the Notes cell of 10057 "
               "record that Marcus Hale confirmed the desk recap ($7,500) was in error (incorrect accessory charge) and "
               "approved the posted total gross of $6,700; desk recap correction requested from Sales/F&I.",
           [R_GROSS])


def _flores_gross(ctx: Context):
    w = world(ctx)
    for name, sheets in _books(w, DEAL_LOG):
        for hdr, r in _deal_rows(sheets, 10057):
            g = _cell(hdr, r, r"^Total Deal Gross$")
            yield (num(g) == 6700,
                   f"Deal #10057 (Flores) Total Deal Gross in {name} is '{g}'. Marcus Hale approved the posted amount "
                   "($6,700; the $7,500 desk recap was in error) - restore Total Deal Gross to 6700.", [R_GROSS])


def _title_hold(ctx: Context):
    w = world(ctx)
    vals = [(n, _cell(h, r, r"^Title Status$")) for n, s in _books(w, DEAL_LOG) for h, r in _deal_rows(s, 10091, r"2027")]
    ok = any(nh(v) == HELD for _, v in vals)
    got = ", ".join(f"{n}: '{v}'" for n, v in vals) or "row not found"
    yield (ok, f"Set the Title Status of Deal #10091 (Patricia Morris, Q1 2027) in the deal log to exactly '{HELD}' "
               f"(returned check $2,300, R02 Account Closed) - currently {got}.", [R_NSF, R_NSF2])


def _cash_entry(ctx: Context):
    w = world(ctx)
    base_hdr, base_rows = _table(_sheet(_initial(w, CASH_LOG), "Cash Exception Log", 0) or [], r"^Entry #$")
    seen0 = [tuple(r) for _, r in base_rows]
    best: list[str] | None = None
    for name, sheets in _books(w, CASH_LOG):
        hdr, rows = _table(_sheet(sheets, "Cash Exception Log", 0) or [], r"^Entry #$")
        seen = list(seen0)
        for _, r in rows:
            if tuple(r) in seen:
                seen.remove(tuple(r))
                continue
            if not re.search(r"Morris|10091", " ".join(r), re.I):
                continue
            probs = []
            c = lambda rx: _cell(hdr, r, rx)
            if num(c(r"^Deal #$")) != 10091:
                probs.append(f"Deal # must be 10091 (got '{c(r'^Deal #$')}'; 10068 is a different, Q4 2026 deal)")
            if not re.search(r"Morris", c(r"Customer Name"), re.I):
                probs.append("Customer Name must be Patricia Morris")
            if _date(c(r"Original Deposit Date")) != dt.date(2027, 3, 12):
                probs.append("Original Deposit Date must be 03/12/2027")
            if _date(c(r"Return/Notice Date")) != dt.date(2027, 3, 25):
                probs.append("Return/Notice Date must be 03/25/2027")
            if not any(num(c(rx)) == 2300 for rx in (r"^Original Amount$", r"Return Amount")):
                probs.append("the check amount 2300 must be recorded (Original Amount / Variance / Return Amount)")
            if not re.search(r"R02|account closed", c(r"Reason Code"), re.I):
                probs.append("Bank Return Reason Code must be R02 – Account Closed")
            if not (re.search(r"hale", c(r"Escalated To"), re.I) and re.search(r"brooks", c(r"Escalated To"), re.I)):
                probs.append("Escalated To must record the same-day report to Marcus Hale and Elena Brooks")
            if best is None or len(probs) < len(best):
                best = [f"{name}: {p}" for p in probs]
    if best is None:
        yield (False, "Record the returned check in the cash exception log (new row): Deal # 10091, Customer Name "
                      "Patricia Morris, Original Deposit Date 03/12/2027, Return/Notice Date 03/25/2027, check amount "
                      "$2,300.00, Bank Return Reason Code R02 – Account Closed (ref RTN-2027-03892), Escalated To "
                      "Marcus Hale; Elena Brooks.", [R_NSF, R_EXC, R_DOC])
    else:
        yield (not best, "The cash exception log entry for the Morris returned check is incomplete: " + "; ".join(best)
               + ".", [R_NSF, R_DOC])


def _cash_integrity(ctx: Context):
    w = world(ctx)
    hdr0, rows0 = _table(_sheet(_initial(w, CASH_LOG), "Cash Exception Log", 0) or [], r"^Entry #$")
    if not rows0:
        return
    for name, sheets in _books(w, CASH_LOG):
        hdr, rows = _table(_sheet(sheets, "Cash Exception Log", 0) or [], r"^Entry #$")
        cur = [tuple(r) for _, r in rows]
        gone = []
        for _, r in rows0:
            if tuple(r) in cur:
                cur.remove(tuple(r))
            else:
                gone.append(r)
        yield (not gone, f"{name} is append-only: {len(gone)} existing row(s) were edited or removed (e.g. entry "
                         f"{gone[0][0] if gone else ''}). Restore them exactly and only append new rows.", [R_EXC, R_DOC])
        extra = [r for r in cur if not re.search(r"Morris|10091", " ".join(r), re.I)]
        yield (not extra, f"{name}: {len(extra)} new row(s) that no SOP checkpoint in this task calls for (e.g. "
                          f"'{' | '.join(extra[0][:5]) if extra else ''}'). The only new cash exception entry is the "
                          "Morris returned check (Deal #10091); remove the others.", [R_EXC])


def _deal_log_integrity(ctx: Context):
    w = world(ctx)
    init = _initial(w, DEAL_LOG)
    if not init:
        return
    for name, sheets in _books(w, DEAL_LOG):
        bad = []
        for pos, (sname, grid0) in enumerate(init.items()):
            if not isinstance(grid0, list):
                continue
            grid = _sheet(sheets, sname, pos)
            if grid is None:
                bad.append(f"sheet '{sname}' is missing")
                continue
            old = [_trim(r) for r in grid0 if any(str(c).strip() for c in r)]
            new = [_trim(r) for r in grid if any(str(c).strip() for c in r)]
            rest = list(new)
            for r in old:
                if r in rest:
                    rest.remove(r)
                elif num(r[0] if r else "") not in ALLOWED_DEALS:
                    bad.append(f"'{sname}' row '{' | '.join(r[:9])}' was changed or removed")
            for r in rest:
                if num(r[0] if r else "") not in ALLOWED_DEALS:
                    bad.append(f"'{sname}' has a new/changed row '{' | '.join(r[:9])}'")
        for deal in sorted(ALLOWED_DEALS):
            before = {_cell(h, r, r"^Doc Fee$") for h, r in _deal_rows(init, deal)}
            for h, r in _deal_rows(sheets, deal):
                if _cell(h, r, r"^Doc Fee$") not in before:
                    bad.append(f"Doc Fee of Deal #{deal} changed to '{_cell(h, r, r'^Doc Fee$')}' (approved doc fee "
                               "is $899; changes need Elena Brooks written approval)")
        yield (not bad, f"{name}: unrequested deal log changes - only deals 10091 (Morris, Q1 2027), 10057 (Flores) and "
                        f"10099 (Ortiz) are in scope; restore: " + "; ".join(bad[:4])
               + ("" if len(bad) <= 4 else f" (+{len(bad) - 4} more)") + ". Note: the Q4 2026 Patricia Morris row "
               "(10068) is a different deal - the returned check (deposited 03/12/2027) is Deal #10091.",
               [R_FILES, R_NSF, R_DOCFEE])


def _returned_check_mgmt(ctx: Context):
    w = world(ctx)
    for person in ("Marcus Hale", "Elena Brooks"):
        ok = any(reaches(w, a, person) and re.search(r"10091|Morris", text_of(a), re.I)
                 and re.search(r"2,?300", a.text) for a in w.comms())
        yield (ok, f"Report the returned check to {person} today (> $1,000, SOP 3.3): email {PEOPLE[person][0]} or Slack "
                   "DM with Deal #10091, customer Patricia Morris, check $2,300.00 returned 03/25/2027 (R02 – Account "
                   "Closed, ref RTN-2027-03892), deposited 03/12/2027; title work on hold.",
               [R_NSF2, R_SAMEDAY])


def _renee(ctx: Context):
    w = world(ctx)
    ok = any(reaches(w, a, "Renee Lawson") and re.search(r"10091|Morris", text_of(a), re.I)
             and re.search(r"return|NSF|R02", text_of(a), re.I) for a in w.comms())
    yield (ok, f"Notify Renee Lawson (Cashier / Receivables) of the returned item: email {RENEE}, Slack DM, or "
               "#acct-cash-desk tagging @renee.lawson - Deal #10091, Patricia Morris, $2,300.00 check returned "
               "03/25/2027 (R02 – Account Closed), logged in the cash exception log.", [R_EXC, R_MX_CASH])


# ---- pre rules -------------------------------------------------------------------------------------------------

def _iso_dates(ctx: Context, a: Action):
    if a.kind not in COMM_KINDS:
        return None
    hits = sorted(set(ISO_DATE.findall(text_of(a))))
    if not hits:
        return None
    eg = dt.date.fromisoformat(hits[0]).strftime("%m/%d/%Y") if _date(hits[0]) else "MM/DD/YYYY"
    return f"Dates must use the MM/DD/YYYY format (found {', '.join(hits)}; e.g. write {eg})."


def _unlisted_tool(ctx: Context, a: Action):
    if a.is_write and a.tool.startswith(("jira__", "shopify__")):
        return (f"{a.tool}: the SOP lists the tools accounting work uses (deal log, spreadsheets, document imaging, "
                "word processing, presentations, Calendar, Email, Slack); other software needs Controller approval.")
    return None


RULES = (
    no_placeholders([R_TPL])
    + comm_rules("comms", specs)
    + pre_rule("dates.format", _iso_dates, [R_TOOLS], "Rewrite the dates as MM/DD/YYYY.")
    + pre_rule("tools.unlisted", _unlisted_tool, [R_TOOLS], "Use email, Slack, Calendar or the workbooks instead.")
    + forbid_writes("files.source_docs", r"^20270321_10099_Ortiz_6D030D\.pdf$|^Sunshine_Set_Automotive_SOP\.html$",
                    "source documents must not be overwritten (save revised versions with a suffix such as _v2).",
                    [R_FILES])
    + state_rule("deal.ortiz_not_posted", _ortiz_hold, "Leave Deal #10099 unposted until Marcus Hale resolves it.")
    + state_rule("deal.ortiz_escalation", _ortiz_escalation, "Send the escalation to Marcus Hale.")
    + state_rule("deal.flores_note", _flores_note, "Add the note to Deal #10057 in the deal log.")
    + state_rule("deal.flores_gross", _flores_gross, "Keep the approved posted gross.")
    + state_rule("deal.title_hold", _title_hold, f"Set Title Status to '{HELD}'.")
    + state_rule("cash.returned_check_logged", _cash_entry, "Fix the cash exception log entry as listed.")
    + state_rule("cash.log_integrity", _cash_integrity, "Restore the cash exception log rows.")
    + state_rule("deal.log_integrity", _deal_log_integrity, "Restore the deal log rows.")
    + state_rule("notify.returned_check_mgmt", _returned_check_mgmt, "Send the same-day report.")
    + state_rule("notify.renee", _renee, "Notify Renee Lawson.")
)
