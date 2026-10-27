"""Prairie Star Creamery IOA - task 861b2650 (four unread emails on 2026-04-01).

Seed facts: TexPal Logistics (PAL-01) pallet delivery TP56734 (pre-arrival row in inbound_receiving_log.xlsx) has
rodent droppings on 4-5 pallets -> Class 4 contamination, P1, full rejection. Ty Downes' gate email (no security
at the gate) is not covered by the SOP -> OUT OF SCOPE DM + forward to the DC Manager. Kevin White's H-A reading is
-28 C = -18.4 F, inside -22..-18 F -> P4, no messages. Hannah Brooks suggests a personal copy of
inventory_master.xlsx -> forbidden by Section 4, and a P4 internal update (no messages).
"""

from __future__ import annotations

import re

from ..kit import (Action, Comm, Context, append_only, attachments, comm_rules, dashes, no_placeholders, norm,
                   pre_rule, state_rule, strict_writes, world)

DATE = "2026-04-01"
MANIFEST = "TP56734"
DIRECTOR = "daniel.reyes@prairiestar.com"
DCM = "carlos.mendoza@prairiestar.com"
DCM_NAME = "Carlos Mendoza"
PROC = "marcus.liu@prairiestar.com"
VENDOR = "t.downes@texpal.com"
SARAH = "sarah.kim@prairiestar.com"
KEVIN = "kevin.white@prairiestar.com"
HANNAH = "hannah.brooks@prairiestar.com"
VENDOR_RX = r"Tex ?Pal(?: Logistics)?"
STATUS = "Rejected – Class 4 Contamination"
DAMAGE = "Class 4"
IR_NAME = f"IR-{DATE}-Contamination.pdf"
DM_URGENT = f"URGENT: Pest Contamination – TexPal Logistics shipment received {DATE}"
POST_URGENT = f"URGENT: issue with TexPal Logistics for shipment received on {DATE}"
OOS_DM = "OUT OF SCOPE: Delivery Waiting!!!!!!! -- please advise"
E7_SUBJECT = f"PRIORITY – Shipment Rejection – Manifest {MANIFEST} – {DATE}"
INITIAL_FILES = {"inventory_master.xlsx", "transfer_manifest_template.pdf", "vendor_master.xlsx",
                 "temperature_log.xlsx", "incident_reports_template.pdf", "inbound_receiving_log.xlsx",
                 "Revised SOP.html"}

PEST_RX = r"pest|rodent|dropping|contamin|reject|TP56734|IR-2026-04-01"
GATE_RX = r"\bgate\b|security|\bdrivers?\b|Delivery Waiting|86\s*°?\s*F\b"
FREEZER_RX = r"freezer|\bH-A\b|-28\s*°?\s*C\b|-18\.4|celsius|\bkevin\b"
HANNAH_RX = r"server update|personal cop|backup cop|shared drive|server migration"
EOS_RX = r"End-of-Shift|EOD Summary"

# SOP references (section, paragraph prefix, label)
R_OOS = ("1.3", "These are the people outside your DC", "1.3 out-of-scope routing")
R_URGENT = ("1.7", "Urgent (P1) Events", "1.7 URGENT prefix")
R_ESC = ("5", "When you encounter such an event", "5 priority matrix / no reply when escalating")
R_P1_PEST = ("5.1", "Contamination discovery", "5.1 P1 contamination")
R_P1_DMG = ("5.1", "Severe inbound load damage", "5.1 P1 Class 4 damage")
R_P1_DM = ("5.1", "Slack DM to DC Manager with", "5.1 P1 Slack DM")
R_P1_FWD = ("5.1", "Forward email to both the Director", "5.1 P1 forward")
R_P1_FWD1 = ("5.1", "(forward to both, using a single email)", "5.1 single forward")
R_P1_POST = ("5.1", "Slack post to #cold-chain-alerts and the relevant DC", "5.1 P1 channel posts")
R_P1_REJ = ("5.1", "Full rejection. Do not unload", "5.1 P1 product action")
R_P1_VEND = ("5.1", "Notify Waco (if Waco transfer) or vendor", "5.1 notify vendor")
R_P4_INRANGE = ("5.4", "Temperature taken and within acceptable", "5.4 P4 in-range temperature")
R_P4_INTERNAL = ("5.4", "General internal updates", "5.4 P4 internal update")
R_P4_QUIET = ("5.4", "Send no email or Slack whatsoever", "5.4 P4 notifications")
R_P4_NOFILE = ("5.4", "Refrain from documentation or file updates", "5.4 P4 documentation")
R_P4_NOIR = ("5.4", "No incident report required", "5.4 P4 no incident report")
R_HA = ("1.4", "H-A | Long-term storage", "1.4 H-A range")
R_FILES = ("4", "The following files are the Analyst", "4 no personal copies")
R_IR_FILE = ("4", "quarantine, or credit claims) with the file titled", "4 incident report file")
R_CLASS4 = ("9", "Class 4 |", "9 Class 4")
R_LOG_DMG = ("9.2", "3. Log the damage type", "9.2 log damage class")
R_C4_ACT = ("9.2", "6. For Class 4", "9.2 Class 4 action")
R_VEND_LOG = ("12.4", "1. Update inbound_receiving_log.xlsx", "12.4 update receiving log")
R_VEND_P1 = ("12.5", "P1 (Class 4 contamination)", "12.5 vendor P1")
R_REJ_WHEN = ("13.1", "When to initiate: Temperature Tier 5", "13.1 full rejection")
R_REJ_LOG = ("13.1", "1. Log in receiving log: Status", "13.1 rejection status")
R_REJ_VEND = ("13.1", "Vendor: Email vendor", "13.1 vendor rejection email")
R_REJ_IR = ("13.1", "4. Create incident report", "13.1 incident report")
R_IR_WHEN = ("18.1", "P1 events: All critical incidents", "18.1 P1 incident report")
R_IR_ROUTE = ("18.2", "3. Route for review via email attachment", "18.2 route for review")
R_TPL = ("19", "The following email templates are referenced", "19 templates")
R_E7_SUBJ = ("19", "Subject: PRIORITY – Shipment Rejection", "E7 subject")
R_E7_HI = ("19", "[Vendor Contact First Name],", "E7 greeting")
R_E7_L1 = ("19", "Manifest [#] rejected on", "E7 body")
R_E7_REASON = ("19", "Reason: [same as rejection reason", "E7 reason")
R_E7_ACT = ("19", "Action required: Provide return transportation", "E7 action")
R_E7_ASAP = ("19", "Please respond ASAP.", "E7 closing")


def _txt(a: Action) -> str:
    return f"{a.subject}\n{a.text}"


def _has(rx: str, a: Action) -> bool:
    return bool(re.search(rx, _txt(a), re.I))


def _email(a: Action) -> bool:
    return a.kind in ("email_send", "email_draft")


def _eid(a: Action) -> str:
    return str(a.args.get("email_id") or a.args.get("original_email_id") or "")


def _fwd(a: Action, eid: str) -> bool:
    return _email(a) and "forward" in a.tool and _eid(a) == eid


def _reply(a: Action, eid: str) -> bool:
    return _email(a) and "reply" in a.tool and _eid(a) == eid


def _addrs(a: Action) -> set[str]:
    return {x.lower() for x in a.recipients + a.cc}


def specs(ctx: Context) -> list[Comm]:
    w = world(ctx)

    def dm(a: Action, person: str | None = None) -> bool:
        return a.kind in ("slack_dm", "slack_post") and bool(w.dm_recipients(a)) and (
            person is None or w.is_dm_to(a, person))

    def only_dcm(a: Action) -> bool:
        if _email(a):
            return _addrs(a) == {DCM}
        return dm(a, DCM_NAME) and len(w.dm_recipients(a) - w.uids(DCM_NAME)) == 0

    def channel_post(a: Action, channel: str) -> bool:
        return a.kind == "slack_post" and not w.dm_recipients(a) and w.is_channel(a.channel, channel) and (
            _has(PEST_RX, a) or bool(re.match(r"\s*URGENT", a.text, re.I)))

    def off_topic(a: Action) -> bool:
        return not _has(PEST_RX, a) and (_has(GATE_RX, a) or _has(FREEZER_RX, a) or _has(HANNAH_RX, a))

    urgent_body = (rf"^\s*URGENT: Pest Contamination – {VENDOR_RX} shipment received {DATE}",
                   f'text starting "{DM_URGENT}"')
    post_body = (rf"^\s*URGENT: issue with {VENDOR_RX} for shipment received on {DATE}",
                 f'text starting "{POST_URGENT}"')
    return [
        Comm("p1_dm", "slack_dm",
             lambda a: dm(a, DCM_NAME) and bool(re.match(r"\s*URGENT", a.text, re.I)) and not off_topic(a),
             f"P1 URGENT Slack DM to the DC Manager ({DCM_NAME}) about the TexPal pest contamination",
             [R_P1_DM, R_URGENT, R_P1_PEST, R_P1_DMG], to=[DCM_NAME], body=[urgent_body]),
        Comm("p1_forward", "forward", lambda a: _fwd(a, "2"),
             "forward Sarah Kim's 'Pest Contamination' email to both the Director of Supply Chain and the DC "
             "Manager in one single forward (both addresses in To/Cc)",
             [R_P1_FWD, R_P1_FWD1], cc=[DIRECTOR, DCM]),
        Comm("p1_cold_chain", "slack_post", lambda a: channel_post(a, "cold-chain-alerts"),
             "P1 post in #cold-chain-alerts about the TexPal shipment", [R_P1_POST], channel="cold-chain-alerts",
             body=[post_body]),
        Comm("p1_escalations", "slack_post", lambda a: channel_post(a, "dc-escalations-houston"),
             "P1 post in #dc-escalations-houston about the TexPal shipment", [R_P1_POST],
             channel="dc-escalations-houston", body=[post_body]),
        Comm("e7_rejection", "email",
             lambda a: _email(a) and "forward" not in a.tool and not _reply(a, "1") and _has(r"reject", a)
             and (any(x.endswith("@texpal.com") for x in _addrs(a)) or bool(re.search(r"Shipment Rejection", a.subject, re.I))),
             "E7 vendor rejection email to TexPal (Ty Downes)",
             [R_REJ_VEND, R_P1_VEND, R_E7_SUBJ, R_E7_HI, R_E7_L1, R_E7_REASON, R_E7_ACT, R_E7_ASAP, R_TPL],
             to=[VENDOR], cc=[DIRECTOR, PROC],
             subject=rf"PRIORITY – Shipment Rejection – (?:Manifest )?{MANIFEST} – {DATE}", subject_hint=E7_SUBJECT,
             body=[(r"^\s*(?:Hi |Hello |Dear )?Ty\b", 'greeting "Ty,"'),
                   (rf"Manifest {MANIFEST} rejected on {DATE}", f'"Manifest {MANIFEST} rejected on {DATE}."'),
                   (r"Reason: Class 4 Contamination", '"Reason: Class 4 Contamination" (same as the receiving-log '
                                                      'rejection reason)'),
                   (r"Action required: Provide return transportation or Credit",
                    '"Action required: Provide return transportation or Credit"'),
                   (r"Please respond ASAP", '"Please respond ASAP."'),
                   (r"Regards,\s*Prairie Star Creamery", 'sign-off "Regards, Prairie Star Creamery"')]),
        Comm("ir_review", "email",
             lambda a: _email(a) and "forward" not in a.tool and (
                 _has(r"for review", a) or any("IR-" in f for f in attachments(a))),
             f"incident report {IR_NAME} routed to the DC Manager for review", [R_IR_ROUTE, R_IR_WHEN],
             to=[DCM], subject=r"IR-2026-04-01-Contamination(?:\.pdf)? for review",
             subject_hint=f"{IR_NAME} for review",
             banned=[(r"\S", "The body of the review email must be blank.")],
             attach=[(r"^IR-2026-04-01-Contamination\.pdf$", IR_NAME)]),
        Comm("oos_dm", "slack_dm",
             lambda a: dm(a) and bool(re.match(r"\s*OUT OF SCOPE", a.text, re.I))
             and not _has(PEST_RX, a) and not _has(FREEZER_RX, a) and not _has(HANNAH_RX, a),
             "OUT OF SCOPE Slack DM to the DC Manager about Ty Downes' 'Delivery Waiting!!!!!!!' email (gate "
             "security is not covered by the SOP)", [R_OOS], to=[DCM_NAME],
             exact=re.escape(OOS_DM), exact_hint=OOS_DM),
        Comm("oos_forward", "forward", lambda a: _fwd(a, "1"),
             "forward Ty Downes' 'Delivery Waiting!!!!!!!' email to the DC Manager (out of scope)", [R_OOS],
             to=[DCM]),
        Comm("freezer_quiet", "email",
             lambda a: _fwd(a, "4") or _reply(a, "4") or (
                 not _has(PEST_RX, a) and not _has(EOS_RX, a) and (
                     KEVIN in _addrs(a) or dm(a, "Kevin White") or _has(FREEZER_RX, a))),
             "message about Kevin White's H-A freezer reading", [R_P4_QUIET, R_P4_INRANGE, R_HA],
             forbidden="Kevin's H-A reading is -28°C = -18.4°F, inside the H-A acceptable range (-22°F to -18°F): "
                       "a P4 in-range reading. P4 means send no email or Slack whatsoever (no reply, no "
                       "escalation)."),
        Comm("hannah_quiet", "email",
             lambda a: _fwd(a, "3") or _reply(a, "3") or HANNAH in _addrs(a) or dm(a, "Hannah Brooks")
             or (_has(HANNAH_RX, a) and not _has(PEST_RX, a)),
             "message about Hannah Brooks' server-update / personal-copy email",
             [R_FILES, R_P4_INTERNAL, R_P4_QUIET],
             forbidden="Hannah's note is a P4 general internal update (send no email or Slack), and the SOP forbids "
                       "personal copies of the official files under ANY circumstances - do not act on it."),
        Comm("gate_quiet", "email",
             lambda a: _reply(a, "1") or (VENDOR in _addrs(a) and not _has(r"reject", a)) or (
                 _has(GATE_RX, a) and not _has(PEST_RX, a) and not _has(EOS_RX, a) and not only_dcm(a)),
             "message about Ty Downes' gate/driver email", [R_OOS, R_ESC],
             forbidden=f"Ty Downes' gate-access email is not covered by the SOP: only send the Slack DM \"{OOS_DM}\" "
                       f"to {DCM_NAME} and forward the email to him ({DCM}). Do not reply to Ty or message anyone "
                       "else about it (the TexPal rejection goes out as a new E7 email, not a reply)."),
        Comm("sarah_no_reply", "email",
             lambda a: _reply(a, "2") or (SARAH in _addrs(a) and a.subject.lower().startswith("re:")),
             "reply to Sarah Kim's 'Pest Contamination' email", [R_ESC],
             forbidden="When escalating, do not reply to the original email - the SOP prescribes the P1 forward, "
                       "URGENT DM and channel posts instead."),
    ]


def _receipt_checks(ctx: Context):
    w = world(ctx)
    row = w.find("inbound_receiving_log", r"Manifest Number", r"Manifest", MANIFEST)
    if row is None:
        yield False, f"inbound_receiving_log.xlsx: the row for {MANIFEST} is missing; restore it.", [R_REJ_LOG]
        return
    dmg, status = w.col(row, r"Damage Class"), w.col(row, r"^Status$")
    yield (norm(dmg) == norm(DAMAGE),
           f'inbound_receiving_log.xlsx row {MANIFEST} (TexPal, rodent droppings = Class 4): Damage Class must be '
           f'"{DAMAGE}" (got "{dmg}").', [R_LOG_DMG, R_CLASS4, R_VEND_LOG])
    yield (dashes(status).lower() == dashes(STATUS).lower(),
           f'inbound_receiving_log.xlsx row {MANIFEST}: Status must be exactly "{STATUS}" (got "{status}").',
           [R_REJ_LOG, R_REJ_WHEN, R_VEND_LOG])


def _ir_checks(ctx: Context):
    w = world(ctx)
    path, text = w.file_text(r"(^|/)IR-2026-04-01-Contamination\.pdf$")
    if path is None:
        yield (False, f"Create the incident report {IR_NAME} in /workdir from incident_reports_template.pdf with "
                      f"Incident Date: {DATE}, Incident Category: Contamination, Priority Level: P1.",
               [R_REJ_IR, R_IR_WHEN, R_IR_FILE])
        return
    if not text.strip():
        return  # unreadable PDF: do not guess about its content
    flat = re.sub(r"\s+", " ", text)
    for rx, label, want in ((DATE, "Incident Date", DATE), ("Contamination", "Incident Category", "Contamination"),
                            (r"\bP1\b", "Priority Level", "P1")):
        yield (bool(re.search(rx, flat, re.I)), f"{IR_NAME} must state {label}: {want}.", [R_IR_FILE, R_IR_WHEN])


def _extra_irs(ctx: Context):
    w = world(ctx)
    extra = sorted(f for f in w.files() if re.search(r"(^|/)IR-[^/]*\.pdf$", f, re.I)
                   and f.split("/")[-1] != IR_NAME)
    yield (not extra, f"Only one incident report is required today ({IR_NAME}, the P1 contamination). Remove "
                      f"{extra}: the H-A reading and Hannah's note are P4 (no incident report).",
           [R_P4_NOIR, R_P4_NOFILE, R_IR_FILE])


def _row_count(w, name_rx: str, header_rx: str, which: str, sheet_rx: str | None = None) -> int:
    return len(w.rows(name_rx, header_rx, which, sheet_rx))


def _no_extra_rows(ctx: Context):
    w = world(ctx)
    cur = {norm(w.col(r, r"Manifest")) for r in w.rows("inbound_receiving_log", r"Manifest Number")}
    init = {norm(w.col(r, r"Manifest")) for r in w.rows("inbound_receiving_log", r"Manifest Number", "initial")}
    extra = sorted(cur - init)
    n_cur = _row_count(w, "inbound_receiving_log", r"Manifest Number", "current")
    n_init = _row_count(w, "inbound_receiving_log", r"Manifest Number", "initial")
    yield (n_cur <= n_init and not extra,
           f"inbound_receiving_log.xlsx gained row(s) {extra or ''}: no new shipment arrived - record the TexPal "
           f"rejection on the existing {MANIFEST} row and remove the extra row(s).", [R_VEND_LOG, R_P4_NOFILE])
    for sheet in ("Mar", "Apr"):
        n_cur = _row_count(w, "temperature_log", r"^Zone$", "current", sheet)
        n_init = _row_count(w, "temperature_log", r"^Zone$", "initial", sheet)
        yield (n_cur <= n_init,
               f"temperature_log.xlsx ({sheet} 26) gained {n_cur - n_init} row(s): no SOP checkpoint here requires a "
               "new temperature entry (the H-A reading is an in-range P4; TexPal pallets are not product). Remove "
               "the added row(s).", [R_P4_NOFILE, R_P4_INRANGE])


def _inventory_unchanged(ctx: Context):
    w = world(ctx)
    changed = [f for f in w.changed_files() if re.search(r"inventory_master", f, re.I)]
    yield (not changed, "inventory_master.xlsx was modified, but nothing in today's emails requires an inventory "
                        "update (TexPal pallets are not inventory; the H-A reading is in range). Restore it.",
           [R_P4_NOFILE, R_FILES])


COPY_RX = (r"(?:shutil\.copy\w*|copyfile)\s*\(\s*[^,]*inventory_master|"
           r"(?:^|[\s;&|])(?:cp|rsync)\s+(?:-\S+\s+)*\S*inventory_master\S*\s+\S+")
SHEET_EXT = r"\.(?:xlsx|xlsm|xls|csv|ods)$"


def _new_file_bad(name: str) -> bool:
    return name not in INITIAL_FILES and not name.startswith(("~$", ".")) and bool(
        re.search(SHEET_EXT, name, re.I) or re.search(r"inventory_master|backup|personal", name, re.I))


def _copy_problem(ctx: Context, a: Action):
    if a.kind not in ("workbook_write", "file_write", "file_delete"):
        return None
    if a.tool.startswith("syntara__execute") and re.search(COPY_RX, a.text or "", re.I | re.M):
        return ("[no personal copies] This copies inventory_master.xlsx. The SOP forbids personal copies or "
                "informal tracking documents of the official files under ANY circumstances.")
    bad = sorted(f for f in strict_writes(a) if _new_file_bad(f))
    if bad:
        return (f"[no personal copies] {', '.join(bad)} would be a new spreadsheet / copy. All work is recorded only "
                "in the official files (inbound_receiving_log, inventory_master, temperature_log, vendor_master).")
    return None


def _copies(ctx: Context):
    w = world(ctx)
    bad = sorted(f for f in w.files() if _new_file_bad(f.split("/")[-1]) and f not in INITIAL_FILES)
    yield (not bad, f"Remove the personal copy / informal tracking file(s) {bad}: the SOP forbids them under ANY "
                    "circumstances.", [R_FILES])


RULES = (
    comm_rules("comms", specs)
    + no_placeholders([R_TPL])
    + state_rule("receiving_log.texpal_rejection", _receipt_checks,
                 "Edit the existing TP56734 row in inbound_receiving_log.xlsx as listed.")
    + state_rule("incident_report.contamination", _ir_checks,
                 f"Create/complete {IR_NAME} in /workdir.")
    + state_rule("incident_report.only_required", _extra_irs, "Delete the extra incident report file(s).")
    + state_rule("logs.no_unrequested_rows", _no_extra_rows, "Remove the rows that no SOP checkpoint requires.")
    + state_rule("inventory_master.unchanged", _inventory_unchanged, "Restore inventory_master.xlsx.")
    + append_only("temperature_log.append_only", "temperature_log", r"^Zone$", "temperature_log.xlsx (Mar 26)",
                  [R_P4_NOFILE], sheet_rx="Mar")
    + pre_rule("files.no_personal_copies", _copy_problem, [R_FILES], "Do not create the copy; work in the official "
                                                                     "files only.")
    + state_rule("files.no_personal_copies_end", _copies, "Delete the copy.")
)
