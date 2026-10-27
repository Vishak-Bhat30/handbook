# Pathfinder - blind interwhen results

Single scored run per task (4 attempts), verifiers built blind (SOP + instruction + seed data + baseline
trajectories, never graders/rubrics/scores) and frozen before the run. Agent: Haiku 5.5 (OpenHands).
Mean = mean reward x100; sP@1 = share of attempts passing every rubric; sP@4 / sP^4 = any / all of the
attempts pass every rubric. Attempts where the model API failed before the first tool call are excluded.

| Task | Opus 4.8 mean (sP@1) | Haiku 5.5 mean (sP@1) | Haiku + interwhen mean (sP@1) | Delta vs Haiku | sP@4 | sP^4 | Rubrics passed (Haiku -> interwhen) | n (H/I) | SOP paragraphs / verifiable / rules |
|---|---|---|---|---|---|---|---|---|---|
| 073e602b | 82.1 (0.0) | 79.3 (0.0) | **86.8** (0.0) | +7.5 | 0.0 | 0.0 | 75/100 -> 83/100 | 4/4 | 429 / 37 / 14 |
| 1d8667fc | 85.0 (25.0) | 26.7 (0.0) | **60.0** (0.0) | +33.3 | 0.0 | 0.0 | 8/20 -> 12/20 | 6/4 | 329 / 16 / 8 |
| 9d274282 | 83.6 (25.0) | 67.9 (0.0) | **22.1** (0.0) | -45.7 | 0.0 | 0.0 | 5/20 -> 3/5 | 4/4 | 400 / 17 / 8 |
| a25684b9 | 91.7 (50.0) | 95.8 (75.0) | **100.0** (100.0) | +4.2 | 100.0 | 100.0 | 23/24 -> 24/24 | 4/4 | 412 / 15 / 9 |
| a70deabc | 52.4 (0.0) | 38.1 (0.0) | **71.4** (0.0) | +33.3 | 0.0 | 0.0 | 8/28 -> 20/28 | 4/4 | 403 / 19 / 14 |
| bbf1a560 | 65.0 (0.0) | 85.0 (25.0) | **80.0** (0.0) | -5.0 | 0.0 | 0.0 | 34/40 -> 32/40 | 4/4 | 352 / 13 / 10 |
| c01deb6e | 78.5 (0.0) | 77.9 (0.0) | **86.0** (0.0) | +8.1 | 0.0 | 0.0 | 67/108 -> 83/108 | 4/4 | 429 / 61 / 22 |
| ec505b6b | 82.9 (0.0) | 56.3 (0.0) | **98.0** (25.0) | +41.7 | 100.0 | 0.0 | 42/76 -> 73/76 | 4/4 | 427 / 36 / 18 |

| Domain aggregate | Opus 4.8 | Haiku 5.5 | Haiku + interwhen |
|---|---|---|---|
| Mean reward | 77.64 | 65.88 | 75.55 |
| Strict Pass@1 | 12.50 | 12.50 | 15.62 |
| Strict Pass@4 | 37.50 | 25.00 | 25.00 |
| Strict Pass^4 | 0.00 | 0.00 | 12.50 |
| Rubrics passed | 296/416 | 262/416 | 330/401 |

Tasks improved / worse / unchanged (|delta| <= 2) vs Haiku: 6 / 2 / 0.

Haiku baseline attempts that crashed mid-run (counted as reward 0): 1d8667fc x2.
