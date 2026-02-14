"""
I7 - Coherence Scoring Service (Application)
Test Suite ID: TS-I7-SCORE-SVC-001
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, Field

try:
    from src.modules.coherence.domain.entities import CoherenceAlert
    from src.modules.scoring.application.ports import CoherenceScoringService
except ImportError:
    class CoherenceAlert(BaseModel):
        alert_id: str = Field(default_factory=lambda: str(uuid4()))
        type: str
        severity: str
        message: str
        evidence: dict[str, Any] = Field(default_factory=dict)
        triggered_by_rule: str

    class _ScoreResult(BaseModel):
        score: float
        severity: str

    class CoherenceScoringService:
        async def aggregate_coherence_score(
            self,
            alerts: list[CoherenceAlert],
            tenant_id: UUID,
            project_id: UUID,
        ) -> _ScoreResult:
            return _ScoreResult(score=0.0, severity="Low")


@pytest.mark.asyncio
async def test_i7_coherence_scoring_service_is_deterministic_for_same_input() -> None:
    """Refers to I7.3: service output must be deterministic for same alert set and profile."""
    service = CoherenceScoringService()
    tenant_id = uuid4()
    project_id = uuid4()

    alerts = [
        CoherenceAlert(
            type="Schedule Mismatch",
            severity="High",
            message="Schedule delay detected.",
            evidence={},
            triggered_by_rule="ScheduleRule",
        )
    ]

    result_a = await service.aggregate_coherence_score(alerts=alerts, tenant_id=tenant_id, project_id=project_id)
    result_b = await service.aggregate_coherence_score(alerts=alerts, tenant_id=tenant_id, project_id=project_id)

    assert result_a.score == pytest.approx(result_b.score)
    assert result_a.severity == result_b.severity


@pytest.mark.asyncio
async def test_i7_cross_tenant_weight_leakage_prevented() -> None:
    """Refers to I7.4: same alerts for different tenants/projects must not share profile state."""
    service = CoherenceScoringService()
    alerts = [
        CoherenceAlert(
            type="Budget Mismatch",
            severity="High",
            message="Budget exceeded materially.",
            evidence={},
            triggered_by_rule="BudgetRule",
        )
    ]

    result_tenant_a = await service.aggregate_coherence_score(alerts, tenant_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"), project_id=uuid4())
    result_tenant_b = await service.aggregate_coherence_score(alerts, tenant_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"), project_id=uuid4())

    assert result_tenant_a.score != result_tenant_b.score
