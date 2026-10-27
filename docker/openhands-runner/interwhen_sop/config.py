"""Runtime configuration shared by the runner, hooks and tests."""

from __future__ import annotations

import os
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
TASKS_DIR = PKG_DIR / "tasks"


def state_dir() -> Path:
    path = Path(os.environ.get("INTERWHEN_STATE_DIR", "/logs/agent/interwhen"))
    make_shared_dir(path)
    return path


def task_id() -> str:
    return os.environ.get("INTERWHEN_TASK", "")


def workdir() -> Path:
    return Path(os.environ.get("INTERWHEN_WORKDIR", "/workdir"))


def slm_url() -> str:
    return os.environ.get("INTERWHEN_SLM_URL", "http://172.17.0.1:8000/v1").rstrip("/")


def slm_model() -> str | None:
    return os.environ.get("INTERWHEN_SLM_MODEL") or None


def xlsx_python() -> str:
    # The runner venv lacks openpyxl; the syntara app venv has it.
    return os.environ.get("INTERWHEN_XLSX_PYTHON", "/app/.venv/bin/python")


MAX_COMPLETION_DENIALS = int(os.environ.get("INTERWHEN_MAX_COMPLETION_DENIALS", "3"))
MAX_STALE_DENIALS = int(os.environ.get("INTERWHEN_MAX_STALE_DENIALS", "1000"))
CHECKLIST = os.environ.get("INTERWHEN_CHECKLIST", "0") == "1"


def make_shared_dir(path: Path) -> None:
    """Create dirs world-writable so root-written logs stay removable on the host."""
    if path.exists():
        return
    old = os.umask(0)
    try:
        path.mkdir(parents=True, exist_ok=True, mode=0o777)
    finally:
        os.umask(old)


def write_shared(path: Path, text: str, append: bool = False) -> None:
    make_shared_dir(path.parent)
    old = os.umask(0)
    try:
        with open(path, "a" if append else "w", encoding="utf-8") as fh:
            fh.write(text)
    finally:
        os.umask(old)
