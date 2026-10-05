"""
Line B reviewer-integrity contracts for bounded bulk review.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from src.alerts.application.use_cases.bulk_review_alerts_use_case import (
    BulkReviewAlertsUseCase,
    BulkReviewPolicyError,
)
from src.alerts.domain.enums import AlertSeverity, AlertStatus, ApprovalStatus
from src.alerts.domain.models import Alert


def _alert(severity: AlertSeverity = AlertSeverity.MEDIUM) -> Alert:
    return Alert(
        id=uuid4(),
        project_id=uuid4(),
        severity=severity,
        category="LEGAL",
        status=AlertStatus.OPEN,
        approval_status=ApprovalStatus.PENDING,
        rule_id="LINE-B-REVIEW",
        title="Review integrity alert",
        description="Review integrity alert",
        affected_entities={},
        alert_metadata={},
        created_at=datetime.now(UTC),
    )


class _FakeRepository:
    def __init__(self, alerts: list[Alert]) -> None:
        self.alerts = {alert.id: alert for alert in alerts}
        self.saved: list[UUID] = []
        self.commit_count = 0

    async def get_by_id(self, alert_id: UUID, tenant_id: UUID) -> Alert | None:
        return self.alerts.get(alert_id)

    async def save(self, alert: Alert, tenant_id: UUID | None = None) -> None:
        self.saved.append(alert.id)

    async def commit(self) -> None:
        self.commit_count += 1


@pytest.mark.asyncio
async def test_bulk_approve_is_bounded_and_commits_once() -> None:
    alerts = [_alert() for _ in range(5)]
    repository = _FakeRepository(alerts)
    use_case = BulkReviewAlertsUseCase(repository=repository)

    response = await use_case.execute(
        alert_ids=[str(alert.id) for alert in alerts],
        tenant_id=uuid4(),
        user_id=uuid4(),
        decision="approve",
        comment="Reviewed as one bounded medium-risk batch",
    )

    assert response.processed_count == 5
    assert repository.commit_count == 1
    assert set(repository.saved) == {alert.id for alert in alerts}
    assert all(alert.status is AlertStatus.ACKNOWLEDGED for alert in alerts)
    assert all(alert.approval_status is ApprovalStatus.APPROVED for alert in alerts)


@pytest.mark.asyncio
async def test_oversized_bulk_approval_fails_before_any_mutation() -> None:
    alerts = [_alert() for _ in range(6)]
    repository = _FakeRepository(alerts)
    use_case = BulkReviewAlertsUseCase(repository=repository)

    with pytest.raises(BulkReviewPolicyError, match="maximum"):
        await use_case.execute(
            alert_ids=[str(alert.id) for alert in alerts],
            tenant_id=uuid4(),
            user_id=uuid4(),
            decision="approve",
            comment="Oversized batch",
        )

    assert repository.saved == []
    assert repository.commit_count == 0
    assert all(alert.status is AlertStatus.OPEN for alert in alerts)


@pytest.mark.asyncio
@pytest.mark.parametrize("severity", [AlertSeverity.HIGH, AlertSeverity.CRITICAL])
async def test_high_risk_bulk_approval_requires_individual_review(
    severity: AlertSeverity,
) -> None:
    alert = _alert(severity)
    repository = _FakeRepository([alert])
    use_case = BulkReviewAlertsUseCase(repository=repository)

    with pytest.raises(BulkReviewPolicyError, match="individual review"):
        await use_case.execute(
            alert_ids=[str(alert.id)],
            tenant_id=uuid4(),
            user_id=uuid4(),
            decision="approve",
            comment="Attempted bulk approval",
        )

    assert repository.saved == []
    assert repository.commit_count == 0
    assert alert.status is AlertStatus.OPEN


@pytest.mark.asyncio
async def test_bulk_rejection_requires_non_empty_audit_reason() -> None:
    alert = _alert()
    repository = _FakeRepository([alert])
    use_case = BulkReviewAlertsUseCase(repository=repository)

    with pytest.raises(BulkReviewPolicyError, match="reason"):
        await use_case.execute(
            alert_ids=[str(alert.id)],
            tenant_id=uuid4(),
            user_id=uuid4(),
            decision="reject",
            comment="   ",
        )

    assert repository.saved == []
    assert repository.commit_count == 0
    assert alert.status is AlertStatus.OPEN
