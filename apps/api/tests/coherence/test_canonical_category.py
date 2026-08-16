"""
Canonical per-category scorer invariants (ADR-009 §A/§B/§D, 2026-08-16 amendment).

Interim band anchors: ceilings {low:95, med:80, high:65, crit:45}, floors are the
next-worse ceiling with the VP-pinned critical floor = 25. Certainty×materiality
interpolates within the band (higher ⇒ nearer the floor).

Refers to Suite ID: TS-UA-COH-CANON-CAT-001.
"""
from __future__ import annotations

import pytest

from src.coherence.canonical.category import (
    CategoryScoreInput,
    ConflictInput,
    score_category,
)
from src.coherence.canonical.guardrails import FLOOR_MIN_SCORE


def _crit(certainty: float = 1.0, magnitude: float | None = 1.0) -> CategoryScoreInput:
    return CategoryScoreInput(
        base=100.0,
        conflict=ConflictInput(severity="critical", certainty=certainty, magnitude=magnitude),
    )


# --- null-not-zero -----------------------------------------------------------


@pytest.mark.unit
def test_unassessed_yields_null_not_zero() -> None:
    out = score_category(CategoryScoreInput(base=100.0, assessed=False))
    assert out.score is None


@pytest.mark.unit
def test_insufficient_evidence_yields_null_not_zero() -> None:
    out = score_category(CategoryScoreInput(base=100.0, evidence_sufficient=False))
    assert out.score is None


# --- clean (no hard conflict) ------------------------------------------------


@pytest.mark.unit
def test_no_conflict_returns_base() -> None:
    out = score_category(CategoryScoreInput(base=88.0))
    assert out.score == pytest.approx(88.0)
    assert out.band == "clean"


# --- the chosen interim band -------------------------------------------------


@pytest.mark.unit
def test_fully_certain_material_critical_lands_on_floor_25() -> None:
    """VP-pinned interim: a fully-certain, fully-material critical → 25 (not ~8, not 0)."""
    out = score_category(_crit(certainty=1.0, magnitude=1.0))
    assert out.score == pytest.approx(25.0)
    assert out.band == "critical"


@pytest.mark.unit
def test_less_certain_critical_is_milder() -> None:
    """certainty 0.9 ⇒ 45 - 20*0.9 = 27.0 (milder penalty, higher score)."""
    out = score_category(_crit(certainty=0.9, magnitude=1.0))
    assert out.score == pytest.approx(27.0)


# --- invariants --------------------------------------------------------------


@pytest.mark.unit
def test_conflict_is_never_zero() -> None:
    out = score_category(_crit(certainty=1.0, magnitude=1.0))
    assert out.score is not None
    assert out.score > 0.0
    assert out.score >= FLOOR_MIN_SCORE


@pytest.mark.unit
def test_certainty_is_monotonic_penalty_direction() -> None:
    """Higher certainty ⇒ stronger penalty ⇒ lower-or-equal score."""
    high = score_category(_crit(certainty=1.0)).score
    mid = score_category(_crit(certainty=0.9)).score
    low = score_category(_crit(certainty=0.5)).score
    assert high is not None and mid is not None and low is not None
    assert high <= mid <= low


@pytest.mark.unit
def test_materiality_is_monotonic() -> None:
    """Higher materiality ⇒ stronger penalty ⇒ lower-or-equal score."""
    full = score_category(_crit(certainty=1.0, magnitude=1.0)).score
    half = score_category(_crit(certainty=1.0, magnitude=0.5)).score
    assert full is not None and half is not None
    assert full <= half  # 25 <= 35


@pytest.mark.unit
def test_severity_is_monotonic_at_full_certainty() -> None:
    def s(sev: str) -> float:
        out = score_category(
            CategoryScoreInput(
                base=100.0,
                conflict=ConflictInput(severity=sev, certainty=1.0, magnitude=1.0),  # type: ignore[arg-type]
            )
        )
        assert out.score is not None
        return out.score

    crit, high, med, low = s("critical"), s("high"), s("medium"), s("low")
    assert crit < high < med < low
    assert (crit, high, med, low) == (25.0, 45.0, 65.0, 80.0)


@pytest.mark.unit
def test_conflict_scores_worse_than_clean_base() -> None:
    clean = score_category(CategoryScoreInput(base=100.0)).score
    conflicted = score_category(_crit()).score
    assert clean is not None and conflicted is not None
    assert conflicted < clean
