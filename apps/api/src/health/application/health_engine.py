"""TS-UD-HEALTH-018-005 - Health vector assembly engine."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from src.health.domain.health_vector import (
    HealthBand,
    HealthSignal,
    HealthTrend,
    HealthVector,
    band_for_score,
)

_TREND_EPSILON = 0.01


def assemble_health_vector(
    project_id: UUID,
    tenant_id: UUID,
    *,
    signals: list[HealthSignal],
    prior_composite: float | None,
) -> HealthVector:
    """Assemble a project HealthVector from already honest-null dimension signals."""

    scored = [signal for signal in signals if signal.score is not None]
    if not scored:
        composite_score = None
        composite_band = HealthBand.UNKNOWN
    else:
        total_weight = sum(signal.confidence for signal in scored)
        if total_weight <= 0:
            total_weight = float(len(scored))
            composite_score = sum(float(signal.score) for signal in scored) / total_weight
        else:
            composite_score = (
                sum(float(signal.score) * signal.confidence for signal in scored) / total_weight
            )
        composite_band = band_for_score(composite_score)

    _ = composite_trend(composite_score, prior_composite)
    return HealthVector(
        project_id=project_id,
        tenant_id=tenant_id,
        dimensions=signals,
        composite_score=composite_score,
        composite_band=composite_band,
        computed_at=datetime.now(UTC).replace(tzinfo=None),
    )


def composite_trend(current: float | None, prior: float | None) -> HealthTrend:
    """Classify composite trend against the most recent prior snapshot composite."""

    if current is None or prior is None:
        return HealthTrend.UNKNOWN
    delta = current - prior
    if abs(delta) <= _TREND_EPSILON:
        return HealthTrend.FLAT
    if delta > 0:
        return HealthTrend.UP
    return HealthTrend.DOWN


__all__ = ["assemble_health_vector", "composite_trend"]
