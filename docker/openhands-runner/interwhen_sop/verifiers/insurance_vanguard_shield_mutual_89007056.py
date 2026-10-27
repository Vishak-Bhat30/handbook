"""Verifiers for insurance_vanguard_shield_mutual_89007056: audit the Pending Approval Sales T&E reports in
OPS_HR_TE (SOP §6.2), built from the SOP, the Jira/Calendar/Shopify/Slack seed and nothing else.

Expected outcome derived from the seed (today Mon 2026-04-06; Mar 28 and Apr 4 are Saturdays):
- OPS_HR_TE-2 Marcus Chen: all lines covered (Apr 1-3 Northeast Client Tour, Apr 2 Acme meeting) -> approve.
- OPS_HR_TE-3 Priya Sharma: line 1 (Sat Mar 28 dinner, no calendar) rejected - Missing business justification;
  line 2 merch passes Shopify (#VS-2001, priya.sharma, $350); line 3 (Mar 30 cab vs. standup) left to the agent.
  Reporting Manager jnakamura -> Template B-2 DM to Jun Nakamura.
- OPS_HR_TE-4 Derek Washington: line 1 polo shirts not in Shopify for his email -> Unauthorized vendor, line 1;
  line 2 mileage covered by Apr 3 TechForward site visit. Reporting Manager blank -> email people@ (Template
  B-9), no B-2 until the manager is confirmed.
- OPS_HR_TE-5 Aisha Robinson: line 1 covered by the Apr 3 QBR; lines 2-3 (Apr 3 flight/hotel vs. the Apr 4-8
  conference) are ambiguous, so only consistency is enforced (rejection -> B-2 DM to Diana Park; approval -> none).
Workflow transitions (Approve/Reject) are not enforced: the seeded Jira workflow does not offer them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..kit import (Action, Comm, Context, World, comm_rules, dashes, money_rx, no_placeholders, pre_rule,
                   state_rule, world)

TAKE_ACTION = ("6.2", "Step 4. Take action", "§6.2 Step 4 Take action")
CROSS_REF = ("6.2", "Step 2. Cross-reference business activity", "§6.2 Step 2 Cross-reference business activity")
NO_EVENT = ("6.2", "windows). If (A) and no matching calendar event", "§6.2 Step 2 (no matching calendar event)")
SHOPIFY = ("6.2", "Step 3. Verify merch purchases", "§6.2 Step 3 Verify merch purchases")
SCOPE = ("6.2", "Objective: Ensure employee expenses", "§6.2 Step 1 Review submissions")
MANAGER = ("1.3", "Reporting Manager: Custom field", "§1.3 Reporting Manager")
B2 = ("7.3", "Template B-2: T&E Expense Review Flag", "Appendix B Template B-2")
B2_ACTION = ("7.3", "Action Taken: Line item rejected", "Appendix B Template B-2 (Action Taken)")
B9 = ("7.3", "[Reporting Manager Lookup] Employee:", "Appendix B Template B-9")

APPROVAL_TEXT = "T&E review complete—all lines supported | OPS-HR-TE-{n}"
MBJ, UV = "Missing business justification", "Unauthorized vendor"
NOTE_TEXT = "{reason}. Please submit personal reimbursement for line items: {lines}."
FLAG_RX = r"T&E Review Flag|direct report|line items? rejected"
OUT_OF_SCOPE = ("CLM_LIFE", "CLM_LEGAL", "OPS_AP_INV", "OPS_AP_TRACE")


def key(s) -> str:
    """Issue key without separators/case, so OPS_HR_TE-3 == OPS-HR-TE-3."""
    return re.sub(r"[-_\s]", "", str(s or "")).upper()


def issue_rx(n: int) -> str:
    return rf"OPS[-_ ]?HR[-_ ]?TE[-_ ]?{n}(?!\d)"


# ---- decision comments -------------------------------------------------------------------------

def approval_of(text: str) -> int | None:
    """Report number referenced by an approval comment, else None."""
    m = re.search(r"T&E review complete\s*[-–—]+\s*all lines supported\s*\|\s*OPS[-_ ]?HR[-_ ]?TE[-_ ]?(\d+)",
                  dashes(text), re.I)
    return int(m.group(1)) if m else None


def note_of(text: str) -> tuple[str, set[int]] | None:
    """(reason, rejected line numbers) of a rejection note, else None."""
    t = dashes(text)
    if not re.search(r"personal reimbursement", t, re.I):
        return None
    mbj, uv = bool(re.search(MBJ, t, re.I)), bool(re.search(UV, t, re.I))
    reason = "both" if mbj and uv else MBJ if mbj else UV if uv else ""
    m = re.search(r"personal reimbursement for line items?\s*:?\s*([0-9][0-9,\s&]*(?:and\s*[0-9]+)?)", t, re.I)
    lines = {int(x) for x in re.findall(r"\d+", m.group(1))} if m else set()
    return reason, lines


@dataclass(frozen=True)
class Report:
    n: int
    employee: str
    emp_id: str
    reason: str | None          # required rejection reason; None = approve; "" = agent's call (report 5)
    must: frozenset             # line numbers that must be rejected
    never: frozenset            # line numbers that must not be rejected
    why: str


REPORTS = {
    2: Report(2, "Marcus Chen", "EMP-1847", None, frozenset(), frozenset({1, 2, 3}),
              "all three lines are covered by Calendar (Apr 1-3 Northeast Client Tour - Hartford, Apr 2 Acme Corp "
              "client meeting); no merchandise lines"),
    3: Report(3, "Priya Sharma", "EMP-2103", MBJ, frozenset({1}), frozenset({2}),
              "line 1 (The Capital Grille, Sat Mar 28, $215.00) is a weekend meal with no Calendar event; line 2 "
              "(VS Team Merch, $350.00) passed Shopify (order #VS-2001 by priya.sharma@vanguardshield.com)"),
    4: Report(4, "Derek Washington", "EMP-2287", UV, frozenset({1}), frozenset({2}),
              "line 1 (VS Branded Gear polo shirts, $420.00) has no Shopify order under "
              "derek.washington@vanguardshield.com; line 2 (mileage, Apr 3) is covered by the TechForward site visit"),
    5: Report(5, "Aisha Robinson", "EMP-1592", "", frozenset(), frozenset({1}),
              "line 1 (Cafe Soleil, Apr 3) is covered by the Apr 3 QBR working lunch; lines 2-3 depend on your "
              "Calendar reading"),
}


def note_problem(r: Report, reason: str, lines: set[int]) -> str | None:
    if r.reason is None:
        return (f"OPS_HR_TE-{r.n} ({r.employee}) must be approved, not rejected: {r.why}. Comment exactly "
                f"\"{APPROVAL_TEXT.format(n=r.n)}\" instead.")
    want = r.reason or MBJ
    if reason != want:
        got = {"both": f"{MBJ} and unauthorized vendor", "": "no reason phrase"}.get(reason, reason)
        return (f"Rejection reason on OPS_HR_TE-{r.n} must be \"{want}\" (got {got}): {r.why}.")
    if not lines:
        return f"The note on OPS_HR_TE-{r.n} must list the rejected line numbers after \"line items:\"."
    bad, miss = sorted(lines & r.never), sorted(r.must - lines)
    if bad or miss:
        return (f"Rejected line items on OPS_HR_TE-{r.n} are wrong ({'do not list ' + ', '.join(map(str, bad)) if bad else ''}"
                f"{'; ' if bad and miss else ''}{'must include ' + ', '.join(map(str, miss)) if miss else ''}): {r.why}.")
    if r.n == 4 and lines != {1}:
        return f"OPS_HR_TE-4 rejects line item 1 only: {r.why}."
    return None


def decisions(w: World) -> dict[int, list[tuple[str, object]]]:
    """Executed decision comments per report: [('approve', n) | ('reject', (reason, lines))]."""
    out: dict[int, list] = {n: [] for n in REPORTS}
    for a in w.calls("jira_comment"):
        n = next((n for n in REPORTS if key(a.channel) == key(f"OPS_HR_TE-{n}")), None)
        if n is None:
            continue
        if approval_of(a.text) is not None:
            out[n].append(("approve", approval_of(a.text)))
        elif note_of(a.text):
            out[n].append(("reject", note_of(a.text)))
    return out


def comment_problem(ctx: Context, a: Action) -> str | None:
    if a.kind != "jira_comment":
        return None
    n = next((n for n in REPORTS if key(a.channel) == key(f"OPS_HR_TE-{n}")), None)
    if n is None:
        return None
    r, appr, note = REPORTS[n], approval_of(a.text), note_of(a.text)
    prior = {d for d, _ in decisions(world(ctx))[n]}
    if appr is not None:
        if r.reason not in (None, ""):
            return (f"OPS_HR_TE-{n} ({r.employee}) fails the Take action tests and must be rejected, not approved: "
                    f"{r.why}. Comment \"{NOTE_TEXT.format(reason=r.reason, lines=', '.join(map(str, sorted(r.must))))}\".")
        if appr != n:
            return f"The approval comment on OPS_HR_TE-{n} must reference this report: \"{APPROVAL_TEXT.format(n=n)}\"."
        if "reject" in prior:
            return f"OPS_HR_TE-{n} already has a rejection note; do not also approve it."
        return None
    if note:
        if "approve" in prior:
            return f"OPS_HR_TE-{n} already has the approval comment; do not also reject it."
        return note_problem(r, *note)
    return None


def decision_checks(ctx: Context):
    w = world(ctx)
    dec = decisions(w)
    for n, r in REPORTS.items():
        ok = False
        for kind, val in dec[n]:
            if kind == "approve" and val == n and r.reason in (None, ""):
                ok = True
            if kind == "reject" and r.reason is not None and not note_problem(r, *val):
                ok = True
        if ok:
            continue
        if r.reason is None:
            want = (f"add the Jira comment exactly \"{APPROVAL_TEXT.format(n=n)}\" and transition it from Pending "
                    "Approval to Approved (Approve)")
            refs = [TAKE_ACTION, CROSS_REF]
        elif r.reason:
            lines = ", ".join(map(str, sorted(r.must)))
            want = (f"comment the rejection note \"{NOTE_TEXT.format(reason=r.reason, lines=lines)}\""
                    f"{' (add line 3 only if you find no Calendar coverage for the Mar 30 cab)' if n == 3 else ''} "
                    "and set the workflow to rejected (Reject)")
            refs = [TAKE_ACTION, NO_EVENT if r.reason == MBJ else SHOPIFY]
        else:
            want = (f"record the decision: either the approval comment \"{APPROVAL_TEXT.format(n=n)}\" or the "
                    f"rejection note \"{NOTE_TEXT.format(reason=MBJ, lines='<rejected line numbers>')}\" (line 1 is "
                    "covered and must not be listed)")
            refs = [TAKE_ACTION, CROSS_REF]
        yield False, f"OPS_HR_TE-{n} ({r.employee}): {r.why}. Not done yet: {want}.", refs


# ---- messages ----------------------------------------------------------------------------------

def mentions(a: Action, r: Report) -> bool:
    t = f"{a.subject}\n{a.text}"
    return bool(re.search(rf"{re.escape(r.emp_id)}|{r.employee}|{issue_rx(r.n)}", t, re.I))


def b2_like(a: Action, r: Report, flag: str = FLAG_RX + "|reject") -> bool:
    return a.kind in ("slack_dm", "slack_post") and mentions(a, r) and bool(re.search(flag, a.text, re.I))


@dataclass
class DM(Comm):
    """Slack DM to one person; accepts the Slack user id, handle or a DM channel with that user."""
    uid: str = ""
    handle: str = ""
    person: str = ""

    def problems(self, a: Action, w: World) -> list[str]:
        out = super().problems(a, w)
        if self.forbidden or a.kind not in ("slack_dm", "slack_post"):
            return out
        got = w.dm_recipients(a) | {x.lstrip("@") for x in a.recipients if a.kind == "slack_dm"}
        got = {x if re.fullmatch(r"[UW][A-Z0-9]+", x) else x.lower() for x in got} - w.self_uids
        want = {self.uid, self.handle}
        if not got:
            out.append(f"Send this as a Slack direct message to {self.person} ({self.uid} / @{self.handle}), "
                       "not in a channel.")
        elif not (got & want) or (got - want):
            out.append(f"Send this direct message only to {self.person} ({self.uid} / @{self.handle}).")
        return out


def b2_body(r: Report, extra: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [(r"T&E Review Flag", "the B-2 tag [T&E Review Flag]"),
            (re.escape(r.emp_id), f"Employee ID: {r.emp_id}")] + extra


def specs(ctx: Context) -> list[Comm]:
    w = world(ctx)
    r2, r3, r4, r5 = (REPORTS[n] for n in (2, 3, 4, 5))
    dec5 = {d for d, _ in decisions(w)[5]}
    out: list[Comm] = [
        DM("b2_priya", "slack_dm", lambda a: b2_like(a, r3),
           "Template B-2 T&E Review Flag DM to Priya Sharma's Reporting Manager Jun Nakamura (jnakamura) for the "
           "rejected OPS_HR_TE-3 lines", [TAKE_ACTION, B2, B2_ACTION, MANAGER],
           body=b2_body(r3, [(money_rx(215.0), "Expense Date: March 28, 2026 | Amount: $215.00"),
                             (r"Capital Grille", "Merchant: The Capital Grille")]),
           uid="U003", handle="jnakamura", person="Jun Nakamura"),
        DM("b2_marcus", "slack_dm", lambda a: b2_like(a, r2, FLAG_RX), "Template B-2 for Marcus Chen",
           [TAKE_ACTION, B2], forbidden="OPS_HR_TE-2 (Marcus Chen) is approved - the SOP says do not send Template "
                                        "B-2 for an approved report."),
        DM("b2_derek", "slack_dm", lambda a: b2_like(a, r4, FLAG_RX), "Template B-2 for Derek Washington",
           [TAKE_ACTION, MANAGER], forbidden="OPS_HR_TE-4 has a blank Reporting Manager field - do not send Template "
           "B-2 until the manager is confirmed; email people@vanguardshield.com with Template B-9 instead."),
        Comm("b9_derek", "email",
             lambda a: a.kind in ("email_send", "email_draft") and mentions(a, r4) and (
                 "people@vanguardshield.com" in a.recipients or bool(re.search(r"Reporting Manager Lookup", a.text, re.I))),
             "Template B-9 Reporting Manager Lookup email to people@vanguardshield.com for Derek Washington "
             "(OPS_HR_TE-4 Reporting Manager field is blank)", [MANAGER, B9, TAKE_ACTION],
             to=["people@vanguardshield.com"], exact_to=False,
             body=[(r"Reporting Manager Lookup", "the B-9 tag [Reporting Manager Lookup]"),
                   (r"Derek Washington", "Employee: Derek Washington"), (r"EMP-2287", "ID: EMP-2287"),
                   (issue_rx(4), "OPS-HR-TE / expense report issue: OPS_HR_TE-4"),
                   (r"Reporting manager name and Jira username",
                    "Need: Reporting manager name and Jira username to complete required workflow notification.")]),
    ]
    if "approve" in dec5 and "reject" not in dec5:
        out.append(DM("b2_aisha", "slack_dm", lambda a: b2_like(a, r5, FLAG_RX), "Template B-2 for Aisha Robinson",
                      [TAKE_ACTION, B2], forbidden="OPS_HR_TE-5 was approved - do not send Template B-2."))
    else:
        out.append(DM("b2_aisha", "slack_dm", lambda a: b2_like(a, r5),
                      "Template B-2 T&E Review Flag DM to Aisha Robinson's Reporting Manager Diana Park (dpark) for the "
                      "rejected OPS_HR_TE-5 lines", [TAKE_ACTION, B2, B2_ACTION, MANAGER],
                      body=b2_body(r5, []), required="reject" in dec5, uid="U002", handle="dpark", person="Diana Park"))
    return out


def b2_order(ctx: Context, a: Action) -> str | None:
    """B-2 goes out only after the report was rejected (Take action applied)."""
    if a.kind not in ("slack_dm", "slack_post"):
        return None
    dec = decisions(world(ctx))
    for n in (3, 5):
        r = REPORTS[n]
        if b2_like(a, r) and not any(d == "reject" for d, _ in dec[n]):
            return (f"Template B-2 for {r.employee} is sent only after you applied Take action on OPS_HR_TE-{n} "
                    "(rejection note comment + reject). Post the rejection note first.")
    return None


# ---- scope -------------------------------------------------------------------------------------

def scope_problem(ctx: Context, a: Action) -> str | None:
    if a.kind in ("email_send", "email_draft"):
        ext = [x for x in a.recipients + a.cc if not x.endswith("@vanguardshield.com")]
        if ext:
            return (f"External recipients {', '.join(ext)}: the request is the Sales T&E audit (§6.2); vendor or other "
                    "external correspondence is outside it.")
        return None
    if not a.kind.startswith("jira_"):
        return None
    target = a.channel.upper()
    if a.kind == "jira_create":
        if target in OUT_OF_SCOPE or target == "OPS_HR_TE":
            return f"Creating issues in {target} is outside the Sales T&E audit (§6.2)."
        return None
    if a.kind == "jira_delete":
        return "Do not delete Jira issues."
    if any(target.startswith(p + "-") for p in OUT_OF_SCOPE) or key(target) == key("OPS_HR_TE-1"):
        return (f"{a.channel} is not one of the Pending Approval Sales T&E reports (OPS_HR_TE-2..5); the request is "
                "the T&E audit only. Leave it unchanged.")
    if a.kind == "jira_update" and re.search(r"customfield_10100|Reporting Manager", str(a.args), re.I):
        return ("Do not edit the Reporting Manager field; §1.3: if it is blank, email people@vanguardshield.com "
                "(Template B-9) to obtain the manager.")
    return None


RULES = (
    pre_rule("te.comments", comment_problem, [TAKE_ACTION, CROSS_REF, SHOPIFY],
             "Fix the comment as described and post it again.")
    + state_rule("te.decisions", decision_checks, "Record each report's decision on its OPS_HR_TE issue as listed.")
    + comm_rules("te", specs)
    + pre_rule("te.b2_order", b2_order, [TAKE_ACTION, B2_ACTION], "Reject the report first, then notify the manager.")
    + pre_rule("te.scope", scope_problem, [SCOPE, MANAGER], "Do not make this change.")
    + no_placeholders([B2, B9], literal=("[T&E Review Flag]", "[Reporting Manager Lookup]", "[T&E Manager Lookup]"))
)
