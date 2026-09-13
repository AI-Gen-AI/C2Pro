"""TS-P0D-REPORT-003 - Current State Report HTTP contract."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.core.auth.dependencies import get_current_user
from src.procurement.application.budget_use_cases import BudgetResponse
from src.projects.domain.models import ProjectStatus
from src.reporting.adapters.http.router import (
    get_current_state_sources,
    get_project_repository,
    router,
)
from src.reporting.application.ports import DocumentsInput, HitlInput, StakeholdersInput
from src.stakeholders.application.dtos import RaciMatrixViewResponse


class _Projects:
    def __init__(self, owner_tenant: UUID, project_id: UUID) -> None:
        self.owner_tenant = owner_tenant
        self.project_id = project_id
        self.calls: list[tuple[UUID, UUID]] = []

    async def get_by_id(self, project_id: UUID, tenant_id: UUID):  # noqa: ANN201
        self.calls.append((project_id, tenant_id))
        if project_id != self.project_id or tenant_id != self.owner_tenant:
            return None
        return SimpleNamespace(
            id=project_id,
            name="Hospital North",
            code="HN-01",
            status=ProjectStatus.ACTIVE,
        )


class _Sources:
    def __init__(self) -> None:
        self.tenants: set[UUID] = set()

    async def _seen(self, tenant_id: UUID) -> None:
        self.tenants.add(tenant_id)

    async def load_documents(self, project_id: UUID, tenant_id: UUID) -> DocumentsInput:
        await self._seen(tenant_id)
        return DocumentsInput(documents=[], total=0)

    async def load_health(self, project_id: UUID, tenant_id: UUID):  # noqa: ANN201
        await self._seen(tenant_id)
        return None

    async def load_coherence(self, project_id: UUID, tenant_id: UUID):  # noqa: ANN201
        await self._seen(tenant_id)
        return None

    async def load_alerts(self, project_id: UUID, tenant_id: UUID):  # noqa: ANN201
        await self._seen(tenant_id)
        return []

    async def load_hitl(self, project_id: UUID, tenant_id: UUID) -> HitlInput:
        await self._seen(tenant_id)
        return HitlInput(items=[], pending_count=0)

    async def load_budget(self, project_id: UUID, tenant_id: UUID) -> BudgetResponse:
        await self._seen(tenant_id)
        return BudgetResponse(project_id=project_id, items=[])

    async def load_wbs(self, project_id: UUID, tenant_id: UUID):  # noqa: ANN201
        await self._seen(tenant_id)
        return []

    async def load_stakeholders(self, project_id: UUID, tenant_id: UUID) -> StakeholdersInput:
        await self._seen(tenant_id)
        return StakeholdersInput(stakeholders=[], total=0)

    async def load_raci(self, project_id: UUID, tenant_id: UUID) -> RaciMatrixViewResponse:
        await self._seen(tenant_id)
        return RaciMatrixViewResponse(matrix=[])


def _app(*, caller_tenant: UUID, owner_tenant: UUID, project_id: UUID, sources: _Sources) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def _user() -> SimpleNamespace:
        return SimpleNamespace(tenant_id=caller_tenant, id=uuid4())

    async def _projects():  # noqa: ANN202
        yield _Projects(owner_tenant, project_id)

    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_project_repository] = _projects
    app.dependency_overrides[get_current_state_sources] = lambda: sources
    return app


async def _get(app: FastAPI, project_id: UUID):  # noqa: ANN202
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(f"/api/v1/projects/{project_id}/reports/current-state")


async def test_owned_project_returns_current_state_report() -> None:
    tenant_id, project_id = uuid4(), uuid4()
    sources = _Sources()
    response = await _get(
        _app(caller_tenant=tenant_id, owner_tenant=tenant_id, project_id=project_id, sources=sources),
        project_id,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["report_schema_version"] == "current-state-report/v1"
    assert body["project"] == {"id": str(project_id), "name": "Hospital North", "code": "HN-01", "status": "active"}
    assert body["sections"]["risks"]["status"] == "not_modeled"
    assert body["sections"]["health"]["status"] == "unavailable"
    assert body["sections"]["budget"]["status"] == "empty"
    assert datetime.fromisoformat(body["generated_at"]).tzinfo is not None
    assert len(body["content_fingerprint"]) == 64
    assert sources.tenants == {tenant_id}


async def test_foreign_tenant_gets_404_indistinguishable_from_missing() -> None:
    owner, caller, project_id = uuid4(), uuid4(), uuid4()
    sources = _Sources()
    foreign = await _get(_app(caller_tenant=caller, owner_tenant=owner, project_id=project_id, sources=sources), project_id)
    missing = await _get(_app(caller_tenant=owner, owner_tenant=owner, project_id=project_id, sources=sources), uuid4())
    assert foreign.status_code == 404
    assert missing.status_code == 404
    assert foreign.json() == missing.json() == {"detail": "Project not found"}
    assert sources.tenants == set(), "no domain source may be read for a project the caller cannot see"


async def test_report_response_is_not_cacheable() -> None:
    tenant_id, project_id = uuid4(), uuid4()
    response = await _get(
        _app(caller_tenant=tenant_id, owner_tenant=tenant_id, project_id=project_id, sources=_Sources()),
        project_id,
    )
    assert response.headers.get("cache-control") == "no-store"


async def test_generated_at_reflects_request_time() -> None:
    tenant_id, project_id = uuid4(), uuid4()
    before = datetime.now(UTC)
    response = await _get(
        _app(caller_tenant=tenant_id, owner_tenant=tenant_id, project_id=project_id, sources=_Sources()),
        project_id,
    )
    after = datetime.now(UTC)
    generated_at = datetime.fromisoformat(response.json()["generated_at"])
    assert before <= generated_at <= after
