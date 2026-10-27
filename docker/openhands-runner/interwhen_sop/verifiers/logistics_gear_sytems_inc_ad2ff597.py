"""Verifiers for logistics_gear_sytems_inc_ad2ff597 (Gear Systems Meridian, SOP-LOG-MER-02).

Situation (seed data, 03/12/2026 10:15): REC-20260312-001 / APPT-20260312-001 / MER-PO-103517 from Redstone Alloy
Fabricators, Inc. (SUP-0010, Approved) is a hazmat load (FL-20044-A3 gear oil, 80 pails, UN1270 Class 3). Manifest
is on file and Curtis confirmed DOT labels, but the SDS (FL-20044-A3_SDS.pdf) is missing -> Section 17.1.2 step 2:
do not unload, TRUCK HOLD post, DM Darnell + Chris (EHS), and per the 16.2.1 override also Elizabeth; wait for
written guidance. The user holds off on the NCR letter.
Closed POs this week: MER-PO-103515 / REC-20260309-004 is logged with SKU FL-20044-A3 but the PO, packing slip,
SDS and inventory show FL-21300-A1 -> cross-shift correction request to Maribel (13.6.1, never edit the row);
MER-PO-103516 / REC-20260310-001 references COC_BG-33044-A1_MER-PO-103516.pdf which is not in the workspace ->
13.6.1 step 7 missing-document DM to Maribel.
"""

from __future__ import annotations

import json
import re
from collections import Counter

from ..kit import (COMM_KINDS, WRITE_KINDS, Comm, Context, blank, comm_rules, nh, no_placeholders, norm, num,
                   pre_rule, state_rule, world)

REC = "REC-20260312-001"
PO = "MER-PO-103517"
APPT = "APPT-20260312-001"
SUPPLIER = "Redstone Alloy Fabricators, Inc."
TODAY_IDS = re.compile(r"REC-20260312-001|MER-PO-103517|APPT-20260312-001|\b103517\b")

# ---- SOP references (section, paragraph prefix, label) ----------------------------------------------------------
R_HAZ_DOCS = ("17.1.1", "DOT-compliant labeling on every package", "17.1.1 hazmat documents before unloading")
R_HAZ_SDS = ("17.1.1", "Safety Data Sheet (SDS) for each hazardous material", "17.1.1 SDS required")
R_HAZ_STEP2 = ("17.1.2", "2. If any of the three required items is missing", "17.1.2 step 2")
R_NO_UNLOAD = ("17.1.2", "Do not unload.", "17.1.2 do not unload")
R_HOLD_POST = ("17.1.2", "Post in #receiving-doc kinstructing the Dock Crew to hold", "17.1.2 TRUCK HOLD post")
R_HOLD_FMT = ("17.1.2", "TRUCK HOLD: [Receipt_ID]", "17.1.2 TRUCK HOLD format")
R_HAZ_DM = ("17.1.2", "Direct-message Darnell Hooks AND the Plant EHS contact", "17.1.2 hazmat DM")
R_HAZ_DM2 = ("17.1.2", "[list]. Truck holding. Awaiting guidance.", "17.1.2 hazmat DM format")
R_WAIT = ("17.1.2", "Wait for written guidance. If documentation can be produced", "17.1.2 wait for guidance")
R_NCR_DOC = ("17.1.2", "NCR required, severity Major (type DOC).", "17.1.2 NCR Major DOC")
R_PROHIB18 = ("21.4", "18. Do not authorize unloading of a hazmat shipment", "21.4 prohibition 18")
R_OVERRIDE = ("16.2.1", "The following conditions trigger an escalation override", "16.2.1 override routing")
R_OVERRIDE_HAZ = ("16.2.1", "Line-down risk confirmed by Aditi", "16.2.1 hazmat without SDS routing")
R_REFUSE_LAST = ("8.7", "Refusal is irreversible once the carrier leaves", "8.7 refusal irreversible")
R_AWAIT = ("16.3", "2. Do not act on the escalated receipt.", "16.4 do not act while awaiting escalation")
R_TPL21 = ("23", "Template 21 — Hazmat Documentation Request", "Template 21")
R_TPL21_SUBJ = ("23", "Subject: URGENT — Hazmat Documentation Required", "Template 21 subject")
R_AWAIT_STATUS = ("16.3", "3. Update receiving_log.xls fxor the escalated receipt", "16.4 step 3 awaiting status")
R_STATUS_NOTE = ("15.2.1", "For Approved suppliers, the Coordinator follows Sections", "15.2.1 supplier status note")
R_NO_PROMISE = ("21.3", "14. Do not promise a supplier any specific resolution", "21.3 prohibition 14")
R_INV_ACCEPT = ("13.2", "After posting the receiving log, the Coordinator updates", "13.2 inventory update")
R_INV_QUAR = ("13.3", "For any line whose Disposition is a quarantine", "13.3 quarantine flag")
R_POST = ("13.1", "Once all rows for the receipt have every required column", "13.1 posting")
R_CROSS_SCOPE = ("13.6", "If the error is discovered after the end of the shift", "13.6 cross-shift scope")
R_CROSS_NOEDIT = ("13.6.1", "1. Do not edit the original row. Do not add a correction row yourself.",
                  "13.6.1 step 1")
R_CROSS_DM = ("13.6.1", "2. Direct-message Maribel Ortiz (Inventory Control Lead) with the format",
              "13.6.1 step 2")
R_CROSS_FMT = ("13.6.1", "[column name] = [original value]. Correct value should be", "13.6.1 format")
R_CROSS_ID = ("13.6.1", "Where [Record_ID] is the value of the first column", "13.6.1 Record_ID")
R_MISSING_DOC = ("13.6.1", "7. If a document referenced in a log entry is not found", "13.6.1 step 7")
R_PROHIB6 = ("21.2", "6. Do not edit or overwrite a posted receiving log row.", "21.2 prohibition 6")
R_PROHIB7 = ("21.2", "7. Do not delete records of any kind.", "21.2 prohibition 7")
R_READONLY = ("5.3", "Read-only for the Coordinator", "5.3 read-only files")
R_SUPMASTER = ("5.1", "supplier_master.xls", "5.1 supplier_master owner")
R_STATUS_OWNER = ("15", "Supplier status is owned by Procurement", "15 supplier status owner")
R_NCR_NUM = ("14.2", "NCRs are numbered sequentially", "14.2 NCR numbering")
R_NCR_ROW = ("14.2", "3. Add a new row with the next sequential NCR number.", "14.2 NCR log row")
R_NCR_DRAFT = ("14.4.2", "2. Save a working copy as NCRs", "14.4.2 NCR draft")
R_NCR_SEND = ("14.4.4", "1. Compose an email to the supplier", "14.4.4 sending the NCR")
R_PLACEHOLDER = ("14.4.2", "3. Fill in every bracketed placeholder.", "14.4.2 placeholders")
R_TPL_RULE = ("23", "This section contains every email template", "23 templates as written")
R_DOCK_REFUSED = ("8.7", "3. Update dock_schedule.xls: xStatus → Refused", "8.7 refusal dock schedule update")
R_EMAIL_NODEL = ("18.5.2", "Do not delete any email without supervisor approval.", "18.5.2 no email deletion")
R_SLACK_NODEL = ("21.3", "13. Do not delete or move a Slack post", "21.3 prohibition 13")

INSTRUCTION = "Task instruction: \"hold off on drafting/sending the NCR\""


# ---- helpers ------------------------------------------------------------------------------------------------------

def _cell(v) -> str:
    """Number-tolerant cell value (an openpyxl re-save may turn 8.0 into 8 or '001' into 1)."""
    s = "" if blank(v) else nh(v)
    if s and re.fullmatch(r"[$\-+]?[\d,]*\.?\d+%?", s.replace(" ", "")):
        n = num(s)
        if n is not None:
            return f"#{round(n, 4)}"
    return s


def _key(r: dict, cols: tuple[str, ...]) -> tuple:
    return tuple(norm(r.get(c, "")) for c in cols)


def _diff(w, book: str, hdr: str, cols: tuple[str, ...], skip=lambda r: False):
    """(edited/removed initial rows, new rows) between the initial and current workbook, compared on the
    initial header columns only and number-tolerantly. ``skip(row)`` exempts initial rows that may change."""
    init = w.rows(book, hdr, "initial")
    if not init:
        return [], []
    cur = w.rows(book, hdr, "current")
    headers = [h for h in init[0] if h != "__row__"]
    vals = lambda r: tuple(_cell(r.get(h)) for h in headers)
    by_key: dict[tuple, list[dict]] = {}
    for r in cur:
        by_key.setdefault(_key(r, cols), []).append(r)
    changed = []
    for r in init:
        if skip(r):
            continue
        cands = by_key.get(_key(r, cols), [])
        if any(vals(c) == vals(r) for c in cands):
            continue
        label = " / ".join(str(r.get(c, "")) for c in cols)
        if cands:
            diff = [h for h in headers if h and _cell(cands[0].get(h)) != _cell(r.get(h))]
            changed.append(f"{label} (changed: {', '.join(diff) or 'layout'})")
        else:
            changed.append(f"{label} (row missing)")
    seen = Counter(_key(r, cols) for r in init)
    new = []
    for r in cur:
        k = _key(r, cols)
        if seen[k] > 0:
            seen[k] -= 1
        else:
            new.append(r)
    return changed, new


def _has_books(w) -> bool:
    return bool(w.current) and bool(w.initial)


def _dm_to(w, a, person: str) -> bool:
    return a.kind in ("slack_dm", "slack_post") and w.is_dm_to(a, person)


def _channel_post(w, a) -> bool:
    return a.kind == "slack_post" and not w.dm_recipients(a)


def _txt(a) -> str:
    return f"{a.subject}\n{a.text}"


def _first_only(w, c: Comm) -> Comm:
    """Vet only the first compliant instance; later follow-ups on the same topic are not re-checked."""
    strict = c.about

    def about(a):
        if not strict(a):
            return False
        comms = w.comms()
        idx = next((i for i, x in enumerate(comms) if x is a), len(comms))
        return not any(strict(x) and not c.problems(x, w) for x in comms[:idx])
    c.about = about
    return c


# ---- messages: today's hazmat truck --------------------------------------------------------------------------------

HOLD_TEXT = (f"TRUCK HOLD: {REC}, {SUPPLIER}, PO #{PO}. Driver on truck — hazmat documentation incomplete. "
             "Do not unload.")
HAZ_DM_TEXT = (f"Hazmat documentation issue — {REC}, {SUPPLIER}, PO #{PO}. Missing: SDS for FL-20044-A3 "
               "(Gear Oil, 75W-140 Synthetic, 5-gal). Truck holding. Awaiting guidance.")
HAZ_DM_BODY = [
    (r"Hazmat documentation issue", "the format opener \"Hazmat documentation issue —\""),
    (r"REC-20260312-001", f"Receipt ID {REC}"),
    (r"Redstone Alloy Fabricators", f"supplier name {SUPPLIER}"),
    (r"MER-PO-103517", f"PO #{PO}"),
    (r"Missing\W.{0,60}(SDS|Safety Data Sheet)", "\"Missing: SDS for FL-20044-A3\""),
    (r"Truck holding", "\"Truck holding.\""),
    (r"Awaiting guidance", "\"Awaiting guidance.\""),
]
CLEARANCE = re.compile(r"(?:^|[.!:]\s*)cleared (to|for) unload|EARLY UNLOAD (AUTHORIZED|APPROVED)|"
                       r"ARRIVAL (ON TIME|EARLY|LATE)\s*:|PUTAWAY AUTHORIZED|HAZMAT RECEIPT\s*:|"
                       r"(?:^|[.!:]\s*)(proceed (with|to) unload|OK to unload|okay to unload|go ahead (and|with) unload)",
                       re.I | re.M)
NEGATED = re.compile(r"do not unload|TRUCK HOLD|\bnot\s+(?:be\s+|yet\s+)?(?:cleared|unload|authori[sz]ed)|"
                     r"\bcannot\b|\bcan't\b|\buntil\b|\bunless\b", re.I)
# Template 21 itself says "will be refused and returned to the carrier" - only definitive refusals match.
REFUSAL = re.compile(r"SHIPMENT REFUSED|Shipment Refused at Receiving|REFUSED AT DOCK|has been refused|"
                     r"is being refused|we are refusing|REFUSED\s*[–—-]\s*DO NOT UNLOAD", re.I)
NCR_LETTER = re.compile(r"^\s*NCR-MER-\d{4}-\d+|NONCONFORMANCE REPORT\s*[–—-]|Nonconformance Report \(NCR\) documents",
                        re.I | re.M)


def _hazmat_specs(ctx: Context) -> list[Comm]:
    w = world(ctx)

    def hold_post(a):
        return _channel_post(w, a) and bool(re.search(r"TRUCK HOLD\s*:", a.text))

    def haz_dm(person):
        def about(a):
            return (_dm_to(w, a, person) and bool(TODAY_IDS.search(a.text))
                    and bool(re.search(r"Hazmat documentation issue|SDS|Safety Data Sheet", a.text, re.I)))
        return about

    def eliz_dm(a):
        return _dm_to(w, a, "Elizabeth Velasquez") and bool(TODAY_IDS.search(a.text))

    def tpl21(a):
        return (a.kind == "email_send"
                and any(x.endswith("@redstonefab.com") for x in a.recipients + a.cc)
                and bool(re.search(r"hazmat documentation|\bSDS\b|Safety Data Sheet", _txt(a), re.I))
                and not NCR_LETTER.search(_txt(a)))

    def clearance(a):
        t = a.text
        return (a.kind in ("slack_post", "slack_dm") and bool(TODAY_IDS.search(_txt(a)))
                and bool(CLEARANCE.search(t)) and not NEGATED.search(t))

    def refusal(a):
        return a.kind in COMM_KINDS and bool(TODAY_IDS.search(_txt(a))) and bool(REFUSAL.search(_txt(a)))

    def ncr_letter(a):
        return (a.kind in ("email_send", "email_draft") and bool(NCR_LETTER.search(_txt(a)))
                and bool(re.search(r"MER-PO-103517|REC-20260312-001|FL-20044-A3", _txt(a))))

    hold_refs = [R_HAZ_STEP2, R_HOLD_POST, R_HOLD_FMT]
    dm_refs = [R_HAZ_STEP2, R_HAZ_DM, R_HAZ_DM2]
    return [_first_only(w, c) if not c.forbidden else c for c in [
        Comm("truck_hold", "slack_post", hold_post,
             f"TRUCK HOLD post in #receiving-dock for {REC} (SDS for FL-20044-A3 missing)", hold_refs,
             channel="receiving-dock", max_count=2, exact_hint=HOLD_TEXT,
             body=[(r"TRUCK HOLD:\s*REC-20260312-001", f"\"TRUCK HOLD: {REC}\""),
                   (r"Redstone Alloy Fabricators", f"supplier name {SUPPLIER}"),
                   (r"PO\s*#?\s*MER-PO-103517", f"\"PO #{PO}\""),
                   (r"Driver on truck", "\"Driver on truck\""),
                   (r"hazmat documentation incomplete", "\"hazmat documentation incomplete\""),
                   (r"Do not un\s?load", "\"Do not unload.\"")]),
        Comm("hazmat_dm_darnell", "slack_dm", haz_dm("Darnell Hooks"),
             f"Hazmat documentation issue DM to Darnell Hooks for {REC}", dm_refs,
             to=["Darnell Hooks"], body=HAZ_DM_BODY, max_count=2, exact_hint=HAZ_DM_TEXT),
        Comm("hazmat_dm_ehs", "slack_dm", haz_dm("Chris Wojciechowski"),
             f"Hazmat documentation issue DM to the Plant EHS contact Chris Wojciechowski for {REC}", dm_refs,
             to=["Chris Wojciechowski"], body=HAZ_DM_BODY, max_count=2, exact_hint=HAZ_DM_TEXT),
        Comm("hazmat_dm_elizabeth", "slack_dm", eliz_dm,
             f"Severity-override DM to Elizabeth Velasquez (hazmat shipment without SDS) for {REC}",
             [R_OVERRIDE, R_OVERRIDE_HAZ], to=["Elizabeth Velasquez"], max_count=2,
             body=[(r"REC-20260312-001|MER-PO-103517", f"{REC} / PO #{PO}"),
                   (r"\bSDS\b|Safety Data Sheet", "that the SDS for FL-20044-A3 is missing")]),
        Comm("hazmat_doc_request", "email", tpl21,
             "Template 21 Hazmat Documentation Request to Redstone", [R_TPL21, R_TPL21_SUBJ],
             required=False, exact_to=False, max_count=2,
             subject=r"URGENT\s*–\s*Hazmat Documentation Required\s*–\s*PO\s*#?\s*MER-PO-103517\s*–\s*Truck Holding",
             subject_hint=f"URGENT — Hazmat Documentation Required — PO #{PO} — Truck Holding",
             body=[(r"FL-20044-A3", "the SKU whose SDS is missing (FL-20044-A3)")],
             banned=[(r"\b(credit|replacement|return authorization|price adjustment)\b.{0,40}\b(will be|is being|has been) "
                      r"(issued|approved|granted|provided|arranged)",
                      "Do not promise the supplier a resolution (credit, replacement, return); that is Procurement's "
                      "or Quality's call.")]),
        Comm("no_unload_clearance", "slack_post", clearance,
             f"Unload/putaway clearance for {REC}", [R_HAZ_STEP2, R_NO_UNLOAD, R_PROHIB18, R_HAZ_SDS],
             forbidden=(f"{PO} is a hazmat load without its SDS (FL-20044-A3_SDS.pdf is not on file). It must not be "
                        "cleared to unload or put away; post the TRUCK HOLD instead and wait for written guidance.")),
        Comm("no_refusal_yet", "email", refusal,
             f"Refusal of {REC}", [R_WAIT, R_REFUSE_LAST, R_AWAIT],
             forbidden=("No written guidance has been received yet. Section 17.1.2 says to hold the truck, DM Darnell "
                        "Hooks and Chris Wojciechowski and wait for written guidance; refuse only if the supplier "
                        "cannot produce the SDS within 1 hour.")),
        Comm("no_ncr_letter", "email", ncr_letter,
             f"NCR letter for {PO}", [R_NCR_DOC, R_NCR_SEND],
             forbidden=f"{INSTRUCTION} - do not draft or send the NCR letter for {PO}."),
    ]]


# ---- messages: closed POs this week -------------------------------------------------------------------------------

CROSS_TEXT = ("Cross-shift receiving correction request — receiving_log.xlsx: REC-20260309-004. "
              "SKU = FL-20044-A3. Correct value should be FL-21300-A1.")
MISSING_TEXT = ("Missing document — REC-20260310-001, PO #MER-PO-103516. Referenced document(s) not found in "
                "workspace: COC (COC_BG-33044-A1_MER-PO-103516.pdf). PO closed 03/10/2026.")


def _closed_po_specs(ctx: Context) -> list[Comm]:
    w = world(ctx)

    def cross(a):
        return _dm_to(w, a, "Maribel Ortiz") and "REC-20260309-004" in a.text

    def missing(a):
        return _dm_to(w, a, "Maribel Ortiz") and "REC-20260310-001" in a.text

    return [_first_only(w, c) for c in [
        Comm("cross_shift_sku", "slack_dm", cross,
             "cross-shift correction request to Maribel Ortiz for the wrong SKU on posted row REC-20260309-004 "
             "(MER-PO-103515 shipped FL-21300-A1 per PO, packing slip, SDS and inventory)",
             [R_CROSS_SCOPE, R_CROSS_DM, R_CROSS_FMT, R_CROSS_ID], to=["Maribel Ortiz"], max_count=2,
             exact_hint=CROSS_TEXT,
             body=[(r"Cross-shift receiving correction request", "\"Cross-shift receiving correction request —\""),
                   (r"receiving_log", "the file name receiving_log.xlsx"),
                   (r"REC-20260309-004", "the Record_ID REC-20260309-004"),
                   (r"\bSKU\b", "the column name SKU"),
                   (r"FL-20044-A3", "the original value FL-20044-A3"),
                   (r"FL-21300-A1", "the correct value FL-21300-A1")]),
        Comm("missing_doc_coc", "slack_dm", missing,
             "missing-document DM to Maribel Ortiz for closed receipt REC-20260310-001 (COC "
             "COC_BG-33044-A1_MER-PO-103516.pdf referenced in the log but not in the workspace)",
             [R_MISSING_DOC], to=["Maribel Ortiz"], max_count=2, exact_hint=MISSING_TEXT,
             body=[(r"Missing document", "\"Missing document —\""),
                   (r"REC-20260310-001", "REC-20260310-001"),
                   (r"MER-PO-103516", "PO #MER-PO-103516"),
                   (r"\bCOC\b|Certificate of Conformance", "the missing document type (COC)"),
                   (r"03/10/2026", "\"PO closed 03/10/2026\"")]),
    ]]


# ---- end-state rules ----------------------------------------------------------------------------------------------

def _today_state(ctx: Context):
    w = world(ctx)
    if not _has_books(w):
        return
    rec = w.find(r"receiving_log", r"^Receipt_ID$", "Receipt_ID", REC)
    if rec is None:
        yield False, f"The receiving_log.xlsx row {REC} (In Process) is missing; restore it.", [R_PROHIB7]
    else:
        status, disp = w.col(rec, r"^Status$"), w.col(rec, r"^Disposition$")
        if re.search(r"\b(posted|refused|complete)\b", status, re.I) \
                or re.match(r"\s*(accepted|refused|quarantine)\b", disp, re.I) \
                or not blank(w.col(rec, r"^Putaway_Authorized")):
            yield False, (f"receiving_log.xlsx {REC} shows Status \"{status}\" / Disposition \"{disp}\". The hazmat "
                          f"truck is holding without its SDS and awaiting written guidance - it is not accepted, "
                          "refused, posted or authorized for putaway. Leave Disposition and "
                          "Putaway_Authorized_Timestamp blank and do not set Status to Posted/Refused."), \
                [R_HAZ_STEP2, R_WAIT, R_POST, R_AWAIT]
        elif not re.search(r"awaiting escalation respon", status, re.I) \
                or not re.search(r"\bSDS\b|Safety Data Sheet", w.col(rec, r"^Notes$"), re.I):
            yield False, (f"receiving_log.xlsx {REC}: the receipt is awaiting the hazmat escalation response, so set "
                          f"Status to AWAITING ESCALATION RESPONSE (got \"{status}\") and put in Notes what is awaited, "
                          "e.g. \"Hazmat receipt - SDS for FL-20044-A3 missing per Section 17.1.2; truck holding, not "
                          "unloaded. Awaiting written guidance from Darnell Hooks / Chris Wojciechowski.\""), \
                [R_AWAIT_STATUS, R_HAZ_STEP2]
        if not re.search(r"Supplier status:\s*Approved as of 09/14/2023", w.col(rec, r"^Notes$"), re.I):
            yield False, (f"receiving_log.xlsx {REC} Notes must record the supplier status check: "
                          "\"Supplier status: Approved as of 09/14/2023.\" (Redstone, SUP-0010, per supplier_master.xlsx)."), \
                [R_STATUS_NOTE]
    appt = w.find(r"dock_schedule", r"^Appointment_ID$", "Appointment_ID", APPT)
    if appt is not None:
        st = w.col(appt, r"^Status$")
        if re.match(r"\s*(unloading|complete|refused)\b", st, re.I):
            yield False, (f"dock_schedule.xlsx {APPT} Status is \"{st}\" but the truck is holding (not unloading, "
                          "not refused) until written guidance arrives. Set it back to Arrived."), \
                [R_HAZ_STEP2, R_WAIT, R_DOCK_REFUSED]
    changed, new = _diff(w, r"dock_schedule", r"^Appointment_ID$", ("Appointment_ID",),
                         skip=lambda r: norm(r.get("Appointment_ID")) == norm(APPT))
    if changed or new:
        yield False, ("dock_schedule.xlsx rows other than today's appointment were changed or added: "
                      f"{'; '.join(changed + [str(r.get('Appointment_ID')) for r in new])}. Restore them."), \
            [R_PROHIB7, R_HAZ_STEP2]
    changed, new = _diff(w, r"inventory_master", r"^SKU$", ("SKU", "Location"))
    if changed or new:
        what = changed + [f"{r.get('SKU')} / {r.get('Location')} (new row)" for r in new]
        yield False, ("inventory_master.xlsx must not change: the hazmat load is still on the truck (nothing accepted "
                      "or quarantined) and cross-shift corrections are made by Maribel Ortiz, not the Coordinator. "
                      f"Restore: {'; '.join(what)}."), [R_NO_UNLOAD, R_INV_ACCEPT, R_INV_QUAR, R_CROSS_NOEDIT]


def _receiving_log_rows(ctx: Context):
    w = world(ctx)
    if not _has_books(w):
        return
    changed, new = _diff(w, r"receiving_log", r"^Receipt_ID$", ("Receipt_ID",),
                         skip=lambda r: norm(r.get("Receipt_ID")) == norm(REC))
    if changed:
        yield False, ("Posted receiving_log.xlsx rows were edited or removed: " + "; ".join(changed) +
                      ". Restore them exactly as posted (e.g. REC-20260309-004 keeps SKU FL-20044-A3). A cross-shift "
                      "error is reported to Maribel Ortiz by DM, not edited."), [R_PROHIB6, R_CROSS_NOEDIT]
    if new:
        ids = ", ".join(str(r.get("Receipt_ID")) for r in new)
        yield False, (f"New receiving_log.xlsx row(s) {ids} were added. No SOP step here adds a row: today's receipt "
                      f"already has row {REC}, and cross-shift corrections (13.6.1) are not added by the Coordinator. "
                      "Remove the added row(s)."), [R_CROSS_NOEDIT, R_PROHIB6]


def _readonly_books(ctx: Context):
    w = world(ctx)
    if not _has_books(w):
        return
    for book, hdr, cols in (("supplier_master", r"^Supplier_ID$", ("Supplier_ID",)),
                            ("closed_pos_archive", r"^PO_Number$", ("PO_Number", "PO_Line"))):
        changed, new = _diff(w, book, hdr, cols)
        if changed or new:
            what = changed + [" / ".join(str(r.get(c)) for c in cols) + " (new row)" for r in new]
            yield False, (f"{book}.xlsx is read-only for the Coordinator (owned by Procurement, Joon-ho Park). "
                          f"Restore: {'; '.join(what)}."), [R_READONLY, R_SUPMASTER, R_STATUS_OWNER]


def _ncr_log(ctx: Context):
    w = world(ctx)
    if not _has_books(w):
        return
    changed, new = _diff(w, r"ncr_log", r"^NCR_Number$", ("NCR_Number",))
    gone = [c for c in changed if c.endswith("(row missing)")]
    if gone:
        yield False, ("Existing ncr_log.xlsx rows were removed: " + "; ".join(gone) +
                      ". Restore them; records are never deleted."), [R_PROHIB7, R_NCR_ROW]
    for i, r in enumerate(new):
        c = lambda rx: w.col(r, rx)
        probs = []
        if i > 0:
            probs.append("only one NCR (for MER-PO-103517) can arise here")
        else:
            if norm(c(r"^NCR_Number$")) != norm("NCR-MER-2026-0032"):
                probs.append(f"NCR_Number must be the next sequential number NCR-MER-2026-0032 (got {c(r'^NCR_Number$')})")
            if not re.search(r"MER-PO-103517", c(r"^PO_Number$")) and not re.search(REC, c(r"^Receipt_ID$")):
                probs.append(f"the only NCR trigger here is {PO} / {REC}")
            if c(r"^NCR_Type$") and norm(c(r"^NCR_Type$")) != "doc":
                probs.append(f"NCR_Type must be DOC (got {c(r'^NCR_Type$')})")
            if c(r"^Severity$") and norm(c(r"^Severity$")) != "major":
                probs.append(f"Severity must be Major (got {c(r'^Severity$')})")
            dv = num(c(r"^Dollar_Value$"))
            if dv is not None and abs(dv - 3780) > 0.01:
                probs.append(f"Dollar_Value must be $3,780.00 (80 x $47.25; got {c(r'^Dollar_Value$')})")
        if probs:
            yield False, f"New ncr_log.xlsx row {c(r'^NCR_Number$')}: " + "; ".join(probs) + ".", \
                [R_NCR_NUM, R_NCR_ROW, R_NCR_DOC]


# ---- pre rules ----------------------------------------------------------------------------------------------------

READONLY_RX = re.compile(r"supplier_master\.xlsx|closed_pos_archive\.xlsx", re.I)


def _readonly_write(ctx: Context, a):
    if a.kind not in WRITE_KINDS:
        return None
    hits = {f for f in a.files_written if READONLY_RX.search(f)}
    if not hits:
        return None
    if a.kind == "workbook_write":
        code = a.code or a.text
        literal = [f for f in hits if re.search(r"(save|to_excel)\(\s*[rf]?['\"][^'\"]*" + re.escape(f), code)]
        referenced = set(re.findall(r"[\w.-]+\.xlsx", code))
        if not literal and len(referenced) > 1:
            return None
        hits = set(literal) or hits
    return (f"[read-only] {', '.join(sorted(hits))} is read-only for the Coordinator (owned by Procurement, Joon-ho "
            "Park); do not write it.")


# NCR letter files per 14.4.2: NCRs\[NCR_Number]_draft.docx and [NCR_Number].pdf
NCR_FILE = re.compile(r"NCR[-_]MER[-_]\d{4}[-_]\d+[\w\-]*\.(?:docx?|pdf)|NCRs[/\\][^'\"\s]+\.(?:docx?|pdf)|"
                      r"NCR[\w\-]*draft[\w\-]*\.(?:docx?|pdf)", re.I)
NCR_WRITE = re.compile(r"(?:\.save\(|write_bytes\(|write_text\()[^)\n;|]*?(?:" + NCR_FILE.pattern + ")|"
                       r"open\(\s*[rf]?['\"][^'\"]*?(?:" + NCR_FILE.pattern + r")['\"]\s*,\s*['\"][wax]", re.I)
NCR_SHELL_WRITE = re.compile(r"(?:>\s*|\btee\s+(?:-a\s+)?|\b(?:cp|mv)\s+(?:-\w+\s+)*\S+\s+)[^\s;&|]*?(?:"
                             + NCR_FILE.pattern + ")", re.I)


def _ncr_draft(ctx: Context, a):
    if a.kind == "file_write" and any(NCR_FILE.search(f) for f in a.files_written):
        return f"[ncr-hold] {INSTRUCTION}: do not draft the NCR letter file."
    if a.tool not in ("syntara__executePython", "syntara__executeBash"):
        return None
    code = a.text or ""
    hit = bool(NCR_WRITE.search(code)) or (a.tool == "syntara__executeBash"
                                            and bool(NCR_SHELL_WRITE.search(code)))
    if not hit:
        for var in re.findall(r"^\s*(\w+)\s*=\s*[^\n]*?(?:" + NCR_FILE.pattern + ")", code, re.I | re.M):
            if re.search(r"(?:\.save\(|write_bytes\(|write_text\()\s*" + re.escape(var) + r"\b", code) \
                    or re.search(r"open\(\s*" + re.escape(var) + r"\s*,\s*['\"][wax]", code) \
                    or re.search(r"\b" + re.escape(var) + r"\.(?:write_bytes|write_text)\(", code):
                hit = True
    if hit:
        return f"[ncr-hold] {INSTRUCTION}: do not draft the NCR letter (NCRs\\[NCR_Number]_draft.docx / .pdf)."
    return None


def _no_delete(ctx: Context, a):
    if a.kind == "email_delete":
        return "[no-delete] Emails are records and are never deleted; move them to the right folder instead."
    if a.tool.startswith("slack__") and re.search(r"delete|remove", a.tool.split("__", 1)[-1], re.I):
        return "[no-delete] Slack posts are part of the audit trail; post a correction reply instead of deleting."
    if a.kind == "file_delete" and re.search(r"(?:rm\s+(?:-\w+\s+)*|remove\(|unlink\()(?![^\n;]*/tmp/)[^\n;]*"
                                             r"\.(?:xlsx|pdf|docx?)\b", a.text or json.dumps(a.args), re.I):
        return "[no-delete] Workspace records (workbooks, PDFs) are never deleted by the Coordinator."
    return None


# Core templates.PLACEHOLDER has no "_" in its class, so SOP fields like [Receipt_ID] / [PO_Number] slip through.
UNDERSCORE_PH = re.compile(r"\[[A-Z][A-Za-z0-9 #]*_[A-Za-z0-9_ #]*\]")


def _underscore_placeholders(ctx: Context, a):
    if a.kind not in COMM_KINDS:
        return None
    left = sorted(set(UNDERSCORE_PH.findall(_txt(a))))
    return f"[placeholders] The message still contains template placeholders {left}." if left else None


RULES = (
    comm_rules("hazmat", _hazmat_specs)
    + comm_rules("closedpo", _closed_po_specs)
    + state_rule("hazmat.hold_state", _today_state,
                 fix="Keep the hazmat truck on hold: no acceptance, refusal, putaway or inventory change.")
    + state_rule("reclog.posted_rows", _receiving_log_rows, fix="Restore the posted receiving log rows.")
    + state_rule("readonly.files", _readonly_books, fix="Restore the read-only workbook.")
    + state_rule("ncrlog.rows", _ncr_log, fix="Fix the ncr_log.xlsx rows as listed.")
    + pre_rule("readonly.writes", _readonly_write, [R_READONLY, R_SUPMASTER], "Leave that file unchanged.")
    + pre_rule("ncr.hold_letter", _ncr_draft, [R_NCR_DRAFT], "Do not draft the NCR letter; the user is holding it.")
    + pre_rule("records.no_delete", _no_delete, [R_PROHIB7, R_EMAIL_NODEL, R_SLACK_NODEL], "Do not delete records.")
    + no_placeholders([R_PLACEHOLDER, R_TPL_RULE])
    + pre_rule("comms.no_placeholders_fields", _underscore_placeholders, [R_PLACEHOLDER, R_TPL_RULE],
               "Replace every bracketed field with the actual value.")
)
