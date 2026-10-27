# Interwhen - single-iteration results (no grader-driven iteration)

Protocol (`scripts/algo.md` Step 6): one scored run per task, original graders, no re-runs after seeing
grader output. All runs: Haiku 5.5 (`openai/claude-haiku-5.5`), 4 attempts per task. Scores are the raw
`result.json` rewards (computed with `tmp/vs/metrics.py`); the three CareIG grader edits were reverted
(backup: `tmp/cg/grader_edits.patch`) and are **not** applied to any number below.

## Aggregate

| Domain | Tasks | Opus 4.8 baseline | Haiku 5.5 baseline | Haiku 5.5 + interwhen (1 iteration) |
|---|---|---|---|---|
| CareIG | 7 | 70.51 (sP@1 17.86) | 76.41 (sP@1 10.71) | **85.19** (sP@1 32.14) |
| Pathfinder | 8 | 77.64 (sP@1 12.50) | 67.55 (sP@1 12.50) | **98.05** (sP@1 81.25) |
| **All** | 15 | 74.31 (sP@1 15.00) | 71.68 (sP@1 11.67) | **92.05** (sP@1 58.33) |

Mean Reward (Strict Pass@1 in brackets), unweighted mean over tasks.

## CareIG (first interwhen run = Run 1, `jobs/interwhen-cg-<task>-20261019-044652`)

| Task | Opus 4.8 | Haiku 5.5 | Interwhen (1 iteration) | Rubrics |
|---|---|---|---|---|
| 3c62ee67 | 81.9 (sP@1 0) | 79.49 (sP@1 0) | 82.17 (sP@1 0) | 58/72 |
| ea622238 | 43.75 (sP@1 0) | 47.46 (sP@1 0) | 73.32 (sP@1 0) | 33/56 |
| d4619b8b | 34.38 (sP@1 0) | 83.86 (sP@1 25) | 98.96 (sP@1 75) | 47/48 |
| f5947c33 | 58.46 (sP@1 0) | 57.36 (sP@1 0) | 64.71 (sP@1 0) | 44/68 |
| d3e312a5 | 81.25 (sP@1 0) | 81.25 (sP@1 0) | 84.38 (sP@1 0) | 27/32 |
| f6d19d30 | 96.43 (sP@1 75) | 85.71 (sP@1 25) | 92.86 (sP@1 75) | 26/28 |
| 08ae3378 | 97.40 (sP@1 50) | 99.72 (sP@1 25) | 99.96 (sP@1 75) | 47/48 |
| **Mean** | 70.51 | 76.41 | **85.19** | |

For reference only (not a single-iteration number): the first per-paragraph (algo v2) run scored 95.54 mean
(3c62 94.44, ea62 90.29, d461 95.84, f594 88.24, d3e3 100, f6d1 100, 08ae 99.96). Those verifiers were tightened
after reading Run 1 grader failures, so they count as a second iteration.

## Pathfinder (first interwhen run, `jobs/interwhen-haiku55-<task>-*`)

| Task | Opus 4.8 | Haiku 5.5 | Interwhen (1 iteration) | Rubrics |
|---|---|---|---|---|
| 073e602b | 82.14 (sP@1 0) | 79.33 (sP@1 0) | 100.00 (sP@1 100) | 100/100 |
| 1d8667fc | 85.00 (sP@1 25) | 40.00 (sP@1 0) | 100.00 (sP@1 100) | 20/20 |
| 9d274282 | 83.57 (sP@1 25) | 67.86 (sP@1 0) | 100.00 (sP@1 100) | 20/20 |
| a25684b9 | 91.66 (sP@1 50) | 95.83 (sP@1 75) | 100.00 (sP@1 100) | 24/24 |
| a70deabc | 52.38 (sP@1 0) | 38.10 (sP@1 0) | 85.71 (sP@1 0) | 24/28 |
| bbf1a560 | 65.00 (sP@1 0) | 85.00 (sP@1 25) | 100.00 (sP@1 100) | 40/40 |
| c01deb6e | 78.46 (sP@1 0) | 77.93 (sP@1 0) | 100.00 (sP@1 100) | 108/108 |
| ec505b6b | 82.89 (sP@1 0) | 56.32 (sP@1 0) | 98.69 (sP@1 50) | 74/76 |
| **Mean** | 77.64 | 67.55 | **98.05** | |

## Caveats (contamination that a single iteration does not remove)

- **Pathfinder:** the v1 verifiers were written after reading the rubric texts and the baseline FAIL lines, so
  they encode grader knowledge even though they were scored only once. 98.05 is an upper bound and not a blind
  result.
- **CareIG Run 1:** first run of the domain-level verifiers, with no prior grader feedback on those verifiers.
  Rubric access during building was not enforced, so it cannot be certified as blind either.
- A clean number needs a blind builder: no access to `tests/` and no baseline rubric output, verifiers frozen
  before the single scored run. This applies to the remaining domains.

## Remaining domains (not built)

vanguard (7), gear_sytems (6), creamery (6), ridgeline (7), mojave (6), crestwood (6), sunshine (6),
meridian (6). Haiku 5.5 baselines finished before the stop: vanguard 177fce83 20.2, 4321b8e9 60.4,
82da8d17 71.4, 89007056 67.2. vanguard 90ff0751 and 9b2f7a29 were interrupted (2 trials each, no reward) and
must be re-run.
