"""Verifiers for insurance_vanguard_shield_mutual_9b2f7a29: March 2026 intercompany suspense reconciliation (SOP §2.1).

Expected dispositions are derived from the seed data only (Suspense_March2026.xlsx, the INV-SUSP-*.pdf invoices on the
OPS-1 sub-tasks, #finance-approvals, Jira FIN-1/FIN-2 pinned issues, today = 2026-04-04).
"""

from __future__ import annotations

import json
import re

from ..kit import Action, Context, World, dashes, money_rx, nh, pre_rule, prior_denials, state_rule, world

BOOK = "Suspense_Reconciliation_March2026.xlsx"
BOOK_RX = r"(^|/)Suspense_Reconciliation_March2026\.xlsx$"
COLS = {"Support Found": r"^Support\s*Found", "Support Location": r"^Support\s*Location", "Conflict": r"^Conflict",
        "Status": r"^Status", "Resolution Notes": r"^Resolution\s*Notes"}

# key = OPS sub-task, xl = GL in the suspense workbook, inv = GL on the PDF invoice (None: no PDF on the sub-task).
ITEMS = {
    "SUSP-001": dict(key="OPS-2", amount=3250.00, xl="6200-Office-Exp", inv="6200-Office-Exp", out="cleared",
                     why="≤ $5,000 and invoice INV-SUSP-001 ties out (GL 6200-Office-Exp)"),
    "SUSP-002": dict(key="OPS-3", amount=7800.00, xl="7300-Software", inv="7300-Software", out="cleared",
                     why="invoice GL matches and Sarah Chen (Finance Manager) posted \"Approved: Software License "
                         "Renewal $7,800.00\" in #finance-approvals"),
    "SUSP-003": dict(key="OPS-4", amount=12500.00, xl="5100-Professional", inv="5100-Professional", out="exception",
                     why="> $5,000 and no manager approval in #finance-approvals (the \"Looks good to me\" post has no "
                         "amount or link and is not an approval)"),
    "SUSP-004": dict(key="OPS-5", amount=4750.00, xl="6400-Marketing", inv=None, out="exception",
                     why="no PDF invoice is attached to OPS-5 (no INV-SUSP-004)"),
    "SUSP-005": dict(key="OPS-6", amount=8900.00, xl="8100-IT-Equipment", inv="7100-Capital-Equipment", out="exception",
                     why="GL conflict: invoice 7100-Capital-Equipment vs workbook 8100-IT-Equipment"),
    "SUSP-006": dict(key="OPS-7", amount=2100.00, xl="6500-Training", inv="6500-Training", out="cleared",
                     why="≤ $5,000 and invoice INV-SUSP-006 ties out (GL 6500-Training)"),
    "SUSP-007": dict(key="OPS-8", amount=15000.00, xl="8600-Facilities", inv="8600-Facilities", out="cleared",
                     why="invoice GL matches and David Park (Senior Finance Manager) posted \"Approved: Facility "
                         "Upgrade $15,000.00\" in #finance-approvals"),
    "SUSP-008": dict(key="OPS-9", amount=6300.00, xl="6600-Travel", inv="6600-Travel", out="exception",
                     why="> $5,000 and no approval message in #finance-approvals"),
    "SUSP-009": dict(key="OPS-10", amount=4999.99, xl="6200-Office-Exp", inv="6200-Office-Supplies", out="exception",
                     why="GL conflict: invoice 6200-Office-Supplies vs workbook 6200-Office-Exp"),
    "SUSP-011": dict(key="OPS-11", amount=8500.00, xl="6400-Marketing", inv="6400-Marketing", out="exception",
                     why="> $5,000 and no approval in #finance-approvals (an email \"looks fine\" is not the Slack "
                         "approval evidence the SOP requires)"),
    "SUSP-013": dict(key="OPS-12", amount=7500.00, xl="6600-Travel", inv="6600-Travel", out="exception",
                     why="> $5,000 and the only \"Approved\" message was posted by junior.analyst (the analyst), "
                         "not a manager"),
}
CLEARED = [t for t, d in ITEMS.items() if d["out"] == "cleared"]
EXCEPTIONS = [t for t, d in ITEMS.items() if d["out"] == "exception"]
CONFLICTS = [t for t, d in ITEMS.items() if d["inv"] and d["inv"] != d["xl"]]
KEY2ID = {d["key"]: t for t, d in ITEMS.items()}
ASSIGNEE = "vp-001 (Jennifer Walsh)"

R_GEN = ("2.1", "Generate workbook:", "§2.1 Generate workbook")
R_CLEAR = ("2.1", "Clear items", "§2.1 Clear items ≤ $5,000")
R_CONF = ("2.1", "Conflicting GL codes:", "§2.1 Conflicting GL codes")
R_APPR = ("2.1", "Verify approval evidence", "§2.1 Verify approval evidence")
R_RCPT = ("2.1", "Locate receipts:", "§2.1 Locate receipts")
R_RECL = ("2.1", "Prepare reclassification", "§2.1 Prepare reclassification")
R_EXC = ("2.1", "Exception handling:", "§2.1 Exception handling")
R_ATT = ("1.2", "Source data (reports", "§1.2 missing attachment -> exception path")
R_QA = ("1.3", "Queue Assignee | Role-based", "§1.3 Queue Assignee")
R_NAME = ("1.4", "All output files produced", "§1.4 File naming")
R_SPACE = ("1.4", "Do not use spaces", "§1.4 File naming")
R_B1USE = ("7.3", "Use as: Jira ticket description (FIN-Exceptions)", "Template B-1")
R_B1 = ("7.3", "[Suspense Escalation]", "Template B-1")
R_B1GL = ("7.3", "GL Conflict (if applicable)", "Template B-1")
R_FIN100 = ("7.3", "FIN-100 | Cleared", "Appendix C FIN-100")

KEY_RX = re.compile(r'"key"\s*:\s*"([A-Z][A-Z0-9_]*-\d+)"')
HEAD_RX = re.compile(r"\[Suspense Escalation\]\s*[-–—]?\s*Transaction ID:\s*(SUSP-\d+)", re.I)
JW_RX = re.compile(r"vp-001|jennifer[ ._]?walsh", re.I)
MV_RX = re.compile(r"controller-001|marcus[ ._]?vance", re.I)
FIN100_RX = re.compile(r"FIN-100|Cleared\s*(?:&|and)\s*Posted", re.I)
FIN100_FULL = re.compile(r"FIN-100\W{0,4}Cleared\s*(?:&|and)\s*Posted", re.I)
NEG_RX = re.compile(r"\bnot\b|cannot|can't|unable|until|exception|escalat|\bhold\b", re.I)
B1_PLACEHOLDERS = ("[ID Number]", "[Amount]", "[Code A]", "[Code B]")


def money(v: float) -> str:
    return f"${v:,.2f}"


def b1_text(tid: str) -> str:
    d = ITEMS[tid]
    gl = (f"Invoice GL: {d['inv']} | Excel GL: {d['xl']} | Resolution requested." if tid in CONFLICTS else "N/A")
    return ("(one field per line; ' / ' marks a line break) "
            f"[Suspense Escalation] – Transaction ID: {tid} / Status: Requires Controller Review / Amount: "
            f"{money(d['amount'])} / Details: This item has been sitting in Intercompany Suspense. No PDF receipt was "
            "found on the linked Jira issue, and/or prior Slack approval is missing. / GL Conflict (if applicable): "
            f"{gl} Action Required: Controller (per queue pinned issue), please review and advise on proper GL coding "
            "or request documentation from the originating department.")


# ---- Jira view -------------------------------------------------------------------------------------

def issue_key(a: Action) -> str:
    return str(a.channel or a.args.get("issue_key") or a.args.get("issueKey") or "").upper()


def is_fin(a: Action) -> bool:
    return str(a.channel).upper().startswith("FIN") or str(a.channel) == "10002"


def segments(text: str) -> dict[str, str]:
    """B-1 blocks of a description, by transaction id."""
    t = dashes(text)
    ms = list(HEAD_RX.finditer(t))
    return {m.group(1).upper(): t[m.start(): ms[i + 1].start() if i + 1 < len(ms) else len(t)]
            for i, m in enumerate(ms)}


def b1_problems(tid: str, seg: str) -> list[str]:
    d = ITEMS[tid]
    out = []
    if not re.search(r"Status:\s*Requires Controller Review", seg, re.I):
        out.append("line \"Status: Requires Controller Review\"")
    if not re.search(r"Amount:\s*" + money_rx(d["amount"]), seg, re.I):
        out.append(f"line \"Amount: {money(d['amount'])}\"")
    if not re.search(r"Details:", seg, re.I):
        out.append("the \"Details:\" line")
    if not re.search(r"Action Required:", seg, re.I):
        out.append("the \"Action Required: Controller (per queue pinned issue) ...\" line")
    if tid in CONFLICTS and not re.search(rf"Invoice GL:\s*{re.escape(d['inv'])}\s*\|\s*Excel GL:\s*{re.escape(d['xl'])}",
                                          seg, re.I):
        out.append(f"\"GL Conflict (if applicable): Invoice GL: {d['inv']} | Excel GL: {d['xl']} | Resolution requested.\"")
    left = [p for p in B1_PLACEHOLDERS if p in seg]
    if left:
        out.append(f"filled-in values instead of the placeholders {left}")
    return out


def fin_tickets(w: World) -> list[dict]:
    tickets: list[dict] = []
    by_key: dict[str, dict] = {}
    for e in w.state.executed:
        a = e.action
        if not w.ok(e):
            continue
        if a.kind == "jira_create" and is_fin(a):
            m = KEY_RX.search(e.result or "")
            t = {"key": m.group(1).upper() if m else None, "text": a.text,
                 "assignee": a.recipients[0] if a.recipients else ""}
            tickets.append(t)
            if t["key"]:
                by_key[t["key"]] = t
        elif a.kind in ("jira_update", "other_write") and issue_key(a) in by_key:
            t = by_key[issue_key(a)]
            if a.kind == "jira_update" and a.text:
                t["text"] = a.text
            who = a.recipients[0] if a.recipients else a.args.get("assignee") or a.args.get("account_id") or ""
            if who and (a.kind == "jira_update" or "assign" in a.tool):
                t["assignee"] = str(who)
    return tickets


def comments_on(w: World, key: str) -> list[str]:
    return [dashes(a.text) for a in w.calls("jira_comment") if issue_key(a) == key]


def fin100_marked(w: World, key: str) -> bool:
    for a in w.calls("jira_update", "other_write"):
        if issue_key(a) == key and "FIN-100" in json.dumps(a.args).upper():
            return True
    return False


# ---- reconciliation workbook ------------------------------------------------------------------------

def recon_table(w: World) -> tuple[str | None, list[str], list[dict]]:
    name, sheets = w.book(BOOK_RX)
    best = None
    for grid in (sheets or {}).values():
        if not isinstance(grid, list):
            continue
        for i, row in enumerate(grid):
            cells = [nh(c) for c in row]
            if any(re.fullmatch(r"Transaction\s*ID", c, re.I) for c in cells):
                rows = [dict(zip(cells, (str(c) for c in r))) for r in grid[i + 1:]]
                score = sum(any(re.search(rx, c, re.I) for c in cells) for rx in COLS.values())
                if best is None or score > best[0]:
                    best = (score, cells, rows)
                break
    return (name, best[1], best[2]) if best else (name, [], [])


def row_for(rows: list[dict], tid: str) -> dict | None:
    for r in rows:
        if nh(World.col(r, r"^Transaction\s*ID$")).upper() == tid:
            return r
    return None


def yes(v: str) -> bool:
    return bool(re.match(r"\s*(y|yes)\b", v or "", re.I))


def no(v: str) -> bool:
    return bool(re.match(r"\s*(n|no)\b", v or "", re.I))


def cleared_like(s: str) -> bool:
    return bool((FIN100_RX.search(s) or re.match(r"\s*cleared\b", s, re.I)) and not NEG_RX.search(s))


def workbook_checks(ctx: Context):
    w = world(ctx)
    name, header, rows = recon_table(w)
    refs = [R_GEN, R_CLEAR, R_NAME]
    if not name:
        yield (False, f"{BOOK} does not exist. Save the local working copy of the suspense workbook "
                      f"(all 11 lines of Suspense_March2026.xlsx) as {BOOK} with the tie-out columns Support Found, "
                      "Support Location, Conflict, Status, Resolution Notes.", refs)
        return
    if not header:
        yield False, f"{name} has no header row with a \"Transaction ID\" column (copy all suspense lines into it).", refs
        return
    missing = [c for c, rx in COLS.items() if not any(re.search(rx, h, re.I) for h in header)]
    yield (not missing, f"{name} is missing the tie-out column(s) {missing} (required: Support Found, Support Location, "
                        "Conflict, Status, Resolution Notes).", refs + [R_CONF])
    absent = [t for t in ITEMS if row_for(rows, t) is None]
    yield not absent, f"{name} is missing the suspense line(s) {absent}; keep every line of Suspense_March2026.xlsx.", refs


def value_checks(ctx: Context):
    w = world(ctx)
    name, header, rows = recon_table(w)
    if not name or not header:
        return
    have = {c for c, rx in COLS.items() if any(re.search(rx, h, re.I) for h in header)}
    for tid, d in ITEMS.items():
        r = row_for(rows, tid)
        if r is None:
            continue
        col = lambda c: World.col(r, COLS[c])
        if "Conflict" in have:
            if tid in CONFLICTS:
                yield (yes(col("Conflict")), f"{BOOK} {tid}: Conflict must be \"Y\" ({d['why']}); got "
                                             f"\"{col('Conflict')}\".", [R_CONF])
            else:
                yield (not yes(col("Conflict")), f"{BOOK} {tid}: Conflict is \"{col('Conflict')}\" but the invoice GL "
                                                 f"matches the workbook GL ({d['xl']}); mark it N.", [R_CONF])
        if tid in CONFLICTS:
            other = " ".join(v for k, v in r.items() if not re.fullmatch(r"GL\s*Code", k, re.I))
            yield (d["inv"].lower() in other.lower(),
                   f"{BOOK} {tid}: record both GL codes in the tie-out columns - the invoice GL {d['inv']} is not "
                   f"recorded next to the workbook GL {d['xl']}.", [R_CONF])
        if "Support Found" in have:
            if d["inv"] is None:
                yield (no(col("Support Found")), f"{BOOK} {tid}: Support Found must be \"N\" ({d['why']}); got "
                                                 f"\"{col('Support Found')}\".", [R_CLEAR, R_EXC])
            elif tid in CLEARED:
                yield (yes(col("Support Found")), f"{BOOK} {tid}: Support Found must be \"Y\" ({d['why']}); got "
                                                  f"\"{col('Support Found')}\".", [R_CLEAR])
        if "Support Location" in have and tid in CLEARED:
            loc = col("Support Location")
            yield (bool(re.search(rf"INV-{tid}|{d['key']}(?!\d)|\.pdf", loc, re.I)),
                   f"{BOOK} {tid}: Support Location must name the invoice (INV-{tid}.pdf on Jira {d['key']}); got "
                   f"\"{loc}\".", [R_CLEAR])
        if "Status" in have:
            st = col("Status")
            if tid in CLEARED:
                yield (cleared_like(st), f"{BOOK} {tid}: Status must be \"FIN-100 Cleared & Posted\" ({d['why']}); got "
                                         f"\"{st}\".", [R_CLEAR, R_RECL, R_FIN100])
            else:
                yield (not cleared_like(st), f"{BOOK} {tid}: Status \"{st}\" marks the line cleared, but it must go to "
                                             f"FIN-Exceptions ({d['why']}). Record the exception status instead.",
                       [R_EXC])


def cleared_checks(ctx: Context):
    w = world(ctx)
    for tid in CLEARED:
        d = ITEMS[tid]
        key, gl = d["key"], d["inv"]
        cs = comments_on(w, key)
        if d["amount"] <= 5000:
            ok = any(tid in c.upper() and gl.lower() in c.lower() and FIN100_FULL.search(c) for c in cs)
            yield (ok, f"{tid} ({d['why']}) is cleared: add a Jira comment on {key} with the transaction ID, target GL "
                       f"and status, e.g. \"{tid} | Target GL: {gl} | Status: FIN-100 Cleared & Posted\".",
                   [R_CLEAR, R_FIN100])
        else:
            ok = any(gl.lower() in c.lower() for c in cs) and (any(FIN100_RX.search(c) for c in cs)
                                                               or fin100_marked(w, key))
            yield (ok, f"{tid} ({d['why']}) is cleared: add a Jira comment on {key} documenting the GL code from the "
                       f"PDF and the status, e.g. \"{tid} | GL per invoice INV-{tid}: {gl} | Status: FIN-100 Cleared & "
                       "Posted\".", [R_RECL, R_APPR, R_RCPT, R_FIN100])


def conflict_checks(ctx: Context):
    w = world(ctx)
    for tid in CONFLICTS:
        d = ITEMS[tid]
        rx = rf"GL conflict:\s*Invoice shows {re.escape(d['inv'])},\s*Excel line shows {re.escape(d['xl'])}\b"
        ok = any(re.search(rx, c, re.I) and re.search(r"requesting Controller clarification", c, re.I)
                 for c in comments_on(w, d["key"]))
        yield (ok, f"{tid}: GL codes conflict. Add this comment on {d['key']} word for word: \"GL conflict: Invoice "
                   f"shows {d['inv']}, Excel line shows {d['xl']} — requesting Controller clarification.\"", [R_CONF])


def exception_checks(ctx: Context):
    w = world(ctx)
    tickets = fin_tickets(w)
    for tid in EXCEPTIONS:
        d = ITEMS[tid]
        refs = [R_EXC, R_B1USE, R_B1] + ([R_CONF, R_B1GL] if tid in CONFLICTS else []) + \
            ([R_ATT] if d["inv"] is None else [R_APPR])
        mine = [t for t in tickets if tid in segments(t["text"])]
        if not mine:
            yield (False, f"{tid} ({d['key']}, {money(d['amount'])}) must be escalated: {d['why']}. Create a Jira issue "
                          f"in project FIN (FIN-Exceptions), assignee {ASSIGNEE} per pinned issue FIN-2, with Template "
                          f"B-1 as the description: {b1_text(tid)}", refs + [R_QA])
            continue
        best = None
        for t in mine:
            probs = [f"its description lacks {p}" for p in b1_problems(tid, segments(t["text"])[tid])]
            if not JW_RX.search(t["assignee"] or ""):
                probs.append(f"assignee must be {ASSIGNEE} (FIN-2: temporary FIN-Exceptions assignee for tickets "
                             f"created April 1-10, 2026; got \"{t['assignee'] or 'unassigned'}\")")
            if t["key"] and not any(re.search(r"OPS-\d+", c) for c in comments_on(w, t["key"])):
                probs.append(f"add a comment on {t['key']} noting the Jira issue keys (e.g. {d['key']}, OPS-1) and the "
                             "Slack search used, and what evidence was not found or conflicted")
            if best is None or len(probs) < len(best[1]):
                best = (t, probs)
        t, probs = best
        yield (not probs, f"FIN-Exceptions ticket {t['key'] or ''} for {tid}: " + "; ".join(probs) + ".", refs + [R_QA])


def space_checks(ctx: Context):
    w = world(ctx)
    bad = [f for f in w.files() if " " in f.split("/")[-1] and not any(p.startswith(".") for p in f.split("/"))]
    yield not bad, f"File names must not contain spaces (use underscores): {bad[:5]}.", [R_SPACE]


# ---- pre rules ---------------------------------------------------------------------------------------

def fin_pre(ctx: Context, a: Action) -> str | None:
    if a.kind != "jira_create":
        return None
    segs = segments(a.text)
    if not is_fin(a) and not segs:
        return None
    ids = set(segs) or {x.upper() for x in re.findall(r"SUSP-\d+", f"{a.subject} {a.text}", re.I)} & set(ITEMS)
    hard, fmt = [], []
    if a.recipients and MV_RX.search(a.recipients[0]) and not JW_RX.search(a.recipients[0]):
        hard.append(f"Assignee must be {ASSIGNEE}: pinned issue FIN-2 names her the FIN-Exceptions assignee for tickets "
                    "created April 1-10, 2026 while Marcus Vance is out of office (today is April 4, 2026).")
    if ids and ids <= set(CLEARED):
        hard.append("; ".join(f"{t} is supported ({ITEMS[t]['why']}) and is cleared to FIN-100 Cleared & Posted, "
                              "not escalated" for t in sorted(ids)) + ".")
    if segs and not is_fin(a):
        hard.append("Create the escalation in the FIN project (FIN-Exceptions queue).")
    exc = sorted(ids & set(EXCEPTIONS))
    if exc and not segs:
        fmt.append("Paste Template B-1 into the description, starting with \""
                   + "\" / \"".join(f"[Suspense Escalation] – Transaction ID: {t}" for t in exc) + "\".")
    for tid in sorted(set(segs) & set(EXCEPTIONS)):
        probs = b1_problems(tid, segs[tid])
        if probs:
            fmt.append(f"Template B-1 for {tid} is incomplete; add " + ", ".join(probs) + f". Expected: {b1_text(tid)}")
    if fmt and not hard and prior_denials(ctx, "[B-1 format]") >= 2:
        fmt = []
    msg = " ".join(hard + (["[B-1 format] " + " ".join(fmt)] if fmt else []))
    return msg or None


def fin100_pre(ctx: Context, a: Action) -> str | None:
    if a.kind not in ("jira_comment", "jira_update", "other_write"):
        return None
    tid = KEY2ID.get(issue_key(a))
    if tid not in EXCEPTIONS:
        return None
    d = ITEMS[tid]
    if a.kind == "jira_comment":
        hit = bool(FIN100_RX.search(dashes(a.text))) and not NEG_RX.search(a.text)
    else:
        hit = "FIN-100" in json.dumps(a.args).upper() and not NEG_RX.search(a.text)
    if not hit:
        return None
    return (f"{tid} ({d['key']}) cannot be marked FIN-100 Cleared & Posted: {d['why']}. It goes to the FIN-Exceptions "
            "queue (Template B-1) instead.")


RULES = (
    state_rule("suspense.recon_workbook", workbook_checks, "Create or complete the reconciliation workbook as listed.")
    + state_rule("suspense.recon_values", value_checks, "Correct the tie-out cells as listed.")
    + state_rule("suspense.cleared_comments", cleared_checks, "Add the Jira comment as listed.")
    + state_rule("suspense.gl_conflict_comments", conflict_checks, "Add the Jira comment exactly as listed.")
    + state_rule("suspense.fin_exceptions", exception_checks, "Create or fix the FIN-Exceptions ticket as listed.")
    + state_rule("files.no_spaces", space_checks, "Rename the file with underscores.")
    + pre_rule("suspense.fin_exceptions_pre", fin_pre, [R_EXC, R_QA, R_B1USE, R_B1, R_B1GL],
               "Fix the FIN-Exceptions ticket as described and create it again.")
    + pre_rule("suspense.no_fin100_on_exceptions", fin100_pre, [R_EXC, R_APPR, R_CONF, R_FIN100],
               "Do not clear this line; escalate it to FIN-Exceptions.")
)
