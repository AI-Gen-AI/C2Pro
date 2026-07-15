"""
TS-E2E-FLW-JRN-001

Repository regressions for alert persistence timestamp handling.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from alerts.adapters.persistence.alert_repository import SqlAlchemyAlertRepository
from alerts.domain.enums import AlertSeverity, AlertStatus, ApprovalStatus
from alerts.domain.models import Alert


@pytest.mark.asyncio
async def test_save_normalizes_aware_review_timestamps_to_naive_utc() -> None:
    """Aware UTC timestamps should be normalized for naive TIMESTAMP columns."""
    session = AsyncMock()
    orm_alert = SimpleNamespace(
        id=uuid4(),
        project_id=uuid4(),
        status="open",
        reviewed_by=None,
        reviewed_at=None,
        resolved_at=None,
        resolved_by=None,
        alert_metadata={},
        updated_at=None,
    )
    session.get.return_value = orm_alert

    repo = SqlAlchemyAlertRepository(session=session)
    aware_now = datetime.now(UTC)
    alert = Alert(
        id=orm_alert.id,
        project_id=orm_alert.project_id,
        severity=AlertSeverity.HIGH,
        category="TIME",
        status=AlertStatus.ACKNOWLEDGED,
        approval_status=ApprovalStatus.PENDING,
        rule_id="R-JRN-001",
        title="Schedule mismatch",
        description="Review timestamp normalization regression",
        reviewed_by=uuid4(),
        reviewed_at=aware_now,
        updated_at=aware_now,
        alert_metadata={"history": []},
    )

    await repo.save(alert)

    assert orm_alert.reviewed_at.tzinfo is None
    assert orm_alert.reviewed_at == aware_now.astimezone(UTC).replace(tzinfo=None)
    assert orm_alert.updated_at.tzinfo is None
