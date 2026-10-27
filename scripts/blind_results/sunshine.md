# Sunshine - blind interwhen results

Single scored run per task (4 attempts), verifiers built blind (SOP + instruction + seed data + baseline
trajectories, never graders/rubrics/scores) and frozen before the run. Agent: Haiku 5.5 (OpenHands).
Mean = mean reward x100; sP@1 = share of attempts passing every rubric; sP@4 / sP^4 = any / all of the
attempts pass every rubric. Attempts where the model API failed before the first tool call are excluded.

| Task | Opus 4.8 mean (sP@1) | Haiku 5.5 mean (sP@1) | Haiku + interwhen mean (sP@1) | Delta vs Haiku | sP@4 | sP^4 | Rubrics passed (Haiku -> interwhen) | n (H/I) | SOP paragraphs / verifiable / rules |
|---|---|---|---|---|---|---|---|---|---|
| 6b9398f4 | 92.9 (50.0) | 73.2 (0.0) | **61.4** (0.0) | -11.8 | 0.0 | 0.0 | 19/28 -> 16/28 | 4/4 | 217 / 16 / 14 |
| 7c041148 | 95.5 (0.0) | 78.9 (0.0) | **78.6** (0.0) | -0.4 | 0.0 | 0.0 | 43/56 -> 44/56 | 4/4 | 323 / 23 / 16 |
| b0b8129d | 91.7 (25.0) | 85.0 (0.0) | **90.0** (0.0) | +5.0 | 0.0 | 0.0 | 51/60 -> 54/60 | 4/4 | 358 / 33 / 14 |
| b581c493 | 90.6 (25.0) | 92.2 (0.0) | **93.8** (0.0) | +1.6 | 0.0 | 0.0 | 59/64 -> 60/64 | 4/4 | 330 / 34 / 14 |
| d9d532c1 | 67.1 (0.0) | 87.5 (25.0) | **100.0** (100.0) | +12.5 | 100.0 | 100.0 | 20/24 -> 24/24 | 4/4 | 248 / 11 / 10 |
| ebac9768 | 75.4 (0.0) | 70.0 (0.0) | **84.5** (0.0) | +14.5 | 0.0 | 0.0 | 30/52 -> 33/52 | 4/4 | 302 / 30 / 9 |

| Domain aggregate | Opus 4.8 | Haiku 5.5 | Haiku + interwhen |
|---|---|---|---|
| Mean reward | 85.51 | 81.14 | 84.72 |
| Strict Pass@1 | 16.67 | 4.17 | 16.67 |
| Strict Pass@4 | 50.00 | 16.67 | 16.67 |
| Strict Pass^4 | 0.00 | 0.00 | 16.67 |
| Rubrics passed | 234/284 | 222/284 | 231/284 |

Tasks improved / worse / unchanged (|delta| <= 2) vs Haiku: 3 / 1 / 2.

