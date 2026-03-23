"""TS-OPS-HLT-WRK-001

Regression tests for Celery worker health endpoint.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.core.routers import health as health_router_module


class _DummyInspect:
    def __init__(self, ping_result, queues_result) -> None:
        self._ping_result = ping_result
        self._queues_result = queues_result

    def ping(self):
        return self._ping_result

    def active_queues(self):
        return self._queues_result


class _DummyControl:
    def __init__(self, ping_result, queues_result) -> None:
        self._ping_result = ping_result
        self._queues_result = queues_result

    def inspect(self):
        return _DummyInspect(self._ping_result, self._queues_result)


def _stub_celery_app(ping_result, queues_result) -> SimpleNamespace:
    return SimpleNamespace(control=_DummyControl(ping_result, queues_result))


@pytest.mark.asyncio
async def test_worker_health_reports_healthy_worker_consuming_document_queue(client, monkeypatch) -> None:
    monkeypatch.setattr(
        health_router_module,
        "celery_app",
        _stub_celery_app(
            {"worker-a": {"ok": "pong"}},
            {"worker-a": [{"name": "document_parsing"}, {"name": "celery"}]},
        ),
    )

    response = await client.get("/api/v1/health/worker")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["queue"] == "document_parsing"
    assert payload["workers_online"] == ["worker-a"]
    assert payload["workers_consuming_queue"] == ["worker-a"]


@pytest.mark.asyncio
async def test_worker_health_fails_when_no_worker_consumes_document_queue(client, monkeypatch) -> None:
    monkeypatch.setattr(
        health_router_module,
        "celery_app",
        _stub_celery_app(
            {"worker-a": {"ok": "pong"}},
            {"worker-a": [{"name": "celery"}]},
        ),
    )

    response = await client.get("/api/v1/health/worker")

    assert response.status_code == 503
    payload = response.json()["detail"]
    assert payload["status"] == "unhealthy"
    assert payload["queue"] == "document_parsing"
    assert payload["workers_online"] == ["worker-a"]
    assert payload["workers_consuming_queue"] == []
