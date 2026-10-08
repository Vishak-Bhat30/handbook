"""World helpers shared by the Gear task verifiers: workbook tables, Slack directory, workspace files.

Facts come from the live workbooks, the task's initial service data (the same records the agent can
read through its tools) and the tool outputs observed so far. Nothing here reads graders or rubrics.
"""

from __future__ import annotations

import json
import os
import re
from functools import cached_property
from pathlib import Path

from . import config, workbooks
from .framework import Context
from .state import Executed

def initial_data() -> Path:
    return Path(os.environ.get("INTERWHEN_INITIAL_DATA", "/initial_data"))
REC_ID = re.compile(r"REC-\d{8}-\d{3}")


def norm(s) -> str:
    """Lower-case, unify dashes/arrows/whitespace for tolerant text comparison."""
    s = str(s or "").replace("\u2192", "->").replace("\u2014", "-").replace("\u2013", "-")
    return re.sub(r"\s+", " ", s).strip().lower()


def blank(v) -> bool:
    return str(v or "").strip() in ("", "None")


def num(v) -> float | None:
    try:
        return float(str(v).replace(",", "").replace("$", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None


class World:
    def __init__(self, ctx: Context):
        self.ctx, self.state = ctx, ctx.state

    # ---- workbooks -------------------------------------------------------------------------
    @cached_property
    def current(self) -> dict:
        return workbooks.dump() or {}

    @cached_property
    def initial(self) -> dict:
        p = workbooks.snapshot_path()
        return json.loads(p.read_text()) if p.exists() else {}

    def rows(self, fname: str, key: str, which: str = "current") -> list[dict]:
        src = self.current if which == "current" else self.initial
        rows = workbooks.table(workbooks.first_sheet(src, fname), key)
        # Drop format-description rows such as "REC-YYYYMMDD-NNN" placeholders.
        return [r for r in rows if not re.search(r"YYYY|NNN", str(r.get(key, "")))]

    def changed_rows(self, fname: str, key: str, match) -> list[tuple[dict | None, dict | None]]:
        """(before, after) pairs for rows selected by ``match`` whose content differs."""
        before = [r for r in self.rows(fname, key, "initial") if match(r)]
        after = [r for r in self.rows(fname, key) if match(r)]
        out = []
        for i in range(max(len(before), len(after))):
            b = before[i] if i < len(before) else None
            a = after[i] if i < len(after) else None
            if b != a:
                out.append((b, a))
        return out

    # ---- slack directory -------------------------------------------------------------------
    @cached_property
    def _slack_seed(self) -> dict:
        p = initial_data() / "slack" / "slack.json"
        try:
            return json.loads(p.read_text())
        except (OSError, json.JSONDecodeError):
            return {}

    @cached_property
    def users(self) -> dict[str, dict]:
        out = {}
        for uid, d in (self._slack_seed.get("users") or {}).items():
            prof = d.get("profile") or {}
            out[uid] = {"name": d.get("real_name") or prof.get("real_name"), "handle": d.get("name"),
                        "title": prof.get("title"), "email": prof.get("email")}
        for uid, d in self.state.users.items():
            out.setdefault(uid, {}).update({k: v for k, v in d.items() if v})
        return out

    @cached_property
    def channels(self) -> dict[str, dict]:
        out = {cid: {"name": d.get("name"), "is_im": bool(d.get("is_im")), "members": d.get("members") or []}
               for cid, d in (self._slack_seed.get("channels") or {}).items()}
        for cid, name in self.state.channels.items():
            out.setdefault(cid, {"name": name, "is_im": False, "members": []})
        return out

    def uids(self, person: str) -> set[str]:
        """Slack ids for a person given by full name (e.g. 'Maribel Ortiz')."""
        p = norm(person)
        first, last = p.split()[0], p.split()[-1]
        return {u for u, d in self.users.items()
                if norm(d.get("name")) == p or (last in norm(d.get("name")) and first in norm(d.get("name")))
                or norm(d.get("handle")) in (f"{first[0]}{last}", f"{first[0]}.{last}")}

    def channel_name(self, ref: str) -> str:
        ref = str(ref or "").lstrip("#")
        return str(self.channels.get(ref, {}).get("name") or ref)

    def is_channel(self, action_channel: str, name: str) -> bool:
        return norm(self.channel_name(action_channel)) == norm(name)

    def dm_recipients(self, ex_action) -> set[str]:
        a = ex_action
        if a.kind == "slack_dm":
            return set(a.recipients)
        if a.kind == "slack_post":
            ch = self.channels.get(str(a.channel).lstrip("#"), {})
            if ch.get("is_im"):
                return set(ch.get("members") or []) - set(self.self_uids)
        return set()

    @cached_property
    def self_uids(self) -> set[str]:
        return {u for u, d in self.users.items() if "inbound materials coordinator" in norm(d.get("title"))}

    def dms_to(self, person: str) -> list[Executed]:
        ids = self.uids(person)
        return [e for e in self.state.executed if self.dm_recipients(e.action) & ids]

    def posts_in(self, channel: str) -> list[Executed]:
        return [e for e in self.state.executed_kinds("slack_post")
                if self.is_channel(e.action.channel, channel) and not self.dm_recipients(e.action)]

    def is_dm_to(self, action, person: str) -> bool:
        return bool(self.dm_recipients(action) & self.uids(person))

    # ---- mail ------------------------------------------------------------------------------
    @cached_property
    def seed_emails(self) -> list[dict]:
        p = initial_data() / "google_mail" / "inbox.json"
        try:
            return list(json.loads(p.read_text()).get("emails") or [])
        except (OSError, json.JSONDecodeError):
            return []

    # ---- calendar --------------------------------------------------------------------------
    @cached_property
    def seed_events(self) -> list[dict]:
        p = initial_data() / "google_calendar" / "calendar_data.json"
        try:
            evs = json.loads(p.read_text()).get("events") or []
        except (OSError, json.JSONDecodeError):
            return []
        return list(evs.values()) if isinstance(evs, dict) else list(evs)

    # ---- workspace files -------------------------------------------------------------------
    def files(self) -> list[str]:
        root = config.workdir()
        out = []
        for dirpath, _, names in os.walk(root):
            out += [os.path.relpath(os.path.join(dirpath, n), root) for n in names]
        return out

    def has_file(self, pattern: str) -> bool:
        rx = re.compile(pattern, re.I)
        return any(rx.search(f) for f in self.files())

    # ---- reads -----------------------------------------------------------------------------
    def read_mentions(self, needle: str) -> bool:
        """True if any executed tool call's arguments or code mention ``needle`` (e.g. a workbook)."""
        n = needle.lower()
        acts = [a for a, _ in self.state.reads] + [e.action for e in self.state.executed]
        return any(n in json.dumps(a.args).lower() for a in acts)
