"""Three-valued evaluator for the generated rule DSL.

A rule pairs ``when`` (applicability) with ``then`` (obligation), both expression
trees over Boolean facts that may be unknown (``None``):

    leaves      const | is_true | is_false | eq ne lt le gt ge (field vs literal)
    combinators and | or | not | implies

``check`` returns PASS when the rule does not apply or holds, FAIL when it applies
and is violated, and abstains (``passed is None``) when unknown facts leave it
undecided; any unknown field referenced by ``when`` abstains. Only FAIL blocks.

While evaluating ``then``, an unmet ``is_true`` on an action-category fact counts
as unknown: the extractor cannot tell "the call does not do Y" from "Y was not
visible", so positive action obligations abstain instead of false-flagging.
Prohibitions, comparisons and context facts stay fully enforced.
"""

from __future__ import annotations

import operator
from dataclasses import dataclass, field

COMPARISONS = {"eq": operator.eq, "ne": operator.ne, "lt": operator.lt,
               "le": operator.le, "gt": operator.gt, "ge": operator.ge}
FIELD_OPS = {"is_true", "is_false", *COMPARISONS}


@dataclass
class Value:
    """Three-valued result with the unknown fields and the fields that made it false."""

    value: bool | None
    unknown: list[str] = field(default_factory=list)
    false: list[str] = field(default_factory=list)


@dataclass
class Outcome:
    """Rule decision: ``passed`` is True, False (blocks) or None (abstains)."""

    passed: bool | None
    missing: list[str] = field(default_factory=list)
    violating: list[str] = field(default_factory=list)


def referenced_fields(expr: dict | None) -> list[str]:
    """Fact names an expression reads, in first-use order."""
    seen: dict[str, None] = {}

    def walk(node):
        """Record field references in ``node`` and its children."""
        if not isinstance(node, dict):
            return
        if node.get("op") in FIELD_OPS:
            seen.setdefault(node["field"], None)
        for key in ("arg", "if", "then"):
            walk(node.get(key))
        for item in node.get("args") or []:
            walk(item)

    walk(expr)
    return list(seen)


def evaluate(expr: dict, facts: dict, categories: dict | None = None, soften: bool = False) -> Value:
    """Evaluate an expression under three-valued logic.

    Args:
        expr: DSL expression.
        facts: Fact values; missing or None means unknown.
        categories: Fact name to ``"action"`` or ``"context"``.
        soften: Treat a False ``is_true`` on an action fact as unknown.

    Returns:
        Truth value with the unknown and falsifying fields.
    """
    op = expr["op"]
    if op == "const":
        return Value(bool(expr["value"]))
    if op in FIELD_OPS:
        name, val = expr["field"], facts.get(expr["field"])
        if val is None:
            return Value(None, [name])
        if op in ("is_true", "is_false"):
            if soften and op == "is_true" and val is False and (categories or {}).get(name) == "action":
                return Value(None, [name])
            result = (val is True) if op == "is_true" else (val is False)
        else:
            try:
                result = COMPARISONS[op](val, expr["value"])
            except TypeError:
                return Value(None, [name])
        return Value(result, false=[] if result else [name])
    if op == "not":
        inner = evaluate(expr["arg"], facts, categories, soften)
        if inner.value is None:
            return inner
        return Value(not inner.value, inner.unknown, [] if not inner.value else referenced_fields(expr["arg"]))
    if op == "and":
        unknown, false = [], []
        any_false = any_unknown = False
        for sub in expr["args"]:
            res = evaluate(sub, facts, categories, soften)
            if res.value is False:
                any_false = True
                false += res.false
            elif res.value is None:
                any_unknown = True
                unknown += res.unknown
        if any_false:
            return Value(False, false=false)
        return Value(None, unknown) if any_unknown else Value(True)
    if op == "or":
        unknown, false = [], []
        any_unknown = False
        for sub in expr["args"]:
            res = evaluate(sub, facts, categories, soften)
            if res.value is True:
                return Value(True, res.unknown)
            if res.value is None:
                any_unknown = True
                unknown += res.unknown
            else:
                false += res.false
        return Value(None, unknown) if any_unknown else Value(False, false=false)
    if op == "implies":
        ant = evaluate(expr["if"], facts, categories, soften)
        if ant.value is False:
            return Value(True)
        cons = evaluate(expr["then"], facts, categories, soften)
        if ant.value is None and cons.value is True:
            return Value(True)
        if ant.value is None or cons.value is None:
            return Value(None, ant.unknown + cons.unknown)
        return Value(cons.value, false=cons.false if cons.value is False else [])
    raise ValueError(f"Unknown op: {op!r}")


def check(rule: dict, facts: dict, categories: dict | None = None) -> Outcome:
    """Decide a rule for one candidate action.

    Args:
        rule: Rule with ``when`` and ``then`` expressions.
        facts: Fact values; missing or None means unknown.
        categories: Fact name to ``"action"`` or ``"context"``.

    Returns:
        PASS (``True``), FAIL (``False``) or abstain (``None``) with the fields involved.
    """
    missing = [name for name in referenced_fields(rule["when"]) if facts.get(name) is None]
    if missing:
        return Outcome(None, missing)
    when = evaluate(rule["when"], facts, categories)
    if when.value is False:
        return Outcome(True)
    if when.value is None:
        return Outcome(None, list(dict.fromkeys(when.unknown)))
    then = evaluate(rule["then"], facts, categories, soften=True)
    if then.value is None:
        return Outcome(None, list(dict.fromkeys(then.unknown)))
    return Outcome(then.value, violating=list(dict.fromkeys(then.false)) if then.value is False else [])
