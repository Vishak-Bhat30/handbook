#!/usr/bin/env bash
# Freeze a task's verifiers before its single scored run: archive + sha256 manifest.
#   freeze.sh <task>          create tmp/blind/frozen/<task>.{tar.gz,sha256}
#   freeze.sh --verify <task> exit 1 if the live files differ from the frozen ones
set -euo pipefail
P=/mnt/datadrive/t-bhatvishak/Vishak_Handbook/docker/openhands-runner
F=/mnt/datadrive/t-bhatvishak/tmp/blind/frozen
verify=0; [[ $1 == --verify ]] && { verify=1; shift; }
t=$1; id=${t##*_}
files=(interwhen_sop/verifiers/$t.py interwhen_sop/tasks/$t/triage.json interwhen_sop/tasks/$t/sop.json interwhen_sop/kit.py)
[[ -f $P/interwhen_sop/tests/blind/test_$id.py ]] && files+=(interwhen_sop/tests/blind/test_$id.py)
cd $P
if (( verify )); then sha256sum -c --quiet $F/$t.sha256; echo "frozen OK $t"; exit 0; fi
[[ -e $F/$t.sha256 ]] && { echo "already frozen: $t" >&2; exit 1; }
sha256sum "${files[@]}" > $F/$t.sha256
tar czf $F/$t.tar.gz "${files[@]}"
echo "frozen $t $(date -u +%FT%TZ)"; cat $F/$t.sha256
