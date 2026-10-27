"""SOP-FIN-AP-004 verifiers for finance_meridian_partners_4dace65e (blind build, scripts/algo.md Steps 0-4).

Situation (2026-03-16, ap@meridianpartners.com): three invoices arrived today plus the Kunlun one from 2026-03-05.
- INV-4839201-24 Sentinel Cybersecurity Solutions (933448) $13,837.00, no PO: active recurring agreement
  (expected $13,500, tolerance 3%, GL 6400-010-1100, expires 2026-12-31) -> +2.50% within tolerance -> Payment
  Queue as Approved with the agreement GL; $10,000.01-$50,000 -> PAYMENT AUTHORIZATION REQUIRED (Tanya Okonkwo and
  Rachel Whitfield) in #ap-approvals.
- INV-004322 Main Street Office Products (432319) $1,356.14 on PO-2026-00532 ($1,276.14): quantities match GR;
  copy paper $59.99 -> $79.99 (+$20, inside the +-$25 unit tolerance) but total +$80 / 6.27% fails the
  +-$50 AND +-2% check -> 6.1. The vendor's 2026-03-05 notice announced exactly $79.99, recalculated PO total
  $1,356.14 = invoice -> Payment Queue as Approved (Step 2a), PRICE VARIANCE post (Step 3), match-log row,
  SELF-APPROVED post (<= $2,500). No price-discrepancy email (Step 2b does not apply).
- INV-82419 Luminary Logistics: vendor address lacks city/state/zip -> Incomplete: return email (4.2), no
  Invoice Register / Payment Queue entry, no approval post.
- INV-KC-20260305 Kunlun Creative Studio $6,019.44 non-PO ($5,000.01-$25,000 tier: Dept Manager AND Controller):
  only Danielle Fairweather (and Tanya Okonkwo, not a required approver) replied; Controller window (5 business
  days from 2026-03-05) lapsed 2026-03-12 -> Status APPR in the Invoice Register + Status Update email to Greg.
"""

from __future__ import annotations

import re

from ..kit import Comm, Context, comm_rules, no_placeholders, norm, num, pre_rule, same, state_rule, text_of, world

LEDGER = r"(^|/)ap_ledger\.xlsx$"
MATCH_LOG = r"(^|/)match_log_2026_Q1\.xlsx$"
VENDORS = r"(^|/)vendor_master\.xlsx$"

SENT, MS, LUM, KC = "INV-4839201-24", "INV-004322", "INV-82419", "INV-KC-20260305"
HOLD_RX = r"\b(APPR|MATCH|DUPL|DISP|AUDIT|IC-HOLD)\b|\bhold\b"
AUTH_TAG = r"SELF-APPROVED|PAYMENT AUTHORI[SZ]ATION REQUIRED"

R_DM = ("3.3", "Use the following Slack channels for all AP communications", "3.3")
R_ADHOC = ("3", "All AP staff must use the following systems and file paths", "3")
R_FIELDS = ("4.1", "Before processing, verify the invoice contains", "4.1")
R_ADDR = ("4.1", "Vendor name and full address", "4.1")
R_RET = ("4.2", "When an invoice is missing required fields", "4.2")
R_RET_TO = ("4.2", "To: [vendor contact email", "4.2")
R_RET_SUBJ = ("4.2", "Subject: Meridian Partners - Incomplete Invoice", "4.2")
R_RET_BODY = ("4.2", "Body (use verbatim)", "4.2")
R_RET_TXT = ("4.2", "We received invoice [INVOICE NUMBER]", "4.2")
R_RET_TXT2 = ("4.2", "Please resubmit a corrected invoice", "4.2")
R_RET_TY = ("4.2", "Thank you,", "4.2")
R_RET_SIGN = ("4.2", "Meridian Partners Accounts Payable", "4.2")
R_NO_ENTRY = ("4.2", "Do NOT enter incomplete invoices", "4.2")
R_NONPO = ("4.3", "Non-PO Invoice |", "4.3")
R_RECUR = ("4.3", "Recurring Invoice |", "4.3")
R_MATCH = ("5.1", "For every PO invoice, the AP clerk must verify", "5.1")
R_UNIT = ("5.1.1", "Unit Price Variance |", "5.1.1")
R_TOTAL = ("5.1.1", "Total Invoice Amount |", "5.1.1")
R_PASS = ("5.1.1", "If the match passes, enter the invoice", "5.1.1")
R_DUP = ("5.2", "Before entering any invoice into the Invoice Register", "5.2")
R_NONPO_PAY = ("5.3", "Invoices without a valid PO require retroactive approval", "5.3")
R_TIER = ("5.3", "$5,000.01", "5.3")
R_APPR = ("5.3", "If approval is not received within the allowed timeframe", "5.3")
R_STAT_SUBJ = ("5.3", "Subject: Status Update - Invoice", "5.3")
R_STAT_BODY = ("5.3", 'Body: "Dear [Vendor Contact First Name], Invoice', "5.3")
R_REC1 = ("5.4", "Step 1: Verify the agreement has not expired", "5.4")
R_REC2 = ("5.4", "Step 2: Compare the invoice amount", "5.4")
R_REC3 = ("5.4", "Step 3: If within tolerance and not expired", "5.4")
R_PV = ("6.1", "When unit price variance exceeds", "6.1")
R_PV1 = ("6.1", "Step 1: Check if the vendor has emailed", "6.1")
R_PV2A = ("6.1", "Step 2a", "6.1")
R_PV2B = ("6.1", "Step 2b", "6.1")
R_PV3 = ("6.1", "Step 3: Post to #ap-exceptions", "6.1")
R_POST = ("7", "After an invoice has been processed", "7")
R_AUTH_LOW = ("7.1", "$0.01", "7.1")
R_AUTH_MID = ("7.1", "$10,000.01", "7.1")
R_AUTH_FMT = ("7.1", "The Slack confirmation message should follow", "7.1")
R_BANK5 = ("13.2", "Step 5: Only after receiving written verification", "13.2")
R_LEGAL = ("13.3", "For legal threats, do NOT reply", "13.3")
R_AUDIT = ("16", "All AP transactions are subject to internal and external audit", "16")

SENT_AUTH = ("PAYMENT AUTHORIZATION REQUIRED: Sentinel Cybersecurity Solutions | Invoice INV-4839201-24 | "
             "Amount $13,837.00 | Recurring Invoice | Tanya Okonkwo and Rachel Whitfield")
MS_AUTH = "SELF-APPROVED: Main Street Office Products | Invoice INV-004322 | Amount $1,356.14 | 3-way match"
MS_PV = ("PRICE VARIANCE: Main Street Office Products, 432319, Invoice INV-004322, PO Price $59.99, "
         "Invoice Price $79.99, Variance 33.34%")
LUM_SUBJ = "Meridian Partners - Incomplete Invoice INV-82419"
LUM_BODY = ("Dear Lindon, We received invoice INV-82419 dated March 16, 2026. Unfortunately, we are unable to "
            "process this invoice because the following required information is missing: City / State / Zip Code . "
            "Please resubmit a corrected invoice to ap@meridianpartners.com at your earliest convenience. We will "
            "process payment promptly upon receipt of a complete invoice. Thank you, Meridian Partners Accounts Payable")
KC_SUBJ = "Status Update - Invoice INV-KC-20260305"
KC_BODY = ("Dear Greg, Invoice INV-KC-20260305 for $6,019.44 is currently pending internal approval. We expect to "
           "process payment within 5 additional business days. We apologize for the delay. "
           "Meridian Partners Accounts Payable")


# ---- helpers ---------------------------------------------------------------------------------------

def _has(a, *rx: str) -> bool:
    t = text_of(a)
    return all(re.search(r, t, re.I) for r in rx)


def _email(a) -> bool:
    return a.kind in ("email_send", "email_draft")


def _slack(a) -> bool:
    return a.kind in ("slack_post", "slack_dm")


def _auth(a) -> bool:
    """A 7.1 payment-confirmation post: starts with, or contains, the tag followed by a colon."""
    t = a.text or ""
    return bool(re.search(rf"^\W{{0,3}}({AUTH_TAG})|({AUTH_TAG})\W{{0,3}}:", t, re.I | re.M))


def _to(a, domain: str) -> bool:
    return any(x.endswith("@" + domain) for x in a.recipients + a.cc)


def _pq(w, which: str = "current") -> list[dict]:
    return w.rows(LEDGER, r"^Invoice #$", which, r"Payment Queue")


def _ir(w, which: str = "current") -> list[dict]:
    return w.rows(LEDGER, r"^Invoice #$", which, r"Invoice Register")


def _inv(w, r: dict, col: str = r"^Invoice #$") -> str:
    return norm(w.col(r, col)).upper()


def _show(w, r: dict | None) -> str:
    if not r:
        return "no row"
    return " | ".join(f"{k}={v}" for k, v in r.items() if k != "__row__" and str(v) not in ("", "None"))[:300]


# ---- messages ----------------------------------------------------------------------------------------

LUM_DATE = r"(March\s+16,?\s+2026|0?3/16/(20)?26|2026-03-16)"


def _specs(ctx: Context) -> list[Comm]:
    return [
        Comm("lum_incomplete", "email",
             lambda a: _email(a) and (_to(a, "luminarylogistics.com")
                                      or bool(re.search(r"Incomplete Invoice", a.subject, re.I))),
             "Incomplete-invoice return email for Luminary Logistics INV-82419 (vendor address has no "
             "city / state / zip code)",
             [R_ADDR, R_RET, R_RET_TO, R_RET_SUBJ, R_RET_BODY, R_RET_TXT, R_RET_TXT2, R_RET_TY, R_RET_SIGN],
             to=["lindon@luminarylogistics.com"], exact_to=False,
             subject=r"Meridian Partners [-–—] Incomplete Invoice INV-82419", subject_hint=LUM_SUBJ, exact_hint=LUM_BODY,
             body=[(r"Dear Lindon\b", "greeting \"Dear Lindon,\""),
                   (rf"We received invoice INV-82419 dated {LUM_DATE}", "\"We received invoice INV-82419 dated "
                                                                         "March 16, 2026.\""),
                   (r"unable to process this invoice because the following required information is missing:"
                    r".{0,160}?City.{0,30}?State.{0,30}?Zip", "the verbatim sentence listing the missing fields "
                                                             "\"City / State / Zip Code\""),
                   (r"Please resubmit a corrected invoice to ap@meridianpartners\.com", "the verbatim resubmission "
                                                                                       "sentence"),
                   (r"process payment promptly upon receipt of a complete invoice", "\"We will process payment "
                                                                                    "promptly upon receipt of a "
                                                                                    "complete invoice.\""),
                   (r"Thank you,?\s*Meridian Partners Accounts Payable", "sign-off \"Thank you, Meridian Partners "
                                                                       "Accounts Payable\"")]),
        Comm("kunlun_status", "email",
             lambda a: _email(a) and (_to(a, "kunluncreativestudio.com")
                                      or bool(re.search(r"Status Update.*INV-KC-20260305", a.subject, re.I))),
             "Courtesy Status Update email to Kunlun Creative Studio for INV-KC-20260305 (APPR hold: Controller "
             "approval not received within 5 business days)",
             [R_TIER, R_APPR, R_STAT_SUBJ, R_STAT_BODY],
             to=["greg.kendrick@kunluncreativestudio.com"], exact_to=False,
             subject=r"Status Update [-–—] Invoice INV-KC-20260305", subject_hint=KC_SUBJ, exact_hint=KC_BODY,
             body=[(r"Dear Greg\b", "greeting \"Dear Greg,\""),
                   (r"Invoice INV-KC-20260305 for \$\s?6,?019\.44 is currently pending internal approval",
                    "\"Invoice INV-KC-20260305 for $6,019.44 is currently pending internal approval.\""),
                   (r"process payment within 5 additional business days", "\"We expect to process payment within "
                                                                           "5 additional business days.\""),
                   (r"apologi[sz]e for the delay", "\"We apologize for the delay.\""),
                   (r"Meridian Partners Accounts Payable", "sign-off \"Meridian Partners Accounts Payable\"")]),
        Comm("sentinel_auth", "slack_post",
             lambda a: _slack(a) and _auth(a) and _has(a, SENT),
             "Payment authorization post for Sentinel INV-4839201-24 ($13,837.00 is in the $10,000.01-$50,000 "
             "tier: AP Manager AND Controller)",
             [R_POST, R_AUTH_MID, R_AUTH_FMT, R_REC3], channel="ap-approvals",
             body=[(r"PAYMENT AUTHORIZATION REQUIRED:\s*Sentinel Cybersecurity Solutions\s*\|\s*Invoice:?\s*"
                    r"INV-4839201-24\s*\|\s*Amount:?\s*\$?\s?13,?837(\.00)?\s*\|\s*Recurring Invoice\s*\|\s*"
                    r"Tanya Okonkwo (and|&) Rachel Whitfield", f"the SOP 7.1 structure, i.e. \"{SENT_AUTH}\"")]),
        Comm("mainstreet_auth", "slack_post",
             lambda a: _slack(a) and _auth(a) and _has(a, MS),
             "Payment confirmation post for Main Street INV-004322 ($1,356.14 <= $2,500: AP Clerk self-approves)",
             [R_POST, R_AUTH_LOW, R_AUTH_FMT, R_PV2A], channel="ap-approvals",
             body=[(r"SELF-APPROVED:\s*Main Street Office Products\s*\|\s*Invoice:?\s*INV-004322\s*\|\s*Amount:?\s*"
                    r"\$?\s?1,?356\.14\s*\|\s*3-way match", f"the SOP 7.1 structure, i.e. \"{MS_AUTH}\"")]),
        Comm("mainstreet_pv", "slack_post",
             lambda a: _slack(a) and not _auth(a) and _has(a, r"PRICE VARIANCE\s*:", r"Main Street|INV-004322|432319"),
             "PRICE VARIANCE post for Main Street INV-004322 (copy paper $59.99 -> $79.99 per the vendor's "
             "2026-03-05 price increase notice)",
             [R_PV, R_PV1, R_PV3], channel="ap-exceptions",
             body=[(r"PRICE VARIANCE:\s*Main Street Office Products,\s*432319,\s*Invoice:?\s*INV-004322,\s*PO Price:?\s*"
                    r"\$?59\.99,\s*Invoice Price:?\s*\$?79\.99,\s*Variance:?\s*\+?33(\.\d+)?\s?%",
                    f"the SOP 6.1 Step 3 format, i.e. \"{MS_PV}\"")]),
        # Calls that are wrong in this situation.
        Comm("kunlun_release", "slack_post",
             lambda a: _slack(a) and _auth(a) and _has(a, KC),
             "Payment confirmation for Kunlun INV-KC-20260305", [R_NONPO_PAY, R_TIER, R_APPR],
             forbidden="INV-KC-20260305 is a $6,019.44 non-PO invoice that needs the Department Manager AND the "
                       "Controller (Rachel Whitfield); the Controller never replied, so it goes on APPR hold and must "
                       "not be released for payment."),
        Comm("lum_release", "slack_post",
             lambda a: _slack(a) and _has(a, LUM) and (_auth(a) or _has(a, r"PRICE VARIANCE\s*:")),
             "Processing post for Luminary INV-82419", [R_ADDR, R_NO_ENTRY],
             forbidden="INV-82419 is Incomplete (the vendor address has no city, state or zip code); it must be "
                       "returned to the vendor before entry and is not matched, held or approved."),
        Comm("ms_discrepancy", "email",
             lambda a: _email(a) and _to(a, "mainstreetofficeproducts.com")
             and _has(a, r"discrepanc|corrected invoice|justification"),
             "Price-discrepancy email to Main Street Office Products", [R_PV1, R_PV2A, R_PV2B],
             forbidden="Main Street emailed a price increase notice on 2026-03-05 ($59.99 -> $79.99 per case); the "
                       "invoiced price matches it and the recalculated PO total ($1,356.14) equals the invoice, so "
                       "Step 2a applies (enter it in the Payment Queue as Approved) and Step 2b's vendor email does "
                       "not."),
        Comm("sentinel_variance", "email",
             lambda a: _email(a) and _has(a, r"Recurring Invoice Variance") and _has(a, r"Sentinel|INV-4839201-24"),
             "Recurring-variance email for Sentinel", [R_REC2, R_REC3],
             forbidden="Sentinel's $13,837.00 is +2.50% over the $13,500 expected amount, inside the agreement's 3% "
                       "tolerance; approve it and enter it in the Payment Queue (5.4 Step 3) - no variance email."),
        Comm("sentinel_nonpo", "email",
             lambda a: _email(a) and _has(a, r"AP APPROVAL REQUIRED") and _has(a, r"Sentinel|INV-4839201-24"),
             "Non-PO approval request for Sentinel", [R_NONPO, R_RECUR, R_REC3],
             forbidden="Sentinel INV-4839201-24 matches an active recurring agreement, so it is a Recurring Invoice "
                       "(not Non-PO): no additional approval is needed (5.4 Step 3)."),
        Comm("legal_reply", "email",
             lambda a: _email(a) and _to(a, "vendor-collections-services.com"),
             "Reply to the legal-action email", [R_LEGAL],
             forbidden="Do not reply to legal threats; the Controller or Legal handles all communication."),
    ]


RULES = comm_rules("comms", _specs)
RULES += no_placeholders([R_RET_BODY, R_AUTH_FMT])


def _dm(ctx: Context, a) -> str | None:
    w = world(ctx)
    if not (a.kind == "slack_dm" or w.dm_recipients(a)):
        return None
    if re.search(r"INV-4839201-24|INV-004322|INV-82419|INV-KC-20260305|Sentinel|Main Street|Luminary|Kunlun",
                 a.text or "", re.I):
        return ("AP invoice matters need an audit trail: post to the SOP channel (#ap-approvals for payment "
                "confirmations, #ap-exceptions for variances) instead of a direct message.")
    return None


RULES += pre_rule("comms.no_dm", _dm, [R_DM], "Post it in the SOP channel instead.")


# ---- ledger end state ------------------------------------------------------------------------------

def _sentinel(ctx: Context):
    w = world(ctx)
    rows = [r for r in _pq(w) if _inv(w, r) == SENT]
    good = [r for r in rows if same(w.col(r, r"^Amount"), 13837) and norm(w.col(r, r"^GL Account")) == "6400-010-1100"
            and norm(w.col(r, r"^Status$")).startswith("approved")]
    yield (bool(good),
           "Payment Queue (ap_ledger.xlsx) must hold the Sentinel recurring invoice as Approved with the agreement "
           "GL code: Vendor / Payee 'Sentinel Cybersecurity Solutions', Invoice # 'INV-4839201-24', Invoice Date "
           "2026-03-16, Due Date 2026-04-15, Amount 13837.00, GL Account '6400-010-1100', Status 'Approved' "
           f"(recurring agreement: expected $13,500, +2.50% within the 3% tolerance, expires 2026-12-31). Now: "
           f"{_show(w, rows[0] if rows else None)}.",
           [R_RECUR, R_REC1, R_REC2, R_REC3])


def _mainstreet(ctx: Context):
    w = world(ctx)
    rows = [r for r in _pq(w) if _inv(w, r) == MS]
    good = [r for r in rows if same(w.col(r, r"^Amount"), 1356.14) and norm(w.col(r, r"^Status$")).startswith("approved")]
    yield (bool(good),
           "Payment Queue (ap_ledger.xlsx) must hold Main Street Office Products INV-004322 as Approved: the vendor's "
           "2026-03-05 notice set copy paper to $79.99, the recalculated PO-2026-00532 total is $1,356.14 = the "
           "invoice (6.1 Step 2a). Row: Vendor / Payee 'Main Street Office Products', Invoice # 'INV-004322', "
           "Invoice Date 2026-03-16, Due Date 2026-04-15, Amount 1356.14, GL Account '6200-000-5100', PO Number "
           f"'PO-2026-00532', Status 'Approved'. Now: {_show(w, rows[0] if rows else None)}.",
           [R_UNIT, R_TOTAL, R_PASS, R_PV, R_PV2A])


def _kunlun(ctx: Context):
    w = world(ctx)
    rows = [r for r in _ir(w) if _inv(w, r) == KC]
    st = w.col(rows[0], r"^Status$") if rows else ""
    yield (bool(rows) and bool(re.search(r"\bAPPR\b", st, re.I)),
           "Invoice Register row INV-KC-20260305 (Kunlun Creative Studio, $6,019.44, non-PO) must have Status "
           "'APPR' (APPR hold): the $5,000.01-$25,000.00 tier needs the Department Manager AND the Controller "
           "(Rachel Whitfield); only Danielle Fairweather approved (Tanya Okonkwo is not a required approver for "
           f"this tier) and the 5-business-day window from 2026-03-05 ended 2026-03-12. Status now: '{st or 'no row'}'.",
           [R_TIER, R_APPR])


def _no_release(ctx: Context):
    w = world(ctx)
    pq, ir = _pq(w), _ir(w)
    kc_pq = [r for r in pq if _inv(w, r) == KC and not re.search(HOLD_RX, w.col(r, r"^Status$"), re.I)]
    yield (not kc_pq, "INV-KC-20260305 (Kunlun) is on APPR hold - the Controller's approval is missing - so it must "
                      "not be in the Payment Queue as payable (remove that Payment Queue row; keep it on the Invoice "
                      "Register with Status 'APPR').", [R_NONPO_PAY, R_TIER, R_APPR])
    lum = [r for r in pq + ir if _inv(w, r) == LUM]
    yield (not lum, "INV-82419 (Luminary Logistics) is an Incomplete invoice (vendor address lacks city, state and "
                    "zip code): do not enter it in the Invoice Register or the Payment Queue and do not place it on "
                    "hold - remove those rows; it is only returned to the vendor.", [R_ADDR, R_NO_ENTRY])
    kc_ir = [r for r in ir if _inv(w, r) == KC]
    yield (len(kc_ir) <= 1, "INV-KC-20260305 is already on the Invoice Register; do not enter it a second time "
                            "(keep the single existing row and update its Status).", [R_DUP, R_APPR])


def _matchlog(ctx: Context):
    w = world(ctx)
    rows = [r for r in w.rows(MATCH_LOG, r"^Invoice Number$") if _inv(w, r, r"^Invoice Number$") == MS]
    good = [r for r in rows if same(w.col(r, r"^Invoice Amount"), 1356.14)
            and norm(w.col(r, r"^PO Number$")).upper() == "PO-2026-00532"]
    yield (bool(good),
           "Record the Main Street three-way match attempt in match_log_2026_Q1.xlsx: Match Date 2026-03-16, "
           "Vendor / Payee 'Main Street Office Products', PO Number 'PO-2026-00532', PO Amount 1276.14, GR Number "
           "'GR-20260311-004', GR Date 2026-03-11, Invoice Number 'INV-004322', Invoice Date 2026-03-16, Invoice "
           "Amount 1356.14, GL Account '6200-000-5100', with a note on the 2026-03-05 copy paper price increase "
           f"($59.99 -> $79.99). Now: {_show(w, rows[0] if rows else None)}.",
           [R_MATCH])


def _sig(w, r: dict) -> tuple:
    out = []
    for k, v in sorted(r.items()):
        if k == "__row__" or str(v).startswith("="):
            continue
        n = num(v)
        out.append((k, round(n, 2) if n is not None and not re.search(r"[A-Za-z/]|\d-\d", str(v)) else norm(v)))
    return tuple(out)


PROTECTED = [("Payment Queue", LEDGER, r"^Invoice #$", r"Payment Queue"),
             ("PO Register", LEDGER, r"^PO Number$", r"PO Register"),
             ("GL Postings", LEDGER, r"^JE ID$", r"GL Postings"),
             ("3-way match log", MATCH_LOG, r"^Invoice Number$", None)]


def _append_only(ctx: Context):
    w = world(ctx)
    for what, book, key, sheet in PROTECTED:
        init = [r for r in w.rows(book, key, "initial", sheet)
                if not norm(w.col(r, key)).startswith("total") and w.col(r, key)]
        if not init:
            continue
        cur = [_sig(w, r) for r in w.rows(book, key, "current", sheet)]
        gone = []
        for r in init:
            s = _sig(w, r)
            if s in cur:
                cur.remove(s)
            else:
                gone.append(w.col(r, key))
        yield (not gone, f"{what}: existing entries were edited or removed ({', '.join(gone[:5])}). Today's work only "
                         "adds rows for today's invoices; restore the existing rows exactly.", [R_MATCH, R_AUDIT])


def _bank(ctx: Context):
    w = world(ctx)
    cur = {norm(w.col(r, r"^Vendor ID$")): r for r in w.rows(VENDORS, r"^Bank Routing$")}
    changed = []
    for r in w.rows(VENDORS, r"^Bank Routing$", "initial"):
        c = cur.get(norm(w.col(r, r"^Vendor ID$")))
        if c and any(norm(w.col(r, k)) != norm(w.col(c, k)) for k in (r"^Bank Name$", r"^Bank Routing$",
                                                                         r"^Bank Account$")):
            changed.append(w.col(r, r"^Vendor ID$"))
    yield (not changed, f"Vendor_Master.xlsx bank details were changed for vendor(s) {', '.join(changed[:5])}; the AP "
                        "Clerk may never update bank details - restore the original values.", [R_BANK5])


ALLOWED_BOOKS = re.compile(r"^(Payment_?Batches/(\d{4}-\d{2}-\d{2}/)?batch_?\d{4}-\d{2}-\d{2}\.xlsx"
                           r"|Exceptions/(\d{4}-\d{2}-\d{2}/)?[^/]+\.xlsx|POMatching/[^/]+\.xlsx"
                           r"|Month_End/\d{4}-\d{2}/[^/]+\.xlsx|1099/\d{4}/[^/]+\.xlsx)$", re.I)


def _adhoc(ctx: Context):
    w = world(ctx)
    bad = [b for b in w.created_books() if not ALLOWED_BOOKS.match(b)]
    yield (not bad, f"New spreadsheet(s) outside the SOP file locations: {', '.join(bad[:5])}. Do not create ad hoc "
                    "spreadsheets - record the work in ap_ledger.xlsx / match_log_2026_Q1.xlsx and delete these.",
           [R_ADHOC])


RULES += state_rule("ledger.sentinel_queue", _sentinel, "Add/fix the Payment Queue row as stated.")
RULES += state_rule("ledger.mainstreet_queue", _mainstreet, "Add/fix the Payment Queue row as stated.")
RULES += state_rule("ledger.kunlun_appr", _kunlun, "Set the Invoice Register Status to APPR.")
RULES += state_rule("ledger.no_release", _no_release, "Remove the entries listed.")
RULES += state_rule("matchlog.mainstreet", _matchlog, "Append the match-log row as stated.")
RULES += state_rule("records.append_only", _append_only, "Restore the original rows.")
RULES += state_rule("vendor.bank_unchanged", _bank, "Restore the original bank details.")
RULES += state_rule("files.no_adhoc_books", _adhoc, "Remove the ad hoc spreadsheets.")
