"""
RED tests — canonical score_version enforcement across all Coherence models.

Phase F: Replace legacy score_version strings with closed 2-value enum.
Canonical values: "coherence-v1" and "coherence-v2" only.

Suite ID: TS-ECOA-V2-PHASE-F-001
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.coherence.domain.v2_constants import (
    SCORE_VERSION_V1,
    SCORE_VERSION_V2,
    SCORE_VERSION_VALUES,
)
from src.coherence.models import (
    CoherenceResult,
    DashboardSummary,
    EnrichedCoherenceResult,
)

# ---------------------------------------------------------------------------
# Constants presence and values
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_score_version_v1_constant_is_canonical() -> None:
    """SCORE_VERSION_V1 must equal 'coherence-v1'."""
    assert SCORE_VERSION_V1 == "coherence-v1"


@pytest.mark.unit
def test_score_version_v2_constant_is_canonical() -> None:
    """SCORE_VERSION_V2 must equal 'coherence-v2'."""
    assert SCORE_VERSION_V2 == "coherence-v2"


@pytest.mark.unit
def test_score_version_values_contains_both() -> None:
    """SCORE_VERSION_VALUES must contain exactly both canonical strings."""
    assert set(SCORE_VERSION_VALUES) == {"coherence-v1", "coherence-v2"}


# ---------------------------------------------------------------------------
# CoherenceResult
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_coherence_result_accepts_v1() -> None:
    """CoherenceResult(score_version='coherence-v1') must succeed."""
    result = CoherenceResult(
        overall_score=75.0,
        alerts=[],
        score_version=SCORE_VERSION_V1,
    )
    assert result.score_version == "coherence-v1"


@pytest.mark.unit
def test_coherence_result_accepts_v2() -> None:
    """CoherenceResult(score_version='coherence-v2') must succeed."""
    result = CoherenceResult(
        overall_score=80.0,
        alerts=[],
        score_version=SCORE_VERSION_V2,
    )
    assert result.score_version == "coherence-v2"


@pytest.mark.unit
def test_coherence_result_rejects_v0_flag_based() -> None:
    """CoherenceResult(score_version='v0_flag_based') must raise ValidationError."""
    with pytest.raises(ValidationError):
        CoherenceResult(
            overall_score=75.0,
            alerts=[],
            score_version="v0_flag_based",
        )


@pytest.mark.unit
def test_coherence_result_rejects_v1_exponential_decay() -> None:
    """CoherenceResult(score_version='v1_exponential_decay') must raise ValidationError."""
    with pytest.raises(ValidationError):
        CoherenceResult(
            overall_score=75.0,
            alerts=[],
            score_version="v1_exponential_decay",
        )


@pytest.mark.unit
def test_coherence_result_rejects_bare_v1() -> None:
    """CoherenceResult(score_version='v1') must raise ValidationError."""
    with pytest.raises(ValidationError):
        CoherenceResult(
            overall_score=75.0,
            alerts=[],
            score_version="v1",
        )


# ---------------------------------------------------------------------------
# EnrichedCoherenceResult
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_enriched_coherence_result_accepts_v1() -> None:
    """EnrichedCoherenceResult(score_version='coherence-v1') must succeed."""
    result = EnrichedCoherenceResult(
        overall_score=70.0,
        score_version=SCORE_VERSION_V1,
    )
    assert result.score_version == "coherence-v1"


@pytest.mark.unit
def test_enriched_coherence_result_accepts_v2() -> None:
    """EnrichedCoherenceResult(score_version='coherence-v2') must succeed."""
    result = EnrichedCoherenceResult(
        overall_score=None,
        score_version=SCORE_VERSION_V2,
    )
    assert result.score_version == "coherence-v2"


@pytest.mark.unit
def test_enriched_coherence_result_rejects_v0_flag_based() -> None:
    """EnrichedCoherenceResult(score_version='v0_flag_based') must raise ValidationError."""
    with pytest.raises(ValidationError):
        EnrichedCoherenceResult(
            overall_score=72.5,
            score_version="v0_flag_based",
        )


@pytest.mark.unit
def test_enriched_coherence_result_rejects_v1_exponential_decay() -> None:
    """EnrichedCoherenceResult(score_version='v1_exponential_decay') must raise ValidationError."""
    with pytest.raises(ValidationError):
        EnrichedCoherenceResult(
            overall_score=72.5,
            score_version="v1_exponential_decay",
        )


# ---------------------------------------------------------------------------
# DashboardSummary
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_dashboard_summary_accepts_v1() -> None:
    """DashboardSummary(score_version='coherence-v1') must succeed."""
    from datetime import UTC, datetime
    from uuid import uuid4

    summary = DashboardSummary(
        project_id=str(uuid4()),
        tenant_id=str(uuid4()),
        global_score=80,
        coherence_score=80.0,
        sub_scores={},
        weights_used={},
        alert_count=0,
        document_count=1,
        last_updated=datetime.now(UTC),
        score_version=SCORE_VERSION_V1,
    )
    assert summary.score_version == "coherence-v1"


@pytest.mark.unit
def test_dashboard_summary_accepts_v2() -> None:
    """DashboardSummary(score_version='coherence-v2') must succeed."""
    from datetime import UTC, datetime
    from uuid import uuid4

    summary = DashboardSummary(
        project_id=str(uuid4()),
        tenant_id=str(uuid4()),
        global_score=80,
        coherence_score=80.0,
        sub_scores={},
        weights_used={},
        alert_count=0,
        document_count=1,
        last_updated=datetime.now(UTC),
        score_version=SCORE_VERSION_V2,
    )
    assert summary.score_version == "coherence-v2"


@pytest.mark.unit
def test_dashboard_summary_accepts_none_score_version() -> None:
    """DashboardSummary(score_version=None) is still allowed (unknown state)."""
    from datetime import UTC, datetime
    from uuid import uuid4

    summary = DashboardSummary(
        project_id=str(uuid4()),
        tenant_id=str(uuid4()),
        global_score=80,
        coherence_score=80.0,
        sub_scores={},
        weights_used={},
        alert_count=0,
        document_count=1,
        last_updated=datetime.now(UTC),
        score_version=None,
    )
    assert summary.score_version is None


@pytest.mark.unit
def test_dashboard_summary_rejects_v0_flag_based() -> None:
    """DashboardSummary(score_version='v0_flag_based') must raise ValidationError."""
    from datetime import UTC, datetime
    from uuid import uuid4

    with pytest.raises(ValidationError):
        DashboardSummary(
            project_id=str(uuid4()),
            tenant_id=str(uuid4()),
            global_score=80,
            coherence_score=80.0,
            sub_scores={},
            weights_used={},
            alert_count=0,
            document_count=1,
            last_updated=datetime.now(UTC),
            score_version="v0_flag_based",
        )


@pytest.mark.unit
def test_dashboard_summary_rejects_v1_exponential_decay() -> None:
    """DashboardSummary(score_version='v1_exponential_decay') must raise ValidationError."""
    from datetime import UTC, datetime
    from uuid import uuid4

    with pytest.raises(ValidationError):
        DashboardSummary(
            project_id=str(uuid4()),
            tenant_id=str(uuid4()),
            global_score=80,
            coherence_score=80.0,
            sub_scores={},
            weights_used={},
            alert_count=0,
            document_count=1,
            last_updated=datetime.now(UTC),
            score_version="v1_exponential_decay",
        )
