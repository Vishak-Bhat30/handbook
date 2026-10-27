"""Post-hoc failure analysis (analysis only, never fed back into frozen verifiers).

Per (task, rubric): pass counts for Opus / Haiku / Haiku+interwhen, rubric text and type; per interwhen attempt:
whether the stop hook was still refusing (findings left) when the run ended, and the number of pre blocks.
    python3 failures.py   -> failures.json + stdout summary
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path("/mnt/datadrive/t-bhatvishak/Vishak_Handbook")
ARMS = {"opus": "jobs/baseline-claude-opus-4.8-max-20260907", "haiku": "jobs/baseline-haiku55-*", "iw": "jobs/blind-*"}
LINE = re.compile(r"^\s+\[(PASS|FAIL)\]\s*([0-9a-zA-Z_-]+):\s?(.*)$", re.M)


def attempts(pattern):
    for job in REPO.glob(pattern):
        for d in job.glob("*__*"):
            cfg, so = d / "config.json", d / "verifier/test-stdout.txt"
            if not (cfg.exists() and so.exists()):
                continue
            log = d / "agent/run-openhands.log"
            if log.exists() and not re.search(r"Tool:|ActionEvent|tool_call", log.read_text(errors="ignore")):
                continue
            m = re.search(r"tasks/([a-z_]+_[0-9a-f]{8})", cfg.read_text())
            if m:
                yield m.group(1), d, {k: (s == "PASS", msg) for s, k, msg in LINE.findall(so.read_text())}


def iw_state(d):
    dec = d / "agent/interwhen/decisions.jsonl"
    if not dec.exists():
        return None
    rows = [json.loads(x) for x in dec.read_text().splitlines() if x.strip()]
    comp = [r for r in rows if r.get("stage") == "completion"]
    pre = [r for r in rows if r.get("stage") == "pre" and r.get("decision") == "deny"]
    last = comp[-1] if comp else None
    left = bool(last and last.get("decision") == "allow" and last.get("findings"))  # allowed to finish with findings
    exhausted = bool(last and last.get("budget_exhausted"))
    return {"pre_blocks": len(pre), "completion_refusals": sum(r.get("decision") == "deny" for r in comp),
            "ended_with_findings": left or exhausted,
            "left_rules": sorted({f.get("rule") for f in (last or {}).get("findings", []) or []} if (left or exhausted) else [])}


def main():
    rub_text = {}
    for f in REPO.glob("tasks/*/tests/rubrics.json"):
        for r in json.loads(f.read_text()):
            rub_text[(f.parts[-3], r["id"])] = (r.get("rubric_text", ""), r.get("criterion_type", ""))
    stats = defaultdict(lambda: {a: [0, 0] for a in ARMS})
    msgs = defaultdict(list)
    trials = []
    for arm, pat in ARMS.items():
        for task, d, res in attempts(pat):
            for rid, (ok, msg) in res.items():
                s = stats[(task, rid)][arm]
                s[0] += ok
                s[1] += 1
                if arm == "iw" and not ok:
                    msgs[(task, rid)].append(msg[:300])
            if arm == "iw":
                st = iw_state(d)
                trials.append({"task": task, "trial": d.name, "fails": sum(not ok for ok, _ in res.values()),
                               **(st or {})})
    out = []
    for (task, rid), s in stats.items():
        text, ctype = rub_text.get((task, rid), ("", ""))
        rate = {a: (s[a][0] / s[a][1] if s[a][1] else None) for a in ARMS}
        out.append({"task": task, "rubric": rid, "type": ctype, "text": text, "pass": s, "rate": rate,
                    "iw_fail_msgs": msgs.get((task, rid), [])[:2]})
    json.dump({"rubrics": out, "trials": trials}, open(Path(__file__).with_name("failures.json"), "w"), indent=1)

    def cls(r):
        h, i = r["rate"]["haiku"], r["rate"]["iw"]
        if h is None or i is None:
            return "missing"
        if i == 1 and h == 1:
            return "always passed"
        if i == 1:
            return "fixed by interwhen"
        if i < h - 0.25:
            return "regressed (worse than Haiku)"
        if i > h + 0.25:
            return "improved, still failing sometimes"
        if i == 0:
            return "never passes with interwhen"
        return "unchanged, failing sometimes"
    c = Counter(cls(r) for r in out)
    print("rubric outcomes:", dict(c))
    ended = Counter(t.get("ended_with_findings") for t in trials if t["fails"])
    print("interwhen attempts with >=1 failed rubric:", sum(ended.values()), "| ended while verifier still had findings:",
          ended.get(True, 0))
    print("pre blocks per attempt (mean):", sum(t.get("pre_blocks", 0) for t in trials) / len(trials))


if __name__ == "__main__":
    main()
