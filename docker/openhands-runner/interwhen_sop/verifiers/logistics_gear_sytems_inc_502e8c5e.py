"""Verifiers for task logistics_gear_sytems_inc_502e8c5e (process today's dock arrivals that already occurred).

Built from the task's own SOP plus the instruction ("arrivals that have already occurred today"):
  * 8.2 - dock check-in = the Dock Crew's #receiving-dock post announcing the paperwork scan; record that
    time in dock_schedule (Status Arrived) and create the receiving-log row (REC-YYYYMMDD-NNN, CST)
  * 8.3 - on-time post format
  * 9.3 / 9.5 - one row per shipped PO line, Qty_Claimed_On_Slip from the packing slip, Status Awaiting
    Count, partial-fulfillment note
  * 10.1 - never estimate counts: Qty_Received and everything after it waits for the UNLOAD COMPLETE post
Arrivals are derived from the Dock Crew scan posts; schedule/PO facts from the workbooks.
"""

from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from dataclasses import dataclass
from functools import cached_property

from .. import common
from ..actions import Action
from ..framework import Context, Finding, Rule, registry
from ..gear import World, blank, norm, num

TASK_RULES: list[Rule] = []
rule = registry(TASK_RULES)

TODAY = dt.date(2026, 5, 20)       # task system prompt: "May, 20, 2026, 7:08 AM"
PLANT_UTC_OFFSET = -6              # the SOP clock is CST; the system time 7:08 AM fixes it at UTC-6
DOCK, RCV, POS = "dock_schedule.xlsx", "receiving_log.xlsx", "open_pos.xlsx"
SCAN = re.compile(r"BOL and packing slip scanned and uploaded for (APPT-\d{8}-\d{3})")


@dataclass
class Arrival:
    appt: dict
    checkin: dt.datetime
    lines: list[dict]          # open_pos rows on the packing slip
    slip_qty: dict[str, float]  # PO_Line -> Qty shipped per packing slip/BOL


class Facts(World):
    @cached_property
    def scans(self) -> dict[str, dt.datetime]:
        msgs = [(m.get("text", ""), float(m.get("ts", 0))) for ms in (self._slack_seed.get("messages") or {}).values()
                for m in ms]
        msgs += [(m.text, m.ts) for m in self.state.slack]
        tz = dt.timezone(dt.timedelta(hours=PLANT_UTC_OFFSET))
        out = {}
        for text, ts in msgs:
            m = SCAN.search(text)
            if m:
                out[m.group(1)] = dt.datetime.fromtimestamp(ts, tz).replace(tzinfo=None)
        return out

    @cached_property
    def todays_appts(self) -> list[dict]:
        today = TODAY.strftime("%m/%d/%Y")
        return [r for r in self.rows(DOCK, "Appointment_ID", "initial") if str(r.get("Scheduled_Date")) == today]

    @cached_property
    def arrivals(self) -> list[Arrival]:
        pos = self.rows(POS, "PO_Number", "initial")
        out = []
        for a in self.todays_appts:
            t = self.scans.get(a["Appointment_ID"])
            if not t or t.date() != TODAY:
                continue
            po = a.get("Expected_PO_Numbers", "").split(",")[0].strip()
            lines = [p for p in pos if p.get("PO_Number") == po and norm(p.get("Receipt_Status")) != "fulfilled"]
            out.append(Arrival(a, t, lines, self.slip_quantities(po)))
        return out

    def slip_quantities(self, po: str) -> dict[str, float]:
        """Shipped quantity per PO line from the packing slip text the agent has read (or the workspace PDF)."""
        texts = [o.get("text", "") for o in self.state.observations if po in o.get("text", "")
                 and "PACKING SLIP" in o.get("text", "").upper()]
        out = {}
        for t in texts:
            for m in re.finditer(r"\b(\d{3})\s+[A-Z]{2}-\d{5}-[A-Z]\d\b.*?\b([\d,]+)\s+([\d,]+)\s+units", t):
                out[m.group(1)] = num(m.group(3))
        return out

    @cached_property
    def pending_ids(self) -> set[str]:
        """Today's appointments/POs with no check-in yet - not to be processed."""
        arrived = {a.appt["Appointment_ID"] for a in self.arrivals}
        ids = set()
        for a in self.todays_appts:
            if a["Appointment_ID"] not in arrived and norm(a.get("Status")) == "scheduled":
                ids.add(a["Appointment_ID"])
                ids |= {p.strip() for p in str(a.get("Expected_PO_Numbers", "")).split(",") if p.strip()}
        return ids

    @cached_property
    def initials(self) -> str:
        c = Counter(r.get("Coordinator_Initials") for r in self.rows(RCV, "Receipt_ID", "initial")
                    if r.get("Coordinator_Initials"))
        return c.most_common(1)[0][0] if c else ""

    def receipt_id(self, arrival: Arrival) -> str:
        existing = sorted(r["Receipt_ID"] for r in self.rows(RCV, "Receipt_ID", "initial")
                          if r["Receipt_ID"].startswith(f"REC-{TODAY:%Y%m%d}-"))
        n = int(existing[-1][-3:]) if existing else 0
        return f"REC-{TODAY:%Y%m%d}-{n + 1 + self.arrivals.index(arrival):03d}"

    def unloaded(self, rid: str) -> bool:
        msgs = [m.get("text", "") for ms in (self._slack_seed.get("messages") or {}).values() for m in ms]
        msgs += [m.text for m in self.state.slack]
        return any(t.startswith("UNLOAD COMPLETE") and rid in t for t in msgs)


def facts(ctx: Context) -> Facts:
    return ctx.memo("f502", lambda: Facts(ctx))


def _blob(a: Action) -> str:
    return f"{a.subject}\n{a.text}\n{a.code}"


@rule("arrivals.only_checked_in", "pre", [("8.2", "When a truck arrives at the Meridian receiving gate")],
      source="sop+task_instruction")
def only_checked_in(ctx: Context, action: Action) -> list[Finding]:
    if action.kind in ("read", "control"):
        return []
    if action.kind in ("slack_post", "slack_dm", "email_send") and not re.search(
            r"ARRIVAL|cleared to unload|PUTAWAY|REFUSED|HOLD|received", action.text, re.I):
        return []
    f = facts(ctx)
    hits = sorted(i for i in f.pending_ids if i in _blob(action))
    if not hits:
        return []
    return [Finding("arrivals.only_checked_in", [
        ctx.cite("8.2", "When a truck arrives at the Meridian receiving gate", "8.2 (dock check-in)"),
        "Task instruction: \"Process all dock arrivals that have already occurred today\""],
        f"{', '.join(hits)} has not checked in: no Dock Crew post announcing its paperwork scan exists, so the "
        "truck has not arrived yet (an advance packing slip is not a check-in).",
        ["Leave that appointment, its PO and the receiving log untouched until the truck checks in."])]


def _arrival_post(f: Facts, a: Arrival) -> str:
    ap = a.appt
    return (f"ARRIVAL ON TIME: {ap['Appointment_ID']}, {ap['Supplier_Name']}, {ap['Dock_Door']}, "
            f"PO #{ap['Expected_PO_Numbers']}. Cleared to unload.")


def _on_time(a: Arrival) -> bool:
    start, end = a.appt.get("Scheduled_Window_Start", ""), a.appt.get("Scheduled_Window_End", "")
    hhmm = a.checkin.strftime("%H:%M")
    return bool(start and end) and start <= hhmm <= end


@rule("arrivals.post_format", "pre", [("8.3", "ARRIVAL ON TIME:")])
def arrival_post(ctx: Context, action: Action) -> list[Finding]:
    if action.kind != "slack_post" or not action.text.strip().upper().startswith("ARRIVAL"):
        return []
    f = facts(ctx)
    a = next((x for x in f.arrivals if x.appt["Appointment_ID"] in action.text), None)
    if a is None or not _on_time(a):
        return []
    want = _arrival_post(f, a)
    probs = [] if norm(want) == norm(action.text) else [f"Dock check-in was {a.checkin:%H:%M} CST, inside the "
                                                        f"window, so the post must read exactly: '{want}'"]
    if not f.is_channel(action.channel, "receiving-dock"):
        probs.append("Post it in #receiving-dock.")
    if not probs:
        return []
    return [Finding("arrivals.post_format", [ctx.cite("8.3", "ARRIVAL ON TIME:", "8.3 step 2")], " ".join(probs),
                    ["Use the exact Section 8.3 wording."])]


@rule("quantity.no_estimated_counts", "pre", [("10.1", "If the physical count has not yet been reported")])
def no_estimates(ctx: Context, action: Action) -> list[Finding]:
    f = facts(ctx)
    for a in f.arrivals:
        rid = f.receipt_id(a)
        if f.unloaded(rid):
            continue
        blob = _blob(action)
        putaway = action.kind == "slack_post" and "PUTAWAY AUTHORIZED" in blob.upper() and rid in blob
        count = action.kind == "workbook_write" and RCV in action.files_written and re.search(
            r"Qty_Received['\"]?\s*\]?\s*[:=,]\s*[^\s'\"]|Variance_|Disposition['\"]?\s*\]?\s*[:=,]", action.code)
        if putaway or count:
            return [Finding("quantity.no_estimated_counts", [
                ctx.cite("10.1", "If the physical count has not yet been reported", "10.1")],
                f"No 'UNLOAD COMPLETE: {rid} ...' count has been posted by the Dock Lead yet; quantity, variance, "
                "disposition and putaway cannot be recorded from the packing slip or BOL.",
                ["Leave Qty_Received and the disposition columns blank (Status: Awaiting Count) and wait for the "
                 "Dock Lead's count."])]
    return []


@rule("arrivals.completion", "completion", [("8.2", "Within 15 minutes of dock check-in"),
                                            ("9.3", "5. For each line, populate")])
def completion(ctx: Context) -> list[Finding]:
    f = facts(ctx)
    probs: list[str] = []
    dock_now = {r["Appointment_ID"]: r for r in f.rows(DOCK, "Appointment_ID")}
    rcv_now = f.rows(RCV, "Receipt_ID")
    posts = [e.action.text for e in f.posts_in("receiving-dock")]
    for a in f.arrivals:
        aid, po = a.appt["Appointment_ID"], a.appt.get("Expected_PO_Numbers", "")
        hhmm = a.checkin.strftime("%H:%M")
        d = dock_now.get(aid, {})
        if str(d.get("Actual_Arrival_Time", "")).strip()[:5] != hhmm or norm(d.get("Status")) != "arrived":
            probs.append(f"dock_schedule.xlsx {aid}: Actual_Arrival_Time must be {hhmm} (time of the Dock Crew's scan "
                         f"post, CST) and Status 'Arrived' (got '{d.get('Actual_Arrival_Time', '')}', "
                         f"'{d.get('Status', '')}').")
        if _on_time(a) and not any(norm(_arrival_post(f, a)) in norm(p) for p in posts):
            probs.append(f"No '{_arrival_post(f, a)}' post in #receiving-dock (8.3).")
        rid = f.receipt_id(a)
        rows = [r for r in rcv_now if r.get("Receipt_ID") == rid]
        if not rows:
            probs.append(f"receiving_log.xlsx has no row for {rid} (8.2 step 2 / 9.3: one row per shipped PO line).")
            continue
        unloaded = f.unloaded(rid)
        shipped = {l["PO_Line"] for l in a.lines}
        for r in rows:
            line = next((l for l in a.lines if l.get("PO_Line") == r.get("PO_Line")), None)
            bad = []
            if line is None:
                bad.append(f"PO_Line {r.get('PO_Line')} is not an open line on this shipment's packing slip "
                           "(9.5 step 5: record only lines actually shipped)")
            else:
                exp = {"PO_Number": po, "SKU": line.get("SKU"), "Supplier_ID": a.appt.get("Supplier_ID"),
                       "Carrier_Name": a.appt.get("Carrier_Name"), "Dock_Door": a.appt.get("Dock_Door"),
                       "Safety_Critical": line.get("Safety_Critical"), "Coordinator_Initials": f.initials}
                bad += [f"{k} = {v}" for k, v in exp.items() if v and str(r.get(k, "")).strip() != v]
                if num(r.get("Qty_Ordered")) != num(line.get("Qty_Ordered")):
                    bad.append(f"Qty_Ordered = {line.get('Qty_Ordered')} (from the PO)")
                slip = a.slip_qty.get(line["PO_Line"])
                if slip is not None and num(r.get("Qty_Claimed_On_Slip")) != slip:
                    bad.append(f"Qty_Claimed_On_Slip = {int(slip)} (from the packing slip)")
                elif blank(r.get("Qty_Claimed_On_Slip")):
                    bad.append("Qty_Claimed_On_Slip from the packing slip")
            want_ts = f"{TODAY:%m/%d/%Y} {hhmm} CST"
            if str(r.get("Arrival_Timestamp", "")).strip() != want_ts:
                bad.append(f"Arrival_Timestamp = '{want_ts}'")
            if not unloaded:
                if any(not blank(r.get(k)) for k in ("Qty_Received", "Variance_Units", "Variance_Band", "Disposition")):
                    bad.append("Qty_Received/variance/disposition left blank until the Dock Lead posts the count "
                               "(10.1)")
                if norm(r.get("Status")) != "awaiting count":
                    bad.append("Status = 'Awaiting Count' (9.3 step 5)")
            if bad:
                probs.append(f"receiving_log.xlsx {rid} line {r.get('PO_Line')}: " + "; ".join(bad) + ".")
        all_lines = [p for p in f.rows(POS, "PO_Number", "initial") if p.get("PO_Number") == po]
        if len(all_lines) > 1 and not any("partial po fulfillment" in norm(r.get("Notes")) for r in rows):
            probs.append(f"{po} has {len(all_lines)} lines but this shipment covers {', '.join(sorted(shipped))}: add "
                         "the 9.5 step 6 note 'Partial PO fulfillment: this shipment covers PO lines [list], remaining "
                         "open lines: [list].' to the first row.")
    for b, a2 in f.changed_rows(DOCK, "Appointment_ID", lambda r: r.get("Appointment_ID") in f.pending_ids):
        probs.append(f"dock_schedule.xlsx {(b or a2 or {}).get('Appointment_ID')} was changed but that truck has not "
                     "checked in; restore it.")
    if any(r.get("PO_Number") in f.pending_ids for r in rcv_now):
        probs.append("receiving_log.xlsx has a row for a PO whose truck has not checked in; remove that premature "
                     "entry's data (it must not exist yet).")
    if not probs:
        return []
    return [Finding("arrivals.completion", [ctx.cite("8.2", "Within 15 minutes of dock check-in", "8.2"),
                                            ctx.cite("9.3", "5. For each line, populate", "9.3 step 5"),
                                            ctx.cite("10.1", "If the physical count has not yet been reported", "10.1")],
                    "Today's arrivals are not recorded per the SOP: " + " ".join(probs[:8]),
                    ["Fix each listed item, then finish."])]


RULES = common.RULES + TASK_RULES
