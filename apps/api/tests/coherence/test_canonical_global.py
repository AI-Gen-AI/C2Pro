"""
Canonical global aggregation + critical-risk envelope invariants (ADR-009 §C/§14).

The global layer is the ONLY place `worst_open` acts: it applies the envelope
(interim `overall critical ≤ 60`) and enforces null-not-zero on insufficient
active weight. It performs no per-category scoring.

Refers to Suite ID: TS-UA-COH-CANON-GLOBAL-001.
"""
from __future__ import annotations

import pytest

from src.coherence.canonical.category import CategoryScore
from src.coherence.canonical.global_agg import GlobalScoreInput, aggregate_global

_ALL = ("SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY")


def _scores(value: float | None, n: int = 6) -> dict[str, CategoryScore]:
    return {
        cat: CategoryScore(score=value, band=None)
        for cat in _ALL[:n]
    }


def _weights(n: int = 6) -> dict[str, float]:
    return dict.fromkeys(_ALL[:n], 1.0)


@pytest.mark.unit
def test_plain_weighted_mean_without_worst_open() -> None:
    out = aggregate_global(
        GlobalScoreInput(_scores(100.0), _weights(), worst_open_severity=None)
    )
    assert out.score == pytest.approx(100.0)
    assert out.envelope_applied is None


@pytest.mark.unit
def test_open_critical_caps_headline_at_60() -> None:
    """Five/six clean categories must not headline 'healthy' with an open critical."""
    out = aggregate_global(
        GlobalScoreInput(_scores(100.0), _weights(), worst_open_severity="critical")
    )
    assert out.score == pytest.approx(60.0)
    assert out.envelope_applied == "critical"


@pytest.mark.unit
def test_open_high_caps_headline_at_75() -> None:
    out = aggregate_global(
        GlobalScoreInput(_scores(90.0), _weights(), worst_open_severity="high")
    )
    assert out.score == pytest.approx(75.0)
    assert out.envelope_applied == "high"


@pytest.mark.unit
def test_envelope_only_lowers_never_raises() -> None:
    """If the mean is already below the cap, the envelope does not fire."""
    out = aggregate_global(
        GlobalScoreInput(_scores(50.0), _weights(), worst_open_severity="critical")
    )
    assert out.score == pytest.approx(50.0)
    assert out.envelope_applied is None


@pytest.mark.unit
def test_insufficient_active_weight_is_null_not_zero() -> None:
    """Only 1 of 6 categories assessed ⇒ active_weight 0.167 < 0.35 ⇒ null headline."""
    scores = {"SCOPE": CategoryScore(score=90.0, band=None)}
    for cat in _ALL[1:]:
        scores[cat] = CategoryScore(score=None, band=None)
    out = aggregate_global(GlobalScoreInput(scores, _weights(), worst_open_severity=None))
    assert out.score is None
    assert out.reason == "insufficient_active_weight"


@pytest.mark.unit
def test_weighted_mean_respects_weights() -> None:
    scores = {"BUDGET": CategoryScore(score=40.0, band=None),
              "LEGAL": CategoryScore(score=100.0, band=None)}
    weights = {"BUDGET": 3.0, "LEGAL": 1.0}  # active_weight = 1.0 (only these two exist)
    out = aggregate_global(GlobalScoreInput(scores, weights, worst_open_severity=None))
    # (40*3 + 100*1) / 4 = 55
    assert out.score == pytest.approx(55.0)
