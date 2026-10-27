"""Prairie Star Creamery - inbound Waco transfer 2026-04-02-001 (Houston), task a9dc52cb.

Derived from the SOP and seed data only. Alicia's report (email): seal intact; temps front -9.5 / middle -10.5 /
rear -13.0 (warmest -9.5 -> rounds toward the warmer tier -> -9 -> Tier 2, Accept with Note, P4); 20 pallets;
399 of 400 cases (SC-003 119/120) -> -1 case, -0.25% of the manifest total -> Minor; it is the third minor Waco
variance in 30 days (2026-03-25 -3, 2026-03-31 -1) -> P3, notifications per 12.7 only (S3 post in
#receiving-houston + E2 email to the Production Planner cc the DC Manager); one torn label -> Class 1 (P4, no claim).
"""

from __future__ import annotations

import re

from ..kit import (Action, Comm, Context, WRITE_KINDS, append_only, comm_rules, dashes, forbid_writes, nh,
                   no_placeholders, norm, pre_rule, state_rule, text_of, world)

MANIFEST = "2026-04-02-001"
TODAY = "2026-04-02"
S1_TS = "1775137500"  # seed S1 arrival post in #receiving-houston for this manifest
PLANNER, DC_MGR = "jacob.patel@prairiestar.com", "carlos.mendoza@prairiestar.com"
LOG, INV, EXP, TEMP = r"inbound_receiving_log\.xlsx", r"inventory_master\.xlsx", r"expiry_tracker\.xlsx", \
    r"temperature_log\.xlsx"

# SOP references: (section, paragraph text prefix, label)
R_NOTES_ONLY = ("1.2", "Tool Purpose Email Formal notifications", "1.2 Tools (receiving log Notes)")
R_SUBJECT = ("1.7", "Email Subject Line Format:", "1.7 Communication Rules")
R_FILES = ("4", "The following files are the Analyst's working documents.", "4 Files and Systems")
R_READONLY = ("4", "Prairie Star Creamery — Inventory Operations Analyst SOP transfer_manifests/", "4 Files and Systems")
R_P3_EMAIL = ("5.3", "Email notification to relevant stakeholders", "5.3 P3 notification")
R_P3_SLACK = ("5.3", "Slack post to relevant channel", "5.3 P3 notification")
R_P3_NOTATION = ("5.3", "Update receiving log with P3 notation", "5.3 P3 notification")
R_P3_STATUS = ("5.3", "Log entry in receiving log with", "5.3 P3 documentation")
R_TEMP_LOG = ("6.1", "3. Record all three readings in inbound_receiving_log.xlsx.", "6.1 step 3")
R_WARMEST = ("4", "determine the tier.", "6.1 step 4")
R_ROUND = ("4", "5. Decimal readings: round to the nearest whole degree.", "6.1 step 5")
R_TIER2 = ("6.2", "Tier 2 -9°F to -5°F", "6.2 Tier 2")
R_ABS = ("1", "● Absolute variance = Actual cases", "7.1 Absolute variance")
R_PCT = ("1", "● Note: “Manifest cases” always refers", "7.1 Percentage variance")
R_MINOR = ("0", "Log in receiving log Note “Minor variance”.", "7.2 Minor variance")
R_PATTERN_SLACK = ("7.4", "If a vendor has a pattern of recurring minor variances", "7.4 Recurring Minor Variances")
R_DMG_EXACT = ("9", "The Analyst receives damage reports from the dock crew", "9 Damage Disposition Rules")
R_CLASS1 = ("9.1", "Class Definition Examples Priority Immediate Action Class 1", "9.1 Class 1")
R_DMG_LOG = ("9.2", "3. Log the damage in inbound_receiving_log.xlsx", "9.2 step 3")
R_NO_CLAIM = ("18.2", "For Class 1 damage: No claim required.", "18.2 Credit Claim Initiation")
R_PREFILL = ("3", "number, origin (", "12.1 step 3")
R_S1 = ("4", "transfer [manifest#] expected at [time].", "12.1 step 4 (Template S1)")
R_MINOR_124 = ("12.4", "● 1-3 cases and ≤1%: Minor variance.", "12.4 Minor variance")
R_UPDATE = ("12.6", "Once dock crew confirms all data is accurate", "12.6 Update Inventory Records")
R_S3 = ("12.7", "● P3 (Tier 3 temperature or Minor escalated/Moderate variance)", "12.7 P3 notifications")
R_E2 = ("22", "E2 — Waco Transfer: Variance Notification", "22 Template E2")
R_E2_BODY = ("22", "Manifest: [Manifest#] SKU affected:", "22 Template E2 body")
R_FEFO = ("1", "- SKU, zone, lot code, case count, received date, expiry date", "15.2 FEFO step 1")
R_HOLD_OPEN = ("5.3", "● If variance: hold receipt open pending variance resolution", "5.3 P3 product action")
R_NO_CLOSE = ("12.8", "● Post final confirmation to #receiving-[site]", "12.8 Close the Receipt")
R_EXPIRY_ADD = ("8", "Every time a new lot is put away", "8 Expiry Management")
R_ZONE = ("2.7", "● Signature Line (SC-001 to SC-010): Assign to H-A", "2.7 SKU-to-Zone")

# lots on manifest 2026-04-02-001 with the dock crew's counts; expiry = production + 18 months (Section 2.1)
LOTS = {
    "A-20260327-01": dict(sku="SC-001", name="Sweet Cream Prairie", qty=160, prod="2026-03-27", exp="2027-09-27", days=543),
    "A-20260327-02": dict(sku="SC-003", name="Midnight Chocolate Range", qty=119, prod="2026-03-27", exp="2027-09-27",
                          days=543),
    "A-20260328-01": dict(sku="SC-007", name="Golden Caramel Prairie Fire", qty=120, prod="2026-03-28",
                          exp="2027-09-28", days=544),
}
PRIOR = r"2026-03-25|2026-03-31|\b0?3/25\b|\b0?3/31\b|\bprior\b|\bprevious\b|\bearlier deliver"
WARM_NOTE = "Accepted – Warm side of acceptable range"
DAMAGE_REPORT = "One case label torn (SC-001 pallet 3). No breach."


def fnum(v) -> float | None:
    m = re.search(r"[-−+]?\d+(?:\.\d+)?", str(v or "").replace(",", ""))
    return float(m.group(0).replace("−", "-")) if m else None


def eqn(v, *wants: float, tol: float = 0.01) -> bool:
    x = fnum(v)
    return x is not None and any(abs(x - w) < tol for w in wants)


def date_of(v) -> str:
    s = str(v or "")
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return m.group(0)
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else ""


def has(text, phrase: str) -> bool:
    return norm(dashes(phrase)) in norm(dashes(text))


# ---- receiving log row ---------------------------------------------------------------------------------------

def receiving_checks(ctx: Context):
    w = world(ctx)
    row = w.find(LOG, r"Manifest", r"^Manifest", MANIFEST)
    if row is None:
        yield False, f"inbound_receiving_log.xlsx: the pre-filled row for manifest {MANIFEST} is missing.", [R_UPDATE]
        return
    c = lambda rx: w.col(row, rx)
    for rx, want, label in ((r"^Receipt", TODAY, "Receipt Date"), (r"^Origin", "Waco Transfer", "Origin")):
        got = date_of(c(rx)) if label == "Receipt Date" else c(rx)
        yield norm(got) == norm(want), f"Row {MANIFEST}: {label} must stay '{want}' (got '{c(rx)}').", [R_PREFILL]
    yield eqn(c(r"^Pallets"), 20) and eqn(c(r"^Cases"), 400), \
        f"Row {MANIFEST}: Pallets (Manifest) / Cases (Manifest) must stay 20 / 400 (the manifest totals).", [R_PREFILL]
    # raw readings or the Section 6.1 step 5 roundings (halves toward the warmer side)
    yield (eqn(c(r"^Temp 1"), -9.5, -9) and eqn(c(r"^Temp 2"), -10.5, -10) and eqn(c(r"^Temp 3"), -13)), \
        (f"Row {MANIFEST}: log the three readings as reported - Temp 1 (front) = -9.5, Temp 2 (middle) = -10.5, "
         f"Temp 3 (rear) = -13 (got {c(r'^Temp 1')!r}, {c(r'^Temp 2')!r}, {c(r'^Temp 3')!r})."), [R_TEMP_LOG]
    yield eqn(c(r"^Warmest"), -9.5, -9), \
        f"Row {MANIFEST}: Warmest Temp must be the front reading -9.5°F (rounded -9°F) (got {c(r'^Warmest')!r}).", \
        [R_WARMEST, R_ROUND]
    yield norm(c(r"^Temp Tier")) == "tier 2", \
        (f"Row {MANIFEST}: Temp Tier must be 'Tier 2' - warmest -9.5°F rounds toward the warmer tier to -9°F "
         f"(Tier 2, -9°F to -5°F) (got {c(r'^Temp Tier')!r})."), [R_ROUND, R_TIER2]
    yield eqn(c(r"^Actual"), 399), f"Row {MANIFEST}: Actual Cases must be 399 (got {c(r'^Actual')!r}).", [R_UPDATE]
    yield eqn(c(r"^Variance \(Cases"), -1), \
        f"Row {MANIFEST}: Variance (Cases) must be -1 (399 actual - 400 manifest) (got {c(r'^Variance \(Cases')!r}).", \
        [R_ABS]
    pct = c(r"^Variance %")
    # -0.25% exactly, or one decimal as in the log's earlier rows (-0.2% / -0.3%)
    pct_ok = (eqn(pct, -0.25, -0.2, -0.3, tol=0.006) if "%" in pct
              else eqn(pct, -0.25, -0.0025, -0.002, -0.003, tol=0.00006))
    yield pct_ok, (f"Row {MANIFEST}: Variance % must be -0.25% (-1 ÷ 400 total manifest cases, not the SKU quantity) "
                   f"(got {pct!r})."), [R_PCT]
    dmg = c(r"^Damage")
    yield (re.search(r"class\s*1", dmg, re.I) is not None and re.search(r"label", dmg, re.I) is not None
           and re.search(r"torn|tear", dmg, re.I) is not None and "SC-001" in dmg.upper()
           and re.search(r"pallet\s*3\b", dmg, re.I) is not None), \
        (f"Row {MANIFEST}: Damage Notes must give the class and the damage exactly as reported, e.g. "
         f"'Class 1 – {DAMAGE_REPORT}' (got {dmg!r})."), [R_DMG_EXACT, R_DMG_LOG]
    disp = c(r"^Disposition")
    yield norm(disp).rstrip(".") == "accept with note", \
        (f"Row {MANIFEST}: Disposition must be the Section 6.2 Acceptance value for Tier 2: 'Accept with Note' "
         f"(got {disp!r})."), [R_TEMP_LOG, R_TIER2]
    notes, status = c(r"^Notes$"), c(r"^Status")
    yield has(notes, WARM_NOTE), \
        f"Row {MANIFEST}: Notes must contain \"{WARM_NOTE}\" (Tier 2) (got {notes!r}).", [R_TIER2, R_NOTES_ONLY]
    yield has(notes, "Minor variance") or has(status, "Minor variance"), \
        f"Row {MANIFEST}: note \"Minor variance\" in the receiving log Notes (got Notes {notes!r}).", [R_MINOR]
    yield has(notes, "Class 1 damage") or has(dmg, "Class 1 damage"), \
        f"Row {MANIFEST}: note \"Class 1 damage\" in the receiving log (got Notes {notes!r}).", [R_CLASS1]
    yield not re.search(PRIOR, notes, re.I), \
        (f"Row {MANIFEST}: Notes may only hold the SOP-instructed notes (e.g. \"{WARM_NOTE}; Minor variance; "
         f"Class 1 damage\") - remove the references to prior deliveries (got {notes!r})."), [R_NOTES_ONLY]
    yield re.search(r"\bP3\b", f"{status} {notes}") is not None, \
        (f"Row {MANIFEST}: record the P3 notation (third minor Waco variance in 30 days), e.g. Status "
         f"'P3 – Open – Pending Variance Resolution (third minor variance from Waco in 30 days)' "
         f"(got Status {status!r})."), \
        [R_P3_NOTATION, R_P3_STATUS, R_MINOR_124]
    yield bool(status) and not re.search(r"pending receiving data|^pending$", status, re.I), \
        f"Row {MANIFEST}: Status is still the pre-arrival value {status!r}; update it now that receiving data is in.", \
        [R_UPDATE]
    yield not re.match(r"\s*(P\d\s*[-–—]\s*)?closed", status, re.I), \
        (f"Row {MANIFEST}: do not close the receipt while the variance explanation requested from Waco is pending - "
         f"keep it open, e.g. Status 'P3 – Open – Pending Variance Resolution' (got {status!r})."), \
        [R_HOLD_OPEN, R_NO_CLOSE]


def receiving_log_invariants(ctx: Context):
    w = world(ctx)
    gone = [r for r in w.missing_rows(LOG, r"Manifest") if norm(w.col(r, r"^Manifest")) != MANIFEST]
    yield not gone, (f"inbound_receiving_log.xlsx is a log: {len(gone)} earlier row(s) were edited or removed "
                     f"(e.g. {w.col(gone[0], r'^Manifest') if gone else ''}). Restore them."), [R_FILES]
    new = [r for r in w.new_rows(LOG, r"Manifest") if norm(w.col(r, r"^Manifest")) != MANIFEST]
    dup = [r for r in w.rows(LOG, r"Manifest") if norm(w.col(r, r"^Manifest")) == MANIFEST]
    yield not new and len(dup) <= 1, \
        (f"inbound_receiving_log.xlsx: update the pre-filled row for {MANIFEST}; do not add new rows "
         f"({len(new)} unrelated new row(s), {len(dup)} row(s) for {MANIFEST})."), [R_PREFILL, R_FILES]


# ---- inventory master / expiry tracker (checked only if the agent adds the lots) ----------------------------

KEY_INV = (r"^SKU", r"^Lot", r"^Zone", r"^Qty", r"^Expiry", r"^Status$")
KEY_EXP = (r"^SKU", r"^Lot", r"^Zone", r"^Qty", r"^Expiry")


def _keys(w, r, cols):
    return tuple(norm(w.col(r, rx)) for rx in cols)


def lot_checks(ctx: Context, name_rx: str, book: str, cols, refs, expiry: bool):
    w = world(ctx)
    init = [_keys(w, r, cols) for r in w.rows(name_rx, r"^SKU$", "initial")]
    cur = [_keys(w, r, cols) for r in w.rows(name_rx, r"^SKU$")]
    gone = [k for k in init if k not in cur]
    yield not gone, f"{book}: existing lot rows were changed or removed (e.g. {' | '.join(gone[0][:2]) if gone else ''})." \
                    " Leave earlier lots as they were.", refs
    new = w.new_rows(name_rx, r"^SKU$")
    if not new:
        return
    seen = {}
    for r in new:
        lot = w.col(r, r"^Lot").upper()
        exp = LOTS.get(lot)
        if exp is None:
            yield False, (f"{book}: new row for lot {lot or '(blank)'} does not belong to manifest {MANIFEST} "
                          f"(lots: {', '.join(LOTS)}). Remove it."), refs
            continue
        seen[lot] = seen.get(lot, 0) + 1
        bad = []
        if norm(w.col(r, r"^SKU")) != norm(exp["sku"]):
            bad.append(f"SKU {exp['sku']}")
        if norm(w.col(r, r"^Zone")) != "h-a":
            bad.append("Zone H-A")
        if not eqn(w.col(r, r"^Qty"), exp["qty"]):
            bad.append(f"Qty {exp['qty']}")
        if date_of(w.col(r, r"^Expiry")) != exp["exp"]:
            bad.append(f"Expiry Date {exp['exp']}")
        if date_of(w.col(r, r"^Production")) not in ("", exp["prod"]):
            bad.append(f"Production Date {exp['prod']}")
        if expiry:
            days = w.col(r, r"^Days")
            if days and not days.startswith("=") and not eqn(days, exp["days"]):
                bad.append(f"Days Remaining {exp['days']}")
            if norm(w.col(r, r"^Status")) != "green":
                bad.append("Status Flag Green")
        else:
            if date_of(w.col(r, r"^Receipt")) != TODAY:
                bad.append(f"Receipt Date {TODAY}")
            if norm(w.col(r, r"^Status")) != "active":
                bad.append("Status Active")
        yield not bad, f"{book}: row for lot {lot} needs " + ", ".join(bad) + ".", refs
    if seen:
        missing = [l for l in LOTS if l not in seen]
        dupes = [l for l, n in seen.items() if n > 1]
        yield not missing and not dupes, (f"{book}: add exactly one row per lot received on {MANIFEST} "
                                           f"(missing: {', '.join(missing) or 'none'}; duplicated: "
                                           f"{', '.join(dupes) or 'none'})."), refs


def new_books(ctx: Context):
    w = world(ctx)
    extra = [b for b in w.created_books()
             if not re.search(r"(cycle_count_log|vendor_master|vendor_scorecard)\.xlsx$", b, re.I)]
    yield not extra, (f"New workbook(s) {extra}: do not create personal copies or informal tracking files - "
                      "record the work in the official files and delete these."), [R_FILES]


# ---- messages ------------------------------------------------------------------------------------------------

def specs(ctx: Context) -> list[Comm]:
    w = world(ctx)

    def in_channel(a: Action, ch: str) -> bool:
        return a.kind == "slack_post" and not w.dm_recipients(a) and w.is_channel(a.channel, ch)

    def is_s1(a: Action) -> bool:
        return re.search(r"expected at", a.text, re.I) is not None

    def is_receipt_update(a: Action) -> bool:
        return re.search(r"variance detected|received with flags|received and accepted|\bvariance:|\btemp:",
                         a.text, re.I) is not None

    return [
        Comm("e2_variance", "email",
             lambda a: a.kind == "email_send" and MANIFEST in text_of(a) and re.search(r"variance", a.subject, re.I),
             f"P3 variance notification (Template E2) for manifest {MANIFEST}", [R_S3, R_MINOR_124, R_E2, R_E2_BODY,
                                                                                R_P3_EMAIL, R_SUBJECT],
             to=[PLANNER], cc=[DC_MGR], exact_to=False,
             subject=rf"P3 – Variance Notification – (?:Inbound )?(?:Waco )?(?:Manifest )?{MANIFEST} – {TODAY}\.?",
             subject_hint=f"P3 – Variance Notification – {MANIFEST} – {TODAY}",
             body=[(MANIFEST, f"Manifest: {MANIFEST}"), (r"SC-003", "SKU affected: SC-003"),
                   (r"0\.25\s*%", "Overall Variance: -1 cases (-0.25%) (percentage of the 400-case manifest total)"),
                   (r"Classification:\s*Minor", "Classification: Minor"),
                   (r"pattern escalation|third minor", "Pattern escalation (third minor variance from Waco in 30 days)"),
                   (r"explanation or corrective action", "Please provide explanation or corrective action.")]),
        Comm("s3_flags", "slack_post",
             lambda a: in_channel(a, "receiving-houston") and MANIFEST in a.text and not is_s1(a)
             and is_receipt_update(a),
             f"Template S3 (Receipt with Flags) post for manifest {MANIFEST}", [R_S3, R_P3_SLACK, R_PATTERN_SLACK],
             channel="receiving-houston",
             body=[(rf"Variance detected\.?\s*Manifest {MANIFEST} received with flags",
                    f"Variance detected. Manifest {MANIFEST} received with flags."),
                   (r"Temp:\s*[-−]9\s*°?\s*F?(?![\d.])",
                    "Temp: -9°F (warmest reading -9.5°F rounded) with the priority in parentheses"),
                   (r"Variance:\s*[-−]?1\s*cases?\b", "Variance: -1 cases"),
                   (r"Email sent to", "Email sent to the Production Planner and DC Manager.")],
             banned=[(PRIOR + r"|\bthird\b|\b3rd\b|in 30 days",
                      "Include only the current delivery's temperature and variance data - do not reference the "
                      "prior deliveries or the pattern in this post.")]),
        Comm("s1_repost", "slack_post", lambda a: a.kind == "slack_post" and MANIFEST in a.text and is_s1(a),
             f"S1 arrival post for {MANIFEST}", [R_S1],
             forbidden=(f"The S1 arrival post for {MANIFEST} was already posted in #receiving-houston this morning "
                        "and Alicia's receiving report is already in the inbox ('Manifest 2026-04-02-001 – "
                        "Receiving Complete'). Do not repeat pre-arrival steps; process the report.")),
        Comm("waco_coord_post", "slack_post",
             lambda a: in_channel(a, "waco-production-coord") and MANIFEST in a.text,
             f"#waco-production-coord post about {MANIFEST}", [R_MINOR_124, R_S3, R_P3_SLACK],
             forbidden=("A minor variance escalated to P3 as a pattern uses only the Section 12.7 notifications: the "
                        "S3 post in #receiving-houston and the email to the Production Planner (cc DC Manager).")),
        Comm("class1_claim", "email",
             lambda a: a.kind in ("email_send", "email_draft") and MANIFEST in text_of(a)
             and re.search(r"credit claim", a.subject, re.I),
             f"credit claim for manifest {MANIFEST}", [R_CLASS1, R_NO_CLAIM],
             forbidden="The only damage is Class 1 (one torn label): no credit claim is filed for Class 1 damage."),
    ]


def s3_thread(ctx: Context, a: Action):
    w = world(ctx)
    if a.kind != "slack_post" or w.dm_recipients(a) or not w.is_channel(a.channel, "receiving-houston"):
        return None
    if MANIFEST not in a.text or re.search(r"expected at", a.text, re.I):
        return None
    if any(S1_TS in str(v) for k, v in a.args.items() if k not in ("text", "summary")):
        return None
    return (f"Post this update to manifest {MANIFEST} as a reply in the thread of this morning's S1 arrival post "
            f"(#receiving-houston, thread_ts {S1_TS}.000000), not as a new top-level message.")


def no_at_channel(ctx: Context, a: Action):
    if a.kind in ("slack_post", "slack_dm") and re.search(r"@channel|@here|<!channel>|<!here>", a.text, re.I):
        return "Do not use @channel or @here - this is not a P1 event."
    return None


RULES = (
    forbid_writes("a9.manifests_readonly", r"^\d{4}-\d{2}-\d{2}-\d{3}\.pdf$|SOP_?\.pdf$",
                  "transfer manifests (and the SOP) are read-only reference documents.", [R_READONLY])
    + comm_rules("a9.comms", specs)
    + pre_rule("a9.s3_thread", s3_thread, [R_SUBJECT, R_S3], "Use slack__reply_to_thread with that thread_ts.")
    + pre_rule("a9.no_at_channel", no_at_channel, [R_SUBJECT], "Tag the relevant people instead.")
    + no_placeholders([R_E2])
    + state_rule("a9.receiving_row", receiving_checks, "Update that cell of the 2026-04-02-001 row as listed.")
    + state_rule("a9.receiving_log_append_only", receiving_log_invariants)
    + state_rule("a9.inventory_rows", lambda ctx: lot_checks(ctx, INV, "inventory_master.xlsx", KEY_INV,
                                                             [R_UPDATE, R_FEFO, R_ZONE], expiry=False))
    + state_rule("a9.expiry_rows", lambda ctx: lot_checks(ctx, EXP, "expiry_tracker.xlsx", KEY_EXP,
                                                          [R_UPDATE, R_EXPIRY_ADD, R_ZONE], expiry=True))
    + append_only("a9.temperature_log_append_only", TEMP, r"^Zone$", "temperature_log.xlsx (April)", [R_FILES],
                  sheet_rx=r"April")
    + state_rule("a9.no_new_workbooks", new_books)
)
