"""
TS-E2E-SEC-TNT-001

Repository-level tenant isolation hardening tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.analysis.adapters.persistence.alert_repository import SqlAlchemyAlertRepository
from src.analysis.adapters.persistence.analysis_repository import SqlAlchemyAnalysisRepository
from src.stakeholders.adapters.persistence.sqlalchemy_stakeholder_repository import (
    SqlAlchemyStakeholderRepository,
)


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
    assert "projects.tenant_id" in str(stmt)


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
    assert "projects.tenant_id" in str(first_stmt)
