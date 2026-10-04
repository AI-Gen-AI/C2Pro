from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.analysis.adapters.persistence.alert_repository import SqlAlchemyAlertRepository
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
