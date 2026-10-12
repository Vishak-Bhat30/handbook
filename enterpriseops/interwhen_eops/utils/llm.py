"""JSON chat calls to the OpenAI-compatible endpoint with pinned model identity.

Offline pipeline calls may name a record directory holding request.json and
response.json; a saved response for an identical request is reused, so an
interrupted stage resumes without repeating completed calls.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from . import config
from .data import read_json, write_json


class ModelIdentityError(RuntimeError):
    """The endpoint answered with a different model; results would not be comparable."""


def extract_json(text: str) -> str:
    """Strip a Markdown code fence, if any, from a model reply."""
    for fence in ("```json", "```"):
        if fence in text:
            return text.split(fence, 1)[1].split("```", 1)[0].strip()
    return text.strip()


def chat_json(system: str, data, role: str, record: Path | None = None):
    """Send ``data`` as JSON to a role's model and parse its JSON reply.

    Args:
        system: System prompt.
        data: JSON-serializable user content.
        role: Model role from ``config.MODELS``.
        record: Optional folder for request.json/response.json, reused on resume.

    Returns:
        The parsed JSON reply.

    Raises:
        ValueError: Malformed or truncated reply (callers may retry).
        ModelIdentityError: The endpoint answered with a different model.
    """
    model = config.model(role)
    payload = {"model": model, "temperature": 0, "max_tokens": 16384, "response_format": {"type": "json_object"},
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": json.dumps(data, ensure_ascii=True)}]}
    saved = record / "response.json" if record else None
    if saved and saved.exists() and read_json(record / "request.json") == payload:
        reply = read_json(saved)
    else:
        response = httpx.post(config.endpoint() + "/chat/completions", json=payload, timeout=600)
        response.raise_for_status()
        reply = response.json()
        if record:
            write_json(record / "request.json", payload)
            write_json(saved, reply)
    if reply.get("model") != model:
        raise ModelIdentityError(f"Model identity changed to {reply.get('model')!r}; no fallback")
    choice = reply["choices"][0]
    if choice.get("finish_reason") not in {None, "stop"}:
        raise ValueError("Model response was not completed")
    return json.loads(extract_json(choice["message"]["content"]))


async def chat_async(client: httpx.AsyncClient, model: str, messages: list[dict]) -> dict:
    """Deterministic JSON-mode completion for the runtime extractor and planner.

    Args:
        client: Open async HTTP client.
        model: Expected model name.
        messages: Chat messages.

    Returns:
        The raw completion response.

    Raises:
        ModelIdentityError: The endpoint answered with a different model.
    """
    response = await client.post(config.endpoint() + "/chat/completions", json={
        "model": model, "temperature": 0, "response_format": {"type": "json_object"}, "messages": messages})
    response.raise_for_status()
    reply = response.json()
    if reply.get("model") != model:
        raise ModelIdentityError(f"Model identity changed to {reply.get('model')!r}")
    return reply
