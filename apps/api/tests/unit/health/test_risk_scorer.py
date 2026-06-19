"""TS-UD-HEALTH-018-002 - Risk health scorer honest-null behavior."""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.analysis.domain.contracts import RiskItem, Severity
from src.evidence.domain.runtime_trust import EvidenceRef, EvidenceTier
from src.health.application.risk_scorer import score_risk_dimension
from src.health.domain.health_vector import HealthBand, HealthDimension, HealthNullReason
from src.project_state.domain.entities import ProjectRisk


def _evidence(ref_id: str = "risk-1") -> EvidenceRef:
    return EvidenceRef(
        ref_id=ref_id,
        source="risk_assessment",
        tier=EvidenceTier.VERIFIED,
        locator=ref_id,
    )


def _risk(severity: Severity, ref_id: str) -> ProjectRisk:
    return ProjectRisk(
        entity_id=uuid4(),
        evidence=[_evidence(ref_id)],
        payload=RiskItem(
            title=f"{severity.value} risk",
            description="Risk description",
            severity=severity,
        ),
    )


def test_risk_assessment_not_run_is_unknown_not_green() -> None:
    signal = score_risk_dimension([], assessment_ran=False)

    assert signal.dimension is HealthDimension.RISK
    assert signal.score is None
    assert signal.band is HealthBand.UNKNOWN
    assert signal.null_reason is HealthNullReason.INSUFFICIENT_EVIDENCE
    assert "risk assessment did not run" in signal.missing_data
    assert signal.confidence == 0


def test_successful_assessment_with_zero_risks_is_clean_signal_with_evidence() -> None:
    signal = score_risk_dimension([], assessment_ran=True, extraction_quality=0.85)

    assert signal.score == 90
    assert signal.band is HealthBand.HEALTHY
    assert signal.confidence == pytest.approx(0.85)
    assert signal.evidence
    assert signal.evidence[0].ref_id == "risk-assessment-clean"


def test_high_risks_reduce_score_and_confidence_tracks_extraction_quality() -> None:
    signal = score_risk_dimension(
        [
            _risk(Severity.HIGH, "risk-1"),
            _risk(Severity.HIGH, "risk-2"),
            _risk(Severity.HIGH, "risk-3"),
        ],
        assessment_ran=True,
        extraction_quality=0.6,
    )

    assert signal.score == 20
    assert signal.band is HealthBand.CRITICAL
    assert signal.confidence == pytest.approx(0.6)
    assert len(signal.evidence) == 3


def test_poor_extraction_quality_is_unknown_not_clean() -> None:
    signal = score_risk_dimension([], assessment_ran=True, extraction_quality=0.2)

    assert signal.score is None
    assert signal.band is HealthBand.UNKNOWN
    assert signal.null_reason is HealthNullReason.INSUFFICIENT_EVIDENCE
    assert "poor extraction quality" in signal.missing_data
