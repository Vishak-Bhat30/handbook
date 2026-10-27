#!/usr/bin/env bash
# Single scored interwhen run (4 attempts) for frozen tasks. Usage: run_task.sh <task> [<task> ...]
set -euo pipefail
cd /mnt/datadrive/t-bhatvishak/Vishak_Handbook
for t in "$@"; do /mnt/datadrive/t-bhatvishak/tmp/blind/freeze.sh --verify "$t"; done
TASKS="$*" ATTEMPTS=4 CONCURRENCY=4 CHECKLIST=1 MAX_DENIALS=6 MAX_STALE=2 JOB_PREFIX=blind scripts/run_interwhen.sh
