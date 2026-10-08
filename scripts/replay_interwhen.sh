#!/usr/bin/env bash
# Replay baseline trajectories through interwhen_sop inside the task image (writes applied to a scratch /workdir).
#   scripts/replay_interwhen.sh <task_id> <job_dir> [trial_glob]
set -euo pipefail
cd "$(dirname "$0")/.."
TASK="$1"; JOB="$2"; GLOB="${3:-*}"
OUT="${OUT:-/mnt/datadrive/t-bhatvishak/tmp/interwhen-replay/$TASK}"
mkdir -p "$OUT"
for traj in "$JOB"/${TASK:0:32}__$GLOB/agent/trajectory.json; do
  trial=$(basename "$(dirname "$(dirname "$traj")")")
  rel=${traj#"$PWD"/}
  sg docker -c "docker run --rm -e OPENHANDS_SUPPRESS_BANNER=1 -e PYTHONDONTWRITEBYTECODE=1 \
    -e INTERWHEN_SLM_URL=http://172.17.0.1:8000/v1 -e INTERWHEN_REPO=/repo \
    -v $PWD:/repo:ro -v $OUT:/out --tmpfs /workdir:rw,size=64m --tmpfs /tmp:rw,size=256m \
    --entrypoint bash handbook_base:latest -c '
      cp -r /repo/tasks/$TASK/environment/initial_workspace/. /workdir/ && cd /repo/docker/openhands-runner &&
      /app/openhands-runner/.venv/bin/python -m interwhen_sop.tests.replay_trace /repo/$rel --task $TASK \
        --workdir /workdir --state-dir /tmp/st --apply-writes > /out/$trial.txt 2>&1;
      cp /tmp/st/decisions.jsonl /out/$trial.decisions.jsonl; chmod a+rw /out/$trial.*'"
  echo "$trial: allow=$(grep -c '^allow' "$OUT/$trial.txt") deny=$(grep -c '^DENY' "$OUT/$trial.txt")"
done
