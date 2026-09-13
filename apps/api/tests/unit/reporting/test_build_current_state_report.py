"""TS-P0D-REPORT-002 - Current State Report use case orchestration.

Each authoritative source is read independently. One failing source must not
fail the report, and internal exception text must never reach the payload.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.procurement.application.budget_use_cases import BudgetResponse
from src.reporting.application.build_current_state_report import BuildCurrentStateReportUseCase
from src.reporting.application.ports import (
    DocumentsInput,
    HitlInput,
    SourceUnavailableError,
    StakeholdersInput,
)
from src.reporting.domain.current_state_report import ProjectIdentity, SectionStatus
from src.stakeholders.application.dtos import RaciMatrixViewResponse

NOW = datetime(2026, 9, 13, 9, 30, tzinfo=UTC)
PROJECT_ID = uuid4()
TENANT_ID = uuid4()
PROJECT = ProjectIdentity(id=PROJECT_ID, name="Hospital North", code=None, status="active")


class _Sources:
    def __init__(self, *, fail: str | None = None, unavailable: dict[str, str] | None = None) -> None:
        self.fail = fail
        self.unavailable = unavailable or {}
        self.calls: list[tuple[str, UUID, UUID]] = []

    async def _guard(self, name: str, project_id: UUID, tenant_id: UUID) -> None:
        self.calls.append((name, project_id, tenant_id))
        if name == self.fail:
            raise RuntimeError("boom: psycopg connection string postgres://secret@db")
        if name in self.unavailable:
            raise SourceUnavailableError(self.unavailable[name])

    async def load_documents(self, project_id: UUID, tenant_id: UUID) -> DocumentsInput:
        await self._guard("documents", project_id, tenant_id)
        return DocumentsInput(documents=[], total=0)

    async def load_health(self, project_id: UUID, tenant_id: UUID):  # noqa: ANN201
        await self._guard("health", project_id, tenant_id)
        return None

    async def load_coherence(self, project_id: UUID, tenant_id: UUID):  # noqa: ANN201
        await self._guard("coherence", project_id, tenant_id)
        return None

    async def load_alerts(self, project_id: UUID, tenant_id: UUID):  # noqa: ANN201
        await self._guard("alerts", project_id, tenant_id)
        return []

    async def load_hitl(self, project_id: UUID, tenant_id: UUID) -> HitlInput:
        await self._guard("hitl", project_id, tenant_id)
        return HitlInput(items=[], pending_count=0)

    async def load_budget(self, project_id: UUID, tenant_id: UUID) -> BudgetResponse:
        await self._guard("budget", project_id, tenant_id)
        return BudgetResponse(project_id=project_id, items=[])

    async def load_wbs(self, project_id: UUID, tenant_id: UUID):  # noqa: ANN201
        await self._guard("wbs", project_id, tenant_id)
        return []

    async def load_stakeholders(self, project_id: UUID, tenant_id: UUID) -> StakeholdersInput:
        await self._guard("stakeholders", project_id, tenant_id)
        return StakeholdersInput(stakeholders=[], total=0)

    async def load_raci(self, project_id: UUID, tenant_id: UUID) -> RaciMatrixViewResponse:
        await self._guard("raci", project_id, tenant_id)
        return RaciMatrixViewResponse(matrix=[])


async def test_every_source_is_read_with_project_and_tenant() -> None:
    sources = _Sources()
    await BuildCurrentStateReportUseCase(sources, clock=lambda: NOW).execute(PROJECT, TENANT_ID)
    assert {name for name, _, _ in sources.calls} == {
        "documents",
        "health",
        "coherence",
        "alerts",
        "hitl",
        "budget",
        "wbs",
        "stakeholders",
        "raci",
    }
    assert all(project == PROJECT_ID and tenant == TENANT_ID for _, project, tenant in sources.calls)


async def test_generated_at_comes_from_clock() -> None:
    report = await BuildCurrentStateReportUseCase(_Sources(), clock=lambda: NOW).execute(PROJECT, TENANT_ID)
    assert report.generated_at == NOW
    assert report.project == PROJECT


async def test_one_failing_source_becomes_error_section_without_leaking_exception() -> None:
    report = await BuildCurrentStateReportUseCase(_Sources(fail="alerts"), clock=lambda: NOW).execute(
        PROJECT, TENANT_ID
    )
    alerts = report.sections.alerts
    assert alerts.status is SectionStatus.ERROR
    assert alerts.status_reason
    assert "boom" not in alerts.status_reason
    assert "postgres" not in alerts.status_reason
    assert report.sections.documents.status is SectionStatus.EMPTY
    assert "boom" not in report.model_dump_json()


async def test_source_unavailable_error_maps_to_unavailable_with_reason() -> None:
    reason = "Coherence analysis is not enabled for this environment."
    report = await BuildCurrentStateReportUseCase(
        _Sources(unavailable={"coherence": reason}), clock=lambda: NOW
    ).execute(PROJECT, TENANT_ID)
    assert report.sections.coherence.status is SectionStatus.UNAVAILABLE
    assert report.sections.coherence.status_reason == reason


async def test_empty_project_report_is_honest() -> None:
    report = await BuildCurrentStateReportUseCase(_Sources(), clock=lambda: NOW).execute(PROJECT, TENANT_ID)
    sections = report.sections
    assert sections.health.status is SectionStatus.UNAVAILABLE
    assert sections.budget.status is SectionStatus.EMPTY
    assert sections.alerts.status is SectionStatus.EMPTY
    assert sections.risks.status is SectionStatus.NOT_MODELED
    assert sections.executive_summary.data is not None
    assert sections.executive_summary.data.health_composite_score is None
