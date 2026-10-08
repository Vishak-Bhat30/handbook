"""Append-only JSONL ledger of the conversation, written by the runner callback.

Hook processes are separate subprocesses with no access to conversation
history, so the runner mirrors every event here and hooks rebuild state from it.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from . import config


def path() -> Path:
    return config.state_dir() / "ledger.jsonl"


def append(record: dict[str, Any]) -> None:
    record = {"t": time.time(), **record}
    config.write_shared(path(), json.dumps(record, ensure_ascii=False, default=str) + "\n", append=True)


def read(ledger_path: Path | None = None) -> list[dict[str, Any]]:
    p = ledger_path or path()
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def record_event(event: Any) -> None:
    """Translate an OpenHands SDK event into a ledger record (runner side)."""
    from openhands.sdk import MessageEvent
    from openhands.sdk.event import ActionEvent, ObservationEvent
    from openhands.sdk.llm.message import content_to_str

    try:
        from openhands.sdk.event import UserRejectObservation
    except ImportError:  # pragma: no cover - older SDKs
        UserRejectObservation = ()  # type: ignore[assignment]

    if isinstance(event, ActionEvent):
        raw = getattr(getattr(event, "tool_call", None), "arguments", None)
        try:
            args = json.loads(raw) if raw else {}
        except (TypeError, json.JSONDecodeError):
            args = {"_raw": raw}
        append({"type": "action", "id": event.id, "call_id": event.tool_call_id,
                "tool": event.tool_name, "args": args})
    elif isinstance(event, ObservationEvent):
        text = "".join(content_to_str(event.observation.to_llm_content)) if event.observation else ""
        append({"type": "observation", "call_id": event.tool_call_id, "action_id": event.action_id,
                "tool": event.tool_name, "text": text})
    elif UserRejectObservation and isinstance(event, UserRejectObservation):
        append({"type": "rejection", "call_id": event.tool_call_id, "action_id": event.action_id,
                "tool": event.tool_name, "text": event.rejection_reason,
                "source": str(getattr(event, "rejection_source", ""))})
    elif isinstance(event, MessageEvent):
        msg = getattr(event, "llm_message", None)
        text = "".join(content_to_str(msg.content)) if msg is not None else ""
        if text.strip():
            append({"type": f"{event.source}_message", "text": text})
