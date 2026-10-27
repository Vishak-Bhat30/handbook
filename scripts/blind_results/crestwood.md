# Crestwood - blind interwhen results

Single scored run per task (4 attempts), verifiers built blind (SOP + instruction + seed data + baseline
trajectories, never graders/rubrics/scores) and frozen before the run. Agent: Haiku 5.5 (OpenHands).
Mean = mean reward x100; sP@1 = share of attempts passing every rubric; sP@4 / sP^4 = any / all of the
attempts pass every rubric. Attempts where the model API failed before the first tool call are excluded.

| Task | Opus 4.8 mean (sP@1) | Haiku 5.5 mean (sP@1) | Haiku + interwhen mean (sP@1) | Delta vs Haiku | sP@4 | sP^4 | Rubrics passed (Haiku -> interwhen) | n (H/I) | SOP paragraphs / verifiable / rules |
|---|---|---|---|---|---|---|---|---|---|
| 1b602061 | 89.0 (50.0) | 72.5 (0.0) | **88.1** (0.0) | +15.6 | 0.0 | 0.0 | 61/84 -> 74/84 | 4/4 | 662 / 58 / 20 |
| 2071c562 | 83.9 (0.0) | 0.0 (0.0) | **62.5** (0.0) | +62.5 | 0.0 | 0.0 | 0/0 -> 35/56 | 4/4 | 612 / 52 / 12 |
| 79786c46 | 81.0 (0.0) | 90.5 (25.0) | **90.5** (0.0) | +0.0 | 0.0 | 0.0 | 76/84 -> 76/84 | 4/4 | 596 / 35 / 14 |
| d93daa01 | 96.9 (75.0) | 93.8 (75.0) | **87.5** (75.0) | -6.2 | 100.0 | 0.0 | 30/32 -> 28/32 | 4/4 | 336 / 24 / 16 |
| da394eac | 77.5 (0.0) | 81.9 (0.0) | **95.0** (0.0) | +13.1 | 0.0 | 0.0 | 65/80 -> 76/80 | 4/4 | 378 / 38 / 12 |
| ee4d1791 | 75.0 (0.0) | 72.2 (0.0) | **94.4** (0.0) | +22.2 | 0.0 | 0.0 | 52/72 -> 68/72 | 4/4 | 588 / 52 / 18 |

| Domain aggregate | Opus 4.8 | Haiku 5.5 | Haiku + interwhen |
|---|---|---|---|
| Mean reward | 83.88 | 68.47 | 86.34 |
| Strict Pass@1 | 20.83 | 16.67 | 12.50 |
| Strict Pass@4 | 33.33 | 33.33 | 16.67 |
| Strict Pass^4 | 0.00 | 0.00 | 0.00 |
| Rubrics passed | 337/408 | 284/352 | 357/408 |

Tasks improved / worse / unchanged (|delta| <= 2) vs Haiku: 4 / 1 / 1.

Haiku baseline attempts that crashed mid-run (counted as reward 0): 2071c562 x4.
