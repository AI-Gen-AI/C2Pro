"""TS-UD-HEALTH-018-006 - Project health API contract."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.core.auth.dependencies import get_current_user
from src.health.adapters.http.router import get_snapshot_repository, router
from src.health.domain.health_vector import HealthBand, HealthDimension
from src.temporal.domain.project_snapshot import ProjectSnapshot, SnapshotTrigger


class _SnapshotRepo:
    def __init__(self, snapshot: ProjectSnapshot | None) -> None:
        self.snapshot = snapshot

    async def append_snapshot(self, snapshot: ProjectSnapshot) -> ProjectSnapshot:
        return snapshot

    async def latest(self, project_id: UUID, tenant_id: UUID) -> ProjectSnapshot | None:
        if (
            self.snapshot is not None
            and self.snapshot.project_id == project_id
            and self.snapshot.tenant_id == tenant_id
        ):
            return self.snapshot
        return None

    async def list_since(self, project_id, tenant_id, since):  # noqa: ANN001
        return []


def _snapshot(project_id: UUID, tenant_id: UUID, composite_score: float) -> ProjectSnapshot:
    now = datetime.now(UTC).replace(tzinfo=None)
    return ProjectSnapshot(
        snapshot_id=uuid4(),
        project_id=project_id,
        tenant_id=tenant_id,
        captured_at=now,
        trigger=SnapshotTrigger.GRAPH_COMPLETED,
        health_vector={
            "project_id": str(project_id),
            "tenant_id": str(tenant_id),
            "dimensions": [
                {
                    "dimension": "contract",
                    "score": composite_score,
                    "band": "healthy",
                    "confidence": 1.0,
                    "evidence": [
                        {
                            "ref_id": "contract",
                            "source": "test",
                            "tier": "verified",
                            "locator": "contract",
                        }
                    ],
                    "trend": "unknown",
                    "missing_data": [],
                    "null_reason": None,
                }
            ],
            "composite_score": composite_score,
            "composite_band": "healthy",
            "composite_trend": "up",
            "computed_at": now.isoformat(),
        },
        created_at=now,
    )


def _app(repo: _SnapshotRepo, tenant_id: UUID) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def _current_user() -> SimpleNamespace:
        return SimpleNamespace(tenant_id=tenant_id)

    async def _repo() -> _SnapshotRepo:
        return repo

    app.dependency_overrides[get_current_user] = _current_user
    app.dependency_overrides[get_snapshot_repository] = _repo
    return app


@pytest.mark.asyncio
async def test_project_health_returns_latest_snapshot_vector() -> None:
    project_id = uuid4()
    tenant_id = uuid4()
    app = _app(_SnapshotRepo(_snapshot(project_id, tenant_id, 88)), tenant_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/projects/{project_id}/health")

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == str(project_id)
    assert body["tenant_id"] == str(tenant_id)
    assert body["composite_score"] == 88
    assert body["composite_trend"] == "up"


@pytest.mark.asyncio
async def test_project_health_is_tenant_scoped() -> None:
    project_id = uuid4()
    tenant_id = uuid4()
    other_tenant_id = uuid4()
    app = _app(_SnapshotRepo(_snapshot(project_id, other_tenant_id, 88)), tenant_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/projects/{project_id}/health")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == str(tenant_id)
    assert body["composite_score"] is None
    assert body["composite_band"] == HealthBand.UNKNOWN.value
    assert body["composite_trend"] == "unknown"


@pytest.mark.asyncio
async def test_project_health_no_snapshot_returns_honest_insufficient_data_vector() -> None:
    project_id = uuid4()
    tenant_id = uuid4()
    app = _app(_SnapshotRepo(None), tenant_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/projects/{project_id}/health")

    assert response.status_code == 200
    body = response.json()
    assert body["composite_score"] is None
    assert body["composite_band"] == HealthBand.UNKNOWN.value
    dimensions = {item["dimension"]: item for item in body["dimensions"]}
    assert set(dimensions) == {
        HealthDimension.CONTRACT.value,
        HealthDimension.RISK.value,
        HealthDimension.DOCUMENTATION.value,
        HealthDimension.GOVERNANCE.value,
    }
    assert all(item["score"] is None for item in dimensions.values())
    assert all(item["null_reason"] == "insufficient_evidence" for item in dimensions.values())


def test_project_health_openapi_path_is_registered() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    schema = app.openapi()

    assert "/api/v1/projects/{project_id}/health" in schema["paths"]
