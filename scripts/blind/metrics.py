"""Per-task and aggregate metrics for Prairie jobs (task id read from each trial's config.json).

    python3 pr_metrics.py <job_dir> [<job_dir> ...]      # jobs are pooled per task
Metrics: Mean Reward, Strict Pass@1, Pass@1 N-1, Strict Pass@k, Strict Pass^k (k = trials per task).
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


def trials(jobs):
    out = defaultdict(list)
    for job in jobs:
        for d in sorted(Path(job).glob("*__*")):
            rp, so = d / "verifier" / "reward.txt", d / "verifier" / "test-stdout.txt"
            if not rp.exists() or not so.exists():
                continue
            m = re.search(r"tasks/([a-z_]+_[0-9a-f]{8})", (d / "config.json").read_text())
            if not m:
                continue
            task = m.group(1)
            flags = re.findall(r"^\s+\[(PASS|FAIL)\]", so.read_text(), flags=re.M)
            out[task].append({"reward": float(rp.read_text().strip()), "fails": flags.count("FAIL"),
                              "n": len(flags), "passed": flags.count("PASS")})
    return out


def metrics(rows):
    n = len(rows)
    strict = [r["fails"] == 0 for r in rows]
    return {"n": n, "mean": 100 * sum(r["reward"] for r in rows) / n, "sP@1": 100 * sum(strict) / n,
            "P@1N-1": 100 * sum(r["fails"] <= 1 for r in rows) / n, "sP@k": 100.0 * any(strict),
            "sP^k": 100.0 * all(strict), "rubrics": (sum(r["passed"] for r in rows), sum(r["n"] for r in rows))}


def main():
    groups = [a.split(",") for a in sys.argv[1:]]
    names = [Path(g[0]).name[:28] for g in groups]
    data = [trials(g) for g in groups]
    tasks = sorted(set().union(*data))
    print("| Task | " + " | ".join(names) + " |\n|---|" + "---|" * len(names))
    for t in tasks:
        cells = []
        for d in data:
            if t in d:
                m = metrics(d[t])
                cells.append(f"{m['mean']:.1f} (sP@1 {m['sP@1']:.0f}, n={m['n']})")
            else:
                cells.append("-")
        print(f"| {t[-8:]} | " + " | ".join(cells) + " |")
    print("\n| Metric | " + " | ".join(names) + " |\n|---|" + "---|" * len(names))
    per = [{t: metrics(d[t]) for t in d} for d in data]
    for key, lab in [("mean", "Mean Reward"), ("sP@1", "Strict Pass@1"), ("P@1N-1", "Pass@1 N−1"),
                     ("sP@k", "Strict Pass@4"), ("sP^k", "Strict Pass^4")]:
        cells = []
        for p, d in zip(per, data):
            if key in ("mean", "sP@1", "P@1N-1"):
                rows = [r for t in d for r in d[t]]
                cells.append(f"{metrics(rows)[key]:.2f}" if rows else "-")
            else:
                cells.append(f"{sum(m[key] for m in p.values()) / len(p):.2f}" if p else "-")
        print(f"| {lab} | " + " | ".join(cells) + " |")
    cells = []
    for d in data:
        rows = [r for t in d for r in d[t]]
        cells.append(f"{sum(r['passed'] for r in rows)}/{sum(r['n'] for r in rows)}")
    print("| Rubrics passed | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
