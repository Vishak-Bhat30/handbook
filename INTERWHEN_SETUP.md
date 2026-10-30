# Interwhen Handoff and Setup Guide

This guide sets up the `Handbook_interwhen` branch and runs one Interwhen task.

## What `127.0.0.1:8000` means

`127.0.0.1` is the loopback address: it always means **this computer**. It is
not Vishak's server and it is not a public IP address.

The setup uses one required OpenAI-compatible model service:

| Address | Purpose |
| --- | --- |
| `http://127.0.0.1:3141/v1` | Main model used by the OpenHands agent |

The repository does not start this model service. It must be available on the
machine running the benchmark.

The codebase still contains an optional SLM extraction client and an offline
`triage propose` utility. The current runtime verifier modules do not invoke
them: policy decisions and fact checks are deterministic Python. Therefore no
service is required on port `8000` for normal Interwhen runs.

## Prerequisites

- Linux
- Git and `curl`
- Python 3.13
- Docker Engine with Buildx and Compose v2
- `uv`
- An OpenAI-compatible main model service on host port `3141`
- Sufficient disk space and GPU resources for any locally hosted models

Verify Docker before continuing:

```bash
docker info
docker buildx version
docker compose version
```

If Docker reports a permission error, add the current user to the Docker group,
then log out and back in:

```bash
sudo usermod -aG docker "$USER"
```

## 1. Clone the handoff branch

```bash
git clone --branch Handbook_interwhen \
  https://github.com/Vishak-Bhat30/handbook.git
cd handbook
```

## 2. Install `uv` and Python dependencies

Install `uv` if it is not already installed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
```

Create the environment and install Harbor plus the local agent harness:

```bash
uv venv .venv --python 3.13
uv pip install --python .venv/bin/python harbor -e ./agent_harness
```

## 3. Build the benchmark image

```bash
docker buildx build --load -t handbook_base docker/
```

## 4. Configure the main agent model

The commands in this repository expect an OpenAI-compatible model service on
`127.0.0.1:3141`. This service is external to the repository. Start your model
proxy or inference server first, then verify it:

```bash
curl -fsS http://127.0.0.1:3141/v1/models | python -m json.tool
```

Create the environment file used by Harbor:

```bash
cat > .env <<'EOF'
OPENAI_BASE_URL=http://172.17.0.1:3141/v1
OPENAI_API_KEY=local-proxy-no-key-required
OPENROUTER_API_KEY=unused
ANTHROPIC_API_KEY=unused
EOF
```

Use real credentials instead of placeholder values if your proxy requires
authentication. Never commit `.env`.

## 5. Start the main-model bridge

The main model listens on host loopback, which Docker containers cannot access
directly. Keep this bridge running in a separate terminal:

```bash
cd handbook
.venv/bin/python scripts/proxy_bridge.py
```

Expected mapping:

```text
172.17.0.1:3141 -> 127.0.0.1:3141
```

## 6. Run one Interwhen task

First list the main model IDs and select one exactly as returned by the port
`3141` service:

```bash
curl -fsS http://127.0.0.1:3141/v1/models | python -m json.tool
```

Then run the default task:

```bash
MODEL=openai/<model-id> scripts/run_interwhen.sh
```

Example, only if that exact ID appears in `/v1/models`:

```bash
MODEL=openai/claude-haiku-5.5 scripts/run_interwhen.sh
```

Run a particular supported task with multiple attempts:

```bash
TASK=logistics_gear_sytems_inc_74170ae1 \
ATTEMPTS=4 \
CONCURRENCY=4 \
MODEL=openai/<model-id> \
scripts/run_interwhen.sh
```

Results are written under `jobs/`. Per-run logs are also announced under
`/tmp/` when the launcher starts.

## 7. Run local tests

The pure Python and workbook tests can run without either model service. Some
legacy SLM-dependent tests are skipped when no extraction service is configured.

Install the workbook test dependency:

```bash
uv pip install --python .venv/bin/python openpyxl
```

```bash
cd docker/openhands-runner
INTERWHEN_REPO="$(cd ../.. && pwd)" \
INTERWHEN_XLSX_PYTHON="$(cd ../.. && pwd)/.venv/bin/python" \
../../.venv/bin/python -m unittest discover \
  -s interwhen_sop/tests \
  -p 'test_*.py' \
  -v
```

## Troubleshooting

### `proxy bridge not reachable on 172.17.0.1:3141`

Start `scripts/proxy_bridge.py` in another terminal. Also confirm that the main
model API itself answers on `127.0.0.1:3141`.

### `model '<id>' is not served by the proxy`

Use an exact model ID returned by:

```bash
curl -fsS http://127.0.0.1:3141/v1/models | python -m json.tool
```

### Docker socket permission denied

Add the user to the `docker` group and start a new login session.

## Optional legacy SLM extraction

Port `8000` is only needed when deliberately using the dormant extraction
helpers or `python -m interwhen_sop.triage propose`. Configure a reachable
OpenAI-compatible endpoint explicitly:

```bash
export SLM_URL=http://MODEL_HOST:8000/v1
```

Do not use `127.0.0.1` for a model on another computer: loopback always refers
to the current computer. Avoid exposing an unauthenticated inference server to
the public internet.
