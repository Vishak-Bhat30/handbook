"""SOP verifiers for insurance_vanguard_shield_mutual_fe30fce5 - Q1 2026 international wire dual-authorization
audit (SOP §3.3, Templates B-3 / B-4, Appendix C TRE-900).

Facts (seed data): wires in workbook order INTL-2026-0147 (OPS-2), -0151 (OPS-3), -0158 (OPS-4), -0163 (OPS-5);
#treasury-wires threads: 0147 Karen Stills (VP) + Michael Drury (SVP) -> dual OK; 0151 only Karen Stills -> missing;
0158 Karen Stills + Brett Connors (Senior Manager, below threshold) -> missing; 0163 Karen Stills + Priya Mehta (AVP)
-> dual OK. Compliance-Alerts pinned issue OPS-1: Chief Compliance Officer = diana.walsh. Project key OPS.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from ..kit import (Action, Comm, Context, World, comm_rules, dashes, no_placeholders, norm, pre_rule, prior_denials,
                   state_rule, world)

WB = r"Wire_Population_Q1_2026\.xlsx$"
HDR = r"^Wire ID$"
CHANNEL = "compliance-urgent"
CCO = "diana.walsh"
PROJECT = "OPS"
WIRE_RX = re.compile(r"INTL-2026-\d{4}")
VERIFIED_RX = re.compile(r"status=verified", re.I)
TRE_RX = re.compile(r"TRE-900 High-Risk Exception", re.I)
JIRA_KINDS = ("jira_create", "jira_comment", "jira_update", "jira_transition", "jira_link")

R_ORDER = ("3.3", "Pull population:", "§3.3 Pull population")
R_VERIFY = ("3.3", "Verify authorization:", "§3.3 Verify authorization")
R_EXHAUST = ("3.3", "Vanguard Shield Mutual — Core Operations SOP “Slack search exhausted”", "§3.3 Verify authorization (cont.)")
R_SIGN = ("3.3", "Check signatories:", "§3.3 Check signatories")
R_ESC = ("3.3", "Escalation (missing dual approval):", "§3.3 Escalation (missing dual approval)")
R_HAPPY = ("3.3", "Happy path:", "§3.3 Happy path")
R_ROLES = ("1.3", "Queue Assignee (role-based routing):", "§1.3 Queue Assignee")
R_B3HEAD = ("7.3", "Template B-2: T&E Expense Review Flag", "Appendix B Template B-3 (use exactly as written)")
R_B3 = ("7.3", "Wire ID: [Wire ID] OPS-TRE-WIRE issue:", "Template B-3")
R_B3END = ("7.3", "Vanguard Shield Mutual — Core Operations SOP Exception code applied on wire issue", "Template B-3 (cont.)")
R_B4 = ("7.3", "Template B-4: Compliance-Alerts Pointer", "Template B-4")
R_B4T = ("7.3", "Compliance International wire control exception filed", "Template B-4 text")
R_TRE900 = ("7.3", "TRE-900 High-Risk Exception", "Appendix C TRE-900")

KAREN = ("Karen Stills", "VP, Treasury Operations", "Approved.")


@dataclass(frozen=True)
class Wire:
    id: str
    issue: str
    ok: bool
    ts: str
    tz: str
    a1: tuple
    a2: tuple | None

    @property
    def title(self) -> str:
        return f"Exception Report: International Wire Control Exception – {self.id}"

    @property
    def approvers(self) -> str:
        return "; ".join(f"{n} ({t})" for n, t, _ in (self.a1, self.a2) if n) if self.a2 else f"{self.a1[0]} ({self.a1[1]}) only"


# Parent thread ts 15:00Z -> 10:00 AM EST (before the 2026-03-08 DST switch) / 11:00 AM EDT after it.
WIRES = [
    Wire("INTL-2026-0147", "OPS-2", True, "2026-03-04, 10:00 AM", "EST", KAREN, ("Michael Drury", "SVP, Finance & Risk", "Approved.")),
    Wire("INTL-2026-0151", "OPS-3", False, "2026-03-11, 11:00 AM", "EDT", KAREN, None),
    Wire("INTL-2026-0158", "OPS-4", False, "2026-03-19, 11:00 AM", "EDT", KAREN,
         ("Brett Connors", "Senior Manager, Treasury Operations", "Approved.")),
    Wire("INTL-2026-0163", "OPS-5", True, "2026-03-27, 11:00 AM", "EDT", KAREN, ("Priya Mehta", "AVP, Enterprise Risk", "Approved.")),
]
BY_ID = {x.id: x for x in WIRES}
BY_ISSUE = {x.issue: x for x in WIRES}
AMOUNTS_RX = r"\b(312,?500|87,?200|204,?750|519,?000)(\.00)?\b"
BANKS_RX = r"Deutsche Bank|ING Bank|DNB Bank|Barclays"


# ---- Jira view ---------------------------------------------------------------------------------------

def _json(v) -> dict:
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except ValueError:
            return {}
    return v if isinstance(v, dict) else {}


def _fields(a: Action) -> dict:
    return {**_json(a.args.get("additional_fields")), **_json(a.args.get("fields"))}


def _adf_text(v) -> str:
    if isinstance(v, dict):
        if isinstance(v.get("text"), str):
            return v["text"]
        return "\n".join(_adf_text(c) for c in v.get("content") or [])
    if isinstance(v, list):
        return "\n".join(_adf_text(c) for c in v)
    return "" if v is None else str(v)


def _desc(a: Action) -> str | None:
    v = a.args.get("description", _fields(a).get("description"))
    return None if v is None else _adf_text(v)


def _prio(a: Action) -> str | None:
    p = _fields(a).get("priority") or a.args.get("priority")
    if isinstance(p, dict):
        p = p.get("name") or {"1": "Highest", "2": "High", "3": "Medium", "4": "Low", "5": "Lowest"}.get(str(p.get("id")))
    return str(p) if p else None


def _assignee(a: Action) -> str | None:
    v = a.args.get("assignee") or a.args.get("account_id") or _fields(a).get("assignee")
    if isinstance(v, dict):
        v = v.get("accountId") or v.get("name") or v.get("emailAddress")
    return str(v) if v else None


def _wires_in(text: str) -> set[str]:
    return set(WIRE_RX.findall(text or ""))


@dataclass
class Issue:
    key: str
    summary: str
    description: str
    assignee: str
    priority: str | None
    itype: str
    project: str

    @property
    def wire(self) -> str | None:
        ids = _wires_in(self.summary) or _wires_in(self.description)
        return next(iter(ids)) if len(ids) == 1 else None


def created(w: World) -> dict[str, Issue]:
    """Issues the agent created (successful calls), with later updates / assignments / deletes applied."""
    def build():
        out: dict[str, Issue] = {}
        for e in w.state.executed:
            a = e.action
            if not w.ok(e):
                continue
            if a.kind == "jira_create":
                m = re.search(r'"key"\s*:\s*"([A-Z][A-Z0-9_]*-\d+)"', e.result or "")
                if not m:  # no issue key in the result: the call did not create anything
                    continue
                key = m.group(1)
                it = a.args.get("issue_type") or _fields(a).get("issuetype") or ""
                it = it.get("name", "") if isinstance(it, dict) else str(it)
                out[key] = Issue(key, a.subject, _desc(a) or "", _assignee(a) or "", _prio(a), it, a.channel)
                continue
            key = str(a.args.get("issue_key") or "").upper()
            if key not in out:
                continue
            if a.kind == "jira_delete":
                out.pop(key)
            elif a.kind == "jira_update":
                f, iss = _fields(a), out[key]
                if f.get("summary"):  # the top-level "summary" arg is the tool-call note, not the issue title
                    iss.summary = str(f["summary"])
                if _desc(a) is not None:
                    iss.description = _desc(a)
                iss.assignee = _assignee(a) or iss.assignee
                iss.priority = _prio(a) or iss.priority
            elif a.tool.endswith("assign_issue") and _assignee(a):
                out[key].assignee = _assignee(a)
        return out
    return w.ctx.memo("fe30.created", build)


def comments(w: World, key: str) -> list[str]:
    return [a.text for a in w.calls("jira_comment") if a.channel.upper() == key]


def pointers(w: World, x: Wire) -> list[Action]:
    return [a for a in w.posts_in(CHANNEL) if x.id in a.text]


def wire_of(w: World, a: Action) -> str | None:
    """The wire a Jira write / #compliance-urgent post belongs to (None if unrelated or ambiguous)."""
    if a.kind in JIRA_KINDS[1:] or a.tool.endswith("assign_issue"):
        key = str(a.channel or a.args.get("issue_key") or "").upper()
        if key in BY_ISSUE:
            return BY_ISSUE[key].id
        iss = created(w).get(key)
        return iss.wire if iss else None
    if a.kind == "jira_create":
        ids = _wires_in(a.subject) or _wires_in(_desc(a) or "")
        return next(iter(ids)) if len(ids) == 1 else None
    if a.kind == "slack_post" and w.is_channel(a.channel, CHANNEL):
        ids = _wires_in(a.text)
        return next(iter(ids)) if len(ids) == 1 else None
    return None


def missing_steps(w: World, x: Wire) -> list[str]:
    cs = comments(w, x.issue)
    if x.ok:
        return [] if any(VERIFIED_RX.search(c) for c in cs) else [f"comment on {x.issue} including status=verified"]
    out = []
    if not any(TRE_RX.search(dashes(c)) for c in cs):
        out.append(f"comment on {x.issue} with exception code TRE-900 High-Risk Exception")
    if not any(i.wire == x.id for i in created(w).values()):
        out.append(f"create the Jira Task \"{x.title}\" (Template B-3, priority High, assignee {CCO})")
    if not pointers(w, x):
        out.append(f"post Template B-4 for {x.id} in #{CHANNEL}")
    return out


# ---- expected values -----------------------------------------------------------------------------------

def b3_text(x: Wire) -> str:
    a2 = "Missing" if not x.a2 else f"{x.a2[0]} | {x.a2[1]} | {x.a2[2]} | title does not meet threshold"
    return (f"Wire ID: {x.id}\nOPS-TRE-WIRE issue: OPS-TRE-WIRE-{x.id}\n"
            f"Population source: International wires population workbook from OPS-TRE-WIRES-Q1 2026 "
            f"(Wire_Population_Q1_2026.xlsx)\n"
            f"Slack evidence: #treasury-wires | Thread timestamp: {x.ts} {x.tz}\n"
            f"Approver 1: {x.a1[0]} | {x.a1[1]} | {x.a1[2]}\nApprover 2: {a2}\n"
            "Exception code applied on wire issue: TRE-900 High-Risk Exception\n"
            "Action requested: Chief Compliance Officer (per Compliance-Alerts board pinned issue) to determine "
            "corrective action and whether wire may proceed.")


def b3_parts(x: Wire) -> list[tuple[str, str]]:
    q = r"[\"“”']?"
    parts = [
        (rf"Wire ID:\s*{x.id}\b", f"Wire ID: {x.id}"),
        (rf"OPS-TRE-WIRE issue:\s*(OPS-TRE-WIRE-{x.id}|{x.issue})\b", f"OPS-TRE-WIRE issue: OPS-TRE-WIRE-{x.id}"),
        (r"Population source:\s*International wires population workbook from .{0,80}?Wire_Population_Q1_2026\.xlsx",
         "Population source: International wires population workbook from OPS-TRE-WIRES-Q1 2026 "
         "(Wire_Population_Q1_2026.xlsx)"),
        (rf"Slack evidence:\s*#?treasury-wires\s*\|\s*Thread timestamp:\s*{re.escape(x.ts)}"
         rf"(?:[ \t]*\(?(?:{x.tz}|ET)\)?)?(?![ \t]*\(?E[SD]T)",
         f"Slack evidence: #treasury-wires | Thread timestamp: {x.ts} {x.tz}"),
        (rf"Approver 1:\s*{re.escape(x.a1[0])}\s*\|\s*{re.escape(x.a1[1])}\s*\|\s*{q}Approved\.?{q}",
         f"Approver 1: {x.a1[0]} | {x.a1[1]} | {x.a1[2]}"),
        (r"Exception code applied on wire issue:\s*TRE-900 High-Risk Exception",
         "Exception code applied on wire issue: TRE-900 High-Risk Exception"),
        (r"Action requested:\s*Chief Compliance Officer \(per Compliance-Alerts board pinned issue\) to determine "
         r"corrective action and whether wire may proceed",
         "Action requested: Chief Compliance Officer (per Compliance-Alerts board pinned issue) to determine corrective "
         "action and whether wire may proceed."),
    ]
    if x.a2:
        parts.append((rf"Approver 2:\s*{re.escape(x.a2[0])}\s*\|\s*{re.escape(x.a2[1])}\s*\|"
                      r"(?:(?!Exception code applied).)*title does not meet threshold",
                      f"Approver 2: {x.a2[0]} | {x.a2[1]} | {x.a2[2]} | title does not meet threshold"))
    else:
        parts.append((rf"Approver 2:\s*{q}Missing\b", "Approver 2: Missing"))
    return parts


def b3_problems(x: Wire, desc: str) -> list[str]:
    from ..templates import unfilled_placeholders
    body = dashes(desc)
    out = [f"description must contain \"{d}\"" for rx, d in b3_parts(x) if not re.search(rx, body, re.I | re.S)]
    left = unfilled_placeholders(desc)
    if left:
        out.append(f"description still has template placeholders {left}")
    return out


def issue_problems(x: Wire, i: Issue, check_prio: bool = True) -> list[str]:
    out = []
    if norm(i.summary) != norm(x.title):
        out.append(f"title must be exactly \"{x.title}\" (got \"{i.summary}\")")
    if i.project and i.project.upper() != PROJECT:
        out.append(f"create it in project {PROJECT} (the wire issue's project), not {i.project}")
    if i.itype and norm(i.itype) != "task":
        out.append(f"issue type must be Task (got {i.itype})")
    if norm(i.assignee).split("@")[0] not in (CCO, "diana walsh"):
        out.append(f"assign it to {CCO} (Chief Compliance Officer on the Compliance-Alerts pinned issue OPS-1)"
                   + (f", not {i.assignee}" if i.assignee else ""))
    if check_prio and norm(i.priority) != "high":
        out.append("priority must be High" + (f" (got {i.priority})" if i.priority else ""))
    out += b3_problems(x, i.description)
    return out


# ---- pre rules ------------------------------------------------------------------------------------------

def _order(ctx: Context, a: Action) -> str | None:
    w = world(ctx)
    wid = wire_of(w, a)
    if wid not in BY_ID:
        return None
    for x in WIRES[:WIRES.index(BY_ID[wid])]:
        todo = missing_steps(w, x)
        tag = f"[order:{x.id}]"
        if todo and prior_denials(ctx, tag) < 2:
            return (f"{tag} Wires are processed in workbook order, completing all steps for each wire before the next. "
                    f"{x.id} ({x.issue}) is not finished: {'; '.join(todo)}. Finish {x.id} before working on {wid}.")
    return None


def _outcome(ctx: Context, a: Action) -> str | None:
    w = world(ctx)
    if a.kind == "jira_comment":
        x = BY_ISSUE.get(a.channel.upper())
        if not x:
            return None
        if x.ok and TRE_RX.search(dashes(a.text)) and not VERIFIED_RX.search(a.text):
            return (f"{x.id} ({x.issue}) has dual approval from two qualifying approvers ({x.approvers}); it takes the "
                    f"happy path: comment including status=verified, no TRE-900 exception.")
        if not x.ok and VERIFIED_RX.search(a.text):
            why = "only one Approved reply" if not x.a2 else f"{x.a2[0]}'s title ({x.a2[1]}) is not VP/AVP/SVP/EVP/C-level"
            return (f"{x.id} ({x.issue}) lacks dual approval ({why}); do not mark it status=verified. Comment with "
                    f"exception code TRE-900 High-Risk Exception and escalate per §3.3.")
    if a.kind == "jira_create":
        wid = wire_of(w, a)
        x = BY_ID.get(wid or "")
        if x and x.ok and re.search(r"exception", f"{a.subject} {_desc(a) or ''}", re.I):
            return (f"{x.id} has dual approval ({x.approvers}); per the happy path no Compliance ticket is required.")
    return None


def _task(ctx: Context, a: Action) -> str | None:
    if a.kind != "jira_create":
        return None
    w = world(ctx)
    x = BY_ID.get(wire_of(w, a) or "")
    if not x or x.ok or not re.search(r"exception", f"{a.subject} {_desc(a) or ''}", re.I):
        return None
    tag = f"[task:{x.id}]"
    if prior_denials(ctx, tag) >= 2:
        return None
    dup = [i.key for i in created(w).values() if i.wire == x.id]
    if dup:
        return f"{tag} The Exception Report for {x.id} already exists ({', '.join(dup)}); do not create another."
    i = Issue("", a.subject, _desc(a) or "", _assignee(a) or "", None, str(a.args.get("issue_type") or ""), a.channel)
    probs = issue_problems(x, i, check_prio=False)
    if not _assignee(a):
        probs = [p for p in probs if not p.startswith("assign")]
    if probs:
        return (f"{tag} Exception Report for {x.id}: " + "; ".join(probs) + f". Template B-3 filled for this wire:\n"
                f"{b3_text(x)}")
    return None


# ---- completion rules ----------------------------------------------------------------------------------

def _comment_checks(ctx: Context):
    w = world(ctx)
    for x in WIRES:
        cs = comments(w, x.issue)
        if x.ok:
            yield (any(VERIFIED_RX.search(c) for c in cs),
                   f"{x.id}: no comment on {x.issue} containing \"status=verified\". Dual approval is confirmed "
                   f"({x.approvers}); add a comment on {x.issue} that includes status=verified.", [R_HAPPY])
        else:
            yield (any(TRE_RX.search(dashes(c)) for c in cs),
                   f"{x.id}: no comment on {x.issue} with exception code \"TRE-900 High-Risk Exception\" (dual approval "
                   f"missing: {x.approvers}). Post that comment on {x.issue}.", [R_ESC, R_TRE900])


def _task_checks(ctx: Context):
    w = world(ctx)
    ex = created(w)
    for x in WIRES:
        mine = [i for i in ex.values() if i.wire == x.id and re.search(r"exception", f"{i.summary} {i.description}", re.I)]
        if x.ok:
            yield (not mine, f"{x.id} has dual approval but exception issue(s) {[i.key for i in mine]} were created; "
                             "the happy path needs no Compliance ticket.", [R_HAPPY])
            continue
        refs = [R_ESC, R_ROLES, R_B3HEAD, R_B3, R_B3END, R_EXHAUST]
        if not mine:
            yield (False, f"{x.id}: no Exception Report task. Create a Jira Task in project {PROJECT}, priority High, "
                          f"title \"{x.title}\", assignee {CCO}, description (Template B-3):\n{b3_text(x)}", refs)
            continue
        probs = {i.key: issue_problems(x, i) for i in mine}
        if not any(not p for p in probs.values()):
            key = mine[-1].key
            yield (False, f"{x.id}: Exception Report {key} does not match §3.3 / Template B-3: "
                          + "; ".join(probs[key]) + f". Fix it with jira update. Expected description:\n{b3_text(x)}", refs)


def _cell_ok(v: str, want: str) -> bool:
    return norm(v) == norm(want)


def _wb_checks(ctx: Context):
    w = world(ctx)
    refs = [R_VERIFY, R_SIGN, R_ESC]
    rows = w.rows(WB, HDR)
    if not rows:
        yield (False, "Wire_Population_Q1_2026.xlsx (header row 'Wire ID') is missing or unreadable in /workdir; "
                      "record each wire's outcome in that workbook.", [R_ORDER])
        return
    col = w.col
    init = {col(r, HDR): r for r in w.rows(WB, HDR, "initial")}
    cur = {col(r, HDR): r for r in rows}
    src = [r"^Wire ID$", r"^Amount \(USD\)$", r"^Payee$", r"^Beneficiary Bank$", r"^Date Initiated$", r"^Quarter$",
           r"^Jira Issue$"]
    extra = sorted(k for k in cur if k not in init)
    yield (not extra, f"Wire_Population_Q1_2026.xlsx has unexpected rows {extra}; keep exactly the four population "
                      "wires.", [R_ORDER])
    for wid, r0 in init.items():
        r = cur.get(wid)
        if r is None:
            yield (False, f"Wire_Population_Q1_2026.xlsx: the row for {wid} is missing; restore it.", [R_ORDER])
            continue
        changed = [rx.strip("^$").replace("\\", "") for rx in src if col(r, rx) != col(r0, rx)]
        yield (not changed, f"{wid}: pre-populated source columns {changed} were changed; restore the original "
                            "values (only fill the AUDIT columns).", [R_ORDER])
    for x in WIRES:
        r = cur.get(x.id)
        if r is None:
            continue
        bad = []
        ev = col(r, r"^Slack Evidence$")
        if not re.fullmatch(rf"{re.escape(x.ts)}(?:\s*\(?(?:{x.tz}|ET)\)?)?", ev.strip()):
            bad.append(f"Slack Evidence = \"{x.ts} {x.tz}\" (got \"{ev}\")")
        for n, ap in ((1, x.a1), (2, x.a2)):
            want = ap or ("", "", "")
            for field, v in zip(("Name", "Title", "Text"), want):
                got = col(r, rf"^Approver {n} {field}$")
                ok = got.strip().strip("\"“”'") == v if field == "Text" else _cell_ok(got, v)
                if not ok:
                    bad.append(f"Approver {n} {field} = " + (f"\"{v}\"" if v else "empty") + f" (got \"{got}\")")
        dual = col(r, r"^Dual Auth Confirmed")
        if dual.strip().upper() != ("Y" if x.ok else "N"):
            bad.append(f"Dual Auth Confirmed (Y/N) = {'Y' if x.ok else 'N'} (got \"{dual}\")")
        code = col(r, r"^Exception Code Applied$")
        if not x.ok and norm(code) != norm("TRE-900 High-Risk Exception"):
            bad.append(f"Exception Code Applied = \"TRE-900 High-Risk Exception\" (got \"{code}\")")
        if x.ok and "TRE-900" in code.upper():
            bad.append(f"Exception Code Applied must not be TRE-900 (dual approval confirmed; got \"{code}\")")
        yield (not bad, f"Wire_Population_Q1_2026.xlsx row {x.id}: set " + "; ".join(bad) + ".",
               refs + ([R_TRE900] if not x.ok else []))


def _specs(ctx: Context) -> list[Comm]:
    w = world(ctx)
    ex = created(w)
    out = []
    for x in WIRES:
        def about(a: Action, x=x) -> bool:
            return (a.kind in ("slack_post", "slack_dm") and x.id in a.text
                    and (w.is_channel(a.channel, CHANNEL) or bool(re.search(r"wire control exception", a.text, re.I))))
        if x.ok:
            out.append(Comm(f"b4:{x.id}", "slack_post", about, f"#{CHANNEL} alert for {x.id}", [R_HAPPY, R_ESC],
                            channel=CHANNEL, required=False,
                            forbidden=f"{x.id} has dual approval ({x.approvers}); the happy path needs no Compliance "
                                      f"ticket and no #{CHANNEL} alert."))
            continue
        keys = [i.key for i in ex.values() if i.wire == x.id]
        key_rx = "(" + "|".join(re.escape(k) for k in keys) + ")" if keys else r"(?!)"
        hint = keys[-1] if keys else "<key of the Exception Report task - create that task first>"
        text = (f"Compliance International wire control exception filed — Jira: {hint} | Wire ID: {x.id} | "
                f"OPS-TRE-WIRE-{x.id} | <your role>")
        out.append(Comm(
            f"b4:{x.id}", "slack_post", about, f"Template B-4 pointer for {x.id}", [R_ESC, R_B4, R_B4T],
            channel=CHANNEL,
            body=[(rf"Compliance International wire control exception filed\s*–\s*Jira:\s*{key_rx}\s*\|\s*Wire ID:\s*"
                   rf"{x.id}\s*\|\s*(OPS-TRE-WIRE-{x.id}|{x.issue})\s*\|\s*\S", f"the Template B-4 text \"{text}\"")],
            banned=[(r"\$\s?\d", "Do not post dollar amounts in Slack - reference Jira only."),
                    (AMOUNTS_RX, "Do not post wire amounts in Slack - reference Jira only."),
                    (BANKS_RX, "Do not post beneficiary bank details in Slack - reference Jira only.")]))
    return out


RULES = [
    *pre_rule("wire.order", _order, [R_ORDER], "Finish the earlier wire's steps first."),
    *pre_rule("wire.outcome", _outcome, [R_VERIFY, R_SIGN, R_ESC, R_HAPPY], "Apply the correct §3.3 branch."),
    *pre_rule("wire.exception_task_fields", _task, [R_ESC, R_ROLES, R_B3HEAD, R_B3, R_B3END],
              "Fix the issue fields as listed and create it again."),
    *state_rule("wire.jira_comments", _comment_checks, "Add the missing Jira comment."),
    *state_rule("wire.exception_task", _task_checks, "Create or fix the Exception Report task as listed."),
    *state_rule("wire.workbook", _wb_checks, "Write the listed values into Wire_Population_Q1_2026.xlsx."),
    *comm_rules("wire.b4", _specs),
    *no_placeholders([R_B4]),
]
