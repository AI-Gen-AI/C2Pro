"""Runtime compatibility checks for the supported Uvicorn floor."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterable
from pathlib import Path
from socket import AF_INET, SOCK_STREAM, socket
from typing import Any

from starlette.routing import BaseRoute, WebSocketRoute

HOST = "127.0.0.1"
STARTUP_TIMEOUT_SECONDS = 30
SHUTDOWN_TIMEOUT_SECONDS = 15


def create_c2pro_app() -> Any:
    """Load the production routing surface for the subprocess smoke test."""
    from src.main import app

    return app


async def proxy_scope_probe(
    scope: dict[str, Any], receive: Any, send: Any
) -> None:
    """Expose the HTTP scope after Uvicorn applies its proxy-header middleware."""
    assert scope["type"] == "http"
    body = json.dumps(
        {
            "client_host": scope["client"][0],
            "scheme": scope["scheme"],
        }
    ).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": body})


def _unused_port() -> int:
    with socket(AF_INET, SOCK_STREAM) as listener:
        listener.bind((HOST, 0))
        return int(listener.getsockname()[1])


def _start_uvicorn(app: str, *, factory: bool = False) -> tuple[subprocess.Popen[str], int]:
    port = _unused_port()
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        app,
        "--host",
        HOST,
        "--port",
        str(port),
        "--lifespan",
        "off",
        "--log-level",
        "info",
    ]
    if factory:
        command.append("--factory")

    environment = os.environ.copy()
    environment.pop("FORWARDED_ALLOW_IPS", None)
    process = subprocess.Popen(
        command,
        cwd=Path(__file__).resolve().parents[2],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return process, port


def _get_json(
    process: subprocess.Popen[str],
    port: int,
    *,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    request = urllib.request.Request(f"http://{HOST}:{port}/health/live", headers=headers or {})

    while time.monotonic() < deadline:
        if process.poll() is not None:
            output, _ = process.communicate()
            raise AssertionError(f"Uvicorn exited before becoming ready:\n{output}")
        try:
            with urllib.request.urlopen(request, timeout=1) as response:
                assert response.status == 200
                return dict(json.load(response))
        except (ConnectionError, TimeoutError, urllib.error.URLError):
            time.sleep(0.1)

    raise AssertionError("Uvicorn did not serve /health/live before the startup timeout")


def _terminate_gracefully(process: subprocess.Popen[str]) -> str:
    process.send_signal(signal.SIGTERM)
    try:
        output, _ = process.communicate(timeout=SHUTDOWN_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        output, _ = process.communicate()
        raise AssertionError(f"Uvicorn did not stop after SIGTERM:\n{output}")

    assert process.returncode in {0, -signal.SIGTERM}, output
    return output


def _kill_if_running(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.kill()
        process.communicate()


def _walk_routes(routes: Iterable[BaseRoute]) -> Iterable[BaseRoute]:
    for route in routes:
        yield route
        nested_routes = getattr(route, "routes", None)
        if nested_routes:
            yield from _walk_routes(nested_routes)


def test_real_c2pro_server_serves_liveness_and_stops_cleanly_on_sigterm() -> None:
    process, port = _start_uvicorn(
        "tests.integration.test_uvicorn_runtime:create_c2pro_app",
        factory=True,
    )
    try:
        assert _get_json(process, port) == {"status": "ok"}
        output = _terminate_gracefully(process)
    finally:
        _kill_if_running(process)

    assert "Shutting down" in output
    assert "Finished server process" in output


def test_default_trusted_proxy_headers_reach_the_asgi_scope() -> None:
    process, port = _start_uvicorn("tests.integration.test_uvicorn_runtime:proxy_scope_probe")
    try:
        payload = _get_json(
            process,
            port,
            headers={
                "X-Forwarded-For": "203.0.113.9",
                "X-Forwarded-Proto": "https",
            },
        )
        _terminate_gracefully(process)
    finally:
        _kill_if_running(process)

    assert payload == {"client_host": "203.0.113.9", "scheme": "https"}


def test_c2pro_routing_surface_has_no_websocket_routes() -> None:
    from src.main import app

    websocket_routes = [
        route for route in _walk_routes(app.routes) if isinstance(route, WebSocketRoute)
    ]

    assert websocket_routes == []
