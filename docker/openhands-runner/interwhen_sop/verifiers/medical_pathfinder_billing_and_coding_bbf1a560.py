"""Pathfinder Billing & Coding bbf1a560: Bullion Gold Insurance duplicate-payment (overpayment) refund case.

Seed facts: ERA 260403-001-Z3689F paid six AA45175 / B8475Q claims a second time (3 x $350 + 3 x $75 =
$1,275.00). The patient's other unpaid B8475Q claims are BGI-38399991 ($350, Submitted) and BGI-40001965
($75, New), so $425.00 can be re-classed and $850.00 must be refunded -> a refund case: the Resolution Auditor
(Jill) escalates to the RCM Manager (SOP 2.2), logs it (9.5), posts the 10.4 Slack (9.1), notifies #coders and
#billing-specs ("Refund case - AA45175 - B8475Q") and creates the 9.4 calendar event.
"""

from __future__ import annotations

import datetime as dt
import json
import re

from ..kit import (COMM_KINDS, Comm, append_only, comm_rules, dashes, forbid_writes, nh, no_placeholders, norm,
                   pre_rule, state_rule, text_of, world)

TODAY = "2026-04-09"
PATIENT, PAYER_ID, PAYER = "AA45175", "B8475Q", "Bullion Gold Insurance"
PAYER_EMAIL, JOE, MAY = "popler.wen@bulliongoldinsurance.com", "joem@pathfinder.com", "mayj@pathfinder.com"
DUPES = {"BGI-39882091": 350.0, "BGI-39667288": 350.0, "BGI-31199221": 350.0,
         "BGI-33991911": 75.0, "BGI-36110292": 75.0, "BGI-37918822": 75.0}
RECLASS = {"BGI-38399991": 350.0, "BGI-40001965": 75.0}
OVERPAID, REFUND = sum(DUPES.values()), sum(DUPES.values()) - sum(RECLASS.values())  # 1275.00, 850.00
TKG = f"Escalated to RCM Manager - {TODAY}"
CAL_TITLE = "Escalation Attempt - Jill - RCM Manager"
REFUND_NOTE = f"Refund case - {PATIENT} - {PAYER_ID}"
ESC_SLACK_HINT = f"Escalation: {TODAY}. Category: Operational. Payer: {PAYER}. (Category Financial is also accepted)"
ESC_LOG = r"PBC_Escalation_Log"
ESC_HDR = r"^Resolution_Tkg$"

R_REFUND = ("2.2", "• Escalation Trigger: The Resolution Auditor will escalate to the RCM Manager any denials",
            "2.2 Resolution Auditor escalation trigger (refund cases)")
R_CREDIT = ("1.3", "Credit Balance:", "1.3 Credit Balance")
R_CHAIN = ("9.1", "Level Trigger Escalation Path", "9.1 Escalation Chain")
R_ALL_LOGGED = ("9.1", "Information only moves upward", "9.1 all escalations logged")
R_REDUND = ("9.4", "To prevent tasks from disappearing", "9.4 Escalation Redundancy Rule")
R_REDUND2 = ("9.4", "- [Role the issue", "9.4 calendar title")
R_LOG = ("9.5", "When an escalation is made", "9.5 Logging Escalations")
R_T104 = ("10.4", "Slack: \"Escalation:", "10.4 Non-High-Value Escalation template")
R_PHI = ("11.2", "• Communication Protocol:", "11.2 Communication Protocol (PHI)")
R_ISO = ("1.3", "Data Isolation:", "1.3 Data Isolation")
R_CATS = ("1", "Denial Recovery Action", "Appendix B Escalation Category values")
R_DENIAL = ("6.1", "When a denial is identified", "6.1 Denial Triage")
R_FILES = ("13.4", "Appendix A: File Ecosystem", "Appendix A File Ecosystem")


def _amount(v: float) -> str:
    whole, cents = f"{v:.2f}".split(".")
    w = f"{int(whole):,}".replace(",", ",?")
    return rf"(?<![\d,.])\$?\s?{w}" + (rf"\.{cents}" if cents != "00" else r"(?:\.00)?") + r"(?![\d,])"


def _id_with_amount(cid: str, v: float) -> str:
    """Claim id followed (before the next claim id) by its amount, or the amount shortly before the id
    (no other number in between). Comm bodies arrive whitespace-collapsed."""
    c, amt = re.escape(cid), _amount(v)
    return (rf"{c}(?:(?!BGI-\d)[^\n]){{0,150}}?{amt}|{c}[^\n]*\n(?:(?!BGI-\d)[^\n]){{0,80}}?{amt}"
            rf"|{amt}[^\d\n]{{0,60}}?{c}")


def _fmt(v: float) -> str:
    return f"${v:,.2f}"


class BccComm(Comm):
    """Comm whose ``cc`` addresses must be in the BCC field (the task asks for May in BCC)."""

    def problems(self, a, w):
        out = super().problems(a, w)
        if not self.forbidden and a.kind in ("email_send", "email_draft"):
            bcc = {x.lower() for x in re.findall(r"[\w.+-]+@[\w.-]+\w", json.dumps(a.args.get("bcc") or ""))}
            missing = [x for x in self.cc if x.lower() not in bcc]
            if missing:
                out.append(f"Put {', '.join(missing)} in BCC (not To/CC).")
        return out


def _is_email_to(a, addr: str) -> bool:
    return a.kind in ("email_send", "email_draft") and addr in {x.lower() for x in a.recipients + a.cc}


def specs(ctx) -> list[Comm]:
    w = world(ctx)
    dupes_body = [(_id_with_amount(c, v), f"claim {c} with its overpaid amount {_fmt(v)}") for c, v in DUPES.items()]
    payer = BccComm(
        "payer_overpayment", "draft",
        lambda a: _is_email_to(a, PAYER_EMAIL) or (a.kind in ("email_send", "email_draft")
                                                    and any("bulliongold" in x for x in a.recipients + a.cc)),
        f"Draft overpayment notice to the payer ({PAYER}, {PAYER_EMAIL})", [R_CREDIT, R_REFUND],
        to=[PAYER_EMAIL], cc=[MAY],
        body=dupes_body + [
            (r"re-?\s?class", "that any excess will be re-classed to yet unpaid claims for the same patient"),
            (r"refund", "that the rest will be processed for refund back to the payer"),
            (r"approv", "that the refund is subject to approval"),
            (r"updat", "that updates will be provided as the situation evolves")])
    joe = BccComm(
        "joe_refund", "draft", lambda a: _is_email_to(a, JOE),
        "Draft refund-case escalation email to Joe (RCM Manager, joem@pathfinder.com)", [R_REFUND],
        to=[JOE], cc=[MAY],
        body=[(re.escape(PAYER), f"the payer name {PAYER} as the party requiring a refund")]
        + [(re.escape(c), f"problematic claim ID {c}") for c in DUPES]
        + [(_amount(OVERPAID), f"the exact overpaid amount {_fmt(OVERPAID)}")]
        + [(_id_with_amount(c, v), f"re-class {_fmt(v)} to unpaid claim {c}") for c, v in RECLASS.items()]
        + [(_amount(REFUND), f"the expected refund amount {_fmt(REFUND)} ({_fmt(OVERPAID)} - {_fmt(OVERPAID - REFUND)})")])
    rx_note = r"Refund case\s*[-–—]\s*AA45175\s*[-–—]\s*B8475Q"
    note = [(rx_note, f"the notification text exactly: {REFUND_NOTE}")]
    refund_post = lambda ch: (lambda a: a.kind == "slack_post" and not w.dm_recipients(a)
                              and w.is_channel(a.channel, ch) and re.search(r"refund\s+case", a.text, re.I))
    coders = Comm("refund_note_coders", "slack_post", refund_post("coders"),
                  "Refund-case notification to the CMCs in #coders", [R_REFUND], channel="coders", body=note)
    billing = Comm("refund_note_billing", "slack_post", refund_post("billing-specs"),
                   "Refund-case notification to the Billing Specialists in #billing-specs", [R_REFUND],
                   channel="billing-specs", body=note)
    esc = Comm("esc_slack_rcm", "slack_post",
               lambda a: a.kind == "slack_post" and not w.dm_recipients(a)
               and w.is_channel(a.channel, "escalations-rcm-mgr") and re.search(r"^\W*Escalation\s*:", a.text, re.I),
               "Section 10.4 escalation Slack to the RCM Manager channel #escalations-rcm-mgr",
               [R_CHAIN, R_T104], channel="escalations-rcm-mgr",
               body=[(rf"Escalation: {TODAY}\. Category: (Operational|Financial)\. Payer: {PAYER}\.",
                      f"the 10.4 template filled exactly: {ESC_SLACK_HINT}")])
    return [payer, joe, coders, billing, esc]


# ---- outgoing messages: no PHI (names / DOB), no email sent ----------------------------------------------

def _patients(ctx) -> list[tuple[str, list[str]]]:
    def load():
        w = world(ctx)
        out = []
        for r in w.rows(r"PBC_Eligibility_Responses", r"^Patient_Name$", "initial"):
            name, dob = w.col(r, r"^Patient_Name$"), w.col(r, r"^DOB$")
            d = dob[:10]
            forms = []
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
                y, m, dd = d.split("-")
                forms = [d, f"{m}/{dd}/{y}", f"{int(m)}/{int(dd)}/{y}"]
            if name:
                out.append((name, forms))
        return out
    return ctx.memo("bbf1a560.patients", load)


def phi_problem(ctx, a):
    if a.kind not in COMM_KINDS:
        return None
    text = text_of(a)
    hits = [n for n, _ in _patients(ctx) if re.search(rf"\b{re.escape(n)}\b", text, re.I)]
    hits += [f"DOB {f}" for _, forms in _patients(ctx) for f in forms if re.search(rf"(?<![\d/]){re.escape(f)}(?![\d/])", text)]
    if hits:
        return (f"[phi] This {a.kind.replace('_', ' ')} contains patient PHI ({', '.join(hits)}). PHI must never be sent "
                "via standard email or Slack - identify the case by claim IDs / Patient ID only.")
    return None


def send_problem(ctx, a):
    if a.kind != "email_send":
        return None
    return ("[no-send] The user asked that no email be sent yet - save both emails (payer notice, refund email to Joe) "
            "as drafts with google_mail__save_draft and leave them for Jill to review.")


# ---- 9.4 calendar event ------------------------------------------------------------------------------------

def _ct(v, wall: bool = False) -> dt.datetime | None:
    """Naive Central-time datetime; ``wall`` keeps the written clock time (seed events use a fixed -06:00)."""
    if not isinstance(v, dict):
        return None
    s = v.get("dateTime") or ""
    try:
        t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is not None and not (wall and t.utcoffset() != dt.timedelta(0)):
        from zoneinfo import ZoneInfo
        t = t.astimezone(ZoneInfo("America/Chicago"))
    return t.replace(tzinfo=None)


def _events(ctx) -> list[dict]:
    """Events the agent created/updated (and did not delete): {summary, start, end}."""
    w = world(ctx)
    evs: dict[str, dict] = {}
    for e in w.state.executed:
        a = e.action
        if a.kind not in ("calendar_create", "calendar_update", "calendar_delete") or not w.ok(e):
            continue
        try:
            res = json.loads(re.sub(r"^\s*\[Tool '[^']*' executed\.\]\s*", "", e.result or ""))
        except ValueError:
            res = {}
        ev = res.get("event") if isinstance(res, dict) and isinstance(res.get("event"), dict) else {}
        eid = str(ev.get("id") or a.args.get("eventId") or a.args.get("event_id") or f"new{e.index}")
        if a.kind == "calendar_delete":
            evs.pop(eid, None)
            continue
        cur = evs.get(eid, {})
        merged = {**cur, **{k: v for k, v in a.args.items() if v not in (None, "")}, **ev}
        evs[eid] = merged
    return list(evs.values())


def _cal_ok(ev: dict) -> str | None:
    if dashes(nh(ev.get("summary"))) != dashes(CAL_TITLE):
        return f"title must be exactly \"{CAL_TITLE}\" (got \"{ev.get('summary')}\")"
    s, e = _ct(ev.get("start")), _ct(ev.get("end"))
    if not s or not e:
        return "give it a start and end time (not an all-day event)"
    starts = {s, _ct(ev.get("start"), wall=True)}
    if not any(t.date().isoformat() == TODAY and dt.time(13, 0) <= t.time() <= dt.time(15, 0) for t in starts):
        return f"it must start when the escalation was made today ({TODAY}, ~1:30 PM CT)"
    if e - s != dt.timedelta(hours=2):
        return "it must end 2 business hours after the start (e.g. 1:30 PM - 3:30 PM CT)"
    return None


def cal_pre(ctx, a):
    if a.kind not in ("calendar_create", "calendar_update"):
        return None
    title = nh(a.args.get("summary"))
    if not re.search(r"escalation\s+attempt", title, re.I):
        return None
    if dashes(title) != dashes(CAL_TITLE):
        return (f"[calendar] The 9.4 escalation-attempt event title must be exactly \"{CAL_TITLE}\" "
                f"(got \"{title}\").")
    s, e = _ct(a.args.get("start")), _ct(a.args.get("end"))
    if s and e and e - s != dt.timedelta(hours=2):
        return "[calendar] The 9.4 event must end 2 business hours after it starts (e.g. 1:30 PM - 3:30 PM CT today)."
    return None


def cal_checks(ctx):
    evs = [ev for ev in _events(ctx) if re.search(r"escalation\s+attempt", nh(ev.get("summary")), re.I)]
    probs = [_cal_ok(ev) for ev in evs]
    ok = any(p is None for p in probs)
    detail = "; ".join(p for p in probs if p) if probs else "no such event was created"
    yield (ok, f"Create the 9.4 calendar event \"{CAL_TITLE}\" from the escalation time to 2 business hours later "
               f"({TODAY} 1:30 PM - 3:30 PM CT) - {detail}.", [R_REDUND, R_REDUND2])


# ---- 9.5 escalation log ----------------------------------------------------------------------------------

def log_checks(ctx):
    w = world(ctx)
    init = w.rows(ESC_LOG, ESC_HDR, "initial")
    cur = w.rows(ESC_LOG, ESC_HDR, "current")
    if not init:
        return
    cid = lambda r: w.col(r, r"^Claim_ID")
    pay = lambda r: w.col(r, r"^Payer_ID")
    cat = lambda r: w.col(r, r"^Category$")
    rsn = lambda r: w.col(r, r"^Esc_Reason$")
    tkg = lambda r: w.col(r, r"^Resolution_Tkg$")
    for c in DUPES:
        rows = [r for r in cur if cid(r) == c]
        orig = next(r for r in init if cid(r) == c)
        if len(rows) != 1:
            yield (False, f"Escalation log: claim {c} must keep exactly one row (found {len(rows)}); the row already "
                          f"exists, so only update its Resolution_Tkg.", [R_LOG])
            continue
        r = rows[0]
        bad = []
        if norm(dashes(tkg(r))) != norm(dashes(TKG)):
            bad.append(f"Resolution_Tkg must be \"{TKG}\" (got \"{tkg(r)}\")")
        if pay(r) != pay(orig) or rsn(r) != rsn(orig):
            bad.append(f"Payer_ID / Esc_Reason must stay \"{pay(orig)}\" / \"{rsn(orig)}\"")
        if norm(cat(r)) not in ("operational", "financial"):
            bad.append(f"Category must be a controlled value for this sub-$5,000 refund escalation "
                       f"(Operational or Financial; got \"{cat(r)}\")")
        yield (not bad, f"Escalation log row {c}: " + "; ".join(bad) + ".", [R_LOG, R_CATS])
    others = [r for r in init if cid(r) not in DUPES]
    keep = lambda r: tuple(v for k, v in r.items() if k != "__row__")
    cur_keys = [keep(r) for r in cur]
    gone = [r for r in others if keep(r) not in cur_keys]
    yield (not gone, f"Escalation log: {len(gone)} unrelated existing row(s) were changed or removed "
                     f"(e.g. {keep(gone[0]) if gone else ''}); restore them.", [R_LOG])
    extra = [r for r in cur if cid(r) not in DUPES and cid(r) not in RECLASS and keep(r) not in [keep(o) for o in others]]
    yield (not extra, f"Escalation log: unrequested new row(s) {[keep(r) for r in extra][:3]} - the refund-case rows "
                      f"already exist; only their Resolution_Tkg changes.", [R_LOG, R_ALL_LOGGED])


# ---- no unrequested writes -------------------------------------------------------------------------------

def unrequested_checks(ctx):
    w = world(ctx)
    for name, hdr, what in ((r"PBC_QA_Queue", r"^Claim_ID$", "QA queue (no QA review is triggered here)"),
                            (r"PBC_Denial_Worklist", r"^Claim_ID$", "Denial Worklist (no denial in this case)")):
        new = w.new_rows(name, hdr)
        yield (not new, f"{what}: unrequested new row(s) added ({len(new)}); remove them.", [R_FILES, R_DENIAL])


RULES = (
    comm_rules("bbf1a560.comms", specs)
    + pre_rule("bbf1a560.phi", phi_problem, [R_PHI, R_ISO], "Remove the patient name / DOB from the message.")
    + pre_rule("bbf1a560.no_send", send_problem, [], "Save it as a draft instead.")
    + pre_rule("bbf1a560.calendar_title", cal_pre, [R_REDUND, R_REDUND2], f"Use the title \"{CAL_TITLE}\".")
    + state_rule("bbf1a560.calendar", cal_checks, "Create the calendar event as described.")
    + state_rule("bbf1a560.esc_log", log_checks, "Edit PBC_Escalation_Log.xlsx as described.")
    + append_only("bbf1a560.denial_append_only", r"PBC_Denial_Worklist", r"^Claim_ID$", "PBC_Denial_Worklist.xlsx",
                  [R_FILES])
    + state_rule("bbf1a560.unrequested_rows", unrequested_checks, "Remove the rows.")
    + forbid_writes("bbf1a560.reference_files",
                    r"^(ERA_[\w.-]+\.xlsx|PBC_Fee_Schedule\.xlsx|PBC_NCCI_Edits\.xlsx|PBC_Eligibility_Responses\.xlsx"
                    r"|((RARC|CARC) )?Codes\.(xlsx|pdf)|SOP\.pdf)$",
                    "inbound ERA batches and reference tables (fee schedule, NCCI, eligibility, CARC/RARC, SOP) are "
                    "read-only sources; nothing in this case changes them.", [R_FILES])
    + no_placeholders([R_T104])
)
