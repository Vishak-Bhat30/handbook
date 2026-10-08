"""Verifiers for task logistics_gear_sytems_inc_74170ae1 (end-of-shift handoff, SOP Section 18).

Built from the task's own SOP only. Facts are computed in Python from the workbooks and
the observed Slack/mail; the SLM only extracts fields from free text (email topic facts,
Handoff_Notes parts, closed-workbook claims). Rules = shared SOP checks (common.py) +
the Section 18 rules below.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from functools import cached_property

from .. import common, config, slm, templates, workbooks
from ..actions import Action
from ..framework import Context, Finding, Rule, registry
from ..state import State

TASK_RULES: list[Rule] = []
rule = registry(TASK_RULES)

OPEN_HANDOFF = "open - handoff"
POSTED = {"posted", "closed"}
NCR_ID = re.compile(r"NCR-MER-\d{4}-\d{3,4}")
REC_ID = re.compile(r"REC-\d{8}-\d{3}")
PO_ID = re.compile(r"MER-PO-\d{5,6}")

EMAIL_SCHEMA = """{
  "sender_kind": "supplier"|"carrier"|"internal_staff"|"customer"|"marketing_or_newsletter"|"other",
  "mentions_ncr": boolean,          // the email explicitly refers to a Nonconformance Report / NCR
  "ncr_numbers": [string],          // NCR numbers exactly as written
  "receipt_or_po_refs": [string],   // receipt IDs (REC-...) or PO numbers (MER-PO-...) exactly as written
  "hazmat": boolean,                // about hazardous materials, SDS, EHS
  "customer_return": boolean        // about a customer return / RMA
}"""

NOTE_SCHEMA = """{
  "where_in_process": string|null,      // where the receipt is in the process
  "next_action": string|null,           // what needs to happen next
  "next_action_owner": string|null,     // who owns the next action (person, role, supplier)
  "deadlines_or_sensitivities": string|null
}"""

CLOSED_SCHEMA = """{
  "closed_files": [string],       // workbook/file names the text says were closed
  "not_closed_files": [string]    // file names the text says were NOT open, not present, or not closed
}"""


def norm_status(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[\u2012-\u2015-]+", "-", str(s or ""))).strip().lower()


@dataclass
class Escalation:
    receipt_id: str
    ts: float
    awaiting: list[str]
    acknowledged: bool


@dataclass
class ShiftFacts:
    state: State
    log: list

    @cached_property
    def today(self) -> dt.date | None:
        return self.state.today()

    @property
    def today_str(self) -> str:
        return self.today.strftime("%m/%d/%Y") if self.today else ""

    @cached_property
    def current(self) -> dict:
        return workbooks.dump() or {}

    @cached_property
    def initial(self) -> dict:
        p = workbooks.snapshot_path()
        return json.loads(p.read_text()) if p.exists() else {}

    def receiving(self, which: str = "current") -> list[dict]:
        src = self.current if which == "current" else self.initial
        return workbooks.table(workbooks.first_sheet(src, "receiving_log.xlsx"), "Receipt_ID")

    def _today_rows(self, rows: list[dict]) -> list[dict]:
        return [r for r in rows if str(r.get("Arrival_Timestamp", "")).startswith(self.today_str)]

    @cached_property
    def handoff_rows(self) -> list[dict]:
        """Rows In Process at shift start (Section 18.1 item 1), in their current state."""
        start = {(r["Receipt_ID"], r.get("PO_Line", "")) for r in self._today_rows(self.receiving("initial"))
                 if norm_status(r.get("Status", "")) == "in process"}
        return [r for r in self.receiving() if (r.get("Receipt_ID"), r.get("PO_Line", "")) in start]

    @cached_property
    def open_receipts(self) -> list[str]:
        today = self._today_rows(self.receiving())
        return sorted({r["Receipt_ID"] for r in today if norm_status(r.get("Status", "")) not in POSTED})

    @cached_property
    def completed_receipts(self) -> list[str]:
        return sorted({r["Receipt_ID"] for r in self._today_rows(self.receiving())} - set(self.open_receipts))

    @cached_property
    def ncrs(self) -> list[dict]:
        return workbooks.table(workbooks.first_sheet(self.current, "ncr_log.xlsx"), "NCR_Number")

    @property
    def ncrs_today(self) -> list[dict]:
        return [n for n in self.ncrs if str(n.get("Issue_Date", "")).startswith(self.today_str)]

    @property
    def ncrs_awaiting_coordinator(self) -> list[str]:
        # Status "Open" = drafted, not yet sent (Section 18.1 item 4 "drafts pending Theo's review").
        return sorted(n["NCR_Number"] for n in self.ncrs if norm_status(n.get("Status", "")) == "open")

    @cached_property
    def qhold(self) -> list[dict]:
        inv = workbooks.table(workbooks.first_sheet(self.current, "inventory_master.xlsx"), "SKU")
        return [r for r in inv if str(r.get("Location", "")).upper().startswith("Q-HOLD")]

    @property
    def quarantines_today(self) -> list[dict]:
        return [r for r in self.qhold if str(r.get("Quarantine_Date", "")).startswith(self.today_str)]

    @cached_property
    def escalation_channel(self) -> str | None:
        return next((cid for cid, name in self.state.channels.items() if name == "escalations-meridian"), None)

    @cached_property
    def escalations(self) -> list[Escalation]:
        """Escalation posts (Templates 25-27) and whether every awaited owner replied afterwards."""
        chan = self.escalation_channel
        if not chan:
            return []
        msgs = sorted((m for m in self.state.slack if m.channel == chan), key=lambda m: m.ts)
        out = []
        for m in msgs:
            if not m.text.strip().upper().startswith(("ESCALATION", "TOP-TIER ESCALATION")):
                continue
            rid = REC_ID.search(m.text)
            if not rid:
                continue
            low = m.text.lower()
            tail = m.text[low.rfind("awaiting"):] if "awaiting" in low else ""
            awaiting = re.findall(r"<@(U\w+)>", tail)
            later = [x for x in msgs if x.ts > m.ts]
            acked = bool(awaiting) and all(any(x.user == u for x in later) for u in awaiting)
            out.append(Escalation(rid.group(0), m.ts, awaiting, acked))
        return out

    @property
    def open_escalations(self) -> list[Escalation]:
        return [e for e in self.escalations if not e.acknowledged]

    @cached_property
    def inbox_today(self) -> list:
        day = self.today.isoformat() if self.today else "~"
        return [e for e in self.state.emails if e.folder.upper() == "INBOX" and e.date.startswith(day)]

    def acceptable_folders(self, email) -> tuple[set[str], str]:
        """Section 18.5.1/18.5.2 folders allowed for this email, from SLM-extracted facts."""
        text = f"From: {email.sender}\nSubject: {email.subject}\n{email.body[:3000]}"
        facts = slm.extract("email filing facts", EMAIL_SCHEMA, text, log=self.log) or {}
        ncr_nums = [n for n in facts.get("ncr_numbers") or [] if slm.grounded(n, text)] + NCR_ID.findall(text)
        refs = set(REC_ID.findall(text)) | set(PO_ID.findall(text))
        refs |= {r for r in facts.get("receipt_or_po_refs") or [] if slm.grounded(r, text)}
        linked = [r for r in self.receiving() if r.get("Receipt_ID") in refs or r.get("PO_Number") in refs]
        active = [r for r in linked if norm_status(r.get("Status", "")) not in POSTED]
        if facts.get("mentions_ncr") or ncr_nums:
            closed = {n["NCR_Number"] for n in self.ncrs if norm_status(n.get("Status", "")) in ("resolved", "closed")}
            folder = "NCRs - Closed" if ncr_nums and all(n in closed for n in ncr_nums) else "NCRs - Open"
            return {folder, "General"}, f"refers to an NCR ({', '.join(sorted(set(ncr_nums))) or 'NCR'})"
        cats: set[str] = set()
        why: list[str] = []
        if active:
            cats.add("Receipts - In Process")
            why.append(f"concerns active receipt {active[0]['Receipt_ID']}")
            if any(r.get("NCR_Number") for r in active):
                cats.add("NCRs - Open")
        kind = facts.get("sender_kind")
        if email.sender.endswith("@gearsystems.com") or kind == "internal_staff":
            cats.add("Internal")
            why.append("internal sender")
        if kind == "carrier":
            cats.add("Carriers")
            why.append("carrier communication")
        if kind == "supplier" and not active:
            cats.add("Suppliers - General")
            why.append("supplier communication not tied to an NCR or active receipt")
        if facts.get("hazmat"):
            cats.add("Hazmat")
        if facts.get("customer_return"):
            cats.add("RMA - Redirected")
        if kind == "marketing_or_newsletter":
            cats.add("General")
            why.append("marketing/off-topic")
        if not cats or not facts:
            return set(), "no category facts extracted"
        return cats | {"General"}, "; ".join(why)

    def note_problems(self, note: str) -> list[str]:
        """Section 18.2: '[Status]: [where it is]. [What next]. [Owner]. [Deadlines]'."""
        note = note.strip()
        if not note:
            return ["Handoff_Notes is empty"]
        problems = []
        if not re.match(r"^[^:\n]{3,60}:", note):
            problems.append("does not start with a '[Status]:' label")
        facts = slm.extract("handoff note fields", NOTE_SCHEMA, note, log=self.log)
        if facts is None:
            return problems
        for key, label in (("where_in_process", "where the receipt is in the process"),
                           ("next_action", "what needs to happen next"),
                           ("next_action_owner", "who owns the next action")):
            if not facts.get(key):
                problems.append(f"missing {label}")
        return problems

    def workspace_workbooks(self) -> list[str]:
        return sorted(p.name for p in config.workdir().glob("*.xlsx"))

    def closed_claims(self, text: str) -> set[str]:
        facts = slm.extract("closed workbooks claims", CLOSED_SCHEMA, text[:6000], log=self.log) or {}
        names = lambda key: {re.sub(r"^.*/", "", f).strip() for f in facts.get(key) or [] if slm.grounded(f, text)}  # noqa: E731
        closed = names("closed_files") if facts else set(re.findall(r"[\w-]+\.xlsx", text))
        return closed - names("not_closed_files")


def facts(ctx: Context) -> ShiftFacts:
    return ctx.memo("shift_facts", lambda: ShiftFacts(ctx.state, ctx.log))


def _is_handoff_post(a: Action) -> bool:
    first = next((ln for ln in a.text.splitlines() if ln.strip()), "")
    return a.tool == "slack__post_message" and "END-OF-SHIFT HANDOFF" in templates.norm(first).upper()


def _handoff_posted(ctx: Context) -> list:
    return [e for e in ctx.state.executed if e.action.kind == "slack_post" and _is_handoff_post(e.action)]


def folder_names(ctx: Context) -> list[str]:
    return [m.group(1).strip() for p in ctx.sop.section("18.5.1") if (m := re.match(r"•\s*(.+?)\s+—\s", p["text"]))]


def dock_lead_ids(ctx: Context) -> set[str]:
    """Slack ids of the Dock Lead: by SOP contact name, or as author of UNLOAD COMPLETE posts (Section 9.6)."""
    lead = next((c for c in ctx.sop.contacts if "dock lead" in c.role.lower()), None)
    ids = {u for u, d in ctx.state.users.items()
           if lead and lead.name and str(d.get("name", "")).lower() == lead.name.lower()}
    ids |= {m.user for m in ctx.state.slack if m.text.strip().upper().startswith("UNLOAD COMPLETE")}
    return ids


def row_problems(ctx: Context) -> list[str]:
    """Section 18.1 items 1-3 / 18.2 / 18.3 step 1 on rows that were In Process at shift start."""
    f = facts(ctx)
    out = []
    for r in f.handoff_rows:
        rid = f"{r.get('Receipt_ID')} line {r.get('PO_Line', '')}".strip()
        status = norm_status(r.get("Status", ""))
        if status in POSTED:
            continue
        if status != OPEN_HANDOFF:
            out.append(f"{rid}: Status is '{r.get('Status')}' - set it to 'OPEN — handoff' (Section 18.1 item 3, "
                       f"18.3 step 1) or complete the receipt.")
        probs = f.note_problems(str(r.get("Handoff_Notes", "") or ""))
        if probs:
            out.append(f"{rid}: Handoff_Notes {', '.join(probs)} (Section 18.2 format '[Status]: [where it is]. "
                       f"[What happens next]. [Next-action owner]. [Deadlines]').")
    return out


def _sections(text: str, labels: list[str]) -> dict[str, str]:
    norm_text = "\n".join(templates.norm(ln) for ln in text.splitlines())
    spans = []
    for lab in labels:
        m = re.search(rf"^{re.escape(templates.norm(lab))}\s*$", norm_text, re.M | re.I)
        if m:
            spans.append((m.start(), m.end(), lab))
    spans.sort()
    return {lab: norm_text[e:(spans[i + 1][0] if i + 1 < len(spans) else len(norm_text))]
            for i, (s, e, lab) in enumerate(spans)}


def _count(text: str, label: str) -> int | None:
    m = re.search(rf"^{re.escape(label)}\s*:\s*(\d+)", "\n".join(templates.norm(x) for x in text.splitlines()),
                  re.M | re.I)
    return int(m.group(1)) if m else None


# --------------------------------------------------------------------------- pre-tool rules

@rule("handoff.post_format_and_content", "pre", [
    ("18.4", "The Coordinator posts a single consolidated handoff message"),
    ("18.1", "Item Action Reference 1 Review every In Process row"),
    ("18.1", "6 Review the day"),
    ("18.3", "4. Note in the handoff post"),
    ("16.5", "6. If end of shift approaches"),
])
def handoff_post(ctx: Context, action: Action) -> list[Finding]:
    if action.kind != "slack_post" or not _is_handoff_post(action):
        return []
    f = facts(ctx)
    refs = [ctx.cite("18.4", "The Coordinator posts a single consolidated", "18.4")]
    problems, fixes = [], []
    chan = ctx.state.channels.get(action.channel, action.channel).lstrip("#")
    if chan != "receiving-dock":
        problems.append(f"The handoff post goes in #receiving-dock (got '{chan}').")
    if _handoff_posted(ctx):
        problems.append("A handoff post was already sent; Section 18.4 requires a single consolidated message.")
        fixes.append("Post any correction as a thread reply to the original handoff post (Section 21.3 item 13).")
    rows = row_problems(ctx)
    if rows:
        refs.append(ctx.cite("18.2", "A receipt is open at end of shift", "18.2"))
        problems.append("Receiving log is not ready for handoff (checklist items 1-3 come before the post): "
                        + " ".join(rows))
        fixes.append("Update receiving_log.xlsx first: Status 'OPEN — handoff' and a structured Handoff_Notes "
                     "entry for every receipt that cannot be completed today.")
    if not f.escalation_channel or not any(m.channel == f.escalation_channel for m in ctx.state.slack):
        problems.append("The day's escalations were not reviewed (Section 18.1 item 6).")
        fixes.append("Read #escalations-meridian and include every escalation still awaiting acknowledgement.")

    tpl = ctx.sop.template(28)["body"]
    first = templates.norm(next((ln for ln in action.text.splitlines() if ln.strip()), ""))
    expected_head = f"END-OF-SHIFT HANDOFF {f.today_str} - Coordinator: {ctx.initials[0] or '[Initials]'}"
    if first != templates.norm(expected_head):
        problems.append(f"First line must be the Template 28 header with placeholders filled (no brackets): "
                        f"\"{expected_head.replace(' - ', ' — ')}\" (got \"{first}\").")
    labels = [ln for ln in tpl if ln.endswith(":") and "[" not in ln]
    secs = _sections(action.text, labels)
    missing = [lab for lab in labels if lab not in secs]
    if missing:
        problems.append(f"Missing Template 28 section(s): {missing}.")
    for label, want in (("Receipts completed today", len(f.completed_receipts)),
                        ("Receipts open at handoff", len(f.open_receipts)),
                        ("NCRs issued today", len(f.ncrs_today)),
                        ("Quarantines applied today", len(f.quarantines_today))):
        got = _count(action.text, label)
        if got != want:
            problems.append(f"'{label}: {got if got is not None else '?'}' does not match the workbooks ({want}).")
    esc_got = _count(action.text, "Escalations open")
    if esc_got is None or esc_got < len(f.open_escalations):
        problems.append(f"'Escalations open' must count at least the {len(f.open_escalations)} escalation(s) still "
                        f"awaiting acknowledgement.")

    def need(section: str, ids: list[str], what: str):
        lost = [i for i in ids if i not in secs.get(section, "")]
        if lost:
            problems.append(f"{section} must list {what}: {lost}.")

    need("OPEN RECEIPTS:", f.open_receipts, "every receipt still open (Section 18.3 step 4)")
    need("OPEN NCRs AWAITING COORDINATOR ACTION:", f.ncrs_awaiting_coordinator,
         "NCRs drafted but not yet sent (Section 18.1 item 4)")
    need("OPEN ESCALATIONS:", sorted({e.receipt_id for e in f.open_escalations}),
         "escalations awaiting acknowledgement (Sections 16.5 step 6, 18.1 item 6)")
    m = re.search(r"holds\s+(\d+)\s+entr", secs.get("QUARANTINE STATUS:", ""), re.I)
    if m and int(m.group(1)) != len(f.qhold):
        problems.append(f"Q-HOLD currently holds {len(f.qhold)} entries per inventory_master.xlsx (post says "
                        f"{m.group(1)}).")
    if not problems:
        return []
    fixes.append("Use Template 28 exactly: header, the five count lines, then OPEN RECEIPTS / OPEN NCRs AWAITING "
                 "COORDINATOR ACTION / OPEN ESCALATIONS / QUARANTINE STATUS / NOTES FOR TOMORROW ('- None' when "
                 "empty).")
    return [Finding("handoff.post_format_and_content", refs, " ".join(problems), fixes)]


@rule("handoff.email_folder", "pre", [
    ("18.5.1", "• Receipts - In Process"),
    ("18.5.2", "• If an email belongs to multiple categories"),
])
def email_folder(ctx: Context, action: Action) -> list[Finding]:
    if action.kind != "email_move":
        return []
    allowed = folder_names(ctx)
    target = action.channel.strip()
    refs = [ctx.cite("18.5.2", "• If an email belongs to multiple categories", "18.5.2")]
    if target not in allowed:
        return [Finding("handoff.email_folder", refs, f"'{target}' is not a Section 18.5.1 folder.",
                        [f"Use one of: {', '.join(allowed)}."])]
    f = facts(ctx)
    wrong = []
    for eid in action.recipients:
        em = next((e for e in ctx.state.emails if e.email_id == eid), None)
        if em is None:
            continue
        ok, why = f.acceptable_folders(em)
        if ok and target not in ok:
            wrong.append(f"email {eid} '{em.subject[:60]}' ({why}) belongs in {sorted(ok - {'General'}) or ['General']}")
    if not wrong:
        return []
    return [Finding("handoff.email_folder", refs, f"Wrong folder '{target}': " + "; ".join(wrong) + ".",
                    ["Move each email to its highest-priority Section 18.5.1 folder (NCR-related first); file an "
                     "email in General and leave it unread only if you are unsure."])]


@rule("handoff.close_workbooks_last", "pre", [
    ("18.6", "At the very end of the shift, after the handoff post is sent"),
    ("18.6", "The Coordinator visually confirms each of the following"),
])
def closed_workbooks(ctx: Context, action: Action) -> list[Finding]:
    if action.kind not in ("file_write", "workbook_write"):
        return []
    if not [t for t in action.files_written if not t.endswith(".xlsx")] or ".xlsx" not in action.text:
        return []
    f = facts(ctx)
    closed = f.closed_claims(action.text)
    if not closed:
        return []
    problems = []
    if not _handoff_posted(ctx):
        problems.append("Workbooks are closed at the very end of the shift, after the handoff post is sent.")
    present = set(f.workspace_workbooks())
    if ghost := sorted(closed - present):
        problems.append(f"Listed as closed but not in the workspace: {ghost}.")
    if missing := sorted(present - closed):
        problems.append(f"Workspace workbooks not confirmed closed: {missing}.")
    if not problems:
        return []
    return [Finding("handoff.close_workbooks_last", [ctx.cite("18.6", "At the very end of the shift", "18.6")],
                    " ".join(problems), [f"After the handoff post, confirm exactly these workbooks: {sorted(present)}."])]


# --------------------------------------------------------------------------- completion

@rule("handoff.completion", "completion", [
    ("18.1", "The Coordinator begins the end-of-shift process"),
    ("18.1", "7 File all processed emails"),
    ("18.3", "3. Confirm the Dock Crew knows"),
    ("18.5", "Throughout the shift, the Coordinator processes emails"),
    ("18.5.2", "• Mark every processed email as read"),
])
def handoff_completion(ctx: Context) -> list[Finding]:
    f = facts(ctx)
    out: list[Finding] = []
    if rows := row_problems(ctx):
        out.append(Finding("handoff.completion", [ctx.cite("18.2", "A receipt is open at end of shift", "18.2")],
                           "Open receipts are not handed off: " + " ".join(rows),
                           ["Set Status 'OPEN — handoff' and write a structured Handoff_Notes entry for each."]))
    if not _handoff_posted(ctx):
        out.append(Finding("handoff.completion", [ctx.cite("18.4", "The Coordinator posts a single", "18.4")],
                           "No end-of-shift handoff post was sent in #receiving-dock.",
                           ["Post the Template 28 handoff message in #receiving-dock."]))
    listed = any(a.tool == "google_mail__get_emails" and str(a.args.get("folder", "")).upper() == "INBOX"
                 for a, _ in ctx.state.reads)
    if not listed:
        out.append(Finding("handoff.completion", [ctx.cite("18.5", "Throughout the shift", "18.5")],
                           "The inbox was never reviewed, so emails cannot have been filed.",
                           ["List the INBOX and file every email received this shift (Section 18.5)."]))
    else:
        moved: dict[str, str] = {}
        read: set[str] = set()
        for e in ctx.state.executed:
            if e.action.kind == "email_move":
                moved.update({i: e.action.channel for i in e.action.recipients})
            if e.action.kind == "email_mark" and e.action.args.get("is_read") in (True, "true", "True"):
                read.update(e.action.recipients)
        left = [e for e in f.inbox_today if e.email_id not in moved]
        unread = [e for e in f.inbox_today if e.email_id in moved and moved[e.email_id] != "General"
                  and e.email_id not in read and e.is_read is not True]
        if left:
            out.append(Finding("handoff.completion", [ctx.cite("18.5", "Throughout the shift", "18.5")],
                               "Emails still in the inbox: " + "; ".join(f"{e.email_id} '{e.subject[:50]}'" for e in left),
                               ["File every email into its Section 18.5.1 folder."]))
        if unread:
            out.append(Finding("handoff.completion", [ctx.cite("18.5.2", "• Mark every processed email", "18.5.2")],
                               "Filed emails not marked read: " + ", ".join(e.email_id for e in unread),
                               ["Mark processed emails as read (only unsure emails filed in General stay unread)."]))
    if f.open_receipts:
        curtis = dock_lead_ids(ctx)
        dms = [e for e in ctx.state.executed if e.action.kind == "slack_dm" and set(e.action.recipients) & curtis]
        covered = all(any(re.search(rf"{rid}|REC-{rid[-3:]}\b", e.action.text) for e in dms) for rid in f.open_receipts)
        if not dms or not covered:
            out.append(Finding("handoff.completion", [ctx.cite("18.3", "3. Confirm the Dock Crew knows", "18.3 step 3")],
                               "The Dock Lead has not been sent a summary of which open material is in which status.",
                               [f"Direct-message Curtis Yablonski summarising {', '.join(f.open_receipts)} "
                                f"(location/status of the material)."]))
    m = re.search(r"([\w.-]+\.txt)", ctx.state.instruction)
    if m and not (config.workdir() / m.group(1)).exists():
        out.append(Finding("handoff.completion", ["task instruction"],
                           f"The requested file {m.group(1)} has not been written.",
                           ["After the handoff post, write it listing every workbook you closed (Section 18.6)."]))
    return out


RULES: list[Rule] = common.RULES + TASK_RULES
