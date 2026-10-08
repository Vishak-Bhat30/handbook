"""Minimal client for the local extraction SLM (OpenAI-compatible, stdlib only).

The SLM is used for *extraction only*: it returns JSON facts that Python then
grounds against the source text and feeds to Python verifiers. Every failure
returns ``None`` so callers can fall open rather than block on infra errors.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from typing import Any

from . import config

SYSTEM = (
    "You are an information extraction component. Read the provided text and fill the "
    "requested JSON schema using only facts stated in the text. Do not infer policy, do "
    "not judge compliance, do not invent values; use null/false/[] when the text does not "
    "say. Reply with a single JSON object and nothing else."
)
_model_cache: str | None = None


def _cache_path():
    return config.state_dir() / "slm_cache.json"


def _load_cache() -> dict[str, Any]:
    p = _cache_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _save_cache(cache: dict[str, Any]) -> None:
    config.write_shared(_cache_path(), json.dumps(cache, ensure_ascii=False))


def _post(path: str, payload: dict | None, timeout: float) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        f"{config.slm_url()}{path}", data=data,
        headers={"Content-Type": "application/json", "Authorization": "Bearer local"},
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def model_name() -> str | None:
    global _model_cache
    if _model_cache:
        return _model_cache
    if config.slm_model():
        _model_cache = config.slm_model()
        return _model_cache
    try:
        _model_cache = _post("/models", None, 10)["data"][0]["id"]
    except Exception:
        return None
    return _model_cache


def parse_json_answer(content: str) -> dict | None:
    """Take the text after any </think> block and decode the first JSON object."""
    if "</think>" in content:
        content = content.rsplit("</think>", 1)[1]
    content = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.M).strip()
    for i, ch in enumerate(content):
        if ch == "{":
            try:
                obj, _ = json.JSONDecoder().raw_decode(content[i:])
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                continue
    return None


def extract(task: str, schema: str, text: str, *, max_tokens: int = 4096,
            timeout: float = 90, log: list | None = None) -> dict | None:
    """Run one extraction. ``task`` names the extraction for caching/logging."""
    prompt = f"Extraction task: {task}\n\nJSON schema to fill:\n{schema}\n\nText:\n\"\"\"\n{text}\n\"\"\""
    key = hashlib.sha256(prompt.encode()).hexdigest()
    cache = _load_cache()
    if key in cache:
        if log is not None:
            log.append({"extract": task, "cached": True})
        return cache[key]
    model = model_name()
    if model is None:
        if log is not None:
            log.append({"extract": task, "error": "slm unavailable"})
        return None
    t0 = time.time()
    try:
        resp = _post("/chat/completions", {
            "model": model,
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": max_tokens,
        }, timeout)
        content = resp["choices"][0]["message"].get("content") or ""
        result = parse_json_answer(content)
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError, OSError) as exc:
        if log is not None:
            log.append({"extract": task, "error": str(exc)[:200], "secs": round(time.time() - t0, 2)})
        return None
    if log is not None:
        log.append({"extract": task, "secs": round(time.time() - t0, 2), "ok": result is not None})
    if result is not None:
        cache = _load_cache()
        cache[key] = result
        _save_cache(cache)
    return result


def grounded(value: Any, source: str) -> bool:
    """True when an extracted string/number literally occurs in the source text."""
    if value is None:
        return False
    norm = lambda s: re.sub(r"[\s\u2010-\u2015-]+", " ", str(s)).strip().lower()  # noqa: E731
    return norm(value) in norm(source)
