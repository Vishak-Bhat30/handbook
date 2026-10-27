#!/usr/bin/env bash
# Interwhen run: OpenHands + per-task SOP verifiers (PreToolUse blocking + completion check).
#
#   scripts/run_interwhen.sh                                     # 1 attempt on logistics_gear_sytems_inc_9b60992d
#   TASKS="logistics_gear_sytems_inc_9b60992d logistics_gear_sytems_inc_74170ae1" ATTEMPTS=4 CONCURRENCY=4 \
#       scripts/run_interwhen.sh                                 # one job per task, run in parallel
#
# Each task needs its SOP data (interwhen_sop/tasks/<task>/sop.json) and its verifier module
# (interwhen_sop/verifiers/<task>.py); tasks missing either are refused here.
# Needs: scripts/proxy_bridge.py running and the extraction SLM (vLLM, OpenAI API) on host port 8000.
set -euo pipefail
cd "$(dirname "$0")/.."

TASKS="${TASKS:-${TASK:-logistics_gear_sytems_inc_9b60992d}}"
ATTEMPTS="${ATTEMPTS:-1}"
CONCURRENCY="${CONCURRENCY:-1}"
MODEL="${MODEL:-openai/claude-haiku-5.5}"
SLM_URL="${SLM_URL:-http://172.17.0.1:8000/v1}"
STAMP="$(date +%Y%m%d-%H%M%S)"
IW=docker/openhands-runner/interwhen_sop

for t in $TASKS; do
  [[ -f "$IW/tasks/$t/sop.json" ]] || { echo "no SOP data for $t; run scripts/build_sop_paragraphs.py $t" >&2; exit 1; }
  [[ -f "$IW/verifiers/$t.py" ]] || { echo "no verifier module $IW/verifiers/$t.py" >&2; exit 1; }
done
curl -fsS -m 10 --retry 3 http://127.0.0.1:8000/v1/models >/dev/null || { echo "SLM not reachable on :8000" >&2; exit 1; }
curl -fsS -m 20 --retry 3 http://172.17.0.1:3141/v1/models >/dev/null || {
  echo "proxy bridge not reachable on 172.17.0.1:3141 (start scripts/proxy_bridge.py)" >&2; exit 1; }
scripts/check_model.sh "$MODEL" || exit 1

find docker/openhands-runner -name __pycache__ -type d -prune -exec rm -rf {} +

pids=()
for t in $TASKS; do
  job="${JOB_PREFIX:-interwhen}-${t##*_}-$STAMP"
  .venv/bin/harbor run -p "tasks/$t" \
    --agent-import-path agent_harness.interwhen_agent:InterwhenOpenHandsAgent \
    -m "$MODEL" --ak reasoning_effort=max --ak slm_url="$SLM_URL" \
    --ak checklist="${CHECKLIST:-0}" --ak max_completion_denials="${MAX_DENIALS:-3}" \
    --ak max_stale_denials="${MAX_STALE:-1000}" \
    -k "$ATTEMPTS" -n "$CONCURRENCY" --job-name "$job" --env-file .env > "/tmp/$job.log" 2>&1 &
  pids+=($!)
  echo "started $job (log /tmp/$job.log)"
done
status=0
for p in "${pids[@]}"; do wait "$p" || status=1; done
exit $status
