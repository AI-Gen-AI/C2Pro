"""Unit tests for Journey Excel export HTTP endpoint (WP JV1-A19).

Verifies:
- GET /projects/{project_id}/reports/journey.xlsx
- 200 OK with valid openpyxl-readable spreadsheet for owned project.
- 404 Not Found for foreign tenant project (tenant isolation).
- 404 Not Found for unknown project.
- Content-Type is application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.
- Cache-Control is no-store.
"""

from __future__ import annotations

import io
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import openpyxl
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.core.auth.dependencies import get_current_user
from src.projects.domain.models import ProjectStatus
from src.reporting.adapters.http.router import (
    get_journey_export_sources,
    get_project_repository,
    router,
)
from src.reporting.application.build_journey_export import (
    JourneyExportData,
    JourneyFindingRow,
    JourneySummaryData,
)


class _MockProjects:
    def __init__(self, owner_tenant: UUID, project_id: UUID) -> None:
        self.owner_tenant = owner_tenant
        self.project_id = project_id

    async def get_by_id(self, project_id: UUID, tenant_id: UUID) -> SimpleNamespace | None:
        if project_id != self.project_id or tenant_id != self.owner_tenant:
            return None
        return SimpleNamespace(
            id=project_id,
            name="Journey Pilot Plant",
            code="JPP-01",
            status=ProjectStatus.ACTIVE,
        )


class _MockJourneySources:
    def __init__(self) -> None:
        self.requested_projects: list[tuple[UUID, UUID]] = []

    async def load_journey_data(self, project_id: UUID, tenant_id: UUID) -> JourneyExportData:
        self.requested_projects.append((project_id, tenant_id))
        return JourneyExportData(
            summary=JourneySummaryData(
                project_id=project_id,
                project_name="Journey Pilot Plant",
                project_code="JPP-01",
                status="ACTIVE",
                global_score=85.0,
                trusted_score=83.0,
                projected_score=79.0,
                score_reason="Pilot score validated",
                sub_scores={
                    "SCOPE": 90.0,
                    "BUDGET": 80.0,
                    "TIME": 85.0,
                    "TECHNICAL": 88.0,
                    "LEGAL": 82.0,
                    "QUALITY": 85.0,
                },
                coverage_status="COMPLETE",
                total_windows=5,
                examined_windows=5,
                gap_windows_count=0,
                generated_at=datetime.now(UTC),
            ),
            findings=[
                JourneyFindingRow(
                    finding_id="f-1",
                    title="Warranty Period Exceeds Industry Norm",
                    ai_interpretation="36 months warranty without relief events",
                    exact_quote="Contractor warrants defects for a period of 36 months following completion.",
                    page=12,
                    clause="Clause 11.2",
                    dimension="QUALITY",
                    severity="MEDIUM",
                    decision="CONFIRMED",
                    reviewer="QA Lead",
                    decided_at=datetime.now(UTC),
                )
            ],
            gaps=[],
            references=[],
        )


def _build_test_app(
    *,
    caller_tenant: UUID,
    owner_tenant: UUID,
    project_id: UUID,
    sources: _MockJourneySources,
) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def _user() -> SimpleNamespace:
        return SimpleNamespace(tenant_id=caller_tenant, id=uuid4())

    async def _projects() -> AsyncGenerator[_MockProjects, None]:
        yield _MockProjects(owner_tenant, project_id)

    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_project_repository] = _projects
    app.dependency_overrides[get_journey_export_sources] = lambda: sources
    return app


@pytest.mark.asyncio
async def test_get_journey_export_returns_200_and_valid_excel_for_owned_project() -> None:
    tenant_id, project_id = uuid4(), uuid4()
    sources = _MockJourneySources()
    app = _build_test_app(
        caller_tenant=tenant_id,
        owner_tenant=tenant_id,
        project_id=project_id,
        sources=sources,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/projects/{project_id}/reports/journey.xlsx")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in response.headers["Content-Type"]
    assert "journey" in response.headers.get("Content-Disposition", "")
    assert ".xlsx" in response.headers.get("Content-Disposition", "")

    # Verify openpyxl can read the bytes
    wb = openpyxl.load_workbook(io.BytesIO(response.content))
    assert wb.sheetnames == ["Summary", "Findings", "Gaps & References"]

    ws_findings = wb["Findings"]
    finding_texts = [str(c.value) for row in ws_findings.iter_rows() for c in row if c.value is not None]
    assert "Warranty Period Exceeds Industry Norm" in finding_texts
    assert "Clause 11.2" in finding_texts
    assert "QA Lead" in finding_texts


@pytest.mark.asyncio
async def test_get_journey_export_returns_404_for_foreign_tenant_project() -> None:
    caller_tenant, owner_tenant, project_id = uuid4(), uuid4(), uuid4()
    sources = _MockJourneySources()
    app = _build_test_app(
        caller_tenant=caller_tenant,
        owner_tenant=owner_tenant,
        project_id=project_id,
        sources=sources,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/projects/{project_id}/reports/journey.xlsx")

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"
    assert len(sources.requested_projects) == 0


@pytest.mark.asyncio
async def test_get_journey_export_returns_404_for_unknown_project() -> None:
    tenant_id, project_id, unknown_id = uuid4(), uuid4(), uuid4()
    sources = _MockJourneySources()
    app = _build_test_app(
        caller_tenant=tenant_id,
        owner_tenant=tenant_id,
        project_id=project_id,
        sources=sources,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/projects/{unknown_id}/reports/journey.xlsx")

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"
    assert len(sources.requested_projects) == 0



@pytest.mark.asyncio
async def test_get_journey_export_sources_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    from contextlib import asynccontextmanager

    from src.reporting.adapters.http import router as router_module
    from src.reporting.application.build_journey_export import SqlAlchemyJourneyExportSources

    tenant_id = uuid4()
    mock_session = object()

    @asynccontextmanager
    async def _mock_get_session(tid: UUID) -> AsyncGenerator[object, None]:
        assert tid == tenant_id
        yield mock_session

    monkeypatch.setattr(router_module, "get_session_with_tenant", _mock_get_session)

    user = SimpleNamespace(tenant_id=tenant_id, id=uuid4())
    gen = get_journey_export_sources(current_user=user)  # type: ignore[arg-type]
    sources_yielded = []
    async for s in gen:
        sources_yielded.append(s)

    assert len(sources_yielded) == 1
    assert isinstance(sources_yielded[0], SqlAlchemyJourneyExportSources)
