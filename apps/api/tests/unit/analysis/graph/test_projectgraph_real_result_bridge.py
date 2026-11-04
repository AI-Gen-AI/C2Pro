"""Bridge a real Coherence engine result into truthful ProjectGraph counters.

Regression for first real four-source Actions run #41901333440: the engine
created alerts but the project summary reported zero findings, and the
financial/schedule dimensions were not translated to BUDGET/TIME.
"""
from __future__ import annotations

from src.analysis.adapters.graph.project_graph import _coherence_summary
from src.coherence.models import (
    Alert,
    CategoryBreakdown,
    EnrichedCoherenceResult,
    Evidence,
    FindingSignal,
    SeverityCount,
)


def test_projectgraph_counts_evaluated_alerts_and_uses_canonical_dimensions() -> None:
    signals = [
        FindingSignal(
            rule_id="DET-CONTRACT-BUDGET",
            clause_id="source-contract",
            source="deterministic",
            impact_score=0.6,
            category="BUDGET",
            quote="Contract EUR 1,000,000",
        ),
        FindingSignal(
            rule_id="DET-SCHEDULE-DEADLINE",
            clause_id="source-schedule",
            source="deterministic",
            impact_score=0.7,
            category="TIME",
            quote="Handover on 30 September",
        ),
    ]
    alerts = [
        Alert(
            rule_id=signal.rule_id,
            severity="high",
            category="financial" if signal.category == "BUDGET" else "schedule",
            message="Grounded inconsistency",
            evidence=Evidence(
                source_clause_id=signal.clause_id,
                claim="The project evidence disagrees",
                quote=signal.quote,
            ),
        )
        for signal in signals
    ]
    result = EnrichedCoherenceResult(
        overall_score=46.3,
        finding_signals=signals,
        alerts=alerts,
        category_breakdown=[
            CategoryBreakdown(
                category="financial",
                score=36.1,
                alert_count=1,
                severity_breakdown=SeverityCount(high=1),
                impact_percentage=40.0,
            ),
            CategoryBreakdown(
                category="schedule",
                score=44.8,
                alert_count=1,
                severity_breakdown=SeverityCount(high=1),
                impact_percentage=60.0,
            ),
        ],
        score_missing_dimensions=["TECHNICAL"],
    )

    summary = _coherence_summary(
        result, signal_count=0, finding_count=0, artifact_count=1, llm_on=True
    )

    assert summary.signal_count == 2
    assert summary.finding_count == 2
    assert summary.category_scores == {"BUDGET": 36.1, "TIME": 44.8}
    assert summary.overall_score == 46.3
    assert summary.insufficient_data_reasons == ["TECHNICAL"]


def test_artifact_findings_remain_visible_when_engine_has_no_final_alerts() -> None:
    result = EnrichedCoherenceResult(overall_score=None)
    summary = _coherence_summary(
        result, signal_count=3, finding_count=2, artifact_count=2, llm_on=False
    )
    assert summary.signal_count == 3
    assert summary.finding_count == 2
    assert summary.overall_score is None
