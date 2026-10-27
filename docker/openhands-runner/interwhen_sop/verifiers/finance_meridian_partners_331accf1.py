"""SOP-FIN-AP-004 verifiers for finance_meridian_partners_331accf1.

Situation (seed data, today 2025-09-04): three unprocessed vendor emails with invoice + W-9 attachments.
- Harrison & Cole LLP (law firm, Partnership, EIN 23-7654321): HC-2025-0001, 09/04/2025, $5,000.00, 2/10 Net 30.
  New vendor; non-PO $500.01-$5,000 -> Dept Manager (Jennifer Walsh, HR) + AP Manager (Maria Santos);
  2% discount = $100.00 >= $100 -> take it, deadline 09/14/2025; 1099 Yes / NEC.
- Whitfield Consulting Group, Inc. (S-Corp, EIN 23-7891045, invoice is legal services): WCG-2025-0087,
  08/28/2025, $4,950.00, 2/10 Net 30. New vendor; same approvers; discount $99.00 < $100 -> no discount post;
  S-Corp providing legal services -> 1099 Yes / NEC (Section 14.1).
- ClearPath Talent Solutions: W-9 EIN 58-8901234 = Premier Staffing Group (V-00008) -> no new record,
  DUPLICATE VENDOR SUSPECTED post, invoice CPT-2025-0412 not processed.
Last vendor ID in vendor_master.xlsx is V-00037, so the new vendors get V-00038 and V-00039.
"""

from __future__ import annotations

import datetime as dt
import re

from .. import config
from ..kit import (COMM_KINDS, Comm, Ref, append_only, book_eq, comm_rules, no_placeholders, norm, num,
                   pre_rule, same, state_rule, text_of, world)

VM = r"^vendor_master\.xlsx$"
VM_HDR = r"^Vendor ID$"
LEDGER = r"^ap_ledger\.xlsx$"
IR_HDR = r"^Inv Reg ID$"
IR_SHEET = r"Invoice Register"
NEW_IDS = ("V-00038", "V-00039")
AP_TEAM = "ap.team@meridianpartners.com"
JW = "jennifer.walsh@meridianpartners.com"
MS = "maria.santos@meridianpartners.com"
SELF = "tara.okonkwo@meridianpartners.com"

R_SETUP: Ref = ("12.1", "No invoice may be processed for a vendor that does not exist", "12.1")
R_W9: Ref = ("12.1", "Step 1: Collect a completed W-9 form", "12.1 Step 1")
R_TAXID: Ref = ("12.1", "Step 2: Verify the vendor", "12.1 Step 2")
R_ROW: Ref = ("12.1", "Step 3: Add a new row to vendor_master.xlsx", "12.1 Step 3")
R_POST: Ref = ("12.1", "Step 4: Post to #approvals", "12.1 Step 4")
R_1099: Ref = ("14.1", "Entity Type (from W-9) 1099 Reportable?", "14.1")
R_1099T: Ref = ("14.1", "1099 Type classification", "14.1")
R_CLASS: Ref = ("4.3", "Category Criteria Next Step", "4.3")
R_NONPO: Ref = ("5.3", "Invoices without a valid PO require retroactive", "5.3")
R_TIER: Ref = ("5.3", "Invoice Amount Required Approver", "5.3 approval matrix")
R_REQ: Ref = ("5.3", "To: [required approver(s)]", "5.3 Approval Request Email Format")
R_REQ2: Ref = ("5.3", "Amount: $[AMOUNT]. Description:", "5.3 Approval Request Email Format")
R_COURTESY: Ref = ("5.3", "\"Dear [Vendor Contact Name], Invoice [INVOICE NUMBER]", "5.3 vendor delay notice")
R_QUEUE: Ref = ("7", "After an invoice has been matched (or approved as non-PO)", "7")
R_DISC: Ref = ("7.2", "Rule: Always take the early payment discount", "7.2")
R_DISCF: Ref = ("7.2", "EARLY PAYMENT DISCOUNT:", "7.2 format")
R_FILES: Ref = ("3.2", "Path Contents Invoices/YYYY-MM/", "3.2")
R_ADHOC: Ref = ("3", "All AP staff must use the following systems and file paths", "3")
R_CHAN: Ref = ("3.3", "Use the following Slack channels for all AP communications", "3.3")
R_ESC: Ref = ("13", "Escalations must be posted to the correct Slack channel", "13")
R_EXACT: Ref = ("13.3", "All escalation Slack messages must follow these exact formats", "13.3")
R_BANK1: Ref = ("13.2", "Step 1: Do NOT update vendor_master.xlsx", "13.2 Step 1")
R_BANK5: Ref = ("13.2", "Step 5: Only after receiving written verification", "13.2 Step 5")
R_AUDIT: Ref = ("16", "All AP transactions are subject to internal and external audit", "16")
R_RETAIN: Ref = ("16.1", "Retain all AP records", "16.1")
R_INCOMP: Ref = ("4.2", "When an invoice is missing required fields", "4.2")
R_COMPLETE: Ref = ("4.1", "Before processing, verify the invoice contains", "4.1")
R_DUPCHK: Ref = ("5.2", "After classifying an invoice (Section 4.3)", "5.2")
R_DUPPOST: Ref = ("3", "If a duplicate is detected: Do NOT enter the invoice", "5.2")
R_INTAKE: Ref = ("4", "All invoices arrive through one of three channels", "4")

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


def date_rx(d: dt.date) -> str:
    mon = MONTHS[d.month - 1]
    return (rf"(?:0?{d.month}/0?{d.day}/{d.year}|{d.year}-{d.month:02d}-{d.day:02d}|"
            rf"{mon} 0?{d.day},? {d.year}|{mon[:3]}\.? 0?{d.day},? {d.year})")


VENDORS = [
    dict(key="hc", name="Harrison & Cole LLP", name_rx=r"Harrison (?:&|&amp;|and) Cole LLP", find=r"harrison",
         tax="23-7654321", inv="HC-2025-0001", amount=5000.00, amount_rx=r"\$5,?000(?:\.00)?",
         date=dt.date(2025, 9, 4), bank=r"first national bank of philadelphia", bank_name="First National Bank of Philadelphia",
         routing="031100209", account="7742851903", phone="2155550340", address=r"1200 Market",
         desc=r"Employment law consultation", desc_hint="Employment law consultation - Policy review and compliance assessment",
         domain="harrisoncolellp.com"),
    dict(key="wcg", name="Whitfield Consulting Group, Inc.", name_rx=r"Whitfield Consulting Group(?:,? Inc\.?)?",
         find=r"whitfield", tax="23-7891045", inv="WCG-2025-0087", amount=4950.00, amount_rx=r"\$4,?950(?:\.00)?",
         date=dt.date(2025, 8, 28), bank=r"first republic", bank_name="First Republic Bank",
         routing="321081669", account="7720194583", phone="2155550418", address=r"450 Independence",
         desc=r"FMLA/ADA", desc_hint="Memorandum re: FMLA/ADA intersection analysis",
         domain="whitfieldcg.com"),
]
HC, WCG = VENDORS
CPT_INV = "CPT-2025-0412"
CPT_TAX = "58-8901234"
DISC_DEADLINE = dt.date(2025, 9, 14)
GL_RX = r"(?:1000-\d{3}-6100|6100-\d{3}-\d{4})"


def terms_ok(v, value) -> bool:
    # Whitfield's $99 discount is not taken ("standard terms"), so plain Net 30 is also accepted there.
    rx = r"(?:2/10,? ?)?net ?30" if v is WCG else r"2/10,? ?net ?30"
    return bool(re.fullmatch(rx, norm(value)))


def digits(v) -> str:
    return re.sub(r"\D", "", str(v or ""))


def as_date(v) -> dt.date | None:
    s = str(v or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    n = num(s)
    if n is not None and 30000 < n < 60000:
        return dt.date(1899, 12, 30) + dt.timedelta(days=int(n))
    return None


# ---- vendor master ------------------------------------------------------------------------------

def vm_rows(ctx, v) -> list[dict]:
    w = world(ctx)
    return [r for r in w.new_rows(VM, VM_HDR)
            if digits(w.col(r, r"^Tax ID")) == digits(v["tax"]) or re.search(v["find"], w.col(r, r"^Vendor Name"), re.I)]


def vendor_id(ctx, v) -> str | None:
    rows = vm_rows(ctx, v)
    vid = world(ctx).col(rows[0], r"^Vendor ID") if len(rows) == 1 else ""
    return vid if vid in NEW_IDS else None


def id_rx(ctx, v) -> str:
    vid = vendor_id(ctx, v)
    return re.escape(vid) if vid else r"V-0003[89]"


def id_hint(ctx, v) -> str:
    return vendor_id(ctx, v) or "V-00038/V-00039 (the Vendor ID you assigned in vendor_master.xlsx)"


def vendor_checks(ctx):
    w = world(ctx)
    refs = [R_ROW, R_1099, R_1099T]
    assigned = []
    for v in VENDORS:
        rows = vm_rows(ctx, v)
        want = (f"Vendor ID (next sequential: {' / '.join(NEW_IDS)}), Vendor Name {v['name']}, Tax ID {v['tax']}, "
                f"Address, Contact Name, Contact Email, Phone, Payment Terms 2/10 Net 30, Bank Name {v['bank_name']}, "
                f"Bank Routing {v['routing']}, Bank Account {v['account']}, 1099 Reportable Yes, 1099 Type NEC, "
                f"Status Active, Created Date 2025-09-04")
        if not rows:
            yield False, f"{v['name']} is not in vendor_master.xlsx. Add one new row: {want}.", [R_SETUP] + refs
            continue
        if len(rows) > 1:
            yield False, f"{v['name']} has {len(rows)} new rows in vendor_master.xlsx; keep exactly one.", refs
            continue
        r = rows[0]
        vid = w.col(r, r"^Vendor ID")
        assigned.append(vid)
        bad = []
        if vid not in NEW_IDS:
            bad.append(f"Vendor ID must be the next sequential number after V-00037 ({' or '.join(NEW_IDS)}), got '{vid}'")
        if not re.search(v["find"], w.col(r, r"^Vendor Name"), re.I):
            bad.append(f"Vendor Name must be {v['name']}")
        if digits(w.col(r, r"^Tax ID")) != digits(v["tax"]):
            bad.append(f"Tax ID must be {v['tax']} (from the W-9)")
        for col in (r"^Address", r"^Contact Name", r"^Contact Email", r"^Phone", r"^Payment Terms", r"^Bank Name",
                    r"Routing", r"Bank Account", r"^1099 Reportable", r"^1099 Type", r"^Status", r"^Created Date"):
            if not w.col(r, col):
                bad.append(f"required field '{col.strip('^')}' is blank")
        if w.col(r, r"^Address") and not re.search(v["address"], w.col(r, r"^Address"), re.I):
            bad.append(f"Address must be the W-9 address ({v['address']}...)")
        if w.col(r, r"^Phone") and digits(w.col(r, r"^Phone"))[-10:] != v["phone"]:
            bad.append(f"Phone must be the vendor's number ({v['phone'][:3]}) {v['phone'][3:6]}-{v['phone'][6:]}")
        if w.col(r, r"^Payment Terms") and not terms_ok(v, w.col(r, r"^Payment Terms")):
            bad.append("Payment Terms must be 2/10 Net 30")
        if w.col(r, r"^Bank Name") and not re.search(v["bank"], w.col(r, r"^Bank Name"), re.I):
            bad.append(f"Bank Name must be {v['bank_name']}")
        if w.col(r, r"Routing") and digits(w.col(r, r"Routing")).lstrip("0") != v["routing"].lstrip("0"):
            bad.append(f"Bank Routing must be {v['routing']}")
        if w.col(r, r"Bank Account") and digits(w.col(r, r"Bank Account")) != v["account"]:
            bad.append(f"Bank Account must be {v['account']}")
        if w.col(r, r"^1099 Reportable") and norm(w.col(r, r"^1099 Reportable")) != "yes":
            bad.append("1099 Reportable must be Yes" + (" (payments for legal services are always 1099-reportable, "
                                                          "even for an S-Corp)" if v is WCG else " (law firm / partnership)"))
        if w.col(r, r"^1099 Type") and not re.fullmatch(r"(1099-)?nec", norm(w.col(r, r"^1099 Type"))):
            bad.append("1099 Type must be NEC (services, including legal services)")
        if w.col(r, r"^Status") and norm(w.col(r, r"^Status")) != "active":
            bad.append("Status must be Active")
        if w.col(r, r"^Created Date") and as_date(w.col(r, r"^Created Date")) != dt.date(2025, 9, 4):
            bad.append("Created Date must be today, 2025-09-04")
        yield not bad, f"vendor_master.xlsx row for {v['name']} ({vid}): " + "; ".join(bad) + ".", refs
    if len(assigned) == 2 and assigned[0] == assigned[1]:
        yield False, f"Both new vendors got Vendor ID {assigned[0]}; use V-00038 and V-00039 (one each).", [R_ROW]


def clearpath_vendor_checks(ctx):
    w = world(ctx)
    rows = w.rows(VM, VM_HDR)
    cp = [w.col(r, r"^Vendor ID") or "?" for r in rows if re.search(r"clear\s*path", w.col(r, r"^Vendor Name"), re.I)]
    same_tax = [r for r in rows if digits(w.col(r, r"^Tax ID")) == digits(CPT_TAX)]
    ok = not cp and len(same_tax) <= 1
    yield ok, ("ClearPath Talent Solutions' W-9 Tax ID 58-8901234 already belongs to Premier Staffing Group (V-00008): "
               "do NOT create a vendor record for ClearPath. Remove the added vendor_master.xlsx row"
               f"{' (' + ', '.join(cp) + ')' if cp else ''}."), [R_TAXID, R_SETUP]


# ---- AP ledger ----------------------------------------------------------------------------------

def ir_rows(ctx, inv: str, which: str = "current") -> list[dict]:
    w = world(ctx)
    return [r for r in w.rows(LEDGER, IR_HDR, which, IR_SHEET) if norm(w.col(r, r"^Invoice Number")) == norm(inv)]


def ledger_checks(ctx):
    w = world(ctx)
    for v in VENDORS:
        rows = ir_rows(ctx, v["inv"])
        vid = vendor_id(ctx, v)
        want = (f"Vendor ID {id_hint(ctx, v)}, Vendor Name {v['name']}, Invoice Number {v['inv']}, "
                f"Invoice Date {v['date'].isoformat()}, PO Number blank, Category Non-PO, Amount {v['amount']:.2f}, "
                f"GL Code 1000-120-6100 (HR professional services), Payment Terms 2/10 Net 30, not approved yet")
        if not rows:
            yield False, f"Invoice {v['inv']} ({v['name']}) is not in the Invoice Register of ap_ledger.xlsx. Enter it: {want}.", \
                [R_INTAKE, R_CLASS, R_NONPO]
            continue
        if len(rows) > 1:
            yield False, f"Invoice {v['inv']} appears {len(rows)} times in the Invoice Register; keep one row.", [R_DUPCHK]
            continue
        r = rows[0]
        bad = []
        rid = w.col(r, r"^Vendor ID")
        if (vid and rid != vid) or (not vid and rid not in NEW_IDS):
            bad.append(f"Vendor ID must be {id_hint(ctx, v)}, got '{rid}'")
        if not re.search(v["find"], w.col(r, r"^Vendor Name"), re.I):
            bad.append(f"Vendor Name must be {v['name']}")
        if as_date(w.col(r, r"^Invoice Date")) != v["date"]:
            bad.append(f"Invoice Date must be {v['date'].isoformat()}")
        if w.col(r, r"^PO Number"):
            bad.append("PO Number must be blank (no PO referenced)")
        if norm(w.col(r, r"^Category")) not in ("non-po", "non-po invoice"):
            bad.append("Category must be Non-PO")
        if not same(w.col(r, r"^Amount"), v["amount"]):
            bad.append(f"Amount must be {v['amount']:.2f} (the invoice total)")
        if not re.fullmatch(GL_RX, w.col(r, r"^GL Code")):
            bad.append("GL Code must be a Professional Services code 1000-NNN-6100 (HR department: 1000-120-6100)")
        if not terms_ok(v, w.col(r, r"^Payment Terms")):
            bad.append("Payment Terms must be 2/10 Net 30")
        if norm(w.col(r, r"^Status")) in ("approved", "paid") or w.col(r, r"^Approved By"):
            bad.append("the invoice is not approved yet (approval emails pending): Status must not be Approved/Paid and "
                       "Approved By must stay blank")
        yield not bad, f"Invoice Register row for {v['inv']}: " + "; ".join(bad) + ".", [R_CLASS, R_NONPO]
    if ir_rows(ctx, CPT_INV):
        yield False, ("Invoice CPT-2025-0412 (ClearPath) must not be entered: the vendor does not exist in "
                      "vendor_master.xlsx (its Tax ID matches Premier Staffing Group V-00008). Remove the row."), \
            [R_SETUP, R_TAXID]
    allowed = {norm(v["inv"]) for v in VENDORS} | {norm(CPT_INV)}
    extra = [w.col(r, r"^Invoice Number") or "?" for r in w.new_rows(LEDGER, IR_HDR, IR_SHEET)
             if norm(w.col(r, r"^Invoice Number")) not in allowed]
    yield not extra, (f"Unrequested new Invoice Register rows {extra}: only HC-2025-0001 and WCG-2025-0087 are to be "
                      "entered. Remove them."), [R_SETUP, R_AUDIT]


def other_sheets_checks(ctx):
    w = world(ctx)
    name, cur = w.book(LEDGER)
    _, ini = w.book(LEDGER, "initial")
    if not ini or not cur:
        return
    for sheet in ("PO Register", "Payment Queue", "GL Postings"):
        if sheet in ini and not book_eq(cur.get(sheet), ini.get(sheet)):
            yield False, (f"ap_ledger.xlsx '{sheet}' was changed. The new non-PO invoices are awaiting approval: they "
                          "enter the payment queue only after approval, and nothing else in this sheet is part of "
                          "this task. Restore the sheet."), [R_QUEUE, R_NONPO]


def file_checks(ctx):
    w = world(ctx)
    ini = set(w.initial or {})
    keep = re.compile(r"^(vendor_master|ap_ledger|exceptions_tracker_2025)\.xlsx$")
    changed = [k for k in w.changed_files() if not keep.search(k)]
    yield not changed, (f"Workbooks {changed} were changed but nothing in them is part of processing these three "
                        "invoices. Restore them."), [R_AUDIT]
    created = [k for k in w.created_books() if k not in ini]
    yield not created, (f"New spreadsheets {created} were created. The SOP forbids ad hoc spreadsheets; keep the work "
                        "in the designated workbooks and delete these."), [R_ADHOC]


def stored_checks(ctx):
    w = world(ctx)
    root = config.workdir()
    files = w.files()

    def pdf_ok(rel: str) -> bool:
        try:
            with open(root / rel, "rb") as fh:
                return fh.read(5) == b"%PDF-"
        except OSError:
            return False

    for v in VENDORS:
        w9 = [f for f in files if re.search(rf"^W-?9_.*{v['find']}.*\.pdf$", f.split("/")[-1], re.I) and pdf_ok(f)]
        yield bool(w9), (f"Store {v['name']}'s W-9 (email attachment) as a PDF named per the SOP: "
                         f"1099/2025/W9_{re.sub(r'[^A-Za-z]+', '_', v['name'].replace(', Inc.', '')).strip('_')}.pdf "
                         "(file name W9_<VendorName>.pdf)."), [R_W9, R_FILES]
        vid = vendor_id(ctx, v)
        want = f"INV-{vid or '<VendorID>'}-{v['inv']}.pdf"
        inv = [f for f in files if vid and f.split("/")[-1].lower() == want.lower() and pdf_ok(f)]
        yield bool(inv), (f"Store {v['name']}'s invoice PDF (email attachment) with the SOP name {want} "
                          "(Invoices/YYYY-MM/INV-[VendorID]-[InvoiceNumber].pdf)."), [R_FILES]


# ---- messages -----------------------------------------------------------------------------------

def has(rx: str, a) -> bool:
    return bool(re.search(rx, text_of(a), re.I))


def tag(t: str, a) -> bool:
    """SOP message tags are upper-case literals; match them case-sensitively so prose mentions do not count."""
    return t in text_of(a)


def comm_specs(ctx) -> list[Comm]:
    specs: list[Comm] = []
    for v in VENDORS:
        sub_rx = rf"AP APPROVAL REQUIRED: {v['name_rx']} – {v['amount_rx']} – Invoice {re.escape(v['inv'])}"
        sub_hint = f"AP APPROVAL REQUIRED: {v['name']} - ${v['amount']:,.2f} - Invoice {v['inv']}"
        body = [
            (r"A non-PO invoice requires your approval before payment can be processed",
             "\"A non-PO invoice requires your approval before payment can be processed.\""),
            (rf"Vendor: {v['name_rx']} \({id_rx(ctx, v)}\)", f"\"Vendor: {v['name']} ({id_hint(ctx, v)})\""),
            (rf"Invoice: {re.escape(v['inv'])}, dated {date_rx(v['date'])}",
             f"\"Invoice: {v['inv']}, dated {v['date'].strftime('%m/%d/%Y')}\""),
            (rf"Amount: {v['amount_rx']}", f"\"Amount: ${v['amount']:,.2f}\""),
            (rf"Description: [^\n]*{v['desc']}", f"\"Description: {v['desc_hint']}\" (first line item)"),
            (rf"GL Code: {GL_RX}", "\"GL Code: 1000-120-6100\" (the GL code entered in the Invoice Register)"),
            (r"reply APPROVED or REJECTED", "\"Please reply APPROVED or REJECTED with reason.\""),
            (r"within 3 business days", "\"If no response is received within 3 business days, ...\""),
        ]
        for who, mail in (("Jennifer Walsh (Department Manager, HR - budget owner)", JW),
                          ("Maria Santos (AP Manager)", MS)):
            specs.append(Comm(
                key=f"approval_{v['key']}_{mail.split('.')[0]}", kind="email",
                about=lambda a, v=v, mail=mail: a.kind in ("email_send", "email_draft")
                and (tag("AP APPROVAL REQUIRED", a) or has(r"\bapprov", a)) and v["inv"].lower() in text_of(a).lower()
                and mail in (a.recipients + a.cc),
                what=f"non-PO approval request for {v['inv']} to {who}", refs=[R_NONPO, R_TIER, R_REQ, R_REQ2],
                to=[mail], cc=[AP_TEAM], exact_to=False, subject=sub_rx, subject_hint=sub_hint, body=body))
        specs.append(Comm(
            key=f"new_vendor_{v['key']}", kind="slack_post", channel="approvals",
            about=lambda a, v=v: tag("NEW VENDOR ADDED", a) and has(v["find"], a),
            what=f"NEW VENDOR ADDED post for {v['name'].rstrip('.')}", refs=[R_POST, R_CHAN],
            body=[(rf"NEW VENDOR ADDED: {v['name_rx']}, {id_rx(ctx, v)}, 1099 Reportable: (?:Yes|YES)\b",
                   f"\"NEW VENDOR ADDED: {v['name']}, {id_hint(ctx, v)}, 1099 Reportable: Yes\"")]))
        specs.append(Comm(
            key=f"incomplete_{v['key']}", kind="email",
            about=lambda a, v=v: a.kind in COMM_KINDS and re.search(r"incomplete invoice", a.subject, re.I)
            and has(re.escape(v["inv"]), a),
            what=f"incomplete-invoice return for {v['inv']}", refs=[R_COMPLETE, R_INCOMP],
            forbidden=f"Invoice {v['inv']} has every required field (Section 4.1); do not return it as incomplete."))
        specs.append(Comm(
            key=f"courtesy_{v['key']}", kind="email",
            about=lambda a, v=v: a.kind in ("email_send", "email_draft") and has(r"pending internal approval", a)
            and any(v["domain"] in x for x in a.recipients + a.cc),
            what=f"approval-delay notice to {v['name']}", refs=[R_REQ2, R_COURTESY],
            forbidden="The approval window (3 business days) has not passed; the vendor delay notice is sent only if "
                      "approval is not received within the allowed timeframe."))
    specs.append(Comm(
        key="discount_hc", kind="slack_post", channel="accounts-payable",
        about=lambda a: tag("EARLY PAYMENT DISCOUNT", a) and has(r"harrison|HC-2025-0001", a),
        what="EARLY PAYMENT DISCOUNT post for Harrison & Cole (2% of $5,000.00 = $100.00 >= $100)",
        refs=[R_DISC, R_DISCF, R_CHAN],
        body=[(rf"EARLY PAYMENT DISCOUNT: {HC['name_rx']}, Invoice HC-2025-0001, Discount \$ ?100(?:\.00)?, "
               rf"Deadline {date_rx(DISC_DEADLINE)}",
               "\"EARLY PAYMENT DISCOUNT: Harrison & Cole LLP, Invoice HC-2025-0001, Discount $100.00, "
               "Deadline 09/14/2025\"")]))
    specs.append(Comm(
        key="discount_wcg", kind="slack_post",
        about=lambda a: tag("EARLY PAYMENT DISCOUNT", a) and has(r"whitfield|WCG-2025-0087", a),
        what="EARLY PAYMENT DISCOUNT post for Whitfield", refs=[R_DISC],
        forbidden="Whitfield's 2% discount is $99.00, under the $100 threshold: process at standard terms "
                  "(Net 30) and do not post an EARLY PAYMENT DISCOUNT notice."))
    specs.append(Comm(
        key="dup_vendor_cpt", kind="slack_post", channel="vendor-management",
        about=lambda a: tag("DUPLICATE VENDOR SUSPECTED", a) and has(r"clear\s*path", a),
        what="DUPLICATE VENDOR SUSPECTED post for ClearPath Talent Solutions (W-9 Tax ID 58-8901234 = V-00008)",
        refs=[R_TAXID, R_ESC, R_EXACT],
        exact=(r"DUPLICATE VENDOR SUSPECTED: ClearPath Talent Solutions matches Tax ID of existing vendor "
               r"Premier Staffing Group, V-00008\.?"),
        exact_hint=("DUPLICATE VENDOR SUSPECTED: ClearPath Talent Solutions matches Tax ID of existing vendor "
                    "Premier Staffing Group, V-00008")))
    specs.append(Comm(
        key="new_vendor_cpt", kind="slack_post",
        about=lambda a: tag("NEW VENDOR ADDED", a) and has(r"clear\s*path", a),
        what="NEW VENDOR ADDED post for ClearPath", refs=[R_TAXID],
        forbidden="ClearPath's Tax ID matches existing vendor Premier Staffing Group (V-00008): no new vendor record "
                  "is created, so there is no NEW VENDOR ADDED post."))
    specs.append(Comm(
        key="approval_cpt", kind="email",
        about=lambda a: tag("AP APPROVAL REQUIRED", a) and has(r"CPT-2025-0412|clear\s*path", a),
        what="approval request for ClearPath invoice CPT-2025-0412", refs=[R_SETUP, R_TAXID],
        forbidden="No invoice may be processed for a vendor that does not exist in vendor_master.xlsx; ClearPath was "
                  "not set up (duplicate Tax ID), so do not request approval for CPT-2025-0412."))
    specs.append(Comm(
        key="dup_invoice", kind="slack_post",
        about=lambda a: tag("DUPLICATE DETECTED", a) and has(r"HC-2025-0001|WCG-2025-0087|CPT-2025-0412", a),
        what="DUPLICATE DETECTED notice", refs=[R_DUPCHK, R_DUPPOST],
        forbidden="None of these invoices matches an existing Invoice Register entry on vendor ID + invoice number + "
                  "amount, so they are not duplicate invoices."))
    return specs


def approval_recipients(ctx, a):
    if a.kind not in ("email_send", "email_draft") or not tag("AP APPROVAL REQUIRED", a):
        return None
    if not any(v["inv"].lower() in text_of(a).lower() for v in VENDORS):
        return None
    extra = sorted(set(a.recipients + a.cc) - {JW, MS, AP_TEAM, SELF})
    if extra:
        return (f"Non-PO invoices of $500.01-$5,000.00 need approval from the Department Manager (Jennifer Walsh, HR) "
                f"and the AP Manager (Maria Santos) only, with CC {AP_TEAM}. Remove {', '.join(extra)}.")
    return None


def vendor_first(ctx, a):
    """Approval requests / NEW VENDOR ADDED posts only once the vendor row exists (12.1 opening + Step 3 -> 4)."""
    if a.kind not in COMM_KINDS or not (tag("AP APPROVAL REQUIRED", a) or tag("NEW VENDOR ADDED", a)):
        return None
    if not world(ctx).current:  # workbook dump failed: fail open
        return None
    for v in VENDORS:
        if (v["inv"].lower() in text_of(a).lower() or has(v["find"], a)) and not vm_rows(ctx, v):
            return (f"{v['name']} is not in vendor_master.xlsx yet. Add the vendor row first (next Vendor ID "
                    f"{' / '.join(NEW_IDS)}), then send this message with that Vendor ID.")
    return None


RULES = (
    comm_rules("comms", comm_specs)
    + pre_rule("comms.approval_recipients", approval_recipients, [R_TIER, R_REQ],
               "Address the approval request to jennifer.walsh@ and maria.santos@meridianpartners.com, CC ap.team@.")
    + pre_rule("comms.vendor_setup_first", vendor_first, [R_SETUP, R_ROW, R_POST],
               "Add the vendor to vendor_master.xlsx first.")
    + no_placeholders([R_REQ])
    + state_rule("vendor_master.new_vendors", vendor_checks, "Fix vendor_master.xlsx as listed.")
    + state_rule("vendor_master.no_clearpath", clearpath_vendor_checks, "Remove the ClearPath vendor record.")
    + append_only("vendor_master.append_only", VM, VM_HDR, "vendor_master.xlsx (existing vendor rows, incl. bank details)",
                  [R_BANK1, R_BANK5, R_ROW])
    + state_rule("ledger.invoice_entries", ledger_checks, "Fix the Invoice Register as listed.")
    + append_only("ledger.register_append_only", LEDGER, IR_HDR, "The Invoice Register", [R_AUDIT, R_RETAIN], IR_SHEET)
    + state_rule("ledger.other_sheets_unchanged", other_sheets_checks, "Restore the sheet.")
    + append_only("exceptions.append_only", r"^exceptions_tracker_2025\.xlsx$", r"^Exception ID$",
                  "exceptions_tracker_2025.xlsx", [R_AUDIT, R_RETAIN])
    + state_rule("files.no_unrequested_changes", file_checks, "Restore / remove the files listed.")
    + state_rule("files.stored_documents", stored_checks, "Save the attachment under the SOP file name.")
)
