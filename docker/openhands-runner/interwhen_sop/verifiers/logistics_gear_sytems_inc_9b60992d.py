"""Verifiers for task logistics_gear_sytems_inc_9b60992d (concealed damage reported after receipt).

Rebuilt from the task's SOP, instruction and environment only:
  * 11.7 / 11.7.1 - Tier 4 window (10 business days from receipt), step order: locate the receipt (2),
    window check (3), Template 31 request to the reporter (4), and only "once received" the -T4 row,
    quarantine, NCR/Template 7 and carrier notice (5-10)
  * Template 31 - used as written; list items that do not apply are deleted
  * instruction - internal communication with the reporter by email; nothing beyond the reported issue
Case facts (report, receipt, dates, reporter) are computed in Python from Slack, mail and workbooks.
"""

from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from dataclasses import dataclass
from functools import cached_property

from .. import common, templates
from ..actions import Action
from ..framework import Context, Finding, Rule, registry
from ..gear import World, norm

TASK_RULES: list[Rule] = []
rule = registry(TASK_RULES)

REC = re.compile(r"REC-\d{8}-\d{3}")
IDS = re.compile(r"REC-\d{8}-\d{3}(?:-T4)?|NCR-[A-Z0-9-]*\d{3,4}|MER-PO-[A-Z0-9-]+|APPT-\d{8}-\d{3}")
DAMAGE = re.compile(r"damage|dent|crack|broken|deform|impact", re.I)
PLANT_TZ = dt.timezone(dt.timedelta(hours=-5))


@dataclass
class Case:
    receipt: str
    reporter: str
    reporter_email: str
    reporter_first: str
    report_text: str
    report_date: dt.date
    row: dict
    receipt_date: dt.date
    business_days: int
    sku: str
    po: str
    via_reinspection: bool


def _date(s: str) -> dt.date | None:
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})|(\d{2})/(\d{2})/(\d{4})", str(s))
    if not m:
        return None
    if m.group(1):
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return dt.date(int(m.group(6)), int(m.group(4)), int(m.group(5)))


class Facts(World):
    @cached_property
    def slack_msgs(self) -> list[tuple[str, str, float]]:
        out = [(m.user, m.text, m.ts) for m in self.state.slack]
        for ms in (self._slack_seed.get("messages") or {}).values():
            out += [(m.get("user", ""), m.get("text", ""), float(m.get("ts", 0))) for m in ms]
        return out

    @cached_property
    def receiving(self) -> list[dict]:
        return self.rows("receiving_log.xlsx", "Receipt_ID", "initial")

    @cached_property
    def initials(self) -> str:
        c = Counter(r.get("Coordinator_Initials") for r in self.receiving if r.get("Coordinator_Initials"))
        return c.most_common(1)[0][0] if c else ""

    @cached_property
    def case(self) -> Case | None:
        """Step 1: a damage report on an already-completed receipt, posted by someone other than the Coordinator."""
        for user, text, ts in sorted(self.slack_msgs, key=lambda x: -x[2]):
            ids = REC.findall(text)
            if not ids or not DAMAGE.search(text) or user in self.self_uids:
                continue
            row = next((r for r in self.receiving if r.get("Receipt_ID") == ids[0]), None)
            rdate = _date((row or {}).get("Arrival_Timestamp", ""))
            today = dt.datetime.fromtimestamp(ts, PLANT_TZ).date()
            if not row or not rdate or rdate >= today:
                continue
            name = self.users.get(user, {}).get("name") or ""
            contact = self.ctx.sop.contact_by_name(name) if name else None
            return Case(ids[0], name, (contact.email if contact else "").lower(), name.split()[0] if name else "",
                        text, today, row, rdate, self.ctx.sop.business_days_between(rdate, today),
                        row.get("SKU", ""), row.get("PO_Number", ""), bool(re.search(r"re-?inspection", text, re.I)))
        return None

    def case_ids(self) -> set[str]:
        c = self.case
        return {c.receipt, f"{c.receipt}-T4", c.po} if c else set()

    def request_sent(self) -> list:
        c = self.case
        return [e for e in self.state.sent_emails() if c and c.reporter_email in e.action.recipients
                and c.receipt in f"{e.action.subject} {e.action.text}"]

    def evidence(self) -> bool:
        """Step 5 'Once received': a reply from the reporter about the receipt after the request."""
        c = self.case
        if not c or not self.request_sent():
            return False
        return any(e.sender == c.reporter_email and c.receipt in f"{e.subject} {e.body}" for e in self.state.emails)


def facts(ctx: Context) -> Facts:
    return ctx.memo("f9b6", lambda: Facts(ctx))


def _blob(a: Action) -> str:
    return f"{a.subject}\n{a.text}\n{a.code}"


def _touches_case(f: Facts, a: Action) -> bool:
    c = f.case
    return bool(c) and (c.receipt in _blob(a) or bool(c.sku) and c.sku in _blob(a))


def _t31(f: Facts, ctx: Context, subject: str, body: str) -> templates.TemplateCheck:
    c = f.case
    tpl = ctx.sop.template(31)["body"]
    wanted = ["• Photos", "• Written description", "• Receiving log amendment", "• Discrepancy reported in #receiving-dock"]
    if c.via_reinspection:
        wanted.append("• Re-inspection completed today")
    req = [b for b in tpl if any(b.startswith(w) for w in wanted)]
    return templates.check(ctx.sop, 31, subject, body, fill={"[ID]": c.receipt.removeprefix("REC-")},
                           required_bullets=req, first_name=c.reporter_first,
                           initials_rule=(f.initials or None, "the Coordinator's initials in receiving_log.xlsx"))


@rule("tier4.locate_receipt_first", "pre", [("11.7.1", "2. The Coordinator opens receiving_log.xlsx")])
def locate_first(ctx: Context, action: Action) -> list[Finding]:
    if action.kind in ("read", "control"):
        return []
    f = facts(ctx)
    if not f.case or not _touches_case(f, action) or f.read_mentions("receiving_log"):
        return []
    return [Finding("tier4.locate_receipt_first", [ctx.cite("11.7.1", "2. The Coordinator opens receiving_log.xlsx",
                                                            "11.7.1 step 2")],
                    f"Before acting on {f.case.receipt}, open receiving_log.xlsx, locate the original receipt and "
                    "confirm its receipt date.", ["Read receiving_log.xlsx first."])]


@rule("tier4.window", "pre", [("11.7.1", "3. Calculate the number of business days")])
def window(ctx: Context, action: Action) -> list[Finding]:
    f = facts(ctx)
    c = f.case
    if not c or action.kind not in ("email_send", "slack_post", "slack_dm") or not _touches_case(f, action):
        return []
    says_outside = bool(re.search(r"outside the 10-business-day", action.text, re.I))
    if c.business_days <= 10 and says_outside:
        problem = (f"{c.receipt} was received {c.receipt_date:%m/%d/%Y}, {c.business_days} business days ago - inside "
                   "the 10-business-day concealed damage window.")
    elif c.business_days > 10 and not says_outside and action.kind == "email_send":
        problem = (f"{c.receipt} is {c.business_days} business days old - outside the window; reply to the reporter "
                   "with the exact Section 11.7.1 step 3 wording.")
    else:
        return []
    return [Finding("tier4.window", [ctx.cite("11.7.1", "3. Calculate the number of business days", "11.7.1 step 3")],
                    problem, ["Apply the step that matches the window."])]


@rule("tier4.request_uses_template31", "pre", [("11.7.1", "4. If within the window, request photos")])
def request(ctx: Context, action: Action) -> list[Finding]:
    f = facts(ctx)
    c = f.case
    if not c or action.kind != "email_send" or c.reporter_email not in action.recipients or c.business_days > 10:
        return []
    if f.evidence():
        return []
    res = _t31(f, ctx, action.subject, action.text)
    if res.ok:
        return []
    shown = "\n".join(res.expected_body)
    return [Finding("tier4.request_uses_template31", [
        ctx.cite("11.7.1", "4. If within the window, request photos", "11.7.1 step 4"),
        "SOP Template 31 (General Internal Request): \"Delete all list line items that do not apply.\""],
        "The information request does not follow Template 31 as written: " + " ".join(res.problems),
        [f"Send exactly:\nSubject: {res.expected_subject}\n{shown}"])]


@rule("instruction.reporter_by_email", "pre", [], source="task_instruction")
def by_email(ctx: Context, action: Action) -> list[Finding]:
    f = facts(ctx)
    c = f.case
    if not c or action.kind not in ("slack_post", "slack_dm"):
        return []
    handles = {(f.users.get(u, {}).get("handle") or "").lower() for u in f.uids(c.reporter)} - {""}
    contact = ctx.sop.contact_by_name(c.reporter)
    if contact and contact.handle:
        handles.add(contact.handle.lower())
    text = action.text.lower()
    to_reporter = f.is_dm_to(action, c.reporter) or any(f"@{h}" in text for h in handles) or bool(
        re.search(rf"\b{re.escape(c.reporter_first.lower())}\b", text))
    if not to_reporter:
        return []
    return [Finding("instruction.reporter_by_email", [f"Task instruction: \"Any necessary internal communications with "
                                                      f"{c.reporter_first} should be done through email.\""],
                    f"This Slack message addresses {c.reporter}; the user requires email for that.",
                    [f"Email {c.reporter_email} instead."])]


@rule("tier4.wait_for_evidence", "pre", [("11.7.1", "5. Once received, create a new row")])
def wait(ctx: Context, action: Action) -> list[Finding]:
    f = facts(ctx)
    c = f.case
    if not c or action.kind in ("read", "control") or f.evidence():
        return []
    blob = _blob(action)
    step = None
    if action.kind == "workbook_write" and "receiving_log.xlsx" in action.files_written and (
            c.receipt in blob or "-T4" in blob):
        step = "5-6 (the -T4 receiving-log row)"
    elif action.kind == "workbook_write" and "inventory_master.xlsx" in action.files_written and c.sku in blob:
        step = "7 (quarantine)"
    elif action.kind == "workbook_write" and "ncr_log.xlsx" in action.files_written:
        step = "8 (NCR)"
    elif action.kind == "email_send" and c.reporter_email not in action.recipients and _touches_case(f, action):
        step = "8/10 (supplier NCR notice / carrier notice)"
    elif action.kind in ("slack_post", "slack_dm") and _touches_case(f, action) and re.search(
            r"quarantin|q-hold|ncr|claim", blob, re.I):
        step = "7-10"
    elif action.kind in ("calendar_create", "calendar_update") and _touches_case(f, action):
        step = "7 (quarantine re-inspection event)"
    if not step:
        return []
    return [Finding("tier4.wait_for_evidence", [
        ctx.cite("11.7.1", "5. Once received, create a new row", "11.7.1 step 5")],
        f"Blocked step {step} for the concealed-damage case on {c.receipt}: steps 5-10 start only 'Once received' - "
        f"after {c.reporter} has replied with the photos and description requested via Template 31.",
        ["Send the Template 31 request by email and wait for the reply; the user will take over from there."])]


@rule("instruction.scope", "pre", [], source="task_instruction")
def scope(ctx: Context, action: Action) -> list[Finding]:
    f = facts(ctx)
    c = f.case
    if not c or action.kind in ("read", "control"):
        return []
    others = sorted(set(IDS.findall(_blob(action))) - f.case_ids())
    if not others:
        return []
    return [Finding("instruction.scope", [f"Task instruction: \"Don't handle anything else beyond the issue reported by "
                                          f"{c.reporter_first}.\""],
                    f"This call acts on {', '.join(others[:4])}, which are not part of the {c.receipt} damage report.",
                    ["Leave other receipts, NCRs and POs to the user."])]


@rule("tier4.completion", "completion", [("11.7.1", "4. If within the window, request photos")])
def completion(ctx: Context) -> list[Finding]:
    f = facts(ctx)
    c = f.case
    if not c:
        return []
    probs = []
    if c.business_days <= 10:
        if not any(_t31(f, ctx, e.action.subject, e.action.text).ok for e in f.request_sent()):
            probs.append(f"No Template 31 information request has been emailed to {c.reporter} ({c.reporter_email}) for "
                         f"{c.receipt} ({c.business_days} business days after receipt, inside the window).")
        if f.evidence():
            rows = [r for r in f.rows("receiving_log.xlsx", "Receipt_ID") if r.get("Receipt_ID") == f"{c.receipt}-T4"]
            if not rows:
                probs.append(f"Evidence received: add the {c.receipt}-T4 receiving-log row (steps 5-6).")
            elif norm(rows[0].get("Condition_Tier")) not in ("tier 4", "4"):
                probs.append("The -T4 row needs Condition_Tier = Tier 4 (step 6).")
    if not probs:
        return []
    return [Finding("tier4.completion", [ctx.cite("11.7.1", "4. If within the window, request photos", "11.7.1 step 4")],
                    " ".join(probs), ["Use Template 31 by email to the reporter."])]


RULES = common.RULES + TASK_RULES
