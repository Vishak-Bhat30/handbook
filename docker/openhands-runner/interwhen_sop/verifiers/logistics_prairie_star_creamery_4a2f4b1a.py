"""Prairie Star Creamery (Houston DC), 2026-04-15 13:00 - finish this morning's inbound processing.

Seed facts: Waco manifest 2026-04-15-001 dock report (seal intact, temps -10.2/-10.2/-18.7, reported avg -12.37 is
wrong -> -13.03, 210/210 cases, SC-003 lot A-20260411-01 received vs A-20260412-01 on the manifest, no damage);
manifest 2026-04-15-002 (10:30) has no dock report yet (3-hour follow-up window ends 13:30); vendor deliveries
DRY-02 PO 67204 (10:00, no dock report after 3 hours) and PAL-01 PO 11587 (13:00) still need pre-arrival rows.
No put-away confirmation has been posted, so inventory_master and temperature_log are not updated yet (12.6).
"""

from __future__ import annotations

import re
from datetime import date

from ..kit import (Comm, World, blank, comm_rules, dashes, nh, no_placeholders, norm, num, pre_rule, same,
                   state_rule, world)

TODAY = date(2026, 4, 15)
M1, M2 = "2026-04-15-001", "2026-04-15-002"
LOT_RECV, LOT_MAN = "A-20260411-01", "A-20260412-01"
RLOG, RHDR = r"inbound_receiving_log", r"Manifest / PO"
JACOB, CARLOS = "jacob.patel@prairiestar.com", "carlos.mendoza@prairiestar.com"

# refs
R_SUBJ = ("1.7", "Email Subject Line Format:", "1.7 Email subject line format")
R_LOT = ("2.6", "The lot code is printed on the case", "2.6 Lot code verification")
R_FILES = ("4", "The following files are the Analyst", "4 Files and Systems")
R_MAN_RO = ("4", "transfer_manifests/ — Folder of PDFs.", "4 transfer_manifests (read-only)")
R_PO_RO = ("4", "vendor_pos/ — Folder of PDFs.", "4 vendor_pos (read-only)")
R_VM = ("4", "vendor_master.xlsx — Outside vendor directory.", "4 vendor_master.xlsx")
R_VS = ("4", "vendor_scorecard.xlsx — Vendor performance tracking.", "4 vendor_scorecard.xlsx")
R_P3_SLACK = ("5.3", "Slack post to relevant channel", "5.3 P3 notification")
R_P3_LOG = ("5.3", "Update receiving log with P3 notation", "5.3 P3 receiving-log notation")
R_P3_STATUS = ("5.3", "Log entry in receiving log with", "5.3 P3 status")
R_ROUND = ("6.1", "5. Decimal readings:", "6.1 Decimal readings")
R_TIER1 = ("6.2", "Tier 1 | ≤ -10°F", "6.2 Tier 1")
R_EXACT = ("7.2", "0 cases | 0% | Exact Match", "7.2 Exact Match")
R_MISMATCH = ("12.5", "Mismatch (e.g., manifest shows one lot code", "12.5 Lot code mismatch")
R_RLOG = ("12.6", "inbound_receiving_log.xlsx: Fill in all temperature readings", "12.6 Receiving log update")
R_EXP = ("12.6", "expiry_tracker.xlsx : Add a row for each valid lot code", "12.6 Expiry tracker update")
R_TEMP = ("12.6", "temperature_log.xlsx: Complete upon confirmation of put-away", "12.6 Temperature log update")
R_INV = ("12.6", "inventory_master.xlsx : Complete upon confirmation of put-away", "12.6 Inventory master update")
R_KEEP_OPEN = ("12.8", "Do not close if items remain pending.", "12.8 Do not close while pending")
R_PREFILL = ("13.1", "3. Pre-fill one row in inbound_receiving_log.xlsx", "13.1 Vendor pre-arrival row")
R_FEFO = ("15.2", "1. After put-away confirmation", "15.2 Inventory master after put-away")
R_RECON = ("20.3", "2. Verify all expected inbound has arrived", "20.3 Reconciliation")
R_TPL = ("22", "The following email templates are referenced", "22 Email templates")


def _d10(v) -> str:
    """Date cell as YYYY-MM-DD (datetime cells dump as 'YYYY-MM-DD 00:00:00')."""
    s = str(v or "").strip()
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else s[:10]


def _rlog(w: World, which: str = "current") -> list[dict]:
    return w.rows(RLOG, RHDR, which)


def _receipt(w: World, ref_rx: str) -> dict | None:
    return next((r for r in _rlog(w) if re.fullmatch(ref_rx, nh(w.col(r, r"Manifest / PO")), re.I)), None)


# ---- messages ------------------------------------------------------------------------------------

def _specs(ctx) -> list[Comm]:
    w = world(ctx)
    alicia = w.uids("Alicia Nguyen")

    def mismatch_email(a) -> bool:
        if a.kind != "email_send":
            return False
        t = f"{a.subject}\n{a.text}"
        return "LOT CODE MISMATCH" in t or (JACOB in a.recipients + a.cc and re.search(r"mismatch", t, re.I)
                                            and (M1 in t or LOT_RECV in t))

    def p3_post(a) -> bool:
        return (a.kind == "slack_post" and not w.dm_recipients(a)
                and (w.is_channel(a.channel, "waco-production-coord") or w.is_channel(a.channel, "receiving-houston"))
                and bool(re.match(r"\s*P3\b", a.text or "") or re.search(r"P3\s+Issue\s+Noted", a.text or "", re.I)))

    def overdue_dm(a) -> bool:
        return a.kind in ("slack_dm", "slack_post") and bool(w.dm_recipients(a) & alicia) and "67204" in (a.text or "")

    return [
        Comm("lot_mismatch_email", "email", mismatch_email,
             f"lot code mismatch email for manifest {M1} (12.5: Production Planner, cc DC Manager)",
             [R_MISMATCH, R_LOT, R_SUBJ], to=[JACOB], cc=[CARLOS], exact_to=False,
             subject=rf"P3 – .+ – .*{M1} – 2026-04-15",
             subject_hint=f"P3 – Lot Code Mismatch – Inbound Waco Manifest {M1} – 2026-04-15",
             body=[(rf"LOT CODE MISMATCH\s*[-–—]+\s*(Manifest\s*)?{M1}\s*[-–—]+.{{0,60}}?manifest\s+(lot\s+)?"
                    rf"{LOT_MAN}\s*,?\s*vs\.?\s+received\s+(lot\s+)?{LOT_RECV}",
                    f"\"LOT CODE MISMATCH – {M1} - manifest {LOT_MAN} vs received {LOT_RECV}.\""),
                   (r"Hold receipt open pending clarification", "\"Hold receipt open pending clarification.\"")]),
        Comm("p3_slack", "slack_post", p3_post,
             f"P3 Slack notice for the {M1} lot code mismatch (#waco-production-coord or #receiving-houston)",
             [R_P3_SLACK, R_MISMATCH], channel=None,
             body=[(rf"^\s*P3 Issue Noted!\s*[-–—]+\s*(Manifest\s*)?(#\s*)?{M1}\s*[-–—]+\s*\S",
                    f"the SOP format \"P3 Issue Noted! – {M1} – Lot code mismatch: manifest {LOT_MAN} vs received "
                    f"{LOT_RECV}\" (post in #waco-production-coord)"),
                   (r"mismatch|lot code", "a description of the issue (lot code mismatch)")]),
        Comm("overdue_dm_67204", "slack_dm", overdue_dm,
             "overdue-delivery DM to @a.nguyen for DRY-02 PO 67204 (scheduled 10:00, no dock report after 3 hours; "
             "Analyst Notice IN-2026-001 §1)",
             [R_RECON], to=["Alicia Nguyen"],
             body=[(r"^\s*Hi Alicia\b", "the notice wording starting \"Hi Alicia — \""),
                   (r"PO\s*#?\s*67204\b.{0,80}?was scheduled for 10(:00|\s*a\.?m\.?)",
                    "\"PO 67204 was scheduled for 10:00\""),
                   (r"haven[’'`]?t received a dock report", "\"I haven't received a dock report\""),
                   (r"Can you confirm status or ETA", "\"Can you confirm status or ETA?\"")]),
    ]


def _broadcast(ctx, a):
    if a.kind in ("slack_post", "slack_dm") and re.search(r"@channel|@here|<!channel>|<!here>", a.text or "", re.I):
        return "[@channel/@here] Do not use @channel or @here unless it is a P1 event (none today)."
    return None


# ---- receiving log -------------------------------------------------------------------------------

def _m1_checks(ctx):
    w = world(ctx)
    r = _receipt(w, M1)
    if not r:
        yield False, f"inbound_receiving_log.xlsx: the row for manifest {M1} is missing.", [R_RLOG]
        return
    c = lambda rx: w.col(r, rx)
    want = [("Total Cases (Actual)", r"Total Cases \(Actual", 210, [R_RLOG]),
            ("Temp Front (°F)", r"Temp Front", -10.2, [R_RLOG]),
            ("Temp Middle (°F)", r"Temp Middle", -10.2, [R_RLOG]),
            ("Temp Rear (°F)", r"Temp Rear", -18.7, [R_RLOG]),
            ("Variance (Cases)", r"Variance \(Cases", 0, [R_EXACT]),
            ("Variance %", r"Variance %", 0, [R_EXACT]),
            ("Variance Class", r"Variance Class", "Exact Match", [R_EXACT])]
    for label, rx, val, refs in want:
        yield same(c(rx), val), f"Receiving log {M1}: '{label}' must be {val} (got '{c(rx)}').", refs
    avg = num(c(r"Temp Avg"))
    yield (avg is not None and abs(avg - (-39.1 / 3)) < 0.04,
           f"Receiving log {M1}: 'Temp Avg (°F)' must be the verified average -13.03 (the dock crew's -12.37 is "
           f"wrong; (-10.2 + -10.2 + -18.7) / 3 = -13.03) (got '{c(r'Temp Avg')}').", [R_RLOG])
    yield (bool(re.fullmatch(r"tier\s*1", norm(c(r"Temp Tier")))),
           f"Receiving log {M1}: 'Temp Tier' must be 'Tier 1' (warmest reading -10.2°F rounds to -10°F) "
           f"(got '{c(r'Temp Tier')}').", [R_TIER1, R_ROUND])
    lots = dashes(c(r"Lot Codes"))
    ok = (bool(re.search(rf"{LOT_RECV}.{{0,40}}?--?\s*MISMATCH\s*[-–—]+\s*manifest\s+{LOT_MAN}\s+vs\.?\s+received\s+"
                         rf"{LOT_RECV}", lots, re.S)) and "A-20260410-01" in lots and "B-20260408-01" in lots)
    yield (ok, f"Receiving log {M1}: 'Lot Codes' must list A-20260410-01 and B-20260408-01 and record the mismatch "
               f"as \"{LOT_RECV} -- MISMATCH – manifest {LOT_MAN} vs received {LOT_RECV}.\" (got '{nh(lots)}').",
           [R_MISMATCH])
    yield (nh(c(r"Damage Notes")).rstrip() == "No damage",
           f"Receiving log {M1}: 'Damage Notes' must be exactly 'No damage' (Analyst Notice IN-2026-001 §2) "
           f"(got '{c(r'Damage Notes')}').", [R_RLOG])
    yield (bool(re.match(r"p3\b", norm(c(r"^Priority")))),
           f"Receiving log {M1}: 'Priority' must be 'P3' (lot code mismatch) (got '{c(r'^Priority')}').",
           [R_MISMATCH, R_P3_LOG])
    yield (nh(c(r"^Disposition")) == "Open",
           f"Receiving log {M1}: 'Disposition' must be exactly 'Open' - the receipt is held open pending lot "
           f"clarification (Analyst Notice IN-2026-001 §2 allows only Accepted/Open/Quarantined/Rejected) "
           f"(got '{c(r'^Disposition')}').", [R_MISMATCH, R_RLOG])
    st = norm(c(r"^Status"))
    yield (bool(re.search(r"open|^p3", st)) and "closed" not in st,
           f"Receiving log {M1}: 'Status' must keep the receipt open for the P3 lot mismatch, e.g. "
           f"'Open – Pending Lot Code Clarification' or 'P3 – Lot code mismatch' (got '{c(r'^Status')}').",
           [R_MISMATCH, R_KEEP_OPEN, R_P3_STATUS])


def _m2_checks(ctx):
    w = world(ctx)
    r = _receipt(w, M2)
    if not r:
        yield False, f"inbound_receiving_log.xlsx: the pre-filled row for manifest {M2} is missing.", [R_RLOG]
        return
    cols = [(r"Total Cases \(Actual", "Total Cases (Actual)"), (r"Temp Front", "Temp Front"),
            (r"Temp Middle", "Temp Middle"), (r"Temp Rear", "Temp Rear"), (r"Temp Avg", "Temp Avg"),
            (r"Variance \(Cases", "Variance (Cases)"), (r"Lot Codes", "Lot Codes")]
    filled = [lab for rx, lab in cols if not (blank(w.col(r, rx)) or norm(w.col(r, rx)) == "pending")]
    yield (not filled, f"Receiving log {M2}: no dock report has been received for this manifest, so its receiving "
                       f"data must stay 'Pending' (filled: {', '.join(filled)}).", [R_RLOG])


VENDORS = [("67204", "DRY-02", r"lone star toppings", "Lone Star Toppings Co.", 45),
           ("11587", "PAL-01", r"texpal", "TexPal Logistics", 50)]
XNA = r"(x|n/?a)\b.*"


def _vendor_checks(ctx):
    w = world(ctx)
    perf = {norm(w.col(r, r"Vendor Code")): nh(w.col(r, r"Performance Notes"))
            for r in w.rows(r"vendor_master", r"Vendor Code", "initial")}
    for po, code, origin_rx, origin, qty in VENDORS:
        r = _receipt(w, rf"(PO[\s#:-]*)?{po}")
        notes = perf.get(norm(code), "")
        hint = (f"Receipt Date 2026-04-15, Manifest / PO # '{po}', Origin '{origin}', Total Cases (Manifest) {qty}, "
                f"Total Pallets/Temp columns/Lot Codes 'N/A', Status 'Pre-arrival', Notes '{notes}', "
                f"other columns 'Pending'")
        if not r:
            yield False, f"inbound_receiving_log.xlsx: no pre-arrival row for {code} PO {po}. Add one: {hint}.", [R_PREFILL]
            continue
        c = lambda rx: w.col(r, rx)
        bad = []
        if _d10(c(r"Receipt Date")) != "2026-04-15":
            bad.append(f"Receipt Date 2026-04-15 (got '{c(r'Receipt Date')}')")
        if not re.search(origin_rx, norm(c(r"^Origin"))):
            bad.append(f"Origin '{origin}' (got '{c(r'^Origin')}')")
        if not same(c(r"Total Cases \(Manifest"), qty):
            bad.append(f"Total Cases (Manifest) {qty} (got '{c(r'Total Cases .Manifest')}')")
        for rx, label in [(r"Total Pallets", "Total Pallets (Manifest)"), (r"Temp Front", "Temp Front (°F)"),
                          (r"Temp Middle", "Temp Middle (°F)"), (r"Temp Rear", "Temp Rear (°F)"),
                          (r"Temp Avg", "Temp Avg (°F)"), (r"Temp Tier", "Temp Tier"), (r"Lot Codes", "Lot Codes")]:
            if not re.fullmatch(XNA, norm(c(rx))):
                bad.append(f"{label} 'X' or 'N/A' (got '{c(rx)}')")
        if not re.fullmatch(r"pre[-\s]?arrival\.?", norm(c(r"^Status"))):
            bad.append(f"Status 'Pre-arrival' (got '{c(r'^Status')}')")
        if notes and norm(notes).rstrip(".") not in norm(c(r"^Notes")):
            bad.append(f"Notes containing the vendor_master Performance Notes '{notes}'")
        for rx, label in [(r"Total Cases \(Actual", "Total Cases (Actual)"), (r"Variance \(Cases", "Variance (Cases)"),
                          (r"Variance %", "Variance %"), (r"Variance Class", "Variance Class"),
                          (r"Damage Class", "Damage Class"), (r"Damage Notes", "Damage Notes"),
                          (r"^Priority", "Priority")]:
            if norm(c(rx)) != "pending":
                bad.append(f"{label} 'Pending' (got '{c(rx)}')")
        yield (not bad, f"Receiving log pre-arrival row for {code} PO {po} needs: " + "; ".join(bad) + ".", [R_PREFILL])


def _history_checks(ctx):
    w = world(ctx)
    gone = [r for r in w.missing_rows(RLOG, RHDR) if nh(w.col(r, r"Manifest / PO")) not in (M1, M2)]
    yield (not gone, "inbound_receiving_log.xlsx: earlier receipts are a record and must not be edited or removed "
                     f"({', '.join(nh(w.col(r, r'Manifest / PO')) for r in gone)}). Restore them.", [R_FILES])
    refs = [nh(w.col(r, r"Manifest / PO")) for r in _rlog(w)]
    dup = sorted({x for x in refs if refs.count(x) > 1})
    yield not dup, f"inbound_receiving_log.xlsx: one row per inbound shipment - duplicate rows for {dup}.", [R_RLOG]


# ---- expiry tracker / inventory master / temperature log ----------------------------------------

LOTS = [("SC-001", "Sweet Cream Prairie", "A-20260410-01", "H-A", "2026-04-10", 18, "2027-10-10", 100),
        ("SP-001", "Lavender Cream Moonrise", "B-20260408-01", "H-B", "2026-04-08", 15, "2027-07-08", 30)]
EXP, EHDR = r"expiry_tracker", r"^Lot Code$"


def _expiry_checks(ctx):
    w = world(ctx)
    rows = w.rows(EXP, EHDR)
    for sku, name, lot, zone, prod, life, exp, qty in LOTS:
        hit = [r for r in rows if norm(w.col(r, r"^Lot Code")) == norm(lot)]
        hint = (f"SKU {sku}, Product Name {name}, Lot Code {lot}, Zone {zone}, Received Date 2026-04-15, Production "
                f"Date {prod}, Shelf Life {life}, Expiry Date {exp}, Days Remaining {(date.fromisoformat(exp) - TODAY).days}, "
                f"Tier Green, Quantity {qty}, Monitor Status 'Monitored'")
        if not hit:
            yield False, f"expiry_tracker.xlsx: add a row for valid lot {lot} ({hint}).", [R_EXP]
            continue
        r = hit[0]
        c = lambda rx: w.col(r, rx)
        bad = [f"{lab} {v} (got '{c(rx)}')" for lab, rx, v in
               [("SKU", r"^SKU", sku), ("Zone", r"^Zone", zone), ("Quantity", r"Quantity", qty),
                ("Shelf Life", r"Shelf Life", life), ("Tier", r"^Tier", "Green"),
                ("Monitor Status", r"Monitor Status", "Monitored")] if not same(c(rx), v)]
        bad += [f"{lab} {v} (got '{c(rx)}')" for lab, rx, v in
                [("Received Date", r"Received Date", "2026-04-15"), ("Production Date", r"Production Date", prod),
                 ("Expiry Date", r"Expiry Date", exp)] if _d10(c(rx)) != v]
        if len(hit) > 1:
            bad.append("only one row per lot")
        yield not bad, f"expiry_tracker.xlsx row for lot {lot} needs: " + "; ".join(bad) + ".", [R_EXP]
    bad_lot = [nh(w.col(r, r"^Lot Code")) for r in rows if re.search(rf"{LOT_RECV}|{LOT_MAN}", w.col(r, r"^Lot Code"))]
    yield (not bad_lot, f"expiry_tracker.xlsx: do NOT add a row for the mismatched SC-003 lot ({', '.join(bad_lot)}) "
                        "while the lot code mismatch is unresolved. Remove it.", [R_EXP])
    gone = w.missing_rows(EXP, EHDR)
    yield (not gone, "expiry_tracker.xlsx: existing lots must not be edited or removed "
                     f"({', '.join(nh(w.col(r, r'^Lot Code')) for r in gone)}). Restore them.", [R_FILES])
    known = {norm(x[2]) for x in LOTS} | {norm(LOT_RECV), norm(LOT_MAN)}
    extra = [nh(w.col(r, r"^Lot Code")) for r in w.new_rows(EXP, EHDR) if norm(w.col(r, r"^Lot Code")) not in known]
    yield (not extra, f"expiry_tracker.xlsx: rows added for lots not received today ({', '.join(extra)}). "
                      "Only today's valid lots A-20260410-01 and B-20260408-01 are added.", [R_EXP])


def _inventory_checks(ctx):
    w = world(ctx)
    hdr = r"^Lot Code$"
    new = [nh(w.col(r, r"^Lot Code")) or nh(w.col(r, r"^SKU")) for r in w.new_rows(r"inventory_master", hdr)]
    gone = [nh(w.col(r, r"^Lot Code")) for r in w.missing_rows(r"inventory_master", hdr)]
    yield (not new, "inventory_master.xlsx: no put-away confirmation has been received via Slack for today's "
                    f"receipts, so no lots may be added yet (added: {', '.join(new)}); the mismatched lot "
                    f"{LOT_RECV} is never added while unresolved. Remove the added rows.", [R_INV, R_FEFO])
    yield (not gone, f"inventory_master.xlsx: existing rows were edited or removed ({', '.join(gone)}). Restore them.",
           [R_FILES])


def _temperature_checks(ctx):
    w = world(ctx)
    hdr = r"^Zone$"
    new = [f"{nh(w.col(r, r'^Date'))} {nh(w.col(r, r'^Zone'))}" for r in w.new_rows(r"temperature_log", hdr)]
    gone = w.missing_rows(r"temperature_log", hdr)
    yield (not new, "temperature_log.xlsx: the inbound readings are logged only upon put-away confirmation via Slack, "
                    f"which has not been received (added: {'; '.join(new)}). Remove the added rows.", [R_TEMP])
    yield not gone, "temperature_log.xlsx: existing readings were edited or removed. Restore them.", [R_FILES]


def _other_files(ctx):
    w = world(ctx)
    changed = w.changed_files(r"inbound_receiving_log|expiry_tracker|inventory_master|temperature_log")
    yield (not changed, f"{', '.join(changed)}: no SOP step today changes these files (no vendor receipt has been "
                        "processed, no vendor details changed). Restore them.", [R_VM, R_VS])
    created = w.created_books()
    yield (not created, f"New workbooks {created}: do not create personal copies or informal tracking documents - "
                        "record work only in the official files.", [R_FILES])
    missing = [f for f in ("transfer_manifests.zip", "vendor_pos.zip") if not w.has_file(re.escape(f) + "$")]
    yield not missing, f"Reference documents {missing} were removed; they are read-only.", [R_MAN_RO, R_PO_RO]


RULES = (
    comm_rules("comms", _specs)
    + pre_rule("comms.no_broadcast", _broadcast, [R_SUBJ], "Remove @channel / @here and tag the relevant people.")
    + no_placeholders([R_TPL])
    + state_rule("receiving.manifest_001", _m1_checks, "Update the 2026-04-15-001 row of inbound_receiving_log.xlsx.")
    + state_rule("receiving.manifest_002", _m2_checks, "Leave the 2026-04-15-002 receiving data as 'Pending'.")
    + state_rule("receiving.vendor_prearrival", _vendor_checks, "Pre-fill the vendor rows in inbound_receiving_log.xlsx.")
    + state_rule("receiving.history", _history_checks, "Restore the earlier receiving-log rows.")
    + state_rule("expiry.lots", _expiry_checks, "Fix expiry_tracker.xlsx as listed.")
    + state_rule("inventory.put_away_pending", _inventory_checks, "Restore inventory_master.xlsx.")
    + state_rule("temperature.put_away_pending", _temperature_checks, "Restore temperature_log.xlsx.")
    + state_rule("files.unrequested", _other_files, "Restore those files.")
)
