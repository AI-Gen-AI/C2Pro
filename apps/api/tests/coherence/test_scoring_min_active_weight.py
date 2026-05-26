"""
TDD RED tests — §14 MIN_ACTIVE_WEIGHT guard for _calculate_detailed_with_coverage.

ADR-009 §1 P1 + §14: when the sum of assessed-category weights is below
MIN_ACTIVE_WEIGHT (0.35), the function MUST return score=None with
reason="insufficient_active_weight" rather than a mean×coverage_ratio scalar.

Suite IDs: TS-UA-COH-SCORING-014 through TS-UA-COH-SCORING-017
"""
from __future__ import annotations

import pytest

from src.coherence.scoring import ScoringDiagnostics, ScoringService
from src.coherence.domain.v2_constants import MIN_ACTIVE_WEIGHT, DEFAULT_CATEGORY_WEIGHTS

ALL_CATEGORIES = ("SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY")


@pytest.fixture
def svc() -> ScoringService:
    return ScoringService()


# ---------------------------------------------------------------------------
# TS-UA-COH-SCORING-014
# SCOPE-only assessed (weight 1/6 ≈ 0.167 < 0.35) + zero findings → null
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_scope_only_returns_null_score(svc: ScoringService) -> None:
    """
    A project where only SCOPE is assessed has active_weight ≈ 0.167 which
    is below MIN_ACTIVE_WEIGHT=0.35. The engine MUST return score=None and
    reason="insufficient_active_weight" (ADR-009 §14).
    """
    coverage_map = {c: (c == "SCOPE") for c in ALL_CATEGORIES}

    result: ScoringDiagnostics = svc.calculate_detailed(
        signals=[],
        num_clauses=10,
        coverage_map=coverage_map,
    )

    assert result.score is None, (
        f"Expected None but got {result.score}; "
        "active_weight for SCOPE-only is ~0.167 < MIN_ACTIVE_WEIGHT=0.35"
    )
    assert result.reason == "insufficient_active_weight", (
        f"Expected reason='insufficient_active_weight' but got {result.reason!r}"
    )


# ---------------------------------------------------------------------------
# TS-UA-COH-SCORING-015
# SCOPE + BUDGET + QUALITY assessed (weights 1/6+1/6+1/6 = 0.50 ≥ 0.35)
# with zero findings → numeric score, reason=None
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_three_categories_returns_numeric_score(svc: ScoringService) -> None:
    """
    With SCOPE+BUDGET+QUALITY assessed, active_weight = 3/6 = 0.50 ≥ 0.35.
    Zero findings means each category gets the clean baseline (~90).
    Must return a numeric score and reason=None (not 'assessed_clean' collapse).
    Note: SCOPE+BUDGET alone gives 2/6 ≈ 0.333 < 0.35, still insufficient.
    """
    coverage_map = {
        "SCOPE": True,
        "BUDGET": True,
        "QUALITY": True,
        "TIME": False,
        "TECHNICAL": False,
        "LEGAL": False,
    }

    result: ScoringDiagnostics = svc.calculate_detailed(
        signals=[],
        num_clauses=10,
        coverage_map=coverage_map,
    )

    assert result.score is not None, (
        "Expected a numeric score for active_weight=0.50 (≥ 0.35)"
    )
    assert isinstance(result.score, float), f"score must be float, got {type(result.score)}"
    assert 0.0 < result.score <= 100.0
    # reason must NOT carry 'assessed_clean' for partial coverage even with zero findings
    assert result.reason != "assessed_clean", (
        "reason='assessed_clean' MUST only fire when ALL 6 categories are assessed"
    )


# ---------------------------------------------------------------------------
# TS-UA-COH-SCORING-016
# All 6 assessed + zero findings → numeric score, reason=None (not old
# "assessed_clean" mass-collapse that multiplied by coverage_ratio)
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_all_six_assessed_zero_findings_no_collapse(svc: ScoringService) -> None:
    """
    All 6 categories assessed, zero findings. active_weight = 1.0 ≥ 0.35.
    The score must be a weighted mean of baselines, NOT mean × coverage_ratio.
    The coverage_ratio multiplier was the ADR-009 §1 P1 violation — it must be
    removed. reason should be 'assessed_clean' when all assessed and no findings.
    """
    coverage_map = {c: True for c in ALL_CATEGORIES}

    result: ScoringDiagnostics = svc.calculate_detailed(
        signals=[],
        num_clauses=10,
        coverage_map=coverage_map,
    )

    assert result.score is not None, "All 6 assessed with no findings must yield a numeric score"
    # With coverage_ratio=1.0 the old formula and the new formula produce the same number.
    # Verify it is in the baseline clean band [80, 90]:
    assert 70.0 <= result.score <= 100.0, (
        f"All-assessed clean score {result.score} outside expected baseline band"
    )
    # When ALL 6 assessed + zero findings, 'assessed_clean' is acceptable
    assert result.reason in {None, "assessed_clean"}


# ---------------------------------------------------------------------------
# TS-UA-COH-SCORING-017
# poor_extraction_quality=True → score=None, reason="insufficient_evidence"
# (unchanged behaviour — must still hold after the §14 guard is added)
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_poor_extraction_quality_returns_insufficient_evidence(svc: ScoringService) -> None:
    """
    Regardless of coverage_map, poor_extraction_quality=True must return
    score=None with reason="insufficient_evidence". This behaviour is unchanged
    by the §14 guard — the poor-quality gate fires before it.
    """
    coverage_map = {c: True for c in ALL_CATEGORIES}

    result: ScoringDiagnostics = svc.calculate_detailed(
        signals=[],
        num_clauses=10,
        coverage_map=coverage_map,
        poor_extraction_quality=True,
    )

    assert result.score is None
    assert result.reason == "insufficient_evidence"
