"""Rebuild conversation state from the ledger (pure Python parsing of tool output)."""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass, field
from typing import Any

from . import actions as act_mod

try:
    from zoneinfo import ZoneInfo

    PLANT_TZ: dt.tzinfo = ZoneInfo("America/Chicago")
except Exception:  # pragma: no cover - tzdata missing
    PLANT_TZ = dt.timezone(dt.timedelta(hours=-5))

RECEIPT_ID = re.compile(r"REC-(\d{8})-(\d{3})(?:-T4)?")


@dataclass
class SlackMessage:
    channel: str
    user: str
    text: str
    ts: float
    files: list[Any] = field(default_factory=list)

    @property
    def date(self) -> dt.date:
        return dt.datetime.fromtimestamp(self.ts, PLANT_TZ).date()


@dataclass
class Email:
    sender: str
    to: list[str]
    subject: str
    body: str
    date: str
    folder: str
    attachments: list[Any]
    email_id: str = ""
    is_read: bool | None = None


@dataclass
class Executed:
    action: act_mod.Action
    result: str
    index: int


@dataclass
class State:
    instruction: str = ""
    records: list[dict] = field(default_factory=list)
    observations: list[dict] = field(default_factory=list)
    slack: list[SlackMessage] = field(default_factory=list)
    emails: list[Email] = field(default_factory=list)
    channels: dict[str, str] = field(default_factory=dict)  # id -> name
    users: dict[str, dict] = field(default_factory=dict)  # id -> {name, email, title}
    executed: list[Executed] = field(default_factory=list)
    reads: list[tuple[act_mod.Action, str]] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)
    agent_messages: list[str] = field(default_factory=list)

    @property
    def observed_text(self) -> str:
        return "\n".join(o.get("text", "") for o in self.observations)

    def today(self) -> dt.date | None:
        """Latest in-world date seen in Slack timestamps (the plant's 'today')."""
        if not self.slack:
            return None
        return max(m.date for m in self.slack)

    def executed_kinds(self, kind: str) -> list[Executed]:
        return [e for e in self.executed if e.action.kind == kind]

    def sent_emails(self) -> list[Executed]:
        return self.executed_kinds("email_send")


def _json_payload(text: str) -> Any:
    text = re.sub(r"^\s*\[Tool '[^']*' executed\.\]\s*", "", text)
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
    if start < 0:
        return None
    try:
        return json.loads(text[start:])
    except json.JSONDecodeError:
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[start:])
            return obj
        except json.JSONDecodeError:
            return None


def _iter_dicts(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _iter_dicts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _iter_dicts(v)


def _succeeded(text: str) -> bool:
    payload = _json_payload(text)
    if isinstance(payload, dict):
        if payload.get("ok") is False or payload.get("success") is False or payload.get("error"):
            return False
        if payload.get("returncode") not in (None, 0):
            return False
        return True
    return not re.search(r"\b(error|exception|traceback|failed)\b", text.lower()[:400])


def build(records: list[dict]) -> State:
    st = State(records=records)
    pending: dict[str, tuple[act_mod.Action, int]] = {}
    for i, rec in enumerate(records):
        rtype = rec.get("type")
        if rtype == "user_message" and not st.instruction:
            st.instruction = rec.get("text", "")
        elif rtype == "agent_message":
            st.agent_messages.append(rec.get("text", ""))
        elif rtype == "action":
            a = act_mod.classify(rec.get("tool", ""), rec.get("args") or {})
            pending[rec.get("call_id") or rec.get("id")] = (a, i)
        elif rtype == "rejection":
            pending.pop(rec.get("call_id"), None)
            st.rejected.append(rec)
        elif rtype == "observation":
            text = rec.get("text", "")
            st.observations.append(rec)
            key = rec.get("call_id")
            a_i = pending.pop(key, None)
            tool = rec.get("tool", "")
            args = a_i[0].args if a_i else {}
            # World facts come only from reads: the agent's own posts carry wall-clock timestamps.
            if a_i is None or not a_i[0].is_write:
                _absorb(st, tool, args, text)
                if a_i is not None:
                    st.reads.append((a_i[0], text))
            if a_i and a_i[0].is_write and _succeeded(text):
                st.executed.append(Executed(a_i[0], text, a_i[1]))
    return st


def _absorb(st: State, tool: str, args: dict, text: str) -> None:
    payload = _json_payload(text)
    if payload is None:
        return
    if tool.startswith("slack__"):
        channel = str(args.get("channel_id") or args.get("channel") or "")
        for d in _iter_dicts(payload):
            if "ts" in d and "text" in d and ("user" in d or "username" in d):
                try:
                    ts = float(d["ts"])
                except (TypeError, ValueError):
                    continue
                msg = SlackMessage(str(d.get("channel") or channel), str(d.get("user", "")),
                                   str(d.get("text", "")), ts, list(d.get("files") or []))
                if not any(m.ts == msg.ts and m.text == msg.text for m in st.slack):
                    st.slack.append(msg)
            if "id" in d and "name" in d and str(d["id"]).startswith(("C", "G", "D")) and (
                    "is_channel" in d or "is_im" in d or "is_private" in d):
                st.channels[str(d["id"])] = str(d["name"])
            if "id" in d and str(d["id"]).startswith("U") and ("real_name" in d or "profile" in d):
                prof = d.get("profile") or {}
                st.users[str(d["id"])] = {
                    "name": d.get("real_name") or prof.get("real_name"),
                    "email": prof.get("email") or d.get("email"),
                    "title": prof.get("title") or d.get("title"),
                }
        if tool == "slack__get_user_profile" and isinstance(payload, dict):
            uid = str(args.get("user_id", ""))
            prof = payload.get("profile") or payload
            if uid and isinstance(prof, dict):
                st.users.setdefault(uid, {}).update({
                    "name": prof.get("real_name") or st.users.get(uid, {}).get("name"),
                    "email": prof.get("email"), "title": prof.get("title")})
    elif tool.startswith("google_mail__"):
        for d in _iter_dicts(payload):
            sender = d.get("from_addr") or d.get("from") or d.get("sender")
            if not (sender and "subject" in d and ("email_id" in d or "body_text" in d or "body" in d)):
                continue
            eid = str(d.get("email_id") or d.get("id") or "")
            body = str(d.get("body_text") or d.get("body") or d.get("snippet") or "")
            prev = next((e for e in st.emails if eid and e.email_id == eid), None)
            if prev is not None:
                prev.body = body or prev.body
                prev.folder = str(d.get("folder") or prev.folder)
                prev.attachments = list(d.get("attachments") or prev.attachments)
                if d.get("is_read") is not None:
                    prev.is_read = bool(d["is_read"])
                continue
            to = d.get("to_addr") or d.get("to") or ""
            st.emails.append(Email(str(sender).lower(), act_mod._split_addrs(to), str(d.get("subject", "")),
                                   body, str(d.get("date", "")), str(d.get("folder", "")),
                                   list(d.get("attachments") or []), eid,
                                   None if d.get("is_read") is None else bool(d["is_read"])))
