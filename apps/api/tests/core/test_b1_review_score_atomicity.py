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
from src.coherence.application.disposition_review import (
    CoherenceReviewRescoreUnavailable,
    rescore_coherence_after_review,
)


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



@pytest.mark.asyncio
async def test_review_pre_handler_runs_before_alert_load_and_mutation() -> None:
    events: list[str] = []
    alert = _alert()

    class OrderedRepo(_Repo):
        async def get_by_id(self, alert_id: UUID, tenant_id: UUID) -> Alert | None:
            events.append("get")
            return await super().get_by_id(alert_id, tenant_id)

    repo = OrderedRepo([alert], events)

    async def pre_handler(
        alert_id: UUID,  # noqa: ARG001
        tenant_id: UUID,  # noqa: ARG001
        decision: str,
    ) -> None:
        assert decision == "reject"
        events.append("lock")

    async def post_handler(
        reviewed: Alert,  # noqa: ARG001
        tenant_id: UUID,  # noqa: ARG001
        decision: str,  # noqa: ARG001
    ) -> None:
        events.append("rescore")

    use_case = ReviewAlertUseCase(
        repository=repo,
        pre_review_handler=pre_handler,
        post_review_handler=post_handler,
    )
    await use_case.execute(
        alert_id=alert.id,
        tenant_id=uuid4(),
        user_id=uuid4(),
        decision="reject",
        comment="Validated false positive",
    )

    assert events == ["lock", "get", "save", "rescore", "commit"]


@pytest.mark.asyncio
async def test_exact_review_rescore_fails_closed_without_scoring_snapshot() -> None:
    basis = "basis-current"
    finding_key = "family-1"
    alert = _alert()
    alert.alert_metadata.update(
        {
            "finding_key": finding_key,
            "current_observation_key": basis,
            "disposition_basis_key": basis,
            "disposition": "false_positive",
        }
    )
    alert.status = AlertStatus.DISMISSED

    latest = type(
        "Latest",
        (),
        {
            "id": uuid4(),
            "score_version": "coherence-v1",
            "scoring_snapshot": None,
        },
    )()

    class Session:
        async def scalar(self, statement):  # noqa: ANN001, ARG002
            return latest

    with pytest.raises(
        CoherenceReviewRescoreUnavailable,
        match="SCORING_SNAPSHOT_REQUIRED",
    ):
        await rescore_coherence_after_review(
            session=Session(),  # type: ignore[arg-type]
            alert=alert,
            tenant_id=uuid4(),
            decision="reject",
        )


@pytest.mark.asyncio
async def test_exact_review_rescore_replays_full_signal_inputs_and_appends_result() -> None:
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    basis = "basis-current"
    finding_key = "family-1"
    project_id = uuid4()
    tenant_id = uuid4()
    alert = _alert()
    alert.project_id = project_id
    alert.alert_metadata.update(
        {
            "finding_key": finding_key,
            "current_observation_key": basis,
            "disposition_basis_key": basis,
            "disposition": "false_positive",
        }
    )
    alert.status = AlertStatus.DISMISSED

    signal_payload = {
        "rule_id": "DET-TIM-B1-REVIEW",
        "clause_id": str(uuid4()),
        "source": "deterministic",
        "impact_score": 0.95,
        "confidence": 1.0,
        "severity": "critical",
        "category": "TIME",
        "evidence_summary": "False positive timing conflict",
        "quote": "Exact evidence",
        "raw_data": {},
    }
    snapshot = {
        "schema_version": 1,
        "score_version": "coherence-v1",
        "num_clauses": 1,
        "poor_extraction_quality": False,
        "coverage_map": {
            "SCOPE": True,
            "BUDGET": True,
            "QUALITY": True,
            "TECHNICAL": True,
            "LEGAL": True,
            "TIME": True,
        },
        "budget_throttled_categories": [],
        "findings": [
            {
                "finding_key": finding_key,
                "observation_key": basis,
                "signal": signal_payload,
                "alert": {
                    "rule_id": "DET-TIM-B1-REVIEW",
                    "severity": "critical",
                    "category": "schedule",
                    "message": "False positive timing conflict",
                    "evidence": {
                        "source_clause_id": signal_payload["clause_id"],
                        "claim": "False positive timing conflict",
                        "quote": "Exact evidence",
                    },
                },
            }
        ],
    }
    latest = SimpleNamespace(
        id=uuid4(),
        score_version="coherence-v1",
        scoring_snapshot=snapshot,
        is_gaming_detected=False,
        gaming_violations=[],
        penalty_points=0,
    )
    persisted_alert = SimpleNamespace(
        status=SimpleNamespace(value="dismissed"),
        alert_metadata=dict(alert.alert_metadata),
    )

    session = Mock()
    session.scalar = AsyncMock(return_value=latest)
    session.scalars = AsyncMock(
        return_value=SimpleNamespace(all=lambda: [persisted_alert])
    )
    session.flush = AsyncMock()
    session.add = Mock()

    await rescore_coherence_after_review(
        session=session,
        alert=alert,
        tenant_id=tenant_id,
        decision="reject",
    )

    session.add.assert_called_once()
    new_result = session.add.call_args.args[0]
    assert new_result.project_id == project_id
    assert new_result.tenant_id == tenant_id
    assert new_result.score_version == "coherence-v1"
    assert new_result.alerts == []
    assert new_result.scoring_snapshot["last_rescore"]["reviewed_finding_key"] == finding_key
    session.flush.assert_awaited_once()
