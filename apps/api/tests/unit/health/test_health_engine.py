"""TS-UD-HEALTH-018-005 - HealthEngine composite and trend behavior."""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.evidence.domain.runtime_trust import EvidenceRef, EvidenceTier
from src.health.application.health_engine import assemble_health_vector, composite_trend
from src.health.domain.health_vector import (
    HealthBand,
    HealthDimension,
    HealthNullReason,
    HealthSignal,
    HealthTrend,
)


def _evidence(ref_id: str) -> EvidenceRef:
    return EvidenceRef(
        ref_id=ref_id,
        source="health_test",
        tier=EvidenceTier.VERIFIED,
        locator=ref_id,
    )


def _scored(
    dimension: HealthDimension,
    score: float,
    confidence: float,
    ref_id: str,
) -> HealthSignal:
    return HealthSignal(
        dimension=dimension,
        score=score,
        band=HealthBand.HEALTHY if score >= 80 else HealthBand.WATCH,
        confidence=confidence,
        evidence=[_evidence(ref_id)],
    )


def _unknown(dimension: HealthDimension) -> HealthSignal:
    return HealthSignal(
        dimension=dimension,
        score=None,
        band=HealthBand.UNKNOWN,
        confidence=0,
        null_reason=HealthNullReason.INSUFFICIENT_EVIDENCE,
        missing_data=["missing input"],
    )


def test_composite_is_confidence_weighted_over_non_null_dimensions_only() -> None:
    project_id = uuid4()
    tenant_id = uuid4()
    vector = assemble_health_vector(
        project_id,
        tenant_id,
        signals=[
            _scored(HealthDimension.CONTRACT, 80, 0.75, "contract"),
            _scored(HealthDimension.RISK, 60, 0.25, "risk"),
            _unknown(HealthDimension.DOCUMENTATION),
        ],
        prior_composite=None,
    )

    assert vector.composite_score == pytest.approx(75)
    assert vector.composite_band is HealthBand.WATCH
    assert vector.composite_trend is HealthTrend.UNKNOWN
    assert [signal.dimension for signal in vector.dimensions] == [
        HealthDimension.CONTRACT,
        HealthDimension.RISK,
        HealthDimension.DOCUMENTATION,
    ]


def test_all_null_dimensions_keep_composite_unknown_not_green() -> None:
    vector = assemble_health_vector(
        uuid4(),
        uuid4(),
        signals=[
            _unknown(HealthDimension.CONTRACT),
            _unknown(HealthDimension.RISK),
        ],
        prior_composite=90,
    )

    assert vector.composite_score is None
    assert vector.composite_band is HealthBand.UNKNOWN


def test_green_composite_requires_real_scored_dimensions_with_evidence() -> None:
    vector = assemble_health_vector(
        uuid4(),
        uuid4(),
        signals=[_scored(HealthDimension.CONTRACT, 90, 1.0, "contract")],
        prior_composite=None,
    )

    assert vector.composite_score == 90
    assert vector.composite_band is HealthBand.HEALTHY
    assert vector.dimensions[0].evidence


def test_composite_trend_from_prior_snapshot_score() -> None:
    assert composite_trend(current=None, prior=None) is HealthTrend.UNKNOWN
    assert composite_trend(current=80, prior=None) is HealthTrend.UNKNOWN
    assert composite_trend(current=81, prior=80) is HealthTrend.UP
    assert composite_trend(current=79, prior=80) is HealthTrend.DOWN
    assert composite_trend(current=80.004, prior=80) is HealthTrend.FLAT


@pytest.mark.parametrize(
    ("prior", "expected"),
    [
        (70, HealthTrend.UP),
        (90, HealthTrend.DOWN),
        (80.004, HealthTrend.FLAT),
        (None, HealthTrend.UNKNOWN),
    ],
)
def test_assemble_health_vector_surfaces_composite_trend(
    prior: float | None,
    expected: HealthTrend,
) -> None:
    vector = assemble_health_vector(
        uuid4(),
        uuid4(),
        signals=[_scored(HealthDimension.CONTRACT, 80, 1.0, "contract")],
        prior_composite=prior,
    )

    assert vector.composite_trend is expected
