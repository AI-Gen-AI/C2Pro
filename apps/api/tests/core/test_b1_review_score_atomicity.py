"""B1-11/B1-13 review -> Coherence recalculation transaction contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from src.alerts.application.use_cases.bulk_review_alerts_use_case import (
    BulkReviewAlertsUseCase,
    BulkReviewPolicyError,
)
from src.alerts.application.use_cases.review_alert_use_case import ReviewAlertUseCase
from src.alerts.domain.enums import AlertSeverity, AlertStatus, ApprovalStatus
from src.alerts.domain.models import Alert


def _alert(*, alert_type: str = "coherence") -> Alert:
    return Alert(
        id=uuid4(),
        project_id=uuid4(),
        severity=AlertSeverity.MEDIUM,
        category="TIME",
        status=AlertStatus.OPEN,
        approval_status=ApprovalStatus.PENDING,
        rule_id="DET-TIM-B1-REVIEW",
        title="Timing conflict",
        description="Timing conflict",
        alert_type=alert_type,
        affected_entities={},
        alert_metadata={
            "source": "coherence_evaluate",
            "current_observation_key": "basis-current",
        },
        created_at=datetime.now(UTC),
    )


class _Repo:
    def __init__(self, alerts: list[Alert], events: list[str] | None = None) -> None:
        self.alerts = {alert.id: alert for alert in alerts}
        self.events = events if events is not None else []
        self.commit_count = 0

    async def get_by_id(self, alert_id: UUID, tenant_id: UUID) -> Alert | None:  # noqa: ARG002
        return self.alerts.get(alert_id)

    async def save(self, alert: Alert, tenant_id: UUID | None = None) -> None:  # noqa: ARG002
        self.events.append("save")

    async def commit(self) -> None:
        self.events.append("commit")
        self.commit_count += 1


@pytest.mark.asyncio
async def test_individual_review_runs_score_handler_after_flush_before_commit() -> None:
    events: list[str] = []
    alert = _alert()
    repo = _Repo([alert], events)

    async def score_handler(
        reviewed: Alert,
        tenant_id: UUID,  # noqa: ARG001
        decision: str,
    ) -> None:
        assert decision == "reject"
        assert reviewed.status is AlertStatus.DISMISSED
        assert reviewed.alert_metadata["disposition"] == "false_positive"
        events.append("score_handler")

    use_case = ReviewAlertUseCase(
        repository=repo,
        post_review_handler=score_handler,
    )
    await use_case.execute(
        alert_id=alert.id,
        tenant_id=uuid4(),
        user_id=uuid4(),
        decision="reject",
        comment="Validated detector false positive",
    )

    assert events == ["save", "score_handler", "commit"]
    assert repo.commit_count == 1


@pytest.mark.asyncio
async def test_score_recalculation_failure_prevents_review_commit() -> None:
    events: list[str] = []
    alert = _alert()
    repo = _Repo([alert], events)

    async def failing_handler(
        reviewed: Alert,  # noqa: ARG001
        tenant_id: UUID,  # noqa: ARG001
        decision: str,  # noqa: ARG001
    ) -> None:
        events.append("score_handler")
        raise RuntimeError("canonical rescore failed")

    use_case = ReviewAlertUseCase(
        repository=repo,
        post_review_handler=failing_handler,
    )

    with pytest.raises(RuntimeError, match="canonical rescore failed"):
        await use_case.execute(
            alert_id=alert.id,
            tenant_id=uuid4(),
            user_id=uuid4(),
            decision="reject",
            comment="Validated detector false positive",
        )

    assert events == ["save", "score_handler"]
    assert repo.commit_count == 0


@pytest.mark.asyncio
async def test_bulk_reject_coherence_alert_requires_individual_atomic_review() -> None:
    alert = _alert(alert_type="coherence")
    repo = _Repo([alert])
    use_case = BulkReviewAlertsUseCase(repository=repo)

    with pytest.raises(BulkReviewPolicyError, match="individual review"):
        await use_case.execute(
            alert_ids=[str(alert.id)],
            tenant_id=uuid4(),
            user_id=uuid4(),
            decision="reject",
            comment="Would change Coherence scoring eligibility",
        )

    assert repo.commit_count == 0
    assert alert.status is AlertStatus.OPEN


@pytest.mark.asyncio
async def test_bulk_reject_non_coherence_alert_keeps_existing_policy() -> None:
    alert = _alert(alert_type="risk")
    repo = _Repo([alert])
    use_case = BulkReviewAlertsUseCase(repository=repo)

    response = await use_case.execute(
        alert_ids=[str(alert.id)],
        tenant_id=uuid4(),
        user_id=uuid4(),
        decision="reject",
        comment="Reviewed risk false positive",
    )

    assert response.processed_count == 1
    assert repo.commit_count == 1
    assert alert.status is AlertStatus.DISMISSED
