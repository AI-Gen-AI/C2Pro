"""TS-UD-HEALTH-018-003 - Documentation health scorer honest-null behavior."""

from __future__ import annotations

from src.analysis.domain.documentation_health import DocumentationHealthSignal
from src.health.application.documentation_scorer import score_documentation_dimension
from src.health.domain.health_vector import HealthBand, HealthDimension, HealthNullReason


def test_missing_documentation_signal_is_unknown_not_green() -> None:
    signal = score_documentation_dimension(None)

    assert signal.dimension is HealthDimension.DOCUMENTATION
    assert signal.score is None
    assert signal.band is HealthBand.UNKNOWN
    assert signal.null_reason is HealthNullReason.INSUFFICIENT_EVIDENCE
    assert "no pipeline documentation-health signal" in signal.missing_data
    assert signal.evidence == []


def test_all_ok_documentation_signal_scores_high_with_evidence() -> None:
    signal = score_documentation_dimension(
        DocumentationHealthSignal(
            total_count=8,
            failed_count=0,
            degraded_count=0,
            skipped_count=0,
        )
    )

    assert signal.score == 95
    assert signal.band is HealthBand.HEALTHY
    assert signal.confidence == 1
    assert signal.evidence


def test_failed_documentation_nodes_cap_below_healthy() -> None:
    signal = score_documentation_dimension(
        DocumentationHealthSignal(
            total_count=10,
            failed_count=1,
            degraded_count=0,
            skipped_count=0,
            failed_nodes=["N8"],
        )
    )

    assert signal.score == 79
    assert signal.band is HealthBand.WATCH
    assert signal.evidence
    assert "failed nodes present" in signal.missing_data


def test_degraded_heavy_documentation_signal_lowers_band() -> None:
    signal = score_documentation_dimension(
        DocumentationHealthSignal(
            total_count=4,
            failed_count=0,
            degraded_count=4,
            skipped_count=0,
            degraded_nodes=["N4", "N8", "N11", "N17"],
        )
    )

    assert signal.score == 55
    assert signal.band is HealthBand.AT_RISK
    assert signal.evidence
