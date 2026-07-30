"""A private uvicorn for the gate, on its own port.

The gate serves the same FastAPI app the normal launcher does, but on
`GATE_PORT` rather than 8000, so raising the gate never collides with (or gets
silently hijacked by) a normal `python -m engine.cli.app` already running.

Runs in-process on a daemon thread: when the gate exits — cleanly, on a deadman
kill, or by dying outright — the server goes with it, and no orphan is left
serving the study API on a stray port.
"""
from __future__ import annotations

import socket
import threading
import time


def port_is_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def wait_until_ready(port: int, timeout: float, host: str = "127.0.0.1") -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex((host, port)) == 0:
                return True
        time.sleep(0.1)
    return False


def start(port: int, host: str = "127.0.0.1") -> threading.Thread:
    """Serve engine.api on a daemon thread. Caller must wait_until_ready()."""
    import uvicorn

    config = uvicorn.Config(
        "engine.api:app", host=host, port=port, log_level="warning", access_log=False
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="gate-uvicorn", daemon=True)
    thread.start()
    return thread
