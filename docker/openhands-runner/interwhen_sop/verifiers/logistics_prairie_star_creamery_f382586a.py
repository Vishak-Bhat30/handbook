"""SOP verifiers for logistics_prairie_star_creamery_f382586a (Houston DC, Waco manifest 2026-04-14-001).

Situation derived from the SOP and seed data only:
- Alicia's report: seal intact, temps -4.5/-5/-8 (avg -6), 22 pallets, 438 cases (SC-001 218 vs 220,
  SC-006 220), lot codes match, no damage, no put-away confirmation.
- Warmest -4.5 rounds toward the warmer tier -> -4F -> Tier 3 (P3, 6.1 step 5 / 6.2).
- SC-001 -2 cases (0.9% of 220, Minor) is the third minor Waco variance in 30 days (03-17 -2, 04-01 -3,
  04-14 -2) -> P3 pattern (7.2 / 5.5).
- Two P3 events on one shipment -> compound P2 (5.5, 12 intro, 12.6): email Director cc DC Manager +
  Production Planner, P2 post in #dc-escalations, receiving log Status "Open — Pending P2 Assessment",
  Disposition "Hold", Priority "P2"; no put-away, so no inventory_master / expiry_tracker rows (12.7).
- Each P3 issue still gets its own handling (12 intro): Tier 3 email to the Production Planner (6.2) and
  the repeated-variance notice to the origin (7.2), plus the exact pattern note in the receiving log.
"""

from __future__ import annotations

import re

from ..kit import (COMM_KINDS, Comm, Context, comm_rules, dashes, forbid_writes, nh, no_placeholders, norm, num,
                   pre_rule, state_rule, world)

MANIFEST = "2026-04-14-001"
LOTS = ("A-20260411-01", "A-20260411-02")
DIRECTOR = "daniel.reyes@prairiestar.com"
DC_MGR = "carlos.mendoza@prairiestar.com"
PLANNER = "jacob.patel@prairiestar.com"
DISPATCH = "brandon.keller@prairiestar.com"
STATUS = "Open — Pending P2 Assessment"
PATTERN_NOTE = "Third Repeated Minor Variance Pattern - P3"

RLOG, RLOG_HDR = r"inbound_receiving_log", r"^Manifest / PO #$"
TLOG, TLOG_HDR, TLOG_SHEET = r"temperature_log", r"^Reading \(°F\)$", r"April 2026"
INV, EXP, LOT_HDR = r"inventory_master", r"expiry_tracker", r"^Lot Code$"

R_SUBJECT = ("1.7", "Email Subject Line Format", "1.7 email subject format")
R_THREAD = ("1.7", "Slack Threading", "1.7 Slack threading / no @channel")
R_BRANDON = ("1.4", "Coordinate with Brandon", "1.4 dispatcher coordination")
R_P2_EMAIL = ("5.2", "Email to the Director of Supply Chain (cc: DC Manager, relevant vendor",
              "5.2 P2 notification email")
R_P2_SLACK = ("5.2", "Slack post to #dc-escalations thread", "5.2 P2 Slack post")
R_P2_FMT = ("5.2", "Slack message format:", "5.2 P2 Slack format")
R_P2_CC = ("5.2", "If inbound Waco, also add the Production Planner", "5.2 Production Planner cc")
R_P2_LOG = ("5.2", "Log entry in receiving log with", "5.2 P2 receiving-log priority")
R_COMPOUND = ("5.5", "Compound events", "5.5 compound P3 events = P2")
R_ROUND = ("6.1", "5. Decimal readings", "6.1 rounding rule")
R_RECORD = ("6.1", "3. Record all three readings", "6.1 record readings")
R_TIER3 = ("6.2", "Tier 3 |", "6.2 Tier 3")
R_MINOR = ("7.2", "1–3 cases |", "7.2 minor variance / third-pattern rule")
R_MODERATE = ("7.2", "4–10 cases |", "7.2 origin email contents")
R_12 = ("12", "This procedure describes how the Analyst processes receiving reports for inbound Waco",
        "12 treat issues separately, escalate at 12.6")
R_T3_STEP = ("12.3", "Tier 3 (-4 to 0°F)", "12.3 Tier 3")
R_MINOR_STEP = ("12.4", "1-3 cases and ≤1%", "12.4 minor variance")
R_P2_STEP = ("12.6", "P2 (Tier 4 temperature", "12.6 P2 actions")
R_FILL = ("12.7", "inbound_receiving_log.xlsx: Fill in all", "12.7 receiving log update")
R_TEMPLOG = ("12.7", "temperature_log.xlsx: Log all three", "12.7 temperature log update")
R_INV = ("12.7", "inventory_master.xlsx (only after", "12.7 inventory_master after put-away only")
R_EXP = ("12.7", "expiry_tracker.xlsx (only after", "12.7 expiry_tracker after put-away only")
R_NOCLOSE = ("12.8", "Do not close if items remain pending", "12.8 do not close pending receipt")
R_NO_COPIES = ("4", "The following files are the Analyst", "4 no personal copies")
R_ONE_ROW = ("4", "inbound_receiving_log.xlsx — Master receiving log", "4 one row per inbound shipment")
R_MANIFEST_RO = ("4", "transfer_manifests/ — Folder of PDFs", "4 manifests read-only")
R_TEMPLATES = ("22", "The following email templates are referenced", "22 templates")


def _mentions(a, rx=re.escape(MANIFEST)) -> bool:
    return bool(re.search(rx, f"{a.subject}\n{a.text}", re.I))


def _neg(n: str) -> str:
    """Regex for a negative reading as written in a message (hyphen, en/em dash or unicode minus)."""
    return rf"(?<![\w.])[-–—−]\s?{n}(?![\d])"


# ---- messages ------------------------------------------------------------------------------------

def _to(a, addr: str) -> bool:
    return a.kind in ("email_send", "email_draft") and addr in [x.lower() for x in a.recipients]


def specs(ctx: Context) -> list[Comm]:
    return [
        Comm("p2_director", "email",
             lambda a: _to(a, DIRECTOR) and _mentions(a),
             "P2 (compound Tier 3 + repeated-variance) escalation email to the Director for manifest " + MANIFEST,
             [R_P2_EMAIL, R_P2_CC, R_COMPOUND, R_P2_STEP, R_SUBJECT],
             to=[DIRECTOR], cc=[DC_MGR, PLANNER], exact_to=False,
             subject=rf"P2\b.*{re.escape(MANIFEST)}.*",
             subject_hint=f"P2 – Inbound Waco Manifest {MANIFEST} – 2026-04-14",
             body=[(re.escape(MANIFEST), f"manifest number {MANIFEST}"),
                   (r"(?=.*put[- ]?away)(?=.*\bhold)(?=.*(guidance|advis|direct|decision|instruct|approv))",
                    "a request for Director guidance on whether to proceed with put-away or hold")]),
        Comm("tier3_planner", "email",
             lambda a: _to(a, PLANNER) and _mentions(a) and bool(re.search(r"temp|°\s?F", a.text, re.I)),
             "Tier 3 temperature email to the Production Planner (Jacob Patel) for manifest " + MANIFEST,
             [R_TIER3, R_T3_STEP, R_12],
             to=[PLANNER], exact_to=False,
             body=[(re.escape(MANIFEST), f"manifest number {MANIFEST}"),
                   (_neg(r"4\.5"), "reading -4.5°F"), (_neg("5"), "reading -5°F"), (_neg("8"), "reading -8°F"),
                   (r"(av(g|erage)|mean)\b[^\n]{0,60}?" + _neg(r"(6|5\.8\d?)"), "the average reading (-6°F, i.e. -5.8°F)"),
                   (r"expir\w*[^\n]{0,40}monitor|monitor\w*[^\n]{0,40}expir",
                    "a note that the product is flagged for enhanced expiry monitoring")]),
        Comm("variance_planner", "email",
             lambda a: _to(a, PLANNER) and _mentions(a) and bool(re.search(r"varian|short", a.text, re.I)),
             "repeated minor variance notice to the origin (Jacob Patel) for manifest " + MANIFEST,
             [R_MINOR, R_MODERATE, R_MINOR_STEP, R_12],
             to=[PLANNER], exact_to=False,
             body=[(re.escape(MANIFEST), f"manifest number {MANIFEST}"),
                   (r"SC-001", "the SKU SC-001"),
                   (_neg("2") + r"|\b2 cases?\b|\btwo cases?\b", "the absolute variance -2 cases (218 received vs 220)"),
                   (r"pattern|third|3rd|repeat|recurr", "a note of the repeated minor variance pattern (3rd in 30 days: "
                                                         "2026-03-17 -2, 2026-04-01 -3, 2026-04-14 -2)"),
                   (r"explanation|explain|credit", "a request for explanation or credit")]),
        Comm("p2_slack", "slack_post",
             lambda a: a.kind == "slack_post" and world(ctx).is_channel(a.channel, "dc-escalations")
             and not (a.args.get("thread_ts") or a.args.get("thread_id")),
             "P2 post in #dc-escalations for manifest " + MANIFEST,
             [R_P2_SLACK, R_P2_FMT, R_P2_STEP],
             channel="dc-escalations",
             body=[(r"^\s*P2\b", "the \"P2\" prefix at the start"),
                   (rf"P2 escalation\. Manifest {re.escape(MANIFEST)}\.",
                    f"the SOP format \"P2 escalation. Manifest {MANIFEST}.\"")],
             banned=[(r"@channel|@here|<!channel>|<!here>", "Do not use @channel/@here (not a P1 event).")]),
    ]


# ---- receiving log / temperature log --------------------------------------------------------------

def _row(w, which="current"):
    return w.find(RLOG, RLOG_HDR, r"^Manifest / PO #$", MANIFEST, which)


def _formula_or(v: str, ok: set[float]) -> bool:
    return str(v).startswith("=") or (num(v) is not None and any(abs(num(v) - x) < 0.006 for x in ok))


def rlog_checks(ctx: Context):
    w = world(ctx)
    r = _row(w)
    if r is None:
        yield False, f"inbound_receiving_log.xlsx: the pre-filled row for manifest {MANIFEST} is missing.", [R_FILL]
        return
    c = lambda rx: w.col(r, rx)
    yield same_num(c(r"^Actual Pallets$"), 22), f"Actual Pallets for {MANIFEST} must be 22 (got '{c(r'^Actual Pallets$')}').", [R_FILL]
    yield same_num(c(r"^Actual Cases$"), 438), f"Actual Cases for {MANIFEST} must be 438 (got '{c(r'^Actual Cases$')}').", [R_FILL]
    temps = [c(r"^Temp Reading 1"), c(r"^Temp Reading 2"), c(r"^Temp Reading 3")]
    vals = sorted(num(t) if num(t) is not None else 99 for t in temps)
    ok_t = len(vals) == 3 and abs(vals[0] + 8) < .01 and abs(vals[1] + 5) < .01 and vals[2] in (-4.5, -4.0)
    yield ok_t, (f"Temp Reading 1/2/3 for {MANIFEST} must be the reported readings -4.5, -5, -8 °F (got {temps})."), \
        [R_RECORD, R_FILL]
    warm = c(r"^Warmest Temp")
    yield _formula_or(warm, {-4.5, -4.0}), f"Warmest Temp for {MANIFEST} must be -4.5 (or keep the MAX formula); got '{warm}'.", [R_FILL]
    tier = c(r"^Temp Tier$")
    yield bool(re.fullmatch(r"(tier\s*)?3\b.*", tier.strip(), re.I)), \
        (f"Temp Tier for {MANIFEST} must be \"Tier 3\": warmest -4.5°F rounds toward the warmer tier to -4°F "
         f"(Tier 3, -4°F to 0°F); got '{tier}'."), [R_ROUND, R_TIER3]
    var = c(r"^Variance \(Cases\)$")
    yield _formula_or(var, {-2.0}), f"Variance (Cases) for {MANIFEST} must be -2 (or keep the formula); got '{var}'.", [R_FILL]
    pct = c(r"^Variance %$")
    yield not blank_or_pending(pct), f"Variance % for {MANIFEST} must be filled (keep the formula); got '{pct}'.", [R_FILL]
    dmg = c(r"^Damage Class$")
    # kit's col() maps the literal text "None" to "", so only 'pending' and a damage class are wrong here
    yield norm(dmg) != "pending" and not re.search(r"class\s*[1-4]", dmg, re.I), \
        f"Damage Class for {MANIFEST} must be \"None\" (no damage reported); got '{dmg}'.", [R_FILL]
    lots = c(r"^Lot Codes$")
    yield all(l in lots for l in LOTS), f"Lot Codes for {MANIFEST} must list {LOTS[0]} (SC-001, 218 cases) and {LOTS[1]} (SC-006, 220 cases).", [R_FILL]
    disp = c(r"^Disposition$")
    yield norm(disp) == "hold", f"Disposition for {MANIFEST} must be \"Hold\" (compound P2); got '{disp}'.", [R_P2_STEP, R_COMPOUND]
    pri = c(r"^Priority$")
    yield norm(pri) == "p2", f"Priority for {MANIFEST} must be \"P2\" (two P3 events = compound P2); got '{pri}'.", [R_P2_LOG, R_COMPOUND]
    st = c(r"^Status$")
    yield nh(st) == STATUS, (f"Status for {MANIFEST} must be exactly \"{STATUS}\" (em dash, as the SOP prints it); "
                             f"got '{st}'. Do not close or mark put-away while the P2 assessment is pending."), \
        [R_P2_STEP, R_NOCLOSE]
    notes = nh(c(r"^Notes$"))
    yield PATTERN_NOTE in notes, (f"Notes for {MANIFEST} must contain \"{PATTERN_NOTE}\" (third minor Waco variance in "
                                  "30 days: 2026-03-17 -2, 2026-04-01 -3, 2026-04-14 -2)."), [R_MINOR]


def same_num(v, want) -> bool:
    return num(v) is not None and abs(num(v) - want) < 0.006


def blank_or_pending(v) -> bool:
    return norm(v) in ("", "none", "nan", "pending")


def _key(r: dict) -> tuple:
    # an openpyxl round-trip rewrites 20.0 as 20, so kit's exact row tuples report untouched rows as changed
    return tuple(f"{num(v):g}" if num(v) is not None else nh(v) for k, v in r.items() if k != "__row__")


def _diff(w, name_rx: str, header_rx: str, sheet_rx: str | None = None) -> tuple[list[dict], list[dict]]:
    """(initial rows no longer present, current rows not present initially), numbers compared by value."""
    ini, cur = w.rows(name_rx, header_rx, "initial", sheet_rx), w.rows(name_rx, header_rx, "current", sheet_rx)
    pool = [_key(r) for r in cur]
    gone = []
    for r in ini:
        k = _key(r)
        if k in pool:
            pool.remove(k)
        else:
            gone.append(r)
    pool = [_key(r) for r in ini]
    new = []
    for r in cur:
        k = _key(r)
        if k in pool:
            pool.remove(k)
        else:
            new.append(r)
    return gone, new


def rlog_other_checks(ctx: Context):
    w = world(ctx)
    keep = lambda rows: [r for r in rows if norm(w.col(r, r"^Manifest / PO #$")) != norm(MANIFEST)]
    gone, new = (keep(x) for x in _diff(w, RLOG, RLOG_HDR))
    yield not gone, (f"inbound_receiving_log.xlsx: {len(gone)} existing row(s) other than {MANIFEST} were edited or "
                     f"removed (e.g. {w.col(gone[0], r'^Manifest / PO #$') if gone else ''}). Restore them; only "
                     f"the {MANIFEST} row is processed here."), [R_ONE_ROW]
    yield not new, (f"inbound_receiving_log.xlsx: {len(new)} new row(s) added. The log has one row per shipment; fill "
                    f"the existing pre-filled {MANIFEST} row instead and remove the extra rows."), [R_ONE_ROW]


def templog_checks(ctx: Context):
    w = world(ctx)
    rows = [r for r in w.rows(TLOG, TLOG_HDR, "current", TLOG_SHEET) if MANIFEST in w.col(r, r"^Manifest/PO")]
    readings = [w.col(r, r"^Reading") for r in rows]
    nums = [num(x) for x in readings]
    ok = (sum(1 for n in nums if n is not None and abs(n + 8) < .01) >= 1
          and sum(1 for n in nums if n is not None and abs(n + 5) < .01) >= 1
          and any(n is not None and n in (-4.5, -4.0) for n in nums)
          and not any(norm(x) == "pending" for x in readings))
    yield ok, (f"temperature_log.xlsx (April 2026): the three Inbound rows for {MANIFEST} must hold the readings "
               f"-4.5, -5 and -8 °F instead of 'pending' (got {readings})."), [R_RECORD, R_TEMPLOG]
    wr = [w.col(r, r"^Within Range") for r in rows]
    yield not any(norm(x) in ("pending", "") for x in wr), \
        f"temperature_log.xlsx: fill 'Within Range (Y/N)' for the {MANIFEST} inbound rows (got {wr}).", [R_TEMPLOG]


def templog_other_checks(ctx: Context):
    w = world(ctx)
    keep = lambda rows: [r for r in rows if MANIFEST not in w.col(r, r"^Manifest/PO")]
    gone, new = (keep(x) for x in _diff(w, TLOG, TLOG_HDR, TLOG_SHEET))
    yield not gone, (f"temperature_log.xlsx (April 2026): {len(gone)} existing row(s) not about {MANIFEST} were edited "
                     "or removed. Restore them."), [R_TEMPLOG]
    yield not new, (f"temperature_log.xlsx (April 2026): {len(new)} new row(s) not about {MANIFEST} were added. Only the "
                    f"{MANIFEST} inbound readings are logged for this report; remove them."), [R_TEMPLOG]


def records_checks(ctx: Context):
    w = world(ctx)
    for name, rx, sheet, ref in (("inventory_master.xlsx", INV, None, R_INV),
                                 ("expiry_tracker.xlsx", EXP, r"Expiry Tracker", R_EXP)):
        gone, added = _diff(w, rx, LOT_HDR, sheet)
        new = [r for r in added if any(l in w.col(r, LOT_HDR) for l in LOTS)]
        yield not new, (f"{name}: rows for {', '.join(LOTS)} were added, but these rows are only added after the dock "
                        "crew confirms put-away, and this receipt is on Hold (P2) with no put-away. Remove them."), \
            [ref, R_P2_STEP]
        yield not gone, (f"{name}: {len(gone)} existing lot row(s) were edited or removed (e.g. "
                         f"{w.col(gone[0], LOT_HDR) if gone else ''}). This report does not change existing lots; "
                         "restore them."), [ref]


def copies_checks(ctx: Context):
    new = world(ctx).created_books()
    yield not new, (f"New workbook(s) {new} were created in the workspace. All work is recorded in the official files; "
                    "do not create personal copies or informal tracking workbooks - remove them."), [R_NO_COPIES]


def dispatcher_checks(ctx: Context):
    w = world(ctx)
    keller = w.uids("Brandon Keller")
    hit = False
    for a in w.comms():
        to_him = (w.is_dm_to(a, "Brandon Keller") or DISPATCH in [x.lower() for x in a.recipients + a.cc]
                  or (a.kind == "slack_post" and re.search(r"@b\.keller|brandon" + "".join(f"|<@{u}>" for u in keller),
                                                           a.text, re.I)))
        if to_him and re.search(r"\bhold|\bheld\b|not (yet )?available|unavailable", a.text, re.I) \
                and re.search(rf"SC-00[16]|{re.escape(MANIFEST)}", a.text):
            hit = True
    yield hit, ("Dispatcher Brandon Keller (@b.keller) asked about SC-001/SC-006 for Thursday and must be told about "
                f"holds: tell him the {MANIFEST} receipt (SC-001 lot {LOTS[0]} 218 cases, SC-006 lot {LOTS[1]} 220 "
                "cases) is on Hold pending the Director's P2 assessment and not available for picking yet; existing "
                "H-A stock (SC-001 1,233 cases; SC-006 160 cases, lot A-20260210-02) is unaffected."), [R_BRANDON]


# ---- pre rules -----------------------------------------------------------------------------------

GO_RX = [
    re.compile(r"\b(?:may|can|should|ok(?:ay)?\s+to|clear(?:ed)?\s+to|go\s+ahead(?:\s+and)?|please|approved\s+to|"
               r"authori[sz]ed\s+to|crew\s+to|team\s+to)\s+(?:now\s+)?(?:proceed|start|begin|continue|complete|do)\s+"
               r"(?:with\s+)?(?:the\s+|standard\s+)?put[- ]?away", re.I),
    re.compile(r"\b(?:go\s+ahead\s+with|cleared\s+for|approved\s+for|released\s+for|ok(?:ay)?\s+for)\s+"
               r"(?:the\s+|standard\s+)?put[- ]?away", re.I),
]
NEG_RX = re.compile(r"\b(not|no|whether|until|pending|hold|once|after|if|before|await\w*)\b|n't", re.I)


def putaway_go(ctx: Context, a) -> str | None:
    if a.kind not in COMM_KINDS or not _mentions(a, rf"{re.escape(MANIFEST)}|SC-00[16]|{LOTS[0]}|{LOTS[1]}"):
        return None
    for sent in re.split(r"(?<=[.!?\n])\s+", dashes(a.text)):
        if any(rx.search(sent) for rx in GO_RX) and not NEG_RX.search(sent):
            return (f"[putaway] This message authorises put-away (\"{sent.strip()[:120]}\"), but manifest {MANIFEST} "
                    "is a compound P2 event (Tier 3 temperature + third minor variance in 30 days): do not proceed "
                    "with put-away; the receipt is on Hold pending the Director's guidance.")
    return None


def no_mass_tag(ctx: Context, a) -> str | None:
    if a.kind in ("slack_post", "slack_dm") and re.search(r"@channel|@here|<!channel>|<!here>", a.text, re.I):
        return "[slack] Do not use @channel or @here; this is not a P1 event."
    return None


def dup_subject(ctx: Context, a) -> str | None:
    if a.kind != "email_send" or not a.subject.strip():
        return None
    subj = norm(dashes(a.subject))
    rcpt = {x.lower() for x in a.recipients + a.cc}
    for b in world(ctx).calls("email_send"):
        both = rcpt & {x.lower() for x in b.recipients + b.cc}
        if norm(dashes(b.subject)) == subj and both:
            return (f"[subject] An email with the identical subject \"{a.subject}\" was already sent to "
                    f"{', '.join(sorted(both))}. Emails with identical subjects to the same recipient must be combined "
                    "into a single email; do not send a second one with this subject (if a separate message is truly "
                    "needed, use the matching template subject, e.g. \"P3 – Temperature Excursion – "
                    f"{MANIFEST} – 2026-04-14\" or \"P3 – Variance Notification – {MANIFEST} – 2026-04-14\").")
    return None


RULES = (
    comm_rules("f382586a.comms", specs)
    + state_rule("f382586a.rlog_row", rlog_checks, "Update the 2026-04-14-001 row of inbound_receiving_log.xlsx as listed.")
    + state_rule("f382586a.rlog_other", rlog_other_checks, "Restore inbound_receiving_log.xlsx outside the 2026-04-14-001 row.")
    + state_rule("f382586a.templog", templog_checks, "Fill the 2026-04-14-001 inbound rows of temperature_log.xlsx.")
    + state_rule("f382586a.templog_other", templog_other_checks, "Restore the other temperature_log.xlsx rows.")
    + state_rule("f382586a.no_putaway_records", records_checks, "Revert those inventory_master / expiry_tracker changes.")
    + state_rule("f382586a.dispatcher", dispatcher_checks, "Send Brandon Keller the hold notice.")
    + state_rule("f382586a.no_copies", copies_checks, "Delete the extra workbook(s).")
    + pre_rule("f382586a.no_putaway_go", putaway_go, [R_P2_STEP, R_COMPOUND],
               "Do not authorise put-away; state that the receipt is on Hold pending the Director's decision.")
    + pre_rule("f382586a.no_mass_tag", no_mass_tag, [R_THREAD], "Remove @channel/@here.")
    + pre_rule("f382586a.dup_subject", dup_subject, [R_SUBJECT], "Combine the content into one email.")
    + forbid_writes("f382586a.readonly", r"transfer_manifests|2026-04-14-001\.pdf|Prairie_Star_Creamery_SOP\.docx",
                    "transfer manifests and the SOP are read-only reference documents.", [R_MANIFEST_RO])
    + no_placeholders([R_TEMPLATES])
)
