"""S7: one contract-budget fact can have two alerts, but ONE score impact."""

from __future__ import annotations

from src.coherence.models import FindingSignal
from src.coherence.scoring import ScoringService


def _signal(
    rule: str, contract: float, budget: float, *, source: str = "revision-1"
) -> FindingSignal:
    return FindingSignal(
        rule_id=rule,
        clause_id=f"xdoc:{rule}",
        source="deterministic",
        impact_score=0.83 if rule == "DET-CRS-CONBUD" else 1.0,
        confidence=1.0,
        severity="critical",
        category="BUDGET",
        raw_data={
            "contract_total": contract,
            "budget_total": budget,
            "delta": budget - contract,
            "evidence": {
                "sources": [
                    {
                        "family": "budget",
                        "document_id": "doc-1",
                        "revision_id": source,
                        "source_locator": "Presupuesto!5",
                    }
                ]
            },
        },
    )


def test_related_economic_alerts_count_one_score_penalty_even_with_full_coverage():
    scoring = ScoringService()
    conbud = _signal("DET-CRS-CONBUD", 1_000_000, 1_500_000)
    negmargin = _signal("DET-CRS-NEGMARGIN", 1_000_000, 1_500_000)
    coverage = dict.fromkeys(scoring._ALL_CATEGORIES, True)
    only_stronger = scoring.calculate_detailed([negmargin], 5, coverage_map=coverage)
    both = scoring.calculate_detailed([conbud, negmargin], 5, coverage_map=coverage)
    assert both.raw_penalty_sum == only_stronger.raw_penalty_sum
    assert both.category_contributions == only_stronger.category_contributions
    assert both.score == only_stronger.score
    assert both.total_findings == 1
    assert both.severity_distribution["critical"] == 1
    assert scoring.calculate_from_signals([conbud, negmargin], 5) == scoring.calculate_from_signals(
        [negmargin], 5
    )


def test_different_revision_or_comparison_is_not_falsely_collapsed():
    scoring = ScoringService()
    coverage = dict.fromkeys(scoring._ALL_CATEGORIES, True)
    a = _signal("DET-CRS-CONBUD", 1_000_000, 1_500_000)
    b = _signal("DET-CRS-NEGMARGIN", 1_000_000, 1_500_000, source="revision-2")
    different = scoring.calculate_detailed([a, b], 5, coverage_map=coverage)
    assert different.total_findings == 2
    assert (
        different.raw_penalty_sum
        > scoring.calculate_detailed([b], 5, coverage_map=coverage).raw_penalty_sum
    )
    c = _signal("DET-CRS-NEGMARGIN", 1_000_000, 1_700_000)
    assert scoring.calculate_detailed([a, c], 5, coverage_map=coverage).total_findings == 2


def test_unrelated_findings_remain_independent():
    scoring = ScoringService()
    a = _signal("DET-CRS-CONBUD", 1_000_000, 1_500_000)
    c = _signal("DET-CRS-WBSBUD", 1_000_000, 1_500_000)
    coverage = dict.fromkeys(scoring._ALL_CATEGORIES, True)
    assert scoring.calculate_detailed([a, c], 5, coverage_map=coverage).total_findings == 2
