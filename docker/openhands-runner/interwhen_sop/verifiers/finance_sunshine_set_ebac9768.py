"""Verifiers for finance_sunshine_set_ebac9768 (Sunshine & Set: Johnson deal SL-2026-0412, BD 3 of April close).

Seed facts: today Mon 2026-04-14 (BD 3); Marcus Hale (Assistant Controller) is out of office Apr 14-16, so per
SOP 1.2 items awaiting his sign-off default to the Controller, Elena Brooks (elena.brooks@sunshineauto.com).
"""

from __future__ import annotations

import re

from ..kit import (Comm, World, comm_rules, dashes, money_rx, no_placeholders, norm, num, state_rule, text_of,
                   world)

DEAL = "SL-2026-0412"
ELENA = "elena.brooks@sunshineauto.com"

R_CASH = ("3.1", "During month-end close periods (Business Day 1 through Business Day 7)", "3.1 month-end cash")
R_CASH_STD = ("3.1", "The daily bank deposit must match the total", "3.1 deposit differences")
R_ABSENT = ("1.2", "Conversely, when the Assistant Controller is absent", "1.2 Assistant Controller absence")
R_FUND = ("2.2", "Unfunded deals require daily status updates", "2.2 unfunded escalation")
R_STIPS = ("2.2", "Use #acct-contracts-funding to request missing stips", "2.2 missing stips")
R_PAYOFF = ("2.4", "If the actual payoff amount differs from the estimated payoff", "2.4 payoff variance")
R_PAYOFF_CLOSE = ("2.4", "If the payoff variance is identified during the month-end close window",
                  "2.4 close-window recalculation")
R_GROSS = ("2.1", "If the posted deal gross differs from the approved desk recap", "2.1 gross variance tiers")
R_CB_ESC = ("6", "Use #acct-chargebacks for questions involving product providers", "6 chargeback escalation")
R_CB_TPL = ("6", "When escalating an aging or high-dollar chargeback, send an email using Template F",
            "6 Template F")
R_TPL_F = ("10.5", "Subject: Chargeback Escalation", "Appendix A Template F subject")
R_TPL_F_BODY = ("10.5", "The following chargeback(s) have been open for more than 15 days",
                "Appendix A Template F body")
R_TPL_KEEP = ("10.5", "The following email templates are referenced throughout this SOP",
              "Appendix A template structure")
R_CB_DISPUTE = ("6", "Verify whether the chargeback affects customer refunds", "6 disputed chargebacks")
R_CB_APPROVAL = ("6", "Chargebacks under $250 with no dispute flag", "6 chargeback approvals")
R_CB_POST = ("6", "Post approved chargebacks to the correct general ledger account", "6 posting chargebacks")
R_CB_TRACK = ("6", "Track all chargebacks including warranty cancellations", "6 chargeback tracker")
R_OFFSET = ("7.2", "Chargeback offsets under $250 may be applied automatically", "7.2 offset approvals")
R_FP_SOLD = ("5.6", "The daily floorplan balance in the inventory tracker must match", "5.6 sold-not-paid payoff")
R_FP_OOT = ("5.6", "Any potential out-of-trust exposure, aged curtailment", "5.6 out-of-trust notification")
R_FP_CH = ("1.4", "#acct-floorplan", "1.4 #acct-floorplan")
R_STOP = ("9.3", "Stop the workflow at the point the discrepancy is identified", "9.3 stop the workflow")
R_TRAIL = ("9.4", "Every accounting process must leave an audit trail", "9.4 audit trail")

DEADLINE_RX = (r"April\s+14|Apr\.?\s*14|\b0?4/14\b|2026-04-14|\btoday\b|\bEOD\b|\bEOB\b|\bCOB\b|"
               r"end of (the )?(business )?day|close of business|\b5(:00)?\s*(PM|p\.m\.)")


# ---- helpers ------------------------------------------------------------------------------------

def mrx(v: float) -> str:
    # money_rx alone would find 5,000 inside 25,000
    return r"(?<![\d,.])" + money_rx(v)


def _has_elena_email(a) -> bool:
    return any(re.match(r"elena\.brooks@", x) for x in [*a.recipients, *a.cc])


def to_controller(w: World, a) -> bool:
    """A sent message that reaches Elena Brooks: email to/cc her, Slack DM, #leadership-escalations or a tag."""
    if a.kind == "email_send":
        return _has_elena_email(a)
    if a.kind in ("slack_dm", "slack_post"):
        if w.is_dm_to(a, "Elena Brooks"):
            return True
        if a.kind == "slack_post" and not w.dm_recipients(a):
            if w.is_channel(a.channel, "leadership-escalations"):
                return True
            return bool(re.search(r"<@U001>|@elena(\.brooks)?\b", a.text or "", re.I))
    return False


def _controller_texts(ctx) -> list[str]:
    w = world(ctx)
    return [dashes(text_of(a)) for a in w.comms() if to_controller(w, a)]


def _books(w: World, stem: str) -> list[str]:
    return [b for b in w.books(rf"(^|/){stem}[^/]*\.xlsx$")]


def _rows_in(w: World, book: str, header_rx: str) -> list[dict]:
    return w.rows(rf"^{re.escape(book)}$", header_rx)


# ---- messages (Template F to the Controller; stip request in #acct-contracts-funding) --------------

def _is_template_f(a) -> bool:
    return a.kind == "email_send" and _has_elena_email(a) and bool(re.search(r"chargeback", a.subject, re.I))


def _is_stip_request(ctx):
    def about(a) -> bool:
        w = world(ctx)
        return (a.kind == "slack_post" and not w.dm_recipients(a) and w.is_channel(a.channel, "acct-contracts-funding")
                and bool(re.search(r"SL-2026-0412|Johnson", a.text or "", re.I))
                and bool(re.search(r"stip|power of attorney|\bPOA\b|payoff letter", a.text or "", re.I)))
    return about


def specs(ctx) -> list[Comm]:
    return [
        Comm("template_f", "email", _is_template_f,
             "Template F chargeback escalation to Controller Elena Brooks for CB-2026-0089 ($2,800 SafeGuard VSC "
             "chargeback on Deal SL-2026-0412 / Johnson - high-dollar, >= $2,500)",
             [R_CB_TPL, R_TPL_F, R_TPL_F_BODY, R_CB_ESC, R_TPL_KEEP], exact_to=False,
             subject=r"(Chargeback Escalation\b.*\$\s?2,?800(\.00)?\b.*|.*High[- ]Value Chargeback Requiring "
                     r"Immediate Action.*)",
             subject_hint=f"Chargeback Escalation – $2,800.00 – 1 Open Items Over 15 Days\" to {ELENA}",
             body=[(r"SL-2026-0412", "Deal # SL-2026-0412"), (r"Johnson", "Customer Johnson"),
                   (r"Vehicle Service Contract|\bVSC\b", "Product Type Vehicle Service Contract"),
                   (mrx(2800), "Chargeback Amount $2,800.00"),
                   (r"Date Received", "a 'Date Received' field (2026-04-14)"),
                   (r"Days Open", "a 'Days Open' field (0)"),
                   (r"Recommended next step", "'Recommended next step:' line")]),
        Comm("stip_request", "slack_post", _is_stip_request(ctx),
             "Missing-stip request in #acct-contracts-funding for Deal SL-2026-0412 (Johnson): Power of Attorney "
             "and Payoff Letter for Wells Fargo, due end of business today April 14, 2026",
             [R_STIPS], channel="acct-contracts-funding", max_count=3,
             body=[(r"Wells Fargo", "bank name Wells Fargo"), (r"SL-2026-0412", "deal number SL-2026-0412"),
                   (DEADLINE_RX, "the funding deadline (end of business today, April 14, 2026)")]),
    ]


# ---- reports to the Controller -------------------------------------------------------------------

def controller_checks(ctx):
    texts = _controller_texts(ctx)
    cash = any(re.search(r"(?<![\d,.])\$?\s?180(\.00)?(?![\d,])", t) and re.search(r"cash|deposit", t, re.I)
               for t in texts)
    yield (cash, "The unresolved $180 cash deposit shortage has not been reported to the Controller. During month-end "
                 "close (today is BD 3) any unresolved deposit discrepancy over $150 must be reported to Elena Brooks "
                 f"the same business day. Report it to Elena Brooks ({ELENA} or Slack DM): Johnson, Deal SL-2026-0412, "
                 "batch 20260414-001, check expected $3,500.00, deposited $3,320.00, short $180.00, unresolved; "
                 "daily cash report held open.", [R_CASH, R_CASH_STD])
    fund = any(re.search(r"fund|Wells Fargo", t, re.I) and re.search(r"power of attorney|\bPOA\b", t, re.I)
               for t in texts)
    yield (fund, "The unfunded Wells Fargo contract has not been escalated to the Controller. Deal SL-2026-0412 "
                 "(contract $30,500 > $25,000, submitted 2026-04-08, 6 days unfunded) escalates to the Assistant "
                 "Controller at 3 days, but Marcus Hale is out of office Apr 14-16, so it defaults to the Controller. "
                 f"Escalate in writing to Elena Brooks ({ELENA} or Slack DM) with the outstanding stips (Power of "
                 "Attorney, Payoff Letter - due to Wells Fargo by end of business today) and next steps.",
           [R_FUND, R_ABSENT])
    pay = any(re.search(r"payoff", t, re.I) and re.search(mrx(5000), t) and re.search(mrx(4710), t)
              and re.search(r"threshold|tier|classif|\$\s?51\b|\b51\s*(-|–|to)|range|band|bracket", t, re.I)
              for t in texts)
    yield (pay, "The $290 Chase trade payoff variance (quoted $11,250.00, applied $11,540.00) exceeds $200 and needs "
                "Assistant Controller review before processing; Marcus Hale is out of office, so escalate to Elena "
                f"Brooks ({ELENA} or Slack DM). Because it is the month-end close window, the escalation must include "
                "the original total gross $5,000.00, the recalculated total gross $4,710.00 (front gross $3,200.00 - "
                "$290.00 = $2,910.00) and the SOP 2.1 threshold classification (tier) of the $290 adjustment.",
          [R_PAYOFF, R_PAYOFF_CLOSE, R_GROSS, R_ABSENT])


# ---- floorplan sold-not-paid Slack notification --------------------------------------------------

def floorplan_checks(ctx):
    w = world(ctx)
    ok = any(re.search(r"8XJ472|N240412|SL-2026-0412|Johnson", a.text or "", re.I)
             and re.search(r"sold[- ]not[- ]paid|out[- ]of[- ]trust|\bSNP\b", a.text or "", re.I)
             for a in w.posts_in("acct-floorplan") + w.posts_in("leadership-escalations"))
    yield (ok, "The sold-not-paid floorplan unit has not been flagged in Slack. Unit 8XJ472 / Stock N240412 (2026 "
               "Honda Accord, Johnson, Deal SL-2026-0412) was delivered 2026-04-08 and is still unpaid on the floorplan "
               "past the 3-business-day payoff deadline (2026-04-13), accruing interest ($145) - potential "
               "out-of-trust exposure. Post it in #acct-floorplan (tag @darius.kim) with deal number, customer, "
               "VIN/stock and the issue.", [R_FP_OOT, R_FP_SOLD, R_FP_CH])


# ---- end-state prohibitions -------------------------------------------------------------------------

CLOSED_RX = r"^\s*(ok|closed?|resolved|reconciled|cleared|balanced|completed?|posted)\b"


def cash_checks(ctx):
    w = world(ctx)
    for b in _books(w, "daily_cash_log"):
        for r in _rows_in(w, b, r"Batch ID"):
            if norm(w.col(r, r"^Batch ID")) != "20260414-001":
                continue
            status, actual, var = w.col(r, r"^Status"), w.col(r, r"^Actual"), w.col(r, r"^Variance")
            bad = []
            if re.search(CLOSED_RX, status, re.I):
                bad.append(f"Status is \"{status}\"")
            if num(actual) is not None and abs(num(actual) - 3320) > 0.005:
                bad.append(f"Actual Amount was changed to {actual}")
            if num(var) is not None and abs(num(var) + 180) > 0.005:
                bad.append(f"Variance was changed to {var}")
            yield (not bad, f"{b}: the $180 Johnson deposit discrepancy (batch 20260414-001) is unresolved, so the "
                            f"daily cash report must not be closed ({'; '.join(bad)}). Keep Actual Amount 3320, "
                            "Variance -180 and a non-closed status such as \"Discrepancy - Escalated\".",
                   [R_CASH_STD, R_STOP])


def chargeback_checks(ctx):
    w = world(ctx)
    for b in _books(w, "chargeback_tracker"):
        rows = [r for r in _rows_in(w, b, r"Chargeback ID") if norm(w.col(r, r"^Chargeback ID")) == "cb-2026-0089"]
        yield (len(rows) <= 1, f"{b}: CB-2026-0089 appears {len(rows)} times; track it on one row (update the "
                               "existing row instead of adding a duplicate).", [R_CB_TRACK])
        for r in rows:
            off, status = w.col(r, r"Commission Offset"), w.col(r, r"^Status")
            bad = []
            if re.match(r"\s*yes\b", off, re.I):
                bad.append(f"Commission Offset Applied = \"{off}\"")
            if re.search(CLOSED_RX + r"|^\s*(approved|offset applied|processed)\b", status, re.I):
                bad.append(f"Status = \"{status}\"")
            yield (not bad, f"{b}: CB-2026-0089 ($2,800) has no approval yet - it needs Controller review (Marcus Hale "
                            "is out) and it conflicts with the deal posting (VSC premium $1,895), so no offsetting "
                            f"entry or commission offset may be posted ({'; '.join(bad)}). Set Commission Offset "
                            "Applied back to \"No\" and use a pending status such as \"Escalated - Pending Review\".",
                   [R_CB_APPROVAL, R_CB_DISPUTE, R_CB_POST, R_OFFSET])


def gross_checks(ctx):
    w = world(ctx)
    for b in _books(w, "deal_log"):
        r = next((r for r in _rows_in(w, b, r"Deal #") if norm(w.col(r, r"^Deal #")) == norm(DEAL)), None)
        if not r:
            continue
        bad = []
        for col, want in ((r"^Front Gross", 3200), (r"^Back Gross", 1800), (r"^Total Gross", 5000)):
            got = w.col(r, col)
            if got and (num(got) is None or abs(num(got) - want) > 0.005):
                bad.append(f"{col.strip('^')} = {got} (posted {want})")
        yield (not bad, f"{b}: the deal gross of SL-2026-0412 was adjusted before the $290 payoff variance was "
                        f"approved ({'; '.join(bad)}). Variances over $200 are escalated before processing; restore "
                        "Front Gross 3200, Back Gross 1800, Total Gross 5000 and put the recalculation ($4,710) in "
                        "the escalation instead.", [R_PAYOFF, R_GROSS, R_STOP])


def summary_checks(ctx):
    w = world(ctx)
    path, text = w.file_text(r"(^|/)actions_summary\.txt$")
    yield ((bool(path) and len(text.strip()) >= 50) or (not path and w.wrote(r"^actions_summary\.txt$")),
           "The requested actions summary is missing: save actions_summary.txt in the workspace (/workdir) listing "
           "every action taken and the decision rationale for each escalation path.", [R_TRAIL])


RULES = [
    *comm_rules("ebac.comms", specs),
    *state_rule("ebac.controller_reports", controller_checks, "Send the report to Elena Brooks as described."),
    *state_rule("ebac.floorplan_slack", floorplan_checks, "Post the notification in #acct-floorplan."),
    *state_rule("ebac.cash_report_open", cash_checks, "Restore the cash log row as described."),
    *state_rule("ebac.chargeback_not_posted", chargeback_checks, "Restore the chargeback tracker row."),
    *state_rule("ebac.deal_gross_unchanged", gross_checks, "Restore the deal log figures."),
    *state_rule("ebac.actions_summary", summary_checks, "Write /workdir/actions_summary.txt."),
    *no_placeholders([R_TPL_KEEP], literal_rx=[r"\[[Xx]\]"]),
]
