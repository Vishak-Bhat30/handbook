"""Verifiers for task logistics_gear_sytems_inc_dba0375e (standard receipt of three simultaneous arrivals).

Built from the task's own SOP plus the user's instruction:
  * instruction - handle only the standard (non-hazmat) arrival; the two hazmat ones belong to the user;
    free-text fields without SOP wording get "Actioned per SOP protocol"; the disposition timestamp is
    the current time (task system prompt: 11/24/2026 14:21 CST); user is James Reed (JR).
  * 10.7 / 11.8 / 12.8 / 12.9 / 13.1 - receiving-log values for an exact, clean, documented receipt
  * 13.2 - a SKU absent from inventory_master is never created by the Coordinator: Template 18 to Maribel
  * 13.4 + Template 24 - putaway post format
  * 15 - supplier status must be checked before any disposition
"""

from __future__ import annotations

import re
from functools import cached_property

from .. import common
from ..actions import Action
from ..framework import Context, Finding, Rule, registry
from ..gear import World, blank, norm, num

TASK_RULES: list[Rule] = []
rule = registry(TASK_RULES)

NOW = "11/24/2026 14:21 CST"   # task system prompt
TODAY = "11/24/2026"
USER, INITIALS = "James Reed", "JR"   # task instruction
RCV, INV, DOCK = "receiving_log.xlsx", "inventory_master.xlsx", "dock_schedule.xlsx"


class Facts(World):
    @cached_property
    def dock(self) -> list[dict]:
        return self.rows(DOCK, "Appointment_ID", "initial")

    def _today(self, r: dict) -> bool:
        d = str(r.get("Scheduled_Date", ""))
        return d.startswith("2026-11-24") or d.startswith(TODAY)

    @cached_property
    def standard_appts(self) -> list[dict]:
        return [r for r in self.dock if self._today(r) and str(r.get("Hazmat_Flag", "")).upper() == "N"]

    @cached_property
    def hazmat_appts(self) -> list[dict]:
        return [r for r in self.dock if self._today(r) and str(r.get("Hazmat_Flag", "")).upper() == "Y"]

    def receipts_for(self, appts: list[dict]) -> list[dict]:
        pos = {p.strip() for a in appts for p in str(a.get("Expected_PO_Numbers", "")).split(",")}
        return [r for r in self.rows(RCV, "Receipt_ID", "initial") if r.get("PO_Number") in pos]

    @cached_property
    def target(self) -> dict:
        rows = self.receipts_for(self.standard_appts)
        return rows[0] if rows else {}

    @cached_property
    def hazmat_ids(self) -> set[str]:
        ids = {r["Receipt_ID"] for r in self.receipts_for(self.hazmat_appts)}
        ids |= {a["Appointment_ID"] for a in self.hazmat_appts}
        ids |= {p.strip() for a in self.hazmat_appts for p in str(a.get("Expected_PO_Numbers", "")).split(",")}
        return {i for i in ids if i}

    @cached_property
    def unload(self) -> str:
        rid = self.target.get("Receipt_ID", "")
        msgs = [m.get("text", "") for m in (self._slack_seed.get("messages") or {}).get("C001", [])]
        msgs += [m.text for m in self.state.slack]
        return next((t for t in msgs if t.startswith("UNLOAD COMPLETE") and rid in t), "")

    @cached_property
    def supplier_name(self) -> str:
        a = self.standard_appts[0] if self.standard_appts else {}
        return str(a.get("Supplier_Name", ""))

    @cached_property
    def sku_known(self) -> bool:
        sku = self.target.get("SKU")
        return any(r.get("SKU") == sku for r in self.rows(INV, "SKU", "initial"))

    def row_now(self) -> dict | None:
        t = self.target
        return next((r for r in self.rows(RCV, "Receipt_ID")
                     if r.get("Receipt_ID") == t.get("Receipt_ID") and r.get("PO_Line") == t.get("PO_Line")), None)


def facts(ctx: Context) -> Facts:
    return ctx.memo("fdba", lambda: Facts(ctx))


def _qty(t: dict) -> str:
    q = num(t.get("Qty_Claimed_On_Slip"))
    return str(int(q)) if q is not None else ""


def _blob(a: Action) -> str:
    return f"{a.subject}\n{a.text}\n{a.code}"


@rule("instruction.leave_hazmat_receipts", "pre", [], source="task_instruction")
def leave_hazmat(ctx: Context, action: Action) -> list[Finding]:
    if action.kind in ("read", "control"):
        return []
    f = facts(ctx)
    hits = sorted(i for i in f.hazmat_ids if i in _blob(action))
    if not hits:
        return []
    return [Finding("instruction.leave_hazmat_receipts", ["Task instruction: \"Please take care of the standard one "
                    "while I deal with the two hazard ones.\""],
                    f"This call acts on the hazmat arrivals ({', '.join(hits)}), which the user is handling personally.",
                    [f"Only process the standard receipt {f.target.get('Receipt_ID')}; leave the hazmat rows, "
                     "appointments and POs untouched."])]


@rule("receipt.supplier_status_before_disposition", "pre",
      [("15", "Every supplier on Gear Systems’ Approved Supplier List")])
def supplier_status(ctx: Context, action: Action) -> list[Finding]:
    if action.kind != "workbook_write" or RCV not in action.files_written:
        return []
    if not re.search(r"ACCEPTED|Disposition|Posted", action.code, re.I):
        return []
    f = facts(ctx)
    if f.read_mentions("supplier_master"):
        return []
    return [Finding("receipt.supplier_status_before_disposition", [
        ctx.cite("15", "Every supplier on Gear Systems’ Approved Supplier List", "15")],
        "The disposition is being recorded before the supplier's status was checked in supplier_master.xlsx.",
        ["Open supplier_master.xlsx and verify the supplier's status first, then apply the matching Section 15.2 "
         "path (or escalate per Section 16.2.2 if the status cannot be determined)."])]


@rule("inventory.no_new_sku_row", "pre", [("13.2", "If the SKU does not exist in inventory_master")])
def new_sku(ctx: Context, action: Action) -> list[Finding]:
    if action.kind != "workbook_write" or INV not in action.files_written:
        return []
    f = facts(ctx)
    sku = f.target.get("SKU", "")
    if not sku or f.sku_known:
        return []
    base = sku.rsplit("-", 1)[0]
    if sku not in action.code and base not in action.code:
        return []
    return [Finding("inventory.no_new_sku_row", [
        ctx.cite("13.2", "If the SKU does not exist in inventory_master", "13.2 (new SKU)")],
        f"{sku} has no row in inventory_master.xlsx. The Coordinator must not create one, and other revisions of "
        f"{base} are different SKUs whose rows must not absorb this receipt.",
        [f"Leave inventory_master.xlsx unchanged and direct-message Maribel Ortiz with Template 18 (New SKU Setup "
         f"Request — {f.target.get('Receipt_ID')} — {sku})."])]


def _t18_problems(f: Facts, text: str) -> list[str]:
    t = f.target
    need = {"Receipt ID": t.get("Receipt_ID"), "PO Number": t.get("PO_Number"), "Supplier": f.supplier_name,
            "SKU": t.get("SKU"), "Quantity received": _qty(t) if "Count match: Y" in f.unload else None,
            "Safety-Critical": t.get("Safety_Critical")}
    out = []
    for label, val in need.items():
        if val and not re.search(rf"{re.escape(label)}\s*:\s*{re.escape(str(val))}", text, re.I):
            out.append(f"'- {label}: {val}'")
    return out


@rule("comms.template18_new_sku", "pre", [("13.2", "If the SKU does not exist in inventory_master")])
def template18(ctx: Context, action: Action) -> list[Finding]:
    if action.kind not in ("slack_dm", "slack_post") or "new sku setup request" not in action.text.lower():
        return []
    f = facts(ctx)
    probs = []
    if not f.is_dm_to(action, "Maribel Ortiz"):
        probs.append("Template 18 is a direct message to Maribel Ortiz (Inventory Control).")
    miss = _t18_problems(f, action.text)
    if miss:
        probs.append("Template 18 fields missing or wrong: " + ", ".join(miss) + ".")
    if not probs:
        return []
    return [Finding("comms.template18_new_sku", [ctx.cite("13.2", "If the SKU does not exist", "13.2"),
                                                 "SOP Template 18 (New SKU Setup Request)"], " ".join(probs),
                    ["Send Template 18 with every field filled from the receipt."])]


@rule("comms.putaway_post_format", "pre", [("13.4", "Once the inventory master is updated")])
def putaway_post(ctx: Context, action: Action) -> list[Finding]:
    if action.kind != "slack_post" or "PUTAWAY AUTHORIZED" not in action.text.upper():
        return []
    f = facts(ctx)
    t = f.target
    probs = []
    head = rf"PUTAWAY AUTHORIZED:\s*{re.escape(t.get('Receipt_ID', ''))},\s*{re.escape(f.supplier_name)},\s*1 lines?\."
    if not re.search(head, action.text, re.I):
        probs.append(f"First line must be 'PUTAWAY AUTHORIZED: {t.get('Receipt_ID')}, {f.supplier_name}, 1 line.'")
    m = re.search(rf"-\s*Line\s+{t.get('PO_Line')}:\s*{re.escape(t.get('SKU', ''))},\s*{_qty(t)} units\s*(?:→|->)\s*(\S+)",
                  action.text)
    if not m:
        probs.append(f"List the line as '- Line {t.get('PO_Line')}: {t.get('SKU')}, {_qty(t)} units → [Location]'.")
    elif not f.sku_known and m.group(1).rstrip(".") != "C-RCV-01":
        probs.append(f"{t.get('SKU')} is a new SKU: per Section 13.2(d) the FL- prefix goes to Zone C's default "
                     f"receiving slot C-RCV-01 (got {m.group(1)}).")
    if not re.search(rf"Coordinator:\s*{INITIALS}\b", action.text):
        probs.append(f"End with 'Coordinator: {INITIALS}'.")
    if not f.is_channel(action.channel, "receiving-dock"):
        probs.append("Post it in #receiving-dock.")
    if not probs:
        return []
    return [Finding("comms.putaway_post_format", [ctx.cite("13.4", "Once the inventory master is updated", "13.4"),
                                                  "SOP Template 24 (Putaway Authorization Post)"], " ".join(probs),
                    ["Rewrite the post to match Template 24."])]


EXPECT = {
    "Variance_Band": "exact", "Quantity_Action": "accepted", "Condition_Tier": "tier 0",
    "Condition_Action": "accepted", "Photos_Folder": "n/a", "Documentation_Status": "verified",
    "Documentation_Action": "accepted", "Disposition": "accepted clean",
}


@rule("receipt.completion", "completion", [("12.9", "After Sections 10, 11, and 12"),
                                           ("13.1", "Before posting, the Coordinator confirms")])
def completion(ctx: Context) -> list[Finding]:
    f = facts(ctx)
    t = f.target
    if not t:
        return []
    rid = t["Receipt_ID"]
    probs: list[str] = []
    row = f.row_now() or {}
    clean = "Count match: Y" in f.unload and "Condition: Clean" in f.unload
    escalated = any(rid in e.action.text for p in ("Darnell Hooks", "Joon-ho Park") for e in f.dms_to(p))
    if norm(row.get("Status")) != "posted":
        if not escalated:
            probs.append(f"{rid} is not Posted. Complete Sections 10-12 and the 13.1 final pass (every required "
                         "column populated, Status → Posted), or escalate per Section 16.2.2 if something blocks it.")
    elif clean:
        bad = [f"{k} = '{v.upper() if k == 'Disposition' else v}' (got '{row.get(k, '')}')"
               for k, v in EXPECT.items() if norm(row.get(k)) != v]
        qty = num(t.get("Qty_Claimed_On_Slip"))
        if num(row.get("Qty_Received")) != qty:
            bad.append(f"Qty_Received = {int(qty or 0)} (Dock Lead reported 'Count match: Y')")
        if num(row.get("Variance_Units")) != 0:
            bad.append("Variance_Units = 0")
        if num(row.get("Variance_Pct")) != 0 or blank(row.get("Variance_Pct")):
            bad.append("Variance_Pct = 0.0%")
        if str(row.get("Disposition_Timestamp", "")).strip() != NOW:
            bad.append(f"Disposition_Timestamp = '{NOW}' (instruction: exactly the current time)")
        if str(row.get("Coordinator_Initials", "")).strip() != INITIALS:
            bad.append(f"Coordinator_Initials = {INITIALS}")
        if blank(row.get("Notes")):
            bad.append("Notes populated (13.1 requires it; use 'Actioned per SOP protocol' where the SOP gives "
                       "no wording)")
        for k in ("Heat_Numbers", "COC_Filename", "MTR_Filename", "NCR_Number"):
            if t.get("Safety_Critical") == "N" and not blank(row.get(k)):
                bad.append(f"{k} blank (standard part, no NCR)")
        if bad:
            probs.append(f"receiving_log.xlsx {rid}: " + "; ".join(bad) + ".")
    for which, fname, key in (("receiving", RCV, "Receipt_ID"), ("dock", DOCK, "Appointment_ID")):
        for b, a in f.changed_rows(fname, key, lambda r: any(i in str(r.get(key, "")) or i in str(r.get("PO_Number", ""))
                                                             for i in f.hazmat_ids)):
            probs.append(f"{fname} row {(b or a or {}).get(key)} (hazmat arrival handled by the user) was changed; "
                         "restore it.")
    if not f.sku_known:
        sku = t.get("SKU", "")
        base = sku.rsplit("-", 1)[0]
        for b, a in f.changed_rows(INV, "SKU", lambda r: str(r.get("SKU", "")).startswith(base)):
            probs.append(f"inventory_master.xlsx row for {(b or a or {}).get('SKU')} was added/changed; {sku} is a new "
                         "SKU and Section 13.2 forbids creating or repurposing rows - restore it.")
        dms = [e for e in f.dms_to("Maribel Ortiz") if "new sku setup request" in e.action.text.lower()]
        if norm(row.get("Status")) == "posted" and not any(not _t18_problems(f, e.action.text) for e in dms):
            probs.append(f"{sku} is not in inventory_master.xlsx: direct-message Maribel Ortiz with Template 18 "
                         f"(New SKU Setup Request — {rid} — {sku}) (Section 13.2).")
    if not probs:
        return []
    return [Finding("receipt.completion", [ctx.cite("12.9", "After Sections 10, 11, and 12", "12.9"),
                                           ctx.cite("13.1", "Before posting, the Coordinator confirms", "13.1"),
                                           ctx.cite("13.2", "If the SKU does not exist in inventory_master", "13.2")],
                    "The standard receipt is not finished per the SOP: " + " ".join(probs),
                    ["Fix each listed item, then finish."])]


RULES = common.RULES + TASK_RULES
