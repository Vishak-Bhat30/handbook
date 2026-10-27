# Meridian - blind interwhen results

Single scored run per task (4 attempts), verifiers built blind (SOP + instruction + seed data + baseline
trajectories, never graders/rubrics/scores) and frozen before the run. Agent: Haiku 5.5 (OpenHands).
Mean = mean reward x100; sP@1 = share of attempts passing every rubric; sP@4 / sP^4 = any / all of the
attempts pass every rubric. Attempts where the model API failed before the first tool call are excluded.

| Task | Opus 4.8 mean (sP@1) | Haiku 5.5 mean (sP@1) | Haiku + interwhen mean (sP@1) | Delta vs Haiku | sP@4 | sP^4 | Rubrics passed (Haiku -> interwhen) | n (H/I) | SOP paragraphs / verifiable / rules |
|---|---|---|---|---|---|---|---|---|---|
| 158b9045 | 87.0 (0.0) | 93.7 (0.0) | **99.0** (0.0) | +5.3 | 0.0 | 0.0 | 77/100 -> 89/100 | 4/4 | 296 / 47 / 12 |
| 19d57538 | 100.0 (100.0) | 97.2 (75.0) | **100.0** (100.0) | +2.8 | 100.0 | 100.0 | 35/36 -> 36/36 | 4/4 | 273 / 24 / 8 |
| 331accf1 | 81.6 (0.0) | 60.5 (0.0) | **92.6** (0.0) | +32.2 | 0.0 | 0.0 | 41/76 -> 64/76 | 4/4 | 242 / 33 / 23 |
| 4dace65e | 68.6 (0.0) | 85.9 (25.0) | **98.4** (75.0) | +12.5 | 100.0 | 0.0 | 55/64 -> 63/64 | 4/4 | 312 / 46 / 12 |
| a0895480 | 90.6 (25.0) | 87.5 (50.0) | **100.0** (100.0) | +12.5 | 100.0 | 100.0 | 28/32 -> 32/32 | 4/4 | 293 / 56 / 17 |
| cc2fc143 | 85.4 (0.0) | 68.2 (0.0) | **70.0** (0.0) | +1.8 | 0.0 | 0.0 | 13/28 -> 16/28 | 4/4 | 252 / 19 / 9 |

| Domain aggregate | Opus 4.8 | Haiku 5.5 | Haiku + interwhen |
|---|---|---|---|
| Mean reward | 85.52 | 82.17 | 93.35 |
| Strict Pass@1 | 20.83 | 25.00 | 45.83 |
| Strict Pass@4 | 33.33 | 50.00 | 50.00 |
| Strict Pass^4 | 16.67 | 0.00 | 33.33 |
| Rubrics passed | 259/336 | 249/336 | 300/336 |

Tasks improved / worse / unchanged (|delta| <= 2) vs Haiku: 5 / 0 / 1.

