"""Write per-domain and dataset result tables for the blind interwhen experiment from summary.json.

    python3 summary.py && python3 report.py      -> REPO/scripts/blind_results/{<domain>.md, SUMMARY.md}
"""
import json
from collections import defaultdict
from pathlib import Path

REPO = Path("/mnt/datadrive/t-bhatvishak/Vishak_Handbook")
PKG = REPO / "docker/openhands-runner/interwhen_sop"
OUT = REPO / "scripts/blind_results"
R = json.load(open(Path(__file__).with_name("summary.json")))
ORDER = ["CareIG", "Pathfinder", "Vanguard", "Mojave", "Gear Systems", "Prairie Creamery", "Ridgeline", "Crestwood",
         "Sunshine", "Meridian"]


def triage(task):
    p = json.load(open(PKG / f"tasks/{task}/triage.json"))["paragraphs"]
    ver = [x for x in p if x["verdict"] == "verifiable"]
    return len(p), len(ver), len({v for x in ver for v in x.get("verifiers", [])})


def cell(s, key="mean"):
    return "-" if not s else f"{s[key]:.1f}"


def agg(rows, k):
    xs = [r[k] for r in rows if r[k]]
    if not xs:
        return None
    n = len(xs)
    rub = (sum(x["rub"][0] for x in xs), sum(x["rub"][1] for x in xs))
    return {"tasks": n, "mean": sum(x["mean"] for x in xs) / n, "sp1": sum(x["sp1"] for x in xs) / n,
            "spk": sum(x["spk"] for x in xs) / n, "spK": sum(x["spK"] for x in xs) / n, "rub": rub,
            "trials": sum(x["n"] for x in xs)}


def wins(rows):
    w = l = t = 0
    for r in rows:
        if r["blind"] and r["haiku"]:
            d = r["blind"]["mean"] - r["haiku"]["mean"]
            w, l, t = w + (d > 2), l + (d < -2), t + (abs(d) <= 2)
    return w, l, t


def domain_md(dom, items):
    rows = [v for _, v in items]
    L = [f"# {dom} - blind interwhen results", "",
         "Single scored run per task (4 attempts), verifiers built blind (SOP + instruction + seed data + baseline",
         "trajectories, never graders/rubrics/scores) and frozen before the run. Agent: Haiku 5.5 (OpenHands).",
         "Mean = mean reward x100; sP@1 = share of attempts passing every rubric; sP@4 / sP^4 = any / all of the",
         "attempts pass every rubric. Attempts where the model API failed before the first tool call are excluded.", "",
         "| Task | Opus 4.8 mean (sP@1) | Haiku 5.5 mean (sP@1) | Haiku + interwhen mean (sP@1) | Delta vs Haiku | sP@4 | sP^4 | Rubrics passed (Haiku -> interwhen) | n (H/I) | SOP paragraphs / verifiable / rules |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for t, v in items:
        o, h, b = v["opus"], v["haiku"], v["blind"]
        d = f"{b['mean'] - h['mean']:+.1f}" if b and h else "-"
        para, ver, rules = triage(t)
        rub = f"{h['rub'][0]}/{h['rub'][1]} -> {b['rub'][0]}/{b['rub'][1]}" if b and h else "-"
        L.append(f"| {t[-8:]} | {cell(o)} ({cell(o, 'sp1')}) | {cell(h)} ({cell(h, 'sp1')}) | **{cell(b)}** ({cell(b, 'sp1')}) "
                 f"| {d} | {cell(b, 'spk')} | {cell(b, 'spK')} | {rub} | {h['n'] if h else 0}/{b['n'] if b else 0} | {para} / {ver} / {rules} |")
    a = {k: agg(rows, k) for k in ("opus", "haiku", "blind")}
    w, l, t = wins(rows)
    L += ["", "| Domain aggregate | Opus 4.8 | Haiku 5.5 | Haiku + interwhen |", "|---|---|---|---|"]
    for key, lab in [("mean", "Mean reward"), ("sp1", "Strict Pass@1"), ("spk", "Strict Pass@4"), ("spK", "Strict Pass^4")]:
        L.append(f"| {lab} | " + " | ".join(f"{a[k][key]:.2f}" if a[k] else "-" for k in ("opus", "haiku", "blind")) + " |")
    L.append("| Rubrics passed | " + " | ".join(f"{a[k]['rub'][0]}/{a[k]['rub'][1]}" if a[k] else "-" for k in ("opus", "haiku", "blind")) + " |")
    L += ["", f"Tasks improved / worse / unchanged (|delta| <= 2) vs Haiku: {w} / {l} / {t}.", ""]
    crash = [(t[-8:], v["haiku_crash"]) for t, v in items if v["haiku_crash"]]
    if crash:
        L.append("Haiku baseline attempts that crashed mid-run (counted as reward 0): "
                 + ", ".join(f"{t} x{n}" for t, n in crash) + ".")
    return "\n".join(L) + "\n", a, (w, l, t)


def main():
    OUT.mkdir(exist_ok=True)
    by = defaultdict(list)
    for t, v in sorted(R.items()):
        by[v["domain"]].append((t, v))
    S = ["# Blind interwhen - dataset summary", "",
         "Protocol: `tmp/blind/algo_blind.md` (Steps 0-4 by a blind builder: SOP, instruction, seed data and Haiku",
         "baseline trajectories only; no graders, rubrics or scores), verifiers frozen (sha256 in `tmp/blind/frozen/`)",
         "before one scored run of 4 attempts per task. No re-runs after scoring except attempts that never reached",
         "the agent (Docker / model-API failures). Agent model: Haiku 5.5. Opus 4.8 = earlier baseline run",
         "(`jobs/baseline-claude-opus-4.8-max-20260907`). Per-task tables: one md file per domain in this folder.", "",
         "## Per domain (mean of per-task values)", "",
         "| Domain | Tasks | Opus 4.8 mean | Haiku 5.5 mean | Haiku + interwhen mean | Delta | Haiku sP@1 | Interwhen sP@1 | Interwhen sP^4 | Improved / worse / same |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    allrows = []
    for dom in ORDER:
        items = by.get(dom, [])
        if not items:
            continue
        md, a, (w, l, t) = domain_md(dom, items)
        (OUT / f"{dom.lower().replace(' ', '_')}.md").write_text(md)
        allrows += [v for _, v in items]
        S.append(f"| [{dom}]({dom.lower().replace(' ', '_')}.md) | {len(items)} | {a['opus']['mean']:.2f} | {a['haiku']['mean']:.2f} "
                 f"| **{a['blind']['mean']:.2f}** | {a['blind']['mean'] - a['haiku']['mean']:+.2f} | {a['haiku']['sp1']:.1f} "
                 f"| {a['blind']['sp1']:.1f} | {a['blind']['spK']:.1f} | {w} / {l} / {t} |")
    a = {k: agg(allrows, k) for k in ("opus", "haiku", "blind")}
    w, l, t = wins(allrows)
    S += ["", "## Whole dataset", "", f"Tasks: {len(allrows)}. Improved / worse / unchanged vs Haiku: {w} / {l} / {t}.", "",
          "| Metric | Opus 4.8 | Haiku 5.5 | Haiku + interwhen |", "|---|---|---|---|"]
    for key, lab in [("mean", "Mean reward (task mean)"), ("sp1", "Strict Pass@1"), ("spk", "Strict Pass@4"),
                     ("spK", "Strict Pass^4")]:
        S.append(f"| {lab} | " + " | ".join(f"{a[k][key]:.2f}" for k in ("opus", "haiku", "blind")) + " |")
    S.append("| Rubrics passed | " + " | ".join(f"{a[k]['rub'][0]}/{a[k]['rub'][1]}" for k in ("opus", "haiku", "blind")) + " |")
    S.append("| Scored attempts | " + " | ".join(str(a[k]["trials"]) for k in ("opus", "haiku", "blind")) + " |")
    clean = [v for v in allrows if not v["haiku_crash"] and not v["blind_crash"]]
    c = {k: agg(clean, k) for k in ("opus", "haiku", "blind")}
    S += ["", "## Caveats", "",
          "- Attempts that crashed mid-run with \"Message exceeds token limit\" count as reward 0 in both arms "
          "(Haiku: " + ", ".join(f"{t[-8:]} x{v['haiku_crash']}" for t, v in R.items() if v["haiku_crash"]) +
          "; interwhen: " + ", ".join(f"{t[-8:]} x{v['blind_crash']}" for t, v in R.items() if v["blind_crash"]) + ").",
          f"  Excluding those {len(allrows) - len(clean)} tasks ({len(clean)} left): Opus {c['opus']['mean']:.2f}, "
          f"Haiku {c['haiku']['mean']:.2f}, interwhen {c['blind']['mean']:.2f} mean reward; sP@1 "
          f"{c['opus']['sp1']:.1f} / {c['haiku']['sp1']:.1f} / {c['blind']['sp1']:.1f}.",
          "- Rubric totals differ between arms because crashed attempts produce no rubric output.",
          "- Builders read the Haiku baseline trajectories (behaviour, never scores) for replay validation.",
          "- Opus 4.8 numbers come from an earlier run whose served model could not be verified by the proxy guard."]
    (OUT / "SUMMARY.md").write_text("\n".join(S) + "\n")
    print("\n".join(S))


if __name__ == "__main__":
    main()
