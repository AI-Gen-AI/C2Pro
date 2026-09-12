"""Test Suite ID: TS-BCK-042-001.

Integration-style router coverage for DLQ admin endpoints and admin auth.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
import structlog.testing
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.admin.adapters.http.router import get_dlq_admin_port, router
from src.core.auth.platform_operator import (
    PlatformOperator,
    require_platform_operator,
)

_PLATFORM_OPERATOR = PlatformOperator(
    clerk_user_id="user_c26_integration_operator",
    clerk_org_id="org_c26_integration_operator",
    email="operator@example.test",
)


@dataclass(slots=True)
class _DLQEntry:
    id: UUID
    tenant_id: UUID
    task_type: str
    document_id: UUID | None
    payload_json: dict[str, Any]
    error_message: str
    error_traceback: str | None
    retry_count: int
    max_retries: int
    status: str
    created_at: datetime
    updated_at: datetime
    next_retry_at: datetime | None


def _make_entry(status: str = "pending") -> _DLQEntry:
    return _DLQEntry(
        id=uuid4(),
        tenant_id=uuid4(),
        task_type="document_analysis",
        document_id=None,
        payload_json={"document_id": str(uuid4())},
        error_message="analysis failed",
        error_traceback=None,
        retry_count=1,
        max_retries=3,
        status=status,
        created_at=datetime(2026, 4, 28, tzinfo=UTC),
        updated_at=datetime(2026, 4, 28, tzinfo=UTC),
        next_retry_at=None,
    )


class _FakeDLQPort:
    def __init__(self, entries: list[_DLQEntry] | None = None) -> None:
        self._entries = entries or [_make_entry()]
        self.entry = self._entries[0]
        self.list_status: str | None = None
        self.retry_ids: list[UUID] = []

    async def list_by_status(
        self, status: str, *, limit: int, offset: int
    ) -> list[_DLQEntry]:
        self.list_status = status
        matching = [e for e in self._entries if e.status == status]
        return matching[offset : offset + limit]

    async def count_by_status(self, status: str) -> int:
        return sum(1 for e in self._entries if e.status == status)

    async def get_by_id(self, dlq_id: UUID) -> _DLQEntry | None:
        return next((e for e in self._entries if e.id == dlq_id), None)

    async def retry(self, dlq_id: UUID) -> None:
        self.retry_ids.append(dlq_id)


class _FailingRetryPort(_FakeDLQPort):
    """Port whose retry() always raises — to test audit log on failure."""

    async def retry(self, dlq_id: UUID) -> None:
        raise RuntimeError("db_down")


def _app(
    fake_port: _FakeDLQPort,
    *,
    platform_operator: PlatformOperator | None = _PLATFORM_OPERATOR,
) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_dlq_admin_port] = lambda: fake_port
    if platform_operator is not None:
        app.dependency_overrides[require_platform_operator] = lambda: platform_operator
    return app


# ---------------------------------------------------------------------------
# List endpoint — basic access control
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_platform_operator_can_list_dlq_entries_by_status() -> None:
    """TS-BCK-042-001: GET /admin/dlq returns entries for platform operators."""
    fake_port = _FakeDLQPort()
    app = _app(fake_port)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": "Bearer platform-operator-token"},
    ) as client:
        response = await client.get("/api/v1/admin/dlq", params={"status": "pending"})

    assert response.status_code == 200
    body = response.json()
    assert body["entries"][0]["id"] == str(fake_port.entry.id)
    assert body["entries"][0]["tenant_id"] == str(fake_port.entry.tenant_id)
    assert body["entries"][0]["status"] == "pending"
    assert fake_port.list_status == "pending"


@pytest.mark.asyncio
async def test_non_platform_caller_returns_403_for_list_endpoint() -> None:
    """TS-BCK-042-001: a caller without a platform identity cannot list entries."""
    fake_port = _FakeDLQPort()
    app = _app(fake_port, platform_operator=None)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": "Bearer non-platform-token"},
    ) as client:
        response = await client.get("/api/v1/admin/dlq", params={"status": "pending"})

    assert response.status_code == 403
    assert fake_port.list_status is None


# ---------------------------------------------------------------------------
# List endpoint — pagination shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_response_includes_pagination_metadata() -> None:
    """TS-BCK-042-001: response body carries total, limit, offset, has_more."""
    fake_port = _FakeDLQPort()
    app = _app(fake_port)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": "Bearer platform-operator-token"},
    ) as client:
        response = await client.get(
            "/api/v1/admin/dlq",
            params={"status": "pending", "limit": 10, "offset": 0},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["limit"] == 10
    assert body["offset"] == 0
    assert body["has_more"] is False


@pytest.mark.asyncio
async def test_list_has_more_true_when_entries_remain() -> None:
    """TS-BCK-042-001: has_more=True when a subsequent page exists."""
    entries = [_make_entry() for _ in range(5)]
    fake_port = _FakeDLQPort(entries=entries)
    app = _app(fake_port)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": "Bearer platform-operator-token"},
    ) as client:
        response = await client.get(
            "/api/v1/admin/dlq",
            params={"status": "pending", "limit": 2, "offset": 0},
        )

    body = response.json()
    assert len(body["entries"]) == 2
    assert body["total"] == 5
    assert body["has_more"] is True


@pytest.mark.asyncio
async def test_list_has_more_false_on_last_page() -> None:
    """TS-BCK-042-001: has_more=False on the final page."""
    entries = [_make_entry() for _ in range(3)]
    fake_port = _FakeDLQPort(entries=entries)
    app = _app(fake_port)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": "Bearer platform-operator-token"},
    ) as client:
        response = await client.get(
            "/api/v1/admin/dlq",
            params={"status": "pending", "limit": 2, "offset": 2},
        )

    body = response.json()
    assert len(body["entries"]) == 1
    assert body["total"] == 3
    assert body["has_more"] is False


@pytest.mark.asyncio
async def test_list_defaults_to_limit_50_offset_0() -> None:
    """TS-BCK-042-001: omitting limit/offset uses the documented defaults."""
    fake_port = _FakeDLQPort()
    app = _app(fake_port)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": "Bearer platform-operator-token"},
    ) as client:
        response = await client.get("/api/v1/admin/dlq", params={"status": "pending"})

    body = response.json()
    assert body["limit"] == 50
    assert body["offset"] == 0


# ---------------------------------------------------------------------------
# Retry endpoint — basic access control
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_platform_operator_can_retry_dlq_entry() -> None:
    """TS-BCK-042-001: POST /admin/dlq/{id}/retry retries the selected entry."""
    fake_port = _FakeDLQPort()
    app = _app(fake_port)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": "Bearer platform-operator-token"},
    ) as client:
        response = await client.post(f"/api/v1/admin/dlq/{fake_port.entry.id}/retry")

    assert response.status_code == 200
    assert response.json() == {"id": str(fake_port.entry.id), "status": "retrying"}
    assert fake_port.retry_ids == [fake_port.entry.id]


@pytest.mark.asyncio
async def test_non_platform_caller_returns_403_for_retry_endpoint() -> None:
    """TS-BCK-042-001: a caller without a platform identity cannot retry entries."""
    fake_port = _FakeDLQPort()
    app = _app(fake_port, platform_operator=None)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": "Bearer non-platform-token"},
    ) as client:
        response = await client.post(f"/api/v1/admin/dlq/{fake_port.entry.id}/retry")

    assert response.status_code == 403
    assert fake_port.retry_ids == []


# ---------------------------------------------------------------------------
# Retry endpoint — audit log
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_emits_structured_audit_log() -> None:
    """TS-BCK-042-001: retry emits the platform-operator audit payload."""
    fake_port = _FakeDLQPort()
    app = _app(fake_port)

    with structlog.testing.capture_logs() as cap:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
            headers={"Authorization": "Bearer platform-operator-token"},
        ) as client:
            response = await client.post(f"/api/v1/admin/dlq/{fake_port.entry.id}/retry")

    assert response.status_code == 200
    audit_events = [e for e in cap if e.get("event") == "platform_operator_dlq_retry"]
    assert len(audit_events) == 1
    evt = audit_events[0]
    assert evt["operator_id"] == _PLATFORM_OPERATOR.clerk_user_id
    assert evt["org_id"] == _PLATFORM_OPERATOR.clerk_org_id
    assert evt["dlq_id"] == str(fake_port.entry.id)
    assert evt["tenant_id"] == str(fake_port.entry.tenant_id)


@pytest.mark.asyncio
async def test_retry_does_not_emit_audit_log_when_retry_fails() -> None:
    """TS-BCK-042-001: C2.6 records a retry audit event only after success."""
    fake_port = _FailingRetryPort()
    app = _app(fake_port)

    with structlog.testing.capture_logs() as cap:
        async with AsyncClient(
            # raise_app_exceptions=False lets unhandled errors come back as 500
            # responses rather than propagating through httpx.
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://testserver",
            headers={"Authorization": "Bearer platform-operator-token"},
        ) as client:
            # Port.retry() raises RuntimeError → 500
            response = await client.post(f"/api/v1/admin/dlq/{fake_port.entry.id}/retry")

    assert response.status_code == 500
    audit_events = [e for e in cap if e.get("event") == "platform_operator_dlq_retry"]
    assert audit_events == []
