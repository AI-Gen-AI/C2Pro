"""DLQ admin router contract tests.

Test Suite ID: TS-BCK-042-001
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.dlq.router import get_dlq_service, router
from src.core.middleware.clerk_auth import require_admin
from src.core.security import get_current_tenant_id


class _FakeDLQService:
    def __init__(self) -> None:
        self.tenant_id = uuid4()
        self.dlq_id = uuid4()
        self.retry_calls: list = []

    async def get_by_status(self, tenant_id, status):
        self.list_call = (tenant_id, status)
        return [
            SimpleNamespace(
                id=self.dlq_id,
                tenant_id=tenant_id,
                task_type="document_analysis",
                document_id=None,
                payload_json={"document_id": str(uuid4())},
                error_message="analysis failed",
                error_traceback=None,
                retry_count=1,
                max_retries=3,
                status=status,
                created_at=datetime(2026, 4, 20, tzinfo=UTC),
                updated_at=datetime(2026, 4, 20, tzinfo=UTC),
                next_retry_at=None,
            )
        ]

    async def get_by_id(self, dlq_id):
        if dlq_id != self.dlq_id:
            return None
        return SimpleNamespace(id=dlq_id, tenant_id=self.tenant_id, status="pending")

    async def increment_retry(self, dlq_id):
        self.retry_calls.append(dlq_id)


def _client(fake_service: _FakeDLQService) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_dlq_service] = lambda: fake_service
    app.dependency_overrides[get_current_tenant_id] = lambda: fake_service.tenant_id
    app.dependency_overrides[require_admin] = lambda: object()
    return TestClient(app)


def test_admin_can_list_dlq_tasks_by_status() -> None:
    """TS-BCK-042-001: admin list endpoint returns tenant-filtered DLQ tasks."""
    fake_service = _FakeDLQService()
    client = _client(fake_service)

    response = client.get("/api/v1/admin/dlq", params={"status": "pending"})

    assert response.status_code == 200
    body = response.json()
    assert body["tasks"][0]["id"] == str(fake_service.dlq_id)
    assert body["tasks"][0]["status"] == "pending"
    assert fake_service.list_call == (fake_service.tenant_id, "pending")


def test_admin_can_retry_dlq_task() -> None:
    """TS-BCK-042-001: retry endpoint increments retry state for the selected task."""
    fake_service = _FakeDLQService()
    client = _client(fake_service)

    response = client.post(f"/api/v1/admin/dlq/{fake_service.dlq_id}/retry")

    assert response.status_code == 200
    assert response.json() == {"id": str(fake_service.dlq_id), "status": "retrying"}
    assert fake_service.retry_calls == [fake_service.dlq_id]


def test_retry_dlq_task_rejects_cross_tenant_record() -> None:
    """TS-BCK-042-001: retry endpoint does not expose records from another tenant."""
    fake_service = _FakeDLQService()
    current_tenant_id = uuid4()
    client = _client(fake_service)
    client.app.dependency_overrides[get_current_tenant_id] = lambda: current_tenant_id

    response = client.post(f"/api/v1/admin/dlq/{fake_service.dlq_id}/retry")

    assert response.status_code == 404
    assert fake_service.retry_calls == []
