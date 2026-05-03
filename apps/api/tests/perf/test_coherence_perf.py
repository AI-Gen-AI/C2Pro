"""TS-INF-PERF-056-002: Coherence scoring benchmark coverage."""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.performance


def _make_signals(count: int):
    from src.coherence.models import FindingSignal

    categories = ["SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"]
    severities = ["low", "medium", "high", "critical"]
    return [
        FindingSignal(
            rule_id=f"DET-PERF-{index:04d}",
            clause_id=f"clause-{index:04d}",
            source="deterministic",
            impact_score=0.25 + ((index % 4) * 0.15),
            confidence=0.9,
            severity=severities[index % len(severities)],
            category=categories[index % len(categories)],
            evidence_summary="Synthetic benchmark finding",
            quote="Synthetic clause evidence",
        )
        for index in range(count)
    ]


def test_coherence_scoring_handles_250_findings(benchmark) -> None:
    """TS-INF-PERF-056-002: Benchmark deterministic coherence scoring."""
    from src.coherence.scoring import ScoringService

    service = ScoringService()
    signals = _make_signals(250)

    result = benchmark.pedantic(
        service.calculate_from_signals,
        args=(signals,),
        kwargs={"num_clauses": 50, "num_rules": 18},
        rounds=8,
        iterations=5,
    )

    assert result.score is not None
