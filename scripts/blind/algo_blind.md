# Interwhen SOP verifiers - paragraph-driven algorithm (v2)

Goal: an agent working a task must follow the task's SOP. We compile the SOP into Python verifiers that run
inside the agent loop (interwhen): they block a wrong tool call before it executes, refuse to let the agent
finish while SOP obligations are outstanding, and tell the agent exactly what to do instead.

## Ground rules

- Verifiers are built only from: the SOP, the task instruction / system prompt, and the seed data the agent
  can see (initial workspace files, initial mail / Slack / calendar / Jira). Never from `tests/`, graders,
  rubric texts, rubric output or baseline FAIL lines. Do not open `tests/` while building.
- **One scored iteration.** Verifiers are frozen (git commit) before the first scored run. The grader runs
  once, on that run, and its score is the reported result. No change to verifiers after seeing grader
  output, no re-runs to raise the score, no grader edits (report the original grader's score; disagreements
  with the grader are written up, not fixed).
- The SLM (port 8000) is used only to extract information (from the conversation, tool outputs, documents).
  Every decision is plain Python. Regex also can be used.
- A wrong block is worse than a missing one: it wastes the agent's turns and can push it into a violation.
  Precision before recall.
- **Blind builder.** Each task is built by a fresh builder with no prior knowledge of that task's graders.
  The builder must not open: `tasks/<task>/tests/`, `tasks/<task>/solution/` (if any), anything under
  `jobs/*/*/verifier/`, any `result.json` / `reward*` file, `scripts/*results*.md`, `/memories/`, or
  `/mnt/datadrive/t-bhatvishak/archive_verifiers_*` (old, grader-informed verifiers). Allowed inputs: the
  task's `instruction.md`, `system_prompt.md`, `environment/` (workspace + seed services), the SOP, the
  interwhen core package, and baseline *trajectories* (`jobs/baseline-haiku55-<id>-*/*/agent/trajectory.json`).

## Step 0 - Parse the SOP into paragraphs

`scripts/build_sop_any.py <task> [sop file]` -> `interwhen_sop/tasks/<task>/sop.json`
(paragraph id, section, section title, kind = heading / text / bullet / table_row, templates, contacts).

## Step 1 - Task fact sheet

Dump everything the agent can observe: instruction, today's date, the acting user, mailbox, Slack channels and
history, calendar, every workbook (`python3 tmp/dump_env.py tasks/<task> tmp/blind/<id>/env.txt`), plus the
tool catalog with argument shapes (`interwhen_sop/actions.py: classify`). This is the "world" each paragraph
is judged against.

## Step 2 - Paragraph triage (one decision per paragraph, nothing skipped)

Iterate over **every** paragraph `P`. Context for the decision = section title, the paragraphs immediately
before/after `P`, any section / template `P` references, the fact sheet and the tool catalog. Decide:

| verdict | meaning |
|---|---|
| `context` | heading, purpose, definitions, governance - no instruction |
| `data` | a lookup the rules consume (template text, code tables, contact list, column list) |
| `not_observable` | phone calls, physical handling, timing or other people's actions no tool call can show |
| `not_applicable` | an instruction whose trigger cannot arise in this task's seed data (e.g. a CO-22 rule when no CO-22 exists). Generic prohibitions are always applicable |
| `verifiable` | an instruction whose compliance shows up in tool-call arguments, tool outputs or the end state |

For each `verifiable` paragraph also record:
- `trigger` - which tool calls / files / messages it governs,
- `stage` - `pre` (block the call), `completion` (end-state / missing obligation), or both,
- `oracle` - where the expected value comes from (SOP literal, seed-data cell, SLM extraction of a document),
- `strictness` - `exact` for templates, tags, subjects, log lines; `semantic` otherwise,
- `verifiers` - the rule ids that implement it (filled in Step 3).

Output: `interwhen_sop/tasks/<task>/triage.json`. Workflow (from `docker/openhands-runner`):
`python3 -m interwhen_sop.triage init <task>` (needs the verifier module to exist; a stub `RULES = []` is
fine) marks headings as context; the builder writes every other verdict as a TSV
(`id<TAB>verdict<TAB>rule ids<TAB>reason`, kept in `tmp/blind/<id>/verdicts.tsv`) and loads it with
`triage apply <task> <tsv>`; `triage pending <task>` lists what is still open.

## Step 3 - Build a verifier for every verifiable paragraph

- One rule per paragraph (or per small group of paragraphs about the same action). Each rule cites its
  paragraph ids; feedback quotes the paragraph.
- `pre` rules: inspect the call's arguments (recipient, channel, subject, body, attachments, file + cells
  written). Block only when the call itself breaks the paragraph.
- `completion` rules: required messages not sent, required file / row / cell values missing, forbidden end
  states. Read workbooks from the live workspace (snapshot diff), not from the agent's claims.
- Exact matching for literal SOP text (templates, Slack tags, subject lines, "identical to the original").
  Do not normalise away characters the SOP prints (dashes, `MemberID` vs `Member_ID`).
- Feedback must contain the exact expected value (the full subject / tag / cell value) so the agent can copy it.
- Invariants every task gets:
  - append-only logs stay append-only;
  - **no unrequested writes**: a new audit/log row must correspond to an SOP checkpoint paragraph;
  - no unfilled template placeholders;
  - legal / compliance STOP paragraphs block every write and message about that case except the escalation.
- Implement the triage's `verifiers` field as you go.
- Code: `interwhen_sop/verifiers/<task>.py` exporting `RULES`, built on the domain-free `interwhen_sop/kit.py`
  (`World`/`world(ctx)`, `Comm` + `comm_rules`, `state_rule`, `pre_rule`, `append_only`, `forbid_writes`,
  `no_placeholders`, text helpers). Task-specific helpers stay in the task module; `kit.py` is not edited.

## Step 4 - Validate the verifiers before any run (precision gate)

1. **Initial state**: the completion stage on the untouched workspace must list exactly the obligations the
   triage expects - no more (a finding on something already correct is a parser bug).
   `cd tmp && python3 tall.py <id>`.
2. **Replay** the task's Haiku baseline trajectories through the `pre` rules
   (`cd tmp && python3 replay.py <id> <trial dir>`; it reads only `agent/trajectory.json`). Every block must
   be a genuine violation of the cited paragraph; investigate each one. Never look at the trial's reward.
3. **Unit tests**: per rule, one compliant and one violating synthetic call / state, in
   `interwhen_sop/tests/blind/test_<id>.py` on `interwhen_sop/tests/base.py: TaskCase`.
4. **Coverage**: `python -m interwhen_sop.triage check <task>` - every paragraph has a verdict, every
   `verifiable` paragraph has an implemented rule id, every rule id exists.

## Step 5 - Run-time policy (interwhen)

- **Obligation checklist**: at the first user message, inject the completion findings on the initial state as
  an SOP checklist (`INTERWHEN_CHECKLIST=1`), so the agent plans for them instead of discovering them at the end.
- `pre` hook: block with paragraph-quoting feedback + exact fix.
- `stop` hook: refuse completion while findings remain. **Adaptive budget**: keep refusing while the number
  of findings keeps shrinking; stop refusing after `INTERWHEN_MAX_STALE_DENIALS` refusals without progress
  or `INTERWHEN_MAX_COMPLETION_DENIALS` refusals overall.
- A crashing verifier fails open (never blocks).

## Step 6 - Freeze, run once, evaluate (no iteration)

1. Freeze: Steps 0-4 pass; `tmp/blind/freeze.sh <task>` archives the verifier, triage and tests with their
   sha256 in `tmp/blind/frozen/`. Any debugging before this point may use only the SOP, seed
   data, unit tests and *unscored* replays of agent trajectories (tool calls / outputs, never rewards or
   rubric results).
2. Run 4 attempts per task once (`scripts/run_interwhen.sh`) and score with the original grader. Report Mean
   Reward, Strict Pass@1, Pass@1 N-1, Strict Pass@4, Strict Pass^4, rubrics passed against the Haiku and
   Opus baselines. This is the final number for the task.
3. Post-hoc audit (analysis only, never fed back): classify each failed rubric as verifier wrong (false
   block / wrong SOP reading) / caught but not fixed / not covered / grader disagrees with SOP. Lessons may
   improve the *algorithm* for tasks not yet built, never the verifiers of an already-scored task.