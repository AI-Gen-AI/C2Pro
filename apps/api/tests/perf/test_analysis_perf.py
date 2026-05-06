"""TS-INF-PERF-056-002: Analysis derivation benchmark coverage."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.performance


def _analysis_input():
    from src.analysis.domain.coherence_derivation import CoherenceDerivationInput

    risks = [
        {
            "category": category,
            "impact": "HIGH" if index % 7 == 0 else "LOW",
            "description": f"Synthetic risk {index}",
        }
        for index, category in enumerate(
            ["SCOPE", "BUDGET", "SCHEDULE", "TECHNICAL", "LEGAL", "QUALITY"] * 25
        )
    ]
    wbs = [
        {"name": f"Activity {index}", "confidence": 0.82, "duration_days": (index % 12) + 1}
        for index in range(180)
    ]
    bom = [{"name": f"Item {index}", "amount": 1250.0 + index} for index in range(120)]
    return CoherenceDerivationInput(
        extracted_risks=risks,
        extracted_wbs=wbs,
        bom_items=bom,
        confidence_score=0.86,
        document_text="Construction contract scope and commercial terms. " * 80,
    )


def test_analysis_coherence_derivation_handles_large_extraction(benchmark) -> None:
    """TS-INF-PERF-056-002: Benchmark pure analysis-to-coherence derivation."""
    from src.analysis.domain.coherence_derivation import CoherenceScoringDerivationService

    service = CoherenceScoringDerivationService()
    input_data = _analysis_input()

    result = benchmark.pedantic(service.derive, args=(input_data,), rounds=8, iterations=5)

    assert result.risk_count == 150
    assert result.wbs_count == 180
