"""P0 CORE original-source report endpoint: access before source reads."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.core.auth.dependencies import get_current_user
from src.reporting.adapters.http import router as reporting_router_module
from src.reporting.adapters.http.router import get_project_repository, router


class Projects:
    def __init__(self, tenant_id: UUID, project_id: UUID):
        self.tenant_id = tenant_id
        self.project_id = project_id

    async def get_by_id(self, project_id: UUID, tenant_id: UUID):
        if tenant_id == self.tenant_id and project_id == self.project_id:
            return SimpleNamespace(id=project_id)
        return None


def _app(caller_tenant: UUID, owner_tenant: UUID, project_id: UUID):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def _user():
        return SimpleNamespace(tenant_id=caller_tenant, id=uuid4())

    async def _projects():
        yield Projects(owner_tenant, project_id)

    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_project_repository] = _projects
    return app


async def _get(app: FastAPI, project_id: UUID):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        return await client.get(f"/api/v1/projects/{project_id}/reports/source-evidence")


@pytest.mark.asyncio
async def test_owned_project_can_read_original_rows_without_approval_claim(monkeypatch):
    owner, project = uuid4(), uuid4()
    seen = []

    async def fake_reader(*, tenant_id: UUID, project_id: UUID):
        seen.append((tenant_id, project_id))
        return {
            "state": "SOURCE_OBSERVED_NOT_APPROVED",
            "baseline_approved": False,
            "budget": {
                "observed_rows": 1,
                "preview_rows": [{
                    "source_locator": "Budget!3",
                    "revision_id": str(uuid4()),
                    "fields": {"kind": "line_item", "amount": "1250.00"},
                }],
            },
            "schedule": {"observed_rows": 0, "preview_rows": []},
        }

    monkeypatch.setattr(reporting_router_module, "read_project_source_evidence", fake_reader)
    response = await _get(_app(owner, owner, project), project)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["baseline_approved"] is False
    assert response.json()["budget"]["preview_rows"][0]["source_locator"] == "Budget!3"
    assert seen == [(owner, project)]


@pytest.mark.asyncio
async def test_cross_tenant_and_nonexistent_project_never_read_source(monkeypatch):
    owner, foreign, project = uuid4(), uuid4(), uuid4()
    called = []

    async def forbidden_reader(**kwargs):
        called.append(kwargs)
        raise AssertionError("no source read allowed")

    monkeypatch.setattr(reporting_router_module, "read_project_source_evidence", forbidden_reader)
    denied = await _get(_app(foreign, owner, project), project)
    unknown = await _get(_app(owner, owner, project), uuid4())
    assert denied.status_code == 404
    assert unknown.status_code == 404
    assert denied.json() == unknown.json()
    assert called == []


@pytest.mark.asyncio
async def test_missing_source_table_returns_unavailable_not_zero(monkeypatch):
    owner, project = uuid4(), uuid4()

    async def broken_reader(**kwargs):
        raise RuntimeError("internal database connectivity detail not for UI")

    monkeypatch.setattr(reporting_router_module, "read_project_source_evidence", broken_reader)
    response = await _get(_app(owner, owner, project), project)
    assert response.status_code == 503
    assert "internal database" not in response.text
    assert "not available" in response.json()["detail"]
