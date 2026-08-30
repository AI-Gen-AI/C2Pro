"""TS-UD-HEALTH-018-006 - Project health API contract."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.core.auth.dependencies import get_current_user
from src.core.tenants.types import TenantId
from src.health.adapters.http.router import (
    get_project_repository,
    get_snapshot_repository,
    router,
)
from src.health.domain.health_vector import HealthBand, HealthDimension
from src.projects.adapters.persistence.project_repository import SQLAlchemyProjectRepository
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


class _ProjectRepo:
    """Ownership gate double: does this tenant own this project?"""

    def __init__(self, owned: bool = True) -> None:
        self.owned = owned

    async def exists_by_id(self, project_id: UUID, tenant_id: UUID) -> bool:
        return self.owned


def _app(
    repo: _SnapshotRepo, tenant_id: UUID, *, project_owned: bool = True
) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def _current_user() -> SimpleNamespace:
        return SimpleNamespace(tenant_id=tenant_id)

    async def _repo() -> _SnapshotRepo:
        return repo

    async def _projects() -> _ProjectRepo:
        return _ProjectRepo(project_owned)

    app.dependency_overrides[get_current_user] = _current_user
    app.dependency_overrides[get_snapshot_repository] = _repo
    app.dependency_overrides[get_project_repository] = _projects
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
    """A project this tenant does not own is 404 — never a 200 empty vector."""
    project_id = uuid4()
    tenant_id = uuid4()
    other_tenant_id = uuid4()
    app = _app(
        _SnapshotRepo(_snapshot(project_id, other_tenant_id, 88)),
        tenant_id,
        project_owned=False,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/projects/{project_id}/health")

    assert response.status_code == 404
    assert str(other_tenant_id) not in response.text
    assert "composite_score" not in response.text


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


@pytest.mark.asyncio
async def test_project_health_normalizes_tenant_once_at_http_boundary(monkeypatch) -> None:
    """TS-UD-HEALTH-018-006: pass a normalized tenant into the snapshot port."""
    from src.health.adapters.http import router as health_router

    project_id = uuid4()
    raw_tenant_id = uuid4()
    normalized_tenant_id = TenantId(uuid4())
    normalize = Mock(return_value=normalized_tenant_id)
    repository = SimpleNamespace(latest=AsyncMock(return_value=None))
    projects = SimpleNamespace(exists_by_id=AsyncMock(return_value=True))
    monkeypatch.setattr(health_router, "require_tenant_id", normalize, raising=False)

    result = await health_router.get_project_health(
        project_id=project_id,
        current_user=SimpleNamespace(tenant_id=raw_tenant_id),
        repository=repository,
        projects=projects,
    )

    normalize.assert_called_once_with(raw_tenant_id)
    # The ownership gate is checked with the SAME normalized tenant as the data read.
    projects.exists_by_id.assert_awaited_once_with(project_id, normalized_tenant_id)
    repository.latest.assert_awaited_once_with(project_id, normalized_tenant_id)
    assert result.tenant_id == normalized_tenant_id


@pytest.mark.asyncio
async def test_project_repository_provider_binds_session_to_authenticated_tenant(
    monkeypatch,
) -> None:
    """The ownership gate is only sound if its session is opened for the CALLER's tenant.

    ``get_session_with_tenant`` is what sets the RLS tenant context, so a provider that
    opened the session for anything other than the authenticated user's tenant would let
    the gate read another tenant's projects. Pin the binding, not just the return type.
    """
    from src.health.adapters.http import router as health_router

    tenant_id = uuid4()
    session = object()
    opened_for: list[object] = []

    @asynccontextmanager
    async def _fake_session(requested_tenant_id):
        opened_for.append(requested_tenant_id)
        yield session

    monkeypatch.setattr(health_router, "get_session_with_tenant", _fake_session)

    provided = [
        repo
        async for repo in health_router.get_project_repository(
            current_user=SimpleNamespace(tenant_id=tenant_id)
        )
    ]

    assert opened_for == [tenant_id]
    assert len(provided) == 1
    assert isinstance(provided[0], SQLAlchemyProjectRepository)
    assert provided[0].session is session
