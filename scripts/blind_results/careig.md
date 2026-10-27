# CareIG - blind interwhen results

Single scored run per task (4 attempts), verifiers built blind (SOP + instruction + seed data + baseline
trajectories, never graders/rubrics/scores) and frozen before the run. Agent: Haiku 5.5 (OpenHands).
Mean = mean reward x100; sP@1 = share of attempts passing every rubric; sP@4 / sP^4 = any / all of the
attempts pass every rubric. Attempts where the model API failed before the first tool call are excluded.

| Task | Opus 4.8 mean (sP@1) | Haiku 5.5 mean (sP@1) | Haiku + interwhen mean (sP@1) | Delta vs Haiku | sP@4 | sP^4 | Rubrics passed (Haiku -> interwhen) | n (H/I) | SOP paragraphs / verifiable / rules |
|---|---|---|---|---|---|---|---|---|---|
| 08ae3378 | 97.4 (50.0) | 99.7 (25.0) | **100.0** (100.0) | +0.3 | 100.0 | 100.0 | 45/48 -> 48/48 | 4/4 | 564 / 46 / 9 |
| 3c62ee67 | 81.9 (0.0) | 79.5 (0.0) | **78.2** (0.0) | -1.3 | 0.0 | 0.0 | 56/72 -> 55/72 | 4/4 | 417 / 26 / 11 |
| d3e312a5 | 81.2 (0.0) | 81.2 (0.0) | **81.2** (0.0) | +0.0 | 0.0 | 0.0 | 26/32 -> 26/32 | 4/4 | 461 / 76 / 10 |
| d4619b8b | 34.4 (0.0) | 83.9 (25.0) | **100.0** (100.0) | +16.1 | 100.0 | 100.0 | 39/48 -> 48/48 | 4/4 | 403 / 62 / 13 |
| ea622238 | 43.8 (0.0) | 47.5 (0.0) | **84.6** (0.0) | +37.2 | 0.0 | 0.0 | 20/56 -> 40/56 | 4/4 | 457 / 33 / 12 |
| f5947c33 | 58.5 (0.0) | 57.4 (0.0) | **75.0** (0.0) | +17.6 | 0.0 | 0.0 | 39/68 -> 51/68 | 4/4 | 442 / 40 / 9 |
| f6d19d30 | 96.4 (75.0) | 85.7 (25.0) | **89.3** (25.0) | +3.6 | 100.0 | 0.0 | 24/28 -> 25/28 | 4/4 | 297 / 11 / 12 |

| Domain aggregate | Opus 4.8 | Haiku 5.5 | Haiku + interwhen |
|---|---|---|---|
| Mean reward | 70.52 | 76.41 | 86.91 |
| Strict Pass@1 | 17.86 | 10.71 | 32.14 |
| Strict Pass@4 | 28.57 | 42.86 | 42.86 |
| Strict Pass^4 | 0.00 | 0.00 | 28.57 |
| Rubrics passed | 220/352 | 249/352 | 293/352 |

Tasks improved / worse / unchanged (|delta| <= 2) vs Haiku: 4 / 0 / 3.

