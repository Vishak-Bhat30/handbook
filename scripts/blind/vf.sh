#!/usr/bin/env bash
# Validate (coverage 0 gaps + unit tests OK) and freeze each task; print the tasks that passed.
cd /mnt/datadrive/t-bhatvishak/Vishak_Handbook/docker/openhands-runner
ok=()
for id in "$@"; do
  t=$(ls interwhen_sop/tasks | grep "_$id$")
  c=$(python3 -m interwhen_sop.triage check $t 2>&1 | tail -1)
  u=$(INTERWHEN_XLSX_PYTHON=/home/t-bhatvishak/miniconda3/bin/python3 timeout 900 python3 -m unittest interwhen_sop.tests.blind.test_$id 2>&1 | tail -1)
  echo "$id | $c | tests: $u"
  if [[ $c == *" 0 gaps" && $u == OK* ]]; then /mnt/datadrive/t-bhatvishak/tmp/blind/freeze.sh $t >/dev/null && ok+=($t); fi
done
echo "FROZEN: ${ok[*]}"
