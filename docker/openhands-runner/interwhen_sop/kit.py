"""Domain-free building blocks for per-task SOP verifiers (scripts/algo.md Step 3).

Facts come only from the task's seed data (initial workspace, mail, Slack, calendar, Jira, ...), the live
workbooks and the executed tool calls. Nothing here reads graders, rubrics or tests/. Task modules in
``interwhen_sop/verifiers/<task>.py`` import from here and export ``RULES``.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Callable, Iterable

from . import config, templates, workbooks
from .actions import Action, _shell_write_targets
from .framework import Context, Finding, Rule, registry
from .state import Executed

COMM_KINDS = ("email_send", "email_draft", "slack_post", "slack_dm")
WRITE_KINDS = ("workbook_write", "file_write", "file_delete")
MAX_DENIALS_PER_TAG = 2
Ref = tuple[str, str, str]  # (SOP section, paragraph text prefix, label)


# ---- text helpers ------------------------------------------------------------------------------

def nh(s) -> str:
    """Collapse whitespace."""
    return re.sub(r"\s+", " ", str(s if s is not None else "")).strip()


def norm(s) -> str:
    """Lower-case, unify dashes/arrows/whitespace for tolerant comparison."""
    s = str(s or "").replace("\u2192", "->").replace("\u2014", "-").replace("\u2013", "-")
    return re.sub(r"\s+", " ", s).strip().lower()


def dashes(s) -> str:
    """Unify en/em dashes and spaced hyphens so formats compare on content (regexes still use [-–—])."""
    s = str(s or "").replace("\u2014", "–").replace("\u2013", "–")
    s = re.sub(r"\s+-\s+", " – ", s)
    return re.sub(r"\s+", " ", s).strip()


def num(v) -> float | None:
    try:
        return float(str(v).replace(",", "").replace("$", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def blank(v) -> bool:
    return str(v if v is not None else "").strip() in ("", "None", "nan")


def same(got, want, tol: float = 0.006) -> bool:
    """Cell equality: numbers within ``tol``, text by ``norm``; ``want=None`` means blank."""
    if want is None:
        return blank(got)
    a, b = num(got), num(want)
    if a is not None and b is not None:
        return abs(a - b) < tol
    return norm(got) == norm(want)


def money_rx(v: float) -> str:
    """Regex for an amount written as 1,234.50 / $1234.5 / 1234.50 (cents optional when .00)."""
    whole, cents = f"{v:.2f}".split(".")
    return rf"\$?\s?{int(whole):,}".replace(",", ",?") + (rf"\.{cents}" if cents != "00" else r"(\.00)?") + r"(?!\d)"


def text_of(a: Action) -> str:
    return f"{a.subject}\n{a.text}"


def attachments(a: Action) -> list[str]:
    att = a.args.get("attachments") or a.args.get("attachment") or []
    if isinstance(att, (str, dict)):
        att = [att]
    out = []
    for x in att:
        if isinstance(x, dict):
            x = x.get("filename") or x.get("path") or x.get("name") or ""
        out.append(str(x).split("/")[-1])
    return out


def strict_writes(a: Action) -> set[str]:
    """File names a call provably writes (literal save target or a variable bound to one)."""
    if a.kind in ("file_write", "file_delete"):
        return {f.split("/")[-1] for f in a.files_written}
    if a.kind != "workbook_write":
        return set()
    out: set[str] = set(f.split("/")[-1] for f in a.files_written)
    if a.tool == "syntara__executeBash":
        out |= {f.split("/")[-1] for f in _shell_write_targets(a.text)}
    return out


def initial_data() -> Path:
    return Path(os.environ.get("INTERWHEN_INITIAL_DATA", "/initial_data"))


def pdf_text(path, layout: bool = False) -> str:
    """Text of a PDF (pdftotext, falling back to pypdf in the xlsx python); '' if unreadable."""
    import shutil
    import subprocess
    flags = ["-layout"] if layout else []
    cmds = ([["pdftotext", *flags, str(path), "-"]] if shutil.which("pdftotext") else []) + [
        [config.xlsx_python(), "-c", "import sys,pypdf;print('\\n'.join(p.extract_text() or '' for p in "
                                     "pypdf.PdfReader(sys.argv[1]).pages))", str(path)]]
    for cmd in cmds:
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout
        except (OSError, subprocess.TimeoutExpired):
            continue
    return ""


def docx_text(path) -> str:
    import zipfile
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
        return re.sub(r"<[^>]+>", " ", re.sub(r"</w:p>", "\n", xml))
    except (OSError, KeyError, zipfile.BadZipFile):
        return ""


def _strip(r: dict) -> tuple:
    return tuple(v for k, v in r.items() if k != "__row__")


def book_eq(a, b) -> bool:
    """Workbook snapshots equal, ignoring openpyxl object reprs (array formulas print a memory address)."""
    n = lambda x: re.sub(r" at 0x[0-9a-f]+", "", json.dumps(x, default=str, sort_keys=True))
    return n(a) == n(b)


# ---- world view ----------------------------------------------------------------------------------

class World:
    """What the verifier can observe: live/initial workbooks, workspace files, seed services, executed calls."""

    def __init__(self, ctx: Context):
        self.ctx, self.state = ctx, ctx.state

    # workbooks: {relative path: {sheet: [[cell, ...], ...]}}
    @cached_property
    def current(self) -> dict:
        return workbooks.dump() or {}

    @cached_property
    def initial(self) -> dict:
        p = workbooks.snapshot_path()
        return json.loads(p.read_text()) if p.exists() else {}

    def book(self, name_rx: str, which: str = "current") -> tuple[str | None, dict | None]:
        src = self.current if which == "current" else self.initial
        hits = sorted(k for k in (src or {}) if re.search(name_rx, k, re.I) and isinstance(src[k], dict))
        return (hits[0], src[hits[0]]) if hits else (None, None)

    def books(self, name_rx: str, which: str = "current") -> list[str]:
        src = self.current if which == "current" else self.initial
        return sorted(k for k in (src or {}) if re.search(name_rx, k, re.I))

    def sheet(self, name_rx: str, sheet_rx: str | None = None, which: str = "current") -> list[list[str]]:
        _, sheets = self.book(name_rx, which)
        if not sheets:
            return []
        if sheet_rx:
            name = next((n for n in sheets if re.search(sheet_rx, n, re.I)), None)
            return sheets.get(name, []) if name else []
        return next(iter(sheets.values()))

    def rows(self, name_rx: str, header_rx: str, which: str = "current", sheet_rx: str | None = None) -> list[dict]:
        """Data rows under the first row containing a cell matching ``header_rx``; '__row__' = 1-based row."""
        grid = self.sheet(name_rx, sheet_rx, which)
        for i, row in enumerate(grid):
            if any(re.search(header_rx, nh(c), re.I) for c in row):
                header = [nh(c) for c in row]
                out = []
                for j, r in enumerate(grid[i + 1:], start=i + 2):
                    if any(str(c).strip() not in ("", "None") for c in r):
                        d = dict(zip(header, (str(c) for c in r)))
                        d["__row__"] = str(j)
                        out.append(d)
                return out
        return []

    @staticmethod
    def col(row: dict, name_rx: str) -> str:
        for k, v in row.items():
            if k != "__row__" and re.search(name_rx, k, re.I):
                return "" if str(v) in ("None", "nan") else str(v).strip()
        return ""

    def find(self, name_rx: str, header_rx: str, key_col_rx: str, value, which: str = "current",
             sheet_rx: str | None = None) -> dict | None:
        want = norm(value)
        return next((r for r in self.rows(name_rx, header_rx, which, sheet_rx) if norm(self.col(r, key_col_rx)) == want),
                    None)

    def new_rows(self, name_rx: str, header_rx: str, sheet_rx: str | None = None) -> list[dict]:
        """Rows present now that were not in the initial workbook (multiset difference)."""
        seen = [_strip(r) for r in self.rows(name_rx, header_rx, "initial", sheet_rx)]
        out = []
        for r in self.rows(name_rx, header_rx, "current", sheet_rx):
            s = _strip(r)
            if s in seen:
                seen.remove(s)
            else:
                out.append(r)
        return out

    def missing_rows(self, name_rx: str, header_rx: str, sheet_rx: str | None = None) -> list[dict]:
        """Initial rows that are no longer present unchanged."""
        cur = [_strip(r) for r in self.rows(name_rx, header_rx, "current", sheet_rx)]
        out = []
        for r in self.rows(name_rx, header_rx, "initial", sheet_rx):
            s = _strip(r)
            if s in cur:
                cur.remove(s)
            else:
                out.append(r)
        return out

    def changed_files(self, keep_rx: str = r"^$") -> list[str]:
        """Initial workbooks whose content changed (or were removed), except those matching ``keep_rx``."""
        return [k for k in (self.initial or {}) if not re.search(keep_rx, k)
                and not book_eq((self.current or {}).get(k), self.initial[k])]

    def created_books(self) -> list[str]:
        return sorted(set(self.current or {}) - set(self.initial or {}))

    # workspace files
    def files(self) -> list[str]:
        root = config.workdir()
        out = []
        for dirpath, _, names in os.walk(root):
            out += [os.path.relpath(os.path.join(dirpath, n), root) for n in names]
        return out

    def has_file(self, rx: str) -> bool:
        r = re.compile(rx, re.I)
        return any(r.search(f) for f in self.files())

    def file_text(self, name_rx: str) -> tuple[str | None, str]:
        """(relative path, text) of the first workspace PDF/DOCX/TXT/CSV/MD matching ``name_rx``."""
        root = config.workdir()
        hits = sorted(f for f in self.files() if re.search(name_rx, f, re.I))
        for f in hits:
            p = root / f
            if f.lower().endswith(".pdf"):
                return f, pdf_text(p)
            if f.lower().endswith(".docx"):
                return f, docx_text(p)
            if f.lower().endswith((".txt", ".csv", ".md", ".json")):
                try:
                    return f, p.read_text(errors="ignore")
                except OSError:
                    continue
        return (hits[0], "") if hits else (None, "")

    # seed services
    def _seed(self, *parts: str) -> dict:
        try:
            return json.loads(initial_data().joinpath(*parts).read_text())
        except (OSError, json.JSONDecodeError):
            return {}

    @cached_property
    def slack_seed(self) -> dict:
        return self._seed("slack", "slack.json")

    @cached_property
    def seed_emails(self) -> list[dict]:
        return list(self._seed("google_mail", "inbox.json").get("emails") or [])

    @cached_property
    def mailbox(self) -> str:
        m = self._seed("google_mail", "inbox.json").get("mailbox") or {}
        return norm(m.get("email") if isinstance(m, dict) else m)

    @cached_property
    def seed_events(self) -> list[dict]:
        evs = self._seed("google_calendar", "calendar_data.json").get("events") or []
        return list(evs.values()) if isinstance(evs, dict) else list(evs)

    @cached_property
    def users(self) -> dict[str, dict]:
        out = {}
        for uid, d in (self.slack_seed.get("users") or {}).items():
            prof = d.get("profile") or {}
            out[uid] = {"name": d.get("real_name") or prof.get("real_name"), "handle": d.get("name"),
                        "title": prof.get("title"), "email": prof.get("email")}
        for uid, d in self.state.users.items():
            out.setdefault(uid, {}).update({k: v for k, v in d.items() if v})
        return out

    @cached_property
    def channels(self) -> dict[str, dict]:
        out = {cid: {"name": d.get("name"), "is_im": bool(d.get("is_im")), "members": d.get("members") or []}
               for cid, d in (self.slack_seed.get("channels") or {}).items()}
        for cid, name in self.state.channels.items():
            out.setdefault(cid, {"name": name, "is_im": False, "members": []})
        return out

    @cached_property
    def self_uids(self) -> set[str]:
        """Slack ids of the acting user (matched by the mailbox address)."""
        return {u for u, d in self.users.items() if self.mailbox and norm(d.get("email")) == self.mailbox}

    def uids(self, person: str) -> set[str]:
        p = norm(person)
        first, last = p.split()[0], p.split()[-1]
        return {u for u, d in self.users.items()
                if norm(d.get("name")) == p or (last in norm(d.get("name")) and first in norm(d.get("name")))
                or norm(d.get("email")) == p}

    def channel_name(self, ref) -> str:
        ref = str(ref or "").lstrip("#")
        return str(self.channels.get(ref, {}).get("name") or ref)

    def is_channel(self, action_channel, name: str) -> bool:
        return norm(self.channel_name(action_channel)) == norm(name.lstrip("#"))

    def dm_recipients(self, a: Action) -> set[str]:
        if a.kind == "slack_dm":
            return set(a.recipients)
        if a.kind == "slack_post":
            ch = self.channels.get(str(a.channel).lstrip("#"), {})
            if ch.get("is_im"):
                return set(ch.get("members") or []) - set(self.self_uids)
        return set()

    def is_dm_to(self, a: Action, person: str) -> bool:
        return bool(self.dm_recipients(a) & self.uids(person))

    # executed calls
    def ok(self, e: Executed) -> bool:
        """The call's tool result was not an error."""
        return not re.search(r'"status"\s*:\s*"error"|"error"\s*:\s*"[^"]', e.result or "")

    def calls(self, *kinds: str, ok_only: bool = True) -> list[Action]:
        return [e.action for e in self.state.executed if (not kinds or e.action.kind in kinds)
                and (not ok_only or self.ok(e))]

    def comms(self) -> list[Action]:
        return self.calls(*COMM_KINDS)

    def posts_in(self, channel: str) -> list[Action]:
        return [a for a in self.calls("slack_post") if self.is_channel(a.channel, channel) and not self.dm_recipients(a)]

    def wrote(self, file_rx: str) -> bool:
        return any(re.search(file_rx, f, re.I) for a in self.calls(*WRITE_KINDS) for f in strict_writes(a))


def world(ctx: Context) -> World:
    return ctx.memo("kit.world", lambda: World(ctx))


def cites(ctx: Context, refs: Iterable[Ref]) -> list[str]:
    return [ctx.cite(s, p, lab) for s, p, lab in refs]


def prior_denials(ctx: Context, tag: str) -> int:
    return sum(tag in json.dumps(r) for r in ctx.state.rejected)


# ---- rule builders -------------------------------------------------------------------------------

def state_rule(rule_id: str, checks: Callable[[Context], Iterable[tuple[bool, str, list[Ref]]]],
               fix: str = "Fix this as listed.") -> list[Rule]:
    """Completion rule over the end state: ``checks(ctx)`` yields (ok, problem, refs)."""
    rules: list[Rule] = []
    rule = registry(rules)

    @rule(rule_id, "completion", [])
    def check(ctx: Context) -> list[Finding]:
        return [Finding(rule_id, cites(ctx, refs), problem, [fix]) for ok, problem, refs in checks(ctx) if not ok]

    return rules


def pre_rule(rule_id: str, problem: Callable[[Context, Action], str | None], refs: list[Ref],
             fix: str = "Change the call as described.") -> list[Rule]:
    """Pre-tool rule: block a call when ``problem(ctx, action)`` returns a non-empty message."""
    rules: list[Rule] = []
    rule = registry(rules)

    @rule(rule_id, "pre", [])
    def check(ctx: Context, action: Action) -> list[Finding]:
        msg = problem(ctx, action)
        return [Finding(rule_id, cites(ctx, refs), msg, [fix])] if msg else []

    return rules


def append_only(rule_id: str, name_rx: str, header_rx: str, what: str, refs: list[Ref],
                sheet_rx: str | None = None) -> list[Rule]:
    """Existing rows of a log stay exactly as they were; new rows are appended."""
    def checks(ctx: Context):
        w = world(ctx)
        if not w.rows(name_rx, header_rx, "initial", sheet_rx):
            return []
        gone = w.missing_rows(name_rx, header_rx, sheet_rx)
        eg = " | ".join(_strip(gone[0])[:5]) if gone else ""
        return [(not gone, f"{what} is append-only: {len(gone)} existing row(s) were edited or removed (e.g. {eg}). "
                           "Restore them and only append new rows.", refs)]
    return state_rule(rule_id, checks)


def forbid_writes(rule_id: str, file_rx: str, why: str, refs: list[Ref]) -> list[Rule]:
    """Block writes/deletes of files whose name matches ``file_rx``."""
    def problem(ctx: Context, a: Action):
        if a.kind not in WRITE_KINDS:
            return None
        hit = [f for f in strict_writes(a) if re.search(file_rx, f, re.I)]
        if not hit and a.kind == "file_delete" and re.search(file_rx, a.text or json.dumps(a.args), re.I):
            hit = ["(deleted file)"]
        return f"{', '.join(hit)}: {why}" if hit else None
    return pre_rule(rule_id, problem, refs, "Leave that file unchanged.")


def no_placeholders(refs: list[Ref], literal: Iterable[str] = (), literal_rx: Iterable[str] = ()) -> list[Rule]:
    """Every [bracketed template field] is filled before a message is sent. ``literal``/``literal_rx`` are
    bracketed tags the SOP itself prints (e.g. a Slack tag) and that are therefore not placeholders."""
    templates.LITERAL.update(literal)
    templates.LITERAL_RX.extend(re.compile(r) for r in literal_rx)

    def problem(ctx: Context, a: Action):
        if a.kind not in COMM_KINDS:
            return None
        left = templates.unfilled_placeholders(text_of(a))
        return f"[placeholders] The message still contains template placeholders {left}." if left else None
    return pre_rule("comms.no_placeholders", problem, refs, "Replace every bracketed field with the actual value.")


@dataclass
class Comm:
    """One SOP-prescribed (or SOP-prohibited) message, checked before it is sent and at completion.

    kind: email | forward | draft | slack_post | slack_dm.  ``about(action)`` decides whether an outgoing call
    is this message. Text regexes run on the dash-normalised text (use [-–—] for dashes)."""
    key: str
    kind: str
    about: Callable[[Action], bool]
    what: str
    refs: list[Ref]
    to: list[str] = field(default_factory=list)      # emails (email/forward/draft) or full names (slack_dm)
    cc: list[str] = field(default_factory=list)
    channel: str | None = None
    subject: str | None = None                       # regex, fullmatch on the dash-normalised subject
    subject_hint: str = ""
    body: list[tuple[str, str]] = field(default_factory=list)    # (regex, description) that must appear
    banned: list[tuple[str, str]] = field(default_factory=list)  # (regex, why) that must not appear
    attach: list[tuple[str, str]] = field(default_factory=list)  # (file-name regex, description)
    forbidden: str = ""                              # non-empty: any matching call is blocked with this reason
    required: bool = True
    exact_to: bool = True
    max_count: int = 1
    exact: str = ""                                  # regex the whole normalised body must fullmatch
    exact_hint: str = ""
    keep_placeholders: tuple = ()

    def problems(self, a: Action, w: World) -> list[str]:
        if self.forbidden:
            return [self.forbidden]
        out: list[str] = []
        kinds = {"email": ("email_send",), "forward": ("email_send",), "draft": ("email_draft",),
                 "slack_post": ("slack_post",), "slack_dm": ("slack_dm", "slack_post")}[self.kind]
        if a.kind not in kinds:
            return ["Save this as an email draft (do not send it)." if self.kind == "draft" else
                    f"This must be sent as a {self.kind.replace('_', ' ')}, not a {a.kind.replace('_', ' ')}."]
        if self.kind in ("email", "forward", "draft"):
            to, cc = {x.lower() for x in a.recipients}, {x.lower() for x in a.cc}
            want_to, want_cc = {x.lower() for x in self.to}, {x.lower() for x in self.cc}
            if self.kind == "forward" and "forward" not in a.tool:
                out.append("Forward the original email instead of writing a new one.")
            if want_to - to:
                out.append(f"To must include {', '.join(sorted(want_to - to))}.")
            if want_cc - to - cc:
                out.append(f"CC must include {', '.join(sorted(want_cc - to - cc))}.")
            extra = sorted((to | cc) - want_to - want_cc)
            if self.exact_to and extra:
                out.append(f"Remove recipients the SOP does not route this to: {', '.join(extra)}.")
            if self.subject and not re.fullmatch(self.subject, dashes(a.subject), re.I):
                out.append(f"Subject must follow the SOP format{': ' + self.subject_hint if self.subject_hint else ''}"
                           f" (got \"{a.subject}\").")
            have = attachments(a)
            for rx, desc in self.attach:
                if not any(re.search(rx, f, re.I) for f in have):
                    out.append(f"Attach {desc}.")
        elif self.kind == "slack_post":
            if w.dm_recipients(a):
                out.append(f"Post this in #{self.channel}, not as a direct message.")
            elif self.channel and not w.is_channel(a.channel, self.channel):
                out.append(f"Post this in #{self.channel} (got #{w.channel_name(a.channel)}).")
        elif self.kind == "slack_dm":
            for person in self.to:
                if not w.is_dm_to(a, person):
                    out.append(f"Send this as a direct message to {person}.")
        body = dashes(a.text)
        for rx, desc in self.body:
            if not re.search(rx, body, re.I | re.S):
                out.append(f"Missing: {desc}.")
        if self.exact and not re.fullmatch(self.exact, body.strip()):
            out.append(f"The SOP gives this message word for word - send exactly: {self.exact_hint}")
        for rx, why in self.banned:
            if re.search(rx, body, re.I | re.S):
                out.append(why)
        left = [p for p in templates.unfilled_placeholders(text_of(a)) if p not in self.keep_placeholders]
        if left:
            out.append(f"Unfilled template placeholders {left}.")
        return out


def comm_rules(rule_id: str, specs: Callable[[Context], list[Comm]]) -> list[Rule]:
    """A pre rule vetting outgoing messages against ``specs`` and a completion rule for required ones."""
    rules: list[Rule] = []
    rule = registry(rules)

    @rule(f"{rule_id}.messages", "pre", [])
    def pre(ctx: Context, action: Action) -> list[Finding]:
        if action.kind not in COMM_KINDS:
            return []
        w = world(ctx)
        out = []
        for c in specs(ctx):
            try:
                if not c.about(action):
                    continue
            except Exception:
                continue
            tag = f"[comm:{c.key}]"
            if not c.forbidden and prior_denials(ctx, tag) >= MAX_DENIALS_PER_TAG:
                continue
            probs = c.problems(action, w)
            if not probs and not c.forbidden:
                done = [a for a in w.comms() if c.about(a) and not c.problems(a, w)]
                if len(done) >= c.max_count:
                    probs = [f"This message ({c.what}) was already sent; do not send it again."]
            if probs:
                out.append(Finding(f"{rule_id}.messages", cites(ctx, c.refs), f"{tag} {c.what}: " + " ".join(probs),
                                   ["Do not send this message." if c.forbidden else
                                    "Fix the message as listed and send it again."]))
        return out

    @rule(f"{rule_id}.messages_sent", "completion", [])
    def done(ctx: Context) -> list[Finding]:
        w = world(ctx)
        out = []
        for c in specs(ctx):
            if c.forbidden or not c.required:
                continue
            if any(c.about(a) and not c.problems(a, w) for a in w.comms()):
                continue
            hint = []
            if c.to:
                hint.append(("to " if c.kind != "slack_dm" else "DM to ") + ", ".join(c.to))
            if c.cc:
                hint.append("cc " + ", ".join(c.cc))
            if c.channel:
                hint.append(f"in #{c.channel}")
            if c.subject_hint:
                hint.append(f"subject \"{c.subject_hint}\"")
            if c.exact_hint:
                hint.append(f"text exactly: {c.exact_hint}")
            elif c.body:
                hint.append("containing " + "; ".join(d for _, d in c.body))
            if c.attach:
                hint.append("attaching " + "; ".join(d for _, d in c.attach))
            verb = "Save the draft" if c.kind == "draft" else "Send it"
            out.append(Finding(f"{rule_id}.messages_sent", cites(ctx, c.refs),
                               f"Not yet done per the SOP: {c.what}.", [f"{verb} ({'; '.join(hint)})."]))
        return out

    return rules


__all__ = ["COMM_KINDS", "WRITE_KINDS", "Ref", "nh", "norm", "dashes", "num", "blank", "same", "money_rx", "text_of",
           "attachments", "strict_writes", "pdf_text", "docx_text", "book_eq", "World", "world", "cites",
           "prior_denials", "state_rule", "pre_rule", "append_only", "forbid_writes", "no_placeholders", "Comm",
           "comm_rules", "Action", "Context", "Finding", "Rule", "registry"]
