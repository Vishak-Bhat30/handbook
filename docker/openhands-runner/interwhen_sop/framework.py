"""Verifier framework: findings, rule registration, shared context, per-task rule loading.

Each task has its own verifier module ``interwhen_sop/verifiers/<task_id>.py`` exporting
``RULES``; :func:`load_rules` imports the module named after ``INTERWHEN_TASK``.
"""

from __future__ import annotations

import importlib
import importlib.util
from dataclasses import dataclass, field
from functools import cached_property
from typing import Callable

from . import extract
from .actions import Action
from .sopdata import SOP
from .state import State


@dataclass
class Finding:
    rule: str
    refs: list[str]
    problem: str
    fix: list[str] = field(default_factory=list)


@dataclass
class Rule:
    id: str
    stage: str  # "pre" | "completion"
    anchors: list[tuple[str, str]]  # (section, paragraph text prefix) from the SOP
    source: str  # "sop" | "task_instruction"
    fn: Callable


def registry(rules: list[Rule]):
    """Decorator factory that appends rules to ``rules``."""
    def rule(rule_id: str, stage: str, anchors: list[tuple[str, str]], source: str = "sop"):
        def deco(fn):
            rules.append(Rule(rule_id, stage, anchors, source, fn))
            return fn
        return deco
    return rule


def anchor_ids(sop: SOP, r: Rule) -> list[str]:
    out = []
    for sec, start in r.anchors:
        try:
            out.append(sop.find(sec, start))
        except KeyError:
            continue  # this SOP variant words the clause differently
    return out


class Context:
    def __init__(self, sop: SOP, state: State, log: list):
        self.sop, self.state, self.log = sop, state, log

    def para(self, section: str, start: str) -> tuple[str, str]:
        pid = self.sop.find(section, start)
        return pid, self.sop.by_id[pid]["text"]

    def cite(self, section: str, start: str, label: str) -> str:
        try:
            pid, text = self.para(section, start)
        except KeyError:
            return f"SOP {label}"
        return f"SOP {label} ({pid}): \"{text[:220]}{'…' if len(text) > 220 else ''}\""

    @cached_property
    def instruction(self) -> dict:
        return extract.instruction_facts(self.state, self.sop, self.log)

    @cached_property
    def initials(self) -> tuple[str | None, str]:
        return extract.coordinator_initials(self.state, self.log, self.instruction.get("acting_for"))

    def memo(self, key: str, fn: Callable):
        if key not in self.__dict__:
            self.__dict__[key] = fn()
        return self.__dict__[key]


def verifier_module(task: str) -> str:
    return f"{__package__}.verifiers.{task}"


def has_verifiers(task: str) -> bool:
    return bool(task) and importlib.util.find_spec(verifier_module(task)) is not None


def load_rules(task: str) -> list[Rule]:
    return list(importlib.import_module(verifier_module(task)).RULES)


def run(rules: list[Rule], stage: str, ctx: Context, action: Action | None = None):
    findings, errors = [], []
    for r in rules:
        if r.stage != stage:
            continue
        try:
            findings += r.fn(ctx, action) if stage == "pre" else r.fn(ctx)
        except Exception as exc:  # a broken verifier must never block the agent
            errors.append({"rule": r.id, "error": f"{type(exc).__name__}: {exc}"})
    return findings, errors
