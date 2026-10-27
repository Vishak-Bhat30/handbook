# Gear Systems - blind interwhen results

Single scored run per task (4 attempts), verifiers built blind (SOP + instruction + seed data + baseline
trajectories, never graders/rubrics/scores) and frozen before the run. Agent: Haiku 5.5 (OpenHands).
Mean = mean reward x100; sP@1 = share of attempts passing every rubric; sP@4 / sP^4 = any / all of the
attempts pass every rubric. Attempts where the model API failed before the first tool call are excluded.

| Task | Opus 4.8 mean (sP@1) | Haiku 5.5 mean (sP@1) | Haiku + interwhen mean (sP@1) | Delta vs Haiku | sP@4 | sP^4 | Rubrics passed (Haiku -> interwhen) | n (H/I) | SOP paragraphs / verifiable / rules |
|---|---|---|---|---|---|---|---|---|---|
| 0807b5a6 | 60.9 (0.0) | 43.6 (0.0) | **92.3** (0.0) | +48.7 | 0.0 | 0.0 | 20/52 -> 48/52 | 4/4 | 1555 / 27 / 14 |
| 502e8c5e | 97.5 (75.0) | 62.5 (25.0) | **95.0** (50.0) | +32.5 | 100.0 | 0.0 | 25/40 -> 38/40 | 4/4 | 1897 / 60 / 16 |
| 74170ae1 | 38.4 (0.0) | 0.0 (0.0) | **0.0** (0.0) | +0.0 | 0.0 | 0.0 | 0/0 -> 0/0 | 4/4 | 1884 / 100 / 20 |
| 9b60992d | 17.2 (0.0) | 74.1 (0.0) | **98.1** (0.0) | +24.0 | 0.0 | 0.0 | 16/24 -> 20/24 | 4/4 | 1876 / 34 / 11 |
| ad2ff597 | 50.4 (0.0) | 47.6 (0.0) | **57.1** (0.0) | +9.5 | 0.0 | 0.0 | 30/68 -> 32/68 | 4/4 | 1830 / 52 / 13 |
| dba0375e | 83.7 (0.0) | 82.1 (0.0) | **80.5** (0.0) | -1.5 | 0.0 | 0.0 | 35/52 -> 37/52 | 4/4 | 1853 / 64 / 20 |

| Domain aggregate | Opus 4.8 | Haiku 5.5 | Haiku + interwhen |
|---|---|---|---|
| Mean reward | 58.02 | 51.64 | 70.50 |
| Strict Pass@1 | 12.50 | 4.17 | 8.33 |
| Strict Pass@4 | 16.67 | 16.67 | 16.67 |
| Strict Pass^4 | 0.00 | 0.00 | 0.00 |
| Rubrics passed | 162/312 | 126/236 | 175/236 |

Tasks improved / worse / unchanged (|delta| <= 2) vs Haiku: 4 / 0 / 2.

Haiku baseline attempts that crashed mid-run (counted as reward 0): 74170ae1 x4.
