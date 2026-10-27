"""Crestwood University HR (79786c46): today's unread mail = new-hire batch from Derek Okonkwo (onboard Yoon,
Kapoor, Webb; Ellis already onboarded; Mendez rescinded), Sarah Mendez's rescission (forward to Derek only) and
Victor Osei's termination notice for Chris Navarro (not from Nicole Ashford / Marta Voss -> do not offboard).
Built from the SOP and seed data only."""

from __future__ import annotations

import datetime as dt
import re

from ..kit import (Action, Comm, Context, World, comm_rules, dashes, nh, no_placeholders, norm, pre_rule, state_rule,
                   text_of, world)

# ---- SOP references ------------------------------------------------------------------------------
R_ROSTER = ("11.1", "Step 1: Open employee_roster.xlsx and add a new row", "11.1 Step 1")
R_CHECKLIST = ("11.1", "Step 2: Open onboarding_checklist.xlsx", "11.1 Step 2")
R_JIRA = ("11.1", "Step 3: Create a Jira ticket: ONBOARD-", "11.1 Step 3")
R_SLACK = ("11.1", "Step 4: Post to #hr-onboarding", "11.1 Step 4")
R_WELCOME = ("11.1", "Step 5: Send Template 4", "11.1 Step 5")
R_IT = ("11.1", "Step 6: Send Template 5", "11.1 Step 6")
R_ORIENT = ("11.1", "Step 7: Send Template 31", "11.1 Step 7")
R_CAL = ("11.1", "Step 8: Create a Calendar event", "11.1 Step 8")
R_I9 = ("11.2", "Before Start Date: The HR Coordinator emails", "11.2 Before Start Date")
R_NEWHIRE_ADDR = ("3.2", "All employee internal email addresses follow", "3.2 Employee Email Addresses")
R_DATES = ("3.1", "All times in this document are Mountain", "3.1 Dates & Times")
R_NAMING = ("8", "Format: [PREFIX]-[Employee Last Name]", "8 Jira naming convention")
R_ROUTE = ("8", "Onboarding | ONBOARD", "8 routing table (Onboarding)")
R_DUP = ("8", "Step 5: Check Jira for existing open tickets", "8 Step 5")
R_CONT = ("8", "Replies to previous emails:", "8 continuation of an existing case")
R_MULTI = ("8", "Multi-topic requests:", "8 Multi-topic requests")
R_RESCIND = ("15.6", "If a candidate notifies HR that they are rescinding", "15.6 Offer Rescission")
R_INVOL = ("12.1", "Involuntary Termination: Notification will come from", "12.1 Involuntary Termination")
R_NO_DM = ("5", "All operational HR communications must use designated Slack channels", "5 Slack channels")
R_TPL = ("18", "Templates must be used as written", "18 Email Templates")
R_SUBJ = ("19", "When composing a new email (not a reply or forward)", "19 Default Email Subject Line")
R_SUBJ_FMT = ("19", "[Template Name] — [Employee Last Name", "19 subject format")
R_KEEP_SUBJ = ("19", "When replying or forwarding, keep the existing subject line", "19 replies/forwards")
R_JDESC = ("19", "When creating a Jira ticket, the ticket description starts empty", "19 Default Jira Description")
R_JDESC_NAME = ("19", "Employee Name | Employee Name:", "19 Jira field Employee Name")
R_JDESC_ASSIGN = ("19", "Assignee | Assignee:", "19 Jira field Assignee")
R_READ = ("17", "Mark as read | Every processed email", "17 Mark as read")
R_P34 = ("17", "P3 / P4 emails | Move to the matching folder", "17 P3/P4 emails")
R_FWD_ONLY = ("17", "Forwarded-only emails | If the only action", "17 Forwarded-only emails")
R_FOLDERS = ("17", "Folder names must match exactly", "17 Email Folders")
R_F_ONB = ("17", "Onboarding | All onboarding-related emails", "17 folder Onboarding")
R_F_GEN = ("17", "General | Forwarded-only emails", "17 folder General")
R_P3 = ("9", "P3 – Standard | Routine processing", "9 Priority P3")

# ---- seed facts (Derek's email #6 + employee_roster.xlsx supervisors) ---------------------------
HIRES = [
    dict(first="Daniel", last="Yoon", personal="danielyoon.work@gmail.com", position="Marketing Coordinator",
         dept="Marketing", campus="West", start="04/28/2026", cls="Exempt", sup="Sandra Bloom",
         sup_email="s.bloom@crestwood.edu"),
    dict(first="Priya", last="Kapoor", personal="priya.kapoor@outlook.com", position="Finance Analyst",
         dept="Finance", campus="Main", start="05/05/2026", cls="Exempt", sup="Robert Chen",
         sup_email="r.chen@crestwood.edu"),
    dict(first="Marcus", last="Webb", personal="marcuswebb84@gmail.com", position="IT Support Specialist",
         dept="Information Technology", campus="Main", start="04/28/2026", cls="Non-Exempt", sup="Lisa Nguyen",
         sup_email="l.nguyen@crestwood.edu"),
]
for _h in HIRES:
    _h["name"] = f"{_h['first']} {_h['last']}"
    _m, _d, _y = _h["start"].split("/")
    _h["iso"] = f"{_y}-{_m}-{_d}"
    _h["ticket"] = f"ONBOARD-{_h['last']}-{_m}{_d}{_y}"

DEREK = "d.okonkwo@crestwood.edu"
JPARK = "j.park@crestwood.edu"
CBRIGGS = "c.briggs@crestwood.edu"
EMAIL_DEREK, EMAIL_OSEI, EMAIL_MENDEZ = "6", "7", "9"
FOLDERS = {"onboarding", "offboarding", "leave", "performance", "recruiting", "general", "inbox"}
ROSTER, ROSTER_HDR = r"employee_roster", r"^first_name$"
CHECK, CHECK_HDR = r"onboarding_checklist", r"^employee_name$"


def _rx(s: str) -> str:
    return re.escape(s).replace(r"\ ", r"\s+")


def _date_is(v, iso: str) -> bool:
    s = str(v or "").strip()
    if s[:10] == iso:
        return True
    try:
        return dt.datetime.strptime(s, "%m/%d/%Y").date().isoformat() == iso
    except ValueError:
        return False


def _emails_to(a: Action) -> set[str]:
    return {x.lower() for x in a.recipients + a.cc}


def _new_rows_for(w, name_rx, hdr, name_of) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in w.new_rows(name_rx, hdr):
        out.setdefault(norm(name_of(r)), []).append(r)
    return out


def _roster_name(r: dict) -> str:
    return f"{World.col(r, r'^first_name$')} {World.col(r, r'^last_name$')}"


def _check_name(r: dict) -> str:
    return World.col(r, r"^employee_name$")


def _subject(ctx: Context, tpl: str, h: dict) -> tuple[str, str]:
    hint = f"{tpl} — {h['last']}, E-#### with the hire's employee ID (or just {tpl} — {h['last']} if none is assigned)"
    return rf"{_rx(tpl)} – {h['last']}(?:, E-\d+)?", hint


# ---- messages ------------------------------------------------------------------------------------

def _onboarding_specs(ctx: Context) -> list[Comm]:
    out: list[Comm] = []
    for h in HIRES:
        name_rx = _rx(h["name"])
        subj, hint = _subject(ctx, "New Hire Welcome", h)
        out.append(Comm(
            f"welcome_{h['last'].lower()}", "email",
            lambda a, h=h: a.kind == "email_send" and h["personal"] in {x.lower() for x in a.recipients},
            f"Template 4 (New Hire Welcome) to {h['name']}", [R_WELCOME, R_I9, R_NEWHIRE_ADDR, R_SUBJ_FMT, R_DATES],
            to=[h["personal"]], cc=[h["sup_email"]], subject=subj, subject_hint=hint,
            body=[(_rx(h["position"]), f"position \"{h['position']}\""),
                  (rf"{_rx(h['dept'])}\s+department", f"department \"{h['dept']} department\""),
                  (rf"\b{_rx(h['campus'])}\b", f"campus \"{h['campus']}\""),
                  (re.escape(h["start"]), f"start date \"{h['start']}\" (MM/DD/YYYY)"),
                  (_rx(h["sup"]), f"supervisor \"{h['sup']}\""),
                  (r"I-9", "the I-9 instructions (complete Section 1 and bring original identity documents)")],
            attach=[(r"^i9_form\.pdf$", "i9_form.pdf")]))
        subj, hint = _subject(ctx, "IT Access Provisioning Request", h)
        out.append(Comm(
            f"it_{h['last'].lower()}", "email",
            lambda a, h=h: a.kind == "email_send" and JPARK in _emails_to(a)
            and re.search(rf"\b{h['last']}\b", text_of(a), re.I) is not None,
            f"Template 5 (IT Access Provisioning Request) for {h['name']}", [R_IT, R_SUBJ_FMT, R_DATES],
            to=[JPARK], subject=subj, subject_hint=hint,
            body=[(name_rx, f"employee name \"{h['name']}\""), (_rx(h["position"]), f"position \"{h['position']}\""),
                  (_rx(h["dept"]), f"department \"{h['dept']}\""), (rf"\b{_rx(h['campus'])}\b", f"campus \"{h['campus']}\""),
                  (re.escape(h["start"]), f"start date \"{h['start']}\""), (_rx(h["sup"]), f"supervisor \"{h['sup']}\"")]))
        subj, hint = _subject(ctx, "Orientation Coordinator Request", h)
        out.append(Comm(
            f"orientation_{h['last'].lower()}", "email",
            lambda a, h=h: a.kind == "email_send" and h["sup_email"] in {x.lower() for x in a.recipients}
            and h["personal"] not in _emails_to(a) and re.search(rf"\b{h['last']}\b", text_of(a), re.I) is not None
            and re.search(r"orientation", text_of(a), re.I) is not None,
            f"Template 31 (Orientation Coordinator Request) to {h['sup']} for {h['name']}", [R_ORIENT, R_SUBJ_FMT],
            to=[h["sup_email"]], subject=subj, subject_hint=hint,
            body=[(name_rx, f"employee name \"{h['name']}\""), (_rx(h["position"]), f"position \"{h['position']}\""),
                  (re.escape(h["start"]), f"start date \"{h['start']}\"")],
            attach=[(r"^i9_form\.pdf$", "i9_form.pdf"),
                    (r"^benefits_enrollment_packet\.pdf$", "benefits_enrollment_packet.pdf")]))
        post = (rf"NEW HIRE: {name_rx}, {_rx(h['position'])}(?: \((?:Exempt|Non-Exempt)[^)]*\))?, {_rx(h['dept'])}, "
                rf"{_rx(h['campus'])}(?: Campus)?, Start Date: {re.escape(h['start'])}, "
                rf"Jira: (?:ONBOARD-\d+|{re.escape(h['ticket'])})\b")
        out.append(Comm(
            f"newhire_post_{h['last'].lower()}", "slack_post",
            lambda a, h=h: a.kind in ("slack_post", "slack_dm") and "NEW HIRE" in a.text.upper()
            and re.search(_rx(h["name"]), a.text, re.I) is not None,
            f"#hr-onboarding NEW HIRE post for {h['name']}", [R_SLACK, R_DATES], channel="hr-onboarding",
            body=[(post, f"exactly \"NEW HIRE: {h['name']}, {h['position']}, {h['dept']}, {h['campus']}, "
                         f"Start Date: {h['start']}, Jira: <ticket key of {h['ticket']}>\"")]))
    out.append(Comm(
        "forward_mendez", "forward",
        lambda a: "forward" in a.tool and str(a.args.get("email_id") or "") == EMAIL_MENDEZ,
        "forward Sarah Mendez's offer rescission email to Derek Okonkwo", [R_RESCIND, R_KEEP_SUBJ],
        to=[DEREK], exact_to=False,
        subject=r"(?:(?:fwd?|fw):\s*)?(?:re:\s*offer – academic advisor, downtown campus)?",
        subject_hint="keep the original subject \"Re: Offer — Academic Advisor, Downtown Campus\" (Fwd: prefix only)"))
    return out


def _is_email(a: Action) -> bool:
    return a.kind in ("email_send", "email_draft")


def _stop_specs(ctx: Context) -> list[Comm]:
    welcome_rx = r"welcome|i-9|orientation|first day|start date"
    no_offboard = ("Chris Navarro's termination notice came from Victor Osei, not as written authorization from "
                   "Nicole Ashford or Marta Voss; per SOP 12.1 do not initiate involuntary offboarding (no SEPARATION "
                   "post, access revocation, final pay request, COBRA/exit messages) without that authorization.")
    mendez = ("Sarah Mendez rescinded her offer acceptance (email \"Re: Offer — Academic Advisor, Downtown Campus\"); "
              "per SOP 15.6 only forward that email to d.okonkwo@crestwood.edu - do not onboard her.")
    ellis = ("Brandon Ellis is already being onboarded (Jira ONBOARD-1, NEW HIRE post, Templates 4/5/31 and the "
             "orientation event exist); do not create a duplicate case or re-send previous templates.")
    t = lambda a: text_of(a)
    return [
        Comm("navarro_offboarding", "email", lambda a: (
            (a.kind == "slack_post" or a.kind == "slack_dm") and re.search(r"navarro", a.text, re.I) is not None
            and re.search(r"SEPARATION\s*:|OFFBOARDING COMPLETE", a.text, re.I) is not None)
            or (_is_email(a) and "c.navarro@crestwood.edu" in _emails_to(a))
            or (_is_email(a) and bool(_emails_to(a) & {JPARK, CBRIGGS})
                and (re.search(r"navarro|E-1014", t(a), re.I) is not None
                     or str(a.args.get("email_id") or "") == EMAIL_OSEI)),
            "involuntary offboarding of Chris Navarro", [R_INVOL], forbidden=no_offboard),
        Comm("mendez_onboarding", "email", lambda a: (
            (a.kind in ("slack_post", "slack_dm") and "NEW HIRE" in a.text.upper() and re.search(r"mendez", a.text, re.I)
             is not None)
            or (_is_email(a) and "sarah.mendez92@gmail.com" in {x.lower() for x in a.recipients}
                and re.search(welcome_rx, t(a), re.I) is not None and "forward" not in a.tool)
            or (_is_email(a) and bool(_emails_to(a) & {JPARK, "t.hayes@crestwood.edu"})
                and re.search(r"sarah mendez", t(a), re.I) is not None
                and re.search(r"orientation|provision|access|welcome", t(a), re.I) is not None)),
            "onboarding Sarah Mendez", [R_RESCIND], forbidden=mendez),
        Comm("ellis_duplicate", "email", lambda a: (
            (a.kind in ("slack_post", "slack_dm") and "NEW HIRE" in a.text.upper() and re.search(r"ellis", a.text, re.I)
             is not None)
            or (_is_email(a) and "brandon.ellis.personal@gmail.com" in {x.lower() for x in a.recipients}
                and re.search(welcome_rx, t(a), re.I) is not None)
            or (_is_email(a) and bool(_emails_to(a) & {JPARK, "t.hayes@crestwood.edu"})
                and re.search(r"brandon ellis", t(a), re.I) is not None
                and re.search(r"orientation|provision|welcome", t(a), re.I) is not None)),
            "re-onboarding Brandon Ellis", [R_DUP, R_CONT], forbidden=ellis),
    ]


# ---- Jira ----------------------------------------------------------------------------------------

def _created_tickets(ctx: Context) -> list[str]:
    return [nh(a.subject) for a in world(ctx).calls("jira_create")]


def _jira_problem(ctx: Context, a: Action) -> str | None:
    if a.kind != "jira_create":
        return None
    s = nh(a.subject)
    if re.search(r"navarro", s, re.I) or re.search(r"^OFFBOARD", s, re.I) and re.search(r"navarro|E-1014", a.text, re.I):
        return ("Do not create an OFFBOARD ticket for Chris Navarro: the termination notice is not written authorization "
                "from Nicole Ashford or Marta Voss (SOP 12.1).")
    if re.search(r"mendez", s, re.I):
        return "Sarah Mendez rescinded her acceptance (SOP 15.6) - do not open an onboarding ticket for her."
    if re.search(r"\bellis\b", s, re.I):
        return "Brandon Ellis already has ticket ONBOARD-1 (ONBOARD-Ellis-04202026); do not create a duplicate."
    for h in HIRES:
        if not re.search(rf"\b{h['last']}\b", s, re.I):
            continue
        if s != h["ticket"]:
            return f"The onboarding ticket for {h['name']} must be named exactly \"{h['ticket']}\" (got \"{s}\")."
        if s in _created_tickets(ctx):
            return f"Ticket {h['ticket']} already exists - do not create a duplicate; comment on it instead."
        miss = [f for f, rx in ((f"Employee Name: {h['name']}", rf"Employee Name:\s*{_rx(h['name'])}"),
                                ("Assignee: HR Coordinator on duty", r"Assignee:\s*HR Coordinator"))
                if not re.search(rx, a.text, re.I)]
        if miss:
            return f"The description of {h['ticket']} must contain the field line(s): " + "; ".join(miss) + "."
    return None


def _jira_done(ctx: Context):
    have = _created_tickets(ctx)
    for h in HIRES:
        yield (h["ticket"] in have,
               f"Jira onboarding ticket for {h['name']} not created: create \"{h['ticket']}\" (project ONBOARD, "
               f"description lines \"Employee Name: {h['name']}\" and \"Assignee: HR Coordinator on duty\").",
               [R_JIRA, R_NAMING, R_ROUTE, R_MULTI])


# ---- calendar ------------------------------------------------------------------------------------

def _when(v) -> tuple[str, int | None, str]:
    s = (v.get("dateTime") or v.get("date_time") or "") if isinstance(v, dict) else str(v or "")
    m = re.match(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}):(\d{2})(?::\d{2})?(?:\.\d+)?\s*(Z|[+-]\d{2}:?\d{2})?$", str(s).strip())
    if not m:
        return "", None, ""
    return m.group(1), int(m.group(2)), (m.group(4) or "")


def _at(v, iso: str, hour: int) -> bool:
    d, h, off = _when(v)
    if d != iso or h is None:
        return False
    if off in ("", "-06:00", "-0600", "-07:00", "-0700"):
        return h == hour
    if off in ("Z", "+00:00", "+0000"):
        return h in (hour + 6, hour + 7)
    return False


def _cal_title(a: Action) -> str:
    return dashes(a.subject or a.args.get("summary") or "")


def _cal_ok(a: Action, h: dict) -> list[str]:
    out = []
    want = f"Orientation – {h['name']}"
    if norm(_cal_title(a)) != norm(want):
        out.append(f"title must be \"Orientation – {h['name']}\"")
    start = a.args.get("start") or a.args.get("start_time")
    end = a.args.get("end") or a.args.get("end_time")
    if not (_at(start, h["iso"], 9) and _at(end, h["iso"], 12)):
        out.append(f"time must be {h['start']} 9:00am–12:00pm Mountain (e.g. {h['iso']}T09:00:00-06:00 to "
                   f"{h['iso']}T12:00:00-06:00)")
    return out


def _cal_problem(ctx: Context, a: Action) -> str | None:
    if a.kind != "calendar_create":
        return None
    title = _cal_title(a)
    if not re.search(r"orientation", title, re.I):
        return None
    if re.search(r"mendez", title, re.I):
        return "Sarah Mendez rescinded her acceptance (SOP 15.6) - do not schedule her orientation."
    if re.search(r"\bellis\b", title, re.I):
        return "\"Orientation - Brandon Ellis\" already exists on the calendar (04/20/2026); do not duplicate it."
    for h in HIRES:
        if re.search(rf"\b{h['last']}\b", title, re.I):
            probs = _cal_ok(a, h)
            if probs:
                return f"Orientation event for {h['name']}: " + "; ".join(probs) + "."
            if any(not _cal_ok(b, h) for b in world(ctx).calls("calendar_create")):
                return f"The orientation event for {h['name']} already exists - do not create it twice."
    return None


def _cal_done(ctx: Context):
    made = world(ctx).calls("calendar_create")
    for h in HIRES:
        yield (any(not _cal_ok(a, h) for a in made),
               f"Calendar event \"Orientation – {h['name']}\" on {h['start']}, 9:00am–12:00pm Mountain "
               f"({h['iso']}T09:00:00-06:00 to {h['iso']}T12:00:00-06:00) not created.", [R_CAL])


# ---- workbooks -----------------------------------------------------------------------------------

def _roster_checks(ctx: Context):
    w = world(ctx)
    by_name = _new_rows_for(w, ROSTER, ROSTER_HDR, _roster_name)
    for h in HIRES:
        rows = by_name.get(norm(h["name"])) or []
        if not rows:
            yield (False, f"employee_roster.xlsx has no new row for {h['name']}: add first_name {h['first']}, last_name "
                          f"{h['last']}, department {h['dept']}, campus {h['campus']}, supervisor {h['sup']}, hire_date "
                          f"{h['iso']} (start date), classification {h['cls']}, employment_type Full-Time, status "
                          f"Onboarding.", [R_ROSTER])
            continue
        if len(rows) > 1:
            yield (False, f"employee_roster.xlsx has {len(rows)} new rows for {h['name']}; keep exactly one.", [R_ROSTER])
        r = rows[0]
        want = [(r"^department$", h["dept"]), (r"^campus$", h["campus"]), (r"^supervisor$", h["sup"]),
                (r"^classification$", h["cls"]), (r"^status$", "Onboarding")]
        bad = [f"{c.strip('^$')} = \"{v}\" (got \"{w.col(r, c)}\")" for c, v in want
               if norm(w.col(r, c)).replace(" ", "-") != norm(v).replace(" ", "-")]
        if not _date_is(w.col(r, r"^hire_date$"), h["iso"]):
            bad.append(f"hire_date = {h['iso']} / {h['start']} (got \"{w.col(r, r'^hire_date$')}\")")
        if not re.fullmatch(r"full[- ]?time", norm(w.col(r, r"^employment_type$"))):
            bad.append(f"employment_type = \"Full-Time\" (got \"{w.col(r, r'^employment_type$')}\")")
        yield (not bad, f"employee_roster.xlsx row for {h['name']} (row {r['__row__']}) must have " + "; ".join(bad) + ".",
               [R_ROSTER])
    names = {norm(h["name"]) for h in HIRES}
    extra = [n for n in by_name if n not in names]
    yield (not extra, f"employee_roster.xlsx gained row(s) for {', '.join(extra)}: only Daniel Yoon, Priya Kapoor and "
                      "Marcus Webb are new hires today (Brandon Ellis is already on the roster; Sarah Mendez "
                      "rescinded her acceptance). Remove those rows.", [R_ROSTER, R_DUP, R_RESCIND])


def _checklist_checks(ctx: Context):
    w = world(ctx)
    by_name = _new_rows_for(w, CHECK, CHECK_HDR, _check_name)
    for h in HIRES:
        rows = by_name.get(norm(h["name"])) or []
        if not rows:
            yield (False, f"onboarding_checklist.xlsx has no new row for {h['name']}: add employee_name {h['name']}, "
                          f"start_date {h['iso']}, every checklist field blank.", [R_CHECKLIST])
            continue
        if len(rows) > 1:
            yield (False, f"onboarding_checklist.xlsx has {len(rows)} new rows for {h['name']}; keep exactly one.",
                   [R_CHECKLIST])
        r = rows[0]
        bad = []
        if not _date_is(w.col(r, r"^start_date$"), h["iso"]):
            bad.append(f"start_date = {h['iso']} (got \"{w.col(r, r'^start_date$')}\")")
        filled = [k for k, v in r.items() if k not in ("__row__", "employee_id", "employee_name", "start_date")
                  and str(v).strip() not in ("", "None", "nan")]
        if filled:
            bad.append("blank (not started) checklist fields - clear " + ", ".join(filled))
        yield (not bad, f"onboarding_checklist.xlsx row for {h['name']} (row {r['__row__']}) needs " + "; ".join(bad) + ".",
               [R_CHECKLIST])
    names = {norm(h["name"]) for h in HIRES}
    extra = [n for n in by_name if n not in names]
    yield (not extra, f"onboarding_checklist.xlsx gained row(s) for {', '.join(extra)}: only Daniel Yoon, Priya Kapoor "
                      "and Marcus Webb need new checklist rows (Brandon Ellis already has one; Sarah Mendez "
                      "rescinded). Remove those rows.", [R_CHECKLIST, R_DUP, R_RESCIND])


def _navarro_checks(ctx: Context):
    w = world(ctx)
    for book, hdr, key in ((ROSTER, ROSTER_HDR, r"^employee_id$"), (r"benefits_enrollment", r"^employee_id$",
                                                                    r"^employee_id$")):
        before = w.find(book, hdr, key, "E-1014", "initial")
        now = w.find(book, hdr, key, "E-1014")
        if before is None:
            continue
        same = now is not None and {k: v for k, v in now.items() if k != "__row__"} == \
            {k: v for k, v in before.items() if k != "__row__"}
        yield (same, f"{w.book(book)[0] or book}: Chris Navarro's (E-1014) row was changed or removed. Involuntary "
                     "offboarding must not be initiated without written authorization from Nicole Ashford or Marta "
                     "Voss - restore the row exactly as it was.", [R_INVOL])


# ---- email housekeeping --------------------------------------------------------------------------

def _truthy(v) -> bool:
    return v is True or str(v).strip().lower() in ("true", "1", "yes")


def _flag_value(args: dict):
    for k in ("is_important", "important", "is_flagged", "flagged", "is_starred", "starred"):
        if k in args:
            return _truthy(args[k])
    return None


def _wrote_to_mendez(ctx: Context) -> bool:
    return any("sarah.mendez92@gmail.com" in _emails_to(a) for a in world(ctx).calls("email_send"))


def _mail_state(ctx: Context) -> dict[str, dict]:
    st: dict[str, dict] = {i: {"read": False, "folder": "INBOX", "flag": False}
                           for i in (EMAIL_DEREK, EMAIL_OSEI, EMAIL_MENDEZ)}
    for a in world(ctx).calls("email_mark", "email_move"):
        for i in a.recipients:
            if i not in st:
                continue
            if a.kind == "email_move":
                st[i]["folder"] = a.channel
                continue
            if "is_read" in a.args or "read" in a.args:
                st[i]["read"] = _truthy(a.args.get("is_read", a.args.get("read")))
            elif re.search(r"^(mark_)?(as_)?read$", str(a.args.get("action") or a.args.get("status") or ""), re.I):
                st[i]["read"] = True
            f = _flag_value(a.args)
            if f is not None:
                st[i]["flag"] = f
    return st


def _house_problem(ctx: Context, a: Action) -> str | None:
    if a.kind == "other_write" and re.search(r"create_(folder|label)", a.tool):
        return "Do not create new email folders; use the existing folders exactly as listed in SOP Section 17."
    if a.kind == "email_move":
        folder = a.channel.strip()
        if norm(folder) not in FOLDERS:
            return (f"\"{folder}\" is not an SOP folder; folder names must match exactly: Onboarding, Offboarding, Leave, "
                    "Performance, Recruiting, General.")
        if EMAIL_DEREK in a.recipients and folder != "Onboarding":
            return ("Derek's \"New Hire Notifications — April/May 2026\" email is a P3 onboarding email: move it to the "
                    "\"Onboarding\" folder.")
        if EMAIL_MENDEZ in a.recipients and folder != "General" and not _wrote_to_mendez(ctx):
            return ("Sarah Mendez's rescission email is a forwarded-only email (SOP 15.6): move it to the \"General\" "
                    "folder.")
    if a.kind == "email_mark" and EMAIL_DEREK in a.recipients and _flag_value(a.args):
        return "Derek's new-hire email is P3 (start dates more than 3 days away): P3/P4 emails are not flagged."
    return None


def _house_done(ctx: Context):
    st = _mail_state(ctx)
    subj = {EMAIL_DEREK: "New Hire Notifications — April/May 2026", EMAIL_OSEI: "Personnel Action — Navarro, E-1014",
            EMAIL_MENDEZ: "Re: Offer — Academic Advisor, Downtown Campus"}
    for i, s in st.items():
        yield (s["read"], f"Email {i} \"{subj[i]}\" is not marked as read (mark_emails email_ids [\"{i}\"], is_read true).",
               [R_READ])
    yield (st[EMAIL_DEREK]["folder"] == "Onboarding",
           f"Email {EMAIL_DEREK} \"{subj[EMAIL_DEREK]}\" (P3 onboarding) must be moved to the \"Onboarding\" folder.",
           [R_P34, R_F_ONB, R_P3])
    yield (not st[EMAIL_DEREK]["flag"], f"Email {EMAIL_DEREK} is P3 - remove the important flag.", [R_P34])
    if not _wrote_to_mendez(ctx):
        yield (st[EMAIL_MENDEZ]["folder"] == "General",
               f"Email {EMAIL_MENDEZ} \"{subj[EMAIL_MENDEZ]}\" was only forwarded: move it to the \"General\" folder.",
               [R_FWD_ONLY, R_F_GEN])


# ---- other invariants ----------------------------------------------------------------------------

def _dm_problem(ctx: Context, a: Action) -> str | None:
    if a.kind == "slack_dm" or world(ctx).dm_recipients(a):
        return "Case-related HR communication must go to the designated Slack channel, not a direct message."
    return None


RULES = (
    comm_rules("onboard", _onboarding_specs)
    + comm_rules("stop", _stop_specs)
    + pre_rule("onboard.jira", _jira_problem, [R_JIRA, R_NAMING, R_DUP, R_INVOL, R_RESCIND, R_JDESC, R_JDESC_NAME,
                                               R_JDESC_ASSIGN], "Create the ticket exactly as described.")
    + state_rule("onboard.jira_done", _jira_done, "Create the missing Jira ticket(s).")
    + pre_rule("onboard.calendar", _cal_problem, [R_CAL, R_RESCIND, R_DUP], "Fix the event as described.")
    + state_rule("onboard.calendar_done", _cal_done, "Create the missing calendar event(s).")
    + state_rule("onboard.roster", _roster_checks, "Fix employee_roster.xlsx as listed.")
    + state_rule("onboard.checklist", _checklist_checks, "Fix onboarding_checklist.xlsx as listed.")
    + state_rule("offboard.navarro_records", _navarro_checks, "Restore the original values.")
    + pre_rule("housekeeping.pre", _house_problem, [R_FOLDERS, R_P34, R_FWD_ONLY, R_F_ONB, R_F_GEN],
               "Use the folder / flag the SOP prescribes.")
    + state_rule("housekeeping.done", _house_done, "Complete the email housekeeping.")
    + pre_rule("comms.no_dm", _dm_problem, [R_NO_DM], "Post in the designated #hr-* channel instead.")
    + no_placeholders([R_TPL], literal=["[OUT OF SCOPE]"])
)
