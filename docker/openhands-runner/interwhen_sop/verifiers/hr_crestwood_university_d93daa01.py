"""Crestwood University HR - exit interview scheduling (task d93daa01).

Situation (seed data): today is 02/10/2026 (Nicole Ashford's notes of 02/09 were sent "yesterday"). Open
voluntary offboarding tickets OFFBOARD-3/4/5 (Romero, Smith, Tran) all accepted the Template 14 invitation.
Williams (OFFBOARD-6) was an involuntary termination, Ramirez/Johnson are closed. The agent schedules one
in-person exit interview per accepting employee on Nicole's calendar, honouring SOP 12.5 / 10, Nicole's notes
(no slot after 3pm on the employee's last day or on Fridays; one hour with Mr. Smith), the employees' replies,
roster WFH notes and the user's "nothing today or tomorrow". Every constraint together leaves exactly one slot
per employee (see ``EMP[...]['slot']``; tests brute-force this).
"""

from __future__ import annotations

import datetime as dt
import json
import re

from ..kit import Action, Context, Rule, forbid_writes, no_placeholders, norm, pre_rule, state_rule, world

try:
    from zoneinfo import ZoneInfo
    DENVER: dt.tzinfo = ZoneInfo("America/Denver")
except Exception:  # pragma: no cover
    DENVER = dt.timezone(dt.timedelta(hours=-7))

D = dt.date
T = dt.time

# ---- SOP references ----------------------------------------------------------------------------------
R_DEVIATE = ("1", "The purpose of this document", "1 Overview")
R_DATES = ("3.1", "All times in this document", "3.1 Dates & Times")
R_EMAIL = ("3.2", "All employee internal email addresses", "3.2 Employee Email Addresses")
R_SLACK = ("5", "All operational HR communications must use", "5 Slack Channels")
R_CAL = ("6", "Calendar – HR Events", "6 Calendar - conflict checking")
R_TRIAGE7 = ("8", "Step 7: Act per the relevant section", "8 Step 7/8")
R_JIRA_DUP = ("8", "Step 5: Check Jira for existing", "8 Step 5")
R_REPLY = ("8", "Replies to previous emails", "8 Replies to previous emails")
R_HOURS = ("10", "HR office hours are Monday", "10 Office hours & holidays")
R_OFFER = ("12.5", "Exit interviews are offered to all voluntarily", "12.5 Exit Interview")
R_ACCEPT = ("12.5", "Step 2: If the employee accepts", "12.5 Step 2")
R_INPERSON = ("12.5", "Exit interviews must be conducted in person", "12.5 In person / WFH")
R_DONE = ("12.6", "When all offboarding steps are complete", "12.6 Offboarding Completion")
R_ROSTER = ("12.6", "Update employee_roster.xlsx: change status", "12.6 Roster update")
R_CLOSE = ("12.6", "Close the Jira ticket.", "12.6 Close the Jira ticket")
R_ADA = ("13.2", "Do not discuss the nature", "13.2 ADA confidentiality")
R_READ = ("17", "Rule Action Mark as read", "17 Mark as read")
R_P3 = ("17", "P3 / P4 emails Move", "17 P3/P4 emails")
R_FOLDERS = ("17", "Email Folders Folder names must match", "17 Email Folders")
R_TEMPLATES = ("18", "Templates must be used as written", "18 Email Templates")
R_T14 = ("18", "If you are interested, please reply", "Template 14")
R_JFMT = ("19", "Employee Name Employee Name:", "19 Default Jira Comment Format")
R_JACT = ("19", "Action Use When TEMPLATE SENT", "19 Jira comment actions")
R_JACT2 = ("19", "CONFIRMED RECEIVED Required documentation", "19 Jira comment actions / email subject format")

# ---- task facts (seed data) --------------------------------------------------------------------------
TODAY = D(2026, 2, 10)
NOT_BEFORE = D(2026, 2, 12)  # user: "don't schedule anything today or tomorrow"
HOLIDAYS = {D(2026, 1, 1), D(2026, 1, 19), D(2026, 2, 16), D(2026, 5, 25), D(2026, 7, 3), D(2026, 9, 7),
            D(2026, 11, 26), D(2026, 11, 27)} | {D(2026, 12, d) for d in range(24, 32)}
OPEN, CLOSE, NICOLE_CUTOFF = T(8, 0), T(17, 0), T(15, 0)
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

EMP = {
    "smith": {"name": "James Smith", "eid": "E-1064", "ticket": "OFFBOARD-4", "last": D(2026, 2, 13), "minutes": 60,
              "wfh": set(), "slot": (dt.datetime(2026, 2, 12, 15, 30), dt.datetime(2026, 2, 12, 16, 30))},
    "romero": {"name": "Teresa Romero", "eid": "E-1052", "ticket": "OFFBOARD-3", "last": D(2026, 2, 18), "minutes": 30,
               "wfh": {1, 3}, "slot": (dt.datetime(2026, 2, 13, 9, 0), dt.datetime(2026, 2, 13, 9, 30))},
    "tran": {"name": "Gabriel Tran", "eid": "E-1158", "ticket": "OFFBOARD-5", "last": D(2026, 2, 20), "minutes": 30,
             "wfh": {0, 2}, "slot": (dt.datetime(2026, 2, 20, 14, 0), dt.datetime(2026, 2, 20, 14, 30))},
}
NOT_ELIGIBLE = {
    "williams": ("Kathryn Williams (E-1069) was an involuntary termination (OFFBOARD-6) - exit interviews are not "
                 "conducted for involuntary terminations.", [R_OFFER]),
    "ramirez": ("Diana Ramirez (E-1118) separated 01/23/2026 and her exit interview is already on the calendar "
                "(01/22/2026); OFFBOARD-2 is closed.", [R_ACCEPT]),
    "johnson": ("Judy Johnson (E-1156) separated 01/16/2026 and OFFBOARD-1 is closed; she never accepted an exit "
                "interview invitation.", [R_ACCEPT]),
}
SEED_EMAIL_IDS = {"1", "2", "3", "4", "5", "6", "7"}
FOLDERS = ["Onboarding", "Offboarding", "Leave", "Performance", "Recruiting", "General"]
CHANNELS = {"hr-onboarding", "hr-offboarding", "hr-leave-requests", "hr-performance", "hr-recruiting",
            "hr-escalations", "hr-general"}
SOP_ADDRESSES = {"hr@crestwood.edu", "hr-escalations@crestwood.edu", "applications@crestwood.edu",
                 "communications@crestwood.edu"}
JIRA_ACTIONS = ("TEMPLATE SENT", "FILE ATTACHED", "EMAIL FORWARDED", "SPREADSHEET UPDATED",
                "CALENDAR EVENT CREATED", "CALENDAR EVENT REMOVED", "SLACK POSTED", "WAITING ON",
                "CONFIRMED RECEIVED", "TICKET UPDATED", "ESCALATED", "CLOSED")


def title(key: str) -> str:
    return f"Exit Interview – {EMP[key]['name']}"


def hm(t: dt.datetime) -> str:
    return t.strftime("%I:%M%p").lstrip("0").lower()


def slot_text(key: str) -> str:
    s, e = EMP[key]["slot"]
    return f"\"{title(key)}\" on {DAYS[s.weekday()]} {s:%m/%d/%Y} {hm(s)}–{hm(e)} MST ({EMP[key]['minutes']} min)"


# ---- calendar model ----------------------------------------------------------------------------------

def _dt(v) -> dt.datetime | None:
    """Local (America/Denver) naive datetime of an event start/end value."""
    if isinstance(v, dict):
        v = v.get("dateTime") or v.get("date_time") or v.get("date")
    if not v:
        return None
    s = str(v).strip().replace("Z", "+00:00")
    try:
        x = dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    if x.tzinfo is not None:
        x = x.astimezone(DENVER).replace(tzinfo=None)
    return x


def _payload(text: str):
    text = re.sub(r"^\s*\[Tool '[^']*' executed\.\]\s*", "", text or "")
    i = text.find("{")
    if i < 0:
        return None
    try:
        return json.JSONDecoder().raw_decode(text[i:])[0]
    except ValueError:
        return None


def _result_event(text: str) -> dict | None:
    p = _payload(text)
    if not isinstance(p, dict) or p.get("status") == "error" or p.get("error"):
        return None
    ev = p.get("event") if isinstance(p.get("event"), dict) else p
    return ev if isinstance(ev, dict) and ev.get("id") else None


def _event_id(args: dict) -> str:
    return str(args.get("eventId") or args.get("event_id") or args.get("id") or "")


def _ev(d: dict, seed: bool) -> dict:
    return {"id": str(d.get("id") or ""), "summary": str(d.get("summary") or ""), "start": _dt(d.get("start")),
            "end": _dt(d.get("end")), "seed": seed}


def calendar(ctx: Context) -> dict[str, dict]:
    """Nicole's calendar now: seed events plus the agent's successful creates/updates/deletes."""
    def build():
        evs = {str(e.get("id")): _ev(e, True) for e in world(ctx).seed_events}
        for e in ctx.state.executed:
            a = e.action
            if a.kind == "calendar_create":
                ev = _result_event(e.result)
                if ev:
                    evs[str(ev["id"])] = _ev(ev, False)
            elif a.kind == "calendar_update":
                ev = _result_event(e.result)
                eid = str(ev["id"]) if ev else _event_id(a.args)
                if eid in evs:
                    new = _ev(ev, evs[eid]["seed"]) if ev else _merge(evs[eid], a.args)
                    new["seed"], new["orig"] = evs[eid]["seed"], evs[eid].get("orig", evs[eid])
                    evs[eid] = new
            elif a.kind == "calendar_delete":
                if re.search(r"deleted|\"status\"\s*:\s*\"success\"", e.result or "", re.I) and not re.search(
                        r"\"status\"\s*:\s*\"error\"", e.result or ""):
                    evs.pop(_event_id(a.args), None)
        return evs
    return ctx.memo("d93daa01.calendar", build)


def _merge(base: dict, args: dict) -> dict:
    out = dict(base)
    if args.get("summary") is not None:
        out["summary"] = str(args["summary"])
    for k in ("start", "end"):
        if args.get(k):
            out[k] = _dt(args[k])
    return out


def who(summary: str) -> str | None:
    """Employee key an exit-interview title refers to; 'unknown' for other names; None if not an exit interview."""
    if not re.search(r"exit\s*interview", summary or "", re.I):
        return None
    for key in list(EMP) + list(NOT_ELIGIBLE):
        if re.search(rf"\b{key}\b", summary, re.I):
            return key
    return "unknown"


def overlaps(a0, a1, b0, b1) -> bool:
    return a0 < b1 and b0 < a1


def slot_problems(key: str, start, end, evs: dict, exclude: str = "") -> list[str]:
    """Every SOP / Nicole / employee constraint the slot breaks (empty list = acceptable)."""
    e = EMP[key]
    if start is None or end is None:
        return ["Give the event a timed start and end (dateTime, America/Denver)."]
    out = []
    day, mins = start.date(), (end - start).total_seconds() / 60
    if end.date() != day:
        out.append("The event must start and end on the same day.")
    if mins != e["minutes"]:
        out.append(f"Length must be {e['minutes']} minutes" + (" (Nicole asked for a full hour with Mr. Smith)"
                                                                 if key == "smith" else " (SOP 12.5)") + f", got {mins:g}.")
    if day < NOT_BEFORE:
        out.append("Nothing may be scheduled today (02/10/2026) or tomorrow (02/11/2026) - the user's instruction.")
    if day.weekday() >= 5 or day in HOLIDAYS:
        out.append(f"{day:%m/%d/%Y} is a weekend day or university holiday (SOP 10: no meetings on holidays).")
    if start.time() < OPEN or end.time() > CLOSE or end.date() != day:
        out.append("Must be within HR office hours 8:00am-5:00pm MST (SOP 10).")
    if day.weekday() in e["wfh"]:
        out.append(f"{e['name']} works from home on {'/'.join(DAYS[i] for i in sorted(e['wfh']))} (roster) and exit "
                   "interviews are in person (SOP 12.5).")
    if day > e["last"]:
        out.append(f"Must be no later than {e['name']}'s last day {e['last']:%m/%d/%Y}.")
    if (day == e["last"] or day.weekday() == 4) and end.time() > NICOLE_CUTOFF:
        out.append("Nicole's notes: nothing after 3pm on the employee's last day or on Fridays.")
    if key == "smith" and end.time() > T(16, 30):
        out.append("James Smith asked to be finished by 4:30pm.")
    if key == "romero" and day != e["last"] and overlaps(start.time(), end.time(), T(9, 30), T(14, 0)):
        out.append("Teresa Romero is booked 9:30am-2:00pm; schedule outside those hours (her last day is not "
                   "possible - Nicole is at the COHRE conference all day 02/18).")
    if key == "tran" and not (D(2026, 2, 16) <= day <= D(2026, 2, 20) and start.time() >= T(12, 0)):
        out.append("Gabriel Tran asked for an afternoon slot during the week of 02/16/2026, which is possible.")
    clash = [v for k, v in evs.items() if k != exclude and v["start"] and v["end"]
             and overlaps(start, end, v["start"], v["end"])]
    if clash:
        out.append("Conflicts with Nicole's calendar: " + "; ".join(
            f"\"{v['summary']}\" {v['start']:%m/%d/%Y %H:%M}-{v['end']:%H:%M}" for v in clash[:3]) + ".")
    if not out:
        for other, o in EMP.items():
            if other != key and overlaps(start, end, *o["slot"]):
                out.append(f"This takes the only slot that works for {o['name']} ({slot_text(other)}).")
    return out


# ---- rules -------------------------------------------------------------------------------------------

def _exit_call(ctx: Context, a: Action):
    if a.kind not in ("calendar_create", "calendar_update"):
        return None
    evs = calendar(ctx)
    if a.kind == "calendar_create":
        return {"id": "", "summary": str(a.args.get("summary") or ""), "start": _dt(a.args.get("start")),
                "end": _dt(a.args.get("end")), "seed": False}, evs
    eid = _event_id(a.args)
    if eid not in evs:
        return None
    return {**_merge(evs[eid], a.args), "id": eid}, evs


def _slot_pre(ctx: Context, a: Action) -> str | None:
    got = _exit_call(ctx, a)
    if not got:
        return None
    ev, evs = got
    if ev.get("seed"):
        return None  # edits of existing events: calendar.no_unrequested
    key = who(ev["summary"])
    if key is None:
        return None
    if key in NOT_ELIGIBLE:
        return f"{NOT_ELIGIBLE[key][0]} Do not schedule an exit interview for this person."
    if key == "unknown":
        return ("Only Teresa Romero, James Smith and Gabriel Tran accepted an exit interview (open voluntary "
                "OFFBOARD tickets + their email replies). Title the event exactly \"Exit Interview – [Employee Full "
                f"Name]\", e.g. \"{title('smith')}\".")
    probs = []
    if ev["summary"].strip() != title(key):
        probs.append(f"Title must be exactly \"{title(key)}\" (got \"{ev['summary']}\").")
    if a.kind == "calendar_create":
        dup = [v for v in evs.values() if not v["seed"] and who(v["summary"]) == key]
        if dup:
            probs.append(f"{EMP[key]['name']} already has an exit interview event (id {dup[0]['id']}); update or "
                         "delete that one instead of adding a second.")
    probs += slot_problems(key, ev["start"], ev["end"], evs, ev["id"])
    if not probs:
        return None
    return " ".join(probs) + f" The slot that satisfies everything: {slot_text(key)}."


def _cal_other_pre(ctx: Context, a: Action) -> str | None:
    if a.kind not in ("calendar_create", "calendar_update", "calendar_delete"):
        return None
    evs = calendar(ctx)
    if a.kind == "calendar_create":
        if who(str(a.args.get("summary") or "")) is None:
            return ("The user asked only for exit interviews on Nicole's calendar; do not add other events "
                    f"(\"{a.args.get('summary')}\").")
        return None
    eid = _event_id(a.args)
    if eid in evs and evs[eid]["seed"]:
        return (f"\"{evs[eid]['summary']}\" is an existing event on Nicole's calendar; do not change or delete it. "
                "Only add the exit interviews.")
    return None


def _scheduled(ctx: Context):
    evs = calendar(ctx)
    live = [v for v in evs.values() if not v["seed"]]
    for key, e in EMP.items():
        mine = [v for v in live if who(v["summary"]) == key]
        refs = [R_ACCEPT, R_INPERSON, R_HOURS, R_CAL]
        if not mine:
            yield False, f"{e['name']} ({e['eid']}) accepted an exit interview but none is scheduled. Create " \
                         f"{slot_text(key)}.", refs
            continue
        if len(mine) > 1:
            yield False, f"{e['name']} has {len(mine)} exit interview events; keep exactly one ({slot_text(key)}) " \
                         "and delete the others.", refs
            continue
        v = mine[0]
        probs = ([f"Title must be exactly \"{title(key)}\" (got \"{v['summary']}\")."]
                 if v["summary"].strip() != title(key) else [])
        probs += slot_problems(key, v["start"], v["end"], evs, v["id"])
        yield not probs, f"Exit interview for {e['name']} (event {v['id']}): " + " ".join(probs) + \
            f" Move it to {slot_text(key)}.", refs
    for v in live:
        key = who(v["summary"])
        if key in NOT_ELIGIBLE or key == "unknown":
            why = NOT_ELIGIBLE[key][0] if key in NOT_ELIGIBLE else "Only Romero, Smith and Tran need exit interviews."
            yield False, f"Remove \"{v['summary']}\" (event {v['id']}): {why}", [R_OFFER, R_ACCEPT]


def _no_unrequested(ctx: Context):
    evs = calendar(ctx)
    seed = {str(e.get("id")): _ev(e, True) for e in world(ctx).seed_events}
    gone = [s for k, s in seed.items() if k not in evs]
    changed = [s for k, s in seed.items() if k in evs and (evs[k]["summary"], evs[k]["start"], evs[k]["end"])
               != (s["summary"], s["start"], s["end"])]
    for s in gone:
        yield False, f"Existing event \"{s['summary']}\" ({s['start']:%m/%d/%Y %H:%M}) was deleted from Nicole's " \
                     "calendar; recreate it unchanged.", [R_DEVIATE]
    for s in changed:
        yield False, f"Existing event \"{s['summary']}\" ({s['start']:%m/%d/%Y %H:%M}-{s['end']:%H:%M}) was " \
                     "changed; restore its original title and time.", [R_DEVIATE]
    for v in evs.values():
        if not v["seed"] and who(v["summary"]) is None:
            yield False, f"Remove \"{v['summary']}\" (event {v['id']}): only exit interviews were requested.", \
                [R_DEVIATE]


T14_RX = re.compile(r"offer you the opportunity to participate in an exit interview", re.I)


def _no_resend(ctx: Context, a: Action) -> str | None:
    if a.kind in ("email_send", "email_draft") and T14_RX.search(a.text or ""):
        return ("Template 14 (Exit Interview Invitation) was already sent and the employees replied; do not re-send "
                "it - just schedule the accepted interviews.")
    return None


def _roster_emails(ctx: Context) -> set[str]:
    def build():
        rows = world(ctx).rows(r"employee_roster", r"^Email$", "initial")
        return {norm(world(ctx).col(r, r"^Email$")) for r in rows} - {""}
    return ctx.memo("d93daa01.roster_emails", build)


def _recipients(ctx: Context, a: Action) -> str | None:
    if a.kind not in ("email_send", "email_draft"):
        return None
    known = _roster_emails(ctx) | SOP_ADDRESSES
    if not _roster_emails(ctx):
        return None
    bad = [x for x in a.recipients + a.cc if x.lower() not in known]
    return (f"Recipient(s) {', '.join(bad)} are not in employee_roster.xlsx (Email column) or the SOP contact list; "
            "look the address up in the roster.") if bad else None


def _slack(ctx: Context, a: Action) -> str | None:
    w = world(ctx)
    if a.kind == "slack_dm" or (a.kind == "slack_post" and w.dm_recipients(a)):
        return "Do not use Slack direct messages for case-related communication; use the designated #hr-* channel."
    if a.kind != "slack_post":
        return None
    ch = norm(w.channel_name(a.channel))
    if ch and ch not in CHANNELS and not re.fullmatch(r"[A-Z0-9]{8,}", str(a.channel).lstrip("#")):
        return f"#{ch} is not a designated HR channel; use one of " + ", ".join(f"#{c}" for c in sorted(CHANNELS)) + "."
    if re.search(r"\bADA\b|accommodation|disabilit", a.text or "", re.I):
        return "Do not discuss an employee's disability or accommodation in Slack (email Patricia Huang/Nicole only)."
    return None


MONTHS = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|" \
         r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
BAD_DATES = [re.compile(r"\b\d{4}-\d{1,2}-\d{1,2}\b"), re.compile(r"(?<![\d/])\d{1,2}/\d{1,2}/\d{2}(?![\d/])"),
             re.compile(r"(?<![\d/])(?:\d/\d{1,2}|\d{2}/\d)/\d{4}\b"),
             re.compile(rf"\b{MONTHS}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?\b(?!:)")]


def _dates(ctx: Context, a: Action) -> str | None:
    if a.kind not in ("email_send", "email_draft", "slack_post", "slack_dm", "calendar_create", "calendar_update",
                      "jira_create", "jira_comment", "jira_update"):
        return None
    text = f"{a.subject}\n{a.text}"
    hits = [m.group(0) for rx in BAD_DATES for m in rx.finditer(text)]
    return (f"Dates must be written MM/DD/YYYY in every system field and message (found {', '.join(hits[:3])}); "
            "e.g. 02/13/2026.") if hits else None


def _jira_dup(ctx: Context, a: Action) -> str | None:
    if a.kind != "jira_create":
        return None
    text = f"{a.subject}\n{a.text}"
    hit = [e["name"] for e in EMP.values() if re.search(rf"\b{e['name'].split()[-1]}\b|{e['eid']}", text, re.I)]
    if hit or re.search(r"exit\s*interview", text, re.I):
        return ("These cases already have open tickets (OFFBOARD-3 Romero, OFFBOARD-4 Smith, OFFBOARD-5 Tran); the "
                "replies continue those cases - do not create a new or duplicate ticket.")
    return None


def _not_complete(ctx: Context, a: Action) -> str | None:
    keys = {e["ticket"] for e in EMP.values()}
    if a.kind in ("jira_transition", "jira_update") and a.channel.upper() in keys:
        blob = f"{a.code} {json.dumps(a.args)}"
        if re.search(r"\bclos|\bdone\b|\bresolv", blob, re.I):
            return (f"{a.channel} cannot be closed yet: offboarding is complete only after the exit interview is "
                    "completed (plus COBRA, final pay, access revocation).")
    if a.kind == "slack_post" and re.search(r"OFFBOARDING COMPLETE", a.text or "", re.I):
        return "Offboarding is not complete for these employees (exit interviews not yet held); do not post this."
    return None


JFMT = re.compile(r"^\s*\[?\s*\d{2}/\d{2}/\d{4}[^\n]*?[—–-]\s*(?:" + "|".join(JIRA_ACTIONS) + r")\s*[—–-]\s*\S",
                  re.S)


def _jira_comment(ctx: Context, a: Action) -> str | None:
    if a.kind != "jira_comment" or JFMT.search(a.text or ""):
        return None
    return ("Jira comments must use the default format \"[Date and time] [SOP SUBHEADER] — [Action] — [Object]\" with "
            "Action one of " + ", ".join(JIRA_ACTIONS) + ", e.g. \"02/10/2026 10:00am [12.5] — CALENDAR EVENT "
            "CREATED — Exit Interview – James Smith on 02/12/2026\".")


def _reply_subject(ctx: Context, a: Action) -> str | None:
    if a.kind != "email_send" or not re.search(r"reply|forward", a.tool) or not a.subject.strip():
        return None
    eid = str(a.args.get("email_id") or a.args.get("message_id") or "")
    orig = next((str(e.get("subject") or "") for e in world(ctx).seed_emails
                 if str(e.get("email_id") or e.get("id") or "") == eid), None)
    if orig is None:
        return None
    base = re.sub(r"^\s*(?:re|fwd?)\s*:\s*", "", orig, flags=re.I).strip()
    got = re.sub(r"^\s*(?:re|fwd?)\s*:\s*", "", a.subject, flags=re.I).strip()
    if got != base:
        return f"When replying or forwarding keep the existing subject line unchanged: \"{orig}\" (got \"{a.subject}\")."
    return None


def _housekeeping(ctx: Context, a: Action) -> str | None:
    ids = {str(i) for i in a.recipients}
    blob = json.dumps(a.args).lower()
    if a.kind == "email_move":
        target = a.channel.strip()
        if target not in FOLDERS:
            return f"Folder \"{target}\" is not an SOP folder; use exactly one of: {', '.join(FOLDERS)}."
        if ids & SEED_EMAIL_IDS and target != "Offboarding":
            return "These exit-interview emails are offboarding emails (P3) and belong in the \"Offboarding\" folder."
    if a.kind == "email_mark" and ids & SEED_EMAIL_IDS:
        if re.search(r"unread|\"(?:is_)?read\"\s*:\s*false", blob):
            return "Processed emails must stay marked as read."
        if re.search(r"flag|important|star", blob) and not re.search(
                r"unflag|unstar|\"(?:is_)?(?:flagged|important|starred)\"\s*:\s*false", blob):
            return "These are P3 offboarding emails: move to the folder, do not flag them."
    return None


RULES: list[Rule] = []
RULES += pre_rule("exit.calendar_slot", _slot_pre, [R_ACCEPT, R_OFFER, R_INPERSON, R_HOURS, R_CAL],
                  "Create/adjust the exit interview exactly as stated.")
RULES += pre_rule("calendar.no_unrequested", _cal_other_pre, [R_DEVIATE, R_ACCEPT],
                  "Leave Nicole's other events alone; only add the exit interviews.")
RULES += state_rule("exit.scheduled", _scheduled, "Schedule each accepted exit interview in its slot.")
RULES += state_rule("calendar.unchanged_otherwise", _no_unrequested, "Restore Nicole's calendar apart from the exit "
                                                                      "interviews.")
RULES += pre_rule("comms.no_resend_t14", _no_resend, [R_REPLY, R_T14], "Do not send this email.")
RULES += pre_rule("comms.recipients", _recipients, [R_EMAIL], "Use the address from employee_roster.xlsx.")
RULES += no_placeholders([R_TEMPLATES])
RULES += pre_rule("slack.channels", _slack, [R_SLACK, R_ADA], "Use the designated channel without case details.")
RULES += pre_rule("dates.format", _dates, [R_DATES], "Rewrite every date as MM/DD/YYYY.")
RULES += pre_rule("jira.no_duplicate", _jira_dup, [R_JIRA_DUP, R_REPLY, R_TRIAGE7], "Use the existing ticket.")
RULES += pre_rule("offboarding.not_complete", _not_complete, [R_DONE, R_CLOSE], "Leave the ticket open.")
RULES += pre_rule("jira.comment_format", _jira_comment, [R_JFMT, R_JACT, R_JACT2],
                  "Rewrite the comment in the SOP format.")
RULES += pre_rule("comms.reply_subject", _reply_subject, [R_JACT2], "Keep the original subject line.")
RULES += pre_rule("email.housekeeping", _housekeeping, [R_FOLDERS, R_P3, R_READ, R_TRIAGE7],
                  "Keep these emails read, unflagged, in Offboarding.")
RULES += forbid_writes("roster.no_writes", r"employee_roster\.xlsx|Crestwood_University_HR_SOP\.pdf",
                       "the roster is only updated at offboarding completion (status Separated, last day, type), "
                       "which has not happened; the user only asked for scheduling.", [R_DONE, R_ROSTER])
RULES += state_rule("roster.unchanged", lambda ctx: [
    (not world(ctx).changed_files(), "employee_roster.xlsx was modified; offboarding is not complete, so restore "
                                     "it to its original content.", [R_DONE, R_ROSTER])], "Restore the roster.")
