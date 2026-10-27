"""Access to the parsed SOP (paragraphs, templates, contacts, holidays)."""

from __future__ import annotations

import datetime as dt
import functools
import json
import re
from dataclasses import dataclass

from . import config


@dataclass(frozen=True)
class Contact:
    name: str | None
    role: str
    email: str
    handle: str
    source: str

    @property
    def first_name(self) -> str | None:
        return self.name.split()[0] if self.name else None


class SOP:
    def __init__(self, data: dict):
        self.data = data
        self.paragraphs: list[dict] = data["paragraphs"]
        self.by_id = {p["id"]: p for p in self.paragraphs}
        self.templates: dict[str, dict] = data["templates"]
        self.contacts = [Contact(**c) for c in data["contacts"]]
        self.holidays = {dt.date.fromisoformat(h["date"]) for h in data["holidays"]}

    def section(self, prefix: str) -> list[dict]:
        return [p for p in self.paragraphs
                if p["section"] == prefix or p["section"].startswith(prefix + ".")]

    def find(self, section: str, startswith: str) -> str:
        """Paragraph id in ``section`` whose text starts with ``startswith``."""
        for p in self.section(section):
            if p["text"].startswith(startswith) or re.sub(r"^[\s•●▪\-–]+", "", p["text"]).startswith(startswith):
                return p["id"]
        raise KeyError(f"no paragraph in {section} starting with {startswith!r}")

    def template(self, number: int) -> dict:
        return self.templates[str(number)]

    def contact_by_email(self, email: str) -> Contact | None:
        email = email.strip().lower()
        return next((c for c in self.contacts if c.email.lower() == email), None)

    def contact_by_name(self, name: str) -> Contact | None:
        """Full-name match, else a unique first-name match."""
        key = _fold(name)
        full = [c for c in self.contacts if c.name and _fold(c.name) == key]
        if full:
            return full[0]
        first = [c for c in self.contacts if c.name and _fold(c.first_name) == key.split(" ")[0]]
        return first[0] if len(first) == 1 else None

    def contact_by_handle(self, handle: str) -> Contact | None:
        handle = handle.lstrip("@").lower()
        return next((c for c in self.contacts if c.handle.lower() == handle), None)

    def standard_signoff(self) -> list[str]:
        # Section 23 preamble: "All templates use the standard sign-off: Best regards, ..."
        sec = self.section("23")
        for i, p in enumerate(sec):
            if p["text"].startswith("All templates use the standard sign-off"):
                joined = " ".join(q["text"] for q in sec[i + 1: i + 5])
                m = re.match(r"(Best regards,)\s+(Inbound Materials Coordinator)\s+(Gear\s+Systems Inc\. — "
                             r"Meridian Plant)\s+(\S+@\S+)", joined)
                if m:
                    return [re.sub(r"\s+", " ", g) for g in m.groups()]
        return []

    def business_days_between(self, start: dt.date, end: dt.date) -> int:
        """Business days after ``start`` up to and including ``end`` (Section 14.5 definition)."""
        if end <= start:
            return 0
        days, cur = 0, start
        while cur < end:
            cur += dt.timedelta(days=1)
            if cur.weekday() < 5 and cur not in self.holidays:
                days += 1
        return days


def _fold(text: str | None) -> str:
    import unicodedata

    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip().lower()


fold = _fold


@functools.lru_cache(maxsize=4)
def load(task: str | None = None) -> SOP:
    task = task or config.task_id()
    path = config.TASKS_DIR / task / "sop.json"
    return SOP(json.loads(path.read_text(encoding="utf-8")))


def available(task: str | None = None) -> bool:
    task = task or config.task_id()
    return bool(task) and (config.TASKS_DIR / task / "sop.json").is_file()
