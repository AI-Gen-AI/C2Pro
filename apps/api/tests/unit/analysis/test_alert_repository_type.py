from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.analysis.adapters.persistence.alert_repository import SqlAlchemyAlertRepository
from src.analysis.adapters.persistence.models import Alert as AlertORM
from src.analysis.application.dtos import AlertCreate
from src.analysis.domain.enums import AlertSeverity, AlertType


@pytest.mark.asyncio
async def test_create_persists_requested_alert_type() -> None:
    tenant_id = uuid4()
    project_id = uuid4()
    session = MagicMock()
    session.scalar = AsyncMock(
        return_value=SimpleNamespace(id=project_id, tenant_id=tenant_id)
    )
    session.flush = AsyncMock()
    session.add = MagicMock()

    payload = AlertCreate(
        project_id=project_id,
        analysis_id=None,
        severity=AlertSeverity.HIGH,
        alert_type=AlertType.COHERENCE,
        category="TIME",
        rule_id="DET-TIM-GAP",
        title="Schedule mismatch",
        description="Schedule mismatch",
        affected_entities={},
        alert_metadata={},
    )

    await SqlAlchemyAlertRepository(session).create(payload)

    persisted = session.add.call_args.args[0]
    assert persisted.alert_type == AlertType.COHERENCE


@pytest.mark.asyncio
async def test_list_for_project_executes_select_through_async_session() -> None:
    tenant_id = uuid4()
    project_id = uuid4()
    now = datetime.now(UTC).replace(tzinfo=None)
    persisted = AlertORM(
        tenant_id=tenant_id,
        project_id=project_id,
        analysis_id=None,
        severity=AlertSeverity.HIGH,
        alert_type=AlertType.COHERENCE,
        category="TIME",
        rule_id="DET-TIM-GAP",
        title="Schedule mismatch",
        message="Schedule mismatch",
        description="Schedule mismatch",
        affected_entities={},
        alert_metadata={},
        created_at=now,
    )
    scalar_result = MagicMock()
    scalar_result.all.return_value = [persisted]

    session = MagicMock()
    session.scalars = AsyncMock(return_value=scalar_result)

    page = await SqlAlchemyAlertRepository(session).list_for_project(
        project_id=project_id,
        tenant_id=tenant_id,
        alert_type=AlertType.COHERENCE,
        limit=20,
    )

    session.scalars.assert_awaited_once()
    assert page.items == [persisted]
    assert page.has_more is False
    assert page.next_cursor is None
