#!/usr/bin/env python3
"""HTTP bridge from the Docker network to the host-local model proxy.

Two jobs:

1. Reachability — the model proxy listens on 127.0.0.1:3141 (host loopback
   only), which task containers cannot reach. This bridge listens on the Docker
   bridge gateway (default 172.17.0.1:3141) and forwards to 127.0.0.1:3141, so
   the in-container agent can connect via
   OPENAI_BASE_URL=http://172.17.0.1:3141/v1.

2. Content flattening — the proxy expects each chat message's ``content`` to be
   a plain string, but the OpenHands SDK (via litellm) sends ``content`` as an
   array of parts (e.g. ``[{"type": "text", "text": "..."}]``). The proxy then
   crashes with ``(msg.content ?? "").replace is not a function``. This bridge
   rewrites ``/v1/chat/completions`` request bodies, joining each message's
   text parts into a single string before forwarding.

Usage:
    python scripts/proxy_bridge.py                # 172.17.0.1:3141 -> 127.0.0.1:3141
    LISTEN_HOST=0.0.0.0 LISTEN_PORT=3141 \
        TARGET_HOST=127.0.0.1 TARGET_PORT=3141 python scripts/proxy_bridge.py

Leave it running (e.g. in its own terminal) while you run harbor.
"""

from __future__ import annotations

import http.client
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LISTEN_HOST = os.environ.get("LISTEN_HOST", "172.17.0.1")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "3141"))
TARGET_HOST = os.environ.get("TARGET_HOST", "127.0.0.1")
TARGET_PORT = int(os.environ.get("TARGET_PORT", "3141"))

# Hop-by-hop headers must not be forwarded (RFC 7230 §6.1).
HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def _flatten_content(content):
    """Turn an array-of-parts ``content`` into a plain string.

    Leaves strings (and anything else non-list) untouched.
    """
    if not isinstance(content, list):
        return content
    parts: list[str] = []
    for part in content:
        if isinstance(part, str):
            parts.append(part)
        elif isinstance(part, dict):
            text = part.get("text")
            if isinstance(text, str):
                parts.append(text)
            # Non-text parts (e.g. image_url) can't be represented as a string
            # for this proxy; drop them rather than crash the request.
    return "".join(parts)


def _transform_body(raw: bytes) -> bytes:
    """Flatten message content arrays in a chat-completions payload."""
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return raw
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return raw
    changed = False
    for msg in messages:
        if isinstance(msg, dict) and isinstance(msg.get("content"), list):
            msg["content"] = _flatten_content(msg["content"])
            changed = True
    if not changed:
        return raw
    return json.dumps(payload).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args) -> None:  # quieter default logging
        pass

    def _proxy(self, method: str) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""

        if body and self.path.rstrip("/").endswith("/chat/completions"):
            body = _transform_body(body)

        fwd_headers = {
            k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP
        }
        fwd_headers.pop("Host", None)  # http.client sets this for the upstream
        if body:
            fwd_headers["Content-Length"] = str(len(body))

        try:
            conn = http.client.HTTPConnection(TARGET_HOST, TARGET_PORT, timeout=900)
            conn.request(method, self.path, body=body or None, headers=fwd_headers)
            resp = conn.getresponse()
        except OSError as exc:
            self.send_error(502, f"upstream connect failed: {exc}")
            return

        self.send_response_only(resp.status, resp.reason)
        for k, v in resp.getheaders():
            if k.lower() in HOP_BY_HOP or k.lower() == "content-length":
                continue
            self.send_header(k, v)
        # Stream the body; force close framing so SSE/unknown-length works.
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            while True:
                chunk = resp.read1(65536) if hasattr(resp, "read1") else resp.read(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except OSError:
            pass
        finally:
            conn.close()
        self.close_connection = True

    def do_GET(self) -> None:
        self._proxy("GET")

    def do_POST(self) -> None:
        self._proxy("POST")

    def do_DELETE(self) -> None:
        self._proxy("DELETE")

    def do_PUT(self) -> None:
        self._proxy("PUT")


def main() -> None:
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), Handler)
    print(
        f"[proxy_bridge] HTTP bridge {LISTEN_HOST}:{LISTEN_PORT} "
        f"-> {TARGET_HOST}:{TARGET_PORT} (flattening chat content; Ctrl-C to stop)"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[proxy_bridge] shutting down")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
