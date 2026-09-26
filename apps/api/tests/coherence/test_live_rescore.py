"""
Live canonical re-score invariants (ADR-017 canary, ADR-009 §G.1).

Refers to Suite ID: TS-UA-COH-CANON-LIVE-RESCORE-001.
"""
from __future__ import annotations

import pytest

from src.coherence.canonical.live_rescore import canonical_rescore
from src.coherence.models import CategoryBreakdown, SeverityCount

_CLEAN = ("SCHEDULE", "SCOPE", "TECHNICAL", "LEGAL", "QUALITY")


def _cb(category: str, state: str, **severities: int) -> CategoryBreakdown:
    return CategoryBreakdown(
        category=category,  # type: ignore[arg-type]
        score=None,
        alert_count=sum(severities.values()),
        severity_breakdown=SeverityCount(**severities),
        impact_percentage=0.0,
        state=state,
    )


@pytest.mark.unit
def test_all_clean_scores_100() -> None:
    breakdowns = [_cb(c, "assessed_clean") for c in ("BUDGET", *_CLEAN)]
    assert canonical_rescore(breakdowns).score == pytest.approx(100.0)


@pytest.mark.unit
def test_single_critical_caps_at_recalibrated_ceiling() -> None:
    """5 clean + 1 critical → canonical envelope caps at 85 (recalibrated), not v1's 65."""
    breakdowns = [_cb("BUDGET", "assessed_findings", critical=1)]
    breakdowns += [_cb(c, "assessed_clean") for c in _CLEAN]
    result = canonical_rescore(breakdowns)
    assert result.score == pytest.approx(85.0)  # §G.1 recalibrated critical ceiling
    budget = result.category_scores["BUDGET"]
    assert budget is not None and budget < 50.0  # the critical category is materially depressed


@pytest.mark.unit
def test_unassessed_category_is_null_not_zero() -> None:
    result = canonical_rescore([_cb("BUDGET", "unassessed")])
    assert result.category_scores["BUDGET"] is None


@pytest.mark.unit
def test_worst_severity_drives_category() -> None:
    """A category with mixed severities is driven by its worst finding."""
    breakdowns = [_cb("BUDGET", "assessed_findings", low=3, high=1)]
    breakdowns += [_cb(c, "assessed_clean") for c in _CLEAN]
    result = canonical_rescore(breakdowns)
    # a high (not low) drives BUDGET → capped by the high envelope (90), not clean.
    assert result.score is not None and result.score <= 90.0


@pytest.mark.unit
def test_alias_normalisation_maps_financial_to_budget() -> None:
    result = canonical_rescore([_cb("financial", "assessed_findings", high=1)])
    assert "BUDGET" in result.category_scores
