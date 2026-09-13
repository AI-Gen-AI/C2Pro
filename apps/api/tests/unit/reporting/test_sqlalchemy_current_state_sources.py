"""TS-P0D-REPORT-004 - SQLAlchemy Current State Report sources.

Each domain is read through its existing repository or use case, in its own
tenant-scoped session, so a failed query in one domain cannot poison the
transaction used by another.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.modules.hitl.domain.entities import ReviewStatus
from src.reporting.adapters.sources import sqlalchemy_current_state_sources as module
from src.reporting.adapters.sources.sqlalchemy_current_state_sources import (
    AWAITING_DECISION_STATUSES,
    COHERENCE_DISABLED_REASON,
    SqlAlchemyCurrentStateSources,
)
from src.reporting.application.ports import SourceUnavailableError

PROJECT_ID = uuid4()
TENANT_ID = uuid4()


class _SessionLog:
    def __init__(self) -> None:
        self.opened: list[tuple[UUID, object]] = []

    def scope(self):  # noqa: ANN201
        log = self

        @asynccontextmanager
        async def _scope(tenant_id: UUID):  # noqa: ANN202
            session = object()
            log.opened.append((tenant_id, session))
            yield session

        return _scope


def _sources(log: _SessionLog, *, coherence_enabled: bool = True) -> SqlAlchemyCurrentStateSources:
    return SqlAlchemyCurrentStateSources(
        current_user=SimpleNamespace(tenant_id=TENANT_ID, id=uuid4()),
        session_scope=log.scope(),
        settings_provider=lambda: SimpleNamespace(feature_coherence_analysis=coherence_enabled),
    )


async def test_each_loader_uses_its_own_tenant_session(monkeypatch: pytest.MonkeyPatch) -> None:
    used: list[object] = []

    class _Snapshots:
        def __init__(self, session: object) -> None:
            used.append(session)

        async def latest(self, project_id: UUID, tenant_id: UUID) -> None:
            return None

    class _Alerts:
        def __init__(self, session: object, tenant_id: UUID | None = None) -> None:
            used.append(session)
            assert tenant_id == TENANT_ID

        async def list_for_project(self, project_id: UUID, tenant_id: UUID) -> list[Any]:
            return []

    monkeypatch.setattr(module, "SqlAlchemyProjectSnapshotRepository", _Snapshots)
    monkeypatch.setattr(module, "SqlAlchemyAlertRepository", _Alerts)

    log = _SessionLog()
    sources = _sources(log)
    await sources.load_health(PROJECT_ID, TENANT_ID)
    await sources.load_alerts(PROJECT_ID, TENANT_ID)

    assert [tenant for tenant, _ in log.opened] == [TENANT_ID, TENANT_ID]
    assert used[0] is log.opened[0][1]
    assert used[1] is log.opened[1][1]
    assert used[0] is not used[1]


async def test_coherence_disabled_is_unavailable_not_error() -> None:
    log = _SessionLog()
    with pytest.raises(SourceUnavailableError) as excinfo:
        await _sources(log, coherence_enabled=False).load_coherence(PROJECT_ID, TENANT_ID)
    assert excinfo.value.reason == COHERENCE_DISABLED_REASON
    assert log.opened == [], "no session is opened for a disabled feature"


async def test_coherence_enabled_reuses_the_dashboard_read(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[UUID, object, object]] = []
    summary = object()

    async def _dashboard(project_id: UUID, current_user: object, session: object) -> object:
        calls.append((project_id, current_user, session))
        return summary

    monkeypatch.setattr(module, "_read_coherence_dashboard", _dashboard)
    log = _SessionLog()
    sources = _sources(log)
    assert await sources.load_coherence(PROJECT_ID, TENANT_ID) is summary
    assert calls[0][0] == PROJECT_ID
    assert calls[0][2] is log.opened[0][1]


async def test_hitl_counts_every_awaiting_decision_status(monkeypatch: pytest.MonkeyPatch) -> None:
    counts = {
        ReviewStatus.PENDING_REVIEW_REQUIRED: 2,
        ReviewStatus.PENDING_REVIEW_CONDITIONAL: 1,
        ReviewStatus.ESCALATED: 3,
    }
    queried: list[tuple[ReviewStatus, UUID | None]] = []

    class _Queue:
        def __init__(self, session: object, tenant_id: UUID | None = None) -> None:
            assert tenant_id == TENANT_ID

        async def count_by_status(self, status: ReviewStatus, *, project_id: UUID | None = None) -> int:
            queried.append((status, project_id))
            return counts[status]

        async def list_by_status(
            self, status: ReviewStatus, *, skip: int = 0, limit: int = 50, project_id: UUID | None = None
        ) -> list[str]:
            return [f"{status.value}-{index}" for index in range(counts[status])]

    monkeypatch.setattr(module, "SqlAlchemyReviewQueueRepository", _Queue)
    result = await _sources(_SessionLog()).load_hitl(PROJECT_ID, TENANT_ID)

    assert set(AWAITING_DECISION_STATUSES) == set(counts)
    assert result.pending_count == 6
    assert len(result.items) == 6
    assert {status for status, _ in queried} == set(counts)
    assert all(project == PROJECT_ID for _, project in queried)


async def test_documents_are_read_once_with_a_bounded_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    # The document repository pages with OFFSET/LIMIT and no ORDER BY, so paging
    # could repeat or skip rows. One bounded read keeps the counts honest; the
    # projection marks counts partial when total exceeds what was read.
    requested: list[tuple[UUID, UUID, int, int]] = []

    class _Documents:
        def __init__(self, session: object) -> None:
            pass

        async def list_for_project(self, tenant_id: UUID, project_id: UUID, skip: int, limit: int):  # noqa: ANN201
            requested.append((tenant_id, project_id, skip, limit))
            return ["d1", "d2"], 1500

    monkeypatch.setattr(module, "SqlAlchemyDocumentRepository", _Documents)
    result = await _sources(_SessionLog()).load_documents(PROJECT_ID, TENANT_ID)

    assert requested == [(TENANT_ID, PROJECT_ID, 0, module.MAX_DOCUMENTS)]
    assert result.documents == ["d1", "d2"]
    assert result.total == 1500


async def test_stakeholders_keep_the_repository_total(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[UUID, UUID, int]] = []

    class _UseCase:
        def __init__(self, repository: object) -> None:
            pass

        async def execute(self, project_id: UUID, tenant_id: UUID, skip: int = 0, limit: int = 100):  # noqa: ANN201
            seen.append((project_id, tenant_id, limit))
            return ["s1", "s2"], 800

    monkeypatch.setattr(module, "SqlAlchemyStakeholderRepository", lambda session: object())
    monkeypatch.setattr(module, "ListProjectStakeholdersUseCase", _UseCase)
    result = await _sources(_SessionLog()).load_stakeholders(PROJECT_ID, TENANT_ID)

    assert seen == [(PROJECT_ID, TENANT_ID, module.MAX_STAKEHOLDERS)]
    assert result.stakeholders == ["s1", "s2"]
    assert result.total == 800


async def test_budget_is_read_through_the_budget_use_case(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[UUID, UUID]] = []
    budget = object()

    class _UseCase:
        def __init__(self, repository: object) -> None:
            pass

        async def execute(self, project_id: UUID, tenant_id: UUID) -> object:
            seen.append((project_id, tenant_id))
            return budget

    monkeypatch.setattr(module, "SQLAlchemyBudgetRepository", lambda session: object())
    monkeypatch.setattr(module, "GetBudgetUseCase", _UseCase)
    assert await _sources(_SessionLog()).load_budget(PROJECT_ID, TENANT_ID) is budget
    assert seen == [(PROJECT_ID, TENANT_ID)]


async def test_wbs_is_read_from_the_persisted_procurement_items_served_to_the_wbs_tab(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # At runtime GET /projects/{id}/wbs is the projects router's handler (it shadows the in-memory wbs
    # router) and reads procurement_wbs_items via SQLAlchemyWBSRepository, as RACI does; not wbs_nodes.
    seen: list[tuple[UUID, UUID]] = []

    class _Repository:
        def __init__(self, session: object) -> None:
            pass

        async def get_by_project(self, project_id: UUID, tenant_id: UUID) -> list[str]:
            seen.append((project_id, tenant_id))
            return ["i1"]

    monkeypatch.setattr(module, "SQLAlchemyWBSRepository", _Repository)
    assert await _sources(_SessionLog()).load_wbs(PROJECT_ID, TENANT_ID) == ["i1"]
    assert seen == [(PROJECT_ID, TENANT_ID)]
    assert not hasattr(module, "WBSNodeRepository")


async def test_raci_matrix_is_read_through_the_raci_use_case(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[UUID, UUID]] = []
    matrix = object()

    class _UseCase:
        def __init__(self, *, stakeholder_repository: object, wbs_repository: object, project_repository: object) -> None:
            pass

        async def execute(self, project_id: UUID, tenant_id: UUID) -> object:
            seen.append((project_id, tenant_id))
            return matrix

    monkeypatch.setattr(module, "SqlAlchemyStakeholderRepository", lambda session: object())
    monkeypatch.setattr(module, "SQLAlchemyWBSRepository", lambda session: object())
    monkeypatch.setattr(module, "SQLAlchemyProjectRepository", lambda session: object())
    monkeypatch.setattr(module, "GetRaciMatrixUseCase", _UseCase)
    assert await _sources(_SessionLog()).load_raci(PROJECT_ID, TENANT_ID) is matrix
    assert seen == [(PROJECT_ID, TENANT_ID)]
