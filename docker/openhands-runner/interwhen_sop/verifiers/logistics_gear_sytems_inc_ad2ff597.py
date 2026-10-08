"""Verifiers for task logistics_gear_sytems_inc_ad2ff597 (hazmat arrival missing a document + closed-PO audit).

Built from the task's own SOP plus the user's instruction:
  * 17.1.1 / 17.1.2 / 21.4 item 18 - hazmat is never unloaded without SDS + manifest + DOT labels; hold the
    truck (TRUCK HOLD post) and DM Darnell Hooks and Chris Wojciechowski with the exact format
  * instruction - "hold off on drafting/sending the NCR"
  * 13.6.1 - cross-shift errors in this week's closed receipts: never edit the row or add a correction row;
    DM Maribel Ortiz ("Cross-shift receiving correction request ..." / "Missing document ...")
Closed-PO findings are computed in Python: archive line vs posted receiving-log row, and referenced
documents vs files present in /workdir.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from functools import cached_property

from .. import common
from ..actions import Action
from ..framework import Context, Finding, Rule, registry
from ..gear import World, blank, norm, num

TASK_RULES: list[Rule] = []
rule = registry(TASK_RULES)

TODAY = dt.date(2026, 3, 12)   # task system prompt: "March, 12, 2026, 10:15"
RCV, DOCK, ARCH = "receiving_log.xlsx", "dock_schedule.xlsx", "closed_pos_archive.xlsx"
SKU = re.compile(r"\b[A-Z]{2}-\d{5}-[A-Z]\d\b")
FALLBACK_HAZMAT_SKUS = ["FL-20044-A3"]   # packing slip MER-PO-103517 (used only if the agent never read it)
COMPARE = [("SKU", "SKU"), ("Qty_Ordered", "Qty_Ordered"), ("PO_Line", "PO_Line"), ("Supplier_ID", "Supplier_ID")]


@dataclass
class Finding13:
    receipt: str
    po: str
    kind: str          # "field" | "document"
    column: str = ""
    wrong: str = ""
    right: str = ""
    missing: tuple = ()
    closed: str = ""


def _date(s: str) -> dt.date | None:
    for fmt in ("%m/%d/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(str(s).strip()[:19], fmt).date()
        except ValueError:
            continue
    return None


class Facts(World):
    @cached_property
    def hazmat(self) -> dict:
        today = TODAY.strftime("%m/%d/%Y")
        appt = next((r for r in self.rows(DOCK, "Appointment_ID", "initial")
                     if str(r.get("Scheduled_Date", "")).startswith(today) and r.get("Hazmat_Flag") == "Y"), {})
        po = str(appt.get("Expected_PO_Numbers", "")).split(",")[0].strip()
        rec = next((r for r in self.rows(RCV, "Receipt_ID", "initial") if r.get("PO_Number") == po), {})
        return {"appt": appt.get("Appointment_ID", ""), "po": po, "receipt": rec.get("Receipt_ID", ""),
                "supplier": appt.get("Supplier_Name", "")}

    @cached_property
    def hazmat_skus(self) -> list[str]:
        po = self.hazmat["po"]
        seen = [o.get("text", "") for o in self.state.observations if po and po in o.get("text", "")
                and "PACKING SLIP" in o.get("text", "").upper()]
        skus = sorted({s for t in seen for s in SKU.findall(t)})
        return skus or FALLBACK_HAZMAT_SKUS

    def sds_present(self, sku: str) -> bool:
        if self.has_file(rf"(^|/)[^/]*{re.escape(sku)}[^/]*SDS[^/]*\.pdf$|(^|/)[^/]*SDS[^/]*{re.escape(sku)}[^/]*\.pdf$"):
            return True
        return any(sku in str(a) and "sds" in str(a).lower() for e in self.state.emails for a in e.attachments)

    @property
    def missing_sds(self) -> list[str]:
        return [s for s in self.hazmat_skus if not self.sds_present(s)]

    @cached_property
    def week_closed(self) -> list[dict]:
        monday = TODAY - dt.timedelta(days=TODAY.weekday())
        return [r for r in self.rows(ARCH, "PO_Number", "initial")
                if (d := _date(r.get("Closure_Date", ""))) and monday <= d <= TODAY]

    @cached_property
    def audit(self) -> list[Finding13]:
        rcv = self.rows(RCV, "Receipt_ID", "initial")
        files = [f.lower() for f in self.files()]
        out = []
        for po in self.week_closed:
            rid = po.get("Receipt_ID", "")
            row = next((r for r in rcv if r.get("Receipt_ID") == rid), None)
            if not row:
                continue
            for acol, rcol in COMPARE:
                a, r = str(po.get(acol, "")).strip(), str(row.get(rcol, "")).strip()
                if a and r and (num(a) != num(r) if num(a) is not None and num(r) is not None else a != r):
                    out.append(Finding13(rid, po["PO_Number"], "field", rcol, r, a))
            refs = [row.get("COC_Filename", ""), row.get("MTR_Filename", "")]
            refs += re.findall(r"[\w.-]+_SDS\.pdf", str(row.get("Notes", "")))
            missing = tuple(x for x in refs if x and not any(x.lower() in f for f in files))
            if missing:
                out.append(Finding13(rid, po["PO_Number"], "document", missing=missing,
                                     closed=str(po.get("Closure_Date", ""))))
        return out

    @cached_property
    def closed_receipts(self) -> set[str]:
        return {p.get("Receipt_ID", "") for p in self.week_closed if p.get("Receipt_ID")}


def facts(ctx: Context) -> Facts:
    return ctx.memo("fad2", lambda: Facts(ctx))


def _blob(a: Action) -> str:
    return f"{a.subject}\n{a.text}\n{a.code}"


UNLOAD_POST = re.compile(r"cleared to unload|HAZMAT RECEIPT:|PUTAWAY AUTHORIZED|UNLOAD AUTHORIZED", re.I)
UNLOAD_WRITE = re.compile(r"Unloading|Complete|Posted|ACCEPTED|Qty_Received|Putaway", re.I)


@rule("hazmat.no_unload_without_docs", "pre", [("17.1.1", "• DOT-compliant labeling on every package"),
                                                ("21.4", "18. Do not authorize unloading of a hazmat")])
def no_unload(ctx: Context, action: Action) -> list[Finding]:
    f = facts(ctx)
    h = f.hazmat
    ids = [x for x in (h["receipt"], h["po"], h["appt"], *f.hazmat_skus) if x]
    blob = _blob(action)
    if not any(i in blob for i in ids):
        return []
    acting = (action.kind == "slack_post" and UNLOAD_POST.search(blob) and "TRUCK HOLD" not in blob.upper()) or (
        action.kind == "workbook_write" and UNLOAD_WRITE.search(action.code))
    if not acting or not f.missing_sds:
        return []
    return [Finding("hazmat.no_unload_without_docs", [
        ctx.cite("17.1.1", "• DOT-compliant labeling on every package", "17.1.1"),
        ctx.cite("21.4", "18. Do not authorize unloading of a hazmat", "21.4 item 18")],
        f"{h['receipt']} is a hazmat shipment and no SDS for {', '.join(f.missing_sds)} is on file (checked "
        "/workdir and received mail). Hazmat is never unloaded, accepted or posted until SDS, manifest and DOT "
        "labeling are all verified.",
        ["Keep the truck on hold: post the Section 17.1.2 TRUCK HOLD message and DM Darnell Hooks and Chris "
         "Wojciechowski; wait for written guidance."])]


def _hold_post_problems(f: Facts, text: str) -> list[str]:
    h = f.hazmat
    want = (f"TRUCK HOLD: {h['receipt']}, {h['supplier']}, PO #{h['po']}. Driver on truck — hazmat "
            "documentation incomplete. Do not unload.")
    return [] if norm(want) in norm(text) else [f"The post must read exactly: '{want}'"]


@rule("hazmat.truck_hold_post", "pre", [("17.1.2", "TRUCK HOLD:")])
def hold_post(ctx: Context, action: Action) -> list[Finding]:
    if action.kind != "slack_post" or "TRUCK HOLD" not in action.text.upper():
        return []
    f = facts(ctx)
    probs = _hold_post_problems(f, action.text)
    if not f.is_channel(action.channel, "receiving-dock"):
        probs.append("Post it in #receiving-dock (the Dock Crew channel).")
    if not probs:
        return []
    return [Finding("hazmat.truck_hold_post", [ctx.cite("17.1.2", "TRUCK HOLD:", "17.1.2 step 2")], " ".join(probs),
                    ["Use the exact Section 17.1.2 wording."])]


def _issue_dm_problems(f: Facts, text: str) -> list[str]:
    h = f.hazmat
    head = f"Hazmat documentation issue — {h['receipt']}, {h['supplier']}, PO #{h['po']}. Missing:"
    out = []
    if norm(head) not in norm(text):
        out.append(f"Start with '{head} [list]. Truck holding. Awaiting guidance.'")
    for s in f.missing_sds:
        if not re.search(rf"SDS[^.]*{re.escape(s)}|{re.escape(s)}[^.]*SDS", text):
            out.append(f"'Missing:' must list the SDS for {s}.")
    if "truck holding. awaiting guidance" not in norm(text):
        out.append("End with 'Truck holding. Awaiting guidance.'")
    return out


@rule("hazmat.issue_dm_format", "pre", [("17.1.2", "– Direct-message Darnell Hooks AND the Plant EHS contact")])
def issue_dm(ctx: Context, action: Action) -> list[Finding]:
    if action.kind not in ("slack_dm", "slack_post") or "hazmat documentation issue" not in action.text.lower():
        return []
    f = facts(ctx)
    probs = _issue_dm_problems(f, action.text)
    if not (f.is_dm_to(action, "Darnell Hooks") or f.is_dm_to(action, "Chris Wojciechowski")):
        probs.append("This message is a direct message to Darnell Hooks and Chris Wojciechowski.")
    if not probs:
        return []
    return [Finding("hazmat.issue_dm_format", [ctx.cite("17.1.2", "– Direct-message Darnell Hooks AND", "17.1.2")],
                    " ".join(probs), ["Send the Section 17.1.2 format to both people."])]


@rule("instruction.hold_ncr", "pre", [], source="task_instruction")
def hold_ncr(ctx: Context, action: Action) -> list[Finding]:
    f = facts(ctx)
    existing = {r.get("NCR_Number") for r in f.rows("ncr_log.xlsx", "NCR_Number", "initial")}
    text = f"{action.subject}\n{action.text}"
    new_numbers = set(re.findall(r"NCR-MER-\d{4}-\d{4}", text)) - existing
    ncr_mail = action.kind == "email_send" and (re.search(r"NONCONFORMANCE REPORT", text, re.I) or new_numbers)
    ncr_log = action.kind in ("workbook_write", "file_write") and "ncr_log.xlsx" in action.files_written
    if not (ncr_mail or ncr_log):
        return []
    return [Finding("instruction.hold_ncr", ["Task instruction: \"hold off on drafting/sending the NCR.\""],
                    "The user asked you to hold off on drafting or sending the NCR (no NCR letter, no ncr_log entry).",
                    ["Skip the NCR step; everything else in Section 17.1.2 still applies."])]


@rule("audit.no_self_correction", "pre", [("13.6.1", "1. Do not edit the original row")])
def no_self_correction(ctx: Context, action: Action) -> list[Finding]:
    if action.kind != "workbook_write" or RCV not in action.files_written:
        return []
    f = facts(ctx)
    hits = sorted(r for r in f.closed_receipts if r in action.code)
    if not hits:
        return []
    return [Finding("audit.no_self_correction", [ctx.cite("13.6.1", "1. Do not edit the original row", "13.6.1 step 1")],
                    f"{', '.join(hits)} was posted on an earlier shift this week; cross-shift errors are never edited "
                    "and the Coordinator does not add the correction row.",
                    ["Direct-message Maribel Ortiz with the Section 13.6.1 format and wait for her response."])]


def _audit_dm_problems(f: Facts, text: str) -> list[str]:
    out = []
    for m in re.finditer(r"Cross-shift receiving correction request\s*[—-]\s*(\S+?):\s*(\S+?)\.\s*(\w+)\s*=\s*(.+?)\."
                         r"\s*Correct value should be\s+(.+?)\.?(?:\n|$)", text):
        fname, rid, col, wrong, right = m.groups()
        hit = next((a for a in f.audit if a.kind == "field" and a.receipt == rid and a.column == col), None)
        if hit and (norm(wrong) != norm(hit.wrong) or norm(right) != norm(hit.right)):
            out.append(f"For {rid} the {col} values are: original '{hit.wrong}', correct '{hit.right}'.")
        if hit is None and not any(a.receipt == rid for a in f.audit):
            out.append(f"No discrepancy found for {rid}.{col}; check the value against the PO archive and source "
                       "documents.")
        if fname.lower() != RCV:
            out.append(f"[File name with error] for {rid} is {RCV}.")
    return out


@rule("audit.dm_format", "pre", [("13.6.1", "2. Direct-message Maribel Ortiz")])
def audit_dm(ctx: Context, action: Action) -> list[Finding]:
    if action.kind not in ("slack_dm", "slack_post"):
        return []
    t = action.text
    if "cross-shift receiving correction request" not in t.lower():
        return []
    f = facts(ctx)
    probs = _audit_dm_problems(f, t)
    if not re.search(r"Cross-shift receiving correction request\s*[—-]\s*\S+:\s*REC-", t):
        probs.append("Use 'Cross-shift receiving correction request — [File name with error]: [Record_ID]. "
                     "[column name] = [original value]. Correct value should be [new value].'")
    if not f.is_dm_to(action, "Maribel Ortiz"):
        probs.append("Send it as a direct message to Maribel Ortiz.")
    if not probs:
        return []
    return [Finding("audit.dm_format", [ctx.cite("13.6.1", "2. Direct-message Maribel Ortiz", "13.6.1 step 2")],
                    " ".join(probs), ["Correct the message and resend."])]


@rule("hazmat_and_audit.completion", "completion", [("17.1.2", "2. If any of the three required items"),
                                                    ("13.6.1", "2. Direct-message Maribel Ortiz")])
def completion(ctx: Context) -> list[Finding]:
    f = facts(ctx)
    probs: list[str] = []
    h = f.hazmat
    if f.missing_sds:
        if not any(not _hold_post_problems(f, e.action.text) for e in f.posts_in("receiving-dock")):
            probs.append(f"No TRUCK HOLD post for {h['receipt']} in #receiving-dock (17.1.2).")
        for person in ("Darnell Hooks", "Chris Wojciechowski"):
            if not any("hazmat documentation issue" in e.action.text.lower() and not _issue_dm_problems(f, e.action.text)
                       for e in f.dms_to(person)):
                probs.append(f"{person} has not been sent the 17.1.2 'Hazmat documentation issue — ...' direct message.")
        for b, a in f.changed_rows(DOCK, "Appointment_ID", lambda r: r.get("Appointment_ID") == h["appt"]):
            if a and norm(a.get("Status")) in ("unloading", "complete"):
                probs.append(f"{h['appt']} Status is '{a.get('Status')}' but the hazmat truck may not unload.")
    dms = [e.action.text for e in f.dms_to("Maribel Ortiz")]
    for a in f.audit:
        if a.kind == "field" and not any(a.receipt in t and a.column in t and a.right in t and
                                         "cross-shift receiving correction request" in t.lower() for t in dms):
            probs.append(f"{a.receipt} (PO {a.po}, closed this week) shows {a.column} = {a.wrong} but the PO is for "
                         f"{a.right}: send Maribel Ortiz the 13.6.1 'Cross-shift receiving correction request' DM.")
        if a.kind == "document" and not any(a.receipt in t and "missing document" in t.lower() for t in dms):
            probs.append(f"{a.receipt} (PO {a.po}, closed {a.closed}) references {', '.join(a.missing)}, not found in "
                         "the workspace: send Maribel Ortiz the 13.6.1 step 7 'Missing document — ...' DM.")
    for b, a in f.changed_rows(RCV, "Receipt_ID", lambda r: r.get("Receipt_ID", "").split("-C")[0] in f.closed_receipts):
        probs.append(f"receiving_log.xlsx row {(b or a or {}).get('Receipt_ID')} was edited or a correction row was "
                     "added; 13.6.1 forbids both for cross-shift errors - restore it.")
    if not probs:
        return []
    return [Finding("hazmat_and_audit.completion", [
        ctx.cite("17.1.2", "2. If any of the three required items", "17.1.2"),
        ctx.cite("13.6.1", "2. Direct-message Maribel Ortiz", "13.6.1")],
        "Not finished per the SOP: " + " ".join(probs), ["Fix each listed item, then finish."])]


RULES = common.RULES + TASK_RULES
