# HANDBOOK.md — First-Time Setup & Run Guide

End-to-end steps to clone, set up, and run the HANDBOOK.md benchmark using the
local OpenAI-compatible model proxy (`http://127.0.0.1:3141`, serving Claude
models).

## 1. Clone the repository

```bash
git clone https://github.com/surge-ai/handbook.git
cd handbook
```

## 2. Grant Docker access (one-time)

The build and run steps need to talk to the Docker daemon. If you get
`permission denied ... /var/run/docker.sock`, add your user to the `docker`
group:

```bash
sudo usermod -aG docker $USER
newgrp docker          # apply to current shell (or log out and back in)
docker info | head -5  # verify: prints server info, no permission error
```

> Fully log out/in (or restart your terminal) so the VS Code integrated
> terminal also picks up the new group.

## 3. Build the base image

```bash
docker build -t handbook_base docker/
```

## 4. Install Harbor + the agent harness

```bash
uv venv .venv --python 3.13
uv pip install --python .venv/bin/python harbor -e ./agent_harness
```

## 5. Configure the model proxy

The agent runs **inside** the task container, but the proxy only listens on the
host's `127.0.0.1`, which a container cannot reach. We (a) point the pipeline at
the proxy and (b) republish it on the Docker bridge gateway (`172.17.0.1`).

Create `.env` in the repo root:

```bash
cat > .env <<'EOF'
OPENAI_BASE_URL=http://172.17.0.1:3141/v1
OPENAI_API_KEY=local-proxy-no-key-required
OPENROUTER_API_KEY=unused
ANTHROPIC_API_KEY=unused
EOF
```

The harness routes any `openai/<model>` id through `OPENAI_BASE_URL`
(see `agent_harness/openhands_runner._resolve_llm_auth`), and the agent forwards
`OPENAI_*` into the container automatically.

### Available Claude models on the proxy

`claude-opus-4.6`, `claude-opus-4.7`, `claude-opus-4.8`, `claude-opus-5`,
`claude-sonnet-4.6`, `claude-sonnet-5`, `claude-haiku-4.5`

## 6. Start the proxy bridge (keep running)

In its own terminal, leave this running while you run tasks:

```bash
.venv/bin/python scripts/proxy_bridge.py
# [proxy_bridge] forwarding 172.17.0.1:3141 -> 127.0.0.1:3141
```

## 7. Run a single task

```bash
.venv/bin/harbor run -p tasks/finance_meridian_partners_158b9045 \
    --agent-import-path agent_harness.openhands_agent:OpenHandsAgent \
    -m openai/claude-opus-4.8 -n 1 \
    --env-file .env
```

Swap the model with any from the list above, e.g. `-m openai/claude-sonnet-5`.

## 8. Run the full task set (leaderboard config)

Four runs per task across every task directory:

```bash
.venv/bin/harbor run -p tasks/ \
    --agent-import-path agent_harness.openhands_agent:OpenHandsAgent \
    -m openai/claude-opus-4.8 -k 4 \
    --env-file .env
```

Results are written under `jobs/` (gitignored).

## Notes

- Single-task runs (`-n 1`) are the simplest; the default bridge networking
  avoids in-container MCP proxy port collisions.
- The proxy reports `usage: 0` tokens, so Harbor's cost/token totals show as
  unknown for these runs.
