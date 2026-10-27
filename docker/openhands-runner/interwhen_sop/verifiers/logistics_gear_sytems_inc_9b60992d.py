"""Verifiers for logistics_gear_sytems_inc_9b60992d (SOP-LOG-MER-02, Gear Systems Meridian).

Task: Maribel Ortiz flagged in #receiving-dock (04/14/2026) that the HW-3305 re-inspection on REC-20260407-003
found impact damage on 12 of 800 lock nuts (Coastal Fasteners, received 04/07/2026, still in HW-1 Bin 1D).
That is Tier 4 concealed damage (Section 11.7). The receipt is 5 business days old, inside the 10-business-day
window, so step 4 of 11.7.1 applies: request photos and a detailed description from the reporter with
Template 31 (General Internal Request, printed in the SOP PDF). Per the instruction this goes to Maribel by
email, nothing beyond Maribel's issue is handled, and steps 5+ ("Once received, ...") wait for her reply.
"""

from __future__ import annotations

import re

from ..kit import (COMM_KINDS, Action, Comm, Context, World, comm_rules, dashes, forbid_writes, nh,
                   no_placeholders, norm, num, pre_rule, state_rule, strict_writes, text_of, world)

MARIBEL = "maribel.ortiz@gearsystems.com"
MARIBEL_POST_TS = "1776183000.001350"
REC = "REC-20260407-003"
OURS = re.compile(r"REC-?20260407-?003|HW-?3305|MER-PO-HIST-05|lock\s*nuts?", re.I)
OTHER = re.compile(
    r"NCR-2026-00(?:28|31|33|34|35|36)|NCR-2026-HIST|YF-CLM-88214|"
    r"REC-20260(?:225-009|318-004|331-001|401-007|404-002|409-00[56]|410-001|414-00\d)|"
    r"MER-PO-(?:8812|8813|8790|8833|8845|8830|8860|8870|8880|8820|8821|8822|HIST-0[1-46]|HIST-AX)\b|"
    r"APPT-2026\d{4}-\d{3}|AUDIT RESPONSE|END-OF-SHIFT HANDOFF|DAILY DOCK PREVIEW", re.I)
ALLOWED_DOMAINS = ("gearsystems.com", "coastalfasteners.com", "rlcarriers.com")
INSTR = ("instruction", "", "Task instruction")

R_DETECT = ("11.7.1", "2. The Coordinator opens receiving_log.xlsx and locates the original receipt", "11.7.1 step 2")
R_WINDOW = ("11.7.1", "3. Calculate the number of business days between the receipt date and today.", "11.7.1 step 3")
R_T4_WIN = ("11.7", "Tier 4 damage is discovered after the receipt has been completed", "11.7")
R_REQ = ("11.7.1", "4. If within the window, request photos and a detailed description", "11.7.1 step 4")
R_ONCE = ("11.7.1", "5. Once received, create a new row in receiving_log.xlsx", "11.7.1 step 5")
R_T4ROW = ("11.7.1", "6. Set Condition_Tier to Tier 4", "11.7.1 step 6")
R_POSTED = ("13.1", "SKU The actual SKU received", "13.1")
R_NO_OVERWRITE = ("13.5.1", "1. Do not delete or overwrite the original row.", "13.5.1 step 1")
R_NO_EDIT = ("13.6.1", "1. Do not edit the original row.", "13.6.1 step 1")
R_P6 = ("21.2", "6. Do not edit or overwrite a posted receiving log row.", "21.2 #6")
R_P7 = ("21.2", "7. Do not delete records of any kind.", "21.2 #7")
R_MAIL_DEL = ("18.5.2", "Do not delete any email without supervisor approval.", "18.5.2")
R_SLACK_DEL = ("21.3", "13. Do not delete or move a Slack post", "21.3 #13")
R_RETAIN = ("19.1", "The retention windows below are mandatory.", "19.1")
R_SM_OWNER = ("5.1", "supplier_master.xlsx — Owner: Joon-ho Park", "5.1")
R_RO = ("5.3", "Read-only for the Coordinator: supplier_master.xlsx", "5.3")
R_INV = ("5.3", "The Coordinator can update receipt and quarantine entries in inventory_master.xlsx", "5.3")
R_RW = ("5.3", "Read/write for the Coordinator: receiving_log.xlsx", "5.3")
R_STATUS = ("15", "Supplier status is owned by Procurement", "15")
R_NCR_CLOSE = ("14.8", "The Coordinator never marks an NCR as Resolved or Closed", "14.8")
R_QHOLD = ("21.4", "20. Do not move material out of Q-HOLD", "21.4 #20")
R_FILL = ("14.4.2", "3. Fill in every bracketed placeholder.", "14.4.2 step 3")
R_T23 = ("23", "This section contains every email template", "23")
R_T23B = ("23", "Sending a template with [Supplier Name]", "23")
R_PROMISE = ("21.3", "14. Do not promise a supplier any specific resolution", "21.3 #14")
R_COMMERCIAL = ("4.2", "Owns supplier_master.xlsx.", "4.2")
R_T31 = ("23", "Used when the Coordinator needs specific information, photos", "Template 31")
R_WAIT_PHOTOS = ("11.1", "The Coordinator must read all of these inputs before assigning a damage tier.", "11.1")
T4_ID = "REC-20260407-003-T4"


# ---- helpers -------------------------------------------------------------------------------------

def _cell(v) -> str:
    s = nh(v)
    if s.startswith("="):
        return "=f"
    n = num(s)
    if n is not None and not re.search(r"[A-Za-z]", s):
        return f"{n:.4f}"
    return norm(s)


def _changed_rows(w: World, book: str, header: str, skip=lambda r: False) -> list[dict]:
    """Initial rows (minus ``skip``) no longer present with the same values; number/formula tolerant."""
    init = [r for r in w.rows(book, header, "initial") if not skip(r)]
    if not init:
        return []
    keys = [k for k in init[0] if k != "__row__"]
    cur = [tuple(_cell(r.get(k)) for k in keys) for r in w.rows(book, header, "current")]
    gone = []
    for r in init:
        t = tuple(_cell(r.get(k)) for k in keys)
        if t in cur:
            cur.remove(t)
        else:
            gone.append(r)
    return gone


def _first(r: dict) -> str:
    return next((str(v) for k, v in r.items() if k != "__row__"), "")


def _maribel_replied(ctx: Context) -> bool:
    rx = re.compile(r'"from[_a-z]*"\s*:\s*"[^"]*maribel\.ortiz@|From:\s*[^\n]{0,60}maribel\.ortiz@', re.I)
    return any(rx.search(text or "") for _, text in ctx.state.reads)


def _external(a: Action) -> list[str]:
    return [x for x in a.recipients + a.cc if not x.lower().endswith(ALLOWED_DOMAINS)]


# ---- Template 31 request to Maribel (11.7.1 step 4) ------------------------------------------------

def _to_maribel(a: Action) -> bool:
    if a.kind not in ("email_send", "email_draft") or MARIBEL not in [x.lower() for x in a.recipients]:
        return False
    t = text_of(a)
    return bool(OURS.search(t) or re.search(r"Information Request|photos?\b|concealed|damage", t, re.I))


def _specs(ctx: Context) -> list[Comm]:
    return [Comm(
        key="t31_maribel", kind="email", about=_to_maribel, exact_to=False,
        what=f"Template 31 (General Internal Request) email to Maribel Ortiz requesting photos and a detailed "
             f"description of the HW-3305 concealed damage on {REC} (Tier 4, 5 business days post-receipt, "
             f"inside the 10-business-day window)",
        refs=[R_REQ, R_WINDOW, R_DETECT, R_T31],
        to=[MARIBEL],
        subject=r"Information Request\s*[-–—]\s*REC-20260407-003",
        subject_hint=f"Information Request — {REC}",
        body=[(r"REC-20260407-003", f"the receipt ID {REC}"),
              (r"I need the following to proceed with a receiving item",
               "the Template 31 opening 'I need the following to proceed with a receiving item. Please respond as "
               "soon as possible.'"),
              (r"This relates to", "the 'This relates to:' list (keep only the lines that apply)"),
              (r"Re-inspection completed today on REC-20260407-003|Discrepancy reported in #?receiving-dock for "
               r"REC-20260407-003", f"the applicable 'This relates to' line(s), e.g. 'Re-inspection completed today "
                                   f"on {REC}' and/or 'Discrepancy reported in #receiving-dock for {REC}'"),
              (r"Please provide", "the 'Please provide:' list"),
              (r"photos?\b", "'Photos of all affected units (all damage angles)'"),
              (r"written description", "'Written description: count of affected units, location and nature of "
                                       "damage, any other observations'"),
              (r"Needed to complete", "the 'Needed to complete:' list"),
              (r"receiving log amendment", "'Receiving log amendment' under Needed to complete")],
        banned=[(r"Inbound receipt under PO", f"Delete the 'Inbound receipt under PO #..., received today' line: "
                                              f"{REC} was received 04/07/2026, not today (Template 31: delete lines "
                                              "that do not apply)."),
                (r"In-progress NCR", "Delete the 'In-progress NCR' line: no NCR has been opened for this item "
                                     "(Template 31: delete lines that do not apply)."),
                (r"Document copy", "Delete the 'Document copy: COC / MTR / packing slip' line: HW-3305 is a "
                                   "standard part and only photos/description are needed (Template 31: delete lines "
                                   "that do not apply)."),
                (r"outside (?:of )?the 10[- ]business[- ]day", f"{REC} (received 04/07/2026) is 5 business days "
                                                                "old on 04/14/2026 - inside the 10-business-day "
                                                                "concealed damage window.")],
    )]


# ---- pre rules -----------------------------------------------------------------------------------

def _slack_to_maribel(ctx: Context, a: Action) -> str | None:
    if a.kind not in ("slack_post", "slack_dm"):
        return None
    w = world(ctx)
    if str(a.args.get("thread_ts") or "") == MARIBEL_POST_TS:
        return "Do not reply to Maribel's #receiving-dock post on Slack: the user asked that internal " \
               f"communications with Maribel be done by email ({MARIBEL})."
    if w.is_dm_to(a, "Maribel Ortiz"):
        return "Do not message Maribel on Slack: the user asked that internal communications with Maribel be " \
               f"done by email ({MARIBEL})."
    if re.search(r"<@U007>|@mortiz\b|@maribel", a.text or "", re.I):
        return "Do not @-mention Maribel on Slack: the user asked that internal communications with Maribel be " \
               f"done by email ({MARIBEL})."
    return None


def _scope_comms(ctx: Context, a: Action) -> str | None:
    if a.kind not in COMM_KINDS + ("calendar_create", "calendar_update"):
        return None
    ext = _external(a) if a.kind in ("email_send", "email_draft") else []
    if ext:
        return (f"Recipient(s) {', '.join(ext)} are not part of Maribel's HW-3305 issue ({REC}, Coastal Fasteners / "
                "R&L Carriers). The user said: \"Don't handle anything else beyond the issue reported by Maribel.\"")
    t = text_of(a)
    m = OTHER.search(t)
    if m and not OURS.search(t):
        return (f"This message is about {m.group(0)}, not Maribel's HW-3305 concealed-damage issue ({REC}). The "
                "user said: \"Don't handle anything else beyond the issue reported by Maribel.\"")
    return None


def _scope_writes(ctx: Context, a: Action) -> str | None:
    if a.kind != "workbook_write" or not strict_writes(a):
        return None
    t = a.code or a.text
    m = OTHER.search(t)
    if m and not OURS.search(t):
        return (f"This workbook edit concerns {m.group(0)}, not Maribel's HW-3305 issue ({REC}). The user said: "
                "\"Don't handle anything else beyond the issue reported by Maribel.\"")
    return None


def _t31_internal(ctx: Context, a: Action) -> str | None:
    if a.kind not in ("email_send", "email_draft") or not re.search(r"Information Request", a.subject, re.I):
        return None
    ext = [x for x in a.recipients + a.cc if not x.lower().endswith("gearsystems.com")]
    return (f"Template 31 (General Internal Request) is not for supplier-facing requests; remove {', '.join(ext)}. "
            f"Send it to Maribel Ortiz ({MARIBEL}) only.") if ext else None


def _window(ctx: Context, a: Action) -> str | None:
    if a.kind not in COMM_KINDS:
        return None
    t = dashes(text_of(a))
    if OURS.search(t) and re.search(r"outside (?:of )?the 10[- ]business[- ]day|cannot be claimed against the "
                                    r"supplier", t, re.I):
        return (f"{REC} was received 04/07/2026; on 04/14/2026 that is 5 business days, inside the "
                "10-business-day concealed damage window. Do not tell anyone it is outside the window.")
    return None


def _t4_gate(ctx: Context, a: Action) -> str | None:
    if a.kind != "workbook_write" or "receiving_log.xlsx" not in strict_writes(a):
        return None
    if not re.search(r"20260407-003-T4|-T4\b|Tier 4", a.code or a.text, re.I):
        return None
    if _maribel_replied(ctx):
        return None
    return (f"Section 11.7.1 step 5: the Tier 4 amendment row ({REC}-T4) is created only once the photos and "
            "detailed description requested from Maribel (step 4, Template 31) have been received - no reply from "
            f"her is on file yet. Never edit the posted original row {REC} either; leave receiving_log.xlsx as is "
            "for now.")


DEL_TARGET = re.compile(
    r"(?:os\.remove|os\.unlink|shutil\.rmtree)\s*\(\s*[^)\n]*?([\w./\\-]+\.(?:xlsx|pdf|docx))"
    r"|[\"']([^\"'\n]+\.(?:xlsx|pdf|docx))[\"']\s*\)\s*\.unlink\("
    r"|(?:^|[;&|\s])rm\s+(?:-\w+\s+)*([^\n;&|]*?\.(?:xlsx|pdf|docx))", re.I)
LOGS = {"receiving_log.xlsx", "ncr_log.xlsx"}


def _record_deletes(a: Action) -> list[str]:
    if a.tool in ("syntara__deleteFile", "syntara__removeFile"):
        hits = [str(a.args.get("file_path") or a.args.get("path") or "")]
    else:
        hits = [next(g for g in m.groups() if g) for m in DEL_TARGET.finditer(a.text or "")]
    # SOP 14.4.2 step 5 itself deletes the NCR _draft.docx working copy; scratch files are not records.
    return [h for h in hits if re.search(r"\.(xlsx|pdf|docx)$", h.strip(), re.I)
            and not re.search(r"_draft\.docx$|^/?tmp/", h.strip(), re.I)]


def _no_delete(ctx: Context, a: Action) -> str | None:
    if a.kind == "email_delete":
        return "Do not delete emails (Section 18.5.2: no deletion without supervisor approval; Section 21.2 #7)."
    if a.tool.startswith("slack__") and "delete" in a.tool:
        return "Do not delete Slack posts; post a correction reply instead (Section 21.3 #13)."
    if a.kind == "workbook_write" and re.search(r"\.delete_rows\(", a.code or a.text or ""):
        w = strict_writes(a)
        if w and w <= LOGS:
            return f"Do not delete rows from {', '.join(sorted(w))} (Section 21.2 #7: records are never deleted; " \
                   "posted rows are corrected only by adding new rows)."
    if a.kind in ("file_delete", "workbook_write"):
        hit = _record_deletes(a)
        if hit:
            return f"Do not delete workspace records ({', '.join(hit)}) (Section 21.2 #7, Section 19.1)."
    return None


PROMISE = re.compile(r"\b(?:we|I)\s+(?:will|can|shall|are able to)\s+(?:be\s+)?(?:issu|provid|offer|grant|approv|"
                     r"authori[sz]|process|accept)\w*\s+(?:you\s+)?(?:a\s+|an\s+|the\s+|full\s+|your\s+)?"
                     r"(?:credit|refund|replacement|return authori[sz]ation|price adjustment|rework)", re.I)


def _promise(ctx: Context, a: Action) -> str | None:
    if a.kind not in ("email_send", "email_draft"):
        return None
    if all(x.lower().endswith("gearsystems.com") for x in a.recipients + a.cc):
        return None
    m = PROMISE.search(dashes(a.text))
    return (f"Do not promise a supplier/carrier a specific resolution (\"{m.group(0)}\"); resolution is Procurement's "
            "or Quality's call.") if m else None


# ---- completion rules ----------------------------------------------------------------------------

def _records(ctx: Context):
    w = world(ctx)
    gone = _changed_rows(w, r"receiving_log", r"^Receipt_ID$")
    yield (not gone, "receiving_log.xlsx rows are posted records and must not be edited or removed: "
                     f"{', '.join(_first(r) for r in gone[:6])} changed. Restore their original values; record any "
                     "Tier 4 finding only as a new REC-[ID]-T4 row once Maribel's photos/description arrive.",
           [R_P6, R_NO_OVERWRITE, R_NO_EDIT, R_POSTED, R_ONCE])
    new = [_first(r) for r in w.new_rows(r"receiving_log", r"^Receipt_ID$")]
    extra = [x for x in new if norm(x) != norm(T4_ID)]
    yield (not extra, f"Unrequested new receiving_log.xlsx row(s): {', '.join(extra[:6])}. The only row the SOP adds "
                      f"for Maribel's issue is the Tier 4 amendment {T4_ID} (11.7.1 step 5, after her photos/"
                      "description arrive); no correction rows for posted receipts (13.6.1). Remove them.",
           [R_ONCE, R_NO_EDIT, INSTR])
    early = len(new) > len(extra) and not _maribel_replied(ctx)
    yield (not early, f"{T4_ID} was added before Maribel's photos and detailed description were received. Section "
                      "11.7.1 step 5 creates it only 'once received' - remove it for now.", [R_ONCE, R_WAIT_PHOTOS])
    gone = _changed_rows(w, r"ncr_log", r"^NCR_Number$")
    yield (not gone, f"ncr_log.xlsx existing NCR rows changed ({', '.join(_first(r) for r in gone[:6])}). They are "
                     "not part of Maribel's issue and the Coordinator never changes NCR status/closure on their own "
                     "judgment - restore the original values.", [R_NCR_CLOSE, INSTR])
    gone = _changed_rows(w, r"inventory_master", r"^SKU$",
                         skip=lambda r: norm(r.get("SKU")) in ("hw-3305",) or norm(r.get("SKU")).startswith("total"))
    yield (not gone, "inventory_master.xlsx rows other than HW-3305 changed "
                     f"({', '.join(_first(r) for r in gone[:6])}). Only the HW-3305 (Maribel's issue) receipt/"
                     "quarantine entries may be touched; restore the others, including any Q-HOLD material.",
           [R_INV, R_QHOLD, INSTR])
    gone = _changed_rows(w, r"open_pos", r"^PO_Number$")
    yield (not gone, f"open_pos.xlsx PO data changed ({', '.join(_first(r) for r in gone[:6])}). PO data is "
                     "read-only for the Coordinator - restore it.", [R_RW])


RULES = (
    comm_rules("iw.t31", _specs)
    + pre_rule("iw.maribel_email_only", _slack_to_maribel, [INSTR], "Email Maribel instead (maribel.ortiz@gearsystems.com).")
    + pre_rule("iw.scope_comms", _scope_comms, [INSTR], "Only handle Maribel's HW-3305 / REC-20260407-003 issue.")
    + pre_rule("iw.scope_writes", _scope_writes, [INSTR], "Only handle Maribel's HW-3305 / REC-20260407-003 issue.")
    + pre_rule("iw.t31_internal", _t31_internal, [R_T31], "Address the Template 31 request to Maribel only.")
    + pre_rule("iw.window", _window, [R_WINDOW, R_T4_WIN], "Treat REC-20260407-003 as inside the window (Template 31 request).")
    + pre_rule("iw.t4_gate", _t4_gate, [R_ONCE, R_T4ROW, R_WAIT_PHOTOS, R_P6], "Wait for Maribel's photos and description first.")
    + pre_rule("iw.no_delete", _no_delete, [R_P7, R_MAIL_DEL, R_SLACK_DEL, R_RETAIN], "Do not delete records.")
    + pre_rule("iw.no_promise", _promise, [R_PROMISE, R_COMMERCIAL], "Document and escalate; do not promise a resolution.")
    + forbid_writes("iw.readonly", r"supplier_master\.xlsx|closed_pos_archive\.xlsx",
                    "read-only for the Coordinator (supplier status is owned by Procurement).", [R_RO, R_SM_OWNER, R_STATUS])
    + no_placeholders([R_FILL, R_T23, R_T23B])
    + state_rule("iw.records_unchanged", _records, "Restore the original rows.")
)
