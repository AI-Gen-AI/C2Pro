"""
TS-E2E-SEC-TNT-001 / TS-UA-STK-UC-001 / TASK-BCK-095

Repository-level tenant isolation hardening tests.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.analysis.adapters.persistence.alert_repository import SqlAlchemyAlertRepository
from src.analysis.adapters.persistence.analysis_repository import SqlAlchemyAnalysisRepository
from src.core.approval import ApprovalStatus
from src.stakeholders.adapters.persistence.sqlalchemy_stakeholder_repository import (
    SqlAlchemyStakeholderRepository,
)
from src.stakeholders.domain.models import InterestLevel, PowerLevel, Stakeholder


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


def _assert_stakeholder_identity_is_tenant_scoped(stmt: Any, stakeholder: Stakeholder) -> None:
    statement = str(stmt)
    params = stmt.compile().params
    assert "stakeholders.id" in statement
    assert "stakeholders.tenant_id" in statement
    assert stakeholder.id in params.values()
    assert stakeholder.tenant_id in params.values()


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
