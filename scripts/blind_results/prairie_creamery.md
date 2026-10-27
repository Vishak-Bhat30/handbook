# Prairie Creamery - blind interwhen results

Single scored run per task (4 attempts), verifiers built blind (SOP + instruction + seed data + baseline
trajectories, never graders/rubrics/scores) and frozen before the run. Agent: Haiku 5.5 (OpenHands).
Mean = mean reward x100; sP@1 = share of attempts passing every rubric; sP@4 / sP^4 = any / all of the
attempts pass every rubric. Attempts where the model API failed before the first tool call are excluded.

| Task | Opus 4.8 mean (sP@1) | Haiku 5.5 mean (sP@1) | Haiku + interwhen mean (sP@1) | Delta vs Haiku | sP@4 | sP^4 | Rubrics passed (Haiku -> interwhen) | n (H/I) | SOP paragraphs / verifiable / rules |
|---|---|---|---|---|---|---|---|---|---|
| 27470081 | 63.3 (0.0) | 43.5 (0.0) | **79.7** (0.0) | +36.2 | 0.0 | 0.0 | 18/60 -> 39/60 | 4/4 | 775 / 76 / 15 |
| 4a2f4b1a | 59.1 (0.0) | 68.2 (0.0) | **79.5** (0.0) | +11.4 | 0.0 | 0.0 | 30/44 -> 35/44 | 4/4 | 726 / 38 / 12 |
| 7b63c60d | 66.7 (0.0) | 58.3 (0.0) | **66.7** (0.0) | +8.3 | 0.0 | 0.0 | 7/12 -> 8/12 | 4/4 | 732 / 39 / 8 |
| 861b2650 | 76.7 (0.0) | 84.2 (0.0) | **86.7** (0.0) | +2.5 | 0.0 | 0.0 | 50/60 -> 52/60 | 4/4 | 614 / 42 / 11 |
| a9dc52cb | 62.1 (0.0) | 47.1 (0.0) | **63.8** (0.0) | +16.7 | 0.0 | 0.0 | 3/16 -> 7/16 | 4/4 | 719 / 43 / 12 |
| f382586a | 49.8 (0.0) | 77.0 (0.0) | **83.3** (25.0) | +6.3 | 100.0 | 0.0 | 26/36 -> 30/36 | 4/4 | 788 / 42 / 14 |

| Domain aggregate | Opus 4.8 | Haiku 5.5 | Haiku + interwhen |
|---|---|---|---|
| Mean reward | 62.93 | 63.06 | 76.62 |
| Strict Pass@1 | 0.00 | 0.00 | 4.17 |
| Strict Pass@4 | 0.00 | 0.00 | 16.67 |
| Strict Pass^4 | 0.00 | 0.00 | 0.00 |
| Rubrics passed | 132/228 | 134/228 | 171/228 |

Tasks improved / worse / unchanged (|delta| <= 2) vs Haiku: 6 / 0 / 0.

