"""Paragraph-level SOP verifiers compiled automatically from each task's own sop.json.

Every SOP paragraph that prescribes an exact message (Slack post, direct message, email template)
is compiled into a format check; the column-value tables (8.1, 10.7, 11.8, 12.8, 12.9, 13.1), the
inventory rules (13.2, 13.3) and the Critical Prohibitions (21) become record checks. Checks are pure
Python; nothing here reads graders.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from .actions import Action
from .framework import Context, Finding, Rule, registry
from .gear import World, blank, norm, num
from .sopdata import SOP

RULES: list[Rule] = []
rule = registry(RULES)

PH = re.compile(r"\[[^\[\]]{1,80}\]")
DM_LEAD = re.compile(r"(?:Direct-message|direct message|DM)\s+(?P<who>[^:]{2,160}?)(?:\s+(?:on Slack|simultaneously|"
                     r"with the format|via direct message))*\s*:\s*(?P<fmt>.+)$", re.I)
POST_LEAD = re.compile(r"(?:post(?:s|ed)?|Slack post)\s+(?:in|to)\s+#\s?(?P<chan>[\w-]+)[^:]{0,120}:\s*(?P<fmt>.+)$", re.I)
CAPS_HEAD = re.compile(r"^[a-z]?(?P<fmt>[A-Z][A-Z0-9 \-—/&]{3,}:\s.*)$")
MAX_FORMAT_DENIALS = 2


def _strip(s: str) -> str:
    s = str(s or "").replace("\u2014", "-").replace("\u2013", "-").replace("\u2192", "->")
    s = s.replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", "", s).lower()


@dataclass
class MsgFormat:
    pid: str
    section: str
    raw: str
    chunks: list[str]                 # whitespace-free literal chunks between placeholders
    channel: str | None = None
    recipients: list[str] = field(default_factory=list)

    @property
    def head(self) -> str:
        return self.chunks[0]

    def regex(self) -> re.Pattern:
        return re.compile(".+?".join(re.escape(c) for c in self.chunks), re.S)


@dataclass
class EmailTpl:
    number: str
    title: str
    subject_chunks: list[str]
    body_lines: list[list[str]]       # each substantive line as whitespace-free literal chunks
    pids: list[str]


class Compiled:
    def __init__(self, sop: SOP):
        self.sop = sop
        words = Counter(w.lower() for p in sop.paragraphs for w in re.findall(r"[A-Za-z]{2,}", p["text"]))
        self.vocab = words
        self.formats = self._formats()
        self.templates = self._templates()

    def _clean_chunks(self, text: str) -> list[str]:
        """Literal chunks of a format; a chunk is cut at the first glyph-damaged token (not SOP vocabulary)."""
        out = []
        parts = PH.split(text)
        for i, part in enumerate(parts):
            keep = []
            for tok in re.split(r"(\s+)", part):
                words = re.findall(r"[A-Za-z]{4,}", tok)
                if any(self.vocab.get(w.lower(), 0) < 2 for w in words) or re.search(r"[a-z]\d[a-z]", tok):
                    break
                keep.append(tok)
            else:
                out.append(_strip(part))
                continue
            out.append(_strip("".join(keep)))
            break  # text after damaged glyphs is unreliable
        while out and not out[-1]:
            out.pop()
        return out if out and len(re.sub(r"[^a-z]", "", out[0])) >= 6 else []

    def _who(self, text: str) -> list[str]:
        return [c.name for c in self.sop.contacts if c.name and c.name.split()[0] in text]

    def _formats(self) -> list[MsgFormat]:
        paras = self.sop.paragraphs
        out: list[MsgFormat] = []
        for i, p in enumerate(paras):
            sec = p["section"]
            if sec.startswith(("0", "1.", "2", "3", "22")) or p["kind"] == "heading":
                continue
            text = p["text"]
            m = DM_LEAD.search(text)
            channel, who, fmt = None, [], None
            if m and PH.search(m.group("fmt") or ""):
                who, fmt = self._who(m.group("who")), m.group("fmt")
            else:
                m = POST_LEAD.search(text)
                if m and PH.search(m.group("fmt")):
                    channel, fmt = m.group("chan"), m.group("fmt")
                else:
                    m = CAPS_HEAD.match(text)
                    if m and PH.search(text) and not sec.startswith("23"):
                        fmt = m.group("fmt")
                        for back in paras[max(0, i - 2):i][::-1]:
                            c = re.search(r"#\s?([\w-]{4,})", back["text"])
                            d = re.search(r"Direct-message|direct message", back["text"], re.I)
                            if c:
                                channel = c.group(1)
                                break
                            if d:
                                who = self._who(back["text"])
                                break
            if not fmt:
                continue
            nxt = paras[i + 1] if i + 1 < len(paras) else None
            if nxt and nxt["section"] == sec and nxt["kind"] == "text" and not CAPS_HEAD.match(nxt["text"]) and (
                    nxt["text"][:1].islower() or (PH.search(nxt["text"]) and len(nxt["text"]) < 160)):
                fmt = f"{fmt} {nxt['text']}"
            # Glyph scrambling sometimes moves one letter of the channel name in front of the format.
            fmt = re.sub(r"^[a-z](?=[A-Z]{2})", "", fmt.strip())
            chunks = self._clean_chunks(fmt)
            if chunks:
                out.append(MsgFormat(p["id"], sec, fmt, chunks, channel, who))
        return out

    def _templates(self) -> list[EmailTpl]:
        out = []
        for num_, t in self.sop.templates.items():
            if not t.get("subject"):
                continue
            subj = self._clean_chunks(t["subject"])
            if not subj:
                continue
            lines = []
            for ln in t["body"]:
                if ln.startswith(("•", "-", "[")) or len(_strip(PH.sub("", ln))) < 15:
                    continue
                ch = [c for c in (_strip(x) for x in PH.split(ln)) if len(c) >= 6]
                if ch:
                    lines.append(ch)
            out.append(EmailTpl(num_, t["title"], subj, lines, t.get("paragraph_ids", [])))
        return out


_CACHE: dict[int, Compiled] = {}


def compiled(ctx: Context) -> Compiled:
    key = id(ctx.sop)
    if key not in _CACHE:
        _CACHE[key] = Compiled(ctx.sop)
    return _CACHE[key]


def _channel_matches(w: World, action_channel: str, sop_channel: str) -> bool:
    got = norm(w.channel_name(action_channel)).lstrip("#")
    want = sop_channel.lower().strip("-")
    return bool(got) and (got.startswith(want[:10]) or want.startswith(got[:10]))


def _prior_denials(ctx: Context, tag: str) -> int:
    return sum(tag in str(r.get("text", "")) for r in ctx.state.rejected)


@rule("generic.message_format", "pre", [])
def message_format(ctx: Context, action: Action) -> list[Finding]:
    if action.kind not in ("slack_post", "slack_dm"):
        return []
    c = compiled(ctx)
    body = _strip(action.text)
    cands = [f for f in c.formats if body.startswith(f.head)]
    if not cands:
        return []
    tag = f"[fmt:{cands[0].pid}]"
    if _prior_denials(ctx, tag) >= MAX_FORMAT_DENIALS:
        return []
    if any(f.regex().match(body) for f in cands):
        good = [f for f in cands if f.regex().match(body)]
        w = World(ctx)
        f = good[0]
        if f.channel and action.kind == "slack_post" and not w.dm_recipients(action) and not _channel_matches(
                w, action.channel, f.channel):
            return [Finding("generic.message_format", [ctx.cite(f.section, ctx.sop.by_id[f.pid]["text"][:40], f.section)],
                            f"{tag} This message format belongs in #{f.channel} (SOP {f.section}).",
                            [f"Post it in #{f.channel}."])]
        return []
    shown = " | ".join(f"SOP {f.section}: \"{f.raw[:220]}\"" for f in cands[:2])
    return [Finding("generic.message_format", [ctx.cite(cands[0].section, ctx.sop.by_id[cands[0].pid]["text"][:40],
                                                        cands[0].section)],
                    f"{tag} This message starts like an SOP-prescribed format but does not follow it word for word. "
                    f"Expected: {shown}",
                    ["Fill every [placeholder] and keep all other wording exactly as the SOP gives it."])]


@rule("generic.email_template", "pre", [])
def email_template(ctx: Context, action: Action) -> list[Finding]:
    if action.kind != "email_send":
        return []
    c = compiled(ctx)
    subj = _strip(action.subject)
    body = _strip(action.text)
    for t in c.templates:
        if not subj.startswith(t.subject_chunks[0]):
            continue
        tag = f"[tpl:{t.number}]"
        if _prior_denials(ctx, tag) >= MAX_FORMAT_DENIALS:
            return []
        probs = []
        if not re.match(".+?".join(re.escape(x) for x in t.subject_chunks), subj):
            probs.append(f"Subject must follow Template {t.number}: \"{ctx.sop.template(int(t.number))['subject']}\".")
        missing = [ln for ln in t.body_lines if not re.search(".+?".join(re.escape(x) for x in ln), body, re.S)]
        if t.body_lines and len(missing) > 0.3 * len(t.body_lines):
            probs.append(f"The body leaves out {len(missing)} of {len(t.body_lines)} fixed lines of Template "
                         f"{t.number} ({t.title}); use the template text as written.")
        if probs:
            return [Finding("generic.email_template", [f"SOP Template {t.number} ({t.title}), Section 23"],
                            f"{tag} " + " ".join(probs), ["Rewrite the email from the template, filling placeholders."])]
        return []
    return []


@rule("generic.slack_history_immutable", "pre", [("21.3", "13. Do not delete or move a Slack post")])
def slack_history(ctx: Context, action: Action) -> list[Finding]:
    if not re.search(r"slack__(delete|update|edit|remove)", action.tool):
        return []
    return [Finding("generic.slack_history_immutable", [ctx.cite("21.3", "13. Do not delete or move a Slack post",
                                                                 "21.3 item 13")],
                    "Slack posts are part of the audit trail and are never deleted or edited.",
                    ["Post a correction reply instead."])]


PROMISE = re.compile(r"\b(we will|we'll|we are going to|gear systems will)\b[^.]{0,80}\b(credit|refund|accept(?:ing)? the|"
                     r"replacement|return authori[sz]ation|rework|price|pricing)", re.I)


@rule("generic.no_supplier_promises", "pre", [("21.3", "14. Do not promise a supplier")])
def no_promises(ctx: Context, action: Action) -> list[Finding]:
    if action.kind != "email_send":
        return []
    external = [r for r in action.recipients + action.cc if not r.endswith("@gearsystems.com")]
    if not external or not PROMISE.search(action.text):
        return []
    return [Finding("generic.no_supplier_promises", [ctx.cite("21.3", "14. Do not promise a supplier", "21.3 item 14")],
                    f"The email to {', '.join(external)} promises a resolution (\"{PROMISE.search(action.text).group(0)}\"); "
                    "resolution is Procurement's or Quality's call.", ["Document and escalate; do not commit to an outcome."])]


# ---- record checks -------------------------------------------------------------------------------

DOMAINS = {   # SOP 10.7, 11.8, 12.8, 12.9 column tables
    "Variance_Band": ["Exact", "Band 1", "Band 2", "Band 3", "Over A", "Over B", "Over C"],
    "Quantity_Action": ["Accepted", "Accepted with NCR", "Quarantined", "Excess Staged", "Refused"],
    "Condition_Tier": ["Tier 0", "Tier 1", "Tier 2", "Tier 3", "Tier 4"],
    "Condition_Action": ["Accepted", "Accepted with notation", "Quarantined", "Quarantined - awaiting Quality",
                         "Refused", "Quarantined - concealed damage"],
    "Documentation_Status": ["Verified", "Missing - packing slip requested", "Missing - BOL requested",
                             "Quarantine - missing COC", "Quarantine - missing MTR",
                             "Quarantine - heat number mismatch", "Quarantine - documentation hold"],
    "Documentation_Action": ["Accepted", "Accepted with follow-up", "Quarantined", "Quarantined - safety-critical hold"],
    "Disposition": ["REFUSED", "QUARANTINE - full receipt", "QUARANTINE - line", "ACCEPTED WITH NCR",
                    "ACCEPTED WITH NOTATION", "ACCEPTED CLEAN", "REFUSED AT DOCK"],
}
POSTED_REQUIRED = ["Receipt_ID", "PO_Number", "PO_Line", "SKU", "Safety_Critical", "Supplier_ID", "Carrier_Name",
                   "Arrival_Timestamp", "Disposition_Timestamp", "Dock_Door", "Qty_Ordered", "Qty_Claimed_On_Slip",
                   "Qty_Received", "Variance_Units", "Variance_Pct", "Variance_Band", "Quantity_Action",
                   "Condition_Tier", "Condition_Action", "Photos_Folder", "Documentation_Status",
                   "Documentation_Action", "Disposition", "Coordinator_Initials", "Notes", "Status"]


def _band(var: float, pct: float) -> str:
    if abs(var) <= 1 or abs(pct) <= 0.5:
        return "Exact"
    if var < 0:
        return "Band 1" if -pct <= 5 else "Band 2" if -pct <= 15 else "Band 3"
    return "Over A" if pct <= 2 else "Over B" if pct <= 10 else "Over C"


def _key(r: dict) -> tuple:
    return (r.get("Receipt_ID"), r.get("PO_Line"), r.get("SKU"))


def receiving_problems(w: World) -> list[str]:
    init = w.rows("receiving_log.xlsx", "Receipt_ID", "initial")
    now = w.rows("receiving_log.xlsx", "Receipt_ID")
    before = {_key(r): r for r in init}
    seen = {c: {norm(r.get(c)) for r in init if not blank(r.get(c))} for c in DOMAINS}
    out = []
    for r in now:
        b = before.get(_key(r))
        posted_now = norm(r.get("Status")) == "posted" and (b is None or norm(b.get("Status")) != "posted")
        if b is not None and not posted_now:
            continue
        rid = f"{r.get('Receipt_ID')} line {r.get('PO_Line') or '-'}"
        for col, dom in DOMAINS.items():
            v = r.get(col)
            if col in r and not blank(v) and norm(v) not in {norm(x) for x in dom} | seen.get(col, set()):
                out.append(f"{rid}: {col} '{v}' is not an SOP value ({', '.join(dom)}).")
        q, o = num(r.get("Qty_Received")), num(r.get("Qty_Ordered"))
        if q is not None and o:
            var, pct = q - o, (q - o) / o * 100
            if "Variance_Units" in r and not blank(r.get("Variance_Units")) and num(r.get("Variance_Units")) != var:
                out.append(f"{rid}: Variance_Units must be Qty_Received − Qty_Ordered = {var:g} (10.2).")
            vp = num(r.get("Variance_Pct"))
            if "Variance_Pct" in r and not blank(r.get("Variance_Pct")):
                if vp is not None and abs(vp) <= 1 and abs(pct) > 1.5:
                    vp *= 100
                if vp is None or abs(vp - round(pct, 1)) > 0.051:
                    out.append(f"{rid}: Variance_Pct must be {pct:+.1f}% (signed, one decimal; 10.2/10.7).")
            if "Variance_Band" in r and not blank(r.get("Variance_Band")) and norm(r["Variance_Band"]) != norm(_band(var, pct)):
                out.append(f"{rid}: Variance_Band must be {_band(var, pct)} for {var:+g} units ({pct:+.1f}%) (10.3-10.5).")
        disp = norm(r.get("Disposition"))
        if disp == "accepted clean":
            axes = [norm(r.get(c)) for c in ("Variance_Band", "Condition_Tier", "Documentation_Status") if c in r]
            if any(a and a not in ("exact", "tier 0", "verified") for a in axes):
                out.append(f"{rid}: ACCEPTED CLEAN requires Exact / Tier 0 / Verified on all three axes (12.9).")
        if posted_now:
            missing = [c for c in POSTED_REQUIRED if c in r and blank(r.get(c))]
            if missing:
                out.append(f"{rid}: posted with blank required column(s) {', '.join(missing)} (13.1).")
            if str(r.get("Safety_Critical", "")).upper() == "Y" and disp.startswith("accepted"):
                if "Heat_Numbers" in r and blank(r.get("Heat_Numbers")):
                    out.append(f"{rid}: safety-critical putaway needs verified heat numbers (21.1 item 2).")
                if "packingslip" in _strip(r.get("COC_Filename")) or "packing_slip" in _strip(r.get("COC_Filename")):
                    out.append(f"{rid}: a packing slip is not a COC (21.2 item 10).")
        if b is None and r.get("PO_Number"):
            pos = {p.get("PO_Number") for p in w.rows("open_pos.xlsx", "PO_Number", "initial")}
            base = re.sub(r"-T4|-C\d+$", "", str(r.get("Receipt_ID", "")))
            original = any(x.get("Receipt_ID") == base for x in init)
            if pos and r["PO_Number"] not in pos and not original and not disp.startswith("refused"):
                out.append(f"{rid}: PO {r['PO_Number']} is not in open_pos.xlsx; material is never received against an "
                           "unknown PO (21.1 item 1).")
    return out


def _is_qhold(r: dict) -> bool:
    loc = " ".join(str(r.get(k, "")) for k in ("Location", "Warehouse_Location", "Warehouse_Zone", "Zone", "Status"))
    return bool(re.search(r"q-?hold|quarantin", loc, re.I)) or str(r.get("Quarantine_Flag", "")).upper() == "Y"


def _qty(r: dict) -> float:
    for k in ("On_Hand_Qty", "Qty_On_Hand", "Quarantine_Qty"):
        if num(r.get(k)) is not None:
            return num(r.get(k)) or 0.0
    return 0.0


def _release_authorized(w: World, sku: str) -> bool:
    """A written release naming the SKU from Quality, Receiving Supervisor or Procurement (14.7.1)."""
    owners = {c.email.lower() for c in w.ctx.sop.contacts if re.search(r"quality manager|receiving supervisor|"
                                                                       r"procurement", c.role, re.I)}
    mails = [(str(e.get("from_addr", "")).lower(), f"{e.get('subject', '')} {e.get('body_text', '')}") for e in w.seed_emails]
    mails += [(e.sender, f"{e.subject} {e.body}") for e in w.state.emails]
    return any(s in owners and sku in t and re.search(r"releas", t, re.I) for s, t in mails)


def inventory_problems(w: World) -> list[str]:
    init = w.rows("inventory_master.xlsx", "SKU", "initial")
    now = w.rows("inventory_master.xlsx", "SKU")
    loc_key = next((k for k in ("Location", "Warehouse_Location", "Bin") if init and k in init[0]), None)

    def key(r):
        return (r.get("SKU"), r.get(loc_key) if loc_key else None, _is_qhold(r))
    before = {key(r): r for r in init}
    after = {key(r): r for r in now}
    out = []
    for k, r in after.items():
        if k not in before and not k[2] and r.get("SKU"):
            out.append(f"New inventory_master row for {r.get('SKU')} at {k[1]}: the Coordinator only creates Q-HOLD rows; "
                       "new SKUs go to Maribel Ortiz via Template 18 (13.2, 13.3).")
        if k[2] and (k not in before or _qty(r) > _qty(before[k])):
            for col in ("Quarantine_Reason", "Quarantine_Receipt_ID", "Quarantine_Date"):
                if col in r and blank(r.get(col)):
                    out.append(f"Q-HOLD row for {r.get('SKU')}: populate {col} (13.3 steps 5-7).")
        b = before.get(k)
        if b and not k[2] and "Heat_Numbers_On_Hand" in r:
            old = {h.strip() for h in str(b.get("Heat_Numbers_On_Hand", "")).split(",") if h.strip()}
            new = {h.strip() for h in str(r.get("Heat_Numbers_On_Hand", "")).split(",") if h.strip()}
            if old - new:
                out.append(f"{r.get('SKU')}: heat numbers {', '.join(sorted(old - new))} were removed; "
                           "Heat_Numbers_On_Hand is append-only (13.2 step 6).")
    for k, b in before.items():
        if k[2] and (k not in after or _qty(after[k]) < _qty(b)) and not _release_authorized(w, b.get("SKU", "")):
            out.append(f"Material for {b.get('SKU')} left quarantine without a documented written release "
                       "(14.7.1, 21.4 item 20).")
    return out


DOCK_STATUS = ["Scheduled", "Arrived", "Unloading", "Complete", "Refused", "No-Show", "Holding overnight",
               "Released - late, no unload"]


def dock_problems(w: World) -> list[str]:
    init = w.rows("dock_schedule.xlsx", "Appointment_ID", "initial")
    seen = {norm(r.get("Status")) for r in init} | {norm(s) for s in DOCK_STATUS}
    out = []
    for b, a in w.changed_rows("dock_schedule.xlsx", "Appointment_ID", lambda r: True):
        if a and not blank(a.get("Status")) and norm(a.get("Status")) not in seen:
            out.append(f"dock_schedule {a.get('Appointment_ID')}: Status '{a.get('Status')}' is not an SOP status "
                       f"({', '.join(DOCK_STATUS)}) (8.1).")
        t = str((a or {}).get("Actual_Arrival_Time", "")).strip()
        if a and t and t != str((b or {}).get("Actual_Arrival_Time", "")).strip() and not re.match(r"^\d{2}:\d{2}", t):
            out.append(f"dock_schedule {a.get('Appointment_ID')}: Actual_Arrival_Time must be HH:MM CST (8.1).")
    return out


def ncr_problems(w: World) -> list[str]:
    out = []
    closers = {c.email.lower() for c in w.ctx.sop.contacts if re.search(r"quality manager|procurement", c.role, re.I)}
    texts = [(str(e.get("from_addr", "")).lower(), f"{e.get('subject', '')} {e.get('body_text', '')}") for e in w.seed_emails]
    texts += [(e.sender, f"{e.subject} {e.body}") for e in w.state.emails]
    for b, a in w.changed_rows("ncr_log.xlsx", "NCR_Number", lambda r: True):
        if not a or not b:
            continue
        if re.match(r"(resolved|closed)", norm(a.get("Status"))) and not re.match(r"(resolved|closed)", norm(b.get("Status"))):
            n = a.get("NCR_Number", "")
            if not any(s in closers and n in t and re.search(r"clos|resolv", t, re.I) for s, t in texts):
                out.append(f"{n} was set to '{a.get('Status')}' without a closure decision from Theo Brandt / Joon-ho "
                           "Park; the Coordinator never closes NCRs on their own judgment (14.8).")
    return out


@rule("generic.records", "completion", [("12.9", "After Sections 10, 11, and 12"), ("13.1", "Before posting"),
                                        ("13.3", "For any line whose Disposition is a quarantine"),
                                        ("14.8", "The Coordinator does not unilaterally close NCRs")])
def records(ctx: Context) -> list[Finding]:
    w = World(ctx)
    probs = []
    for fn in (receiving_problems, inventory_problems, dock_problems, ncr_problems):
        try:
            probs += fn(w)
        except Exception:  # a sheet layout this check does not understand must not block
            continue
    if not probs:
        return []
    return [Finding("generic.records", ["SOP 8.1, 10.2-10.7, 11.8, 12.8, 12.9, 13.1-13.3, 14.7.1, 14.8, 21"],
                    "Workbook records do not follow the SOP column rules: " + " ".join(probs[:8]),
                    ["Correct the listed values (never edit posted rows - use the correction procedure)."])]


def compiled_paragraph_ids(sop: SOP) -> dict[str, str]:
    """Paragraph id -> generic rule id, for coverage reporting."""
    c = Compiled(sop)
    out = {f.pid: "generic.message_format" for f in c.formats}
    for t in c.templates:
        for pid in t.pids:
            out[pid] = "generic.email_template"
    return out
