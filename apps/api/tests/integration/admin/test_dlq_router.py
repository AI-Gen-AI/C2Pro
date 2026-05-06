"""Test Suite ID: TS-BCK-042-001.

Integration-style router coverage for DLQ admin endpoints and admin auth.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.admin.adapters.http.router import get_dlq_admin_port, router
from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User, UserRole


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


class _FakeDLQPort:
    def __init__(self) -> None:
        self.entry = _DLQEntry(
            id=uuid4(),
            tenant_id=uuid4(),
            task_type="document_analysis",
            document_id=None,
            payload_json={"document_id": str(uuid4())},
            error_message="analysis failed",
            error_traceback=None,
            retry_count=1,
            max_retries=3,
            status="pending",
            created_at=datetime(2026, 4, 28, tzinfo=UTC),
            updated_at=datetime(2026, 4, 28, tzinfo=UTC),
            next_retry_at=None,
        )
        self.list_status: str | None = None
        self.retry_ids: list[UUID] = []

    async def list_by_status(self, status: str) -> list[_DLQEntry]:
        self.list_status = status
        return [self.entry]

    async def get_by_id(self, dlq_id: UUID) -> _DLQEntry | None:
        return self.entry if dlq_id == self.entry.id else None

    async def retry(self, dlq_id: UUID) -> None:
        self.retry_ids.append(dlq_id)


def _user(role: UserRole) -> User:
    return User(
        id=uuid4(),
        tenant_id=uuid4(),
        email=f"{role.value}@example.com",
        hashed_password="x",
        first_name="Test",
        last_name="User",
        role=role,
        is_active=True,
        is_verified=True,
    )


def _app(fake_port: _FakeDLQPort, *, role: UserRole = UserRole.ADMIN) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_dlq_admin_port] = lambda: fake_port
    app.dependency_overrides[get_current_user] = lambda: _user(role)
    return app


@pytest.mark.asyncio
async def test_admin_can_list_dlq_entries_by_status() -> None:
    """TS-BCK-042-001: GET /admin/dlq returns DLQ entries for admin users."""
    fake_port = _FakeDLQPort()
    app = _app(fake_port)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": "Bearer admin-token"},
    ) as client:
        response = await client.get("/api/v1/admin/dlq", params={"status": "pending"})

    assert response.status_code == 200
    body = response.json()
    assert body["entries"][0]["id"] == str(fake_port.entry.id)
    assert body["entries"][0]["tenant_id"] == str(fake_port.entry.tenant_id)
    assert body["entries"][0]["status"] == "pending"
    assert fake_port.list_status == "pending"


@pytest.mark.asyncio
async def test_admin_can_retry_dlq_entry() -> None:
    """TS-BCK-042-001: POST /admin/dlq/{id}/retry retries the selected entry."""
    fake_port = _FakeDLQPort()
    app = _app(fake_port)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": "Bearer admin-token"},
    ) as client:
        response = await client.post(f"/api/v1/admin/dlq/{fake_port.entry.id}/retry")

    assert response.status_code == 200
    assert response.json() == {"id": str(fake_port.entry.id), "status": "retrying"}
    assert fake_port.retry_ids == [fake_port.entry.id]


@pytest.mark.asyncio
async def test_non_admin_token_returns_403_for_list_endpoint() -> None:
    """TS-BCK-042-001: non-admin Clerk users cannot list DLQ entries."""
    fake_port = _FakeDLQPort()
    app = _app(fake_port, role=UserRole.USER)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": "Bearer non-admin-token"},
    ) as client:
        response = await client.get("/api/v1/admin/dlq", params={"status": "pending"})

    assert response.status_code == 403
    assert fake_port.list_status is None


@pytest.mark.asyncio
async def test_non_admin_token_returns_403_for_retry_endpoint() -> None:
    """TS-BCK-042-001: non-admin Clerk users cannot retry DLQ entries."""
    fake_port = _FakeDLQPort()
    app = _app(fake_port, role=UserRole.USER)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": "Bearer non-admin-token"},
    ) as client:
        response = await client.post(f"/api/v1/admin/dlq/{fake_port.entry.id}/retry")

    assert response.status_code == 403
    assert fake_port.retry_ids == []
