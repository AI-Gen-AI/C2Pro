"""
Tests for the per-category aggregator (ADR-009 §6, §10, §13).

Refers to Suite ID: TS-UA-COH-V2-CATAGG-001.
"""
from __future__ import annotations

import pytest

from src.coherence.application.dtos.coherence_v2_dtos import (
    CategoryStatus,
    CategoryV2,
)
from src.coherence.domain.category_state_machine import CategoryStateMachine
from src.coherence.services.v2.category_aggregator import CategoryAggregator
from src.coherence.services.v2.conflict_service import ConflictReport
from tests.support.coherence_builders import bundle as _bundle
from tests.support.coherence_builders import no_conflict as _no_conflict


@pytest.fixture
def aggregator() -> CategoryAggregator:
    return CategoryAggregator(CategoryStateMachine())


@pytest.mark.unit
def test_insufficient_evidence_yields_null_score(aggregator: CategoryAggregator) -> None:
    cat: CategoryV2 = aggregator.aggregate(
        category="BUDGET",
        evidence=_bundle(count=1),
        conflict=_no_conflict(),
        rule_signals=[],
        applicable=True,
    )
    assert cat.status is CategoryStatus.INSUFFICIENT_EVIDENCE
    assert cat.coherence_score is None


@pytest.mark.unit
def test_pending_documents_when_no_evidence(aggregator: CategoryAggregator) -> None:
    cat = aggregator.aggregate(
        category="SCOPE",
        evidence=_bundle(count=0, coverage=0.0, tri=0.0, freshness=0.0),
        conflict=_no_conflict(),
        rule_signals=[],
        applicable=True,
    )
    assert cat.status is CategoryStatus.PENDING_DOCUMENTS
    assert cat.coherence_score is None


@pytest.mark.unit
def test_not_applicable_carries_reason(aggregator: CategoryAggregator) -> None:
    cat = aggregator.aggregate(
        category="QUALITY",
        evidence=_bundle(count=5),
        conflict=_no_conflict(),
        rule_signals=[],
        applicable=False,
        applicability_reason="No quality-bound deliverables in contract.",
    )
    assert cat.status is CategoryStatus.NOT_APPLICABLE
    assert cat.coherence_score is None
    assert cat.applicability_reason == "No quality-bound deliverables in contract."


@pytest.mark.unit
def test_no_rule_signals_unassessed_yields_honest_null(
    aggregator: CategoryAggregator,
) -> None:
    """TS-UA-COH-V2-CATAGG-001 - INV-1: missing rule assessment must not fabricate 100."""
    cat = aggregator.aggregate(
        category="LEGAL",
        evidence=_bundle(count=1),
        conflict=_no_conflict(),
        rule_signals=[],
        applicable=True,
        assessed=False,
    )

    assert cat.status is CategoryStatus.INSUFFICIENT_EVIDENCE
    assert cat.coherence_score is None
    assert cat.rationale == "rule_assessment_unavailable"
    assert cat.calculation_metadata["assessment_state"] == "unassessed"


@pytest.mark.unit
def test_no_rule_signals_assessed_clean_yields_legitimate_high_score(
    aggregator: CategoryAggregator,
) -> None:
    """TS-UA-COH-V2-CATAGG-001 - Assessed clean categories may score high without findings."""
    cat = aggregator.aggregate(
        category="LEGAL",
        evidence=_bundle(count=1),
        conflict=_no_conflict(),
        rule_signals=[],
        applicable=True,
        assessed=True,
    )

    assert cat.status is CategoryStatus.SCORED
    assert cat.coherence_score == pytest.approx(100.0)
    assert cat.calculation_metadata["assessment_state"] == "assessed_clean"


@pytest.mark.unit
@pytest.mark.parametrize(
    "severity,certainty,base,expected",
    [
        # ADR-009 §B/§C/§D: scoring is delegated to the canonical model. A hard
        # conflict lands in its severity band [floor, ceiling] positioned by
        # certainty × materiality (magnitude None ⇒ fully material). Bands are
        # anchored on the #532 interim ceilings, so `base` no longer scales a
        # conflicted score — it is band-determined.
        ("low", 1.0, 80.0, 80.0),        # band [80,95], strength 1.0 → 80
        ("medium", 0.9, 80.0, 66.5),     # band [65,80], strength 0.9 → 80-15*0.9
        ("high", 1.0, 80.0, 45.0),       # band [45,65], strength 1.0 → 45
        ("critical", 1.0, 80.0, 25.0),   # band [25,45], strength 1.0 → 25 (VP floor)
    ],
)
def test_adjusted_score_formula_for_conflicts(
    aggregator: CategoryAggregator,
    severity: str,
    certainty: float,
    base: float,
    expected: float,
) -> None:
    conflict = ConflictReport(
        severity=severity,
        hard_conflict=True,
        conflict_set=[{"clauses": ["a", "b"]}],
        evidence_certainty=certainty,
    )
    cat = aggregator.aggregate(
        category="BUDGET",
        evidence=_bundle(),
        conflict=conflict,
        rule_signals=[("dummy_rule", base)],
        applicable=True,
    )
    assert cat.status is CategoryStatus.CONFLICTING_EVIDENCE
    assert cat.coherence_score == pytest.approx(expected, rel=1e-6)


@pytest.mark.unit
def test_materiality_positions_within_band(aggregator: CategoryAggregator) -> None:
    """A larger relative discrepancy scores nearer the band floor (materiality-positioned)."""

    def _score(delta: float, denom: float) -> float:
        conflict = ConflictReport(
            severity="high",
            hard_conflict=True,
            conflict_set=[{"compared_values": {"a": denom, "b": denom - delta}, "delta": delta}],
            evidence_certainty=1.0,
        )
        cat = aggregator.aggregate(
            category="BUDGET",
            evidence=_bundle(),
            conflict=conflict,
            rule_signals=[("r", 80.0)],
            applicable=True,
        )
        assert cat.coherence_score is not None
        return cat.coherence_score

    small_gap = _score(delta=5.0, denom=100.0)  # ratio 0.05 → near the ceiling
    large_gap = _score(delta=60.0, denom=100.0)  # ratio 0.60 → floor
    assert large_gap < small_gap
    assert 45.0 <= large_gap <= 65.0  # both stay inside the high band [45, 65]
    assert 45.0 <= small_gap <= 65.0


@pytest.mark.unit
def test_score_explanation_records_multipliers(aggregator: CategoryAggregator) -> None:
    conflict = ConflictReport(
        severity="medium",
        hard_conflict=True,
        conflict_set=[{"clauses": ["a", "b"]}],
        evidence_certainty=0.8,
    )
    cat = aggregator.aggregate(
        category="BUDGET",
        evidence=_bundle(),
        conflict=conflict,
        rule_signals=[("budget_overrun", 90.0)],
        applicable=True,
    )
    assert cat.score_explanation is not None
    steps = {step["step"] for step in cat.score_explanation.score_path}
    # Canonical audit trail: base + severity band + certainty-scaled penalty strength.
    assert {"base", "severity_band", "penalty_strength"} <= steps


@pytest.mark.unit
def test_scored_branch_returns_value_in_range(aggregator: CategoryAggregator) -> None:
    cat = aggregator.aggregate(
        category="LEGAL",
        evidence=_bundle(count=1),  # LEGAL threshold = 1
        conflict=_no_conflict(),
        rule_signals=[("legal_clean", 100.0)],
        applicable=True,
    )
    assert cat.status is CategoryStatus.SCORED
    assert cat.coherence_score is not None
    assert 0.0 <= cat.coherence_score <= 100.0


@pytest.mark.unit
def test_evidence_freshness_is_propagated(aggregator: CategoryAggregator) -> None:
    cat = aggregator.aggregate(
        category="LEGAL",
        evidence=_bundle(count=1, freshness=0.42),
        conflict=_no_conflict(),
        rule_signals=[("ok", 100.0)],
        applicable=True,
    )
    assert cat.evidence_freshness == pytest.approx(0.42)
