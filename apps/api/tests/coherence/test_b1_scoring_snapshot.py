"""B1 scoring-snapshot persistence contracts."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from src.coherence.adapters.persistence.models import CoherenceResultORM
from src.coherence.graph.nodes import _build_category_breakdown, _signal_to_alert
from src.coherence.models import Clause, EnrichedCoherenceResult, FindingSignal
from src.coherence.router import (
    CoherenceEvaluateRequest,
    _CoherenceAlertReconciliation,
    evaluate_project_coherence,
)
from src.coherence.scoring import ScoringService


@pytest.mark.asyncio
async def test_evaluate_persists_exact_scoring_snapshot_for_future_review_replay() -> None:
    project_id = uuid4()
    tenant_id = uuid4()
    clause_id = uuid4()
    signal = FindingSignal(
        rule_id="DET-TIM-SNAPSHOT",
        clause_id=str(clause_id),
        source="deterministic",
        impact_score=0.73,
        confidence=0.91,
        severity="high",
        category="TIME",
        evidence_summary="Schedule conflict",
        quote="Completion dates conflict.",
    )
    coverage = {
        "SCOPE": True,
        "BUDGET": True,
        "QUALITY": True,
        "TECHNICAL": True,
        "LEGAL": True,
        "TIME": True,
    }
    diagnostics = ScoringService().calculate_detailed(
        [signal],
        num_clauses=1,
        coverage_map=coverage,
    )
    alert = _signal_to_alert(signal)
    enriched = EnrichedCoherenceResult(
        overall_score=diagnostics.score,
        alerts=[alert],
        category_breakdown=_build_category_breakdown(
            [signal],
            coverage,
            diagnostics.category_scores or {},
        ),
        finding_signals=[signal],
        deterministic_findings_count=1,
        llm_findings_count=0,
        scope_factor=diagnostics.scope_factor,
        penalty_density=diagnostics.penalty_density,
        avg_impact=diagnostics.avg_impact,
        avg_confidence=diagnostics.avg_confidence,
        category_scores=diagnostics.category_scores,
        audit_coverage=diagnostics.audit_coverage,
    )

    finding_key = "family-snapshot"
    observation_key = "basis-snapshot"
    record = SimpleNamespace(
        alert_metadata={
            "finding_key": finding_key,
            "current_observation_key": observation_key,
        }
    )
    reconciliation = _CoherenceAlertReconciliation(
        finding_keys_by_alert_index=(finding_key,),
        records_by_finding_key={finding_key: record},
    )

    db = Mock()
    db.add = Mock()
    db.scalar = AsyncMock(return_value=None)
    db.commit = AsyncMock()

    with (
        patch(
            "src.coherence.router.evaluate_coherence_async",
            new_callable=AsyncMock,
            return_value=enriched,
        ),
        patch(
            "src.coherence.router._mirror_coherence_alerts_to_alerts_table",
            new_callable=AsyncMock,
            return_value=reconciliation,
        ),
        patch(
            "src.coherence.router._v2_enabled_for",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        result = await evaluate_project_coherence(
            payload=CoherenceEvaluateRequest(
                project_id=project_id,
                clauses=[
                    Clause(
                        id=str(clause_id),
                        text="Completion dates conflict.",
                        data={},
                    )
                ],
            ),
            include_diagnostics=True,
            db=db,
            current_user=SimpleNamespace(tenant_id=tenant_id),
            flags_service=None,
        )

    assert isinstance(result, EnrichedCoherenceResult)
    persisted = next(
        call.args[0]
        for call in db.add.call_args_list
        if isinstance(call.args[0], CoherenceResultORM)
    )
    snapshot = persisted.scoring_snapshot
    assert snapshot["schema_version"] == 1
    assert snapshot["score_version"] == result.score_version
    assert snapshot["num_clauses"] == 1
    assert snapshot["coverage_map"]["TIME"] is True
    assert snapshot["findings"][0]["finding_key"] == finding_key
    assert snapshot["findings"][0]["observation_key"] == observation_key
    assert snapshot["findings"][0]["signal"]["impact_score"] == pytest.approx(0.73)
    assert snapshot["findings"][0]["signal"]["confidence"] == pytest.approx(0.91)
    db.commit.assert_awaited_once()
