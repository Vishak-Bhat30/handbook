# Mojave - blind interwhen results

Single scored run per task (4 attempts), verifiers built blind (SOP + instruction + seed data + baseline
trajectories, never graders/rubrics/scores) and frozen before the run. Agent: Haiku 5.5 (OpenHands).
Mean = mean reward x100; sP@1 = share of attempts passing every rubric; sP@4 / sP^4 = any / all of the
attempts pass every rubric. Attempts where the model API failed before the first tool call are excluded.

| Task | Opus 4.8 mean (sP@1) | Haiku 5.5 mean (sP@1) | Haiku + interwhen mean (sP@1) | Delta vs Haiku | sP@4 | sP^4 | Rubrics passed (Haiku -> interwhen) | n (H/I) | SOP paragraphs / verifiable / rules |
|---|---|---|---|---|---|---|---|---|---|
| 187e3a8c | 96.1 (25.0) | 97.8 (0.0) | **96.4** (0.0) | -1.4 | 0.0 | 0.0 | 56/60 -> 50/60 | 4/4 | 591 / 141 / 13 |
| 2a800bf7 | 64.3 (0.0) | 53.6 (0.0) | **96.4** (75.0) | +42.9 | 100.0 | 0.0 | 15/28 -> 27/28 | 4/4 | 653 / 46 / 9 |
| 4d2a2588 | 66.1 (0.0) | 66.1 (0.0) | **87.5** (0.0) | +21.4 | 0.0 | 0.0 | 37/56 -> 49/56 | 4/4 | 668 / 121 / 24 |
| 5122b4da | 83.3 (0.0) | 89.6 (0.0) | **91.7** (0.0) | +2.1 | 0.0 | 0.0 | 43/48 -> 44/48 | 4/4 | 859 / 132 / 14 |
| 7245b8dd | 82.8 (0.0) | 84.4 (25.0) | **100.0** (100.0) | +15.6 | 100.0 | 100.0 | 28/36 -> 36/36 | 4/4 | 1066 / 81 / 9 |
| ab59bcf7 | 90.8 (0.0) | 82.9 (0.0) | **84.2** (0.0) | +1.3 | 0.0 | 0.0 | 63/76 -> 64/76 | 4/4 | 796 / 82 / 13 |

| Domain aggregate | Opus 4.8 | Haiku 5.5 | Haiku + interwhen |
|---|---|---|---|
| Mean reward | 80.57 | 79.06 | 92.70 |
| Strict Pass@1 | 4.17 | 4.17 | 29.17 |
| Strict Pass@4 | 16.67 | 16.67 | 33.33 |
| Strict Pass^4 | 0.00 | 0.00 | 16.67 |
| Rubrics passed | 249/304 | 242/304 | 270/304 |

Tasks improved / worse / unchanged (|delta| <= 2) vs Haiku: 4 / 0 / 2.

