"""Harbor agent: OpenHands loop with SOP verifiers (interwhen) attached as SDK hooks.

Uploads ``docker/openhands-runner`` (baseline runner + ``interwhen_runner.py`` +
``interwhen_sop`` package) into the container at setup, so no image rebuild is
needed. Verifier data exists per task under ``interwhen_sop/tasks/<task>``; for
tasks without it the runner falls back to the plain baseline loop.

    harbor run -p tasks/logistics_gear_sytems_inc_9b60992d \
        --agent-import-path agent_harness.interwhen_agent:InterwhenOpenHandsAgent \
        -m openai/claude-opus-4.8 --ak reasoning_effort=max \
        --ak slm_url=http://172.17.0.1:8000/v1 --env-file .env
"""

from __future__ import annotations

import os
from pathlib import Path

from harbor.environments.base import BaseEnvironment

from agent_harness.openhands_agent import OpenHandsAgent

REMOTE_IW_DIR = "/app/openhands-runner-iw"
LOCAL_RUNNER_DIR = Path(
    os.environ.get("INTERWHEN_SOURCE_DIR")
    or Path(__file__).resolve().parents[3] / "docker" / "openhands-runner"
)


class InterwhenOpenHandsAgent(OpenHandsAgent):
    runner_path = f"{REMOTE_IW_DIR}/interwhen_runner.py"

    def __init__(self, *args, **kwargs) -> None:
        self.slm_url = kwargs.pop("slm_url", None) or os.environ.get(
            "INTERWHEN_SLM_URL", "http://172.17.0.1:8000/v1")
        self.max_completion_denials = int(kwargs.pop("max_completion_denials", 3))
        super().__init__(*args, **kwargs)

    @staticmethod
    def name() -> str:
        return "openhands-interwhen"

    def version(self) -> str | None:
        return "0.1.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        await super().setup(environment)
        if not (LOCAL_RUNNER_DIR / "interwhen_runner.py").is_file():
            raise RuntimeError(f"interwhen runner sources missing at {LOCAL_RUNNER_DIR}")
        await environment.upload_dir(str(LOCAL_RUNNER_DIR), REMOTE_IW_DIR)

    def _extra_run_config(self, task_dir: Path) -> dict:
        return {"interwhen": {"task": task_dir.name, "slmUrl": self.slm_url,
                              "maxCompletionDenials": self.max_completion_denials}}
