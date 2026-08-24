#!/usr/bin/env python3
"""Forward the Docker bridge gateway to the host-local model proxy.

The model proxy listens on 127.0.0.1:3141 (host loopback only), which task
containers cannot reach. This script republishes it on the Docker bridge
gateway (default 172.17.0.1:3141) so the in-container agent can connect via
OPENAI_BASE_URL=http://172.17.0.1:3141/v1.

Usage:
    python scripts/proxy_bridge.py                # 172.17.0.1:3141 -> 127.0.0.1:3141
    LISTEN_HOST=172.17.0.1 LISTEN_PORT=3141 \
        TARGET_HOST=127.0.0.1 TARGET_PORT=3141 python scripts/proxy_bridge.py

Leave it running (e.g. in its own terminal) while you run harbor.
"""

from __future__ import annotations

import os
import socket
import threading

LISTEN_HOST = os.environ.get("LISTEN_HOST", "172.17.0.1")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "3141"))
TARGET_HOST = os.environ.get("TARGET_HOST", "127.0.0.1")
TARGET_PORT = int(os.environ.get("TARGET_PORT", "3141"))


def _pipe(src: socket.socket, dst: socket.socket) -> None:
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        for s in (src, dst):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def _handle(client: socket.socket) -> None:
    try:
        upstream = socket.create_connection((TARGET_HOST, TARGET_PORT))
    except OSError as exc:
        client.close()
        print(f"[proxy_bridge] upstream connect failed: {exc}")
        return
    threading.Thread(target=_pipe, args=(client, upstream), daemon=True).start()
    threading.Thread(target=_pipe, args=(upstream, client), daemon=True).start()


def main() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((LISTEN_HOST, LISTEN_PORT))
    server.listen(128)
    print(
        f"[proxy_bridge] forwarding {LISTEN_HOST}:{LISTEN_PORT} "
        f"-> {TARGET_HOST}:{TARGET_PORT} (Ctrl-C to stop)"
    )
    try:
        while True:
            client, _ = server.accept()
            threading.Thread(target=_handle, args=(client,), daemon=True).start()
    except KeyboardInterrupt:
        print("\n[proxy_bridge] shutting down")
    finally:
        server.close()


if __name__ == "__main__":
    main()
