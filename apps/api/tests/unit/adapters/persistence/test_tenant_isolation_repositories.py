"""
TS-E2E-SEC-TNT-001 / TS-UA-STK-UC-001 / TASK-BCK-095

Repository-level tenant isolation hardening tests.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.analysis.adapters.persistence.alert_repository import SqlAlchemyAlertRepository
from src.analysis.adapters.persistence.analysis_repository import SqlAlchemyAnalysisRepository
from src.analysis.adapters.persistence.coherence_repository import (
    SqlAlchemyCoherenceRepository,
)
from src.core.approval import ApprovalStatus
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.documents.domain.models import Clause, Document, DocumentStatus, DocumentType
from src.stakeholders.adapters.persistence.sqlalchemy_stakeholder_repository import (
    SqlAlchemyStakeholderRepository,
)
from src.stakeholders.domain.models import (
    InterestLevel,
    PowerLevel,
    RaciAssignment,
    RACIRole,
    Stakeholder,
)


@pytest.mark.asyncio
async def test_coherence_repository_maps_wbs_payload_to_current_orm_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TS-UT-ANA-PER-001: Map legacy extraction keys to the current WBS ORM."""
    tenant_id = uuid4()
    project_id = uuid4()
    db = AsyncMock()
    tenant_db = MagicMock()
    tenant_db.scalar = AsyncMock(return_value=None)
    tenant_db.commit = AsyncMock()
    tenant_db.refresh = AsyncMock()

    @asynccontextmanager
    async def tenant_session(_tenant_id: object):
        yield tenant_db

    monkeypatch.setattr(
        "src.analysis.adapters.persistence.coherence_repository.get_session_with_tenant",
        tenant_session,
    )
    repository = SqlAlchemyCoherenceRepository(db, tenant_id=tenant_id)
    monkeypatch.setattr(
        repository,
        "_load_project",
        AsyncMock(return_value=SimpleNamespace(tenant_id=tenant_id)),
    )

    created_wbs, created_bom = await repository.persist_wbs_bom_items(
        project_id,
        [
            {
                "wbs_code": "1.2",
                "name": "Foundations",
                "level": 2,
                "funded_by_clause_id": None,
            }
        ],
        [],
        tenant_id=tenant_id,
    )

    assert created_bom == []
    assert len(created_wbs) == 1
    assert created_wbs[0].code == "1.2"
    assert created_wbs[0].source_clause_id is None


def _stakeholder() -> Stakeholder:
    now = datetime.now(UTC)
    return Stakeholder(
        id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        power_level=PowerLevel.HIGH,
        interest_level=InterestLevel.HIGH,
        approval_status=ApprovalStatus.APPROVED,
        created_at=now,
        updated_at=now,
        name="Tenant-scoped stakeholder",
    )


def _raci_assignment() -> RaciAssignment:
    """TS-E2E-SEC-TNT-001: Build a tenant-owned RACI assignment."""
    return RaciAssignment(
        id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        stakeholder_id=uuid4(),
        wbs_item_id=uuid4(),
        raci_role=RACIRole.RESPONSIBLE,
        created_at=datetime.now(UTC),
    )


def _assert_stakeholder_identity_is_tenant_scoped(stmt: Any, stakeholder: Stakeholder) -> None:
    statement = str(stmt)
    params = stmt.compile().params
    assert "stakeholders.id" in statement
    assert "stakeholders.tenant_id" in statement
    assert stakeholder.id in params.values()
    assert stakeholder.tenant_id in params.values()


def _document() -> Document:
    return Document(
        id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        document_type=DocumentType.CONTRACT,
        filename="tenant-scoped.pdf",
        upload_status=DocumentStatus.UPLOADED,
    )


def _clause() -> Clause:
    return Clause(
        id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        document_id=uuid4(),
        clause_code="1.1",
        clause_type=None,
        title=None,
        full_text="Tenant-scoped clause",
    )


def _assert_document_identity_is_tenant_scoped(stmt: Any, entity: Document | Clause) -> None:
    statement = str(stmt)
    params = stmt.compile().params
    assert ".id" in statement
    assert ".tenant_id" in statement
    assert entity.id in params.values()
    assert entity.tenant_id in params.values()


@pytest.mark.asyncio
async def test_alert_repository_get_stats_filters_by_tenant_id() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute.return_value = result
    repo = SqlAlchemyAlertRepository(session=session)

    await repo.get_stats(project_id=uuid4(), tenant_id=uuid4())

    stmt = session.execute.call_args.args[0]
    assert "projects.tenant_id" in str(stmt)


@pytest.mark.asyncio
async def test_alert_repository_get_by_id_filters_by_tenant_id() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result
    repo = SqlAlchemyAlertRepository(session=session)

    await repo.get_by_id(alert_id=uuid4(), tenant_id=uuid4())

    stmt = session.execute.call_args.args[0]
    assert "projects.tenant_id" in str(stmt)


@pytest.mark.asyncio
async def test_analysis_repository_list_recent_filters_by_tenant_id() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute.return_value = result
    repo = SqlAlchemyAnalysisRepository(session=session)

    await repo.list_recent(limit=10, offset=0, tenant_id=uuid4())

    stmt = session.execute.call_args.args[0]
    assert "projects.tenant_id" in str(stmt)


@pytest.mark.asyncio
async def test_analysis_repository_count_all_filters_by_tenant_id() -> None:
    session = AsyncMock()
    session.scalar.return_value = 0
    repo = SqlAlchemyAnalysisRepository(session=session)

    await repo.count_all(tenant_id=uuid4())

    stmt = session.scalar.call_args.args[0]
    assert "projects.tenant_id" in str(stmt)


def _analysis_write(*, tenant_id: Any, project_id: Any) -> Any:
    from src.analysis.domain.enums import AnalysisStatus, AnalysisType
    from src.analysis.ports.types import AnalysisWrite

    return AnalysisWrite(
        id=uuid4(),
        tenant_id=tenant_id,
        project_id=project_id,
        analysis_type=AnalysisType.RISK,
        status=AnalysisStatus.COMPLETED,
        result_json={},
        coherence_score=None,
        coherence_breakdown={},
        alerts_count=0,
        completed_at=datetime.now(UTC),
    )


def _alert_write(*, tenant_id: Any, project_id: Any) -> Any:
    from src.analysis.domain.enums import AlertSeverity, AlertType
    from src.analysis.ports.types import AlertWrite

    return AlertWrite(
        tenant_id=tenant_id,
        project_id=project_id,
        analysis_id=None,
        alert_type=AlertType.RISK,
        severity=AlertSeverity.LOW,
        title="t",
        message="m",
        description="d",
        category=None,
        impact_level=None,
        alert_metadata={},
        rule_id=None,
        source_clause_id=None,
        related_clause_ids=None,
        affected_entities={},
        recommendation=None,
    )


@pytest.mark.asyncio
async def test_add_analysis_rejects_project_outside_tenant() -> None:
    """TS-SEC-APP-TENANT-001 (invariant C): a caller-supplied tenant_id that

    does not own the analysis' project must never receive child persistence,
    even though the analysis DTO itself is well-formed.
    """
    caller_tenant = uuid4()
    other_tenant = uuid4()
    project_id = uuid4()

    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = other_tenant  # project belongs elsewhere
    session.execute.return_value = result

    repo = SqlAlchemyAnalysisRepository(session=session)
    analysis = _analysis_write(tenant_id=caller_tenant, project_id=project_id)

    with pytest.raises(PermissionError):
        await repo.add_analysis(analysis, tenant_id=caller_tenant)

    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_add_analysis_rejects_mismatched_dto_tenant_id() -> None:
    """TS-SEC-APP-TENANT-001 (invariant C): the analysis DTO's own tenant_id

    must match the caller-authenticated tenant_id, even if the project
    ownership lookup alone would have passed.
    """
    caller_tenant = uuid4()
    dto_tenant = uuid4()
    project_id = uuid4()

    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = caller_tenant
    session.execute.return_value = result

    repo = SqlAlchemyAnalysisRepository(session=session)
    analysis = _analysis_write(tenant_id=dto_tenant, project_id=project_id)

    with pytest.raises(PermissionError):
        await repo.add_analysis(analysis, tenant_id=caller_tenant)

    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_add_analysis_requires_tenant_id_argument() -> None:
    """TS-SEC-APP-TENANT-001 (invariant D): omitting tenant_id must fail

    closed at the call boundary (TypeError), not silently skip the
    ownership check the way the previous optional-default signature did.
    """
    session = AsyncMock()
    repo = SqlAlchemyAnalysisRepository(session=session)
    analysis = _analysis_write(tenant_id=uuid4(), project_id=uuid4())

    with pytest.raises(TypeError):
        await repo.add_analysis(analysis)  # type: ignore[call-arg]


@pytest.mark.asyncio
async def test_add_analysis_succeeds_for_matching_tenant(monkeypatch: pytest.MonkeyPatch) -> None:
    """TS-SEC-APP-TENANT-001 (invariant E): the correct tenant is unaffected."""
    tenant_id = uuid4()
    project_id = uuid4()

    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = tenant_id
    session.execute.return_value = result

    monkeypatch.setattr(
        "src.analysis.adapters.persistence.analysis_repository.Analysis",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )

    repo = SqlAlchemyAnalysisRepository(session=session)
    analysis = _analysis_write(tenant_id=tenant_id, project_id=project_id)

    await repo.add_analysis(analysis, tenant_id=tenant_id)

    session.add.assert_called_once()


@pytest.mark.asyncio
async def test_add_alerts_rejects_project_outside_tenant() -> None:
    """TS-SEC-APP-TENANT-001 (invariant C): same guarantee for alert persistence."""
    caller_tenant = uuid4()
    other_tenant = uuid4()
    project_id = uuid4()

    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = other_tenant
    session.execute.return_value = result

    repo = SqlAlchemyAnalysisRepository(session=session)
    alert = _alert_write(tenant_id=caller_tenant, project_id=project_id)

    with pytest.raises(PermissionError):
        await repo.add_alerts([alert], tenant_id=caller_tenant)

    session.add_all.assert_not_called()


@pytest.mark.asyncio
async def test_add_alerts_requires_tenant_id_argument() -> None:
    """TS-SEC-APP-TENANT-001 (invariant D): same fail-closed guarantee for alerts."""
    session = AsyncMock()
    repo = SqlAlchemyAnalysisRepository(session=session)
    alert = _alert_write(tenant_id=uuid4(), project_id=uuid4())

    with pytest.raises(TypeError):
        await repo.add_alerts([alert])  # type: ignore[call-arg]


@pytest.mark.asyncio
async def test_stakeholder_repository_get_by_id_filters_by_tenant_id() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result
    repo = SqlAlchemyStakeholderRepository(session=session)

    await repo.get_by_id(stakeholder_id=uuid4(), tenant_id=uuid4())

    stmt = session.execute.call_args.args[0]
    assert "stakeholders.tenant_id" in str(stmt)


@pytest.mark.asyncio
async def test_stakeholder_repository_list_by_project_filters_by_tenant_id() -> None:
    session = AsyncMock()
    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = []
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    session.execute.side_effect = [list_result, count_result]
    repo = SqlAlchemyStakeholderRepository(session=session)

    await repo.get_stakeholders_by_project(project_id=uuid4(), tenant_id=uuid4())

    first_stmt = session.execute.call_args_list[0].args[0]
    assert "stakeholders.tenant_id" in str(first_stmt)


@pytest.mark.asyncio
async def test_stakeholder_repository_update_selects_by_id_and_tenant_id() -> None:
    session = AsyncMock()
    session.get.return_value = None
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result
    repo = SqlAlchemyStakeholderRepository(session=session)
    stakeholder = _stakeholder()

    await repo.update(stakeholder, tenant_id=stakeholder.tenant_id)

    stmt = session.execute.await_args.args[0]
    _assert_stakeholder_identity_is_tenant_scoped(stmt, stakeholder)


@pytest.mark.asyncio
async def test_stakeholder_repository_refresh_selects_by_id_and_tenant_id() -> None:
    session = AsyncMock()
    session.get.return_value = None
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result
    repo = SqlAlchemyStakeholderRepository(session=session)
    stakeholder = _stakeholder()

    await repo.refresh(stakeholder)

    stmt = session.execute.await_args.args[0]
    _assert_stakeholder_identity_is_tenant_scoped(stmt, stakeholder)


@pytest.mark.asyncio
async def test_stakeholder_repository_raci_update_selects_by_id_and_tenant_id() -> None:
    """TS-E2E-SEC-TNT-001: RACI updates must not use an unscoped PK lookup."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result
    repo = SqlAlchemyStakeholderRepository(session=session)
    assignment = _raci_assignment()

    await repo.update_raci_assignment(assignment, tenant_id=assignment.tenant_id)

    stmt = session.execute.await_args.args[0]
    statement = str(stmt)
    assert "stakeholder_wbs_raci.id" in statement
    assert "stakeholder_wbs_raci.tenant_id" in statement
    session.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_stakeholder_repository_raci_refresh_selects_by_id_and_tenant_id() -> None:
    """TS-E2E-SEC-TNT-001: RACI refresh must not cross a tenant boundary."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result
    repo = SqlAlchemyStakeholderRepository(session=session)
    assignment = _raci_assignment()

    await repo.refresh(assignment)

    stmt = session.execute.await_args.args[0]
    statement = str(stmt)
    assert "stakeholder_wbs_raci.id" in statement
    assert "stakeholder_wbs_raci.tenant_id" in statement
    session.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_stakeholder_repository_delete_selects_by_id_and_tenant_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TS-E2E-SEC-TNT-001: Deletes must not re-read a tenant-owned row unscoped."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result
    repo = SqlAlchemyStakeholderRepository(session=session)
    stakeholder = _stakeholder()
    scoped_lookup = AsyncMock(return_value=stakeholder)
    monkeypatch.setattr(repo, "get_by_id", scoped_lookup)

    await repo.delete(stakeholder.id, stakeholder.tenant_id)

    stmt = session.execute.await_args.args[0]
    _assert_stakeholder_identity_is_tenant_scoped(stmt, stakeholder)
    scoped_lookup.assert_not_awaited()
    session.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_document_repository_refresh_selects_document_by_id_and_tenant_id() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result
    repo = SqlAlchemyDocumentRepository(session=session)
    document = _document()

    await repo.refresh(document)

    stmt = session.execute.await_args.args[0]
    _assert_document_identity_is_tenant_scoped(stmt, document)
    session.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_document_repository_refresh_selects_clause_by_id_and_tenant_id() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result
    repo = SqlAlchemyDocumentRepository(session=session)
    clause = _clause()

    await repo.refresh(clause)

    stmt = session.execute.await_args.args[0]
    _assert_document_identity_is_tenant_scoped(stmt, clause)
    session.get.assert_not_awaited()
