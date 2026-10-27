#!/usr/bin/env bash
# Fail unless the model proxy serves the requested model by exact id: the local Copilot proxy silently falls back
# to its first model otherwise.
#   scripts/check_model.sh openai/claude-haiku-5.5
set -euo pipefail
want="${1#openai/}"
ids="$(curl -fsS -m 20 http://127.0.0.1:3141/v1/models | python3 -c 'import json,sys; print("\n".join(m["id"] for m in json.load(sys.stdin)["data"]))')"
if ! grep -qx "$want" <<<"$ids"; then
  echo "model '$want' is not served by the proxy (it would silently fall back to '$(head -1 <<<"$ids")'); available:" >&2
  tr '\n' ' ' <<<"$ids" >&2; echo >&2
  exit 1
fi
echo "model check ok: $want"
