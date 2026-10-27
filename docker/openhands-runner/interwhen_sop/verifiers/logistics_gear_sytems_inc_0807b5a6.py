"""Verifiers for logistics_gear_sytems_inc_0807b5a6 (Gear Systems Meridian - quarantine release requests, 04/23/2026).

Seed facts: two release requests arrived today.
- Email 0041, Theo Brandt (Quality Manager): COC reviewed, release FG-91144-A1, 200 units, REC-20260414-001 (heat
  HT-2026-1803 = Q-HOLD row). Safety-critical release by Theo's written email -> authorized (Sec 14.7.1, 21.1 #3).
  The other two lines of the receipt (AX-04827-B2 x44, AX-05512-C1 x96) stay on hold -> partial release.
- Email 0042, Darnell Hooks (Receiving Supervisor): release BG-33044-A1, 144 units, REC-20260414-002. Safety-critical
  -> needs Theo's email; Darnell's authorization is insufficient -> not actionable.
"""

from __future__ import annotations

import re

from interwhen_sop.kit import (COMM_KINDS, WRITE_KINDS, Comm, World, blank, comm_rules, nh, no_placeholders, norm,
                               num, pre_rule, same, state_rule, strict_writes, world)

INV, RCV, NCR = r"inventory_master\.xlsx$", r"receiving_log\.xlsx$", r"ncr_log\.xlsx$"
FG, BG, AX = "FG-91144-A1", "BG-33044-A1", ("AX-04827-B2", "AX-05512-C1")
REC1, REC2 = "REC-20260414-001", "REC-20260414-002"
TODAY = "04/23/2026"
FG_ON_HAND = 285  # 85 active + 200 released
FG_BINS = r"A-09-0[13]"  # active stock row A-09-01; packing slip noted A-09-03 (receiving log note)
RELEASE_FILE = r"(^|/)quarantine_releases/REC-20260414-001_release\.pdf$"

R_AUTH = [("14.7.1", "Quarantine Type Release Authorization Required", "14.7.1 release authority"),
          ("21.1", "3. Do not release safety-critical material from quarantine", "21.1 #3"),
          ("21.4", "20. Do not move material out of Q-HOLD", "21.4 #20")]
R_FILE = [("14.7.2", "1. Confirm the written authorization is in hand", "14.7.2 step 1"),
          ("5.4", "• Quarantine release authorizations", "5.4")]
R_INV = [("14.7.2", "3. Delete the Q-HOLD row entirely", "14.7.2 step 3"),
         ("14.7.2", "4. On the active stock row for the released SKU", "14.7.2 step 4"),
         ("14.7.2", "5. For safety-critical parts: on the active stock row", "14.7.2 step 5")]
R_RCV = [("14.7.2", "6. Update the original row(s) in receiving_log.xlsx", "14.7.2 step 6")]
R_POST = [("14.7.2", "9. Authorize physical putaway via Slack post", "14.7.2 step 9"),
          ("14.7.2", "QUARANTINE RELEASED: [Original Receipt_ID]", "14.7.2 post format")]
R_CAL = [("14.7.2", "8. If there are any re-inspection calendar events", "14.7.2 step 8"),
         ("14.7.2", "Partial release [Date]", "14.7.2 partial release note")]
R_NCR = [("14.8", "3. Awaiting closure decision", "14.8"),
         ("14.8", "• Any quarantined material has been released or returned", "14.8 closure conditions")]
R_RO = [("5.1", "• supplier_master.xlsx", "5.1"),
        ("5.3", "• Read-only for the Coordinator", "5.3"),
        ("5.3", "• Read/write for the Coordinator", "5.3")]
R_ROWS = [("13.3", "2. Locate the row for the SKU at the Quarantine Cage location", "13.3 step 2"),
          ("21.2", "6. Do not edit or overwrite a posted receiving log row", "21.2 #6"),
          ("14.7.2", "6. Update the original row(s) in receiving_log.xlsx", "14.7.2 step 6")]
R_DEL = [("21.2", "7. Do not delete records of any kind", "21.2 #7"),
         ("18.5.2", "• Do not delete any email without supervisor approval", "18.5.2"),
         ("21.3", "13. Do not delete or move a Slack post", "21.3 #13")]
R_PH = [("23", "This section contains every email template", "23")]


# ---- workbook helpers ----------------------------------------------------------------------------

def _k(v) -> str:
    n = num(v)
    return str(int(n)) if n is not None and n == int(n) else norm(v)


def _get(row: dict | None, col: str) -> str:
    v = (row or {}).get(col, "")
    return "" if str(v) in ("None", "nan") else str(v).strip()


def _changed_cols(cur: dict, init: dict) -> list[str]:
    """Columns whose value changed (number-tolerant; formula cells and the row index ignored)."""
    out = []
    for col, want in init.items():
        if col == "__row__" or str(want).startswith("="):
            continue
        if not same(cur.get(col, ""), None if blank(want) else want):
            out.append(col)
    return out


def _unmatched(init: list[dict], cur: list[dict]) -> tuple[list[dict], list[dict]]:
    """(initial rows with no unchanged counterpart, current rows left over) - multiset match."""
    left, missing = list(cur), []
    for r in init:
        m = next((c for c in left if not _changed_cols(c, r)), None)
        if m is None:
            missing.append(r)
        else:
            left.remove(m)
    return missing, left


def _is_qhold(r: dict) -> bool:
    return "q-hold" in (norm(_get(r, "Warehouse_Zone")), norm(_get(r, "Location")))


def _inv(w: World, which: str = "current") -> list[dict]:
    return w.rows(INV, r"^SKU$", which)


def _date_is(v: str, *mmddyyyy: str) -> bool:
    v = nh(v)
    for d in mmddyyyy:
        m, dd, y = d.split("/")
        if v.startswith(d) or v.startswith(f"{y}-{m}-{dd}"):
            return True
    return False


# ---- completion: FG release end state --------------------------------------------------------------

def _fg_inventory(ctx):
    w = world(ctx)
    if not w.book(INV)[0]:
        return
    rows = [r for r in _inv(w) if norm(_get(r, "SKU")) == norm(FG)]
    hold = [r for r in rows if _is_qhold(r)]
    active = [r for r in rows if not _is_qhold(r)]
    yield (not hold, f"inventory_master.xlsx still has the {FG} Q-HOLD row ({REC1}). All 200 units are released, "
                     "so delete that Q-HOLD row entirely (after copying its heat number to the active row).", R_INV)
    total = sum(num(_get(r, "On_Hand_Qty")) or 0 for r in active)
    yield (abs(total - FG_ON_HAND) < 0.01,
           f"{FG} active stock On_Hand_Qty must be {FG_ON_HAND} (85 on hand + 200 released) on the existing "
           f"active row (Location A-09-01); found {total:g}.", R_INV)
    bad_q = [r for r in active if (num(_get(r, "Quarantine_Qty")) or 0) != 0 or not blank(_get(r, "Quarantine_Reason"))]
    yield (not bad_q, f"On the {FG} active stock row set Quarantine_Qty to 0 and clear Quarantine_Reason.", R_INV)
    heats = " ".join(_get(r, "Heat_Numbers_On_Hand") for r in active).upper()
    yield ("HT-2026-1803" in heats and "HT-2026-0218" in heats,
           f"{FG} active row Heat_Numbers_On_Hand must keep HT-2026-0218 and append HT-2026-1803 "
           "(comma-separated: \"HT-2026-0218, HT-2026-1803\"); heat numbers are append-only.", R_INV)
    ok_last = any(norm(_get(r, "Last_Receipt_ID")) == norm(REC1)
                  and _date_is(_get(r, "Last_Receipt_Date"), "04/14/2026", TODAY) for r in active)
    yield (ok_last, f"{FG} active row: set Last_Receipt_ID to {REC1} and Last_Receipt_Date to the released "
                    "receipt's date 04/14/2026.", R_INV)


def _fg_receiving_log(ctx):
    w = world(ctx)
    if not w.book(RCV)[0]:
        return
    row = next((r for r in w.rows(RCV, r"^Receipt_ID$")
                if norm(_get(r, "Receipt_ID")) == norm(REC1) and norm(_get(r, "SKU")) == norm(FG)), None)
    if row is None:
        yield (False, f"receiving_log.xlsx row {REC1} line 003 ({FG}) is missing; update it in place, do not remove it.",
               R_RCV)
        return
    want = {"Status": "Putaway Complete", "Disposition": "ACCEPTED",
            "Documentation_Status": "COC Received and Verified", "Documentation_Action": "ACCEPTED"}
    wrong = [f"{c} = \"{v}\" (now \"{_get(row, c)}\")" for c, v in want.items() if norm(_get(row, c)) != norm(v)]
    t = nh(_get(row, "Putaway_Auth_Time"))
    if not re.fullmatch(r"(04/23/2026 \d{1,2}:\d{2}( CST)?|2026-04-23[ T]\d{1,2}:\d{2}(:\d{2})?)", t):
        wrong.append(f"Putaway_Auth_Time = current timestamp \"{TODAY} HH:MM CST\" (now \"{t}\")")
    loc = nh(_get(row, "Putaway_Location"))
    if not re.fullmatch(FG_BINS, loc, re.I):
        wrong.append(f"Putaway_Location = the FG-91144-A1 warehouse bin (active stock row A-09-01; the packing "
                     f"slip noted A-09-03) instead of \"{loc}\"")
    yield (not wrong, f"receiving_log.xlsx {REC1} line 003 ({FG}) must be updated in place for the release: "
                      + "; ".join(wrong) + ".", R_RCV)


def _release_record(ctx):
    w = world(ctx)
    yield (any(re.search(RELEASE_FILE, f.replace("\\", "/"), re.I) for f in w.files()),
           "Save Theo Brandt's release authorization email (0041) as "
           "quarantine_releases/REC-20260414-001_release.pdf in the workspace.", R_FILE)


# ---- completion: nothing else released / changed ------------------------------------------------------

def _unauthorized(ctx):
    w = world(ctx)
    held = {norm(BG)} | {norm(s) for s in AX}
    if w.book(INV)[0]:
        missing, extra = _unmatched([r for r in _inv(w, "initial") if norm(_get(r, "SKU")) in held],
                                    [r for r in _inv(w) if norm(_get(r, "SKU")) in held])
        names = sorted({f"{_get(r, 'SKU')} @ {_get(r, 'Location')}" for r in missing + extra})
        yield (not names,
               f"Only {FG} has a valid release (Theo Brandt's email 0041). Restore the inventory_master.xlsx rows for "
               f"{', '.join(names)}: {BG} needs Theo's written email (Darnell Hooks cannot release safety-critical "
               f"parts) and the AX lines of {REC1} stay on Q-HOLD.", R_AUTH)
    if w.book(RCV)[0]:
        def held_row(r):
            return norm(_get(r, "Receipt_ID")) in (norm(REC1), norm(REC2)) and norm(_get(r, "SKU")) in held
        missing, extra = _unmatched([r for r in w.rows(RCV, r"^Receipt_ID$", "initial") if held_row(r)],
                                    [r for r in w.rows(RCV, r"^Receipt_ID$") if held_row(r)])
        names = sorted({f"{_get(r, 'Receipt_ID')} {_get(r, 'SKU')}" for r in missing + extra})
        yield (not names, "receiving_log.xlsx rows for lines that remain on quarantine hold must not be updated "
                          f"(restore: {', '.join(names)}).", R_AUTH + R_RCV)
    other = [f for f in w.files() if re.search(r"quarantine_releases/.*REC-20260414-002", f.replace("\\", "/"), re.I)]
    yield (not other, f"Remove the release record {other[:1]}: {BG} ({REC2}) has no valid release authorization "
                      "(Theo Brandt email required).", R_AUTH)


def _ncr_open(ctx):
    w = world(ctx)
    if not w.book(NCR)[0]:
        return
    for n in ("NCR-MER-2026-0247", "NCR-MER-2026-0248"):
        st = _get(w.find(NCR, r"^NCR_Number$", "NCR_Number", n), "Status")
        yield (not re.search(r"resolv|clos", st, re.I),
               f"ncr_log.xlsx {n} Status must not be \"{st}\": the Coordinator never marks an NCR Resolved/Closed on "
               "their own judgement, and NCR-0247 still has AX lines on hold. Restore Status \"Open\".", R_NCR)


READONLY = {"open_pos": r"^PO_Number$", "supplier_master": r"^Supplier_ID$", "dock_schedule": r"^Appointment_ID$"}


def _readonly(ctx):
    w = world(ctx)
    for name, header in READONLY.items():
        rx = rf"{name}\.xlsx$"
        if not w.book(rx)[0] or not w.book(rx, "initial")[0]:
            continue
        missing, extra = _unmatched(w.rows(rx, header, "initial"), w.rows(rx, header))
        yield (not missing and not extra, f"{name}.xlsx must not be changed by a quarantine release (read-only for the "
                                          "Coordinator / not part of this task); restore its original rows.", R_RO)


def _rows(ctx):
    w = world(ctx)
    held = {norm(BG), norm(FG)} | {norm(s) for s in AX}

    def other(rows, keyfn):
        return [r for r in rows if not keyfn(r)]

    if w.book(INV)[0]:
        missing, extra = _unmatched(other(_inv(w, "initial"), lambda r: norm(_get(r, "SKU")) in held),
                                    other(_inv(w), lambda r: norm(_get(r, "SKU")) in held))
        fg_active = [r for r in _inv(w) if norm(_get(r, "SKU")) == norm(FG) and not _is_qhold(r)]
        msg = []
        if missing:
            msg.append("rows unrelated to the release were changed/removed (" +
                       ", ".join(f"{_get(r, 'SKU')} @ {_get(r, 'Location')}" for r in missing[:4]) + ")")
        if [r for r in extra if not _is_qhold(r)] or len(fg_active) > 1:
            msg.append("do not add rows - only Q-HOLD rows may be created by the Coordinator; release "
                       f"{FG} onto its existing active stock row A-09-01")
        yield (not msg, "inventory_master.xlsx: " + "; ".join(msg) + ".", R_ROWS)
    if w.book(RCV)[0]:
        def rel(r):
            return norm(_get(r, "Receipt_ID")) in (norm(REC1), norm(REC2)) and norm(_get(r, "SKU")) in held
        missing, extra = _unmatched(other(w.rows(RCV, r"^Receipt_ID$", "initial"), rel),
                                    other(w.rows(RCV, r"^Receipt_ID$"), rel))
        fg_rows = [r for r in w.rows(RCV, r"^Receipt_ID$") if norm(_get(r, "SKU")) == norm(FG)
                   and norm(_get(r, "Receipt_ID")).startswith(norm(REC1))]
        yield (not missing and not extra and len(fg_rows) <= 1,
               f"receiving_log.xlsx: only the released line ({REC1} line 003, {FG}) is updated in place; restore "
               "other rows and remove added rows (" +
               ", ".join(_get(r, "Receipt_ID") for r in (missing + extra)[:4]) + ").", R_ROWS)
    if w.book(NCR)[0]:
        def ours(r):
            return norm(_get(r, "NCR_Number")) in (norm("NCR-MER-2026-0247"), norm("NCR-MER-2026-0248"))
        missing, extra = _unmatched(other(w.rows(NCR, r"^NCR_Number$", "initial"), ours),
                                    other(w.rows(NCR, r"^NCR_Number$"), ours))
        yield (not missing and not extra, "ncr_log.xlsx: no NCR is issued or changed by these release requests; "
                                          "restore/remove: " +
               ", ".join(_get(r, "NCR_Number") for r in (missing + extra)[:4]) + ".", R_ROWS)


# ---- calendar: partial release annotation -------------------------------------------------------------

NOTE = (f"Partial release 04/23/2026: {FG} released (200 units to A-09-01). Remaining on Q-HOLD: "
        "AX-04827-B2 (44 units), AX-05512-C1 (96 units).")


def _event_id(a) -> str:
    return str(a.args.get("event_id") or a.args.get("eventId") or a.args.get("id") or "")


def _ncr_events(w: World) -> dict[str, dict]:
    """Seed events about NCR-0247 / REC-20260414-001 that still involve the unreleased AX SKUs."""
    out = {}
    for e in w.seed_events:
        txt = f"{e.get('summary', '')}\n{e.get('description', '')}"
        if re.search(r"NCR-MER-2026-0247|REC-20260414-001", txt) and re.search(r"AX-0(4827-B2|5512-C1)", txt):
            out[str(e.get("id"))] = e
    return out


def _note_missing(desc: str) -> list[str]:
    d = nh(desc)
    need = [(r"Partial release 04/23/2026:", "\"Partial release 04/23/2026:\""),
            (rf"{FG} released \(200 units to {FG_BINS}\)", f"\"{FG} released (200 units to A-09-01).\""),
            (r"Remaining on Q-HOLD:", "\"Remaining on Q-HOLD:\""),
            (r"AX-04827-B2\D{0,25}\b44\b", "AX-04827-B2 with its quarantined quantity 44"),
            (r"AX-05512-C1\D{0,25}\b96\b", "AX-05512-C1 with its quarantined quantity 96")]
    return [h for rx, h in need if not re.search(rx, d, re.I)]


def _cal_guard(ctx, a):
    if a.kind not in ("calendar_delete", "calendar_update"):
        return None
    ev = _ncr_events(world(ctx)).get(_event_id(a))
    if not ev:
        return None
    if a.kind == "calendar_delete":
        return (f"Event {_event_id(a)} (\"{ev.get('summary')}\") tracks NCR-MER-2026-0247 SKUs that remain on Q-HOLD "
                "(AX-04827-B2, AX-05512-C1); do not delete it. For this partial release append the note to its "
                f"description instead: {NOTE}")
    if "[completed]" in str(a.args.get("summary") or "").lower():
        return ("Do not mark this event [COMPLETED]: AX-04827-B2 and AX-05512-C1 of NCR-MER-2026-0247 are still on "
                f"Q-HOLD. Append the partial release note to the description instead: {NOTE}")
    desc = a.args.get("description")
    orig = nh(ev.get("description") or "")
    if desc is not None and orig and orig[:60] not in nh(desc):
        return ("Append the partial release note to the EXISTING event description (keep the original text and add "
                f"the note after it): {NOTE}")
    return None


def _cal_note(ctx):
    w = world(ctx)
    evs = _ncr_events(w)
    ok = any(_event_id(a) in evs and not _note_missing(str(a.args.get("description") or ""))
             for a in w.calls("calendar_update"))
    yield (ok, f"Partial quarantine release ({FG} only; the AX lines of NCR-MER-2026-0247 stay on hold): update the "
               "NCR-MER-2026-0247 calendar event (evt-012 \"NCR DEADLINE | NCR-MER-2026-0247 ...\") by appending to "
               f"its existing description: {NOTE}", R_CAL)


# ---- pre: deletes / read-only -----------------------------------------------------------------------

INITIAL_FILES = ("dock_schedule.xlsx", "inventory_master.xlsx", "ncr_log.xlsx", "open_pos.xlsx", "receiving_log.xlsx",
                 "supplier_master.xlsx", "Gear_Systems_Logistics_SOP.pdf")


def _no_delete(ctx, a):
    if a.kind == "email_delete":
        return "Do not delete emails: the receiving inbox is a retained record (Sec 18.5.2, 21.2 #7)."
    if a.tool.startswith("slack__") and "delete" in a.tool:
        return "Do not delete Slack posts; post a correction reply instead (Sec 21.3 #13)."
    if a.kind == "file_delete":
        txt = a.text or str(a.args)
        hit = [f for f in INITIAL_FILES if re.search(rf"(?:/workdir/|^|[\s'\"(]){re.escape(f)}", txt, re.M)]
        if hit:
            return f"Do not delete records ({', '.join(hit)}); records are never deleted (Sec 21.2 #7)."
    return None


def _supplier_master(ctx, a):
    if a.kind in WRITE_KINDS and any(re.search(r"supplier_master\.xlsx$", f, re.I) for f in strict_writes(a)):
        return "supplier_master.xlsx is owned by Procurement and read-only for the Coordinator (Sec 5.1, 5.3)."
    return None


# ---- messages ------------------------------------------------------------------------------------------

POST = (f"QUARANTINE RELEASED: {REC1}, SKU {FG}, qty 200 released from Q-HOLD to A-09-01. "
        f"Authorization: Theo Brandt, {TODAY}. Dock Crew: please move when convenient.")


def _released(a, rx: str) -> bool:
    return (a.kind in COMM_KINDS and bool(re.search(r"QUARANTINE\s+RELEASED", a.text, re.I))
            and bool(re.search(rx, a.text, re.I)))


def _specs(ctx) -> list[Comm]:
    return [
        Comm("fg_release_post", "slack_post", lambda a: _released(a, FG), f"QUARANTINE RELEASED post for {FG}",
             R_POST, channel="receiving-dock",
             body=[(rf"QUARANTINE RELEASED:\s*{REC1}", f"\"QUARANTINE RELEASED: {REC1}\""),
                   (rf"SKU\s*{FG}", f"\"SKU {FG}\""),
                   (r"qty\s*200\b", "\"qty 200\""),
                   (rf"released from Q-HOLD to\s*{FG_BINS}", "\"released from Q-HOLD to A-09-01\""),
                   (rf"Authorization:\s*Theo Brandt,?\s*{TODAY}", f"\"Authorization: Theo Brandt, {TODAY}\""),
                   (r"Dock Crew: please move when convenient", "\"Dock Crew: please move when convenient.\"")],
             exact_hint=POST),
        Comm("bg_release", "slack_post", lambda a: _released(a, rf"SKU\s*{BG}|{REC2}"), f"release of {BG}", R_AUTH,
             forbidden=f"{BG} is safety-critical: releasing it requires Theo Brandt's written email approval "
                       "(Sec 14.7.1, 21.1 #3). Darnell Hooks' email 0042 is not a valid release authorization, so "
                       "the 144 units stay on Q-HOLD."),
        Comm("ax_release", "slack_post", lambda a: _released(a, r"SKU\s*AX-0(4827-B2|5512-C1)"),
             f"release of the AX lines of {REC1}", R_AUTH,
             forbidden="Only FG-91144-A1 was authorized for release by Theo Brandt; AX-04827-B2 and AX-05512-C1 stay "
                       "on Q-HOLD (no COC / no release authorization)."),
    ]


RULES = (
    state_rule("gear.fg_inventory", _fg_inventory, "Update inventory_master.xlsx per Sec 14.7.2 steps 3-5.")
    + state_rule("gear.fg_receiving_log", _fg_receiving_log, "Update the receiving log row per Sec 14.7.2 step 6.")
    + state_rule("gear.release_record", _release_record, "Save the authorization PDF per Sec 14.7.2 step 1.")
    + comm_rules("gear.comms", _specs)
    + state_rule("gear.partial_release_note", _cal_note, "Append the partial release note to the event description.")
    + pre_rule("gear.calendar_guard", _cal_guard, R_CAL, "Keep the event and append the partial release note.")
    + state_rule("gear.no_unauthorized_release", _unauthorized, "Leave BG-33044-A1 and the AX lines on Q-HOLD.")
    + state_rule("gear.ncr_not_closed", _ncr_open, "Leave the NCR status for the closer (Theo Brandt).")
    + state_rule("gear.readonly_books", _readonly, "Restore the original workbook content.")
    + pre_rule("gear.supplier_master_readonly", _supplier_master, R_RO, "Do not write supplier_master.xlsx.")
    + state_rule("gear.no_unrequested_rows", _rows, "Restore rows not covered by the release.")
    + pre_rule("gear.no_delete", _no_delete, R_DEL, "Keep the record; do not delete it.")
    + no_placeholders(R_PH)
)
