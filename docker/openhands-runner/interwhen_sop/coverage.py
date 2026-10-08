"""Map every parsed SOP paragraph to the verifier(s) that enforce it.

    python3 -m interwhen_sop.coverage logistics_gear_sytems_inc_9b60992d

Writes tasks/<task>/clause_map.json. Paragraphs are labelled:
  enforced        - cited as an anchor by an executable task rule
  enforced_generic- compiled into a paragraph-level check (message/email formats, column tables, prohibitions)
  data            - parsed and used as input by rules (templates, contacts, holidays, file lists)
  context         - overview/definitions/governance text with no actionable instruction
  not_observable  - instructions about timing, physical handling, phone calls or other people's actions,
                    which no tool call in this environment can show
  not_enforced    - actionable SOP text with no verifier
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter

from . import config, framework, sop_generic, sopdata

CONTEXT_SECTIONS = ("0", "1", "2.1", "2.3", "3", "19.1", "19.3", "19.4", "20", "22")
DATA_SECTIONS = {"2.2": "holiday calendar for business-day counting",
                 "4.1": "SOP contact directory", "4.2": "SOP contact directory"}
# Column tables and record rules compiled into generic.records (sop_generic.DOMAINS / receiving / inventory checks).
GENERIC_RECORD_SECTIONS = ("8.1", "10.2", "10.3", "10.4", "10.5", "10.7", "11.8", "12.8", "12.9", "13.1", "13.2",
                           "13.3", "14.8")
GENERIC_PROHIBITIONS = {"21.1": ("1.", "2.", "3."), "21.2": ("6.", "7.", "10."), "21.3": ("13.", "14."),
                        "21.4": ("20.",)}
NOT_OBSERVABLE = re.compile(
    r"within \d+ (minutes|hours)|no later than|\b\d{1,2}:\d{2}\b|at the start of|end of (the )?shift|by phone|"
    r"\bphone\b|physically|photograph|forklift|\bPPE\b|walk|in person|the Dock Crew (will|holds|uses|meets)|"
    r"Curtis .* (will|records)|Theo .* will|Maribel .* will|Joon-ho .* will", re.I)


def _in(section: str, prefixes: tuple[str, ...]) -> bool:
    return any(section == p or section.startswith(p + ".") for p in prefixes)


def build(task: str) -> dict:
    sop = sopdata.load(task)
    rules = framework.load_rules(task)
    enforced: dict[str, list[str]] = {}
    generic_ids = set(r.id for r in sop_generic.RULES)
    for r in rules:
        for pid in framework.anchor_ids(sop, r):
            enforced.setdefault(pid, []).append(r.id)
    compiled = sop_generic.compiled_paragraph_ids(sop)
    t31 = set(sop.templates.get("31", {}).get("paragraph_ids", [])) if any(
        r.id == "tier4.request_uses_template31" for r in rules) else set()
    placeholder_rule = "comms.no_unfilled_placeholders"
    rows = []
    for p in sop.paragraphs:
        pid, sec, text = p["id"], p["section"], p["text"]
        entry = {"id": pid, "section": sec, "kind": p["kind"], "text": text}
        task_rules = [x for x in enforced.get(pid, []) if x not in generic_ids]
        if task_rules:
            entry.update(status="enforced", rules=enforced[pid])
        elif pid in t31:
            entry.update(status="enforced", rules=["tier4.request_uses_template31"],
                         note="Template 31 text checked line-by-line")
        elif pid in compiled or pid in enforced:
            entry.update(status="enforced_generic", rules=[compiled.get(pid)] if pid in compiled else enforced[pid])
        elif p["kind"] == "heading" or _in(sec, CONTEXT_SECTIONS):
            entry.update(status="context", rules=[])
        elif sec in DATA_SECTIONS:
            entry.update(status="data", rules=[], note=DATA_SECTIONS[sec])
        elif sec.startswith("23"):
            entry.update(status="data", rules=[placeholder_rule, "generic.email_template"],
                         note="template text: placeholder check + template conformance when the template is used")
        elif _in(sec, GENERIC_RECORD_SECTIONS):
            entry.update(status="enforced_generic", rules=["generic.records"])
        elif sec in GENERIC_PROHIBITIONS and text.startswith(GENERIC_PROHIBITIONS[sec]):
            entry.update(status="enforced_generic", rules=["generic.records / generic.* prohibition checks"])
        elif NOT_OBSERVABLE.search(text):
            entry.update(status="not_observable", rules=[])
        else:
            entry.update(status="not_enforced", rules=[])
        rows.append(entry)
    counts = Counter(r["status"] for r in rows)
    by_rule = Counter(rid for r in rows for rid in r["rules"])
    return {"task": task, "paragraphs": len(rows), "counts": dict(counts), "rules": dict(by_rule),
            "rule_sources": {r.id: r.source for r in rules}, "clauses": rows}


def main() -> None:
    task = sys.argv[1]
    data = build(task)
    out = config.TASKS_DIR / task / "clause_map.json"
    out.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    print(json.dumps({k: data[k] for k in ("paragraphs", "counts", "rules")}, indent=1))
    print(f"-> {out}")


if __name__ == "__main__":
    main()
