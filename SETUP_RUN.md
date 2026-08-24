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
> terminal also picks up the new group. In a shell whose session predates the
> group change, run commands via `sg docker -c "<command>"` to activate the
> group without re-logging.

## 3. Build the base image

The Dockerfile uses `RUN --mount=type=cache ...`, which **requires BuildKit**
(the legacy builder fails with `the --mount option requires BuildKit`). BuildKit
needs the `buildx` CLI plugin. If `docker buildx version` errors, install it into
your user directory (no sudo needed):

```bash
mkdir -p ~/.docker/cli-plugins
VER=$(curl -sSL https://api.github.com/repos/docker/buildx/releases/latest \
    | grep -oP '"tag_name":\s*"\K[^"]+')
curl -sSL "https://github.com/docker/buildx/releases/download/${VER}/buildx-${VER}.linux-amd64" \
    -o ~/.docker/cli-plugins/docker-buildx
chmod +x ~/.docker/cli-plugins/docker-buildx
docker buildx version   # verify
```

Then build (use `sg docker -c "..."` if the docker group isn't active in this
session):

```bash
docker buildx build --load -t handbook_base docker/
```

Harbor also drives each task with `docker compose`, so the **Compose v2 CLI
plugin** must be present. If `docker compose version` errors, install it the same
way (no sudo):

```bash
VER=$(curl -sSL https://api.github.com/repos/docker/compose/releases/latest \
    | grep -oP '"tag_name":\s*"\K[^"]+')
curl -sSL "https://github.com/docker/compose/releases/download/${VER}/docker-compose-linux-x86_64" \
    -o ~/.docker/cli-plugins/docker-compose
chmod +x ~/.docker/cli-plugins/docker-compose
docker compose version   # verify
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
# [proxy_bridge] HTTP bridge 172.17.0.1:3141 -> 127.0.0.1:3141 (flattening chat content; Ctrl-C to stop)
```

The bridge does two things: (1) republishes the host-only proxy on the Docker
bridge gateway so the in-container agent can reach it, and (2) rewrites
`/v1/chat/completions` requests so each message's `content` is a plain string.
The proxy crashes on array-style content
(`(msg.content ?? "").replace is not a function`), but the OpenHands SDK always
sends `content` as an array of parts, so the bridge flattens the text parts into
a single string before forwarding. Non-text parts (e.g. images) are dropped
because the proxy cannot accept them.

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
- The bridge drops non-text content parts (images from `read_pdf` / `read_media`
  tool results) because the proxy only accepts string content; image-heavy task
  steps may be affected.
