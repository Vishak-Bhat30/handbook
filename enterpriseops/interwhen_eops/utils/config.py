"""Paths, models and endpoints; every setting can be overridden by environment variable."""

from __future__ import annotations

import os
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent.parent
POLICIES_DIR = PKG_DIR / "policies"
SPLIT_PATH = PKG_DIR / "split.json"

DATASET = "ServiceNow-AI/EnterpriseOps-Gym"
DATASET_REVISION = "c8e538eae8a6205294f0a86675fefdc1fac408f6"
DOMAINS = ("teams", "csm", "email", "itsm", "calendar", "hr", "drive", "hybrid")
RUNTIME_VERSION = "v5-generated-extraction"
SCORING_VERSION = "numeric-sql-v2"
TOOL_CONTRACT = "teams-source-v2"

MODELS = {"agent": "claude-opus-5", "creator": "claude-opus-5", "reviewer": "claude-opus-5",
          "extractor": "claude-sonnet-5", "planner": "claude-sonnet-5"}
AGENT_SETTINGS = {"llm_provider": "vllm", "temperature": 0.1, "max_tokens": 16384}
MAX_ITERATIONS = 50


def model(role: str) -> str:
    """Model name for a role.

    Args:
        role: One of ``MODELS`` (agent, creator, reviewer, extractor, planner).

    Returns:
        ``INTERWHEN_<ROLE>_MODEL`` if set, else the default.
    """
    return os.environ.get(f"INTERWHEN_{role.upper()}_MODEL", MODELS[role])


def endpoint() -> str:
    """OpenAI-compatible base URL (``INTERWHEN_ENDPOINT``), without a trailing slash."""
    return os.environ.get("INTERWHEN_ENDPOINT", "http://127.0.0.1:3141/v1").rstrip("/")


def api_key() -> str:
    """API key for the agent endpoint (``INTERWHEN_API_KEY``)."""
    return os.environ.get("INTERWHEN_API_KEY", "EMPTY")


def gym_repo() -> Path:
    """EnterpriseOps-Gym checkout (``ENTERPRISEOPS_REPO``).

    Raises:
        RuntimeError: If the variable is not set.
    """
    value = os.environ.get("ENTERPRISEOPS_REPO")
    if not value:
        raise RuntimeError("Set ENTERPRISEOPS_REPO to an EnterpriseOps-Gym checkout")
    return Path(value).resolve()


def runs_dir() -> Path:
    """Root for pipeline and evaluation outputs (``INTERWHEN_RUNS_DIR``, default ``enterpriseops/runs``)."""
    return Path(os.environ.get("INTERWHEN_RUNS_DIR", PKG_DIR.parent / "runs")).resolve()


def plan_enabled() -> bool:
    """Whether wrap-up planner reminders are on (``INTERWHEN_ENABLE_PLAN``)."""
    return os.environ.get("INTERWHEN_ENABLE_PLAN", "1").strip().lower() in {"1", "true", "yes", "on"}


def plan_max_nudges() -> int:
    """Maximum planner reminders per task (``INTERWHEN_PLAN_MAX_NUDGES``)."""
    return int(os.environ.get("INTERWHEN_PLAN_MAX_NUDGES", "2"))
