# Ridgeline - blind interwhen results

Single scored run per task (4 attempts), verifiers built blind (SOP + instruction + seed data + baseline
trajectories, never graders/rubrics/scores) and frozen before the run. Agent: Haiku 5.5 (OpenHands).
Mean = mean reward x100; sP@1 = share of attempts passing every rubric; sP@4 / sP^4 = any / all of the
attempts pass every rubric. Attempts where the model API failed before the first tool call are excluded.

| Task | Opus 4.8 mean (sP@1) | Haiku 5.5 mean (sP@1) | Haiku + interwhen mean (sP@1) | Delta vs Haiku | sP@4 | sP^4 | Rubrics passed (Haiku -> interwhen) | n (H/I) | SOP paragraphs / verifiable / rules |
|---|---|---|---|---|---|---|---|---|---|
| 2deeab56 | 96.6 (25.0) | 50.0 (50.0) | **100.0** (100.0) | +50.0 | 100.0 | 100.0 | 22/22 -> 44/44 | 4/4 | 1079 / 41 / 11 |
| 44e4c745 | 87.6 (0.0) | 94.1 (50.0) | **99.3** (100.0) | +5.3 | 100.0 | 100.0 | 72/76 -> 76/76 | 4/4 | 959 / 63 / 11 |
| 6950ff2b | 88.6 (25.0) | 79.5 (0.0) | **86.4** (0.0) | +6.8 | 0.0 | 0.0 | 35/44 -> 38/44 | 4/4 | 1002 / 96 / 17 |
| 6d4d0f70 | 61.3 (0.0) | 33.8 (0.0) | **90.0** (0.0) | +56.2 | 0.0 | 0.0 | 12/30 -> 36/40 | 4/4 | 1348 / 44 / 18 |
| 6e501f78 | 100.0 (100.0) | 92.9 (25.0) | **96.4** (50.0) | +3.6 | 100.0 | 0.0 | 24/28 -> 26/28 | 4/4 | 1326 / 60 / 16 |
| 929c1527 | 57.7 (0.0) | 39.6 (0.0) | **92.0** (25.0) | +52.3 | 100.0 | 0.0 | 14/44 -> 39/44 | 4/4 | 1346 / 108 / 25 |
| b337f86b | 82.5 (0.0) | 65.9 (25.0) | **100.0** (100.0) | +34.1 | 100.0 | 100.0 | 29/44 -> 44/44 | 4/4 | 1268 / 61 / 15 |

| Domain aggregate | Opus 4.8 | Haiku 5.5 | Haiku + interwhen |
|---|---|---|---|
| Mean reward | 82.05 | 65.11 | 94.87 |
| Strict Pass@1 | 21.43 | 21.43 | 53.57 |
| Strict Pass@4 | 42.86 | 57.14 | 71.43 |
| Strict Pass^4 | 14.29 | 0.00 | 42.86 |
| Rubrics passed | 256/320 | 208/288 | 303/320 |

Tasks improved / worse / unchanged (|delta| <= 2) vs Haiku: 7 / 0 / 0.

Haiku baseline attempts that crashed mid-run (counted as reward 0): 2deeab56 x2, 6d4d0f70 x1.
