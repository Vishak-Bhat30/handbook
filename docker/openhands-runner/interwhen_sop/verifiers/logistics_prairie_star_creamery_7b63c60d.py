"""SOP verifiers for logistics_prairie_star_creamery_7b63c60d (Houston DC, Waco manifest 2026-05-20-001).

Seed facts: manifest 480 cases / 24 pallets of SC-003 lot A-20260519-01; crew reports 474 cases, 24 pallets,
temps -6.0 / -4.5 / -7.5 F, seal intact, lot matches, no damage. Warmest -4.5 rounds to -4 -> Tier 3 (P3);
variance 474 - 480 = -6 cases (-1.25%) -> Moderate (P3). Two P3 events on one shipment -> compound P2 (SOP 5.5):
one compound email to the Director (cc DC Manager, Production Planner), a P2 post in #dc-escalations, receiving-log
status "P2 – Compound event.", product held in H-Q. Other files are handled by the user (instruction).
"""

from __future__ import annotations

import re

from ..kit import (COMM_KINDS, Comm, World, comm_rules, dashes, forbid_writes, no_placeholders, norm, num, pre_rule,
                   same, state_rule, text_of, world)

MANIFEST = "2026-05-20-001"
DATE = "2026-05-20"
DIRECTOR = "daniel.reyes@prairiestar.com"
DC_MANAGER = "carlos.mendoza@prairiestar.com"
PLANNER = "jacob.patel@prairiestar.com"
LOT = "A-20260519-01"
TEMPS = (-6.0, -4.5, -7.5)
STATUS = "P2 – Compound event."
LOG = r"inbound_receiving_log\.xlsx$"
HDR = r"^Manifest"

R_COMPOUND = ("5.5", "Compound events: If a single shipment has two P3 events", "5.5 compound events")
R_TIER3 = ("6.2", "Tier 3 | -4°F to 0°F", "6.2 Tier 3")
R_ROUND = ("6.1", "5. Decimal readings: round to the nearest whole degree", "6.1 rounding")
R_WARMEST = ("6.1", "4. The warmest of the three readings is the controlling", "6.1 controlling reading")
R_MODERATE = ("7.2", "4–10 cases | OR 1–3% | Moderate", "7.2 moderate variance")
R_VAR_CALC = ("7.1", "Absolute variance = Actual cases – Manifest cases", "7.1 variance calculation")
R_P2_EMAIL = ("5.2", "Email to the Director of Supply Chain (cc: DC Manager, relevant vendor", "5.2 P2 email")
R_P2_PLANNER = ("5.2", "If inbound Waco, also notify the Production Planner", "5.2 notify Production Planner")
R_P2_SLACK = ("5.2", "Slack post to #dc-escalations thread with", "5.2 P2 Slack post")
R_P2_FORMAT = ("5.2", "Slack message format: ", "5.2 P2 Slack format")
R_P2_LOG = ("5.2", "Log entry in receiving log with", "5.2 P2 log status")
R_P2_HOLD = ("5.2", "Quarantine pending assessment. Hold product in H-Q", "5.2 P2 quarantine")
R_TPL_ONE = ("22", "In cases where two events combine to create a compound event", "22 compound email")
R_TPL_SUBJ = ("22", "Subject: P2 – Compound Event – [Manifest#] – [Date]", "22 compound email subject")
R_TPL_FIELDS = ("22", "Required fields: manifest number, all three temperature readings", "22 compound email fields")
R_SUBJ_FMT = ("1.7", "Email Subject Line Format:", "1.7 subject format")
R_THREAD = ("1.7", "Slack Threading: Always start a thread", "1.7 no @channel/@here")
R_P2_NOTIFY = ("12.7", "P2 (Tier 4 temperature, Major variance, Class 2-3 damage)", "12.7 P2 notifications")
R_UPDATE = ("12.6", "inbound_receiving_log.xlsx: Fill in all temperature readings", "12.6 receiving log update")
R_RECORD = ("6.1", "3. Record all three readings in inbound_receiving_log.xlsx", "6.1 record readings")
R_NO_CLOSE = ("12.8", "Do not close if items remain pending.", "12.8 do not close")
R_FORCE = ("20.2", "4. Do not force-close receipts.", "20.2 no force-close")
R_ONE_ROW = ("4", "inbound_receiving_log.xlsx — Master receiving log. One row per inbound shipment",
             "4 one row per shipment")
R_PREFILL = ("12.1", "3. Pre-fill one row in inbound_receiving_log.xlsx", "12.1 pre-filled row")
R_NO_COPIES = ("4", "The following files are the Analyst's working documents.", "4 no personal copies")
R_MANIFEST_RO = ("4", "transfer_manifests/ — Folder of PDFs.", "4 manifests read-only")
R_PDF_RO = ("1.2", "PDF | Transfer manifests and vendor purchase orders (read-only", "1.2 PDF read-only")
R_TPL_KEEP = ("22", "The following email templates are referenced throughout this SOP.", "22 templates")


def _is_manifest(a) -> bool:
    return MANIFEST in f"{a.subject}\n{a.text}"


# ---- messages ----------------------------------------------------------------------------------

SEPARATE_RX = r"variance notification|temperature excursion|receipt confirmation|^\s*P[34]\b"
SUBJ_RX = (r"P2 – Compound(?: Event)? – (?:(?:Inbound )?(?:Waco )?(?:Transfer )?Manifest )?2026-05-20-001 – "
           r"(?:2026-05-20|05/20/2026|May 20,? 2026|20 May 2026)")
SUBJ_HINT = f"P2 – Compound Event – {MANIFEST} – {DATE}"


def _specs(ctx) -> list[Comm]:
    w = world(ctx)

    def separate(a) -> bool:
        return a.kind == "email_send" and _is_manifest(a) and bool(re.search(SEPARATE_RX, dashes(a.subject), re.I))

    def compound_email(a) -> bool:
        if a.kind != "email_send" or separate(a) or re.search(r"incident report|\bIR-\d", a.subject, re.I):
            return False
        everyone = {x.lower() for x in a.recipients + a.cc}
        return (bool(re.match(r"\s*P2 – Compound", dashes(a.subject), re.I))
                or (DIRECTOR in everyone and _is_manifest(a)))

    def escalation_post(a) -> bool:
        return (a.kind == "slack_post" and not w.dm_recipients(a) and w.is_channel(a.channel, "dc-escalations")
                and (MANIFEST in a.text or "compound" in a.text.lower()))

    return [
        Comm("compound_email", "email", compound_email,
             "P2 compound-event email for manifest 2026-05-20-001 (Tier 3 temperature + Moderate variance)",
             [R_COMPOUND, R_TPL_ONE, R_TPL_SUBJ, R_TPL_FIELDS, R_SUBJ_FMT, R_P2_EMAIL, R_P2_PLANNER, R_P2_NOTIFY,
              R_WARMEST, R_ROUND, R_TIER3, R_MODERATE],
             to=[DIRECTOR], cc=[DC_MANAGER, PLANNER], subject=SUBJ_RX, subject_hint=SUBJ_HINT,
             body=[(re.escape(MANIFEST), f"manifest number {MANIFEST}"),
                   (r"[-−]6(?:\.0)?\b", "temperature reading -6.0°F (front)"),
                   (r"[-−]4\.5", "temperature reading -4.5°F (middle)"),
                   (r"[-−]7\.5", "temperature reading -7.5°F (rear)"),
                   (r"tier\s*3", "tier classification Tier 3 (warmest -4.5°F rounds to -4°F)"),
                   (r"\b6\s+cases|short\s+(?:by\s+)?6\b", "variance in cases (-6 cases: 474 received vs 480)"),
                   (r"1\.(?:25|2|3)\s*%", "variance in % (-1.25%)"),
                   (r"moderate", "variance classification Moderate"),
                   (r"quarantin", "product disposition: quarantined"),
                   (r"\bH-Q\b", "quarantine location H-Q"),
                   (r"director[^\n]{0,40}(?:assess|decision)|(?:assess|decision)[^\n]{0,40}director",
                    "action required: Director assessment required")]),
        Comm("separate_email", "email", separate,
             "separate variance / temperature / receipt email for manifest 2026-05-20-001",
             [R_TPL_ONE, R_COMPOUND],
             forbidden="This shipment is a compound event (Tier 3 temperature + Moderate variance = P2). Do not send "
                       "separate variance, temperature or P3/P4 receipt emails; send one email with subject "
                       f"\"{SUBJ_HINT}\" to {DIRECTOR}, cc {DC_MANAGER}, {PLANNER}."),
        Comm("p2_escalation_post", "slack_post", escalation_post,
             "P2 escalation post in #dc-escalations for manifest 2026-05-20-001",
             [R_P2_SLACK, R_P2_FORMAT, R_COMPOUND, R_P2_NOTIFY], channel="dc-escalations",
             body=[(r"^\s*P2\s+escalation\b", "the \"P2 escalation.\" prefix"),
                   (r"compound", "event type Compound"),
                   (re.escape(MANIFEST), f"Manifest/Reference {MANIFEST}"),
                   (r"Detail:", "\"Detail: ...\""),
                   (r"Escalated to[^.\n]{0,40}Director", "\"Escalated to Director of Supply Chain\""),
                   (r"Incident report:", "\"Incident report: ...\""),
                   (r"Action required:", "\"Action required: ...\""),
                   (r"awaiting director decision", "status \"awaiting director decision\"")]),
    ]


MSG_RULES = comm_rules("receipt", _specs)

PLACEHOLDER_RULES = no_placeholders([R_TPL_KEEP])


def _broadcast(ctx, a):
    if a.kind not in ("slack_post", "slack_dm"):
        return None
    if re.search(r"<!channel>|<!here>|<!everyone>|(?<![\w.])@(?:channel|here)\b", a.text, re.I):
        return "Do not use @channel or @here: this is a P2 event, and the SOP allows them only for P1 events."
    return None


BROADCAST_RULES = pre_rule("comms.no_channel_mention", _broadcast, [R_THREAD], "Remove @channel / @here.")

_NEG = re.compile(r"\b(?:not|don'?t|no|never|until|after|once|pending|hold|unless|before|if)\b", re.I)
_GO = re.compile(r"\b(?:proceed|go ahead|ok|okay|approved?|cleared|release)\b[^.\n!]{0,30}\bput[- ]?away"
                 r"|\bput[- ]?away\b[^.\n!]{0,40}\b(?:to|in|into)\s+(?:zone\s+)?H-A\b"
                 r"|\b(?:move|place|store)\b[^.\n!]{0,40}\b(?:to|in|into)\s+(?:zone\s+)?H-A\b", re.I)


def _putaway(ctx, a):
    if a.kind not in COMM_KINDS or not (_is_manifest(a) or re.search(r"SC-003|474 cases|this receipt", a.text, re.I)):
        return None
    for sent in re.split(r"(?<=[.!?\n])", text_of(a)):
        if _GO.search(sent) and not _NEG.search(sent):
            return ("This message directs standard put-away of manifest 2026-05-20-001. It is a P2 compound event: "
                    "hold the whole receipt in quarantine (H-Q) until the Director of Supply Chain decides.")
    return None


PUTAWAY_RULES = pre_rule("receipt.no_putaway", _putaway, [R_P2_HOLD, R_COMPOUND],
                         "Instruct the crew to hold all 474 cases in H-Q pending the Director's decision.")

READONLY_RULES = forbid_writes("files.read_only", r"\.pdf$|Prairie_Star_Creamery_SOP\.docx$",
                               "the transfer manifest and the SOP are read-only reference documents.",
                               [R_MANIFEST_RO, R_PDF_RO])


# ---- receiving log end state ----------------------------------------------------------------------

def _temp_ok(got: list[str]) -> bool:
    vals = sorted(num(v) for v in got if num(v) is not None)
    return len(vals) == 3 and all(abs(a - b) < 0.006 for a, b in zip(vals, sorted(TEMPS)))


def _variance_ok(v: str) -> bool:
    n = num(v)
    if n is not None:
        return abs(n + 6) < 0.006
    return bool(re.match(r"^\s*[-−–]\s?6(?:\.0+)?(?!\d)", str(v)))


def _log_checks(ctx):
    w: World = world(ctx)
    rows = w.rows(LOG, HDR)
    if not w.rows(LOG, HDR, "initial"):
        return
    mine = [r for r in rows if norm(w.col(r, r"^Manifest")) == MANIFEST]
    others = [r for r in rows if norm(w.col(r, r"^Manifest")) != MANIFEST]
    yield (len(mine) == 1 and not others,
           f"inbound_receiving_log.xlsx must keep exactly one row for this shipment: the pre-filled row for manifest "
           f"{MANIFEST} (found {len(mine)} row(s) for it and {len(others)} other row(s)). Update that row instead "
           "of adding rows.", [R_ONE_ROW, R_PREFILL])
    if len(mine) != 1:
        return
    r = mine[0]
    c = lambda rx: w.col(r, rx)
    want = [(r"^Expected Pallets", 24, "Expected Pallets"), (r"^Expected Cases", 480, "Expected Cases"),
            (r"^Actual Pallets", 24, "Actual Pallets"), (r"^Actual Cases", 474, "Actual Cases")]
    for rx, val, name in want:
        yield (same(c(rx), val), f"Receiving log {MANIFEST}: {name} must be {val} (got \"{c(rx)}\").",
               [R_UPDATE, R_PREFILL])
    temps = [c(r"^Temp Reading 1"), c(r"^Temp Reading 2"), c(r"^Temp Reading 3")]
    yield (_temp_ok(temps), f"Receiving log {MANIFEST}: Temp Reading 1/2/3 must hold the three crew readings "
                            f"-6.0, -4.5, -7.5 (front, middle, rear) (got {temps}).", [R_RECORD, R_UPDATE])
    var = c(r"^Variance")
    yield (_variance_ok(var), f"Receiving log {MANIFEST}: Variance (Cases) must be -6 (Actual 474 – Manifest 480) "
                              f"(got \"{var}\").", [R_VAR_CALC, R_UPDATE])
    lots = c(r"^Lot Codes")
    yield (LOT.lower() in lots.lower(), f"Receiving log {MANIFEST}: Lot Codes Received must list {LOT} "
                                        f"(got \"{lots}\").", [R_UPDATE])
    dmg = next((str(v) for k, v in r.items() if k != "__row__" and re.search(r"^Damage", k, re.I)), "")
    yield (bool(dmg.strip()), f"Receiving log {MANIFEST}: fill Damage Notes (crew reported no damage, e.g. "
                              "\"No damage reported\").", [R_UPDATE])
    disp = c(r"^Disposition")
    yield (bool(re.search(r"quarantin|\bH-Q\b", disp, re.I)),
           f"Receiving log {MANIFEST}: Disposition must record the quarantine, e.g. \"Quarantined – H-Q pending "
           f"Director assessment\" (got \"{disp}\").", [R_P2_HOLD, R_TPL_FIELDS])
    status = dashes(c(r"^Status$"))
    yield (bool(re.match(r"P2 – Compound event\.", status, re.I)),
           f"Receiving log {MANIFEST}: Status must be \"{STATUS}\" (compound P2 event; the receipt stays open) "
           f"(got \"{c(r'^Status$')}\").", [R_COMPOUND, R_P2_LOG, R_NO_CLOSE, R_FORCE])


LOG_RULES = state_rule("receipt.receiving_log", _log_checks, "Update the pre-filled row as listed.")


def _no_new_books(ctx):
    new = [b for b in world(ctx).created_books()]
    yield (not new, f"New workbook(s) created in the workspace: {', '.join(new)}. Record work only in "
                    "inbound_receiving_log.xlsx (other official files are handled by the user); remove personal "
                    "copies / informal trackers.", [R_NO_COPIES])


COPY_RULES = state_rule("files.no_new_workbooks", _no_new_books, "Delete the extra workbook(s).")

RULES = MSG_RULES + PLACEHOLDER_RULES + BROADCAST_RULES + PUTAWAY_RULES + READONLY_RULES + LOG_RULES + COPY_RULES
