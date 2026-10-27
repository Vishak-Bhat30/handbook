"""Verifiers for insurance_vanguard_shield_mutual_4321b8e9 - Q1 2026 international wire dual-authorization audit
(SOP §3.3, Templates B-3 / B-4, §1.3 Queue Assignee).

Facts derived from the seed data (Wire_Population_Q1_2026.xlsx, #treasury-wires, Slack profiles, Jira):
  INTL-2026-0214 (OPS-1): Claire Overton (VP) + Rachel Kim (CFO) "Approved." -> verified; has:link query works.
  INTL-2026-0219 (OPS-2): Peter Walsh (EVP) + Nadine Cole (AVP) "Approved." -> verified; no link, query (2) works.
  INTL-2026-0223 (OPS-3): Claire Overton "Approved." + Steven Ford "LGTM" (not qualifying) -> TRE-900 + COMP
  ticket assigned to diana.walsh (CCO per pinned OPS-246) + B-4 in #compliance-urgent; has:link query works.
  INTL-2026-0228 (OPS-4) is in Slack/Jira but not in the population workbook: scope is ambiguous, so nothing is
  required or forbidden for it beyond the generic rules (no status=verified, assignee, no amounts in Slack).
"""

from __future__ import annotations

import re

from ..kit import (Action, Comm, Context, Rule, comm_rules, dashes, no_placeholders, norm, pre_rule, prior_denials,
                   same, state_rule, strict_writes, world)
from .. import templates

R_POP = ("3.3", "Pull population", "§3.3 Pull population")
R_VERIFY = ("3.3", "Verify authorization", "§3.3 Verify authorization")
R_SIGN = ("3.3", "Check signatories", "§3.3 Check signatories")
R_ESC = ("3.3", "Escalation (missing dual approval)", "§3.3 Escalation (missing dual approval)")
R_ESC2 = ("3.3", "Vanguard Shield Mutual — Core Operations SOP Chief Compliance Officer", "§3.3 Escalation (cont.)")
R_HAPPY = ("3.3", "Happy path", "§3.3 Happy path")
R_QA = ("1.3", "Queue Assignee", "§1.3 Queue Assignee")
R_B3 = ("8", "Template B-3: International Wire Control Exception", "Template B-3")
R_B3T = ("8", "[Wire Control Exception] Wire ID", "Template B-3 text")
R_B4 = ("8", "Template B-4: Compliance-Alerts Pointer", "Template B-4")
R_B4T = ("8", "Vanguard Shield Mutual — Core Operations SOP [Compliance]", "Template B-4 text")
R_TRE = ("8", "TRE-900 High-Risk Exception", "Appendix C TRE-900")
R_NAMES = ("1.4", "[Deliverable Type]_[Identifier]", "§1.4 File Naming")

BOOK = r"Wire_Population_Q1_2026\.xlsx$"
HDR = r"^Wire ID$"
CCO = "diana.walsh"
EXC_WIRE = "INTL-2026-0223"
EXC_ISSUE = "OPS-3"
VERIFIED = {"INTL-2026-0214": "OPS-1", "INTL-2026-0219": "OPS-2"}
NOT_VERIFIED_ISSUES = {"OPS-3": "INTL-2026-0223", "OPS-4": "INTL-2026-0228"}

# wire -> (first Slack query that returns the thread, qualifying approvers, dual auth, exception code)
WIRES = {
    "INTL-2026-0214": ("has:link INTL-2026-0214",
                       [("Claire Overton", "VP, Treasury Operations"), ("Rachel Kim", "Chief Financial Officer")],
                       "Y", None),
    "INTL-2026-0219": ("in:#treasury-wires INTL-2026-0219",
                       [("Peter Walsh", "EVP, Corporate Finance"), ("Nadine Cole", "AVP, Enterprise Risk")],
                       "Y", None),
    "INTL-2026-0223": ("has:link INTL-2026-0223", [("Claire Overton", "VP, Treasury Operations")], "N", "TRE-900"),
}
WIRE_RX = re.compile(r"INTL-2026-\d{4}")
AMOUNT_BANK = re.compile(r"\$\s?\d|\b\d{1,3}(?:,\d{3})+(?:\.\d{2})?\b|\b(?:445|178|623|312)[,.]?\d{3}\b|HSBC|"
                         r"Deutsche Bank|ING Bank|BNP Paribas|\bLondon\b|Frankfurt|Amsterdam|\bParis\b", re.I)
NEG = re.compile(r"\b(?:no|not|n/a|without|none|cannot|unable)\b", re.I)


# ---- helpers -------------------------------------------------------------------------------------

def _jira_writes(ctx: Context) -> list[Action]:
    return [a for a in world(ctx).calls() if a.kind.startswith("jira_") or
            (a.kind == "other_write" and a.tool.startswith("jira__"))]


def _issue_key(a: Action) -> str:
    return (a.channel or str(a.args.get("issue_key") or a.args.get("issueKey") or "")).strip().upper()


def _wire_of_create(a: Action) -> str | None:
    m = WIRE_RX.search(a.subject or "") or WIRE_RX.search(a.text or "")
    return m.group(0) if m else None


def _is_comp_create(a: Action) -> bool:
    return a.kind == "jira_create" and norm(a.channel) in ("comp", "compliance-alerts")


def _comp_tickets(ctx: Context) -> dict[str, list[str]]:
    """Wire ID -> keys of COMP issues successfully created for it (from the create call's result)."""
    out: dict[str, list[str]] = {}
    w = world(ctx)
    for e in ctx.state.executed:
        a = e.action
        if not _is_comp_create(a) or not w.ok(e):
            continue
        m = re.search(r'"key"\s*:\s*"([A-Z][A-Z0-9_]*-\d+)"', e.result or "")
        out.setdefault(_wire_of_create(a) or "", []).append(m.group(1) if m else "")
    return out


def _final_comp(ctx: Context, key: str) -> tuple[str, str, str]:
    """(summary, description, assignee) of a COMP issue after the agent's later updates."""
    summary = desc = assignee = ""
    w = world(ctx)
    for e in ctx.state.executed:
        a = e.action
        if not w.ok(e):
            continue
        if _is_comp_create(a) and key and re.search(rf'"key"\s*:\s*"{re.escape(key)}"', e.result or ""):
            summary, desc, assignee = a.subject, a.text, (a.recipients or [""])[0]
        elif a.tool.startswith("jira__") and _issue_key(a) == key and a.kind != "jira_create":
            if a.kind == "jira_update":
                summary = a.subject or summary
                desc = a.text or desc
            if a.recipients and a.kind in ("jira_update", "other_write"):
                assignee = a.recipients[0]
            elif a.kind == "other_write" and "assign" in a.tool:
                assignee = str(a.args.get("assignee") or a.args.get("account_id") or assignee)
    return summary, desc, assignee


def _assignee_ok(v: str) -> bool:
    return norm(v) in (CCO, "diana walsh", "diana.walsh@vanguardshield.com")


def _b3_problems(summary: str, desc: str, assignee: str) -> list[str]:
    want_summary = f"Exception Report: International Wire Control Exception – {EXC_WIRE}"
    out = []
    if dashes(summary).strip() != want_summary:
        out.append(f'Title must be exactly "{want_summary}" (got "{summary}").')
    if not _assignee_ok(assignee):
        out.append(f"Assign it to {CCO} (Chief Compliance Officer on the pinned Queue Roles & Assignees issue "
                   f"OPS-246; got \"{assignee or 'unassigned'}\").")
    d = dashes(desc)
    need = [
        (r"\[Wire Control Exception\]", "the header [Wire Control Exception]"),
        (rf"Wire ID:\s*{EXC_WIRE}", f"Wire ID: {EXC_WIRE}"),
        (rf"OPS-TRE-WIRE issue:.*OPS-TRE-WIRE-{EXC_WIRE}", f"OPS-TRE-WIRE issue: OPS-TRE-WIRE-{EXC_WIRE}"),
        (r"Population source:", "Population source: International wires population workbook from "
                                "OPS-TRE-WIRES-[Quarter]"),
        (r"Slack evidence:.*#treasury-wires", "Slack evidence: Channel #treasury-wires"),
        (rf"has:link {EXC_WIRE}", f"query (1) has:link {EXC_WIRE}"),
        (rf"in:#treasury-wires {EXC_WIRE}", f"query (2) in:#treasury-wires {EXC_WIRE}"),
        (rf"in:#treasury-wires [\"“]{EXC_WIRE}[\"”]", f'query (3) in:#treasury-wires "{EXC_WIRE}"'),
        (r"Result:", "Result: [which query worked]"),
        (r"Approvers found:", "Approvers found: ..."),
        (r"Missing dual approval", "the statement Missing dual approval"),
        (r"Exception code applied on wire issue:\s*TRE-900 High-Risk Exception",
         "Exception code applied on wire issue: TRE-900 High-Risk Exception"),
        (r"Action requested:\s*Chief Compliance Officer", "Action requested: Chief Compliance Officer (per "
                                                          "Compliance-Alerts board pinned issue) to determine "
                                                          "corrective action and whether wire may proceed."),
    ]
    miss = [desc_ for rx, desc_ in need if not re.search(rx, d, re.I | re.S)]
    if miss:
        out.append("Template B-3 description is missing: " + "; ".join(miss) + ".")
    m = re.search(r"Result:(.{0,160})", d, re.S)
    if m:
        seg = re.split(r"Approvers found", m.group(1))[0]
        first = re.search(r"\(([123])\)|query\s*#?\s*([123])\b|(has:link)|(in:#treasury-wires\s*[\"“])|"
                          r"(in:#treasury-wires)|(exhausted)", seg, re.I)
        if first:
            n = first.group(1) or first.group(2) or ("1" if first.group(3) else "3" if first.group(4) else
                                                     "2" if first.group(5) else "x")
            if n != "1":
                out.append(f"Slack evidence Result is wrong: query (1) has:link {EXC_WIRE} is the first query in "
                           "the SOP order that returns the approval thread - state that query (1) worked.")
    left = templates.unfilled_placeholders(desc)
    left = [p for p in left if p != "[Wire Control Exception]"]
    if left:
        out.append(f"Fill the template placeholders {left}.")
    return out


# ---- pre rules -----------------------------------------------------------------------------------

def _verified_on_unapproved(ctx: Context, a: Action):
    if not a.tool.startswith("jira__") or a.kind == "jira_create":
        return None
    key = _issue_key(a)
    if key not in NOT_VERIFIED_ISSUES or not re.search(r"status\s*=\s*verified", a.text or "", re.I):
        return None
    if re.search(r"\b(?:not|cannot|no|unable)\b.{0,30}status\s*=\s*verified", a.text, re.I):
        return None
    return (f"{key} ({NOT_VERIFIED_ISSUES[key]}) does not have two qualifying \"Approved\" replies from VP-or-higher "
            "approvers, so it must not be marked status=verified. Apply TRE-900 and escalate instead.")


def _tre900_on_verified(ctx: Context, a: Action):
    if not a.tool.startswith("jira__") or a.kind == "jira_create":
        return None
    key = _issue_key(a)
    if key not in VERIFIED.values():
        return None
    in_labels = any("TRE-900" in str(x).upper() for x in a.labels)
    in_text = "TRE-900" in (a.text or "").upper() and not NEG.search(a.text or "")
    if in_labels or in_text:
        wire = next(w_ for w_, k in VERIFIED.items() if k == key)
        return (f"{key} ({wire}) has two qualifying Approved replies (dual authorization confirmed); do not apply "
                f"TRE-900 to it - add a comment containing status=verified instead.")
    return None


def _comp_create(ctx: Context, a: Action):
    if not _is_comp_create(a):
        return None
    wire = _wire_of_create(a)
    if wire in VERIFIED:
        return (f"{wire} has confirmed dual approval (happy path) - no Compliance ticket is required. "
                f"Comment status=verified on {VERIFIED[wire]} instead.")
    probs = []
    if not _assignee_ok((a.recipients or [""])[0]):
        probs.append(f"Assign the Compliance-Alerts issue to {CCO} (Chief Compliance Officer listed on the pinned "
                     "Queue Roles & Assignees issue OPS-246).")
    if wire == EXC_WIRE:
        if _comp_tickets(ctx).get(EXC_WIRE):
            return (f"A Compliance-Alerts issue for {EXC_WIRE} was already created "
                    f"({', '.join(_comp_tickets(ctx)[EXC_WIRE])}); do not create a duplicate.")
        if prior_denials(ctx, "[comp-b3]") < 2:
            probs = _b3_problems(a.subject, a.text, (a.recipients or [""])[0])
    return ("[comp-b3] " + " ".join(probs)) if probs else None


def _urgent_amounts(ctx: Context, a: Action):
    if a.kind != "slack_post":
        return None
    w = world(ctx)
    if not w.is_channel(a.channel, "compliance-urgent") or w.dm_recipients(a):
        return None
    m = AMOUNT_BANK.search(a.text or "")
    return (f"#compliance-urgent posts must reference the Jira key only - no wire amounts or beneficiary bank "
            f"details (found \"{m.group(0)}\").") if m else None


def _file_names(ctx: Context, a: Action):
    if a.kind not in ("file_write", "workbook_write"):
        return None
    existing = {f.split("/")[-1] for f in world(ctx).files()}
    bad = [f for f in strict_writes(a) if " " in f and f not in existing]
    return (f"File names must not contain spaces; use underscores (e.g. {bad[0].replace(' ', '_')}).") if bad else None


# ---- completion rules ----------------------------------------------------------------------------

def _cell_text(v: str) -> str:
    return str(v or "").strip().strip("\"'“”‘’").strip()


def _wire_row_problems(w, book: str, wire: str) -> list[str] | None:
    row = w.find(re.escape(book) + "$", HDR, HDR, wire)
    if row is None:
        return None
    query, approvers, dual, code = WIRES[wire]
    c = lambda rx: w.col(row, rx)
    out = []
    if query.lower() not in norm(c(r"^Slack Query Used$")):
        out.append(f'Slack Query Used = "{query}" (the first query in the SOP order that returns the thread)')
    got = [(c(rf"^Approver {i} Name$"), c(rf"^Approver {i} Title$"), c(rf"^Approver {i} Text$")) for i in (1, 2)]
    for name, title in approvers:
        if not any(norm(name) in norm(gn) and norm(title) in norm(gt) and _cell_text(gx) == "Approved."
                   for gn, gt, gx in got):
            out.append(f'an approver with Name "{name}", Title "{title}", Text "Approved."')
    if len(approvers) == 2 and norm(got[0][0]) and norm(got[0][0]) == norm(got[1][0]):
        out.append("two distinct approvers")
    if _cell_text(c(r"^Dual Auth Confirmed")).upper() != dual:
        out.append(f'Dual Auth Confirmed (Y/N) = "{dual}"')
    ex = c(r"^Exception Code Applied$")
    if code and code not in ex.upper():
        out.append(f'Exception Code Applied = "TRE-900 High-Risk Exception"')
    if not code and "TRE-900" in ex.upper() and not NEG.search(ex):
        out.append("no TRE-900 in Exception Code Applied (dual approval confirmed)")
    return out


def _wire_log(ctx: Context):
    w = world(ctx)
    books = [b for b in w.current if re.search(r"\.xlsx$", b, re.I)]
    pop = next((b for b in books if re.search(BOOK, b, re.I)), None)
    for wire in WIRES:
        results = {b: _wire_row_problems(w, b, wire) for b in books}
        if any(r == [] for r in results.values()):
            yield True, "", []
            continue
        probs = results.get(pop) if pop else None
        if probs is None:
            probs = ["a row for this Wire ID"]
        yield (False, f"Wire log for {wire} in Wire_Population_Q1_2026.xlsx is incomplete/incorrect - set: "
                      + "; ".join(probs) + ".", [R_VERIFY, R_SIGN, R_ESC])


def _source_unchanged(ctx: Context):
    w = world(ctx)
    init = w.rows(BOOK, HDR, "initial")
    if not init:
        return
    src_cols = [k for k in init[0] if k != "__row__"][:7]
    bad = []
    for r in init:
        cur = w.find(BOOK, HDR, HDR, r["Wire ID"])
        if cur is None:
            bad.append(f"{r['Wire ID']} row removed")
            continue
        for k in src_cols:
            if not same(cur.get(k), r.get(k) if r.get(k) not in ("", "None") else None):
                bad.append(f"{r['Wire ID']} {k} changed (was \"{r.get(k)}\")")
    yield (not bad, "SOURCE DATA columns of the population workbook must stay as provided: " + "; ".join(bad[:6])
           + ". Restore the original values and only fill the AGENT-FILL columns.", [R_POP])


def _jira_done(ctx: Context):
    writes = _jira_writes(ctx)
    for wire, key in VERIFIED.items():
        ok = any(_issue_key(a) == key and re.search(r"status\s*=\s*verified", a.text or "", re.I) for a in writes)
        yield (ok, f"{key} ({wire}): dual approval is confirmed but no Jira comment containing \"status=verified\" "
                   f"was added. Add a comment on {key} that includes status=verified.", [R_HAPPY])
    ok = any(_issue_key(a) == EXC_ISSUE and ("TRE-900" in (a.text or "").upper()
                                              or any("TRE-900" in str(x).upper() for x in a.labels))
             for a in writes)
    yield (ok, f"{EXC_ISSUE} ({EXC_WIRE}) lacks dual approval but was not updated with exception code TRE-900. "
               f"Update {EXC_ISSUE} with \"TRE-900 High-Risk Exception\" (comment or label).", [R_ESC, R_TRE])
    keys = [k for k in _comp_tickets(ctx).get(EXC_WIRE, []) if k]
    if not keys:
        yield (False, f"No Compliance-Alerts (project COMP) issue was created for {EXC_WIRE}. Create it titled "
                      f"\"Exception Report: International Wire Control Exception – {EXC_WIRE}\", Template B-3 as the "
                      f"description, assigned to {CCO}.", [R_ESC, R_ESC2, R_QA, R_B3])
        return
    probs = _b3_problems(*_final_comp(ctx, keys[-1]))
    yield (not probs, f"Compliance-Alerts issue {keys[-1]} for {EXC_WIRE}: " + " ".join(probs)
           + f" Update {keys[-1]} accordingly.", [R_ESC, R_ESC2, R_QA, R_B3T])


# ---- messages ------------------------------------------------------------------------------------

def _specs(ctx: Context) -> list[Comm]:
    w = world(ctx)
    keys = [k for k in _comp_tickets(ctx).get(EXC_WIRE, []) if k]
    key = keys[-1] if keys else None
    hint_key = key or "<key returned when you create the COMP issue>"
    exact = (rf"\[Compliance\] International wire control exception filed – Jira: {re.escape(key)}\s*\|\s*"
             rf"Wire ID: {EXC_WIRE}\s*\|\s*OPS-TRE-WIRE-{EXC_WIRE}\s*\|\s*Analyst: \S.*") if key else r"(?!)"
    hint = (f"[Compliance] International wire control exception filed — Jira: {hint_key} | Wire ID: {EXC_WIRE} | "
            f"OPS-TRE-WIRE-{EXC_WIRE} | Analyst: <your name>"
            + ("" if key else "  (create the Compliance-Alerts issue first; post immediately after it exists)"))

    def about(a: Action) -> bool:
        if a.kind not in ("slack_post", "slack_dm") or EXC_WIRE not in (a.text or ""):
            return False
        return (a.kind == "slack_post" and w.is_channel(a.channel, "compliance-urgent")) or \
            (a.text or "").lstrip().startswith("[Compliance]")

    return [Comm("b4_pointer", "slack_post", about, f"Template B-4 pointer for {EXC_WIRE} in #compliance-urgent",
                 [R_ESC2, R_B4, R_B4T], channel="compliance-urgent", exact=exact, exact_hint=hint)]


RULES: list[Rule] = []
RULES += pre_rule("vanguard.no_verified_without_dual", _verified_on_unapproved, [R_SIGN, R_HAPPY],
                  "Do not mark this wire verified.")
RULES += pre_rule("vanguard.no_tre900_on_verified", _tre900_on_verified, [R_HAPPY, R_TRE],
                  "Comment status=verified on the wire issue instead.")
RULES += pre_rule("vanguard.comp_ticket", _comp_create, [R_ESC, R_ESC2, R_QA, R_B3, R_HAPPY],
                  "Fix the Compliance-Alerts issue as listed.")
RULES += pre_rule("vanguard.urgent_no_amounts", _urgent_amounts, [R_ESC2, R_B4],
                  "Remove amounts / bank details; reference the Jira key only.")
RULES += pre_rule("vanguard.file_names", _file_names, [R_NAMES], "Rename the file with underscores.")
RULES += comm_rules("vanguard.b4", _specs)
RULES += no_placeholders([R_B4T], literal=["[Compliance]", "[Wire Control Exception]"])
RULES += state_rule("vanguard.wire_log", _wire_log, "Fill the AGENT-FILL columns with the values listed.")
RULES += state_rule("vanguard.source_data", _source_unchanged, "Restore the SOURCE DATA cells.")
RULES += state_rule("vanguard.jira_outcomes", _jira_done, "Make the Jira updates listed.")
