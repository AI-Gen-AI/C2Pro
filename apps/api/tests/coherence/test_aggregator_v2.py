"""
Tests for the global aggregator (ADR-009 §14, §15).

Refers to Suite ID: TS-UA-COH-V2-GLBAGG-001.
"""
from __future__ import annotations

import pytest

from src.coherence.application.dtos.coherence_v2_dtos import (
    CategoryStatus,
    CategoryV2,
    ScoreExplanation,
)
from src.coherence.domain.v2_constants import (
    DEFAULT_CATEGORY_WEIGHTS,
    MIN_ACTIVE_WEIGHT,
)
from src.coherence.services.v2.aggregator_v2 import GlobalAggregatorV2


def _scored(category: str, score: float, tri: float = 0.9,
            coverage: float = 1.0, freshness: float = 1.0) -> CategoryV2:
    return CategoryV2(
        category=category,
        status=CategoryStatus.SCORED,
        coherence_score=score,
        evidence_coverage=coverage,
        technical_reliability=tri,
        evidence_freshness=freshness,
        score_explanation=ScoreExplanation(),
    )


def _insufficient(category: str) -> CategoryV2:
    return CategoryV2(
        category=category,
        status=CategoryStatus.INSUFFICIENT_EVIDENCE,
        coherence_score=None,
        evidence_coverage=0.0,
        technical_reliability=0.0,
        evidence_freshness=0.0,
    )


def _na(category: str, reason: str = "not in scope") -> CategoryV2:
    return CategoryV2(
        category=category,
        status=CategoryStatus.NOT_APPLICABLE,
        coherence_score=None,
        evidence_coverage=0.0,
        technical_reliability=0.0,
        evidence_freshness=0.0,
        applicability_reason=reason,
    )


@pytest.fixture
def aggregator() -> GlobalAggregatorV2:
    return GlobalAggregatorV2()


@pytest.mark.unit
def test_active_weight_below_min_returns_null(aggregator: GlobalAggregatorV2) -> None:
    # Only LEGAL (1/6 ≈ 0.167) is active — below 0.35.
    categories = [
        _scored("LEGAL", 95.0),
        _insufficient("SCOPE"),
        _insufficient("BUDGET"),
        _insufficient("TIME"),
        _insufficient("TECHNICAL"),
        _insufficient("QUALITY"),
    ]
    g = aggregator.aggregate(categories)
    assert g.coherence_score is None
    assert g.score_reason == "insufficient_active_weight"
    assert g.active_weight < MIN_ACTIVE_WEIGHT


@pytest.mark.unit
def test_active_weight_above_min_returns_weighted_score(
    aggregator: GlobalAggregatorV2,
) -> None:
    # Three scored categories: 3/6 = 0.5 active_weight.
    categories = [
        _scored("LEGAL", 80.0),
        _scored("BUDGET", 60.0),
        _scored("SCOPE", 100.0),
        _insufficient("TIME"),
        _insufficient("TECHNICAL"),
        _insufficient("QUALITY"),
    ]
    g = aggregator.aggregate(categories)
    assert g.coherence_score is not None
    expected = (80.0 + 60.0 + 100.0) / 3.0
    assert g.coherence_score == pytest.approx(expected, rel=1e-6)
    assert g.active_weight == pytest.approx(0.5, rel=1e-6)


@pytest.mark.unit
def test_open_critical_caps_headline_at_60(aggregator: GlobalAggregatorV2) -> None:
    """§C envelope: an open critical caps the headline at 60 even when the mean is high."""
    categories = [
        _scored("LEGAL", 100.0),
        _scored("BUDGET", 100.0),
        _scored("SCOPE", 100.0),
        _scored("TIME", 100.0),
        _scored("TECHNICAL", 100.0),
        _scored("QUALITY", 100.0),
    ]
    g = aggregator.aggregate(categories, worst_open_severity="critical")
    assert g.coherence_score == pytest.approx(60.0)
    assert g.score_reason == "critical_risk_capped:critical"


@pytest.mark.unit
def test_envelope_only_lowers_never_raises(aggregator: GlobalAggregatorV2) -> None:
    """If the mean already sits below the cap, the envelope does not fire."""
    categories = [
        _scored("LEGAL", 40.0),
        _scored("BUDGET", 40.0),
        _scored("SCOPE", 40.0),
        _insufficient("TIME"),
        _insufficient("TECHNICAL"),
        _insufficient("QUALITY"),
    ]
    g = aggregator.aggregate(categories, worst_open_severity="critical")
    assert g.coherence_score == pytest.approx(40.0)
    assert g.score_reason == "scored_categories_only"


@pytest.mark.unit
def test_not_applicable_excluded_from_active_weight(
    aggregator: GlobalAggregatorV2,
) -> None:
    # SCOPE + BUDGET scored; TIME marked N/A so denominator drops to 5 categories.
    categories = [
        _scored("SCOPE", 90.0),
        _scored("BUDGET", 70.0),
        _na("TIME"),
        _insufficient("TECHNICAL"),
        _insufficient("LEGAL"),
        _insufficient("QUALITY"),
    ]
    g = aggregator.aggregate(categories)
    # 2 active out of 5 applicable categories.
    expected_active_weight = 2 * (1.0 / 6.0) / (5.0 * (1.0 / 6.0))
    assert g.active_weight == pytest.approx(expected_active_weight, rel=1e-6)


@pytest.mark.unit
def test_completeness_independent_of_coherence(
    aggregator: GlobalAggregatorV2,
) -> None:
    # Same scored scores, but second test has lower coverage per category.
    a = [_scored(c, 80.0, coverage=1.0) for c in DEFAULT_CATEGORY_WEIGHTS]
    b = [_scored(c, 80.0, coverage=0.5) for c in DEFAULT_CATEGORY_WEIGHTS]
    ga = aggregator.aggregate(a)
    gb = aggregator.aggregate(b)
    assert ga.coherence_score == gb.coherence_score
    assert gb.completeness_score < ga.completeness_score


@pytest.mark.unit
def test_technical_reliability_index_weighted_over_active_only(
    aggregator: GlobalAggregatorV2,
) -> None:
    categories = [
        _scored("SCOPE", 80.0, tri=1.0),
        _scored("BUDGET", 80.0, tri=0.5),
        _insufficient("TIME"),
        _insufficient("TECHNICAL"),
        _insufficient("LEGAL"),
        _insufficient("QUALITY"),
    ]
    g = aggregator.aggregate(categories)
    # Mean of 1.0 and 0.5 (excluding insufficient).
    assert g.technical_reliability_index == pytest.approx(0.75, rel=1e-6)


@pytest.mark.unit
def test_status_pending_when_zero_active_and_zero_evidence(
    aggregator: GlobalAggregatorV2,
) -> None:
    categories = [
        CategoryV2(
            category=c,
            status=CategoryStatus.PENDING_DOCUMENTS,
            coherence_score=None,
            evidence_coverage=0.0,
            technical_reliability=0.0,
            evidence_freshness=0.0,
        )
        for c in DEFAULT_CATEGORY_WEIGHTS
    ]
    g = aggregator.aggregate(categories)
    assert g.status == "pending_documents"
    assert g.coherence_score is None
    assert g.completeness_score == 0.0


@pytest.mark.unit
def test_status_scored_when_all_categories_active(
    aggregator: GlobalAggregatorV2,
) -> None:
    categories = [_scored(c, 80.0) for c in DEFAULT_CATEGORY_WEIGHTS]
    g = aggregator.aggregate(categories)
    assert g.status == "scored"
    assert g.active_weight == pytest.approx(1.0, rel=1e-6)
