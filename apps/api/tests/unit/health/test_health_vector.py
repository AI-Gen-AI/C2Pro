"""TS-UD-HEALTH-018-001 - Health vector contract invariants."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.evidence.domain.runtime_trust import EvidenceRef, EvidenceTier
from src.health.domain.health_vector import (
    HealthBand,
    HealthDimension,
    HealthNullReason,
    HealthSignal,
    HealthTrend,
    HealthVector,
    band_for_score,
)


def _evidence() -> EvidenceRef:
    return EvidenceRef(
        ref_id="clause-5.2",
        source="contract",
        tier=EvidenceTier.VERIFIED,
        locator="5.2",
    )


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (None, HealthBand.UNKNOWN),
        (0, HealthBand.CRITICAL),
        (39, HealthBand.CRITICAL),
        (40, HealthBand.AT_RISK),
        (59, HealthBand.AT_RISK),
        (60, HealthBand.WATCH),
        (79, HealthBand.WATCH),
        (80, HealthBand.HEALTHY),
        (100, HealthBand.HEALTHY),
    ],
)
def test_band_for_score_boundaries(score: float | None, expected: HealthBand) -> None:
    assert band_for_score(score) == expected


def test_non_null_score_requires_evidence_or_confidence_and_matching_band() -> None:
    with pytest.raises(ValidationError):
        HealthSignal(
            dimension=HealthDimension.CONTRACT,
            score=85,
            band=HealthBand.HEALTHY,
            confidence=0,
        )

    signal = HealthSignal(
        dimension=HealthDimension.CONTRACT,
        score=85,
        band=HealthBand.HEALTHY,
        confidence=0,
        evidence=[_evidence()],
    )

    assert signal.band is HealthBand.HEALTHY

    with pytest.raises(ValidationError):
        HealthSignal(
            dimension=HealthDimension.CONTRACT,
            score=85,
            band=HealthBand.WATCH,
            confidence=0.8,
            evidence=[_evidence()],
        )


def test_null_score_requires_unknown_band_and_null_reason() -> None:
    with pytest.raises(ValidationError):
        HealthSignal(
            dimension=HealthDimension.RISK,
            score=None,
            band=HealthBand.UNKNOWN,
            confidence=0,
        )

    with pytest.raises(ValidationError):
        HealthSignal(
            dimension=HealthDimension.RISK,
            score=None,
            band=HealthBand.HEALTHY,
            confidence=0,
            null_reason=HealthNullReason.INSUFFICIENT_EVIDENCE,
        )

    signal = HealthSignal(
        dimension=HealthDimension.RISK,
        score=None,
        band=HealthBand.UNKNOWN,
        confidence=0,
        null_reason=HealthNullReason.INSUFFICIENT_EVIDENCE,
        missing_data=["risk assessment did not run"],
    )

    assert signal.band is HealthBand.UNKNOWN
    assert signal.null_reason is HealthNullReason.INSUFFICIENT_EVIDENCE


def test_health_contracts_are_frozen_and_extra_forbidden() -> None:
    signal = HealthSignal(
        dimension=HealthDimension.DOCUMENTATION,
        score=65,
        band=HealthBand.WATCH,
        confidence=0.4,
        evidence=[_evidence()],
        trend=HealthTrend.UNKNOWN,
    )
    vector = HealthVector(
        project_id=uuid4(),
        tenant_id=uuid4(),
        dimensions=[signal],
        computed_at=datetime.now(UTC).replace(tzinfo=None),
    )

    with pytest.raises(ValidationError):
        signal.confidence = 0.7  # type: ignore[misc]

    with pytest.raises(ValidationError):
        HealthSignal(
            dimension=HealthDimension.DOCUMENTATION,
            score=65,
            band=HealthBand.WATCH,
            confidence=0.4,
            evidence=[_evidence()],
            unexpected=True,
        )

    with pytest.raises(ValidationError):
        vector.composite_score = 90  # type: ignore[misc]
