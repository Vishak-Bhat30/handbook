"""Verifiers for medical_pathfinder_billing_and_coding_a70deabc (PBC SOP-RCM-024, blind build).

Task: as Resolution Auditor James Whitfield, work every "Open" item of PBC_RA_Queue.xlsx (today 2026-02-16).
The open items are three BCBS CO-45 denials. Per the CO-45 Recovery Plan (6.2), the RA authority (2.2) and the
SBWO rules (5.1), each claim's path is derived from the seed data:
  - variance (contracted rate - paid) < $5.00                     -> SBWO write-off (Written Off)
  - variance <= $250 and TFL at Orange (<= 30 days, Calendar)     -> RA-approved write-off + #special-authorization
  - otherwise                                                     -> Contractual Rate Dispute, escalate to RCM Manager
"""

from __future__ import annotations

import datetime as dt
import json
import re

from ..kit import (COMM_KINDS, Action, Comm, Context, World, blank, comm_rules, dashes, forbid_writes, nh,
                   no_placeholders, norm, num, pre_rule, same, state_rule, world)

TODAY = dt.date(2026, 2, 16)  # system prompt: "Today's date is, February, 16, 2026, 3:15 PM"
REG, WL, QUEUE, FEES = r"PBC_Claim_Register", r"PBC_Denial_Worklist", r"PBC_RA_Queue", r"PBC_Fee_Schedule"
SBWO_LIMIT, RA_LIMIT, ORANGE_DAYS = 5.00, 250.00, 30

# ---- SOP references (section, paragraph prefix, label) ----
R_RA_AUTH = ("2.2", "Authorization Level: The Resolution Auditor is authorized", "2.2 Resolution Auditor authorization")
R_SPECIAL = ("2.2", "Any time a Resolution auditor", "2.2 #special-authorization post")
R_RA_DUTY = ("2.2", "Core Duties: The Resolution Auditor will investigate", "2.2 Resolution Auditor duties")
R_SEVERITY = ("4.1", "Tasks are prioritized by impact", "4.1 Severity Levels")
R_SEV_L2 = ("4.1", "Level 2: High", "4.1 Level 2: High")
R_SEV_L4 = ("4.1", "Level 4: Low", "4.1 Level 4: Low")
R_ORANGE = ("4.2", "Orange Alert (30 Days to TFL)", "4.2 Orange Alert")
R_SBWO = ("5.1", "Payer Underpayment", "5.1 SBWO Payer Underpayment")
R_SBWO_STATUS = ("5.1", "Whenever any employee applies a SBWO", "5.1 SBWO claim status")
R_TRIAGE = ("6.1", "When a denial is identified", "6.1 Denial Triage")
R_RECOVERY = ("6.2", "All denials require a specific Recovery Plan", "6.2 Recovery Plans")
R_CO45_AUDIT = ("1", "1. Contract Audit", "CO-45 step 1 Contract Audit")
R_CO45_REVIEW = ("1", "2. Case Review", "CO-45 step 2 Case Review")
R_CO45_STATUS = ("1", "3. Update Denial Worklist Status", "CO-45 step 3 Worklist Status")
R_ESC = ("9.1", "Information only moves upward", "9.1 Escalation Chain")
R_ESC_OPS = ("9.1", "Operational |", "9.1 Operational escalation")
R_ESC_ROUTE = ("9.1", "For internal routing", "9.1 escalation routing")
R_REDUND = ("9.4", "To prevent tasks from disappearing", "9.4 Escalation Redundancy Rule")
R_COMMS = ("10", "All external communication must be", "10 Communication Scripts")
R_PHI = ("11.2", "Communication Protocol", "11.2 Communication Protocol")
R_ISOLATION = ("1.3", "Data Isolation", "1.3 Data Isolation")
R_PROPRIETARY = ("1.3", "Proprietary Logic", "1.3 Proprietary Logic")
R_FILES = ("13.4", "The following files surface", "Appendix A File Ecosystem")
R_FEES = ("13.4", "PBC_Fee_Schedule.xlsx |", "Appendix A Fee Schedule")
R_ERA = ("13.4", "ERA_[BatchID].xlsx |", "Appendix A ERA files")
R_VALUES = ("13.4", "Every status or action field uses controlled values", "Appendix B Standard Field Values")
R_CLAIM_STATUS = ("13.4", "New · Submitted", "Appendix B Claim Status")
R_ACTIONS = ("1", "Correct and Resubmit ·", "Appendix B Denial Recovery Action")
R_RSTATUS = ("1", "Pending Review ·", "Appendix B Denial Recovery Status")

CLAIM_STATUSES = ["New", "Submitted", "Acknowledged", "Denied", "In Recovery", "Resubmitted", "Appealed",
                  "Paid - Full", "Paid - Partial", "On Hold", "Closed", "Written Off", "Written Off - RA Approved",
                  "Written Off - RCM Approved"]
RECOVERY_ACTIONS = ["Correct and Resubmit", "Update COB and Resubmit", "Add Modifier and Resubmit",
                    "Appeal - Documentation Supports Service", "Appeal - Payer Processing Error",
                    "Appeal - Timely Filing Exception", "Appeal - Contractual Rate Dispute",
                    "Appeal - Medical Necessity", "Appeal - Prior Auth on File", "Escalate to Resolution Auditor",
                    "Escalate to RCM Manager", "Write Off"]
RECOVERY_STATUSES = ["Pending Review", "In Progress", "Resubmitted", "Appealed", "Escalated", "Resolved", "Written Off"]
SEVERITIES = ["Level 1: Critical", "Level 2: High", "Level 3: Medium", "Level 4: Low"]
QUEUE_STATUSES = ["Open", "In Progress", "Complete"]


def _date(v) -> dt.date | None:
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(v or ""))
    return dt.date(*map(int, m.groups())) if m else None


def _money(v: float) -> str:
    return f"${v:,.2f}"


# ---- the plan, derived from the seed data -------------------------------------------------------------

def plan(ctx: Context) -> dict[str, dict]:
    """Claim ID -> expected outcome for every initially Open RA queue item that is a CO-45 denial."""
    return ctx.memo("a70deabc.plan", lambda: _plan(world(ctx)))


def _tfl(w: World, claim: str, reg_row: dict) -> dt.date | None:
    for ev in w.seed_events:
        if re.fullmatch(rf"{claim}\s+TFL Deadline", nh(ev.get("summary"))):
            st = ev.get("start") or {}
            d = _date(st.get("date") or st.get("dateTime"))
            if d:
                return d
    return _date(w.col(reg_row, r"^Timely_Filing"))


def _plan(w: World) -> dict[str, dict]:
    out: dict[str, dict] = {}
    fees = w.rows(FEES, r"^Contracted_Rate$", "initial")
    for q in w.rows(QUEUE, r"^Queue_ID$", "initial"):
        if norm(w.col(q, r"^Status$")) != "open":
            continue
        claim = w.col(q, r"^Claim_ID$")
        reg = w.find(REG, r"^Claim_ID$", r"^Claim_ID$", claim, "initial")
        dnl = w.find(WL, r"^Denial_ID$", r"^Claim_ID$", claim, "initial")
        if not reg or not dnl or norm(w.col(dnl, r"^CO_Code$")) != "co-45":
            continue
        cpt, payer = w.col(reg, r"^CPT_Code$"), w.col(reg, r"^Payer_Name$")
        fee = next((f for f in fees if norm(w.col(f, r"^CPT_Code$")) == norm(cpt)
                    and norm(w.col(f, r"^Payer_Name$")) == norm(payer)), None)
        paid, billed = num(w.col(reg, r"^Paid_Amount$")), num(w.col(reg, r"^Billed_Amount$"))
        tfl = _tfl(w, claim, reg)
        if fee is None or paid is None or billed is None or tfl is None:
            continue
        rate = num(w.col(fee, r"^Contracted_Rate$"))
        variance = round(rate - paid, 2)
        days = (tfl - TODAY).days
        if variance <= 0:
            continue  # payment matches/exceeds the contract: not present in this seed, left unenforced
        p = dict(claim=claim, queue_id=w.col(q, r"^Queue_ID$"), denial_id=w.col(dnl, r"^Denial_ID$"), cpt=cpt,
                 payer=payer, rate=rate, paid=paid, billed=billed, variance=variance, tfl=tfl, days=days)
        basis = (f"{claim}: {payer} CPT {cpt} contracted rate {_money(rate)} (PBC_Fee_Schedule.xlsx) vs paid "
                 f"{_money(paid)} = {_money(variance)} underpayment; TFL {tfl} (Calendar) is {days} days from {TODAY}")
        if variance < SBWO_LIMIT:
            p.update(path="sbwo", claim_status=["Written Off"], action="Write Off", rstatus="Written Off",
                     qstatus="Complete",
                     why=f"{basis}. The remaining insurance balance is under $5.00, so the SBWO Payer Underpayment "
                         "write-off applies (Contractual Adjustment; Claim Status Written Off instead of Closed).")
        elif variance <= RA_LIMIT and days <= ORANGE_DAYS:
            p.update(path="ra_writeoff", claim_status=["Written Off - RA Approved", "Written Off"],
                     action="Write Off", rstatus="Written Off", qstatus="Complete",
                     why=f"{basis} (Orange Alert, <= 30 days). The Resolution Auditor approves write-offs up to "
                         "$250.00 by default when TFL is at Orange or higher - write it off and log the special "
                         "action in #special-authorization; do not dispute/escalate it.")
        else:
            p.update(path="dispute", claim_status=["In Recovery"], action="Appeal - Contractual Rate Dispute",
                     rstatus="Escalated", qstatus="In Progress",
                     why=f"{basis}. The payment does not match the contract, the balance is not an SBWO and the TFL "
                         "is not at Orange, so the Resolution Auditor attempts recovery via Contractual Rate "
                         "Dispute: Claim Status In Recovery, escalate to the RCM Manager. The queue item stays "
                         "In Progress until the RCM Manager confirms the escalation by email (9.4).")
        if billed > 1000 or days <= 30:
            p["severity"] = "Level 2: High"
            p["sev_why"] = ("denial on a claim totalling > $1,000" if billed > 1000 else
                            f"claim within 30 days of TFL ({days} days)")
        elif p["path"] == "sbwo":
            p["severity"] = "Level 4: Low"
            p["sev_why"] = "routine small-balance denial (< $50)"
        else:
            p["severity"] = None
        out[claim] = p
    return out


def actor_tag(ctx: Context) -> str:
    """'[First] [Last initial].' of the acting user (mailbox owner)."""
    mailbox = world(ctx)._seed("google_mail", "inbox.json").get("mailbox") or {}
    parts = nh(mailbox.get("name") if isinstance(mailbox, dict) else "").split()
    return f"{parts[0]} {parts[-1][0]}." if len(parts) >= 2 else "James W."


def esc_text(claim: str, category: str = "Operational") -> str:
    return f"RCM Manager - Claim ID: {claim}; Reason: Payer Dispute; Escalation Category: {category}"


def esc_rx(claim: str) -> str:
    return rf"RCM Manager [-–—] Claim ID: {re.escape(claim)}; Reason: Payer Dispute; Escalation Category: (?:Operational|Financial)"


# ---- completion: workbook end state for the open items -------------------------------------------------

def _queue_checks(ctx: Context):
    w = world(ctx)
    for claim, p in plan(ctx).items():
        row = w.find(QUEUE, r"^Queue_ID$", r"^Queue_ID$", p["queue_id"])
        tag = f"PBC_RA_Queue.xlsx {p['queue_id']} ({claim})"
        if row is None:
            yield False, f"{tag}: the queue row is missing; restore it.", [R_TRIAGE]
            continue
        got = w.col(row, r"^Status$")
        yield (same(got, p["qstatus"]),
               f"{tag}: Status must be '{p['qstatus']}' (got '{got}'). {p['why']}",
               [R_TRIAGE, R_REDUND] if p["path"] == "dispute" else [R_TRIAGE])
        if p["severity"]:
            sev = w.col(row, r"^Priority_Level$")
            if norm(got) != "open":
                yield (sev == p["severity"],
                       f"{tag}: Priority_Level must be set to the exact severity '{p['severity']}' "
                       f"({p['sev_why']}) when the item leaves 'Open' (got '{sev}').",
                       [R_SEVERITY, R_SEV_L2 if p["severity"].startswith("Level 2") else R_SEV_L4])


def _register_checks(ctx: Context):
    w = world(ctx)
    for claim, p in plan(ctx).items():
        rows = [r for r in w.rows(REG, r"^Claim_ID$") if norm(w.col(r, r"^Claim_ID$")) == norm(claim)]
        tag = f"PBC_Claim_Register.xlsx {claim}"
        if len(rows) != 1:
            yield False, f"{tag}: expected exactly one row for the claim (found {len(rows)}).", [R_RECOVERY]
            continue
        r = rows[0]
        got = w.col(r, r"^Claim_Status$")
        refs = {"sbwo": [R_CO45_REVIEW, R_SBWO, R_SBWO_STATUS], "ra_writeoff": [R_RA_AUTH, R_CO45_REVIEW],
                "dispute": [R_CO45_REVIEW, R_RA_AUTH]}[p["path"]]
        yield (got in p["claim_status"],
               f"{tag}: Claim_Status must be '{p['claim_status'][0]}' (got '{got}'). {p['why']}", refs)
        if p["path"] == "sbwo":
            adj, billed = w.col(r, r"^Adjustment_Amount$"), w.col(r, r"^Billed_Amount$")
            yield (same(adj, 0),
                   f"{tag}: the SBWO Contractual Adjustment sets Adjustment_Amount to 0 (got '{adj}').",
                   [R_CO45_REVIEW])
            yield (same(billed, p["paid"]) or same(billed, p["rate"]),
                   f"{tag}: the Contractual Adjustment updates Billed_Amount to the paid amount {p['paid']:.2f} "
                   f"(got '{billed}').", [R_CO45_REVIEW])


def _worklist_checks(ctx: Context):
    w = world(ctx)
    for claim, p in plan(ctx).items():
        row = w.find(WL, r"^Denial_ID$", r"^Denial_ID$", p["denial_id"])
        tag = f"PBC_Denial_Worklist.xlsx {p['denial_id']} ({claim})"
        if row is None:
            yield False, f"{tag}: the denial row is missing; restore it.", [R_RECOVERY]
            continue
        act, st = w.col(row, r"^Recovery_Action$"), w.col(row, r"^Recovery_Status$")
        yield (act == p["action"], f"{tag}: Recovery_Action must be '{p['action']}' (got '{act}'). {p['why']}",
               [R_CO45_REVIEW, R_RECOVERY])
        yield (st == p["rstatus"], f"{tag}: Recovery_Status must be '{p['rstatus']}' (got '{st}').",
               [R_CO45_STATUS])


def _key(w: World, r: dict, key_rx: str) -> str:
    return norm(w.col(r, key_rx))


def _scope_checks(ctx: Context):
    """Only the Open items are worked: other rows stay unchanged and no register/worklist rows are added."""
    w = world(ctx)
    targets = {norm(c) for c in plan(ctx)}
    for name, header, key, fname in ((REG, r"^Claim_ID$", r"^Claim_ID$", "PBC_Claim_Register.xlsx"),
                                     (WL, r"^Denial_ID$", r"^Claim_ID$", "PBC_Denial_Worklist.xlsx"),
                                     (QUEUE, r"^Queue_ID$", r"^Claim_ID$", "PBC_RA_Queue.xlsx")):
        gone = [r for r in w.missing_rows(name, header) if _key(w, r, key) not in targets]
        if gone:
            ids = ", ".join(w.col(r, header.strip("^$")) for r in gone[:5])
            yield (False, f"{fname}: rows outside the Open queue items were changed or removed ({ids}). Restore "
                          "them exactly; only the Open items are in scope.", [R_RA_DUTY, R_FILES])
        if name != QUEUE:
            n0, n1 = len(w.rows(name, header, "initial")), len(w.rows(name, header))
            if n1 > n0:
                yield (False, f"{fname}: {n1 - n0} new row(s) were added. No CO-45 Recovery Plan step here adds "
                              "rows (a new register row is only for a corrected resubmission). Remove them.",
                       [R_RECOVERY])


def _values_checks(ctx: Context):
    """Status/action fields in rows changed or added use the Appendix B / 4.1 controlled values."""
    w = world(ctx)
    specs = ((REG, r"^Claim_ID$", "PBC_Claim_Register.xlsx", [(r"^Claim_Status$", CLAIM_STATUSES, R_CLAIM_STATUS)]),
             (WL, r"^Denial_ID$", "PBC_Denial_Worklist.xlsx",
              [(r"^Recovery_Action$", RECOVERY_ACTIONS, R_ACTIONS), (r"^Recovery_Status$", RECOVERY_STATUSES, R_RSTATUS)]),
             (QUEUE, r"^Queue_ID$", "PBC_RA_Queue.xlsx",
              [(r"^Priority_Level$", SEVERITIES, R_SEVERITY), (r"^Status$", QUEUE_STATUSES, R_TRIAGE)]))
    for name, header, fname, cols in specs:
        for r in w.new_rows(name, header):
            for col_rx, allowed, ref in cols:
                v = w.col(r, col_rx)
                if not blank(v) and v not in allowed:
                    yield (False, f"{fname} row {r['__row__']}: '{v}' is not a controlled value for "
                                  f"{col_rx.strip('^$')}; use one of: {' · '.join(allowed)}.", [R_VALUES, ref])


# ---- messages ---------------------------------------------------------------------------------------------

def _mentions(a: Action, claim: str) -> bool:
    return claim.lower() in f"{a.subject}\n{a.text}".lower()


def _specs(ctx: Context) -> list[Comm]:
    return ctx.memo("a70deabc.specs", lambda: _build_specs(ctx))


def _build_specs(ctx: Context) -> list[Comm]:
    w = world(ctx)
    out: list[Comm] = []
    who = actor_tag(ctx)

    def in_channel(name: str, extra_rx: str):
        return lambda a: (a.kind == "slack_post" and not w.dm_recipients(a)
                          and (w.is_channel(a.channel, name) or re.search(extra_rx, a.text, re.I)))

    for claim, p in plan(ctx).items():
        esc_about = in_channel("escalations", r"Escalation Category")
        special_about = in_channel("special-authorization", r"special action authori")
        special_text = f"{who} - {claim} special action authorized"
        special_rx = rf"{re.escape(who)} [-–—] {re.escape(claim)} special action authorized"
        if p["path"] == "dispute":
            out.append(Comm(
                f"escalation:{claim}", "slack_post", (lambda c, f: lambda a: f(a) and _mentions(a, c))(claim, esc_about),
                f"escalation of {claim} to the RCM Manager (Contractual Rate Dispute) logged in #escalations",
                [R_ESC, R_CO45_REVIEW, R_ESC_OPS], channel="escalations", exact=esc_rx(claim),
                exact_hint=esc_text(claim)))
            out.append(Comm(
                f"no-special:{claim}", "slack_post",
                (lambda c, f: lambda a: f(a) and _mentions(a, c))(claim, special_about),
                f"#special-authorization post for {claim}", [R_SPECIAL, R_CO45_REVIEW],
                forbidden=f"{claim} is escalated to the RCM Manager for a Contractual Rate Dispute; no Resolution "
                          "Auditor authority is exercised on it, so there is no special-action post."))
        else:
            out.append(Comm(
                f"no-escalation:{claim}", "slack_post",
                (lambda c, f: lambda a: f(a) and _mentions(a, c))(claim, esc_about),
                f"#escalations post for {claim}", [R_ESC, R_RA_AUTH, R_SBWO],
                forbidden=f"{claim} is not escalated. {p['why']}"))
            out.append(Comm(
                f"special:{claim}", "slack_post",
                (lambda c, f: lambda a: f(a) and _mentions(a, c))(claim, special_about),
                f"#special-authorization log of the Resolution Auditor write-off of {claim}", [R_SPECIAL, R_RA_AUTH],
                channel="special-authorization", exact=special_rx, exact_hint=special_text,
                required=p["path"] == "ra_writeoff"))
    return out


def _cal_title_problem(ctx: Context, a: Action) -> str | None:
    if a.kind not in ("calendar_create", "calendar_update"):
        return None
    title = dashes(a.subject)
    if not re.search(r"Claim ID:|Escalation Category|escalat", title, re.I):
        return None
    for claim, p in plan(ctx).items():
        if claim.lower() not in title.lower():
            continue
        if p["path"] != "dispute":
            return f"{claim} is not escalated, so there is no escalation calendar entry for it. {p['why']}"
        posted = [x.text.strip() for x in world(ctx).posts_in("escalations")
                  if re.fullmatch(esc_rx(claim), dashes(x.text).strip())]
        want = posted[-1] if posted else None
        if want and title.strip() != dashes(want):
            return f"The escalation calendar event title must match the #escalations post exactly: \"{want}\"."
        if not want and not re.fullmatch(esc_rx(claim), title.strip()):
            return f"The escalation calendar event title must match the Slack escalation template exactly: \"{esc_text(claim)}\"."
    return None


def _cal_checks(ctx: Context):
    w = world(ctx)
    events = [dashes(a.subject).strip() for a in w.calls("calendar_create", "calendar_update")]
    for claim, p in plan(ctx).items():
        if p["path"] != "dispute":
            continue
        posted = [x.text.strip() for x in w.posts_in("escalations")
                  if re.fullmatch(esc_rx(claim), dashes(x.text).strip())]
        want = posted[-1] if posted else esc_text(claim)
        ok = (any(e == dashes(want) for e in events) if posted
              else any(re.fullmatch(esc_rx(claim), e) for e in events))
        yield (ok, f"Create a calendar event logging the escalation attempt for {claim} titled exactly \"{want}\" "
                   "at the time of the escalation (identical start and end; if the calendar rejects identical times, "
                   "end it one minute after the start).", [R_REDUND])


def _tfl_event_problem(ctx: Context, a: Action) -> str | None:
    if a.kind not in ("calendar_update", "calendar_delete"):
        return None
    eid = str(a.args.get("event_id") or a.args.get("eventId") or a.args.get("id") or "")
    seed = {str(e.get("id")): nh(e.get("summary")) for e in world(ctx).seed_events}
    if eid in seed and "TFL Deadline" in seed[eid]:
        return (f"'{seed[eid]}' is a TFL deadline; the Calendar is the authoritative TFL source. "
                "Do not change or delete it.")
    return None


def _claim_fields_problem(ctx: Context, a: Action) -> str | None:
    """Emails that reference a claim carry Claim ID, Patient ID, DOS, CPT, Payer and current Claim Status."""
    if a.kind not in ("email_send", "email_draft"):
        return None
    w = world(ctx)
    text = f"{a.subject}\n{a.text}"
    missing = []
    for r in w.rows(REG, r"^Claim_ID$", "initial"):
        claim = w.col(r, r"^Claim_ID$")
        if not claim or claim.lower() not in text.lower():
            continue
        dos = _date(w.col(r, r"^Date_Of_Service$"))
        cur = w.find(REG, r"^Claim_ID$", r"^Claim_ID$", claim) or r
        statuses = {w.col(r, r"^Claim_Status$"), w.col(cur, r"^Claim_Status$")} - {""}
        statuses |= set(plan(ctx).get(claim, {}).get("claim_status", []))  # status being set in the same step
        need = [("Patient ID " + w.col(r, r"^Patient_ID$"), re.escape(w.col(r, r"^Patient_ID$"))),
                ("CPT " + w.col(r, r"^CPT_Code$"), rf"\b{re.escape(w.col(r, r'^CPT_Code$'))}\b"),
                ("Payer " + w.col(r, r"^Payer_Name$"), re.escape(w.col(r, r"^Payer_Name$"))),
                ("Claim Status (" + " / ".join(sorted(statuses)) + ")",
                 "|".join(re.escape(s) for s in sorted(statuses, key=len, reverse=True)) or r"$^")]
        if dos:
            need.append((f"DOS {dos}", _date_rx(dos)))
        lack = [d for d, rx in need if not re.search(rx, text, re.I)]
        if lack:
            missing.append(f"{claim}: {', '.join(lack)}")
    if missing:
        return ("A communication that references a claim must include Claim ID, Patient ID, DOS, CPT code(s), "
                "Payer and the current Claim Status from the register. Missing - " + "; ".join(missing) + ".")
    return None


def _date_rx(d: dt.date) -> str:
    mon = d.strftime("%B")
    return (rf"{d:%Y-%m-%d}|0?{d.month}/0?{d.day}/{d.year}|{mon[:3]}[a-z]*\.? 0?{d.day},? {d.year}"
            rf"|0?{d.day} {mon[:3]}[a-z]* {d.year}")


INTERNAL = re.compile(r"@(pathfinder\.med|company\.com)$", re.I)


def _phi_problem(ctx: Context, a: Action) -> str | None:
    if a.kind not in ("email_send", "email_draft"):
        return None
    ext = [x for x in a.recipients + a.cc if not INTERNAL.search(x)]
    if ext and re.search(r"\bPAT-\d+", f"{a.subject}\n{a.text}"):
        return (f"Patient IDs are PHI and must not go by standard email to external recipients ({', '.join(ext)}); "
                "use the secure portal / encrypted channel.")
    return None


# ---- rules ------------------------------------------------------------------------------------------------

RULES = (
    state_rule("queue.open_items", _queue_checks, "Set the queue row as listed.")
    + state_rule("register.co45_outcome", _register_checks, "Update the claim register row as listed.")
    + state_rule("worklist.co45_outcome", _worklist_checks, "Update the denial worklist row as listed.")
    + state_rule("scope.other_rows", _scope_checks, "Restore the out-of-scope rows exactly.")
    + state_rule("values.controlled", _values_checks, "Use the exact controlled value.")
    + comm_rules("comms", _specs)
    + pre_rule("calendar.escalation_title", _cal_title_problem, [R_REDUND, R_ESC], "Use the exact title given.")
    + state_rule("calendar.escalation_event", _cal_checks, "Create the calendar event as listed.")
    + pre_rule("calendar.tfl_kept", _tfl_event_problem, [R_SEVERITY], "Leave the TFL deadline events unchanged.")
    + forbid_writes("files.reference_readonly", r"PBC_Fee_Schedule\.xlsx|^ERA[-_].*\.xlsx$|PBC_SOP\.html",
                    "the Fee Schedule, inbound ERA files and the SOP are reference data; the Recovery Plan only "
                    "reads them (updates go to the claim register, denial worklist and RA queue).",
                    [R_FEES, R_ERA, R_PROPRIETARY])
    + pre_rule("comms.claim_fields", _claim_fields_problem, [R_COMMS], "Add the missing claim details and resend.")
    + pre_rule("comms.phi_external", _phi_problem, [R_PHI, R_ISOLATION], "Remove the PHI or use a secure channel.")
    + no_placeholders([R_SPECIAL, R_ESC])
)
