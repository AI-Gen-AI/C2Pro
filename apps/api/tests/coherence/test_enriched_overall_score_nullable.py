"""
TDD RED test — EnrichedCoherenceResult.overall_score must accept None.

ADR-009 spec §3.1: overall_score should be float | None. The current model
has 'float' non-nullable, causing a ValidationError when score is None.

Suite ID: TS-UA-COH-MODEL-031
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.coherence.domain.v2_constants import SCORE_VERSION_V1
from src.coherence.models import EnrichedCoherenceResult


@pytest.mark.unit
def test_enriched_result_overall_score_accepts_none() -> None:
    """
    EnrichedCoherenceResult(overall_score=None, ...) MUST NOT raise
    ValidationError. The field must be declared float | None.
    This is the primary contract regression for the ECOA v2 hotfix.
    """
    try:
        result = EnrichedCoherenceResult(
            overall_score=None,
            score_reason="insufficient_active_weight",
            score_version=SCORE_VERSION_V1,
        )
    except ValidationError as exc:
        pytest.fail(
            f"EnrichedCoherenceResult raised ValidationError for overall_score=None: {exc}"
        )

    assert result.overall_score is None
    assert result.score_reason == "insufficient_active_weight"


@pytest.mark.unit
def test_enriched_result_overall_score_accepts_float() -> None:
    """Regression: numeric scores must still be accepted after the type change."""
    result = EnrichedCoherenceResult(
        overall_score=72.5,
        score_version=SCORE_VERSION_V1,
    )
    assert result.overall_score == pytest.approx(72.5)


@pytest.mark.unit
def test_enriched_result_overall_score_rejects_negative() -> None:
    """Values < 0.0 must still be rejected (ge=0.0 constraint unchanged)."""
    with pytest.raises(ValidationError):
        EnrichedCoherenceResult(
            overall_score=-1.0,
            score_version=SCORE_VERSION_V1,
        )
