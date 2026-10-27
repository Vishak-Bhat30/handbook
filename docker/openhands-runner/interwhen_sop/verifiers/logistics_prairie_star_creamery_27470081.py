"""SOP verifiers for logistics_prairie_star_creamery_27470081 (Prairie Star Creamery, Houston DC receiving).

Situation (seed data, 2026-04-15 11:45 CDT): three Waco transfers were received this morning and reported by
Alicia Nguyen in #receiving-houston; nothing is put away until after lunch.
  2026-04-15-001  temps -18/-16/-20 (Tier 1), 26 pallets, 492 cases = manifest; SW-008 lot C-20260201-01 expires
                  2026-05-01 = 16 days (Orange) -> inbound short-dated product, P3 (SOP 8.2 / 5.3).
  2026-04-15-002  temps -18/-16/-20 (Tier 1), 522 vs 520 cases; per SKU (7.3): SC-006 194/200 (-6, -3%, Moderate),
                  SC-008 168/160 (+8, +5% > 3% -> Major, round-up rule 5.5) -> P2 Major variance.
  2026-04-15-003  temps -5/-4.5/-4 (warmest -4 -> Tier 3, P3) + SC-003 156/160 (-4, Moderate, P3) -> compound P2 (5.5).
"""

from __future__ import annotations

import re
from collections import Counter

from interwhen_sop import config
from interwhen_sop.kit import (COMM_KINDS, Action, Context, Finding, Rule, World, attachments, blank, cites, dashes,
                               docx_text, nh, no_placeholders, norm, num, pre_rule, registry, same, text_of, world)

TODAY = "2026-04-15"
M1, M2, M3 = "2026-04-15-001", "2026-04-15-002", "2026-04-15-003"
DIRECTOR, DCM, PP, DPM = ("daniel.reyes@prairiestar.com", "carlos.mendoza@prairiestar.com",
                          "jacob.patel@prairiestar.com", "emily.carter@prairiestar.com")
SD_SKU, SD_LOT = "SW-008", "C-20260201-01"

# ---- SOP references (section, paragraph prefix, label) -------------------------------------------
R_SUBJ = ("1.7", "Email Subject Line Format:", "1.7 email subject format")
R_THREAD = ("1.7", "Slack Threading:", "1.7 Slack threading / no @channel")
R_COPIES = ("4", "The following files are the Analyst", "4 official files only")
R_RECV = ("4", "inbound_receiving_log.xlsx", "4 receiving log")
R_MANIF = ("4", "transfer_manifests/", "4 manifests read-only")
R_POS = ("4", "vendor_pos/", "4 vendor POs read-only")
R_INV = ("4", "inventory_master.xlsx", "4 inventory master")
R_INV2 = ("4", "(Active/Hold/Quarantine)", "4 inventory master updated after put-away")
R_TLOG = ("4", "temperature_log.xlsx", "4 temperature log")
R_IRDIR = ("4", "incident_reports/", "4 incident reports")
R_HIGHER = ("5", "When you encounter an event", "5 choose the higher level")
R_P2_EX = ("5.2", "Major quantity variance (>10 cases", "5.2 P2 major variance")
R_P2_MAIL = ("5.2", "Email to the Director of Supply Chain (cc: DC Manager, relevant", "5.2 P2 email")
R_P2_SLACK = ("5.2", "Slack post to #dc-escalations thread with", "5.2 P2 Slack post")
R_P2_FMT = ("5.2", "Slack message format:", "5.2 P2 Slack format")
R_P2_PP = ("5.2", "If inbound Waco, also notify the Production Planner", "5.2 notify Production Planner")
R_P2_IR = ("5.2", "Incident report required (Word template)", "5.2 P2 incident report")
R_P2_LOG = ("5.2", "Log entry in receiving log with", "5.2 P2 log status")
R_SD_EX = ("5.3", "Inbound short-dated product (arriving with <45 days", "5.3 short-dated = P3")
R_P3_MAIL = ("5.3", "Email notification to relevant stakeholders", "5.3 P3 email")
R_P3_SLACK = ("5.3", "Slack post to relevant channel", "5.3 P3 Slack post")
R_P3_LOG = ("5.3", "Update receiving log with P3 notation", "5.3 P3 log notation")
R_P3_HOLD = ("5.3", "If variance: hold receipt open", "5.3 hold variance receipts open")
R_COMPOUND = ("5.5", "Compound events:", "5.5 compound events")
R_ROUNDUP = ("5.5", "Round up rule:", "5.5 round up rule")
R_REC3 = ("6.1", "3. Record all three readings", "6.1 record readings")
R_WARM = ("6.1", "4. The warmest of the three readings", "6.1 warmest reading controls")
R_DEC = ("6.1", "5. Decimal readings:", "6.1 decimal rounding")
R_T1 = ("6.2", "Tier 1 | ≤ -10°F", "6.2 Tier 1")
R_T3 = ("6.2", "Tier 3 | -4°F to 0°F", "6.2 Tier 3")
R_MULTI = ("6.3", "Multiple Readings, Multiple Lots:", "6.3 each manifest independently")
R_VAR = ("7.1", "Variance is the difference between each individual product", "7.1 per-product variance")
R_EXACT = ("7.2", "0 cases | 0% | Exact Match", "7.2 exact match")
R_MOD = ("7.2", "4–10 cases | OR 1–3% | Moderate", "7.2 Moderate variance")
R_MAJ = ("7.2", ">10 cases | OR >3% | Major", "7.2 Major variance")
R_PERSKU = ("7.3", "Calculate variance for each SKU independently.", "7.3 per-SKU variance")
R_MIXMAJ = ("7.3", "If one SKU has a Major variance", "7.3 Major on one SKU -> P2")
R_SD = ("8.2", "When inbound product arrives with less than 45 days", "8.2 inbound short-dated")
R_SD_MAIL = ("8.2", "2. Send email to the Production Planner and cc the Demand Planning Manager", "8.2 short-dated emails")
R_AVG = ("12.3", "Receive the three temperature readings and average.", "12.3 temperature table")
R_12T3 = ("12.3", "Tier 3 (-4 to 0°F): Accept conditionally.", "12.3 Tier 3")
R_12EX = ("12.4", "0 cases: Exact match.", "12.4 exact match")
R_12MOD = ("12.4", "4-10 cases or 1-3%: Moderate variance.", "12.4 Moderate variance")
R_12MAJ = ("12.4", ">10 cases or >3%: Major variance.", "12.4 Major variance")
R_FILL = ("12.6", "inbound_receiving_log.xlsx: Fill in all temperature readings", "12.6 receiving log")
R_TFILL = ("12.6", "temperature_log.xlsx: Log all three temperature readings", "12.6 temperature log")
R_INVPUT = ("12.6", "inventory_master.xlsx (after put-away confirmation)", "12.6 inventory after put-away")
R_N_P4 = ("12.7", "P4 (clean receipt, Tier 1 temperature, exact match):", "12.7 P4 notifications")
R_N_P3 = ("12.7", "P3 (Tier 3 temperature or Minor/Moderate variance):", "12.7 P3 notifications")
R_N_P2 = ("12.7", "P2 (Tier 4 temperature, Major variance, Class 2-3 damage):", "12.7 P2 notifications")
R_NOCLOSE = ("12.8", "Do not close if items remain pending.", "12.8 do not close")
R_FEFO = ("15.2", "1. After put-away confirmation", "15.2 add lots after put-away")
R_INBOUND = ("19.3", "Handled during receiving processing (Section 12).", "19.3 inbound load events")
R_IR_P2 = ("21.1", "P2 events: All urgent incidents", "21.1 P2 incident report")
R_IR_NAME = ("21.2", "1. Create document using the Word incident report template.", "21.2 IR file name")
R_IR_SEQ = ("21.2", "IR-001-2026-04-15-Temperature-Excursion.docx. The sequence", "21.2 IR sequence/category")
R_IR_FIELDS = ("21.2", "2. Complete required fields:", "21.2 IR fields")
R_IR_ROUTE = ("21.2", "3. Route for review.", "21.2 route IR to DC Manager")
R_TPL = ("22", "The following email templates are referenced", "22 email templates")
R_E2S = ("22", "Subject: [Priority] – Variance Notification – [Manifest#]", "22 E2 subject")
R_E2F = ("22", "Required fields: manifest number, SKU(s) affected", "22 E2 fields")
R_E3F = ("22", "Required fields: manifest number, temperature readings, tier classification", "22 E3 fields")

DATE_RX = r"(?:2026-04-15|0?4/15/(?:20)?26|April 15,? 2026|Apr\.? 15,? 2026)"
SUBJ_RX = rf"P[1-4] – .+ – {DATE_RX}\s*"
# other subject formats the SOP itself prints: E15 / 20.6 handoff, 18.2 credit claim, 18.3 / 16.4 follow-ups
SUBJ_OK_RX = rf"(?:P4 – )?End-of-Shift Handoff – {DATE_RX} – .+|Credit Claim – .+|Follow-Up: .+"
SOP_PLACEHOLDER_RX = (r"\[(?:brief description[^\]]*|pending/open/closed|recipient.s slack name|variance detail|"
                      r"minor/moderate/major|open – pending response / resolved|temp[123]|classification|"
                      r"accept/quarantine/reject|slack username\(s\) of recipient\(s\)|optional)\]")
E2_RX = rf"P2 – Variance Notification – (?:Inbound )?(?:Waco )?(?:Transfer )?(?:Manifest )?{M2} – {DATE_RX}\s*"
E2_HINT = f"P2 – Variance Notification – Inbound Waco Manifest {M2} – {TODAY}"
INITIALS_RX = r"A\.?\s?(?:Nguyen|N\.?)"


# ---- helpers -------------------------------------------------------------------------------------

def _t(s) -> str:
    """Dash-normalised text with en/em/unicode minus before digits turned into '-'."""
    return re.sub(r"[–—−](?=\d)", "-", dashes(s))


def _cell(v) -> str:
    s = nh(v)
    if s.endswith(" 00:00:00"):
        s = s[:-9]
    n = num(s)
    if n is not None and re.fullmatch(r"[-+$\d.,%\s]+", s):
        return f"{n:.4f}"
    return s.lower()


def _row_norm(cells) -> tuple:
    out = [_cell(c) for c in cells]
    while out and out[-1] == "":
        out.pop()
    return tuple(out)


def _vals(r: dict) -> list[str]:
    return [v for k, v in r.items() if k != "__row__"]


def _raw(r: dict, rx: str) -> str:
    """Cell text as stored (World.col maps the literal text 'None' to '')."""
    return next((str(v).strip() for k, v in r.items() if k != "__row__" and re.search(rx, k, re.I)), "")


def _emails(w: World) -> list[Action]:
    return [a for a in w.comms() if a.kind == "email_send"]


def _to(a: Action) -> set[str]:
    return {x.lower() for x in a.recipients}


def _all(a: Action) -> set[str]:
    return _to(a) | {x.lower() for x in a.cc}


def _has(rx: str, s: str) -> bool:
    return bool(re.search(rx, s, re.I | re.S))


def _neg(n: str) -> str:
    return rf"(?<![\d.])-{re.escape(n)}(?![\d.])"


def _msg_check(cands: list[Action], what: str, reqs: list[tuple], hint: str) -> tuple[bool, str]:
    """reqs: (predicate(action) -> bool, description). OK when one candidate meets every requirement."""
    best, best_miss = None, None
    for a in cands:
        miss = [d for p, d in reqs if not p(a)]
        if not miss:
            return True, ""
        if best_miss is None or len(miss) < len(best_miss):
            best, best_miss = a, miss
    if best is None:
        return False, f"Not yet done per the SOP: {what}. {hint}"
    shown = f"subject \"{best.subject}\"" if best.subject else f"text \"{nh(best.text)[:80]}\""
    return False, f"{what}: the closest message ({shown}) is missing: {'; '.join(best_miss)}. {hint}"


def _completion(rule_id: str, checks) -> list[Rule]:
    """Completion rule; ``checks(ctx)`` yields (ok, problem, refs, fix)."""
    rules: list[Rule] = []
    rule = registry(rules)

    @rule(rule_id, "completion", [])
    def check(ctx: Context) -> list[Finding]:
        return [Finding(rule_id, cites(ctx, refs), problem, [fix]) for ok, problem, refs, fix in checks(ctx) if not ok]

    return rules


def _mentions_today(a: Action) -> bool:
    t = _t(text_of(a))
    return any(x in t for x in (M1, M2, M3, SD_SKU, SD_LOT))


# ---- pre rules -----------------------------------------------------------------------------------

def _subject_format(ctx: Context, a: Action):
    if a.kind not in ("email_send", "email_draft") or not a.subject.strip() or not _mentions_today(a):
        return None
    s = _t(a.subject).strip()
    if re.fullmatch(SUBJ_RX, s) or re.fullmatch(SUBJ_OK_RX, s, re.I):
        return None
    return (f"Email subject \"{a.subject}\" does not follow the SOP format \"[Priority] – [Category] – [Source] "
            f"[Reference#] – [Date]\", e.g. \"P2 – Variance Notification – Inbound Waco Manifest {M2} – {TODAY}\" or "
            f"\"P3 – Inbound Short-Dated Product – Waco Manifest {M1} – {TODAY}\".")


def _e2_subject(ctx: Context, a: Action):
    if a.kind not in ("email_send", "email_draft"):
        return None
    s = _t(a.subject).strip()
    if M2 not in s or not _has(r"variance", s) or re.fullmatch(E2_RX, s):
        return None
    if _has(r"incident|credit claim|follow[- ]?up|end[- ]of[- ]shift|handoff", s):
        return None
    return f"Variance email subject for manifest {M2} must follow template E2 exactly: \"{E2_HINT}\" (got \"{a.subject}\")."


def _variance002(ctx: Context, a: Action):
    if a.kind not in COMM_KINDS:
        return None
    why = (f"Manifest {M2} has a MAJOR variance: variance is calculated per SKU (7.3) and SC-008 is 168 received vs "
           "160 on the manifest (+8 cases, +5% > 3%), so it is Major / P2 even though SC-006 (-6, -3%) is Moderate "
           "and the net receipt is only +2. When an event fits two levels choose the higher one (5.5).")
    if a.kind in ("email_send", "email_draft"):
        s = _t(a.subject)
        if M2 in s and re.match(r"\s*P[34]\b", s):
            return f"{why} Use priority P2 in the subject, e.g. \"{E2_HINT}\"."
        return None
    t = _t(a.text)
    if M2 in t and _has(r"\b(?:P3|P4|Minor|Moderate)\b", t) and not _has(r"\b(?:P2|Major)\b", t):
        return f"{why} State it as Major / P2 in this message."
    return None


def _sop_placeholders(ctx: Context, a: Action):
    if a.kind not in COMM_KINDS:
        return None
    left = sorted(set(re.findall(SOP_PLACEHOLDER_RX, _t(text_of(a)), re.I)))
    return f"The message still contains SOP format placeholders {left}; replace them with the actual values." if left else None


def _no_channel(ctx: Context, a: Action):
    if a.kind not in ("slack_post", "slack_dm"):
        return None
    if _has(r"@channel|@here|<!channel>|<!here>|<!everyone>", a.text):
        return "Do not use @channel or @here: they are reserved for P1 events and none of today's receipts is P1."
    return None


# ---- completion rules: receiving log -------------------------------------------------------------

RECV = r"inbound_receiving_log"
RECV_H = r"^Manifest / PO"
EXPECT = {
    M1: dict(cases=492, temps=[(-20, -18, -16)], avg=(-18,), tier="1", var=(0,), pri="P3",
             status=f"Received – Pending Put-Away (P3 – short-dated {SD_SKU} lot {SD_LOT}, 16 days, Orange)"),
    M2: dict(cases=522, temps=[(-20, -18, -16)], avg=(-18,), tier="1", var=None, pri="P2",
             status="P2 – Major Variance (SC-008 +8, SC-006 -6) – Open – Pending Major Variance Investigation"),
    M3: dict(cases=516, temps=[(-5, -4.5, -4), (-5, -4, -4)], avg=(-4.5, -4), tier="3", var=(-4, 4), pri="P2",
             status="P2 – Tier 3 temp + Moderate variance (compound) – Open – Pending Variance Resolution / "
                    "Director review"),
}


def _recv_rows(w: World, m: str, which: str = "current") -> list[dict]:
    return [r for r in w.rows(RECV, RECV_H, which) if norm(World.col(r, r"^Manifest")) == m]


def _fill_checks(ctx: Context):
    w = world(ctx)
    refs = [R_FILL, R_REC3, R_AVG, R_WARM, R_DEC, R_T1, R_T3, R_MULTI, R_EXACT, R_12EX, R_PERSKU, R_INBOUND]
    for m, e in EXPECT.items():
        rows = _recv_rows(w, m)
        if not rows:
            yield False, f"inbound_receiving_log.xlsx has no row for manifest {m}.", [R_RECV], \
                f"Fill in the pre-filled row for manifest {m}."
            continue
        r = rows[0]
        c = lambda rx: World.col(r, rx)
        miss = []
        if not same(c(r"^Pallets \(Actual"), 26):
            miss.append("Pallets (Actual) = 26")
        if not same(c(r"^Cases \(Actual"), e["cases"]):
            miss.append(f"Cases (Actual) = {e['cases']}")
        temps = tuple(sorted(n for n in (num(c(rf"^Temp Reading {i}")) for i in (1, 2, 3)) if n is not None))
        if temps not in e["temps"]:
            miss.append("Temp Reading 1/2/3 (front/middle/rear) = " + ", ".join(
                f"{v:g}" for v in {M3: (-5, -4.5, -4)}.get(m, (-18, -16, -20))))
        avg = num(c(r"^Temp Avg"))
        if avg is None or not any(abs(avg - v) < 0.01 for v in e["avg"]):
            miss.append(f"Temp Avg = {e['avg'][0]:g}")
        if not re.fullmatch(rf"(?:tier\s*)?{e['tier']}\b.*", norm(c(r"^Temp Tier"))):
            miss.append(f"Temp Tier = Tier {e['tier']}")
        v = c(r"^Variance \(Cases")
        if blank(v) or (e["var"] is not None and not any(same(v, x) for x in e["var"])):
            miss.append("Variance (Cases) = " + ("0" if m == M1 else "-4" if m == M3 else
                                                  "the variance (net +2; SC-006 -6, SC-008 +8)"))
        if not _raw(r, r"^Damage"):
            miss.append("Damage Notes = None (no damage reported)")
        if miss:
            yield False, f"Receiving log row for manifest {m} is incomplete/incorrect: {'; '.join(miss)}.", refs, \
                f"Update the existing row for {m} in inbound_receiving_log.xlsx with these values."


def _status_checks(ctx: Context):
    w = world(ctx)
    for m, e in EXPECT.items():
        rows = _recv_rows(w, m)
        if not rows:
            continue
        r = rows[0]
        st = World.col(r, r"^Status$")
        text = " | ".join(v for k, v in r.items() if k != "__row__" and not re.match(r"^(Temp|Pallets|Cases)", k))
        refs = [R_FILL, R_NOCLOSE, R_P2_LOG if e["pri"] == "P2" else R_P3_LOG]
        if m == M2:
            refs += [R_MAJ, R_MIXMAJ, R_12MAJ]
        if m == M3:
            refs += [R_COMPOUND, R_12MOD, R_P3_HOLD]
        if m == M1:
            refs += [R_SD_EX]
        fix = f"Set the Status for {m} to e.g. \"{e['status']}\"."
        if blank(st) or norm(st) == "pending":
            yield False, f"Receiving log Status for manifest {m} is not filled in.", refs, fix
        elif _has(r"^\s*closed|put[- ]?away complete", st):
            yield False, (f"Receiving log Status for manifest {m} is \"{st}\", but nothing has been put away yet "
                          "(put-away is after lunch) and the receipt has pending items, so it must stay open."), refs, fix
        elif not re.search(rf"\b{e['pri']}\b", text):
            yield False, (f"Receiving log row for manifest {m} must carry the {e['pri']} notation "
                          f"(\"{e['pri']} – [Description]\") in its status."), refs, fix


def _one_row_checks(ctx: Context):
    w = world(ctx)
    for m in (M1, M2, M3):
        n = len(_recv_rows(w, m))
        yield n <= 1, (f"inbound_receiving_log.xlsx has {n} rows for manifest {m}; the log keeps one row per "
                       "inbound shipment."), [R_RECV], f"Keep only the pre-filled row for {m} and fill it in."


# ---- completion rules: temperature log -----------------------------------------------------------

TLOG = r"temperature_log"
TLOG_H = r"^Zone / Inbound Source"
TEMPS = {M1: [-18, -16, -20], M2: [-18, -16, -20], M3: [-5, -4.5, -4]}


def _temp_checks(ctx: Context):
    w = world(ctx)
    refs = [R_TFILL, R_REC3, R_TLOG]
    rows = w.rows(TLOG, TLOG_H)
    first, last = {}, {}
    for m, want in TEMPS.items():
        mine = [r for r in rows if any(m in _t(v) for v in _vals(r))]
        readings = [(r, num(World.col(r, r"^Reading"))) for r in mine]
        readings = [(r, n) for r, n in readings if n is not None]
        if mine:
            first[m], last[m] = min(int(r["__row__"]) for r in mine), max(int(r["__row__"]) for r in mine)
        have = Counter(n for _, n in readings)
        need = Counter(want)
        ok = all(have[k] >= cnt for k, cnt in need.items()) or (
            m == M3 and all(have[k] >= cnt for k, cnt in Counter([-5, -4, -4]).items()))
        if not ok:
            yield False, (f"temperature_log.xlsx is missing the three inbound readings for manifest {m}: "
                          f"Front {want[0]:g}, Middle {want[1]:g}, Rear {want[2]:g} °F."), refs, \
                (f"Append three rows: Date {TODAY} | Time | \"Inbound – Manifest {m}\" | reading | "
                 "\"Inbound – Front/Middle/Rear\" | Within Range | Action Taken | A.Nguyen.")
            continue
        bad = [r["__row__"] for r, _ in readings if not re.fullmatch(INITIALS_RX, nh(World.col(r, r"^Initials")), re.I)]
        if bad:
            yield False, (f"temperature_log.xlsx rows {', '.join(bad)} for manifest {m} need Alicia Nguyen's initials "
                          "\"A.Nguyen\" (the user said her initials may be used)."), refs, \
                "Put \"A.Nguyen\" in the Initials column of these rows."
    if len(first) == 3 and not (last[M1] < first[M2] and last[M2] < first[M3]):
        yield False, (f"Log the inbound temperature readings in the order the trucks came in: {M1}, then {M2}, then "
                      f"{M3}."), refs, "Reorder the new temperature_log.xlsx rows."


# ---- completion rules: invariants ------------------------------------------------------------------

def _append_checks(ctx: Context):
    w = world(ctx)
    # receiving log: earlier receipts unchanged, today's pre-filled identity cells unchanged
    init = w.rows(RECV, RECV_H, "initial")
    cur = w.rows(RECV, RECV_H)
    cur_norm = Counter(_row_norm(_vals(r)) for r in cur)
    keys = r"^(Receipt Date|Manifest|Origin|Pallets \(Manifest|Cases \(Manifest)"
    bad = []
    for r in init:
        m = norm(World.col(r, r"^Manifest"))
        if m in (M1, M2, M3):
            now = _recv_rows(w, m)
            if now and all(_cell(v) == _cell(World.col(now[0], re.escape(k)))
                           for k, v in r.items() if k != "__row__" and re.match(keys, k)):
                continue
            if now:
                bad.append(f"{m} (pre-filled date/manifest/origin/manifest pallets & cases)")
            continue
        key = _row_norm(_vals(r))
        if cur_norm[key] > 0:
            cur_norm[key] -= 1
        else:
            bad.append(m or f"row {r['__row__']}")
    yield not bad, (f"inbound_receiving_log.xlsx existing entries were changed: {', '.join(bad)}. Earlier receipts "
                    "stay as recorded; only fill in today's rows."), [R_RECV], "Restore the original values."
    # temperature log append-only
    init_t = [_row_norm(_vals(r)) for r in w.rows(TLOG, TLOG_H, "initial")]
    cur_t = Counter(_row_norm(_vals(r)) for r in w.rows(TLOG, TLOG_H))
    gone = []
    for k in init_t:
        if cur_t[k] > 0:
            cur_t[k] -= 1
        else:
            gone.append(" | ".join(k[:3]))
    yield not gone, (f"temperature_log.xlsx is a record log: {len(gone)} existing reading(s) were edited or removed "
                     f"(e.g. {gone[0] if gone else ''})."), [R_TLOG], "Restore them and only append new rows."


def _inv_key(r: dict) -> tuple:
    return (norm(World.col(r, r"^SKU$")), norm(World.col(r, r"^Lot Code$")), _cell(World.col(r, r"^Qty")))


def _inventory_checks(ctx: Context):
    w = world(ctx)
    init = Counter(_inv_key(r) for r in w.rows(r"inventory_master", r"^Lot Code$", "initial"))
    cur = Counter(_inv_key(r) for r in w.rows(r"inventory_master", r"^Lot Code$"))
    if not init:
        return
    added, removed = cur - init, init - cur
    diff = [f"{s.upper()} {lot.upper()} qty {q}" for (s, lot, q) in list(added) + list(removed)]
    yield not diff, ("inventory_master.xlsx lots/quantities changed (" + "; ".join(diff[:4]) + "). Inventory is only "
                     "updated after the dock crew confirms put-away, and none of today's receipts is put away until "
                     "after lunch."), [R_INVPUT, R_INV, R_INV2, R_FEFO], \
        "Revert the inventory_master.xlsx lot rows/quantities; record the lots after put-away confirmation."


RO_RX = r"^(?:\d{4}-\d{2}-\d{2}-\d{3}|[A-Z]{3}-\d{2}-(?:PO|DO)-\d+)\.xlsx$"


def _book_norm(book) -> dict:
    if not isinstance(book, dict):
        return {}
    return {s: [r for r in (_row_norm(row) for row in rows) if r] for s, rows in book.items()}


def _readonly_checks(ctx: Context):
    w = world(ctx)
    bad = [k for k in w.initial if re.search(RO_RX, k.split("/")[-1])
           and _book_norm(w.current.get(k)) != _book_norm(w.initial[k])]
    yield not bad, (f"Transfer manifests and vendor POs are read-only reference documents, but {', '.join(bad)} "
                    "changed."), [R_MANIF, R_POS], "Restore those files to their original content."


def _copies_checks(ctx: Context):
    w = world(ctx)
    new = w.created_books()
    yield not new, (f"New workbook(s) {', '.join(new)} were created. Record all work in the official files; do not "
                    "create personal copies or informal tracking documents."), [R_COPIES], "Remove the extra workbooks."


# ---- completion rules: messages --------------------------------------------------------------------

def _message_checks(ctx: Context):
    w = world(ctx)
    em = _emails(w)
    body = lambda a: _t(text_of(a))

    def about(m):
        return [a for a in em if m in body(a)]

    # 002 major variance -> Director (cc DC Manager, Production Planner), template E2
    yield (*_msg_check(
        [a for a in em if M2 in _t(a.subject)], f"P2 Major variance email for manifest {M2}",
        [(lambda a: DIRECTOR in _to(a), f"To {DIRECTOR}"),
         (lambda a: DCM in _all(a), f"cc {DCM}"),
         (lambda a: PP in _all(a), f"cc {PP}"),
         (lambda a: re.fullmatch(E2_RX, _t(a.subject).strip()), f"subject \"{E2_HINT}\""),
         (lambda a: _has(r"SC-008", body(a)) and _has(r"\b168\b", body(a)) and _has(r"\b160\b", body(a)),
          "SC-008 manifest 160 / actual 168 (+8, +5%)"),
         (lambda a: _has(r"SC-006", body(a)) and _has(r"\b194\b", body(a)) and _has(r"\b200\b", body(a)),
          "SC-006 manifest 200 / actual 194 (-6, -3%)"),
         (lambda a: _has(r"\bmajor\b", body(a)), "classification Major"),
         (lambda a: _has(r"investigat", body(a)), "request for immediate investigation")],
        f"Email {DIRECTOR} (cc {DCM}, {PP}), subject \"{E2_HINT}\", with manifest {M2}, per-SKU variance "
        "(SC-006 200→194 -6 -3% Moderate; SC-008 160→168 +8 +5% Major), classification Major and a request for "
        "immediate investigation."),
        [R_MAJ, R_12MAJ, R_P2_MAIL, R_P2_PP, R_N_P2, R_E2S, R_E2F],
        "Send the email as described.")

    # 002 Slack variance post in #waco-production-coord
    posts = [a for a in w.posts_in("waco-production-coord") if M2 in _t(a.text)]
    yield (*_msg_check(
        posts, f"#waco-production-coord variance post for manifest {M2}",
        [(lambda a: _has(r"variance detected", _t(a.text)), "the SOP format \"Variance detected. ...\""),
         (lambda a: _has(r"SC-008", _t(a.text)), "SKU SC-008 (+8)"),
         (lambda a: _has(r"\bmajor\b", _t(a.text)), "Variance tier: Major")],
        f"Post in #waco-production-coord: \"Variance detected. Manifest {M2}, SKU SC-006, SC-008: SC-006 -6 cases "
        "(-3%), SC-008 +8 cases (+5%). Variance tier: Major. Email sent. Status: Open – Pending response.\""),
        [R_MAJ], "Post the message as described.")

    # P2 escalation posts in #dc-escalations for 002 and 003
    for m, detail, brief in (
            (M2, "Major variance", "SC-008 160 -> 168 (+8, +5%, Major); SC-006 200 -> 194 (-6, -3%, Moderate)"),
            (M3, "Tier 3 temperature + Moderate variance (compound)",
             "temps -5/-4.5/-4°F (Tier 3); SC-003 160 -> 156 (-4, -2.5%, Moderate)")):
        posts = [a for a in w.posts_in("dc-escalations") if m in _t(a.text)]
        yield (*_msg_check(
            posts, f"#dc-escalations P2 post for manifest {m}",
            [(lambda a: re.match(r"^\W*(?:(?:<@\w+>|@[\w.]+)\s*)*P2\b", _t(a.text)) is not None,
              "the \"P2\" prefix at the start"),
             (lambda a: _has(r"incident report", _t(a.text)), "\"Incident report: [pending/open/closed]\"")],
            f"Post in #dc-escalations, e.g.: \"P2 escalation. {detail}. Manifest/Reference {m}. Detail: {brief}. "
            "Escalated to @d.reyes and @c.mendoza. Incident report: open. Action required: Director review.\""),
            [R_P2_SLACK, R_P2_FMT, R_N_P2, R_COMPOUND if m == M3 else R_MIXMAJ], "Post the message as described.")

    # 003 compound P2 -> Director (cc DC Manager)
    yield (*_msg_check(
        [a for a in em if M3 in body(a) and DIRECTOR in _to(a)], f"P2 (compound) email to the Director for {M3}",
        [(lambda a: DCM in _all(a), f"cc {DCM}"),
         (lambda a: _has(r"SC-003", body(a)), "SC-003 variance (160 → 156, -4)"),
         (lambda a: _has(r"tier[\s-]*3", body(a)), "Tier 3 temperature (-5, -4.5, -4 °F)")],
        f"Email {DIRECTOR} (cc {DCM}) about manifest {M3}: P2 compound event – Tier 3 temperature (-5, -4.5, -4 °F) "
        "plus Moderate variance SC-003 160→156 (-4 cases, -2.5%)."),
        [R_COMPOUND, R_P2_MAIL, R_N_P2], "Send the email as described.")

    # 003 Tier 3 -> Production Planner (temperature readings + enhanced expiry monitoring)
    yield (*_msg_check(
        [a for a in em if M3 in body(a) and PP in _all(a)], f"Tier 3 temperature email to the Production Planner for {M3}",
        [(lambda a: all(_has(rx, body(a)) for rx in (_neg("5"), _neg("4.5"), _neg("4"))),
          "the readings -5, -4.5, -4 °F"),
         (lambda a: _has(r"monitor", body(a)), "a note that the product is flagged for enhanced expiry monitoring")],
        f"Email {PP} with manifest {M3}, the readings -5, -4.5, -4 °F (Tier 3, conditional acceptance) and that the "
        "product is flagged for enhanced expiry monitoring."),
        [R_T3, R_12T3, R_P2_PP, R_E3F], "Send the email as described.")

    # 003 Moderate variance -> Production Planner
    yield (*_msg_check(
        [a for a in em if M3 in body(a) and PP in _all(a)], f"Variance email to the Production Planner for {M3}",
        [(lambda a: _has(r"SC-003", body(a)) and _has(r"\b156\b", body(a)) and _has(r"\b160\b", body(a)),
          "SC-003 manifest 160 / actual 156 (-4 cases, -2.5%, Moderate)")],
        f"Email {PP} with manifest {M3} variance detail: SC-003 manifest 160, actual 156 (-4 cases, -2.5%, Moderate), "
        "requesting an explanation or credit."),
        [R_MOD, R_12MOD, R_E2F], "Send the email as described.")

    # 001 short-dated SW-008 -> Production Planner cc Demand Planning; separately the Director
    sd = [a for a in em if SD_SKU in body(a) or SD_LOT in body(a)]
    yield (*_msg_check(
        [a for a in sd if PP in _to(a)], "Inbound short-dated product email to the Production Planner",
        [(lambda a: DPM in _all(a), f"cc {DPM}"),
         (lambda a: _has(r"short[- ]?dated", body(a)), "\"Inbound short-dated product\""),
         (lambda a: _has(SD_SKU, body(a)) and _has(SD_LOT, body(a)), f"SKU {SD_SKU} and lot {SD_LOT}"),
         (lambda a: _has(r"\b16\b", body(a)), "16 days to expiry")],
        f"Email {PP} (cc {DPM}): \"Inbound short-dated product – {SD_SKU}, {SD_LOT}, 16 days to expiry\" (manifest "
        f"{M1}, expires 2026-05-01, Orange) requesting prioritization in outbound."),
        [R_SD, R_SD_MAIL, R_SD_EX, R_P3_MAIL], "Send the email as described.")
    yield (*_msg_check(
        [a for a in sd if DIRECTOR in _to(a)], "Short-dated (<30 days) email to the Director",
        [(lambda a: _has(SD_SKU, body(a)) and _has(SD_LOT, body(a)), f"SKU {SD_SKU} and lot {SD_LOT}"),
         (lambda a: _has(r"\b16\b", body(a)), "16 days to expiry"),
         (lambda a: _has(r"demand plan", body(a)), "a request for an immediate demand plan")],
        f"Because {SD_SKU} arrived with <30 days (16 days, Orange), separately email {DIRECTOR} with {SD_SKU}, lot "
        f"{SD_LOT}, 16 days to expiry, and request an immediate demand plan."),
        [R_SD_MAIL], "Send the email as described.")

    # 001 receipt post in #receiving-houston
    posts = [a for a in w.posts_in("receiving-houston") if M1 in _t(a.text)]
    yield bool(posts), (f"Not yet done per the SOP: post the receipt status for manifest {M1} in #receiving-houston "
                        f"(e.g. \"Manifest {M1} received with flags. Pallets: 26, Cases: 492, Temp: -18°F (avg), "
                        f"Tier 1, Variance: 0. {SD_SKU} lot {SD_LOT} short-dated (16 days, Orange). Email sent to "
                        "the Production Planner and Demand Planning. Pending put-away.\")."), \
        [R_N_P4, R_N_P3, R_P3_SLACK], "Post the message."


# ---- completion rules: incident reports ----------------------------------------------------------

IR_RX = r"(?:^|/)IR-\d{3}-2026-04-15-[^/]+\.docx$"


def _ir_checks(ctx: Context):
    w = world(ctx)
    root = config.workdir()
    docs = [f for f in w.files() if f.lower().endswith(".docx") and "sop" not in f.lower()]
    texts = {f: _t(docx_text(root / f)) for f in docs}
    refs = [R_IR_P2, R_P2_IR, R_IR_NAME, R_IR_SEQ, R_IR_FIELDS, R_IRDIR]
    for m, ex in ((M2, f"IR-001-{TODAY}-Variance.docx"), (M3, f"IR-002-{TODAY}-Variance.docx")):
        good = [f for f in docs if re.search(IR_RX, f) and m in texts[f]]
        if good:
            continue
        other = [f for f in docs if m in texts[f]]
        extra = f" ({', '.join(other)} mentions it but is not named IR-[seq]-{TODAY}-[category].docx)" if other else ""
        yield False, (f"P2 event on manifest {m} requires an incident report (Word document) named "
                      f"IR-[seq]-{TODAY}-[category].docx (sequence increments per report filed), e.g. "
                      f"incident_reports/{ex}{extra}."), \
            refs, ("Create it with: date/time assessed, location (Houston DC, manifest " + m + "), priority P2, "
                   "description as reported by the dock crew, actions taken, notifications sent, current status, "
                   "attachments (temperature readings / variance detail).")
    em = [a for a in _emails(w) if DCM in _all(a)]
    ok = any(_has(r"incident report|\bIR-\d{3}", _t(text_of(a))) or any(f.startswith("IR-") for f in attachments(a))
             for a in em)
    yield ok, ("P2 incident reports must be submitted to the DC Manager the same day: no email to "
               f"{DCM} references the incident report(s)."), [R_IR_ROUTE], \
        f"Email {DCM} (or cc him) referencing / attaching the incident report(s) for {M2} and {M3}."


# ---- RULES -------------------------------------------------------------------------------------------

RULES: list[Rule] = []
RULES += no_placeholders([R_TPL])
RULES += pre_rule("comms.sop_placeholders", _sop_placeholders, [R_P2_FMT, R_TPL], "Fill in every bracketed field.")
RULES += pre_rule("email.subject_format", _subject_format, [R_SUBJ, R_TPL], "Rewrite the subject in the SOP format.")
RULES += pre_rule("email.e2_subject", _e2_subject, [R_E2S, R_SUBJ], "Use the E2 subject.")
RULES += pre_rule("variance002.priority", _variance002, [R_VAR, R_PERSKU, R_MAJ, R_MIXMAJ, R_ROUNDUP, R_HIGHER, R_P2_EX],
                  "Classify manifest 2026-04-15-002 as a Major variance (P2).")
RULES += pre_rule("slack.no_channel_mentions", _no_channel, [R_THREAD], "Remove @channel/@here.")
RULES += _completion("recv_log.fill", _fill_checks)
RULES += _completion("recv_log.status", _status_checks)
RULES += _completion("recv_log.one_row", _one_row_checks)
RULES += _completion("temp_log.inbound", _temp_checks)
RULES += _completion("logs.append_only", _append_checks)
RULES += _completion("inventory.no_putaway", _inventory_checks)
RULES += _completion("files.read_only", _readonly_checks)
RULES += _completion("files.no_copies", _copies_checks)
RULES += _completion("msg.required", _message_checks)
RULES += _completion("ir.p2", _ir_checks)
