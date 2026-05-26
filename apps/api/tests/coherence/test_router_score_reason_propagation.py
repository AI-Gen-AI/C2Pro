"""
TDD RED tests — score_reason propagation from scoring engine through router models.

When the v1 engine returns score=None with reason="insufficient_active_weight",
that reason MUST survive all the way into EnrichedCoherenceResult and DashboardSummary.

Suite IDs: TS-UA-COH-ROUTER-021, TS-UA-COH-ROUTER-022
"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.coherence.domain.v2_constants import SCORE_VERSION_V1
from src.coherence.models import DashboardSummary, EnrichedCoherenceResult


# ---------------------------------------------------------------------------
# TS-UA-COH-ROUTER-021
# EnrichedCoherenceResult.score_reason survives into the JSON response
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_enriched_result_carries_score_reason() -> None:
    """
    EnrichedCoherenceResult constructed with overall_score=None and
    score_reason="insufficient_active_weight" must serialise those values
    without coercion. No '?? 0' or 'or 0' must flatten score to zero.
    """
    result = EnrichedCoherenceResult(
        overall_score=None,
        score_reason="insufficient_active_weight",
        score_missing_dimensions=["BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"],
        score_version=SCORE_VERSION_V1,
    )

    serialised = result.model_dump()

    assert serialised["overall_score"] is None, (
        f"overall_score must remain None; got {serialised['overall_score']}"
    )
    assert serialised["score_reason"] == "insufficient_active_weight", (
        f"score_reason lost in serialisation; got {serialised['score_reason']!r}"
    )
    assert serialised["score_missing_dimensions"] == [
        "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"
    ]


# ---------------------------------------------------------------------------
# TS-UA-COH-ROUTER-022
# DashboardSummary carries score_reason + null coherence_score
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_dashboard_summary_propagates_null_score_and_reason() -> None:
    """
    DashboardSummary must carry coherence_score=None and
    score_reason="insufficient_active_weight" when constructed from a
    partial-coverage CoherenceResult. This validates that the router does
    NOT substitute 0 for None anywhere in the assignment chain.
    """
    summary = DashboardSummary(
        project_id="proj-001",
        tenant_id="tenant-001",
        global_score=None,
        coherence_score=None,
        sub_scores={
            "SCOPE": 90,
            "BUDGET": None,
            "TIME": None,
            "TECHNICAL": None,
            "LEGAL": None,
            "QUALITY": None,
        },
        weights_used={c: 1 / 6 for c in ("SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY")},
        alert_count=0,
        document_count=2,
        score_version=SCORE_VERSION_V1,
        score_reason="insufficient_active_weight",
        score_missing_dimensions=["BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"],
        last_updated=datetime.now(UTC),
    )

    serialised = summary.model_dump()

    assert serialised["coherence_score"] is None, (
        f"coherence_score must be None; got {serialised['coherence_score']}"
    )
    assert serialised["global_score"] is None, (
        f"global_score must be None; got {serialised['global_score']}"
    )
    assert serialised["score_reason"] == "insufficient_active_weight"
