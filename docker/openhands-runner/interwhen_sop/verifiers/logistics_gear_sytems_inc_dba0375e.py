"""SOP verifiers for logistics_gear_sytems_inc_dba0375e (Gear Systems Meridian, SOP-LOG-MER-02 v4.2).

Situation (seed data): three Vantage Lubricants trucks arrived on 11/24/2026; the user (James Reed, JR) handles the
two hazmat receipts (REC-20261124-001/-002) and the agent processes the standard one: REC-20261124-003,
PO MER-PO-204871 line 001, FL-08814-A1 gear oil, 24 ordered / 24 on slip / 24 counted (UNLOAD COMPLETE, count match Y,
clean, no photos), standard part, non-hazmat, supplier SUP-0147 Approved (Last_Status_Change 03/14/2024).
Correct outcome: Exact / Tier 0 / Verified -> ACCEPTED CLEAN at 11/24/2026 14:21 CST, row Posted with the supplier
status notation; FL-08814-A1 is not in inventory_master.xlsx, so no row is created there and Maribel Ortiz gets the
Template 18 New SKU Setup Request; putaway post (Template 24) in #receiving-dock; no NCR, no escalation.
"""

from __future__ import annotations

import re
from collections import Counter

from ..kit import (COMM_KINDS, WRITE_KINDS, Comm, blank, comm_rules, forbid_writes, nh, no_placeholders, norm, num,
                   pre_rule, state_rule, strict_writes, world)

REC = "REC-20261124-003"
PO = "MER-PO-204871"
SKU = "FL-08814-A1"
NOW = "11/24/2026 14:21 CST"
MARIBEL_EMAIL = "maribel.ortiz@gearsystems.com"
SUPPLIER_NOTE = "Supplier status: Approved as of 03/14/2024"
INITIAL_FILES = ("Gear_Systems_Logistics_SOP.pdf", "MER-PO-204871_bol.pdf", "MER-PO-204871_packingslip.pdf",
                 "dock_schedule.xlsx", "inventory_master.xlsx", "open_pos.xlsx", "receiving_log.xlsx",
                 "supplier_master.xlsx")
ABOUT_RX = r"REC-20261124-003|MER-PO-204871|FL-08814-A1"

# ---- SOP references -----------------------------------------------------------------------------
R_RLOG = ("5.1", "receiving_log.xls", "5.1 receiving_log")
R_RW = ("5.3", "Read/write for the Coordinator: receiving_log", "5.3 file access")
R_RO = ("5.3", "Read-only for the Coordinator: supplier_master", "5.3 read-only files")
R_SUPM = ("5.1", "supplier_master.xls", "5.1 supplier_master")
R_SUP_OWN = ("15", "Supplier status is owned by Procurement", "15 supplier status ownership")
R_SUP_CHECK = ("15", "Every supplier on Gear Systems", "15 verify supplier status")
R_APPROVED = ("15.2.1", "For Approved suppliers, the Coordinator follows", "15.2.1 Approved supplier notation")
R_APPROVED2 = ("15.2.1", "This single-line notation creates an audit trail", "15.2.1 notation required")
R_COUNT = ("10.1", "The actual count is recorded in Qty_Receive", "10.1 actual count")
R_VAR = ("10.2", "Variance = Qty_Received", "10.2 variance calculation")
R_EXACT = ("10.3", "A quantity variance is considered an exact match", "10.3 auto-accept threshold")
R_QLOG = ("10.7", "For each line, the Coordinator updates the following columns", "10.7 quantity columns")
R_NODMG = ("11.1", "If the Dock Crew has reported", "11.1 no damage reported")
R_TIER0 = ("11.3", "No action beyond logging. In receiving_log.xls", "11.3 Tier 0")
R_CLOG = ("11.8", "Column Value Condition_Tie", "11.8 condition columns")
R_DOCS = ("12.1", "The following table specifies the documentation required", "12.1 required documents")
R_SLIP = ("12.2", "4. The packing slip is signed or stamped", "12.2 packing slip check")
R_BOL = ("12.3", "3. The BOL is signed by the carrier at pickup.", "12.3 BOL check")
R_DLOG = ("12.8", "Column Value Documentation_Statu", "12.8 documentation columns")
R_CONSOL = ("12.9", "After Sections 10, 11, and 12 have all been processed", "12.9 final disposition")
R_CLEAN = ("12.9", "6. ACCEPTED CLEA", "12.9 ACCEPTED CLEAN")
R_FINAL = ("13.1", "SKU The actual SKU received", "13.1 final-pass columns")
R_POSTED = ("13.1", "Once all rows for the receipt have every required column populated", "13.1 Posted")
R_NEWSKU = ("13.2", "If the SKU does not exist in inventory_master.xls", "13.2 SKU not in inventory_master")
R_ZONE = ("13.2", "d. If the SKU is new", "13.2(d) new SKU")
R_PUTAWAY = ("13.4", "Once the inventory master is updated for accepted lines", "13.4 putaway authorization")
R_T18 = ("23", "Template 18 — New SKU Confirmation Request", "Template 18")
R_T18S = ("23", "Subject: New SKU Setup Request", "Template 18 subject")
R_T24 = ("23", "Template 24 — Putaway Authorization Post", "Template 24")
R_T24L = ("23", "PUTAWAY AUTHORIZED: REC-[ID]", "Template 24 format")
R_NOESC1 = ("16.6", "Routine receipts that follow the standard procedure", "16.6 no escalation")
R_NOESC2 = ("16.6", "Tier 0 clean receipts", "16.6 Tier 0 not escalated")
R_NOESC3 = ("16.6", "Standard parts with verified documentation", "16.6 standard verified not escalated")
R_NCR = ("14.1", "Trigger Standard Parts Safety-Critical Parts", "14.1 NCR triggers")
R_DEL = ("21.2", "7. Do not delete records of any kind.", "21.2 no deletion")
R_DELMAIL = ("18.5.2", "Do not delete any email without supervisor approval", "18.5.2 no email deletion")
R_DELSLACK = ("21.3", "13. Do not delete or move a Slack post", "21.3 no Slack deletion")
R_PLACE = ("14.4.2", "3. Fill in every bracketed placeholder.", "14.4.2 placeholders")
R_PLACE2 = ("23", "This section contains every email template", "23 templates as written")
R_DOCK = ("8.1", "Column Contents Appointment_I", "8.1 dock schedule columns")
R_PROMISE = ("21.3", "14. Do not promise a supplier any specific resolution", "21.3 no promises to suppliers")


# ---- helpers ------------------------------------------------------------------------------------

def _key(v) -> str:
    """Number-tolerant cell key (an openpyxl re-save turns 8.0 into 8)."""
    s = "" if blank(v) else str(v)
    n = num(s) if s.strip() and re.fullmatch(r"[\s$+\-\d.,%]+", s) else None
    return f"#{n:.4f}" if n is not None else norm(s)


def _tuple(row: dict, cols: list[str]) -> tuple:
    return tuple(_key(row.get(c, "")) for c in cols)


def _cols(rows: list[dict], skip: tuple[str, ...] = ()) -> list[str]:
    return [k for k in (rows[0] if rows else {}) if k != "__row__" and k not in skip]


def _diff(init: list[dict], cur: list[dict], cols: list[str]) -> tuple[list[dict], list[dict]]:
    """(initial rows no longer present, current rows not in initial) - multiset, number-tolerant."""
    pool = [_tuple(r, cols) for r in cur]
    gone = []
    for r in init:
        t = _tuple(r, cols)
        if t in pool:
            pool.remove(t)
        else:
            gone.append(r)
    seen = [_tuple(r, cols) for r in init]
    added = []
    for r in cur:
        t = _tuple(r, cols)
        if t in seen:
            seen.remove(t)
        else:
            added.append(r)
    return gone, added


def _rlog(w, which="current") -> list[dict]:
    return w.rows(r"receiving_log", r"^Receipt_ID$", which)


def _rec_row(w) -> dict | None:
    return next((r for r in _rlog(w) if nh(r.get("Receipt_ID")) == REC), None)


def _val(row: dict, col: str) -> str:
    v = row.get(col)
    return "" if blank(v) else str(v).strip()


def _cell_ok(got: str, want) -> bool:
    if want is None:
        return blank(got)
    return _key(got) == _key(want)


def _field_checks(fields: list[tuple[str, object]], refs, why: str):
    def checks(ctx):
        w = world(ctx)
        row = _rec_row(w)
        if row is None:
            return [(False, f"receiving_log.xlsx has no row with Receipt_ID {REC}; restore it (do not delete or "
                            "rename it) and complete it.", refs)]
        bad = []
        for col, want in fields:
            got = _val(row, col)
            if not _cell_ok(got, want):
                bad.append(f"{col} = {'(blank)' if want is None else repr(want)} (now {got!r})")
        return [(not bad, f"receiving_log.xlsx row {REC} ({why}): set " + "; ".join(bad) + ".", refs)] if bad else []
    return checks


# ---- receiving log row REC-20261124-003 ---------------------------------------------------------

IDENTITY = [("PO_Number", PO), ("PO_Line", "001"), ("SKU", SKU), ("Safety_Critical", "N"), ("Supplier_ID", "SUP-0147"),
            ("Carrier_Name", "XPO Logistics"), ("Arrival_Timestamp", "11/24/2026 13:30 CST"), ("Dock_Door", "Dock 2"),
            ("Qty_Ordered", "24"), ("Qty_Claimed_On_Slip", "24"), ("Coordinator_Initials", "JR")]
QUANTITY = [("Qty_Received", "24"), ("Variance_Units", "0"), ("Variance_Pct", "0.0"), ("Variance_Band", "Exact"),
            ("Quantity_Action", "Accepted")]
CONDITION = [("Condition_Tier", "Tier 0"), ("Condition_Action", "Accepted"), ("Photos_Folder", "N/A")]
DOCUMENTATION = [("Documentation_Status", "Verified"), ("Documentation_Action", "Accepted"), ("Heat_Numbers", None),
                 ("COC_Filename", None), ("MTR_Filename", None)]
DISPOSITION = [("Disposition", "ACCEPTED CLEAN"), ("Disposition_Timestamp", NOW), ("NCR_Number", None)]


def _posted_checks(ctx):
    w = world(ctx)
    row = _rec_row(w)
    if row is None:
        return []
    out = []
    notes = nh(_val(row, "Notes"))
    out.append((re.search(r"Supplier status:\s*Approved as of 03/14/2024", notes, re.I) is not None,
                f"receiving_log.xlsx row {REC} Notes must record the supplier status check exactly as "
                f"\"{SUPPLIER_NOTE}\" (SUP-0147 Vantage Lubricants Inc., Last_Status_Change 03/14/2024 in "
                f"supplier_master.xlsx).", [R_APPROVED, R_APPROVED2, R_SUP_CHECK]))
    status = _val(row, "Status")
    out.append((norm(status) == "posted",
                f"receiving_log.xlsx row {REC}: once every required column is populated set Status = 'Posted' "
                f"(now {status!r}). The SKU is new to inventory_master.xlsx, which the SOP allows to be Posted "
                "while Maribel Ortiz creates the master record.", [R_POSTED, R_NEWSKU]))
    return out


# ---- invariants -----------------------------------------------------------------------------------

def _other_rlog_checks(ctx):
    w = world(ctx)
    init = _rlog(w, "initial")
    cur = _rlog(w)
    if not init:
        return []
    cols = _cols(init)
    ids_init = [nh(r.get("Receipt_ID")) for r in init]
    others_i = [r for r in init if nh(r.get("Receipt_ID")) != REC]
    others_c = [r for r in cur if nh(r.get("Receipt_ID")) != REC]
    gone, _ = _diff(others_i, others_c, cols)
    out = []
    if gone:
        ids = ", ".join(sorted({nh(r.get("Receipt_ID")) for r in gone}))
        out.append((False, f"receiving_log.xlsx rows other than {REC} were edited or removed ({ids}). The hazmat "
                           "receipts REC-20261124-001/-002 are being handled by James Reed; restore those rows "
                           "exactly as they were.", [R_RLOG, R_RW]))
    before = Counter(ids_init)
    now = Counter(nh(r.get("Receipt_ID")) for r in cur)
    extra = sorted(k or "(blank id)" for k in now if now[k] > before.get(k, 0))
    if extra:
        out.append((False, f"receiving_log.xlsx has new/duplicate rows ({', '.join(extra)}). This receipt is one PO "
                           f"line, recorded only in the existing row {REC}; remove the extra rows.",
                    [R_RLOG, R_FINAL]))
    return out


def _inventory_checks(ctx):
    w = world(ctx)
    init = w.rows(r"inventory_master", r"^SKU$", "initial")
    cur = w.rows(r"inventory_master", r"^SKU$")
    if not init:
        return []
    gone, added = _diff(init, cur, _cols(init))
    if not gone and not added:
        return []
    eg = "; ".join(f"{r.get('SKU')} @ {r.get('Location')}" for r in (added or gone)[:4])
    return [(False, f"inventory_master.xlsx must stay unchanged: {SKU} has no row there, so the Coordinator does "
                    f"not create one (or add the 24 units to another SKU such as FL-08814-A0) - Maribel Ortiz "
                    f"creates the record after the Template 18 request. Changed/added rows: {eg}. Restore the "
                    "original rows.", [R_NEWSKU])]


def _open_pos_checks(ctx):
    w = world(ctx)
    init = w.rows(r"open_pos", r"^PO_Number$", "initial")
    cur = w.rows(r"open_pos", r"^PO_Number$")
    if not init:
        return []
    gone, added = _diff(init, cur, _cols(init, skip=("Receipt_Status",)))
    if not gone and not added:
        return []
    ids = ", ".join(sorted({nh(r.get("PO_Number")) for r in gone + added}))
    return [(False, f"open_pos.xlsx is read-only for the Coordinator except the Receipt_Status column; other cells "
                    f"were changed ({ids}). Restore them.", [R_RW])]


def _dock_checks(ctx):
    w = world(ctx)
    init = w.rows(r"dock_schedule", r"^Appointment_ID$", "initial")
    cur = w.rows(r"dock_schedule", r"^Appointment_ID$")
    if not init:
        return []
    cols = _cols(init)
    core = [c for c in cols if c not in ("Status", "Actual_Departure_Time", "Special_Handling")]
    out = []
    for r in init:
        aid = nh(r.get("Appointment_ID"))
        match = [c for c in cur if nh(c.get("Appointment_ID")) == aid]
        use = cols if aid in ("APPT-20261124-001", "APPT-20261124-002") else core
        if not match or _tuple(match[0], use) != _tuple(r, use):
            what = "the hazmat appointments are James Reed's" if use is cols else \
                "only Status / Actual_Departure_Time / Special_Handling may change"
            out.append((False, f"dock_schedule.xlsx row {aid} was changed or removed ({what}); restore the original "
                               "values.", [R_DOCK, R_RW]))
    if len(cur) > len(init):
        out.append((False, "dock_schedule.xlsx has new rows; no new appointment is needed for these on-time "
                           "arrivals. Remove them.", [R_DOCK, R_RW]))
    return out


# ---- messages -------------------------------------------------------------------------------------

T18_HINT = (f"Template 18 to Maribel Ortiz (Slack DM, or email to {MARIBEL_EMAIL} with subject "
            f"\"New SKU Setup Request — {REC} — {SKU}\"): Receipt ID: {REC}; PO Number: {PO}; Supplier: Vantage "
            f"Lubricants Inc.; SKU: {SKU}; SKU description: Gear oil, ISO VG 220, 20L drum; Quantity received: 24; "
            "Safety-Critical: N; Suggested location (FL- prefix -> Zone C, C-RCV-01)")
T18_BODY = [(re.escape(REC), f"Receipt ID {REC}"), (re.escape(PO), f"PO Number {PO}"),
            (r"Vantage Lubricants", "Supplier: Vantage Lubricants Inc."), (re.escape(SKU), f"SKU {SKU}"),
            (r"(quantity|qty)[^\n]{0,25}?\b24\b", "Quantity received: 24"),
            (r"safety[- ]critical\W{0,3}(N|No)\b", "Safety-Critical: N")]
T18_REFS = [R_NEWSKU, R_T18, R_T18S]

PUTAWAY_RX = (r"PUTAWAY PENDING: REC-20261124-003|"
              r"PUTAWAY AUTHORIZED: REC-20261124-003, Vantage Lubricants Inc\.?, 1 lines?\.?.*?"
              r"Line 001: FL-08814-A1, 24 units\s*(→|->|to)\s*\S.*?Coordinator: JR")
PUTAWAY_TEXT = (f"PUTAWAY AUTHORIZED: {REC}, Vantage Lubricants Inc., 1 lines.\n"
                f"- Line 001: {SKU}, 24 units → [Location]\nCoordinator: JR")


def _specs(ctx) -> list[Comm]:
    w = world(ctx)

    def t18(a) -> bool:
        return bool(re.search(r"FL-08814-A1|new sku", f"{a.subject}\n{a.text}", re.I))

    def dm_maribel(a) -> bool:
        return a.kind in ("slack_dm", "slack_post") and w.is_dm_to(a, "Maribel Ortiz") and t18(a)

    def mail_maribel(a) -> bool:
        return a.kind in ("email_send", "email_draft") and MARIBEL_EMAIL in a.recipients + a.cc and t18(a)

    def putaway(a) -> bool:
        return a.kind == "slack_post" and not w.dm_recipients(a) and bool(
            re.search(r"PUTAWAY", a.text) and REC in a.text)

    return [
        Comm("t18_dm", "slack_dm", dm_maribel, "Template 18 New SKU Setup Request to Maribel Ortiz", T18_REFS,
             to=["Maribel Ortiz"], body=T18_BODY, required=False),
        Comm("t18_email", "email", mail_maribel, "Template 18 New SKU Setup Request to Maribel Ortiz", T18_REFS,
             to=[MARIBEL_EMAIL], exact_to=False, subject=r"New SKU Setup Request [–-] REC-20261124-003 [–-] FL-08814-A1",
             subject_hint=f"New SKU Setup Request — {REC} — {SKU}", body=T18_BODY, required=False),
        Comm("putaway", "slack_post", putaway, "Template 24 putaway authorization post for REC-20261124-003",
             [R_PUTAWAY, R_T24, R_T24L, R_ZONE], channel="receiving-dock",
             body=[(PUTAWAY_RX, f"the Template 24 text, i.e. \"{PUTAWAY_TEXT}\" (or a holding post "
                                f"\"PUTAWAY PENDING: {REC}, full authorization to follow within [N] minutes\")")],
             banned=[(r"Line 001:[^\n]*Q-HOLD", "This receipt is ACCEPTED CLEAN; its destination is not Q-HOLD.")],
             max_count=2),
    ]


def _t18_done(ctx):
    w = world(ctx)
    specs = [c for c in _specs(ctx) if c.key.startswith("t18")]
    ok = any(c.about(a) and not c.problems(a, w) for c in specs for a in w.comms())
    return [(ok, f"{SKU} does not exist in inventory_master.xlsx: send the {T18_HINT}.", T18_REFS)]


def _escalation(ctx, a):
    if a.kind not in ("slack_post", "slack_dm", "email_send"):
        return None
    if not re.search(ABOUT_RX, f"{a.subject}\n{a.text}"):
        return None
    w = world(ctx)
    if a.kind == "slack_post" and not w.dm_recipients(a) and w.is_channel(a.channel, "escalations-meridian"):
        return (f"[no-escalation] {REC} is a routine Tier 0 / Exact / Verified standard receipt ($924.00); the SOP "
                "says such receipts are not escalated, so do not post it in #escalations-meridian.")
    who = [p for p in ("Elizabeth Velasquez", "Walter Finch") if w.is_dm_to(a, p)]
    rcpt = {x.lower() for x in a.recipients + a.cc}
    who += [n for n, e in (("Elizabeth Velasquez", "elizabeth.velasquez@gearsystems.com"),
                           ("Walter Finch", "walter.finch@gearsystems.com")) if e in rcpt]
    if who:
        return (f"[no-escalation] {REC} is a routine clean standard receipt ($924.00, below every escalation "
                f"threshold); do not escalate it to {', '.join(sorted(set(who)))}. (If genuinely unsure, the SOP's "
                "uncertainty escalation goes to Darnell Hooks.)")
    return None


def _ncr(ctx, a):
    if a.kind not in COMM_KINDS:
        return None
    t = f"{a.subject}\n{a.text}"
    if re.search(ABOUT_RX, t) and re.search(r"NCR-MER-\d|Nonconformance Report|NONCONFORMANCE REPORT", t):
        return (f"[no-ncr] No NCR applies to {REC}: exact quantity, Tier 0 condition and verified standard "
                "documentation trigger no NCR in the Section 14.1 table. Do not issue one.")
    return None


def _no_delete(ctx, a):
    if a.kind == "email_delete":
        return "[no-delete] Emails in the receiving inbox are records; do not delete them (move/file them instead)."
    if "slack" in a.tool and "delete" in a.tool.lower():
        return "[no-delete] Slack history is part of the audit trail; do not delete posts (post a correction reply)."
    if not (a.deletes or a.kind == "file_delete"):
        return None
    blob = f"{a.text}\n{a.args}"
    hit = [f for f in INITIAL_FILES if f in blob]
    if not hit:
        return None
    if a.kind == "file_delete" and a.tool not in ("syntara__executePython", "syntara__executeBash"):
        return f"[no-delete] {', '.join(hit)}: records may never be deleted."
    if re.search(r"\.delete_rows\(", blob):
        return (f"[no-delete] Deleting workbook rows ({', '.join(hit)}) destroys records; correct by adding rows or "
                "restoring values instead.")
    for f in hit:
        if re.search(rf"(?:remove|unlink|rmtree)\([^)\n]*{re.escape(f)}|(?:^|[;&|\s])rm\s[^;&|\n]*{re.escape(f)}",
                     blob):
            return f"[no-delete] {f}: records may never be deleted."
    return None


def _promise(ctx, a):
    if a.kind not in ("email_send", "email_draft"):
        return None
    if not any(x.endswith("@vantagelube.com") for x in a.recipients + a.cc):
        return None
    m = re.search(r"\bwe (?:will|can|'ll)\s+(?:issue\s+(?:you\s+)?(?:a\s+)?)?(?:credit|refund|replace|rework|expedite|"
                  r"adjust (?:the )?pric\w*|authori[sz]e (?:a |the )?return)", a.text, re.I)
    if m:
        return (f"[no-promise] \"{m.group(0)}\": the Coordinator never promises a supplier a resolution (credit, "
                "rework, return authorization, replacement, pricing) - that is Procurement's or Quality's call.")
    return None


def _inventory_write(ctx, a):
    if a.kind not in WRITE_KINDS:
        return None
    if any(re.search(r"inventory_master\.xlsx", f, re.I) for f in strict_writes(a)):
        return (f"[inventory] Do not write inventory_master.xlsx: {SKU} has no row there and the Coordinator must not "
                "create one (nor add the units to FL-08814-A0 or any other row). Send Maribel Ortiz the Template 18 "
                "New SKU Setup Request instead. (If this call does not save inventory_master.xlsx, save each "
                "workbook through a literal file path so the write target is unambiguous.)")
    return None


RULES = (
    no_placeholders([R_PLACE, R_PLACE2])
    + comm_rules("comms", _specs)
    + pre_rule("receipt003.no_escalation", _escalation, [R_NOESC1, R_NOESC2, R_NOESC3],
               "Do not escalate this routine receipt.")
    + pre_rule("receipt003.no_ncr", _ncr, [R_NCR], "Do not issue an NCR for this receipt.")
    + pre_rule("records.no_delete", _no_delete, [R_DEL, R_DELMAIL, R_DELSLACK], "Do not delete records.")
    + pre_rule("comms.no_supplier_promise", _promise, [R_PROMISE], "Remove the promise; route resolution to Procurement.")
    + pre_rule("inventory.no_new_sku_row", _inventory_write, [R_NEWSKU], "Leave inventory_master.xlsx unchanged.")
    + forbid_writes("supplier_master.readonly", r"supplier_master\.xlsx",
                    "supplier_master.xlsx is owned by Procurement and read-only for the Coordinator.",
                    [R_RO, R_SUPM, R_SUP_OWN])
    + state_rule("receipt003.new_sku_request", _t18_done, "Send the Template 18 request as described.")
    + state_rule("receipt003.identity", _field_checks(IDENTITY, [R_FINAL], "PO-match fields must stay as logged"),
                 "Restore the PO-match fields.")
    + state_rule("receipt003.quantity", _field_checks(QUANTITY, [R_COUNT, R_VAR, R_EXACT, R_QLOG],
                                                     "Section 10: 24 ordered, 24 counted -> Exact"),
                 "Fill the quantity columns as listed.")
    + state_rule("receipt003.condition", _field_checks(CONDITION, [R_NODMG, R_TIER0, R_CLOG],
                                                      "Section 11: clean unload, no photos -> Tier 0"),
                 "Fill the condition columns as listed.")
    + state_rule("receipt003.documentation", _field_checks(DOCUMENTATION, [R_DOCS, R_SLIP, R_BOL, R_DLOG],
                                                          "Section 12: standard part, slip + BOL verified"),
                 "Fill the documentation columns as listed.")
    + state_rule("receipt003.disposition", _field_checks(DISPOSITION, [R_CONSOL, R_CLEAN, R_FINAL],
                                                        f"Section 12.9: ACCEPTED CLEAN, decided now ({NOW})"),
                 "Fill the disposition columns as listed.")
    + state_rule("receipt003.posted", _posted_checks, "Complete the Notes/Status as listed.")
    + state_rule("receiving_log.no_unrequested_writes", _other_rlog_checks, "Restore the other rows.")
    + state_rule("inventory.unchanged", _inventory_checks, "Restore inventory_master.xlsx.")
    + state_rule("open_pos.readonly", _open_pos_checks, "Restore open_pos.xlsx.")
    + state_rule("dock_schedule.unchanged", _dock_checks, "Restore dock_schedule.xlsx.")
)
