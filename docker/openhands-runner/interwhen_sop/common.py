"""SOP checks shared by every Gear task (Sections 5.3, 14.6, 21.2, 23).

Task verifier modules include these explicitly via ``RULES = common.RULES + [...]``.
"""

from __future__ import annotations

import re

from . import templates, workbooks
from .actions import Action
from .framework import Context, Finding, Rule, registry

RULES: list[Rule] = []
rule = registry(RULES)


def without(*rule_ids: str) -> list[Rule]:
    """Common rules minus ones a task's SOP procedure explicitly overrides."""
    return [r for r in RULES if r.id not in rule_ids]


@rule("files.read_only_workbooks", "pre", [("5.3", "• Read-only for the Coordinator")])
def read_only(ctx: Context, action: Action) -> list[Finding]:
    if action.kind not in ("workbook_write", "file_write"):
        return []
    _, text = ctx.para("5.3", "• Read-only for the Coordinator")
    # Some SOP variants scramble the extension ("supplier_master.xls (xowned"); keep the stem.
    ro = {f"{stem}.xlsx" for stem in re.findall(r"([a-z][a-z_]{3,})\.x", text.split("The Coordinator can update")[0])}
    hit = sorted(ro & set(action.files_written))
    if not hit:
        return []
    return [Finding("files.read_only_workbooks", [ctx.cite("5.3", "• Read-only for the Coordinator", "5.3")],
                    f"{', '.join(hit)} is read-only for the Coordinator.", ["Do not modify this file."])]


@rule("records.no_deletion", "pre", [("21.2", "7. Do not delete records")])
def no_delete(ctx: Context, action: Action) -> list[Finding]:
    if not action.deletes:
        return []
    return [Finding("records.no_deletion", [ctx.cite("21.2", "7. Do not delete records", "21.2 item 7")],
                    "This call deletes files, emails or workbook rows.",
                    ["Records may be moved but never deleted; use a correction row (Section 13.5/13.6) instead."])]


@rule("comms.no_unfilled_placeholders", "pre", [("23", "This section contains every email template")])
def placeholders(ctx: Context, action: Action) -> list[Finding]:
    if action.kind not in ("email_send", "slack_post", "slack_dm", "calendar_create", "calendar_update"):
        return []
    left = templates.unfilled_placeholders(f"{action.subject}\n{action.text}")
    if not left:
        return []
    return [Finding("comms.no_unfilled_placeholders", [ctx.cite("23", "This section contains", "23")],
                    f"Outgoing text still contains template placeholders {left}.",
                    ["Replace every [bracketed placeholder] with confirmed information before sending."])]


@rule("calendar.reinspection_needs_quarantine", "pre", [
    ("14.6", "Whenever the Coordinator applies a quarantine"),
    ("14.6.1", "2. Create a new event with the title format"),
])
def calendar_rule(ctx: Context, action: Action) -> list[Finding]:
    if action.kind != "calendar_create":
        return []
    inv = workbooks.table(workbooks.first_sheet(workbooks.dump() or {}, "inventory_master.xlsx"), "SKU")
    held = {r.get("Quarantine_Receipt_ID") or r.get("Last_Receipt_ID") for r in inv
            if str(r.get("Location", "")).upper().startswith("Q-HOLD")}
    refs = set(re.findall(r"REC-\d{8}-\d{3}", f"{action.subject}\n{action.text}"))
    quarantined = bool(refs & held) or any(
        "inventory_master.xlsx" in e.action.files_written and re.search(r"q-?hold|quarantin", e.action.code, re.I)
        for e in ctx.state.executed)
    problems, fixes = [], []
    if not quarantined:
        problems.append("Section 14.6 re-inspection events are scheduled for material quarantined under Section "
                        "13.3; the referenced receipt has no Q-HOLD entry in inventory_master.xlsx.")
        fixes.append("Only create re-inspection events for quarantined receipts.")
    if not re.match(r"RE-INSPECTION: REC-\d{8}-\d{3}", action.subject or ""):
        problems.append("The event title (the 'summary' argument) must follow 'RE-INSPECTION: REC-[ID] [SKU] "
                        f"[QUARANTINE REASON]' (got '{action.subject}').")
    if not problems:
        return []
    return [Finding("calendar.reinspection_needs_quarantine",
                    [ctx.cite("14.6.1", "2. Create a new event with the title format", "14.6.1 step 2")],
                    " ".join(problems), fixes)]


@rule("records.posted_rows_unchanged", "completion", [
    ("21.2", "6. Do not edit or overwrite a posted receiving log row"),
    ("21.2", "7. Do not delete records"),
])
def posted_rows(ctx: Context) -> list[Finding]:
    issues = workbooks.integrity_issues()
    if not issues:
        return []
    return [Finding("records.posted_rows_unchanged", [
        ctx.cite("21.2", "6. Do not edit or overwrite", "21.2 item 6"),
        ctx.cite("21.2", "7. Do not delete records", "21.2 item 7")],
        "Workbook records changed in a way the SOP forbids: " + "; ".join(issues[:6]),
        ["Restore the original values; use a correction row per Section 13.5/13.6 instead."])]


from . import sop_generic  # noqa: E402  (paragraph-level checks compiled from each task's SOP)

RULES.extend(sop_generic.RULES)
