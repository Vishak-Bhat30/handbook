"""Per-task / per-domain / dataset metrics: Opus 4.8 baseline, Haiku 5.5 baseline, Haiku 5.5 + blind interwhen.

Trials that ran the agent but produced no reward count as reward 0 (all rubrics failed); infra failures
(container / network never created) are excluded.
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path("/mnt/datadrive/t-bhatvishak/Vishak_Handbook")
INFRA = re.compile(r"non-overlapping IPv4|failed to create network|Error response from daemon|"
                   r"Cannot connect to the Docker daemon|No such container|Docker compose command failed", re.I)
DOMAINS = {"medical_careig_specialty_pharmacy": "CareIG", "medical_pathfinder_billing_and_coding": "Pathfinder",
           "insurance_vanguard_shield_mutual": "Vanguard", "logistics_gear_sytems_inc": "Gear Systems",
           "logistics_prairie_star_creamery": "Prairie Creamery", "hr_ridgeline_gear_co": "Ridgeline",
           "insurance_mojave_crest_assurance_company": "Mojave", "hr_crestwood_university": "Crestwood",
           "finance_sunshine_set": "Sunshine", "finance_meridian_partners": "Meridian"}


def collect(globs):
    out, crashed = defaultdict(list), defaultdict(int)
    for g in globs:
        for job in REPO.glob(g):
            for d in job.glob("*__*"):
                cfg = d / "config.json"
                m = re.search(r"tasks/([a-z_]+_[0-9a-f]{8})", cfg.read_text()) if cfg.exists() else None
                if not m:
                    continue
                task, rp, so, exc = m.group(1), d / "verifier/reward.txt", d / "verifier/test-stdout.txt", d / "exception.txt"
                log = d / "agent/run-openhands.log"
                if log.exists() and not re.search(r"Tool:|ActionEvent|tool_call", log.read_text(errors="ignore")):
                    continue  # LLM timed out before the agent's first tool call: infra, not an attempt
                if rp.exists() and so.exists():
                    flags = re.findall(r"^\s+\[(PASS|FAIL)\]", so.read_text(), flags=re.M)
                    out[task].append((float(rp.read_text().strip()), flags.count("FAIL"), flags.count("PASS"), len(flags)))
                elif exc.exists() and not INFRA.search(exc.read_text(errors="ignore")):
                    out[task].append((0.0, None, 0, None))
                    crashed[task] += 1
    return out, crashed


def stats(rows):
    if not rows:
        return None
    n = len(rows)
    strict = [f == 0 for _, f, _, _ in rows]
    return {"n": n, "mean": 100 * sum(r for r, *_ in rows) / n, "sp1": 100 * sum(strict) / n,
            "spk": 100.0 * any(strict), "spK": 100.0 * all(strict),
            "rub": (sum(p for _, _, p, _ in rows), sum(t for *_, t in rows if t))}


def main():
    opus, _ = collect(["jobs/baseline-claude-opus-4.8-max-20260907"])
    haiku, hc = collect(["jobs/baseline-haiku55-*"])
    blind, bc = collect(["jobs/blind-*"])
    res = {}
    for t in sorted(set(opus) | set(haiku) | set(blind)):
        dom = next((v for k, v in DOMAINS.items() if t.startswith(k)), None)
        if dom:
            res[t] = {"domain": dom, "opus": stats(opus.get(t, [])), "haiku": stats(haiku.get(t, [])),
                      "blind": stats(blind.get(t, [])), "haiku_crash": hc.get(t, 0), "blind_crash": bc.get(t, 0)}
    json.dump(res, open(Path(__file__).with_name("summary.json"), "w"), indent=1)
    f = lambda s: "-" if not s else f"{s['mean']:.1f} ({s['sp1']:.0f}, n={s['n']})"
    for t, r in res.items():
        print(r["domain"], t[-8:], "| opus", f(r["opus"]), "| haiku", f(r["haiku"]), "| blind", f(r["blind"]),
              "| crash h/b", r["haiku_crash"], r["blind_crash"])


if __name__ == "__main__":
    main()
