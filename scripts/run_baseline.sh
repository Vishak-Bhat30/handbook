#!/usr/bin/env bash
# Baseline run (plain OpenHands agent, no verifiers) - same harness settings as scripts/run_interwhen.sh.
#
#   TASKS="medical_careig_specialty_pharmacy_3c62ee67 ..." ATTEMPTS=4 CONCURRENCY=4 scripts/run_baseline.sh
set -euo pipefail
cd "$(dirname "$0")/.."

TASKS="${TASKS:?set TASKS}"
ATTEMPTS="${ATTEMPTS:-4}"
CONCURRENCY="${CONCURRENCY:-1}"
MODEL="${MODEL:-openai/claude-haiku-5.5}"
STAMP="$(date +%Y%m%d-%H%M%S)"

curl -fsS -m 20 --retry 3 http://172.17.0.1:3141/v1/models >/dev/null || {
  echo "proxy bridge not reachable on 172.17.0.1:3141 (start scripts/proxy_bridge.py)" >&2; exit 1; }
scripts/check_model.sh "$MODEL" || exit 1

pids=()
for t in $TASKS; do
  job="${JOB_PREFIX:-baseline}-${t##*_}-$STAMP"
  .venv/bin/harbor run -p "tasks/$t" \
    --agent-import-path agent_harness.openhands_agent:OpenHandsAgent \
    -m "$MODEL" --ak reasoning_effort=max \
    -k "$ATTEMPTS" -n "$CONCURRENCY" --job-name "$job" --env-file .env > "/tmp/$job.log" 2>&1 &
  pids+=($!)
  echo "started $job (log /tmp/$job.log)"
done
status=0
for p in "${pids[@]}"; do wait "$p" || status=1; done
exit $status
