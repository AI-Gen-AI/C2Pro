"""B1 review transaction contracts for score-affecting Coherence dispositions."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from src.alerts.application.use_cases.review_alert_use_case import ReviewAlertUseCase
from src.alerts.domain.enums import AlertSeverity, AlertStatus, ApprovalStatus
from src.alerts.domain.models import Alert


class _Repo:
    def __init__(self, alert: Alert) -> None:
        self.alert = alert
        self.saved = 0
        self.commits = 0

    async def get_by_id(self, alert_id: UUID, tenant_id: UUID) -> Alert | None:
        return self.alert if alert_id == self.alert.id else None

    async def save(self, alert: Alert, tenant_id: UUID | None = None) -> None:
        self.alert = alert
        self.saved += 1

    async def commit(self) -> None:
        self.commits += 1


@pytest.mark.asyncio
async def test_b1_false_positive_review_can_be_flushed_without_committing() -> None:
    """Cross-context orchestration must be able to review + rescore atomically."""
    alert = Alert(
        id=uuid4(),
        project_id=uuid4(),
        severity=AlertSeverity.HIGH,
        category="TIME",
        status=AlertStatus.OPEN,
        approval_status=ApprovalStatus.PENDING,
        rule_id="DET-TIM-COD-MISMATCH",
        title="COD mismatch",
        description="Trusted evidence conflicts",
        alert_metadata={
            "current_observation_key": "obs-v1",
            "fingerprint": "family-1",
        },
        created_at=datetime.now(UTC),
    )
    alert.alert_type = "coherence"
    repo = _Repo(alert)
    use_case = ReviewAlertUseCase(repository=repo)

    response = await use_case.execute(
        alert_id=alert.id,
        tenant_id=uuid4(),
        user_id=uuid4(),
        decision="reject",
        comment="Validated false positive",
        commit=False,
    )

    assert response.status == AlertStatus.DISMISSED.value
    assert repo.saved == 1
    assert repo.commits == 0
    assert alert.alert_metadata["disposition"] == "false_positive"
    assert alert.alert_metadata["disposition_basis_key"] == "obs-v1"
