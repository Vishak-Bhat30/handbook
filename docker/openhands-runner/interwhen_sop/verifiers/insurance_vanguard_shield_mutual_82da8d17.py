"""Vanguard Shield Mutual - SOP §7.2 Processing Multi-Beneficiary Life Claims (task 82da8d17).

Seed facts (Jira CLM_LIFE-1..4 + attached PDFs in the initial workspace), today 2026-04-10, analyst Taylor Morgan (TM):
- CLM_LIFE-1 Martinez LC-2019-08844 $400,000: identity matches (SSN 4456, DOB); the dissolution judgment is dated
  2026-04-10, after the 2026-03-15 date of death, so it is not a decree "finalized prior to the insured's date of
  death" -> allocate Maria L. 60% $240,000.00 / David R. 40% $160,000.00, route to AP.
- CLM_LIFE-2 Whitfield LC-2021-15290 $250,000: clean -> Thomas P. 50% / Emily J. 50% ($125,000.00 each), route to AP.
- CLM_LIFE-3 Drummond LC-2018-06231 $600,000: primary Linda M. Drummond confirmed deceased (death certificate
  additional_document_drummond_01.pdf) -> redistribute pro rata: Mark H. 35/55 = 63.64% $381,818.18,
  Susan E. 20/55 = 36.36% $218,181.82; route to AP.
- CLM_LIFE-4 Okafor LC-2020-11467 $350,000: attorney letter (attorney_letter_okafor_01.pdf, 2026-04-04) -> CLM-920
  Complex Beneficiary Hold, note file name and date, route to CLM-Legal (Legal Claims Lead nbriggs per CLM_LEGAL-1);
  stop - no allocation, no AP routing.
"""

from __future__ import annotations

import json
import re

from ..kit import Action, Context, prior_denials, pre_rule, state_rule, world, money_rx

TODAY = "2026-04-10"
INITIALS = "TM"

R_VERIFY = ("7.2", "Verify documentation: From Jira CLM-LIFE-[number]", "§7.2 Verify documentation")
R_MISMATCH = ("7.2", "mismatch: do not allocate; set status CLM-910", "§7.2 identity mismatch")
R_SCHEDULE = ("7.2", "Review beneficiary schedule:", "§7.2 Review beneficiary schedule")
R_CONFLICT = ("7.2", "Flag conflicts:", "§7.2 Flag conflicts")
R_CALC = ("7.2", "Calculate allocation:", "§7.2 Calculate allocation")
R_HEADER = ("7.2", "--- Beneficiary Allocation ---", "§7.2 allocation format")
R_POLICY = ("7.2", "Policy: [PolicyNumber] | Face Amount:", "§7.2 allocation format")
R_BEN1 = ("7.2", "B eneficiary 1: [Full Name]", "§7.2 allocation format")
R_BEN2 = ("7.2", "$[Calculated] Beneficiary 2:", "§7.2 allocation format")
R_BEN3 = ("7.2", "Amount: $[Calculated]", "§7.2 allocation format")
R_REPEAT = ("7.2", "(Repeat for each beneficiary.", "§7.2 survival / redistribution")
R_PRORATA = ("7.2", "among surviving primaries", "§7.2 survival / redistribution")
R_ANALYST = ("7.2", "Analyst: [Initials] | Date:", "§7.2 allocation format")
R_ROUTE = ("7.2", "Route to AP for payout only when", "§7.2 Route to AP")
R_QUEUE = ("1.3", "Queue Assignee (role-based routing):", "§1.3 Queue Assignee")
R_C910 = ("7.3", "CLM-910 Identity Verification Hold", "Appendix C CLM-910")
R_C920 = ("7.3", "CLM-920 Complex Beneficiary Hold", "Appendix C CLM-920")

FORMAT_REFS = [R_CALC, R_HEADER, R_POLICY, R_BEN1, R_BEN2, R_BEN3, R_REPEAT, R_PRORATA, R_ANALYST]

# (display name, name regex, split %, amount)
CLAIMS = {
    "CLM-LIFE-1": {
        "insured": "Robert James Martinez", "policy": "LC-2019-08844", "face": 400000.00,
        "pay": [("Maria L. Martinez", r"Maria\s+L\.?\s+Martinez", 60.0, 240000.00),
                ("David R. Martinez", r"David\s+R\.?\s+Martinez", 40.0, 160000.00)],
        "exclude": [(r"\bElena\b", "Elena Martinez is a contingent beneficiary; list contingents only if no primary "
                                   "beneficiary survives (both primaries survive)")],
        "why_clear": "identity matches (death certificate CT-2026-018834: SSN last 4 4456, DOB June 14, 1968) and the "
                     "dissolution judgment in legal_filing_martinez_01.pdf is dated April 10, 2026 - after the "
                     "March 15, 2026 date of death, so it is not a divorce decree finalized prior to the date of death",
    },
    "CLM-LIFE-2": {
        "insured": "Catherine A. Whitfield", "policy": "LC-2021-15290", "face": 250000.00,
        "pay": [("Thomas P. Whitfield", r"Thomas\s+P\.?\s+Whitfield", 50.0, 125000.00),
                ("Emily J. Whitfield", r"Emily\s+J\.?\s+Whitfield", 50.0, 125000.00)],
        "exclude": [(r"\bJames\b", "James R. Whitfield is a contingent beneficiary; list contingents only if no "
                                   "primary beneficiary survives (both primaries survive)")],
        "why_clear": "identity matches (death certificate MA-2026-024517: SSN last 4 7823) and no divorce decree, "
                     "competing claim, court order or attorney letter is attached",
    },
    "CLM-LIFE-3": {
        "insured": "Harold W. Drummond", "policy": "LC-2018-06231", "face": 600000.00,
        "pay": [("Mark H. Drummond", r"Mark\s+H\.?\s+Drummond", 35 / 55 * 100, 381818.18),
                ("Susan E. Drummond", r"Susan\s+E\.?\s+Drummond", 20 / 55 * 100, 218181.82)],
        "exclude": [(r"\bLinda\b", "Linda M. Drummond is confirmed deceased (death certificate NY-2026-028114 in "
                                   "additional_document_drummond_01.pdf) - exclude her and redistribute her share pro "
                                   "rata among the surviving primaries"),
                    (r"\bGeorge\b", "George T. Drummond is a contingent beneficiary; list contingents only if no "
                                    "primary beneficiary survives (Mark and Susan survive)")],
        "why_clear": "identity matches (death certificate NY-2026-031982: SSN last 4 3198); the only extra document is "
                     "the death certificate of primary beneficiary Linda M. Drummond, which is handled by pro-rata "
                     "redistribution, not a hold",
    },
}
HOLD_KEY = "CLM-LIFE-4"
HOLD_FILE = "attorney_letter_okafor_01"

ALLOC_RX = re.compile(r"[-–—]{2,}\s*Beneficiary\s+Allocation|^\s*B\s?eneficiary\s*\d+\s*:", re.I | re.M)
BEN_LINE = re.compile(r"^\s*B\s?eneficiary\s*\d+\s*:", re.I)
TEMPLATE_FIELDS = re.compile(r"\[(PolicyNumber|Amount|Full Name|X|Y|Calculated|Initials|YYYY-MM-DD)\]", re.I)
NEG = re.compile(r"\b(not|no|unable|cannot|can't|isn't|unavailable|pending|until|awaiting|will)\b", re.I)
DATE_RX = re.compile(r"\b(20\d\d-\d\d-\d\d|\d{1,2}/\d{1,2}/20\d\d|(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
                     r"\s+\d{1,2},?\s+20\d\d)\b", re.I)
JIRA_WRITES = ("jira_comment", "jira_update", "jira_transition", "jira_create", "jira_link")


def key(a: Action) -> str:
    return re.sub(r"[\s_]+", "-", str(a.channel or "").strip().upper())


def show(k: str) -> str:
    return k.replace("CLM-LIFE", "CLM_LIFE")


def pct(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def expected_block(k: str) -> str:
    c = CLAIMS[k]
    lines = ["--- Beneficiary Allocation ---", f"Policy: {c['policy']} | Face Amount: ${c['face']:,.2f}"]
    for i, (name, _, split, amt) in enumerate(c["pay"], 1):
        lines.append(f"Beneficiary {i}: {name} | Designation: Primary | Split: {pct(split)}% | Amount: ${amt:,.2f}")
    lines.append(f"Analyst: {INITIALS} | Date: {TODAY}")
    return "\n".join(lines)


def alloc_problems(k: str, text: str) -> list[str]:
    c = CLAIMS[k]
    out = []
    if not re.search(r"^\s*[-–—]{3}\s*Beneficiary Allocation\s*[-–—]{3}\s*$", text, re.M | re.I):
        out.append("The block must start with the line '--- Beneficiary Allocation ---'.")
    if not re.search(rf"^\s*Policy:\s*{re.escape(c['policy'])}\s*\|\s*Face Amount:\s*{money_rx(c['face'])}",
                     text, re.M | re.I):
        out.append(f"Policy line must read 'Policy: {c['policy']} | Face Amount: ${c['face']:,.2f}'.")
    lines = [ln for ln in text.splitlines() if BEN_LINE.match(ln)]
    for rx, why in c["exclude"]:
        if any(re.search(rx, ln, re.I) for ln in lines):
            out.append(f"{why}.")
    for name, rx, split, amt in c["pay"]:
        ln = next((x for x in lines if re.search(rx, x, re.I)), None)
        if ln is None:
            out.append(f"Missing beneficiary line for {name}.")
            continue
        if not re.search(r"Designation:\s*Primary\b", ln, re.I):
            out.append(f"{name}: Designation must be Primary.")
        m = re.search(r"Split:\s*([\d.]+)\s*%", ln, re.I)
        if not m or abs(float(m.group(1).rstrip(".") or 0) - split) > 0.05:
            out.append(f"{name}: Split must be {pct(split)}%.")
        m = re.search(r"Amount:\s*\$\s?([\d,]+(?:\.\d+)?)", ln, re.I)
        if not m or abs(float(m.group(1).replace(",", "")) - amt) > 0.011:
            out.append(f"{name}: Amount must be ${amt:,.2f}.")
    if len(lines) != len(c["pay"]):
        out.append(f"List exactly {len(c['pay'])} beneficiary lines (got {len(lines)}).")
    if not re.search(rf"^\s*Analyst:\s*T\.?\s?M\.?\s*\|\s*Date:\s*{TODAY}\b", text, re.M | re.I):
        out.append(f"End with 'Analyst: {INITIALS} | Date: {TODAY}' (analyst initials of Taylor Morgan).")
    left = sorted(set(TEMPLATE_FIELDS.findall(text)))
    if left:
        out.append(f"Fill the template fields {['[' + x + ']' for x in left]}.")
    return out


def is_alloc(a: Action) -> bool:
    return a.kind in ("jira_comment", "jira_update", "jira_transition") and bool(ALLOC_RX.search(a.text or ""))


def valid_alloc(a: Action, k: str) -> bool:
    return key(a) == k and is_alloc(a) and not alloc_problems(k, a.text)


def labels(a: Action) -> list[str]:
    return [str(x) for x in a.labels or []]


def affirmative(text: str, rx: str) -> bool:
    """Some sentence states ``rx`` without a negation/condition word."""
    return any(re.search(rx, s, re.I) and not NEG.search(s) for s in re.split(r"[.;\n]", text or ""))


def routes_to_ap(a: Action) -> bool:
    if a.kind not in ("jira_update", "jira_transition", "jira_comment"):
        return False
    if any(re.search(r"route.?to.?ap|ap.?payout|\bpayout\b", x, re.I) for x in labels(a)):
        return True
    if a.kind == "jira_transition" and re.search(r"route|\bAP\b|payout", f"{a.code} {json.dumps(a.args)}", re.I):
        return True
    return affirmative(a.text, r"\b(routed|transitioned|sent|moved)\s+to\s+(AP|Accounts Payable)\b[^.;\n]{0,15}payout")


def sets_hold(a: Action, code: str) -> bool:
    if any(code.lower() in x.lower() for x in labels(a)):
        return True
    return a.kind == "jira_transition" and code.lower() in f"{a.code} {json.dumps(a.args)}".lower()


def legal_route(a: Action) -> bool:
    if a.kind == "jira_create" and re.search(r"CLM.?LEGAL", a.channel or "", re.I):
        return True
    if key(a) != HOLD_KEY:
        return False
    if a.kind == "jira_update" and any(re.search(r"nbriggs|nathan", r, re.I) for r in a.recipients):
        return True
    if any(re.search(r"clm.?legal", x, re.I) for x in labels(a)):
        return True
    return a.kind == "jira_transition" and bool(re.search(r"legal", f"{a.code} {json.dumps(a.args)}", re.I))


# ---- pre rules ----------------------------------------------------------------------------------

def _alloc_format(ctx: Context, a: Action):
    k = key(a)
    if k not in CLAIMS or not is_alloc(a):
        return None
    tag = f"[alloc:{show(k)}]"
    probs = alloc_problems(k, a.text)
    if not probs or prior_denials(ctx, tag) >= 2:
        return None
    return (f"{tag} The beneficiary allocation comment for {show(k)} does not match the SOP structured format / "
            f"expected values: " + " ".join(probs) + f" Post exactly:\n{expected_block(k)}")


def _okafor_stop(ctx: Context, a: Action):
    if key(a) == HOLD_KEY:
        t = a.text or ""
        if a.kind in ("jira_comment", "jira_update", "jira_transition") and (
                re.search(r"[-–—]{2,}\s*Beneficiary\s+Allocation|^\s*B\s?eneficiary\s*\d+\s*:.*Amount:", t, re.I | re.M)
                or re.search(money_rx(245000) + "|" + money_rx(105000), t)):
            return (f"[okafor] {show(HOLD_KEY)} has an attorney letter ({HOLD_FILE}.pdf) -> CLM-920 Complex "
                    "Beneficiary Hold: do not calculate payout amounts or post an allocation block; set CLM-920, "
                    "note the file name and date, route to CLM-Legal and stop.")
        if routes_to_ap(a):
            return (f"[okafor] {show(HOLD_KEY)} is under CLM-920 Complex Beneficiary Hold - do not route it to AP for "
                    "payout; route it to CLM-Legal (assign nbriggs) instead.")
    if a.kind in ("email_send", "email_draft"):
        ext = [r for r in a.recipients + a.cc if not r.endswith("@vanguardshield.com")]
        if ext and re.search(r"Okafor|LC-2020-11467", f"{a.subject}\n{a.text}", re.I):
            return (f"[okafor] {show(HOLD_KEY)} is on CLM-920 hold and routed to CLM-Legal; the SOP says stop - do not "
                    f"send external correspondence about this claim ({', '.join(ext)}).")
    return None


def _no_hold_on_clear(ctx: Context, a: Action):
    k = key(a)
    if k not in CLAIMS or a.kind not in ("jira_update", "jira_transition"):
        return None
    hit = [c for c in ("CLM-910", "CLM-920") if sets_hold(a, c)]
    if not hit:
        return None
    return (f"[hold:{show(k)}] Do not set {'/'.join(hit)} on {show(k)}: {CLAIMS[k]['why_clear']}. Post the allocation "
            f"comment and route to AP for payout instead.")


def _route_after_alloc(ctx: Context, a: Action):
    k = key(a)
    if k not in CLAIMS or not routes_to_ap(a) or valid_alloc(a, k):
        return None
    if any(valid_alloc(x, k) for x in world(ctx).calls(*JIRA_WRITES)):
        return None
    return (f"[route:{show(k)}] Route {show(k)} to AP for payout only after the complete structured allocation comment "
            f"is in place. Post it first:\n{expected_block(k)}")


RULES = []
RULES += pre_rule("life.allocation_format", _alloc_format, FORMAT_REFS + [R_SCHEDULE],
                  "Post the allocation comment exactly as given.")
RULES += pre_rule("life.okafor_stop", _okafor_stop, [R_CONFLICT, R_CALC, R_ROUTE, R_C920],
                  "Leave CLM_LIFE-4 on CLM-920 hold with CLM-Legal.")
RULES += pre_rule("life.no_hold_on_clear_claims", _no_hold_on_clear, [R_VERIFY, R_MISMATCH, R_CONFLICT, R_C910],
                  "Do not place this hold.")
RULES += pre_rule("life.route_after_allocation", _route_after_alloc, [R_ROUTE], "Post the allocation comment first.")


# ---- completion rules ---------------------------------------------------------------------------

def _allocations(ctx: Context):
    calls = world(ctx).calls(*JIRA_WRITES)
    for k in CLAIMS:
        ok = any(valid_alloc(a, k) for a in calls)
        yield ok, (f"{show(k)} ({CLAIMS[k]['insured']}): no complete structured allocation comment. Add this Jira "
                   f"comment on {show(k)}:\n{expected_block(k)}"), FORMAT_REFS


def _routed(ctx: Context):
    calls = world(ctx).calls(*JIRA_WRITES)
    for k in CLAIMS:
        ok = any(key(a) == k and routes_to_ap(a) for a in calls)
        yield ok, (f"{show(k)} ({CLAIMS[k]['insured']}) was not routed to AP for payout. The Jira workflow has no "
                   f"'Route to AP for Payout' transition, so record it on {show(k)}: add the label "
                   "Route-to-AP-for-Payout (keep the existing labels) after the allocation comment."), [R_ROUTE]


def _okafor(ctx: Context):
    calls = [a for a in world(ctx).calls(*JIRA_WRITES)]
    mine = [a for a in calls if key(a) == HOLD_KEY]
    hold = any(sets_hold(a, "CLM-920") for a in mine) or any(
        a.kind == "jira_comment" and affirmative(a.text, r"CLM-920") and re.search(r"Complex Beneficiary Hold", a.text,
                                                                                  re.I) for a in mine)
    yield hold, (f"{show(HOLD_KEY)} (Patricia N. Okafor): set CLM-920 Complex Beneficiary Hold (add label CLM-920 and "
                 "say 'CLM-920 Complex Beneficiary Hold applied' in the note) - the attorney letter is a potential "
                 "beneficiary conflict."), [R_CONFLICT, R_C920]
    note = any(a.kind == "jira_comment" and HOLD_FILE in (a.text or "").lower() and DATE_RX.search(a.text or "")
               for a in mine)
    yield note, (f"{show(HOLD_KEY)}: add a note comment with the conflict document's file name and date, e.g. "
                 f"'Potential beneficiary conflict: {HOLD_FILE}.pdf (attorney letter dated 2026-04-04)'."), [R_CONFLICT]
    legal = any(legal_route(a) for a in calls)
    yield legal, (f"{show(HOLD_KEY)}: transition/route to CLM-Legal - assign {show(HOLD_KEY)} to nbriggs (Nathan Briggs, "
                  "Legal Claims Lead per the CLM_LEGAL-1 Queue Roles & Assignees issue) and add the label "
                  "CLM-Legal."), [R_CONFLICT, R_QUEUE]


RULES += state_rule("life.allocation_posted", _allocations, "Post the allocation comment.")
RULES += state_rule("life.routed_to_ap", _routed, "Record the routing to AP.")
RULES += state_rule("life.okafor_hold", _okafor, "Complete the CLM-920 / CLM-Legal steps.")
