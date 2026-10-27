# Vanguard - blind interwhen results

Single scored run per task (4 attempts), verifiers built blind (SOP + instruction + seed data + baseline
trajectories, never graders/rubrics/scores) and frozen before the run. Agent: Haiku 5.5 (OpenHands).
Mean = mean reward x100; sP@1 = share of attempts passing every rubric; sP@4 / sP^4 = any / all of the
attempts pass every rubric. Attempts where the model API failed before the first tool call are excluded.

| Task | Opus 4.8 mean (sP@1) | Haiku 5.5 mean (sP@1) | Haiku + interwhen mean (sP@1) | Delta vs Haiku | sP@4 | sP^4 | Rubrics passed (Haiku -> interwhen) | n (H/I) | SOP paragraphs / verifiable / rules |
|---|---|---|---|---|---|---|---|---|---|
| 177fce83 | 53.1 (0.0) | 20.2 (0.0) | **46.9** (0.0) | +26.6 | 0.0 | 0.0 | 10/64 -> 25/64 | 4/4 | 242 / 15 / 8 |
| 4321b8e9 | 91.7 (50.0) | 60.4 (0.0) | **25.0** (0.0) | -35.4 | 0.0 | 0.0 | 29/48 -> 12/48 | 4/4 | 252 / 10 / 10 |
| 82da8d17 | 75.0 (0.0) | 71.4 (0.0) | **78.6** (0.0) | +7.1 | 0.0 | 0.0 | 20/28 -> 22/28 | 4/4 | 349 / 14 / 7 |
| 89007056 | 73.4 (0.0) | 67.2 (0.0) | **79.7** (0.0) | +12.5 | 0.0 | 0.0 | 43/64 -> 51/64 | 4/4 | 209 / 9 / 7 |
| 90ff0751 | 79.5 (0.0) | 72.7 (0.0) | **81.8** (0.0) | +9.1 | 0.0 | 0.0 | 32/44 -> 36/44 | 4/4 | 333 / 8 / 9 |
| 9b2f7a29 | 21.6 (0.0) | 43.2 (0.0) | **22.2** (0.0) | -21.0 | 0.0 | 0.0 | 11/48 -> 8/48 | 4/4 | 320 / 17 / 8 |
| fe30fce5 | 80.8 (0.0) | 72.4 (0.0) | **83.4** (0.0) | +11.0 | 0.0 | 0.0 | 18/40 -> 24/40 | 4/4 | 209 / 13 / 9 |

| Domain aggregate | Opus 4.8 | Haiku 5.5 | Haiku + interwhen |
|---|---|---|---|
| Mean reward | 67.88 | 58.24 | 59.65 |
| Strict Pass@1 | 7.14 | 0.00 | 0.00 |
| Strict Pass@4 | 14.29 | 0.00 | 0.00 |
| Strict Pass^4 | 0.00 | 0.00 | 0.00 |
| Rubrics passed | 201/336 | 163/336 | 178/336 |

Tasks improved / worse / unchanged (|delta| <= 2) vs Haiku: 5 / 2 / 0.

