"""SLM-backed fact extraction with Python grounding.

Each function asks the SLM to *extract* facts from conversation text and then
discards anything that is not literally present in that text. No compliance
decision is taken here.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

from . import slm
from .sopdata import SOP, Contact, fold
from .state import RECEIPT_ID, SlackMessage, State

COORDINATOR_POST_PREFIXES = (
    "END-OF-SHIFT HANDOFF", "PUTAWAY AUTHORIZED", "ARRIVAL", "DOCK SCHEDULE", "DAILY DOCK",
    "SHIPMENT REFUSED", "ESCALATION", "QUARANTINE", "OVERDUE",
)

REPORT_SCHEMA = """{
  "is_new_damage_report": boolean,  // author reports damage they found on material that was already received
  "receipt_ids": [string],          // receipt IDs exactly as written, e.g. REC-20260101-001
  "skus": [string],                 // part numbers exactly as written
  "damaged_units": integer|null,    // number of damaged units stated
  "total_units": integer|null,      // total units of that receipt/lot stated
  "discovery_activity": "re-inspection"|"putaway"|"line staging"|"first use"|"unloading"|"other"|null,
  "photos_provided": boolean,       // the text says photos are attached or shared
  "written_description_provided": boolean, // the text gives a written description of location and nature of the damage
  "material_consumed_in_production": boolean|null
}"""

EVIDENCE_SCHEMA = """{
  "provides_photos": boolean,               // the message supplies photos (attached/shared)
  "provides_written_description": boolean   // the message describes count, location and nature of the damage
}"""

INCIDENT_SCHEMA = """{
  "refers_to_incident": boolean,  // the text is about the incident described under 'Incident'
  "announces": [string]           // any of: quarantine, ncr, carrier_claim, supplier_notification,
                                  // receiving_log_amendment, reinspection_schedule, information_request, other
}"""

COORDINATOR_SCHEMA = """{
  "coordinator_full_name": string|null,  // name of the Inbound Materials Coordinator who wrote these handoff posts / signed these emails, exactly as written (may be abbreviated, e.g. 'Jane D.')
  "coordinator_initials": string|null    // initials only if written explicitly in the text
}"""

INSTRUCTION_SCHEMA = """{
  "acting_for": string|null,        // name of the person the assistant is acting for, if the user states it
  "requests_end_of_shift_handoff": boolean,  // the user asks for the end-of-shift handoff process
  "reported_by": string|null,       // name of the person whose report the user refers to
  "channel_requirements": [{"person": string, "channel": "email"|"slack"|"phone"}]  // explicit instructions on how to communicate with a person
}"""


@dataclass
class DamageReport:
    source: str  # "slack" | "email"
    text: str
    date: dt.date | None
    receipt_id: str
    sku: str | None
    damaged_units: int | None
    total_units: int | None
    discovery_activity: str | None
    photos_provided: bool
    written_description_provided: bool
    consumed: bool | None
    channel: str = ""
    user: str = ""
    reporter: Contact | None = None
    ts: float | None = None
    extra: dict = field(default_factory=dict)

    @property
    def receipt_date(self) -> dt.date:
        m = RECEIPT_ID.search(self.receipt_id)
        d = m.group(1)
        return dt.date(int(d[:4]), int(d[4:6]), int(d[6:8]))


def _report_candidates(st: State, coordinator_users: set[str]) -> list[SlackMessage]:
    out = []
    for m in st.slack:
        if m.user in coordinator_users or m.user.startswith("U_MOCK"):
            continue
        if m.text.strip().upper().startswith(COORDINATOR_POST_PREFIXES):
            continue
        if re.search(r"damag", m.text, re.I):
            out.append(m)
    return out


def coordinator_users(st: State) -> set[str]:
    return {uid for uid, u in st.users.items() if "coordinator" in str(u.get("title") or "").lower()
            and "inbound" in str(u.get("title") or "").lower()}


def damage_reports(st: State, sop: SOP, log: list) -> list[DamageReport]:
    reports: list[DamageReport] = []
    instr = instruction_facts(st, sop, log)
    for m in _report_candidates(st, coordinator_users(st)):
        facts = slm.extract("damage report facts", REPORT_SCHEMA, m.text, log=log)
        if not facts or not facts.get("is_new_damage_report"):
            continue
        rids = [r for r in facts.get("receipt_ids") or [] if slm.grounded(r, m.text) and RECEIPT_ID.fullmatch(r)]
        if not rids:
            rids = [x.group(0) for x in RECEIPT_ID.finditer(m.text)]
        if not rids:
            continue
        skus = [s for s in facts.get("skus") or [] if slm.grounded(s, m.text)]
        num = lambda v: v if isinstance(v, int) and slm.grounded(str(v), m.text) else None  # noqa: E731
        reporter = _resolve_user(st, sop, m.user) or instr.get("reported_by")
        for rid in rids:
            reports.append(DamageReport(
                source="slack", text=m.text, date=m.date, receipt_id=rid,
                sku=skus[0] if skus else None,
                damaged_units=num(facts.get("damaged_units")),
                total_units=num(facts.get("total_units")),
                discovery_activity=facts.get("discovery_activity"),
                photos_provided=bool(facts.get("photos_provided")) and bool(m.files),
                written_description_provided=bool(facts.get("written_description_provided")),
                consumed=facts.get("material_consumed_in_production"),
                channel=m.channel, user=m.user, reporter=reporter, ts=m.ts,
            ))
    return reports


def _resolve_user(st: State, sop: SOP, user_id: str) -> Contact | None:
    u = st.users.get(user_id) or {}
    if u.get("email"):
        c = sop.contact_by_email(u["email"])
        if c:
            return c
    if u.get("name"):
        return sop.contact_by_name(u["name"])
    return None


def evidence_received(st: State, report: DamageReport, log: list) -> tuple[bool, str]:
    """Photos (actual files/attachments) and a written description from the reporter."""
    if report.photos_provided and report.written_description_provided:
        return True, "photos and description were included in the original report"
    if report.reporter is None:
        return False, "reporter unknown"
    ids = {report.receipt_id, report.sku or ""} - {""}
    for em in st.emails:
        if em.sender != report.reporter.email.lower():
            continue
        if not any(i in f"{em.subject}\n{em.body}" for i in ids):
            continue
        if not em.attachments:
            continue
        facts = slm.extract("damage evidence reply", EVIDENCE_SCHEMA, f"Subject: {em.subject}\n{em.body}", log=log)
        if facts and facts.get("provides_photos") and facts.get("provides_written_description"):
            return True, f"email '{em.subject}' from {em.sender} with {len(em.attachments)} attachment(s)"
    for m in st.slack:
        if report.ts is None or m.ts <= report.ts or m.user != report.user or not m.files:
            continue
        facts = slm.extract("damage evidence reply", EVIDENCE_SCHEMA, m.text, log=log)
        if facts and facts.get("provides_photos") and facts.get("provides_written_description"):
            return True, "Slack follow-up from reporter with files"
    return False, "no reply with photos and a written description from the reporter yet"


def refers_to_incident(text: str, report: DamageReport, ids: set[str], log: list) -> tuple[bool, list[str]]:
    if any(i and i in text for i in ids):
        literal = True
    else:
        literal = False
    incident = (f"Concealed damage on receipt {report.receipt_id}"
                f"{' SKU ' + report.sku if report.sku else ''}: {report.text[:400]}")
    facts = slm.extract("outgoing message topic", INCIDENT_SCHEMA,
                        f"Incident: {incident}\n\nMessage:\n{text[:6000]}", log=log)
    announces = [a for a in (facts or {}).get("announces") or [] if isinstance(a, str)]
    return literal or bool(facts and facts.get("refers_to_incident")), announces


def coordinator_initials(st: State, log: list, acting_for: str | None = None) -> tuple[str | None, str]:
    observed = st.observed_text + "\n" + "\n".join(m.text for m in st.slack)
    name, source = acting_for, "user instruction"
    if not name:
        coords = coordinator_users(st)
        name = next((u.get("name") for uid, u in st.users.items() if uid in coords and u.get("name")), None)
        source = "slack user profile"
    initials = None
    if not name:
        # Section 18.4 handoff posts and the role's email signatures name the Coordinator.
        lines = [m.text.splitlines()[0] for m in st.slack if "HANDOFF" in m.text.upper()[:40]]
        for em in st.emails:
            if em.sender.startswith("receiving.") and "Inbound Materials Coordinator" in em.body:
                sig = em.body.split("Inbound Materials Coordinator")[0].strip().splitlines()[-2:]
                lines.append(" / ".join(sig) + " / Inbound Materials Coordinator")
        snippet = "\n".join(dict.fromkeys(lines))[:3000]
        if snippet:
            facts = slm.extract("coordinator identity", COORDINATOR_SCHEMA, snippet, log=log) or {}
            cand = facts.get("coordinator_full_name")
            if cand and slm.grounded(cand, snippet):
                name, source = cand, "observed records"
            ini = facts.get("coordinator_initials")
            if ini and re.fullmatch(r"[A-Z]{2,4}", ini) and re.search(rf"\b{ini}\b", observed):
                initials = ini
    if name and not initials:
        parts = [p for p in re.split(r"[\s.]+", fold(name)) if p]
        if len(parts) >= 2:
            initials = (parts[0][0] + parts[-1][0]).upper()
    if not initials:
        return None, "coordinator initials not found in observed records"
    if not re.search(rf"\b{initials}\b", observed):
        return initials, f"derived from {name} ({source}); not yet seen in records"
    return initials, f"{name or 'Coordinator'} ({source})"


def instruction_facts(st: State, sop: SOP, log: list) -> dict:
    text = st.instruction
    if not text:
        return {}
    facts = slm.extract("user instruction facts", INSTRUCTION_SCHEMA, text, log=log) or {}
    out: dict = {"channel_requirements": [],
                 "end_of_shift_handoff": bool(facts.get("requests_end_of_shift_handoff"))}
    who_for = facts.get("acting_for")
    if who_for and slm.grounded(who_for, text):
        out["acting_for"] = who_for
    who = facts.get("reported_by")
    if who and slm.grounded(who, text):
        out["reported_by"] = sop.contact_by_name(who)
    for req in facts.get("channel_requirements") or []:
        person, channel = (req or {}).get("person"), (req or {}).get("channel")
        if person and channel and slm.grounded(person, text) and slm.grounded(channel, text):
            contact = sop.contact_by_name(person)
            if contact:
                out["channel_requirements"].append((contact, channel))
    return out
