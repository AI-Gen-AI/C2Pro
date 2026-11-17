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


def _v2(signals):
    from uuid import uuid4

    from src.coherence.scoring import calculate_v2_from_signals
    from src.coherence.services.v2.evidence_service import EvidenceBundle

    categories = ("SCOPE", "BUDGET", "QUALITY", "TECHNICAL", "LEGAL", "TIME")
    bundles = {
        cat: EvidenceBundle(
            count=5,
            evidence_coverage=1.0,
            evidence_freshness=1.0,
            avg_technical_reliability=0.9,
            missing_required=[],
            references=["d1", "d2", "d3", "d4", "d5"],
        )
        for cat in categories
    }
    return calculate_v2_from_signals(
        signals=signals,
        evidence_bundles=bundles,
        applicability_map=dict.fromkeys(categories, (True, None)),
        project_id=uuid4(),
    )


def test_v2_considers_two_related_economic_rules_one_independent_conflict():
    a = _signal("DET-CRS-CONBUD", 1_000_000, 1_500_000)
    b = _signal("DET-CRS-NEGMARGIN", 1_000_000, 1_500_000)
    both = _v2([a, b])
    one = _v2([b])
    budget_both = next(cat for cat in both.categories if cat.category == "BUDGET")
    budget_one = next(cat for cat in one.categories if cat.category == "BUDGET")
    assert len(budget_both.detected_conflicts) == 1
    assert budget_both.coherence_score == budget_one.coherence_score
    assert both.global_.coherence_score == one.global_.coherence_score


def test_v2_does_not_merge_different_economic_revisions():
    a = _signal("DET-CRS-CONBUD", 1_000_000, 1_500_000)
    b = _signal("DET-CRS-NEGMARGIN", 1_000_000, 1_500_000, source="revision-2")
    report = _v2([a, b])
    assert (
        len(next(cat for cat in report.categories if cat.category == "BUDGET").detected_conflicts)
        == 2
    )


def test_canonical_canary_category_breakdown_counts_one_economic_impact():
    from src.coherence.graph.nodes import _build_category_breakdown

    a = _signal("DET-CRS-CONBUD", 1_000_000, 1_500_000)
    b = _signal("DET-CRS-NEGMARGIN", 1_000_000, 1_500_000)
    coverage = {k: k == "BUDGET" for k in ScoringService._ALL_CATEGORIES}
    combined = _build_category_breakdown([a, b], coverage, {"BUDGET": 45.0})
    budget = next(c for c in combined if c.category == "financial")
    assert budget.alert_count == 1
    assert budget.severity_breakdown.critical == 1


def test_v2_unassessed_budget_never_issues_numeric_budget_score():
    from uuid import uuid4

    from src.coherence.scoring import calculate_v2_from_signals
    from src.coherence.services.v2.evidence_service import EvidenceBundle

    categories = ("SCOPE", "BUDGET", "QUALITY", "TECHNICAL", "LEGAL", "TIME")
    bundles = {
        cat: EvidenceBundle(
            count=5,
            evidence_coverage=1.0,
            evidence_freshness=1.0,
            avg_technical_reliability=0.9,
            missing_required=[],
            references=["d1", "d2", "d3", "d4", "d5"],
        )
        for cat in categories
    }
    findings = [
        _signal(rule, 1_000_000, 1_500_000) for rule in ("DET-CRS-CONBUD", "DET-CRS-NEGMARGIN")
    ]
    payload = calculate_v2_from_signals(
        signals=findings,
        evidence_bundles=bundles,
        applicability_map=dict.fromkeys(categories, (True, None)),
        project_id=uuid4(),
        assessment_by_category={"BUDGET": False},
        assessment_reason_by_category={"BUDGET": "S7_SOURCE_NOT_HUMAN_APPROVED"},
    )
    budget = next(item for item in payload.categories if item.category == "BUDGET")
    assert budget.coherence_score is None
    assert budget.calculation_metadata["assessment_state"] == "unassessed"


def test_canary_score_for_same_budget_discrepancy_equals_one_impact():
    from src.coherence.canonical.live_rescore import canonical_rescore
    from src.coherence.graph.nodes import _build_category_breakdown

    a = _signal("DET-CRS-CONBUD", 1_000_000, 1_500_000)
    b = _signal("DET-CRS-NEGMARGIN", 1_000_000, 1_500_000)
    coverage = dict.fromkeys(ScoringService._ALL_CATEGORIES, True)
    scores = {"BUDGET": 45.0}
    both = _build_category_breakdown([a, b], coverage, scores)
    one = _build_category_breakdown([b], coverage, scores)
    assert canonical_rescore(both).score == canonical_rescore(one).score
    assert next(x for x in both if x.category == "financial").alert_count == 1
