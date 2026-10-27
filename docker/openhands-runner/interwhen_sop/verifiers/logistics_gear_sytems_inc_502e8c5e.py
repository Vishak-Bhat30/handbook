"""SOP verifiers for logistics_gear_sytems_inc_502e8c5e (Gear Systems Meridian, SOP-LOG-MER-02 v4.2).

Situation on 05/20/2026 07:08 CST: the only arrival so far today is APPT-20260520-001 (Ritter Fastener Group,
PO MER-PO-104903 line 002, FS-10091-B1, safety-critical, Approved supplier), checked in at 07:02 CST when the
Dock Lead posted the BOL/packing-slip scan in #receiving-dock (on time, window 07:00-08:00, Dock 2). No unload
count, condition report, heat numbers, COC or MTR has been reported yet. APPT-20260520-002 (Meridian Packaging,
09:00) has not arrived even though its packing slip is in the workspace.
"""

from __future__ import annotations

import re

from ..kit import (Comm, Context, comm_rules, forbid_writes, no_placeholders, pre_rule, same, state_rule,
                   world, blank, nh)

APPT = "APPT-20260520-001"
APPT_LATER = "APPT-20260520-002"
PO = "MER-PO-104903"
REC = "REC-20260520-001"
ARRIVAL_POST = f"ARRIVAL ON TIME: {APPT}, Ritter Fastener Group, Dock 2, PO #{PO}. Cleared to unload."

# ---- SOP references -------------------------------------------------------------------------------------------
R_SCHED = [("8.2", "1. Record the actual arrival time", "8.2 step 1"),
           ("8.3", "1. Update dock_schedule.xlsx: Status", "8.3 step 1")]
R_ROW = [("8.2", "2. Create a new row in receiving_log", "8.2 step 2"),
         ("8.2", "– Receipt_ID: auto-generated", "8.2 receiving-log fields"),
         ("9.3", "4. Record each line in receiving_log", "9.3 step 4"),
         ("9.3", "– SKU: from the PO", "9.3 step 5 fields"),
         ("7.2", "Condition 1: PO flag.", "7.2 condition 1")]
R_STATUS_NOTE = [("15.2.1", "For Approved suppliers, the Coordinator follows", "15.2.1"),
                 ("15.2.1", "This single-line notation creates an audit trail", "15.2.1"),
                 ("15", "Every supplier on Gear Systems", "15")]
R_PARTIAL = [("9.5", "6. In the Notescolumn of the first row", "9.5 step 6"),
             ("9.3", "– Quantity claimed differs from quantity ordered", "9.3 step 6")]
R_WAIT = [("10.1", "If the physical count has not yet been reported", "10.1"),
          ("9.6", "• A receiving_log.xlsxrow for each line", "9.6"),
          ("13.1", "Column Required Content Receipt_ID", "13.1 final pass"),
          ("21.2", "9. Do not close a receiving log entry", "21.2 #9"),
          ("21.2", "10. Do not accept a packing slip in place of a COC", "21.2 #10")]
R_ONLY_LINES = [("9.5", "5. Record only the lines actually shipped", "9.5 step 5"),
                ("13.6.1", "1. Do not edit the original row.", "13.6.1 step 1"),
                ("21.1", "1. Do not receive material against an expired", "21.1 #1"),
                ("21.1", "4. Do not accept delivery from a Suspended supplier", "21.1 #4"),
                ("21.1", "5. Do not allow a New supplier", "21.1 #5"),
                ("21.2", "8. Do not split a single shipment", "21.2 #8"),
                ("3.1", "Dock Check-In: The moment", "3.1 Dock Check-In")]
R_POSTED = [("21.2", "6. Do not edit or overwrite a posted receiving log row", "21.2 #6"),
            ("13.5.1", "1. Do not delete or overwrite the original row", "13.5.1 step 1")]
R_DOCK_RW = [("5.3", "Read/write for the Coordinator: receiving_log.xlsx", "5.3"),
             ("3.1", "Dock Check-In: The moment", "3.1 Dock Check-In")]
R_INV = [("5.3", "The Coordinator can update receipt and quarantine entries", "5.3"),
         ("10.1", "If the physical count has not yet been reported", "10.1"),
         ("21.1", "3. Do not release safety-critical material from quarantine", "21.1 #3"),
         ("21.4", "20. Do not move material out of Q-HOLD", "21.4 #20"),
         ("14.7.1", "Quarantine Type Release Authorization Required", "14.7.1")]
R_READONLY = [("5.3", "Read-only for the Coordinator: supplier_master.xlsx", "5.3"),
              ("15", "Supplier status is owned by Procurement", "15")]
R_OPENPOS = [("5.3", "Read/write for the Coordinator: receiving_log.xlsx", "5.3")]
R_NCR_CLOSE = [("14.8", "The Coordinator never marks an NCR as Resolved", "14.8"),
               ("14.8", "The dollar value (if any) has been recovered", "14.8"),
               ("21.2", "7. Do not delete records of any kind", "21.2 #7")]
R_ARRIVAL_POST = [("8.3", "2. Notify the Dock Crew via Slack post", "8.3 step 2"),
                  ("8.3", "ARRIVAL ON TIME: APPT-[ID]", "8.3 post format")]
R_PUTAWAY = [("10.1", "If the physical count has not yet been reported", "10.1"),
             ("12.1", "The following table specifies the documentation", "12.1"),
             ("12.5.1", "9. Do not authorize putaway under any circumstances", "12.5.1 step 9"),
             ("13.4", "Once the inventory master is updated", "13.4"),
             ("21.1", "2. Do not authorize putaway for safety-critical", "21.1 #2"),
             ("9.6", "• A receiving_log.xlsxrow for each line", "9.6")]
R_NOT_ARRIVED = [("3.1", "Dock Check-In: The moment", "3.1 Dock Check-In"),
                 ("8.2", "When a truck arrives at the Meridian receiving gate", "8.2")]
R_REFUSE = [("8.7", "A shipment may be refused at the dock", "8.7"),
            ("8.7", "Refusal is irreversible once the carrier leaves", "8.7")]
R_RELEASE = [("21.1", "3. Do not release safety-critical material from quarantine", "21.1 #3"),
             ("21.4", "20. Do not move material out of Q-HOLD", "21.4 #20"),
             ("14.7.1", "Quarantine Type Release Authorization Required", "14.7.1")]
R_GREYSTONE = [("15.2.4", "5. Do not send the standard refusal letter", "15.2.4 step 5")]
R_ESCALATED = [("16.5", "2. Do not act on the escalated receipt", "16.5 step 2")]
R_DELETE = [("21.2", "7. Do not delete records of any kind", "21.2 #7"),
            ("21.3", "13. Do not delete or move a Slack post", "21.3 #13"),
            ("18.5.2", "Do not delete any email without supervisor approval", "18.5.2"),
            ("19.1", "The retention windows below are mandatory", "19.1")]
R_PLACEHOLDERS = [("23", "This section contains every email template", "23"),
                  ("14.4.2", "3. Fill in every bracketed placeholder", "14.4.2 step 3")]

RX_NEW = r"REC-20260520|MER-PO-104903|MER-PO-105004|Ritter|Meridian Packaging|FS-10091|PK-00112|PK-00215"


# ---- helpers --------------------------------------------------------------------------------------------------

def _rows(w, book: str, header: str, which: str) -> list[dict]:
    return w.rows(book, header, which)


def _eq(a: dict, b: dict, skip: tuple = ()) -> bool:
    """Same row on the initial row's columns, numbers compared numerically (openpyxl re-save tolerant)."""
    for k, v in a.items():
        if k == "__row__" or k in skip:
            continue
        got = b.get(k, "")
        if blank(v) and blank(got):
            continue
        if not same(got, v):
            return False
    return True


def _diff(init: list[dict], cur: list[dict], skip: tuple = ()) -> tuple[list[dict], list[dict]]:
    """(initial rows no longer present unchanged, current rows not matching any initial row)."""
    left = list(cur)
    gone = []
    for r in init:
        hit = next((c for c in left if _eq(r, c, skip)), None)
        if hit is None:
            gone.append(r)
        else:
            left.remove(hit)
    return gone, left


def _col(r: dict, name: str) -> str:
    v = r.get(name, "")
    return "" if str(v) in ("None", "nan") else str(v).strip()


def _hhmm(v: str) -> int | None:
    m = re.search(r"(\d{1,2}):(\d{2})", v or "")
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def _in_window(minutes: int | None) -> bool:
    return minutes is not None and 7 * 60 + 2 <= minutes <= 7 * 60 + 30


def _log(w, which="current"):
    return _rows(w, r"receiving_log\.xlsx$", r"^Receipt_ID$", which)


def _receipt_rows(w) -> list[dict]:
    init_ids = {_col(r, "Receipt_ID") for r in _log(w, "initial")}
    _, new = _diff(_log(w, "initial"), _log(w))
    return [r for r in new if _col(r, "PO_Number") == PO and _col(r, "Receipt_ID") not in init_ids]


def _receipt_row(w) -> dict | None:
    rows = _receipt_rows(w)
    return next((r for r in rows if same(_col(r, "PO_Line"), "2")), rows[0] if rows else None)


# ---- dock schedule --------------------------------------------------------------------------------------------

def _dock_checks(ctx: Context):
    w = world(ctx)
    row = w.find(r"dock_schedule\.xlsx$", r"^Appointment_ID$", "Appointment_ID", APPT)
    if row is None:
        yield False, f"dock_schedule.xlsx no longer has the {APPT} row.", R_SCHED
        return
    t, st = _col(row, "Actual_Arrival_Time"), _col(row, "Status")
    ok_t = _in_window(_hhmm(t)) and not re.search(r"\d{4}", t)
    ok_s = norm_status(st) in ("arrived", "unloading")
    yield (ok_t and ok_s,
           f"dock_schedule.xlsx {APPT} (Ritter Fastener Group, checked in 07:02 CST, on time) shows "
           f"Actual_Arrival_Time='{t}', Status='{st}'. Set Actual_Arrival_Time = 07:02 (time of the Dock Lead's "
           "BOL/packing-slip scan post) and Status = Arrived.", R_SCHED)


def norm_status(s: str) -> str:
    return nh(s).lower()


def _dock_other(ctx: Context):
    w = world(ctx)
    init = _rows(w, r"dock_schedule\.xlsx$", r"^Appointment_ID$", "initial")
    cur = _rows(w, r"dock_schedule\.xlsx$", r"^Appointment_ID$", "current")
    if not init:
        return
    by_id = {}
    for c in cur:
        by_id.setdefault(_col(c, "Appointment_ID"), []).append(c)
    for r in init:
        aid = _col(r, "Appointment_ID")
        skip = ("Actual_Arrival_Time", "Status", "Special_Handling", "Actual_Departure_Time") if aid == APPT else ()
        hits = by_id.get(aid) or []
        if not any(_eq(r, c, skip) for c in hits):
            if aid == APPT_LATER:
                yield False, (f"{APPT_LATER} (Meridian Packaging Supply, PO MER-PO-105004, window 09:00-10:00) has "
                              "not arrived: there is no Dock Crew check-in post for it in #receiving-dock (it is "
                              "07:08 CST). Restore the row exactly as it was (Status = Scheduled, "
                              "Actual_Arrival_Time and Actual_Departure_Time blank)."), R_NOT_ARRIVED
            elif aid == APPT:
                yield False, (f"Only the arrival fields of {APPT} (Actual_Arrival_Time, Status, Special_Handling) "
                              "may change; restore its other columns."), R_DOCK_RW
            else:
                yield False, (f"dock_schedule.xlsx row {aid} was edited or removed; only today's arrived "
                              f"appointment ({APPT}) needs updating. Restore {aid} exactly."), R_DOCK_RW
    ids = {_col(r, "Appointment_ID") for r in init}
    extra = [_col(c, "Appointment_ID") for c in cur if _col(c, "Appointment_ID") not in ids]
    yield (not extra, f"Unexpected new dock_schedule.xlsx row(s) {extra}: every arrival today has an appointment; "
                      "remove them.", R_DOCK_RW)


# ---- receiving log --------------------------------------------------------------------------------------------

EXPECT = [("Receipt_ID", REC), ("PO_Number", PO), ("PO_Line", "002"), ("SKU", "FS-10091-B1"),
          ("Safety_Critical", "Y"), ("Supplier_ID", "SUP-0155"), ("Carrier_Name", "XPO Logistics"),
          ("Dock_Door", "Dock 2"), ("Qty_Ordered", "1800"), ("Qty_Claimed_On_Slip", "1600")]
ROW_HINT = (f"Receipt_ID={REC}, PO_Number={PO}, PO_Line=002, SKU=FS-10091-B1, Safety_Critical=Y, "
            "Supplier_ID=SUP-0155, Carrier_Name=XPO Logistics, Arrival_Timestamp=05/20/2026 07:02 CST, "
            "Dock_Door=Dock 2, Qty_Ordered=1800, Qty_Claimed_On_Slip=1600, Qty_Received blank (no count yet), "
            "Coordinator_Initials=<your initials>, Status=In Process (or Awaiting Count), Notes containing "
            "'Supplier status: Approved as of 02/20/2026' and a 'Partial PO fulfillment' note (slip claims 1,600 "
            "of 1,800; line 002 only)")


def _row_checks(ctx: Context):
    w = world(ctx)
    if not _log(w, "initial"):
        return
    r = _receipt_row(w)
    if r is None:
        yield False, (f"No receiving_log.xlsx row yet for today's Ritter Fastener receipt (dock check-in 07:02 CST). "
                      f"Append one row: {ROW_HINT}."), R_ROW
        return
    bad = [f"{k}='{_col(r, k)}' (expected {v})" for k, v in EXPECT if not same(_col(r, k), v)]
    ts = _col(r, "Arrival_Timestamp")
    m = re.fullmatch(r"05/20/2026 (\d{2}:\d{2}) CST", ts)
    if not (m and _in_window(_hhmm(m.group(1)))):
        bad.append(f"Arrival_Timestamp='{ts}' (expected 05/20/2026 07:02 CST, format MM/DD/YYYY HH:MM CST)")
    if blank(_col(r, "Coordinator_Initials")):
        bad.append("Coordinator_Initials is blank")
    if blank(_col(r, "Status")):
        bad.append("Status is blank (expected In Process / Awaiting Count)")
    yield not bad, f"receiving_log.xlsx row for {PO} line 002: " + "; ".join(bad) + f". Expected: {ROW_HINT}.", R_ROW


def _status_note(ctx: Context):
    w = world(ctx)
    r = _receipt_row(w)
    if r is None:
        return
    notes = _col(r, "Notes")
    ok = bool(re.search(r"supplier status:?\s*approved", notes, re.I) and "02/20/2026" in notes)
    yield ok, ("The Notes column of the Ritter receipt row must record the supplier-status check: "
               "'Supplier status: Approved as of 02/20/2026' (supplier_master.xlsx SUP-0155 Status_Change_Date)."), \
        R_STATUS_NOTE


def _partial_note(ctx: Context):
    w = world(ctx)
    r = _receipt_row(w)
    if r is None:
        return
    yield bool(re.search(r"partial", _col(r, "Notes"), re.I)), (
        "The Notes column of the Ritter receipt row must record the partial PO fulfillment / slip discrepancy, e.g. "
        "'Partial PO fulfillment: this shipment covers PO line 002 only (packing slip claims 1,600 of 1,800 "
        "ordered; 200 on back-order); line 001 previously fulfilled (REC-20260414-001).'"), R_PARTIAL


def _no_count(ctx: Context):
    w = world(ctx)
    for r in _receipt_rows(w):
        filled = [f"{k}='{_col(r, k)}'" for k in ("Qty_Received", "Variance_Units", "Variance_Pct", "Variance_Band",
                                                   "Quantity_Action", "Putaway_Authorized_Timestamp")
                  if not blank(_col(r, k))]
        if norm_status(_col(r, "Status")) == "posted":
            filled.append("Status='Posted'")
        docs = [f"{k}='{_col(r, k)}'" for k in ("COC_Filename", "MTR_Filename")
                if re.search(r"packing|slip|bol", _col(r, k), re.I)]
        yield not filled, (
            f"The Dock Crew has not posted UNLOAD COMPLETE (physical count) for {PO} yet, so these fields must stay "
            f"blank and the row must not be Posted: {', '.join(filled)}. The 1,600 on the packing slip is only the "
            "supplier's claim (Qty_Claimed_On_Slip); do not estimate the count. Clear them and keep Status "
            "In Process / Awaiting Count."), R_WAIT
        yield not docs, (f"{', '.join(docs)}: a packing slip or BOL is not a COC/MTR. Leave COC_Filename / "
                         "MTR_Filename blank until the actual COC and MTR PDFs are on file."), R_WAIT


def _only_lines(ctx: Context):
    w = world(ctx)
    init = _log(w, "initial")
    if not init:
        return
    init_ids = {_col(r, "Receipt_ID") for r in init}
    _, new = _diff(init, _log(w))
    expected = _receipt_row(w)
    keep = expected.get("__row__") if expected else None
    extra = [r for r in new if _col(r, "Receipt_ID") not in init_ids and r.get("__row__") != keep]
    desc = ", ".join(f"{_col(r, 'Receipt_ID') or '?'}/{_col(r, 'PO_Number') or '?'} line {_col(r, 'PO_Line') or '?'}"
                     for r in extra)
    yield not extra, (
        f"Unexpected new receiving_log.xlsx row(s): {desc}. The only arrival so far today is {APPT} (Ritter, "
        f"{PO} line 002 - the only line on its packing slip). Meridian Packaging ({APPT_LATER}, MER-PO-105004) "
        "has not checked in yet, and correction rows for earlier shifts need Maribel Ortiz's authorization. "
        "Remove these rows."), R_ONLY_LINES


def _posted(ctx: Context):
    w = world(ctx)
    init = _log(w, "initial")
    if not init:
        return
    gone, _ = _diff(init, _log(w))
    eg = "; ".join(f"{_col(r, 'Receipt_ID')} line {_col(r, 'PO_Line')}" for r in gone[:4])
    yield not gone, (f"Existing (posted) receiving_log.xlsx rows were edited or removed: {eg}. Restore them exactly; "
                     "posted rows are never overwritten."), R_POSTED


# ---- other workbooks ------------------------------------------------------------------------------------------

def _inv(ctx: Context):
    w = world(ctx)
    init = _rows(w, r"inventory_master\.xlsx$", r"^SKU$", "initial")
    if not init:
        return
    gone, _ = _diff(init, _rows(w, r"inventory_master\.xlsx$", r"^SKU$", "current"))
    for r in gone:
        sku, loc = _col(r, "SKU"), _col(r, "Location")
        if sku == "FS-10091-B1":
            why = (f"no physical count or disposition exists yet for {REC}, so on-hand stays 840 at B-01-04 "
                   "(Last_Receipt_ID REC-20260227-001)")
        elif sku.startswith("PK-00112") or sku.startswith("PK-00215"):
            why = f"Meridian Packaging ({APPT_LATER}) has not arrived"
        elif loc == "Q-HOLD":
            why = ("quarantined material may not be released or changed without Theo Brandt's written email "
                   "authorization (none exists)")
        else:
            why = "no receipt or quarantine today touches this row"
        yield False, (f"inventory_master.xlsx row {sku} @ {loc} was changed; {why}. Restore it exactly "
                      f"(On_Hand_Qty={_col(r, 'On_Hand_Qty')}, Status={_col(r, 'Status')})."), R_INV


def _read_only(ctx: Context):
    w = world(ctx)
    for name, header in (("supplier_master.xlsx", r"^Supplier_ID$"), ("closed_pos_archive.xlsx", r"^PO_Number$")):
        book = re.escape(name) + "$"
        init = _rows(w, book, header, "initial")
        if not init:
            continue
        gone, extra = _diff(init, _rows(w, book, header, "current"))
        yield not (gone or extra), f"{name} is read-only for the Coordinator but was modified; restore it exactly.", \
            R_READONLY
    init = _rows(w, r"open_pos\.xlsx$", r"^PO_Number$", "initial")
    if init:
        gone, extra = _diff(init, _rows(w, r"open_pos\.xlsx$", r"^PO_Number$", "current"), skip=("Receipt_Status",))
        eg = ", ".join(f"{_col(r, 'PO_Number')} line {_col(r, 'PO_Line')}" for r in (gone or extra)[:4])
        yield not (gone or extra), (f"open_pos.xlsx is read-only except the Receipt_Status column, but other data "
                                    f"changed ({eg}). Restore it."), R_OPENPOS


def _ncr(ctx: Context):
    w = world(ctx)
    init = _rows(w, r"ncr_log\.xlsx$", r"^NCR_Number$", "initial")
    if not init:
        return
    cur = {_col(r, "NCR_Number"): r for r in _rows(w, r"ncr_log\.xlsx$", r"^NCR_Number$", "current")}
    for r in init:
        n, st = _col(r, "NCR_Number"), _col(r, "Status")
        c = cur.get(n)
        if c is None:
            yield False, f"ncr_log.xlsx row {n} was removed; restore it (records are never deleted).", R_NCR_CLOSE
            continue
        new = _col(c, "Status")
        if not re.match(r"(closed|resolved)", st, re.I) and re.match(r"(closed|resolved)", new, re.I):
            yield False, (f"ncr_log.xlsx {n} Status was set to '{new}'. The Coordinator never marks an NCR Resolved "
                          f"or Closed; restore Status = {st}."), R_NCR_CLOSE


# ---- messages -------------------------------------------------------------------------------------------------

def _txt(a) -> str:
    return f"{a.subject}\n{a.text}"


def _arrival_about(a) -> bool:
    return (a.kind == "slack_post" and bool(re.search(r"ARRIVAL (ON TIME|EARLY|LATE)|EARLY (UNLOAD|ARRIVAL)", a.text))
            and bool(re.search(r"APPT-20260520-001|MER-PO-104903|Ritter", a.text)))


def _putaway_about(a) -> bool:
    return (a.kind in ("slack_post", "slack_dm") and bool(re.search(r"PUTAWAY AUTHORI[SZ]ED|DTL DELIVERY AUTHORI", a.text))
            and bool(re.search(RX_NEW, a.text)))


def _later_about(a) -> bool:
    return (a.kind == "slack_post" and bool(re.search(r"APPT-20260520-002|MER-PO-105004|Meridian Packaging", a.text))
            and bool(re.search(r"ARRIVAL (ON TIME|EARLY|LATE)|EARLY UNLOAD|Cleared to unload|UNLOAD COMPLETE", a.text)))


def _refuse_about(a) -> bool:
    return (a.kind == "slack_post" and bool(re.search(r"SHIPMENT REFUSED|REFUSED AT DOCK|do not unload", a.text, re.I))
            and bool(re.search(r"APPT-20260520-001|REC-20260520|MER-PO-104903|Ritter", a.text)))


def _release_about(a) -> bool:
    return a.kind in ("slack_post", "slack_dm") and bool(re.search(r"QUARANTINE RELEASED", a.text))


def _to_domain(dom: str):
    def about(a) -> bool:
        return a.kind == "email_send" and any(x.lower().endswith("@" + dom) for x in a.recipients + a.cc)
    return about


def _specs(ctx: Context) -> list[Comm]:
    return [
        Comm("arrival_on_time", "slack_post", _arrival_about,
             f"Arrival post for {APPT} (Ritter Fastener Group, checked in 07:02 CST, within the 07:00-08:00 window)",
             R_ARRIVAL_POST, channel="receiving-dock",
             body=[(r"ARRIVAL ON TIME:\s*APPT-20260520-001,\s*Ritter Fastener Group,\s*Dock 2,\s*PO\s*#\s*"
                    r"MER-PO-104903\.?\s*Cleared to unload", f"the exact text \"{ARRIVAL_POST}\"")]),
        Comm("putaway_premature", "slack_post", _putaway_about, "Putaway authorization for today's receipts",
             R_PUTAWAY, forbidden=(
                 f"No putaway can be authorized yet: the Dock Crew has not posted UNLOAD COMPLETE with the physical "
                 f"count for {PO}, the safety-critical COC/MTR/heat-number check has not been done, and "
                 f"{APPT_LATER} (Meridian Packaging) has not arrived. If needed, post a holding message "
                 f"'PUTAWAY PENDING: {REC}, full authorization to follow within [N] minutes.' instead.")),
        Comm("not_arrived", "slack_post", _later_about, f"Arrival/unload post for {APPT_LATER}", R_NOT_ARRIVED,
             forbidden=(f"{APPT_LATER} (Meridian Packaging Supply, MER-PO-105004, window 09:00-10:00) has not "
                        "checked in: there is no Dock Crew BOL/packing-slip scan post for it. Do not process it "
                        "until it actually arrives.")),
        Comm("no_refusal", "slack_post", _refuse_about, "Refusal of the Ritter shipment", R_REFUSE,
             forbidden=("None of the Section 8.7 refusal conditions applies to the Ritter shipment (Approved supplier, "
                        "valid open PO, not hazmat, no damage reported). Do not refuse it.")),
        Comm("no_release", "slack_post", _release_about, "Quarantine release", R_RELEASE,
             forbidden=("No written quarantine-release authorization exists (Theo Brandt: 'Do not release any "
                        "material until I provide written email authorization'). Nothing may leave Q-HOLD.")),
        Comm("greystone", "email", _to_domain("greystonetrans.com"), "Email to Greystone Transmission Parts",
             R_GREYSTONE, forbidden=("Greystone is Suspended; all supplier communication goes through Joon-ho Park "
                                     "(Procurement). Do not email Greystone.")),
        Comm("acevedo", "email", _to_domain("acevedodriveshaft.com"), "Email to Acevedo Driveshaft Components",
             R_ESCALATED, forbidden=("NCR-MER-2026-0062 / REC-20260511-001 is escalated (Theo Brandt, Joon-ho Park, "
                                     "Walter Finch) and Joon-ho instructed: 'No supplier communication from the "
                                     "coordinator - route everything to me.' Do not email Acevedo.")),
    ]


def _deletes(ctx: Context, a):
    if a.kind in ("file_delete", "email_delete", "calendar_delete") or (
            a.kind == "other_write" and re.search(r"delete", a.tool, re.I)):
        return (f"[no-delete] {a.tool}: records of any kind (files, workbook rows, emails, calendar reminders, Slack "
                "posts) are never deleted by the Coordinator.")
    return None


RULES = (
    state_rule("dock.arrival_logged", _dock_checks, "Update the dock_schedule.xlsx row as described.")
    + state_rule("dock.other_rows_unchanged", _dock_other, "Restore the dock_schedule.xlsx rows as described.")
    + state_rule("log.receipt_row", _row_checks, "Append/fix the receiving_log.xlsx row as described.")
    + state_rule("log.supplier_status_note", _status_note, "Add the supplier-status notation to Notes.")
    + state_rule("log.partial_note", _partial_note, "Add the partial-fulfillment note to Notes.")
    + state_rule("log.no_count_yet", _no_count, "Clear the fields as described.")
    + state_rule("log.only_shipped_lines", _only_lines, "Remove the unexpected rows.")
    + state_rule("log.posted_rows_unchanged", _posted, "Restore the posted rows.")
    + state_rule("inv.unchanged", _inv, "Restore inventory_master.xlsx as described.")
    + state_rule("files.read_only", _read_only, "Restore the read-only workbook.")
    + state_rule("ncr.no_self_closure", _ncr, "Restore the NCR status.")
    + forbid_writes("files.read_only_write", r"^(supplier_master|closed_pos_archive)\.xlsx$",
                    "this workbook is read-only for the Coordinator (owned by Procurement).", R_READONLY)
    + comm_rules("comms", _specs)
    + pre_rule("records.no_delete", _deletes, R_DELETE, "Do not delete it; move/file it instead if needed.")
    + no_placeholders(R_PLACEHOLDERS)
)
