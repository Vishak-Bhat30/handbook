"""Validation of model-authored policy packages (pure Python, no model calls).

A package is ``{variables, rules, inventory, reviewer_format, extractor_format}``:
Boolean fact definitions, DSL rules quoting the source policy, a clause inventory
mapping every enforced clause to its rules, and the generated reviewer/extractor
formats whose JSON schemas have a fixed, host-checked shape.
"""

from __future__ import annotations

import hashlib
import html
import json
import keyword
import re
from copy import deepcopy

from ..dsl import COMPARISONS, referenced_fields

PACKAGE_KEYS = {"variables", "rules", "inventory", "reviewer_format", "extractor_format"}
RULE_KEYS = {"id", "title", "rationale", "source", "reference", "quote", "remediation", "when", "then"}
CATEGORIES = {"action", "context"}
INVENTORY_STATUS = {"enforced", "unobservable", "ambiguous", "non_normative"}
SHAPES = {"const": {"op", "value"}, "is_true": {"op", "field"}, "is_false": {"op", "field"},
          **{name: {"op", "field", "value"} for name in COMPARISONS},
          "and": {"op", "args"}, "or": {"op", "args"}, "not": {"op", "arg"}, "implies": {"op", "if", "then"}}


def digest(value) -> str:
    """SHA-256 of the canonical JSON encoding of ``value``."""
    text = json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def citation_text(value: str) -> str:
    """Normalize text for quote matching (HTML entities decoded, whitespace collapsed)."""
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def quoted(quote: str, policy: str) -> bool:
    """Whether ``quote`` appears literally in ``policy`` after normalization."""
    return citation_text(quote) in citation_text(policy)


def valid_identifier(value) -> bool:
    """Whether ``value`` is a lowercase snake_case name that is not a Python keyword."""
    return isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9_]*", value) is not None and not keyword.iskeyword(value)


def check_expression(expr, declared: set[str], path: str) -> None:
    """Check a DSL expression tree.

    Args:
        expr: Expression to check.
        declared: Declared fact names.
        path: Location used in error messages.

    Raises:
        ValueError: If the shape, a literal or a field reference is invalid.
    """
    if not isinstance(expr, dict) or expr.get("op") not in SHAPES or set(expr) != SHAPES[expr["op"]]:
        raise ValueError(f"{path}: invalid expression shape")
    op = expr["op"]
    if op == "const" and not isinstance(expr["value"], bool):
        raise ValueError(f"{path}: const needs a bool")
    if "field" in expr and expr["field"] not in declared:
        raise ValueError(f"{path}: undeclared field {expr['field']!r}")
    if op in COMPARISONS and not isinstance(expr["value"], (str, int, float, bool, type(None))):
        raise ValueError(f"{path}: comparison requires a scalar literal")
    if op in ("and", "or"):
        if not isinstance(expr["args"], list) or not expr["args"]:
            raise ValueError(f"{path}: {op} needs args")
        for index, arg in enumerate(expr["args"]):
            check_expression(arg, declared, f"{path}.{op}[{index}]")
    elif op == "not":
        check_expression(expr["arg"], declared, f"{path}.not")
    elif op == "implies":
        check_expression(expr["if"], declared, f"{path}.implies.if")
        check_expression(expr["then"], declared, f"{path}.implies.then")


def validate_rules(variables, rules, policy: str | None, *, allow_empty: bool = False) -> None:
    """Check fact definitions and DSL rules.

    Args:
        variables: Fact definitions (``name``, ``type``, ``category``, ``description``).
        rules: DSL rules.
        policy: Source policy that rule quotes must come from; None skips quote checks.
        allow_empty: Accept an empty rule list when no facts are declared.

    Raises:
        ValueError: On the first invalid fact or rule.
    """
    if not isinstance(variables, list) or not isinstance(rules, list):
        raise ValueError("variables and rules must both be lists")
    declared: set[str] = set()
    for index, variable in enumerate(variables):
        if not isinstance(variable, dict) or set(variable) != {"name", "type", "category", "description"}:
            raise ValueError(f"variable {index} malformed")
        name = variable["name"]
        if not valid_identifier(name) or name in declared or name.startswith("model_"):
            raise ValueError(f"variable {index} has an unsafe or duplicate name")
        if variable["type"] != "bool" or not isinstance(variable["description"], str) or not variable["description"].strip():
            raise ValueError(f"variable {name!r} needs bool type and description")
        if variable["category"] not in CATEGORIES or not name.startswith(variable["category"] + "_"):
            raise ValueError(f"variable {name!r} needs a category and matching prefix")
        declared.add(name)
    if not rules:
        if not allow_empty or variables:
            raise ValueError("Empty rules require explicit approval and no variables")
        return
    seen_ids: set[str] = set()
    seen_logic: dict[tuple[str, str], str] = {}
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict) or set(rule) != RULE_KEYS:
            raise ValueError(f"rule {index} has invalid keys")
        if not valid_identifier(rule["id"]) or rule["id"] == "facts" or rule["id"] in seen_ids:
            raise ValueError(f"rule {index} has an unsafe, reserved or duplicate id")
        seen_ids.add(rule["id"])
        if any(not isinstance(rule[key], str) or not rule[key].strip() for key in RULE_KEYS - {"when", "then"}):
            raise ValueError(f"rule {rule['id']!r} has an empty text field")
        if policy is not None and not quoted(rule["quote"], policy):
            raise ValueError(f"rule {rule['id']!r} quote not in policy")
        for side in ("when", "then"):
            check_expression(rule[side], declared, f"rule {rule['id']}.{side}")
        if rule["when"]["op"] == "const":
            raise ValueError(f"rule {rule['id']!r}: when is constant")
        if rule["then"] == {"op": "const", "value": True}:
            raise ValueError(f"rule {rule['id']!r}: then is const true, rule can never fail")
        both = set(referenced_fields(rule["when"])) & set(referenced_fields(rule["then"]))
        if both:
            raise ValueError(f"rule {rule['id']!r}: {sorted(both)} appears in both when and then")
        logic = (json.dumps(rule["when"], sort_keys=True), json.dumps(rule["then"], sort_keys=True))
        if logic in seen_logic:
            raise ValueError(f"rule {rule['id']!r} duplicates {seen_logic[logic]!r}")
        seen_logic[logic] = rule["id"]


def object_schema(properties: dict) -> dict:
    """Closed JSON-schema object requiring every property."""
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def format_schema(spec: dict, variables: list, kind: str) -> dict:
    """Fixed response schema of a generated format.

    Args:
        spec: Generated reviewer or extractor format (its response key names).
        variables: Fact definitions.
        kind: ``"reviewer"`` or ``"extractor"``.

    Returns:
        JSON schema the format's ``response_schema`` must match.
    """
    if kind == "reviewer":
        return object_schema({spec["decision_key"]: {"type": "boolean"},
                              spec["issues_key"]: {"type": "array", "items": {"type": "string"}}})
    names = [variable["name"] for variable in variables]
    return object_schema({spec["facts_key"]: object_schema({n: {"type": ["boolean", "null"]} for n in names}),
                          spec["evidence_key"]: object_schema({n: {"type": "string"} for n in names})})


def schema_shape(value):
    """Schema with annotations dropped and type/required lists sorted, for comparison."""
    if isinstance(value, dict):
        return {key: sorted(item) if key in {"required", "type"} and isinstance(item, list) else schema_shape(item)
                for key, item in value.items() if key not in {"description", "title"}}
    return [schema_shape(item) for item in value] if isinstance(value, list) else value


def validate_format(spec, variables: list, kind: str) -> None:
    """Check a generated reviewer or extractor format.

    Args:
        spec: Generated format.
        variables: Fact definitions.
        kind: ``"reviewer"`` or ``"extractor"``.

    Raises:
        ValueError: If keys, instructions or the response schema are invalid.
    """
    keys = ("decision_key", "issues_key") if kind == "reviewer" else ("facts_key", "evidence_key")
    if not isinstance(spec, dict) or set(spec) != {"instructions", "response_schema", *keys}:
        raise ValueError(f"Malformed generated {kind} format")
    if not isinstance(spec["instructions"], str) or not spec["instructions"].strip():
        raise ValueError("Generated instructions are empty")
    names = [spec[key] for key in keys]
    if any(not isinstance(name, str) or not name.isidentifier() for name in names) or len(set(names)) != 2:
        raise ValueError("Generated response keys must be distinct identifiers")
    if schema_shape(spec["response_schema"]) != schema_shape(format_schema(spec, variables, kind)):
        raise ValueError(f"Generated response schema violates the fixed {kind} interface")


def validate_package(package, policy: str) -> None:
    """Check a complete package against its source policy.

    Args:
        package: Policy package.
        policy: Source policy text.

    Raises:
        ValueError: If facts, rules, formats or the clause inventory are invalid.
    """
    if not isinstance(package, dict) or set(package) != PACKAGE_KEYS:
        raise ValueError("Package needs variables, rules, inventory and both formats")
    validate_rules(package["variables"], package["rules"], policy, allow_empty=True)
    for kind in ("reviewer", "extractor"):
        validate_format(package[kind + "_format"], package["variables"], kind)
    rules = {rule["id"] for rule in package["rules"]}
    mapped, ids = set(), set()
    if not isinstance(package["inventory"], list) or not package["inventory"]:
        raise ValueError("Policy clause inventory is required, including empty-policy justification")
    for item in package["inventory"]:
        if (not isinstance(item, dict) or set(item) != {"id", "quote", "status", "rule_ids", "reason"}
                or any(not isinstance(item[key], str) or not item[key].strip() for key in ("id", "quote", "reason"))
                or item["id"] in ids or not quoted(item["quote"], policy) or item["status"] not in INVENTORY_STATUS
                or not isinstance(item["rule_ids"], list) or any(name not in rules for name in item["rule_ids"])
                or bool(item["rule_ids"]) != (item["status"] == "enforced")):
            raise ValueError("Invalid policy-to-rule inventory")
        ids.add(item["id"])
        mapped.update(item["rule_ids"])
    if mapped != rules:
        raise ValueError("Every verifier needs an inventory mapping")


def extraction_schema(package: dict, names: list[str]) -> dict:
    """Extractor response schema restricted to the requested facts.

    Args:
        package: Policy package.
        names: Fact names to extract.

    Returns:
        The package's extractor schema narrowed to ``names``.

    Raises:
        ValueError: If a name is not a declared fact.
    """
    spec = package["extractor_format"]
    if set(names) - {variable["name"] for variable in package["variables"]}:
        raise ValueError("Unknown requested fact")
    schema = deepcopy(spec["response_schema"])
    for key in (spec["facts_key"], spec["evidence_key"]):
        properties = schema["properties"][key]["properties"]
        schema["properties"][key]["properties"] = {name: properties[name] for name in names}
        schema["properties"][key]["required"] = list(names)
    return schema


def parse_extraction(package: dict, names: list[str], response) -> tuple[dict, dict]:
    """Validate an extractor reply.

    Args:
        package: Policy package.
        names: Requested fact names.
        response: Parsed extractor JSON.

    Returns:
        ``(facts, evidence)``: Boolean-or-None facts and their supporting evidence.

    Raises:
        ValueError: If the envelope, values or evidence violate the contract.
    """
    spec = package["extractor_format"]
    keys = (spec["facts_key"], spec["evidence_key"])
    if not isinstance(response, dict) or set(response) != set(keys):
        raise ValueError("Extractor response envelope changed")
    facts, evidence = (response[key] for key in keys)
    if (not isinstance(facts, dict) or not isinstance(evidence, dict) or set(facts) != set(names)
            or set(evidence) != set(names)
            or any(value is not None and type(value) is not bool for value in facts.values())
            or any(not isinstance(value, str) for value in evidence.values())
            or any(value is not None and not evidence[name].strip() for name, value in facts.items())):
        raise ValueError("Extractor facts/evidence violate the generated contract")
    return facts, evidence
