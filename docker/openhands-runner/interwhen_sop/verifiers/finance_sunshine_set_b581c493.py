"""SOP verifiers for finance_sunshine_set_b581c493 (Sunshine & Set Automotive, acting user Jasmine Patel,
Senior Deal Posting Specialist, Friday 2026-04-24).

Inbox items and what the SOP requires for them (derived from the SOP + seed data only):
- email-002 Deal 4481 / Hernandez: approved gross $9,200 vs posted $9,550 (variance $350), total gross > $5,000,
  delivery today 2:30 PM -> #acct-deal-posting template to @marcus.hale, #leadership-escalations template to
  @derrick.soto, Template A to Sofia Ramirez; the deal stays unposted (2.1, 9.2, 9.3).
- email-001 Wells Fargo payoff applied to wrong account (Deal 4477 / Morales) -> forward to Priya Bennett, no reply
  to the lender, payoff-error template in #acct-trade-payoffs tagging Priya and Marcus (2.3).
- email-003 Meridian GAP chargeback CB-2608 / Castellano / $1,600 (Marcus Hale approval level) -> chargeback notice
  template in #acct-chargebacks, backup saved under Accounting/Chargebacks/2026-04 (6).
- email-004 Trent Holloway asks for ACV / book cost (inventory, Darius Kim) -> Template H reply to Trent and forward
  of his email to Darius Kim, no action on the request itself (1.5).
"""

from __future__ import annotations

import dataclasses
import re

from ..kit import (Action, Comm, Context, World, comm_rules, dashes, no_placeholders, norm, pre_rule, state_rule,
                   world)

DOMAIN = "@sunshineandsetauto.com"
SOFIA, MARCUS, PRIYA, DARIUS, TRENT = (f"{n}{DOMAIN}" for n in (
    "sofia.ramirez", "marcus.hale", "priya.bennett", "darius.kim", "trent.holloway"))

R_COMM = ("1.5", "Use the correct Slack channel for", "§1.5 Communication Rules")
R_REDIRECT = ("1.5", "and redirect the sender to the appropriate department contact", "§1.5 role-boundary redirect")
R_VAR = ("2.1", "If the posted deal gross differs from the approved desk recap", "§2.1 gross variance thresholds")
R_VAR_TPL = ("2.1", "Deal #[number] / [Customer Last Name] \u2013 gross variance", "§2.1 #acct-deal-posting template")
R_RESOLVED_WHEN = ("2.1", "When approved by Marcus, use the following template", "§2.1 variance-resolved trigger")
R_RESOLVED_TPL = ("2.1", "Deal #[number] / [Customer Last Name] \u2014 variance resolved", "§2.1 variance-resolved template")
R_LEAD = ("2.1", "When a high-gross deal variance", "§2.1 same-day delivery escalation")
R_LEAD_TPL = ("2.1", "ESCALATION", "§2.1 #leadership-escalations template")
R_TPL_A_WHEN = ("2.1", "When a deal gross variance requires Sales or F&I", "§2.1 Template A requirement")
R_PAYOFF_VAR = ("2.3", "If the actual payoff amount differs", "§2.3 payoff variance")
R_PAYOFF = ("2.3", "escalate to Priya", "§2.3 payoff error escalation")
R_PAYOFF_TPL = ("2.3", "Payoff error", "§2.3 #acct-trade-payoffs template")
R_LENDER = ("2.3", "have direct correspondence with external lenders", "§2.3 external lender emails")
R_CB_TRACK = ("6", "Track all chargebacks including warranty", "§6 chargeback tracking")
R_CB_BACKUP = ("6", "Match each chargeback to the original deal number", "§6 chargeback backup packet")
R_CB_LEVEL = ("6", "Chargebacks under $250 with no dispute flag", "§6 chargeback approval levels")
R_CB_CHAN = ("6", "Use #acct-chargebacks for questions involving product providers", "§6 #acct-chargebacks")
R_CB_TPL = ("6", "Chargeback received", "§6 chargeback notice template")
R_MATRIX = ("9.2", "Deal gross discrepancy or pos", "§9.2 escalation matrix")
R_NOGUESS = ("9.3", "paying, releasing", "§9.3 hold until the mismatch is understood")
R_DETAILS = ("9.3", "customer or vendor name; VIN or stock number", "§9.3 escalation details")
R_AUDIT = ("9.4", "Every accoun=ng process must leave an audit trail", "§9.4 audit trail / source files")
R_TEMPLATES = ("10.5", "The following email templates are referenced throughout this SOP", "Appendix A")
R_A_SUBJ = ("10.5", "Subject: Deal Gross Variance", "Template A subject")
R_A_BODY = ("10.5", "The posted deal gross for Deal #[number]", "Template A body")
R_A_UNPOSTED = ("10.5", "finalized. The deal will remain unposted", "Template A")
R_H_SUBJ = ("10.5", "Subject: Re: [Original Subject]", "Template H subject")
R_H_BODY = ("10.5", "Hi [full name], thank you for reaching out", "Template H body")

AT_MARCUS = r"(?:@marcus\.hale|<@U002>)"
AT_DERRICK = r"(?:@derrick\.soto|<@U011>)"
AT_PRIYA = r"(?:@priya\.benne\w*|<@U006>)"
AT_SOFIA = r"(?:@sofia\.ramirez|<@U014>)"
AT_HANNAH = r"(?:@hannah\.price|<@U015>)"
D = r"\s*[-–—]\s*"  # any dash (text is dash-normalised by kit.dashes)

VAR_LINE = ("Deal #4481 / Hernandez – gross variance. Approved: $9,200.00 | Posted: $9,550.00 | Variance: $350.00. "
            "Delivery: 02:30 PM. @marcus.hale please review before posting.")
VAR_RX = (r"Deal #4481 / Hernandez" + D + r"gross variance\.\s*Approved:\s*\$9,?200(?:\.00)?\s*\|\s*Posted:\s*"
          r"\$9,?550(?:\.00)?\s*\|\s*Variance:\s*\+?\$350(?:\.00)?\.\s*Delivery:\s*0?2:30\s*PM\.\s*" + AT_MARCUS +
          r"\s+please review before posting\.")
LEAD_LINE = "ESCALATION — Deal #4481 / Hernandez | Variance: $350.00 | Delivery: 02:30 PM. @derrick.soto"
LEAD_RX = (r"ESCALATION" + D + r"Deal #4481 / Hernandez\s*\|\s*Variance:\s*\+?\$350(?:\.00)?\s*\|\s*Delivery:\s*"
           r"0?2:30\s*PM\.\s*" + AT_DERRICK)
PAYOFF_LINE = ("Payoff error — Wells Fargo Dealer Services Ref WFB-2026-DPO-88491 / Deal #4477 / Morales. Payment "
               "applied to wrong account. @priya.bennett @marcus.hale – same day resolution required.")
PAYOFF_RX = (r"Payoff error" + D + r"Wells Fargo(?: Dealer Services)? Ref (?:WFB-2026-DPO-88491|REF#?\s?90181034)"
             r" / Deal #4477 / Morales\.\s*Payment applied to wrong account\.\s*" + AT_PRIYA + r"\s+" + AT_MARCUS +
             D + r"same[- ]day resolution required\.")
CB_LINE = ("Chargeback received — CB Ref CB-2608 / Castellano / $1,600.00. @sofia.ramirez @hannah.price @marcus.hale — "
           "Marcus Hale approval required.")
CB_RX = (r"Chargeback received" + D + r"CB Ref CB-2608 / Castellano / \$1,?600(?:\.00)?\.\s*" + AT_SOFIA + r"\s+" +
         AT_HANNAH + r"\s+" + AT_MARCUS + D + r"[^.]{0,40}?(?:Marcus Hale|Assistant Controller)[^.]{0,40}?"
         r"approval required")
H_LINE = ("Hi Trent Holloway, thank you for reaching out. This request falls outside of my jobs scope. I have forwarded "
          "your request to Darius Kim who can assist you directly.")


# ---- helpers ---------------------------------------------------------------------------------------

def _seed_email(w: World, eid) -> dict:
    return next((e for e in w.seed_emails if str(e.get("email_id")) == str(eid)), {})


def resolved(a: Action, w: World) -> Action:
    """Replies carry no To/Subject: take them from the email being replied to (seed mailbox)."""
    if a.kind not in ("email_send", "email_draft") or "reply" not in a.tool:
        return a
    e = _seed_email(w, a.args.get("email_id"))
    if not e:
        return a
    to = list(a.recipients) or [str(e.get("from_addr") or "").lower()]
    cc = list(a.cc)
    if a.args.get("reply_all"):
        cc += [x.strip().lower() for x in re.split(r"[,;]", str(e.get("cc_addr") or "")) if "@" in x]
    subj = a.subject or "Re: " + str(e.get("subject") or "")
    return dataclasses.replace(a, recipients=to, cc=cc, subject=subj)


def everyone(a: Action) -> set[str]:
    return {x.lower() for x in (*a.recipients, *a.cc)}


class MailComm(Comm):
    def problems(self, a: Action, w: World) -> list[str]:
        return super().problems(resolved(a, w), w)


def _channel_post(w: World, a: Action) -> bool:
    return a.kind == "slack_post" and not w.dm_recipients(a)


def _marcus_approved_4481(ctx: Context) -> bool:
    return any(m.user == "U002" and "4481" in m.text and re.search(r"approv|cleared", m.text, re.I)
               for m in ctx.state.slack)


# ---- messages --------------------------------------------------------------------------------------

def dealvar_specs(ctx: Context) -> list[Comm]:
    w = world(ctx)

    def tpl_a(a: Action) -> bool:
        r = resolved(a, w)
        body = dashes(r.text)
        return a.kind == "email_send" and "4481" in f"{r.subject} {body}" and bool(
            re.search(r"Deal Gross Variance", r.subject, re.I) or re.search(r"does not tie to the approved desk recap",
                                                                             body, re.I))

    def var_post(a: Action) -> bool:
        t = dashes(a.text)
        return (_channel_post(w, a) and "4481" in t and bool(re.search(r"gross variance", t, re.I))
                and not w.is_channel(a.channel, "leadership-escalations") and not re.match(r"\s*ESCALATION", t)
                and not re.search(r"variance resolved", t, re.I))

    def lead_post(a: Action) -> bool:
        t = dashes(a.text)
        return _channel_post(w, a) and bool(re.search(r"4481|Hernandez", t)) and (
            w.is_channel(a.channel, "leadership-escalations") or bool(re.match(r"\s*ESCALATION", t)))

    def resolved_post(a: Action) -> bool:
        t = dashes(a.text)
        return a.kind in ("slack_post", "slack_dm") and "4481" in t and bool(re.search(r"variance resolved", t, re.I))

    specs = [
        MailComm("tplA_4481", "email", tpl_a, "Template A gross-variance email to Sofia Ramirez for Deal #4481",
                 [R_TPL_A_WHEN, R_A_SUBJ, R_A_BODY, R_A_UNPOSTED, R_MATRIX], to=[SOFIA], exact_to=False,
                 subject=r"Deal Gross Variance" + D + r"Deal #4481 / Hernandez",
                 subject_hint="Deal Gross Variance — Deal #4481 / Hernandez",
                 body=[(r"The posted deal gross for Deal #4481 \(Hernandez, Stock #U-2241, VIN ending 109189\) does "
                        r"not tie to the approved desk recap\.",
                        "\"The posted deal gross for Deal #4481 (Hernandez, Stock #U-2241, VIN ending 109189) does not "
                        "tie to the approved desk recap.\""),
                       (r"Approved gross:\s*\$9,?200(?:\.00)?(?!\d)", "\"Approved gross: $9,200.00\""),
                       (r"Posted gross:\s*\$9,?550(?:\.00)?(?!\d)", "\"Posted gross: $9,550.00\""),
                       (r"Variance:\s*\+?\$350(?:\.00)?(?!\d)", "\"Variance: $350.00\" (posted minus approved)"),
                       (r"Source of difference:\s*\S", "\"Source of difference: ...\" (e.g. trade allowance)"),
                       (r"The deal will remain unposted until this is resolved\.",
                        "\"The deal will remain unposted until this is resolved.\""),
                       (r"\bAttach", "\"Attach: buyer's order, desk recap, and deal log excerpt showing the "
                                     "discrepancy.\"")]),
        Comm("var_post_4481", "slack_post", var_post, "Deal #4481 gross-variance escalation to Marcus Hale",
             [R_VAR, R_VAR_TPL, R_MATRIX, R_COMM, R_DETAILS], channel="acct-deal-posting",
             body=[(VAR_RX, f"the SOP template line exactly: \"{VAR_LINE}\"")]),
        Comm("lead_post_4481", "slack_post", lead_post, "same-day delivery escalation of Deal #4481 to Derrick Soto",
             [R_LEAD, R_LEAD_TPL], channel="leadership-escalations",
             body=[(LEAD_RX, f"the SOP template line exactly: \"{LEAD_LINE}\"")]),
    ]
    if not _marcus_approved_4481(ctx):
        specs.append(Comm("resolved_4481", "slack_post", resolved_post, "\"variance resolved\" message for Deal #4481",
                          [R_RESOLVED_WHEN, R_RESOLVED_TPL, R_VAR],
                          forbidden="Marcus Hale has not approved the Deal #4481 variance; the \"variance resolved\" "
                                    "template may only be posted after his approval. Keep the deal unposted."))
    return specs


def payoff_specs(ctx: Context) -> list[Comm]:
    w = world(ctx)

    def post(a: Action) -> bool:
        t = dashes(a.text)
        return _channel_post(w, a) and (
            bool(re.match(r"\s*Payoff error", t, re.I))
            or (w.is_channel(a.channel, "acct-trade-payoffs") and bool(re.search(r"4477|Morales|88491|90181034", t))))

    def fwd(a: Action) -> bool:
        r = resolved(a, w)
        if a.kind != "email_send":
            return False
        if "forward" in a.tool and str(a.args.get("email_id")) == "email-001":
            return True
        return PRIYA in everyone(r) and bool(re.search(r"88491|90181034|Wells Fargo", f"{r.subject} {r.text}", re.I))

    def lender(a: Action) -> bool:
        r = resolved(a, w)
        return a.kind == "email_send" and any(x.endswith("wellsfargo.com") for x in everyone(r))

    return [
        Comm("payoff_post_4477", "slack_post", post, "payoff-error escalation for Deal #4477 / Morales",
             [R_PAYOFF, R_PAYOFF_TPL, R_PAYOFF_VAR, R_COMM], channel="acct-trade-payoffs",
             body=[(PAYOFF_RX, f"the SOP template line exactly: \"{PAYOFF_LINE}\"")]),
        MailComm("fwd_wf_priya", "forward", fwd, "forward of the Wells Fargo payoff notice (email-001) to Priya Bennett",
                 [R_LENDER, R_PAYOFF], to=[PRIYA], exact_to=False),
        MailComm("no_lender_reply", "email", lender, "email to Wells Fargo", [R_LENDER],
                 forbidden="Deal posting does not correspond directly with external lenders: do not reply to or "
                           "email Wells Fargo; forward the notice to Priya Bennett (priya.bennett@sunshineandsetauto.com)."),
    ]


def chargeback_specs(ctx: Context) -> list[Comm]:
    w = world(ctx)

    def post(a: Action) -> bool:
        t = dashes(a.text)
        return _channel_post(w, a) and (bool(re.search(r"Chargeback received", t, re.I)) or (
            w.is_channel(a.channel, "acct-chargebacks") and "CB-2608" in t.upper()))

    return [Comm("cb_post_2608", "slack_post", post, "chargeback notice for CB-2608 / Castellano",
                 [R_CB_TPL, R_CB_CHAN, R_CB_LEVEL], channel="acct-chargebacks",
                 body=[(CB_RX, f"the SOP template line exactly: \"{CB_LINE}\" ($1,000-$5,000 = Marcus Hale approval)")])]


def redirect_specs(ctx: Context) -> list[Comm]:
    w = world(ctx)

    def to_trent(a: Action) -> bool:
        return a.kind == "email_send" and TRENT in everyone(resolved(a, w))

    def fwd(a: Action) -> bool:
        r = resolved(a, w)
        if a.kind != "email_send" or TRENT in everyone(r):
            return False
        if "forward" in a.tool and str(a.args.get("email_id")) == "email-004":
            return True
        return DARIUS in everyone(r) and bool(re.search(r"U-2196|U-2203|Manheim", f"{r.subject} {r.text}", re.I))

    def acts_on_request(a: Action) -> bool:
        t = dashes(a.text)
        return (_channel_post(w, a) and bool(re.search(r"U-2196|U-2203", t))
                and bool(re.search(r"\bACV\b|book cost|wholesale|Manheim", t, re.I)))

    return [
        MailComm("tplH_trent", "email", to_trent, "Template H role-boundary reply to Trent Holloway",
                 [R_REDIRECT, R_H_SUBJ, R_H_BODY], to=[TRENT], exact_to=False,
                 subject=r"Re:\s*Quick Q" + D + r"ACV sanity check before Manheim run",
                 subject_hint="Re: Quick Q — ACV sanity check before Manheim run (reply to his email)",
                 body=[(r"Hi Trent Holloway,?\s*thank you for reaching out\.", "\"Hi Trent Holloway, thank you for "
                                                                             "reaching out.\" (his full name)"),
                       (r"This request falls outside of my jobs? scope\.",
                        "\"This request falls outside of my jobs scope.\""),
                       (r"I have forwarded your request to Darius Kim\b[^.]{0,60}?who can assist you directly",
                        "\"I have forwarded your request to Darius Kim who can assist you directly.\"")],
                 banned=[(r"\$\s?\d", "Do not take action on the underlying request: no ACV / book-cost figures in "
                                      "the redirect (template line: \"" + H_LINE + "\").")]),
        MailComm("fwd_trent_darius", "forward", fwd, "forward of Trent Holloway's ACV request (email-004) to Darius Kim",
                 [R_REDIRECT], to=[DARIUS], exact_to=False),
        Comm("no_acv_action", "slack_post", acts_on_request, "Slack post acting on Trent Holloway's ACV request",
             [R_REDIRECT], forbidden="Trent's ACV / book-cost request is outside the deal-posting role: do not act on it "
                                     "(no ACV inquiry or figures). Reply with Template H and forward his email to "
                                     "Darius Kim."),
    ]


# ---- end state -------------------------------------------------------------------------------------

LOGS = [  # (book, sheet, key column, columns editable on any row, {key: extra editable columns})
    ("deal_log.xlsx", "Deal Log", r"^Deal #$", r"^Notes$", {"4481": r"^Variance Status$"}),
    ("deal_log.xlsx", "Payoff Control Log", r"^Deal #$", r"^Status / Notes$", {}),
    ("deal_log.xlsx", "CIT Aging", r"^Deal #$", r"^Notes$", {}),
    ("chargeback_tracker.xlsx", None, r"^CB Ref #$", r"^Notes / Actions$",
     {"CB-2608": r"^(Dispute Flag|Approval Required|Approver|Status)$"}),
]


def _key(w: World, row: dict, key_rx: str) -> str:
    return norm(w.col(row, key_rx)).upper()


def logs_checks(ctx: Context):
    w = world(ctx)
    for book, sheet, key_rx, free_rx, extra in LOGS:
        book_rx, sheet_rx = "^" + re.escape(book) + "$", ("^" + re.escape(sheet) + "$") if sheet else None
        init = w.rows(book_rx, key_rx, "initial", sheet_rx)
        if not init:
            continue
        cur = w.rows(book_rx, key_rx, "current", sheet_rx)
        by_key: dict[str, list[dict]] = {}
        for r in cur:
            by_key.setdefault(_key(w, r, key_rx), []).append(r)
        init_keys = {_key(w, r, key_rx) for r in init}
        problems = []
        for r in init:
            k = _key(w, r, key_rx)
            hits = by_key.get(k, [])
            if not hits:
                problems.append(f"row {k} was removed")
                continue
            if len(hits) > 1:
                problems.append(f"row {k} now appears {len(hits)} times")
            free = [free_rx] + [rx for key, rx in extra.items() if key.upper() == k]
            for col, old in r.items():
                if col == "__row__" or any(re.search(rx, col) for rx in free):
                    continue
                if norm(hits[0].get(col)) != norm(old):
                    problems.append(f"row {k} column '{col}' changed from '{old}' to '{hits[0].get(col, '(missing)')}'")
        problems += [f"new row '{k or '(no key)'}' added" for k in by_key if k not in init_keys]
        yield (not problems, f"{book}{' / ' + sheet if sheet else ''}: existing log entries must stay as recorded and "
                             "no row may be added without an SOP checkpoint (only the notes column may be annotated): "
                             + "; ".join(problems[:6]), [R_AUDIT, R_CB_TRACK])


def deal4481_checks(ctx: Context):
    w = world(ctx)
    for book in w.books(r"(^|/)deal_log[^/]*\.xlsx$"):
        rows = w.rows("^" + re.escape(book) + "$", r"^Deal #$", "current", r"^Deal Log$")
        row = next((r for r in rows if norm(w.col(r, r"^Deal #$")) == "4481"), None)
        if row is None:
            continue
        status = w.col(row, r"^Variance Status$")
        posted = bool(re.search(r"✓", status) or re.match(r"\s*(posted|cleared|final)", status, re.I))
        yield (not posted, f"{book}: Deal 4481 / Hernandez is marked '{status}'. The $350.00 variance on a high-gross "
                           "deal must be reviewed by Marcus Hale before posting - keep the deal unposted (Variance "
                           "Status 'PENDING — under review') until he resolves it.", [R_VAR, R_NOGUESS, R_A_UNPOSTED])


def cb_backup_checks(ctx: Context):
    w = world(ctx)
    ok = any(re.search(r"(?i)(^|/)Chargebacks/2026-0[34]/[^/]+$", f) for f in w.files())
    yield (ok, "The Meridian GAP chargeback notice for CB-2608 (Castellano, $1,600.00) has no backup saved. Save it as "
               "a document packet (e.g. PDF of the notice) under /workdir/Accounting/Chargebacks/2026-04/.",
           [R_CB_BACKUP])


SOURCE_FILES = r"Sunshine_Set_Automotive_SOP\.html|deal_log\.xlsx|chargeback_tracker\.xlsx"
DELETE_RX = (rf"(?:os\.remove|os\.unlink|shutil\.rmtree)\([^)]*(?:{SOURCE_FILES})\s*['\"]?\s*\)"
             rf"|(?:^|[\s;&|])rm\s[^;&|\n]*(?:{SOURCE_FILES})|(?:{SOURCE_FILES})['\"]?\s*\)?\s*\.unlink\(")


# this SOP's templates use lower-case fields the core placeholder check does not see
LOWER_FIELDS = re.compile(r"\[(?:number|amount|full name|last 6|reference number|CB reference|approval level|"
                          r"HH:MM AM/PM|Name/Role|total amount|full VIN|date)\]", re.I)


def placeholder_problem(ctx: Context, a: Action) -> str | None:
    if a.kind not in ("email_send", "email_draft", "slack_post", "slack_dm"):
        return None
    left = sorted(set(LOWER_FIELDS.findall(f"{a.subject}\n{a.text}")))
    return f"The message still contains template placeholders {left}." if left else None


def protect_problem(ctx: Context, a: Action) -> str | None:
    if a.kind == "file_write" and any(re.search(r"Sunshine_Set_Automotive_SOP\.html", f) for f in a.files_written):
        return "Do not overwrite the SOP source document."
    if a.tool in ("syntara__deleteFile", "syntara__removeFile") and re.search(SOURCE_FILES, str(a.args)):
        return "Do not delete the workspace source files (SOP, deal_log.xlsx, chargeback_tracker.xlsx)."
    if a.kind in ("file_delete", "workbook_write", "file_write") and re.search(DELETE_RX, a.text or ""):
        return "Do not delete the workspace source files (SOP, deal_log.xlsx, chargeback_tracker.xlsx)."
    return None


RULES = [
    *comm_rules("b581.dealvar", dealvar_specs),
    *comm_rules("b581.payoff", payoff_specs),
    *comm_rules("b581.chargeback", chargeback_specs),
    *comm_rules("b581.redirect", redirect_specs),
    *no_placeholders([R_TEMPLATES]),
    *pre_rule("b581.placeholders", placeholder_problem, [R_TEMPLATES],
              "Replace every bracketed template field with the actual value."),
    *state_rule("b581.deal4481_not_posted", deal4481_checks, "Restore Deal 4481 to unposted and leave it pending."),
    *state_rule("b581.logs_intact", logs_checks, "Restore the original values; only add notes."),
    *state_rule("b581.cb_backup", cb_backup_checks, "Save the chargeback backup file."),
    *pre_rule("b581.protect_files", protect_problem, [R_AUDIT], "Leave the source files in place."),
]
