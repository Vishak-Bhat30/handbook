"""Verifiers for finance_meridian_partners_cc2fc143 (Meridian SOP-FIN-AP-004).

Situation (seed data, 2026-03-24): invoice GLFD-0441 from Great Lakes Furniture & Design Co. (V-00009, Active,
Net 30, bank info on file), dated 2026-03-20, $7,900.00, Non-PO, Office Supplies account. Payment terms are blank
on the invoice, which SOP 4.1 resolves to the vendor-master terms (Net 30) - the invoice is complete. Non-PO
$5,000.01-$25,000.00 -> retroactive approval by the Department Manager AND the Controller (SOP 5.3). The user wants
the register row, the approval request saved as a DRAFT (not sent) and any required Slack message.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..kit import (Comm, Finding, Rule, World, blank, comm_rules, dashes, nh, no_placeholders, norm, num, registry,
                   state_rule, text_of, world)

INV = "GLFD-0441"
VID = "V-00009"
VNAME = "Great Lakes Furniture & Design Co."
AMOUNT = 7900.00
INV_DATE, RECEIVED, DUE = "2026-03-20", "2026-03-24", "2026-04-19"  # due = invoice date + 30 (vendor master Net 30)
FIRST_LINE = "Executive conference table, 10-person, walnut finish"
CONTROLLER = "r.whitfield@meridianpartners.com"
AP_INBOX = "ap@meridianpartners.com"
VENDOR_DOMAIN = "greatlakesfurniture.com"
FALLBACK_MANAGERS = {"m.chen@meridianpartners.com": ("100", "M. Chen"),
                     "j.carter@meridianpartners.com": ("200", "J. Carter"),
                     "k.desantis@meridianpartners.com": ("300", "K. DeSantis"),
                     "b.singh@meridianpartners.com": ("400", "B. Singh")}
LEDGER = r"ap_ledger\.xlsx$"

R_LOG = ("4", "All invoices arrive through one of three channels", "4 (log and classify every invoice)")
R_FIELDS = ("4.1", "Required Field Example", "4.1 (required fields; missing terms default to vendor master)")
R_RETURN = ("4.1", "Before processing, verify the invoice contains", "4.1 (only incomplete invoices are returned)")
R_CLASS = ("4.3", "Category Criteria Next Step", "4.3 (Non-PO classification)")
R_NONPO = ("5.3", "Invoices without a valid PO require retroactive approval", "5.3 (approval before payment)")
R_TIER = ("5.3", "Meridian Partners, LLC SOP-FIN-AP-004 $5,000.01", "5.3 ($5,000.01-$25,000.00 tier)")
R_TIER_LOW = ("5.3", "Invoice Amount Required Approver", "5.3 (approval tiers)")
R_FMT = ("5.3", "To: [required approver(s)]", "5.3 (approval request email format)")
R_FMT2 = ("5.3", "Amount: $[AMOUNT]. Description:", "5.3 (approval request body; APPR hold only after the window)")
R_FORMATS = ("3", "All AP staff must use the following systems", "3 (YYYY-MM-DD dates, no ad hoc spreadsheets)")
R_TERMS = ("2", "Payment Terms The agreed-upon", "2 (Net 30 = due 30 days from invoice date)")
R_GL = ("2", "6100-xxx-xxxx (Professional Services)", "2 (GL account 6200 = Office Supplies)")
R_GLFMT = ("2", "NNNN-NNN-NNNN (Entity-Department-Account)", "2 (GL code format)")
R_HOLDS = ("2", "Hold Status An invoice flagged", "2 (hold codes)")
R_VM = ("2", "Vendor Master The central record", "2 (vendor master)")
R_ACH = ("15.3", "Method When Used Amount Range", "15.3 (ACH default for vendors with bank info)")
R_QUEUE = ("7", "After an invoice has been matched (or approved as non-PO)", "7 (payment queue only after approval)")
R_GLPOST = ("5.1.1", "The following tolerances determine", "5.1.1 (post to GL on approval)")
R_MATCH = ("5.1", "For every PO invoice, the AP clerk must verify", "5.1 (match log is for PO invoices)")
R_SLACK = ("3.3", "Use the following Slack channels for all AP communications", "3.3 (Slack channels, no DMs)")
R_SLACK2 = ("3.3", "Meridian Partners, LLC SOP-FIN-AP-004 #ap-approvals", "3.3 (#ap-approvals: non-PO approval requests)")
INSTRUCTION = ("Task instruction: \"if an email should be sent, draft it for me and put it in Drafts. Do NOT send it - "
               "I will review it myself before sending.\"")

EMAIL_KINDS = ("email_send", "email_draft")


# ---- value-normalised row/book comparison --------------------------------------------------------
# kit's append_only/new_rows/book_eq compare str(cell); an openpyxl re-save turns 3500.0 into 3500, so every
# row of a re-saved workbook would look edited. These helpers compare numbers numerically instead.

def canon(v) -> str:
    s = nh(v)
    if s in ("None", "nan"):
        return ""
    if re.fullmatch(r"-?\d[\d,]*(\.\d+)?|-?\.\d+", s):
        return repr(round(float(s.replace(",", "")), 6))
    return s


def _key(r: dict) -> tuple:
    return tuple(canon(v) for k, v in r.items() if k != "__row__")


def _diff(a: list[dict], b: list[dict]) -> list[dict]:
    """Rows of ``b`` not matched (multiset) by a row of ``a``."""
    pool = [_key(r) for r in a]
    out = []
    for r in b:
        k = _key(r)
        if k in pool:
            pool.remove(k)
        else:
            out.append(r)
    return out


def new_rows(w: World, name_rx: str, header_rx: str, sheet_rx: str) -> list[dict]:
    return _diff(w.rows(name_rx, header_rx, "initial", sheet_rx), w.rows(name_rx, header_rx, "current", sheet_rx))


def append_only_rule(rule_id: str, header_rx: str, sheet_rx: str, what: str, refs: list) -> list[Rule]:
    def checks(ctx):
        w = world(ctx)
        init = w.rows(LEDGER, header_rx, "initial", sheet_rx)
        if not init:
            return
        gone = _diff(w.rows(LEDGER, header_rx, "current", sheet_rx), init)
        eg = " | ".join(str(v) for k, v in list(gone[0].items())[:5] if k != "__row__") if gone else ""
        yield (not gone, f"{what} is append-only: {len(gone)} existing row(s) were edited or removed (e.g. {eg}). "
                         "Restore them and only append new rows.", refs)
    return state_rule(rule_id, checks, "Restore the original rows.")


def _grid(sheet: list) -> list[tuple]:
    rows = [tuple(canon(c) for c in r) for r in sheet or []]
    rows = [tuple(list(r)[:max([i + 1 for i, c in enumerate(r) if c] or [0])]) for r in rows]
    while rows and not rows[-1]:
        rows.pop()
    return rows


def book_same(a, b) -> bool:
    if not isinstance(a, dict) or not isinstance(b, dict) or set(a) != set(b):
        return False
    return all(_grid(a[s]) == _grid(b[s]) for s in a)


def _mentions(a) -> bool:
    return bool(re.search(r"GLFD[-\s]?0*441|great\s+lakes", text_of(a), re.I))


def _to_vendor(a) -> bool:
    return any(VENDOR_DOMAIN in x.lower() for x in list(a.recipients) + list(a.cc))


def managers(w: World) -> dict[str, tuple[str, str]]:
    """Department managers from directory.xlsx: email -> (dept code, name)."""
    out = {}
    for r in w.rows(r"directory\.xlsx$", r"^Dept Code$", "initial"):
        if re.search(r"dept manager", w.col(r, r"^Role"), re.I) and re.search(r"@", w.col(r, r"^Email$")):
            code = re.sub(r"\.0$", "", w.col(r, r"^Dept Code$"))
            out[w.col(r, r"^Email$").lower()] = (code, w.col(r, r"^Name$"))
    return out or dict(FALLBACK_MANAGERS)


def _mgr_hint(mgrs: dict) -> str:
    return ", ".join(f"{d} = {n} <{e}>" for e, (d, n) in sorted(mgrs.items(), key=lambda kv: kv[1][0]))


@dataclass
class ApprovalComm(Comm):
    """SOP 5.3 approval request; additionally checks the Department Manager matches the GL department."""
    managers: dict = field(default_factory=dict)

    def problems(self, a, w):
        out = super().problems(a, w)
        if a.kind not in EMAIL_KINDS:
            return out
        to, cc = {x.lower() for x in a.recipients}, {x.lower() for x in a.cc}
        depts = "|".join(sorted({d for d, _ in self.managers.values()}))
        m = re.search(rf"GL Code:\s*1000-({depts})-6200", dashes(a.text), re.I)
        want = next((e for e, (d, _) in self.managers.items() if m and d == m.group(1)), None)
        present = sorted(to & set(self.managers))
        if want and want not in to:
            out.append(f"To must include the Department Manager who owns GL department {m.group(1)}: {want}.")
        elif not want and not present:
            out.append("To must include the Department Manager (budget owner) of the GL code's department "
                       f"({_mgr_hint(self.managers)}).")
        keep = {want} if want else set(present[:1])
        extra = sorted((to | cc) - {x.lower() for x in self.to} - {x.lower() for x in self.cc} - keep)
        if extra:
            out.append("Remove recipients the SOP does not route a $5,000.01-$25,000.00 non-PO approval to: "
                       f"{', '.join(extra)} (To: Department Manager + Controller, CC: {AP_INBOX}).")
        return out


def specs(ctx) -> list[Comm]:
    def build():
        w = world(ctx)
        mgrs = managers(w)
        depts = "|".join(sorted({d for d, _ in mgrs.values()}))
        subject = f"AP APPROVAL REQUIRED: {VNAME} - $7,900.00 - Invoice {INV}"
        body = (f"A non-PO invoice requires your approval before payment can be processed. Vendor: {VNAME} ({VID}). "
                f"Invoice: {INV}, dated {INV_DATE}. Amount: $7,900.00. Description: {FIRST_LINE}. "
                "GL Code: 1000-<dept>-6200. Please reply APPROVED or REJECTED with reason. If no response is received "
                "within 5 business days, the invoice will be placed on APPR hold and the vendor will be notified of "
                "the delay.")
        return [
            ApprovalComm(
                key="approval_request", kind="draft",
                about=lambda a: (a.kind in EMAIL_KINDS and _mentions(a) and not _to_vendor(a)
                                 and bool(re.search(r"approv|GLFD|great\s+lakes", a.subject, re.I))),
                what=("the SOP 5.3 non-PO approval request for GLFD-0441, saved as a DRAFT (the user will send it), "
                      "To: the Department Manager owning the GL department AND Rachel Whitfield (Controller) "
                      f"<{CONTROLLER}>, CC: {AP_INBOX}. Department managers: {_mgr_hint(mgrs)}. Body: \"{body}\""),
                refs=[R_TIER_LOW, R_TIER, R_FMT, R_FMT2, R_FORMATS],
                to=[CONTROLLER], cc=[AP_INBOX], exact_to=False, max_count=3, managers=mgrs,
                subject=r"AP APPROVAL REQUIRED: Great Lakes Furniture & Design Co\.? [-–—] \$7,900\.00 [-–—] "
                        r"Invoice GLFD-0441",
                subject_hint=subject,
                body=[(r"A non-PO invoice requires your approval before payment can be processed",
                       "\"A non-PO invoice requires your approval before payment can be processed.\""),
                      (r"Vendor: Great Lakes Furniture & Design Co\.? \(V-00009\)", f"\"Vendor: {VNAME} ({VID}).\""),
                      (r"Invoice: GLFD-0441, dated 2026-03-20", f"\"Invoice: {INV}, dated {INV_DATE}.\" (YYYY-MM-DD)"),
                      (r"Amount: \$7,900\.00", "\"Amount: $7,900.00.\""),
                      (r"Description: Executive conference table, 10-person, walnut finish",
                       f"\"Description: {FIRST_LINE}.\" (first line item)"),
                      (rf"GL Code: 1000-({depts})-6200", "\"GL Code: 1000-<dept>-6200\" (Office Supplies account, "
                                                         "e.g. 1000-100-6200 for Administration)"),
                      (r"Please reply APPROVED or REJECTED with reason",
                       "\"Please reply APPROVED or REJECTED with reason.\""),
                      (r"If no response is received within 5 business days, the invoice will be placed on APPR hold "
                       r"and the vendor will be notified of the delay",
                       "\"If no response is received within 5 business days, the invoice will be placed on APPR hold "
                       "and the vendor will be notified of the delay.\" (5 days for the $5,000.01-$25,000.00 tier)")]),
            Comm(
                key="no_vendor_email", kind="email",
                about=lambda a: a.kind in EMAIL_KINDS and _to_vendor(a),
                what="email to Great Lakes Furniture & Design",
                refs=[R_RETURN, R_FIELDS, R_FMT2],
                forbidden=("No vendor email is due: GLFD-0441 is complete (blank payment terms default to the vendor "
                           "master's Net 30 per SOP 4.1, so it is not returned) and the 5-business-day approval "
                           "window has not lapsed (the delay notice is sent only after it does). The only email is "
                           "the internal approval request draft.")),
            Comm(
                key="slack_route", kind="slack_post", channel="ap-approvals", required=False, max_count=2,
                about=lambda a: a.kind in ("slack_post", "slack_dm") and _mentions(a),
                what="Slack message about the GLFD-0441 non-PO approval",
                refs=[R_SLACK, R_SLACK2]),
        ]
    return ctx.memo("cc2fc143.specs", build)


# ---- task instruction: drafts only --------------------------------------------------------------

_rules: list[Rule] = []
_rule = registry(_rules)


@_rule("instr.draft_only", "pre", [], source="task_instruction")
def draft_only(ctx, a) -> list[Finding]:
    if a.kind != "email_send":
        return []
    return [Finding("instr.draft_only", [INSTRUCTION],
                    "The user asked for the email to be saved in Drafts, not sent.",
                    ["Save it with google_mail__save_draft (same To/CC/subject/body) and do not send it."])]


# ---- Invoice Register row -----------------------------------------------------------------------

def _date_is(v, ymd: str) -> bool:
    s = str(v or "").strip()
    return s == ymd or bool(re.fullmatch(rf"{ymd}[ T]00:00(:00)?(\.0+)?", s))


def glfd_rows(w: World, which: str = "current") -> list[dict]:
    return [r for r in w.rows(LEDGER, r"^Invoice #$", which, r"Invoice Register")
            if re.fullmatch(r"GLFD-?0*441", w.col(r, r"^Invoice #$"), re.I)]


def register_checks(ctx):
    w = world(ctx)
    rows = glfd_rows(w)
    refs = [R_LOG, R_FIELDS, R_CLASS]
    if not rows:
        yield (False, f"Invoice {INV} ({VNAME}, {VID}, $7,900.00, Non-PO) is complete and must be logged in the "
                      "Invoice Register of ap_ledger.xlsx: Invoice # GLFD-0441, Vendor ID V-00009, Vendor Name "
                      f"{VNAME}, Invoice Date {INV_DATE}, Date Received {RECEIVED}, Due Date {DUE} (vendor master "
                      "Net 30), PO Number Non-PO, Invoice Amount 7900.00, GL Code 1000-<dept>-6200 (Office "
                      "Supplies), Payment Method ACH, and a Status showing it awaits approval.", refs)
        return
    yield (len(rows) == 1, f"{INV} appears {len(rows)} times in the Invoice Register; keep exactly one row.", refs)
    r = rows[-1]
    c = lambda rx: w.col(r, rx)
    yield (norm(c(r"^Vendor ID$")) == norm(VID), f"{INV} row: Vendor ID must be {VID} (got '{c(r'^Vendor ID$')}').",
           [R_VM])
    yield (abs((num(c(r"^Invoice Amount$")) or 0) - AMOUNT) < 0.006,
           f"{INV} row: Invoice Amount must be 7900.00 (got '{c(r'^Invoice Amount$')}').", refs)
    for col, want, extra in (("Invoice Date", INV_DATE, []), ("Date Received", RECEIVED, []),
                             ("Due Date", DUE, [R_TERMS])):
        got = c(rf"^{col}$")
        yield (_date_is(got, want), f"{INV} row: {col} must be {want} (YYYY-MM-DD; got '{got}')."
               + (" The invoice shows no terms, so the vendor master's Net 30 applies: 2026-03-20 + 30 days."
                  if col == "Due Date" else ""), [R_FORMATS, R_FIELDS] + extra)
    po = c(r"^PO Number$")
    yield (not re.search(r"PO-\d", po), f"{INV} row: PO Number must be Non-PO (the invoice cites no PO; got '{po}').",
           [R_CLASS])
    gl = c(r"^GL Code$")
    yield (bool(re.fullmatch(r"1000-\d{3}-6200", gl)),
           f"{INV} row: GL Code must be the Office Supplies account 1000-<dept>-6200, e.g. 1000-100-6200 "
           f"(got '{gl}').", [R_GL, R_GLFMT])
    st = c(r"^Status$")
    bad = norm(st) in ("paid", "approved", "cleared", "released", "ic-hold", "match", "dupl", "disp", "audit")
    yield (not blank(st) and not bad,
           f"{INV} row: Status '{st}' is wrong - the invoice is a non-PO invoice awaiting Department Manager + "
           "Controller approval; it is not paid/approved and has no MATCH/DUPL/DISP/AUDIT/IC-HOLD reason.",
           [R_NONPO, R_HOLDS, R_TIER])
    pm = c(r"^Payment Method$")
    yield (blank(pm) or norm(pm) == "ach",
           f"{INV} row: Payment Method must be ACH (vendor V-00009 has bank details on file; got '{pm}').", [R_ACH])


# ---- ledger / file invariants -------------------------------------------------------------------

def ledger_checks(ctx):
    w = world(ctx)
    pq = [r for r in new_rows(w, LEDGER, r"^Payment Ref$", r"Payment Queue") if re.search(r"GLFD", str(r), re.I)]
    yield (not pq, f"{INV} was added to the Payment Queue; a non-PO invoice cannot be queued for payment before its "
                   "Department Manager + Controller approval. Remove that row.", [R_NONPO, R_QUEUE])
    gl = [r for r in new_rows(w, LEDGER, r"^Entry ID$", r"GL Postings") if re.search(r"GLFD", str(r), re.I)]
    yield (not gl, f"GL Postings rows were added for {INV}; the invoice is not approved yet, so nothing is posted to "
                   "the GL now. Remove those rows.", [R_NONPO, R_GLPOST])
    po = new_rows(w, LEDGER, r"^PO Number$", r"PO Register")
    yield (not po, "Rows were added to the PO Register; GLFD-0441 is a Non-PO invoice and needs no PO. Remove them.",
           [R_CLASS, R_NONPO])


def file_checks(ctx):
    w = world(ctx)
    for name, refs in ((r"vendor_master\.xlsx$", [R_VM]), (r"directory\.xlsx$", [R_VM]),
                       (r"match_log_2026_Q1\.xlsx$", [R_MATCH])):
        for k in w.books(name, "initial"):
            yield (book_same((w.current or {}).get(k), w.initial.get(k)),
                   f"{k} was modified; nothing in this task calls for changing it (the vendor record is already "
                   "correct and a non-PO invoice gets no three-way-match entry). Restore it.", refs)
    new = [b for b in w.created_books() if not re.search(r"(^|/)~\$", b)]
    yield (not new, f"New spreadsheet(s) created: {', '.join(new)}. Do not create ad hoc spreadsheets; delete them.",
           [R_FORMATS])


RULES: list[Rule] = [
    *_rules,
    *comm_rules("comms", specs),
    *no_placeholders([R_FMT, R_FMT2]),
    *state_rule("register.glfd_row", register_checks, "Fix the GLFD-0441 row in the Invoice Register as stated."),
    *append_only_rule("register.append_only", r"^Invoice #$", r"Invoice Register", "The Invoice Register", [R_LOG]),
    *append_only_rule("ledger.po_register_unchanged", r"^PO Number$", r"PO Register", "The PO Register", [R_CLASS]),
    *append_only_rule("ledger.payment_queue_unchanged", r"^Payment Ref$", r"Payment Queue", "The Payment Queue",
                      [R_QUEUE]),
    *append_only_rule("ledger.gl_postings_unchanged", r"^Entry ID$", r"GL Postings", "GL Postings", [R_GLPOST]),
    *state_rule("ledger.no_payment_or_posting", ledger_checks, "Remove the rows listed."),
    *state_rule("files.unchanged", file_checks, "Restore the file / delete the extra file."),
]
