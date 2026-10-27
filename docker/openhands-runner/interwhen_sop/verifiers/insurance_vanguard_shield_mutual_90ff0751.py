"""Verifiers for insurance_vanguard_shield_mutual_90ff0751 - SOP §6.2 Sales T&E review (Oct 1-7 batch).

Expected outcome derived from the SOP and seed data (Jira OPS-3/4/5, calendar, Shopify orders):
- OPS-3 Okonkwo (EMP-3312): Oct 1 "VSM Branded Water Bottles - Qty 12" $144.00 is merchandise with no Shopify
  order -> reject (comment + rejected state); Reporting Manager pkim -> Template B-2 Slack DM to Peter Kim.
- OPS-4 Huang (EMP-4507): Oct 3 (Sat) $340.00 and Oct 4 (Sun) $28.00 meals have no calendar event -> reject;
  Reporting Manager blank -> email people@vanguardshield.com, then Template B-8 HR-Ops Jira ticket; no B-2.
- OPS-5 Frost (EMP-5021): every line on the calendar / Shopify order #VSM-5001 -> review comment + Approve.
This Jira has no Reject transition / Rejected status, so a rejection may be recorded via labels (§1.3).
"""

from __future__ import annotations

import re

from ..kit import (COMM_KINDS, Action, Comm, Context, World, comm_rules, dashes, no_placeholders, norm, pre_rule,
                   prior_denials, state_rule, world)
from .. import templates

STEP1 = ("6.2", "Step 1. Review submissions:", "§6.2 Step 1 (Review submissions)")
STEP2 = ("6.2", "Step 2. Cross-reference business activity:", "§6.2 Step 2 (Cross-reference business activity)")
STEP3 = ("6.2", "Step 3. Verify merch purchases:", "§6.2 Step 3 (Verify merch purchases)")
STEP4 = ("6.2", "Step 4. Take action:", "§6.2 Step 4 (Take action)")
NOTIFY = ("6.2", "Notify manager:", "§6.2 Notify manager")
STEP5 = ("6.2", "Step 5. Approve valid reports", "§6.2 Step 5 (Approve valid reports)")
RM = ("1.3", "Reporting Manager:", "§1.3 Reporting Manager field / fallback")
WF = ("1.3", "OPS-HR-TE workflow (Sales T&E):", "§1.3 OPS-HR-TE workflow")
B2 = ("7.3", "[T&E Review Flag]", "Template B-2")
B2_DETAILS = ("7.3", "Details: Expense submitted without", "Template B-2 Details line")
B2_ACTION = ("7.3", "Action Taken: Line item rejected", "Template B-2 Action Taken line")
B8 = ("7.3", "[T&E Manager Lookup]", "Template B-8")
B8_USE = ("7.3", "Use as: Jira HR-Ops description body", "Template B-8 usage")

REJECTED = ("OPS-3", "OPS-4")
APPROVED = "OPS-5"
BATCH = REJECTED + (APPROVED,)
OTHER_SEEDED = ("OPS-1", "OPS-2", "OPS-6", "FIN-1")
LABELS = {"OPS-3": "sales-west", "OPS-4": "sales-midwest"}

REJECT_NOTE_RX = r"Missing business justification\s*/\s*unauthori[sz]ed vendor\.?\s*Please submit personal reimbursement"
REJECT_NOTE = "Missing business justification/unauthorized vendor. Please submit personal reimbursement."
APPROVE_RX = r"T&E review complete\s*[-–—:,|]*\s*all lines supported"
APPROVE_NOTE = "T&E review complete—all lines supported | OPSHR-TE-OPS-5"
WHY = {"OPS-3": "Oct 1 VSM Branded Water Bottles (Qty 12) $144.00 is merchandise with no order in the Shopify "
                "Orders tab for Rachel Okonkwo (Step 3 / Step 4(c))",
       "OPS-4": "Oct 3 (Sat) Sullivan's Steakhouse Detroit $340.00 and Oct 4 (Sun) Hudson's Coffee Detroit $28.00 have "
                "no matching Calendar event and fall on a weekend (the Detroit kickoff ended Oct 2) (Step 4(a)/(b))"}

# Seed workflow: transition id -> target status (identical ids from every status).
TID = {**{i: "approved" for i in ("1", "5", "9", "13")}, **{i: "pending approval" for i in ("2", "6", "10", "14")},
       **{i: "pinned" for i in ("3", "7", "11", "15")},
       **{i: "awaiting controller review" for i in ("4", "8", "12", "16")}}

B2_TEXT = ("[T&E Review Flag] - Employee ID: EMP-3312 / Expense Date: Oct 1, 2026 | Amount: $144.00 / "
           "Merchant: VSM Branded Water Bottles — Qty 12 (VSM internal store) / Details: Expense submitted without a "
           "matching Calendar event, or Shopify promo purchase not found. / Action Taken: Line item rejected in Jira "
           "OPS-HR-TE workflow. Please review with your direct report.")
B8_TITLE = "Manager Lookup Needed – T&E Exception – Derek Huang (EMP-4507)"
B8_TEXT = ("[T&E Manager Lookup] / Employee: Derek Huang | ID: EMP-4507 / OPS-HR-TE / expense report issue: OPS-4 / "
           "Directory / People search result: Reporting Manager field blank on OPS-4; people@vanguardshield.com "
           "returned no result / Need: Correct manager Jira username or Slack handle for Template B-2 notification.")
B8_FIELDS = [
    (r"\[T&E Manager Lookup\]", '"[T&E Manager Lookup]"'),
    (r"Employee:\s*Derek Huang", '"Employee: Derek Huang | ID: EMP-4507"'),
    (r"ID:\s*EMP-4507", '"ID: EMP-4507"'),
    (r"expense report issue:\s*OPS-4\b", '"OPS-HR-TE / expense report issue: OPS-4"'),
    (r"Directory\s*/\s*People search result:\s*\S", '"Directory / People search result: <what the lookup returned>"'),
    (r"Need:\s*Correct manager Jira username or Slack handle for Template B-2 notification",
     '"Need: Correct manager Jira username or Slack handle for Template B-2 notification."'),
]
B8_TITLE_RX = r"Manager Lookup Needed\s*[–-]\s*T&E Exception\s*[–-]\s*.*(Huang|EMP-4507).*"
FLAG_RX = r"T&E Review Flag|Line item rejected in Jira"


def key(a: Action) -> str:
    return str(a.channel or "").strip().upper()


def target(a: Action) -> str | None:
    """Target status of a transition call (seed ids, or by transition name)."""
    if a.kind != "jira_transition":
        return None
    raw = str(a.args.get("transition_id") or a.args.get("transition") or a.args.get("transition_name") or "").strip()
    if raw in TID:
        return TID[raw]
    n = norm(raw)
    for word, t in (("reject", "rejected"), ("approv", "approved"), ("request info", "awaiting submitter"),
                    ("submitter", "awaiting submitter"), ("resubmit", "pending approval"),
                    ("pending", "pending approval"), ("pinned", "pinned"), ("controller", "awaiting controller review")):
        if word in n:
            return t
    return n or None


def status_after(result: str, a: Action) -> str | None:
    m = re.search(r'"status"\s*:\s*\{[^{}]*?"name"\s*:\s*"([^"]+)"', result or "")
    return m.group(1).lower() if m else target(a)


def reject_label(a: Action) -> bool:
    return a.kind == "jira_update" and any("reject" in str(x).lower() for x in a.labels)


def approve_label(a: Action) -> bool:
    return a.kind == "jira_update" and any("approv" in str(x).lower() for x in a.labels)


def done(ctx: Context, kind: str, issue: str | None = None):
    w = world(ctx)
    return [e for e in ctx.state.executed if e.action.kind == kind and w.ok(e)
            and (issue is None or key(e.action) == issue)]


def people_sent(w: World) -> bool:
    return any("people@vanguardshield.com" in {*a.recipients, *a.cc} and a.kind == "email_send" for a in w.comms())


def is_b8(a: Action) -> bool:
    return a.kind == "jira_create" and bool(re.search(r"Manager Lookup", f"{a.subject}\n{a.text}", re.I))


def b8_problems(a: Action) -> list[str]:
    out = []
    if not re.fullmatch(B8_TITLE_RX, dashes(a.subject), re.I):
        out.append(f'Title must follow §6.2: "{B8_TITLE}" (got "{a.subject}").')
    body = dashes(a.text)
    miss = [d for rx, d in B8_FIELDS if not re.search(rx, body, re.I)]
    if miss:
        out.append("Paste Template B-8 into the description; missing " + "; ".join(miss) + ".")
    return out


# ---- pre rules -------------------------------------------------------------------------------------------

def _no_approve_rejected(ctx: Context, a: Action):
    k = key(a)
    if k in REJECTED and (target(a) in ("approved", "pinned", "awaiting controller review") or approve_label(a)):
        return (f"{k} must not be approved or parked: {WHY[k]}, so Step 4 requires rejection. Comment "
                f"\"{REJECT_NOTE}\" on {k} and set it to rejected (Reject transition, or label te-rejected if Jira "
                "offers no Reject transition).")
    if a.kind == "jira_comment" and re.search(APPROVE_RX, a.text, re.I) and k != APPROVED:
        return (f"The Step 5 approval comment applies only to reports where no line failed Step 4; on {k} it is "
                "wrong. Only OPS-5 (Frost) passes every test.")
    return None


def _no_reject_approved(ctx: Context, a: Action):
    k = key(a)
    rejecting = (target(a) in ("rejected", "awaiting submitter") or reject_label(a)
                 or (a.kind == "jira_comment" and re.search(REJECT_NOTE_RX, a.text, re.I)))
    if k == APPROVED and rejecting:
        return ("OPS-5 (Frost, EMP-5021) passes every Step 4 test: Oct 5/6/7 meals match calendar events "
                "(Pinnacle lunch, Meridian dinner, East Region team lunch) and the Oct 4 Client Gift Set — Premium "
                "Edition $175.00 is Shopify order #VSM-5001. Do not reject it; approve it per Step 5.")
    if k in OTHER_SEEDED and rejecting:
        return f"{k} is not a Pending Approval T&E report in this batch; do not reject it."
    return None


def _scope(ctx: Context, a: Action):
    k = key(a)
    if a.kind == "jira_transition" and k in OTHER_SEEDED:
        return (f"{k} is not one of the Pending Approval T&E reports (OPS-3, OPS-4, OPS-5); leave its status "
                "unchanged.")
    if a.kind == "jira_delete" and (k in OTHER_SEEDED or k in BATCH):
        return f"Do not delete {k}; the SOP never deletes Jira issues."
    return None


def _b8_ticket(ctx: Context, a: Action):
    if not is_b8(a):
        return None
    w = world(ctx)
    if not people_sent(w):
        return ("§1.3 fallback order: first email people@vanguardshield.com with the employee's full name "
                "(Derek Huang) to request the reporting manager; only if the People directory returns no result "
                "create the HR-Ops Template B-8 ticket.")
    if prior_denials(ctx, "[jira:b8]") >= 2:
        return None
    probs = b8_problems(a)
    return ("[jira:b8] Manager-lookup ticket: " + " ".join(probs) + f" Expected description: {B8_TEXT}") if probs else None


def _jira_placeholders(ctx: Context, a: Action):
    if a.kind not in ("jira_create", "jira_comment", "jira_update"):
        return None
    left = templates.unfilled_placeholders(f"{a.subject}\n{a.text}")
    return f"[placeholders] The Jira text still contains template placeholders {left}." if left else None


# ---- completion rules ------------------------------------------------------------------------------------

def _rejections(ctx: Context):
    for k in REJECTED:
        notes = [e for e in done(ctx, "jira_comment", k) if re.search(REJECT_NOTE_RX, e.action.text, re.I)]
        yield (bool(notes), f"{k}: no rejection comment. {WHY[k]}. Comment on {k} with the rejection reason and "
                            f"the standard note text \"{REJECT_NOTE}\".", [STEP4, STEP2, STEP3])
        state = any(status_after(e.result, e.action) in ("rejected",) for e in done(ctx, "jira_transition", k)) or \
            any(reject_label(e.action) for e in done(ctx, "jira_update", k))
        yield (state, f"{k}: the workflow is not set to rejected. Use the OPS-6 \"Reject\" transition if Jira offers it; "
                      "this Jira has no Reject transition, so record it with the label scheme (§1.3: labels may differ "
                      f"by scheme): update {k} labels to [\"te-rejected\", \"{LABELS[k]}\"] (replacing te-pending). "
                      "Do not use To Approved / To Pinned / To Awaiting Controller Review.", [STEP4, WF])


def _approval(ctx: Context):
    note = [e for e in done(ctx, "jira_comment", APPROVED) if re.search(APPROVE_RX, e.action.text, re.I)]
    yield (bool(note), f"OPS-5 (Frost) passed every test but has no Step 5 comment. Add the Jira comment "
                       f"\"{APPROVE_NOTE}\" on OPS-5.", [STEP5])
    ok = any(status_after(e.result, e.action) == "approved" for e in done(ctx, "jira_transition", APPROVED))
    yield (ok, "OPS-5 (Frost) is not approved. Transition it from Pending Approval to Approved (OPS-6 \"Approve\"; "
               "in this Jira the transition \"To Approved\", id 5).", [STEP5, WF])


def _b8_done(ctx: Context):
    w = world(ctx)
    good = [e for e in done(ctx, "jira_create") if is_b8(e.action) and not b8_problems(e.action)]
    yield (bool(good), "OPS-4 Reporting Manager is blank and the People directory (people@vanguardshield.com) returned "
                       "no result: create a Jira ticket in the HR-Ops queue (project OPS) titled "
                       f"\"{B8_TITLE}\" with Template B-8 as the description: {B8_TEXT}"
                       + ("" if people_sent(w) else " (Email people@vanguardshield.com first.)"), [NOTIFY, RM, B8])


# ---- messages --------------------------------------------------------------------------------------------

def _first_compliant(spec: Comm, base, w: World) -> None:
    """Match the first compliant message (and identical repeats) once one was sent; until then every candidate."""
    def about(a: Action) -> bool:
        if not base(a):
            return False
        good = [x for x in w.comms() if base(x) and not spec.problems(x, w)]
        return not good or a in good
    spec.about = about


def _specs(ctx: Context) -> list[Comm]:
    w = world(ctx)
    t = lambda a: f"{a.subject}\n{a.text}"

    def b2_base(a: Action) -> bool:
        if a.kind not in COMM_KINDS or re.search(r"EMP-4507|Huang|EMP-5021|Frost", t(a)):
            return False
        about_ops3 = re.search(r"EMP-3312|Okonkwo|OPS-3\b", t(a))
        return bool(about_ops3 and (w.is_dm_to(a, "Peter Kim") or re.search(FLAG_RX, t(a))))

    b2 = Comm("b2_pkim", "slack_dm", b2_base, "Template B-2 T&E Review Flag DM to Peter Kim (pkim) for OPS-3",
              [NOTIFY, B2, B2_DETAILS, B2_ACTION], to=["Peter Kim"],
              body=[(r"\[T&E Review Flag\]\s*[-–]?\s*Employee ID:\s*EMP-3312",
                     '"[T&E Review Flag] - Employee ID: EMP-3312"'),
                    (r"Expense Date:[^\n|]*?(Oct(ober)?\.?\s*0?1\b|10/0?1\b|2026-10-01)",
                     '"Expense Date: Oct 1, 2026" (the rejected water-bottle line)'),
                    (r"Amount:\s*\$?\s?144(\.00)?\b", '"Amount: $144.00"'),
                    (r"Merchant:\s*\S", '"Merchant: VSM Branded Water Bottles — Qty 12"'),
                    (r"Details:\s*Expense submitted without a matching Calendar event,?\s*or Shopify promo purchase not "
                     r"found", '"Details: Expense submitted without a matching Calendar event, or Shopify promo '
                               'purchase not found."'),
                    (r"Action Taken:\s*Line item rejected in Jira OPS-HR-TE workflow\.?\s*Please review with your "
                     r"direct report", '"Action Taken: Line item rejected in Jira OPS-HR-TE workflow. Please review '
                                       'with your direct report."')],
              exact_hint=B2_TEXT)
    _first_compliant(b2, b2_base, w)

    def people_base(a: Action) -> bool:
        return a.kind in ("email_send", "email_draft") and "people@vanguardshield.com" in {*a.recipients, *a.cc}

    people = Comm("people_lookup", "email", people_base,
                  "Reporting-manager request for Derek Huang to people@vanguardshield.com (OPS-4 field blank)", [RM, NOTIFY],
                  to=["people@vanguardshield.com"], exact_to=False,
                  body=[(r"Derek Huang|Huang,\s*Derek", 'the employee\'s full name "Derek Huang"')])
    _first_compliant(people, people_base, w)

    huang = Comm("no_b2_huang", "slack_dm",
                 lambda a: a.kind in COMM_KINDS and bool(re.search(FLAG_RX, t(a)) and re.search(r"EMP-4507|Huang", t(a))),
                 "Template B-2 for Derek Huang (OPS-4)", [NOTIFY, RM],
                 forbidden="OPS-4 has a blank Reporting Manager and no manager has been confirmed (people@ / B-8 "
                           "lookup pending). §6.2: do not send Template B-2 until the manager is confirmed - do not "
                           "guess a manager.")
    frost = Comm("no_b2_frost", "slack_dm",
                 lambda a: a.kind in COMM_KINDS and bool(re.search(FLAG_RX, t(a)) and re.search(r"EMP-5021|Frost", t(a))),
                 "Template B-2 for Vanessa Frost (OPS-5)", [NOTIFY, STEP5],
                 forbidden="OPS-5 passed every Step 4 test and is approved; Template B-2 is only for rejected reports.")
    return [b2, people, huang, frost]


RULES = (
    pre_rule("te.no_approve_rejected", _no_approve_rejected, [STEP4, STEP2, STEP3, WF],
             "Reject OPS-3 / OPS-4 instead.")
    + pre_rule("te.no_reject_approved", _no_reject_approved, [STEP5, STEP2, STEP3], "Approve OPS-5 instead.")
    + pre_rule("te.scope", _scope, [STEP1], "Leave that issue unchanged.")
    + pre_rule("te.b8_ticket_pre", _b8_ticket, [RM, NOTIFY, B8, B8_USE], "Fix the ticket as listed.")
    + pre_rule("te.jira_placeholders", _jira_placeholders, [B2, B8], "Replace every bracketed field with its value.")
    + no_placeholders([B2, B8], literal=("[T&E Review Flag]", "[T&E Manager Lookup]"))
    + comm_rules("te.comms", _specs)
    + state_rule("te.rejections", _rejections, "Complete the Step 4 rejection as listed.")
    + state_rule("te.approval", _approval, "Complete the Step 5 approval as listed.")
    + state_rule("te.b8_ticket", _b8_done, "Create the HR-Ops manager-lookup ticket as listed.")
)
