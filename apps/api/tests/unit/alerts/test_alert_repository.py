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


@pytest.mark.asyncio
async def test_b1_human_disposition_fields_are_all_written_by_repository_save() -> None:
    """B1-03/B1-11: fresh persistence must not depend on the domain object in memory."""
    session = AsyncMock()
    orm_alert = SimpleNamespace(
        id=uuid4(),
        project_id=uuid4(),
        status=AlertStatus.OPEN.value,
        approval_status=ApprovalStatus.PENDING.value,
        reviewed_by=None,
        reviewed_at=None,
        review_comment=None,
        resolved_at=None,
        resolved_by=None,
        resolution_notes=None,
        alert_metadata={},
        updated_at=None,
    )
    session.get.return_value = orm_alert

    repo = SqlAlchemyAlertRepository(session=session)
    alert = Alert(
        id=orm_alert.id,
        project_id=orm_alert.project_id,
        severity=AlertSeverity.HIGH,
        category="TIME",
        status=AlertStatus.RESOLVED,
        approval_status=ApprovalStatus.APPROVED,
        rule_id="DET-TIM-GAP",
        title="Schedule mismatch",
        description="Confirmed schedule mismatch",
        reviewed_by=uuid4(),
        reviewed_at=datetime.now(UTC),
        review_comment="Confirmed against the trusted schedule.",
        resolved_at=datetime.now(UTC),
        resolved_by=uuid4(),
        resolution_notes="Corrective change approved and recorded.",
        alert_metadata={"history": [{"action": "reviewed"}]},
    )

    await repo.save(alert)

    persisted_approval_name = getattr(
        orm_alert.approval_status,
        "name",
        str(orm_alert.approval_status).upper(),
    )
    assert persisted_approval_name == ApprovalStatus.APPROVED.name
    assert orm_alert.review_comment == "Confirmed against the trusted schedule."
    assert orm_alert.resolution_notes == "Corrective change approved and recorded."

def test_b1_repository_roundtrip_exposes_coherence_alert_type_to_domain() -> None:
    """Score-affecting policy must see the durable ORM alert type, not a default."""
    repo = SqlAlchemyAlertRepository(session=AsyncMock())
    orm_alert = SimpleNamespace(
        id=uuid4(),
        project_id=uuid4(),
        severity=AlertSeverity.HIGH.value,
        category="TIME",
        status=AlertStatus.OPEN.value,
        approval_status=ApprovalStatus.PENDING.value,
        alert_type="coherence",
        rule_id="DET-TIM-COHERENCE",
        title="Timing conflict",
        description="Timing conflict",
        affected_entities={},
        alert_metadata={"source": "coherence_evaluate"},
        created_at=datetime.now(UTC),
        updated_at=None,
        reviewed_by=None,
        reviewed_at=None,
        review_comment=None,
        resolved_at=None,
        resolved_by=None,
        resolution_notes=None,
        source_clause_id=None,
    )

    alert = repo._to_domain(orm_alert)

    assert alert.alert_type == "coherence"

