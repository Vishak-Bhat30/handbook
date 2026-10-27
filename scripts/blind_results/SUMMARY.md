# Blind interwhen - dataset summary

Protocol: `tmp/blind/algo_blind.md` (Steps 0-4 by a blind builder: SOP, instruction, seed data and Haiku
baseline trajectories only; no graders, rubrics or scores), verifiers frozen (sha256 in `tmp/blind/frozen/`)
before one scored run of 4 attempts per task. No re-runs after scoring except attempts that never reached
the agent (Docker / model-API failures). Agent model: Haiku 5.5. Opus 4.8 = earlier baseline run
(`jobs/baseline-claude-opus-4.8-max-20260907`). Per-task tables: one md file per domain in this folder.

## Per domain (mean of per-task values)

| Domain | Tasks | Opus 4.8 mean | Haiku 5.5 mean | Haiku + interwhen mean | Delta | Haiku sP@1 | Interwhen sP@1 | Interwhen sP^4 | Improved / worse / same |
|---|---|---|---|---|---|---|---|---|---|
| [CareIG](careig.md) | 7 | 70.52 | 76.41 | **86.91** | +10.51 | 10.7 | 32.1 | 28.6 | 4 / 0 / 3 |
| [Pathfinder](pathfinder.md) | 8 | 77.64 | 65.88 | **75.55** | +9.67 | 12.5 | 15.6 | 12.5 | 6 / 2 / 0 |
| [Vanguard](vanguard.md) | 7 | 67.88 | 58.24 | **59.65** | +1.42 | 0.0 | 0.0 | 0.0 | 5 / 2 / 0 |
| [Mojave](mojave.md) | 6 | 80.57 | 79.06 | **92.70** | +13.64 | 4.2 | 29.2 | 16.7 | 4 / 0 / 2 |
| [Gear Systems](gear_systems.md) | 6 | 58.02 | 51.64 | **70.50** | +18.86 | 4.2 | 8.3 | 0.0 | 4 / 0 / 2 |
| [Prairie Creamery](prairie_creamery.md) | 6 | 62.93 | 63.06 | **76.62** | +13.56 | 0.0 | 4.2 | 0.0 | 6 / 0 / 0 |
| [Ridgeline](ridgeline.md) | 7 | 82.05 | 65.11 | **94.87** | +29.76 | 21.4 | 53.6 | 42.9 | 7 / 0 / 0 |
| [Crestwood](crestwood.md) | 6 | 83.88 | 68.47 | **86.34** | +17.87 | 16.7 | 12.5 | 0.0 | 4 / 1 / 1 |
| [Sunshine](sunshine.md) | 6 | 85.51 | 81.14 | **84.72** | +3.58 | 4.2 | 16.7 | 16.7 | 3 / 1 / 2 |
| [Meridian](meridian.md) | 6 | 85.52 | 82.17 | **93.35** | +11.17 | 25.0 | 45.8 | 33.3 | 5 / 0 / 1 |

## Whole dataset

Tasks: 65. Improved / worse / unchanged vs Haiku: 48 / 6 / 11.

| Metric | Opus 4.8 | Haiku 5.5 | Haiku + interwhen |
|---|---|---|---|
| Mean reward (task mean) | 75.43 | 68.90 | 81.84 |
| Strict Pass@1 | 13.46 | 10.00 | 21.92 |
| Strict Pass@4 | 27.69 | 26.15 | 29.23 |
| Strict Pass^4 | 3.08 | 0.00 | 15.38 |
| Rubrics passed | 2346/3296 | 2139/3132 | 2608/3205 |
| Scored attempts | 260 | 262 | 260 |

## Caveats

- Attempts that crashed mid-run with "Message exceeds token limit" count as reward 0 in both arms (Haiku: 2071c562 x4, 2deeab56 x2, 6d4d0f70 x1, 74170ae1 x4, 1d8667fc x2; interwhen: 74170ae1 x4, 9d274282 x3).
  Excluding those 6 tasks (59 left): Opus 75.49, Haiku 72.89, interwhen 84.49 mean reward; sP@1 13.6 / 10.2 / 22.5.
- Rubric totals differ between arms because crashed attempts produce no rubric output.
- Builders read the Haiku baseline trajectories (behaviour, never scores) for replay validation.
- Opus 4.8 numbers come from an earlier run whose served model could not be verified by the proxy guard.
