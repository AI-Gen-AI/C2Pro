"""
TDD RED tests — Phase B adapter partial-coverage fix.

The current adapt_v1_dashboard() implementation has two bugs:
1. It hardcodes active_weight=1.0 for any non-empty sub_scores dict,
   ignoring the real per-category weights and null values.
2. It echoes v1["coherence_score"] verbatim (e.g. 15) into GlobalV2,
   bypassing the §14 guard.

These tests assert the correct post-fix behaviour. They extend
apps/api/tests/coherence/test_v1_to_v2_adapter.py (existing file) via a
separate module to avoid merge conflicts.

Suite IDs: TS-UA-COH-V2-ADAPT-010 through TS-UA-COH-V2-ADAPT-012
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.coherence.adapters.v1_to_v2 import adapt_v1_dashboard
from src.coherence.application.dtos.coherence_v2_dtos import CategoryStatus
from src.coherence.domain.v2_constants import MIN_ACTIVE_WEIGHT, SCORE_VERSION_V1


def _project_id() -> object:
    return uuid4()


def _now() -> datetime:
    return datetime.now(UTC)


def _make_v1_partial(sub_scores: dict) -> dict:
    """Build a minimal v1 payload with the given sub_scores."""
    return {
        "project_id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "coherence_score": 15,        # the buggy v1 number — must NOT be echoed
        "global_score": 15,
        "sub_scores": sub_scores,
        "weights_used": dict.fromkeys(("SCOPE", "BUDGET", "QUALITY", "TECHNICAL", "LEGAL", "TIME"), 1 / 6),
        "alert_count": 0,
        "document_count": 2,
        "methodology_version": "v1",
        "score_version": SCORE_VERSION_V1,
        "score_reason": None,
        "score_missing_dimensions": [],
        "last_updated": None,
    }


# ---------------------------------------------------------------------------
# TS-UA-COH-V2-ADAPT-010
# SCOPE-only: 5 nulls + 1 numeric → 5 INSUFFICIENT_EVIDENCE + 1 SCORED
# global.coherence_score must be None (active_weight ≈ 0.167 < 0.35)
# Must NOT echo the v1 coherence_score=15
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_adapt_scope_only_yields_null_global_score() -> None:
    """
    adapt_v1_dashboard with only SCOPE scored (others None):
    - 5 categories → CategoryStatus.INSUFFICIENT_EVIDENCE, coherence_score=None
    - 1 category  → CategoryStatus.SCORED
    - global.coherence_score must be None (active_weight < MIN_ACTIVE_WEIGHT)
    - global.status must be "insufficient_active_weight"
    - MUST NOT echo v1["coherence_score"] = 15
    """
    sub_scores = {
        "SCOPE": 90,
        "BUDGET": None,
        "TIME": None,
        "TECHNICAL": None,
        "LEGAL": None,
        "QUALITY": None,
    }
    v1 = _make_v1_partial(sub_scores)

    payload = adapt_v1_dashboard(v1, project_id=_project_id(), generated_at=_now())

    # Global score must be None — must not echo 15
    assert payload.global_.coherence_score is None, (
        f"global.coherence_score must be None for SCOPE-only; got {payload.global_.coherence_score}. "
        "The adapter must NOT echo the buggy v1 score."
    )
    assert payload.global_.status == "insufficient_active_weight", (
        f"global.status must be 'insufficient_active_weight'; got {payload.global_.status!r}"
    )

    # Category classification
    scored = [c for c in payload.categories if c.status == CategoryStatus.SCORED]
    insufficient = [c for c in payload.categories if c.status == CategoryStatus.INSUFFICIENT_EVIDENCE]
    assert len(scored) == 1, f"Expected 1 SCORED category; got {len(scored)}"
    assert len(insufficient) == 5, f"Expected 5 INSUFFICIENT_EVIDENCE; got {len(insufficient)}"

    # Null categories must carry null coherence_score
    for cat in insufficient:
        assert cat.coherence_score is None, (
            f"INSUFFICIENT_EVIDENCE category {cat.category} must have None score"
        )

    # active_weight must be real (≈ 0.167), not hardcoded 1.0
    assert payload.global_.active_weight < MIN_ACTIVE_WEIGHT, (
        f"active_weight {payload.global_.active_weight} must be < MIN_ACTIVE_WEIGHT={MIN_ACTIVE_WEIGHT}"
    )


# ---------------------------------------------------------------------------
# TS-UA-COH-V2-ADAPT-011
# All 6 sub_scores numeric → unchanged behaviour (status="scored", weight≈1.0)
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_adapt_all_numeric_unchanged_behaviour() -> None:
    """
    When all 6 sub_scores are numeric, the adapter must still produce
    status="scored" or "partial" with a numeric coherence_score.
    The score must NOT be the raw v1 number (15 baked in _make_v1_partial).
    It should be the weighted mean of the provided sub_scores.
    """
    sub_scores = {
        "SCOPE": 90,
        "BUDGET": 80,
        "QUALITY": 85,
        "TECHNICAL": 70,
        "LEGAL": 95,
        "TIME": 75,
    }
    v1 = _make_v1_partial(sub_scores)
    # Override coherence_score to something that differs from the weighted mean
    # so we can detect if it's being echoed:
    v1["coherence_score"] = 15  # clearly different from the real weighted mean

    payload = adapt_v1_dashboard(v1, project_id=_project_id(), generated_at=_now())

    assert payload.global_.coherence_score is not None, (
        "All-numeric sub_scores must produce a numeric global score"
    )
    # All categories must be SCORED
    assert all(c.status == CategoryStatus.SCORED for c in payload.categories), (
        "All numeric sub_scores must yield SCORED categories"
    )
    # global.status must be scored
    assert payload.global_.status in {"scored", "partial"}, (
        f"Unexpected status: {payload.global_.status!r}"
    )
    # The computed score must be close to the weighted mean (not the bogus 15)
    expected_mean = sum(sub_scores.values()) / 6  # 495/6 = 82.5
    assert payload.global_.coherence_score == pytest.approx(expected_mean, rel=0.05), (
        f"Expected weighted mean ≈ {expected_mean}; got {payload.global_.coherence_score}"
    )


# ---------------------------------------------------------------------------
# TS-UA-COH-V2-ADAPT-012
# SCOPE + BUDGET + QUALITY scored (active_weight = 3/6 = 0.50 ≥ 0.35)
# → status="partial", numeric coherence_score (weighted mean of the 3)
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_adapt_three_scored_yields_partial_numeric() -> None:
    """
    With SCOPE(90) + BUDGET(80) + QUALITY(85) scored and others None:
    active_weight = 3/6 = 0.50 ≥ MIN_ACTIVE_WEIGHT=0.35.
    Must produce status="partial" and a numeric weighted mean.
    Must NOT produce None or echo v1 coherence_score=15.
    """
    sub_scores = {
        "SCOPE": 90,
        "BUDGET": 80,
        "QUALITY": 85,
        "TIME": None,
        "TECHNICAL": None,
        "LEGAL": None,
    }
    v1 = _make_v1_partial(sub_scores)

    payload = adapt_v1_dashboard(v1, project_id=_project_id(), generated_at=_now())

    assert payload.global_.coherence_score is not None, (
        "active_weight=0.50 is ≥ MIN_ACTIVE_WEIGHT — must produce numeric score"
    )
    # status must be "partial" (not all 6 scored)
    assert payload.global_.status in {"partial", "scored"}, (
        f"Expected 'partial' for 3/6 scored; got {payload.global_.status!r}"
    )
    # weighted mean of the 3 scored categories (each weight 1/6)
    expected = (90 + 80 + 85) / 3  # ≈ 85.0
    assert payload.global_.coherence_score == pytest.approx(expected, rel=0.05), (
        f"Expected weighted mean ≈ {expected}; got {payload.global_.coherence_score}"
    )
    # MUST NOT be the v1 echo (15)
    assert payload.global_.coherence_score != pytest.approx(15.0, abs=1.0), (
        "Adapter must NOT echo the v1 coherence_score of 15"
    )

    # Verify category classification
    insufficient = [c for c in payload.categories if c.status == CategoryStatus.INSUFFICIENT_EVIDENCE]
    scored_cats = [c for c in payload.categories if c.status == CategoryStatus.SCORED]
    assert len(insufficient) == 3
    assert len(scored_cats) == 3
