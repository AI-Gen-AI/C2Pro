"""TS-AI-LANGSMITH-014: Unit tests for POST /api/v1/ai/feedback."""

from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.ai.feedback_router import (
    get_feedback_client,
    get_usage_logger,
    router,
)
from src.core.security import get_current_tenant_id


class _StubUsageLogger:
    def __init__(self, *, owns_trace: bool) -> None:
        self._owns_trace = owns_trace
        self.calls: list[tuple[str, str]] = []

    async def tenant_owns_trace(self, *, tenant_id, trace_id: str) -> bool:
        self.calls.append((str(tenant_id), trace_id))
        return self._owns_trace


class _StubFeedbackClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, float, str | None]] = []

    def create_feedback(self, *, run_id: str, score: float, comment: str | None):
        self.calls.append((run_id, score, comment))
        return {"id": "fb_123"}


def _build_client(*, owns_trace: bool) -> tuple[TestClient, _StubFeedbackClient]:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    usage_logger = _StubUsageLogger(owns_trace=owns_trace)
    feedback_client = _StubFeedbackClient()

    app.dependency_overrides[get_current_tenant_id] = lambda: uuid4()
    app.dependency_overrides[get_usage_logger] = lambda: usage_logger
    app.dependency_overrides[get_feedback_client] = lambda: feedback_client

    return TestClient(app, raise_server_exceptions=False), feedback_client


def test_feedback_endpoint_accepts_owned_trace() -> None:
    client, feedback_client = _build_client(owns_trace=True)
    response = client.post(
        "/api/v1/ai/feedback",
        json={"trace_id": "run-123", "score": 0.9, "comment": "Accurate response"},
    )
    assert response.status_code == 201
    assert response.json() == {"status": "accepted", "trace_id": "run-123"}
    assert feedback_client.calls == [("run-123", 0.9, "Accurate response")]


def test_feedback_endpoint_blocks_cross_tenant_trace() -> None:
    client, feedback_client = _build_client(owns_trace=False)
    response = client.post(
        "/api/v1/ai/feedback",
        json={"trace_id": "run-123", "score": 0.2},
    )
    assert response.status_code == 404
    assert feedback_client.calls == []
