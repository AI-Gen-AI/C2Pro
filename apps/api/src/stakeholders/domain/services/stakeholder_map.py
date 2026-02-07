"""
Stakeholder map data generation.

Refers to Suite ID: TS-UD-STK-MAP-001.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from uuid import UUID

from src.stakeholders.domain.models import StakeholderQuadrant


@dataclass(frozen=True)
class MapPoint:
    """Represents a stakeholder position in the power-interest map."""

    stakeholder_id: UUID
    label: str
    quadrant: StakeholderQuadrant
    x: float
    y: float


def _quadrant_anchor(quadrant: StakeholderQuadrant) -> tuple[float, float]:
    if quadrant == StakeholderQuadrant.KEY_PLAYER:
        return 0.75, 0.75
    if quadrant == StakeholderQuadrant.KEEP_SATISFIED:
        return 0.75, 0.25
    if quadrant == StakeholderQuadrant.KEEP_INFORMED:
        return 0.25, 0.75
    return 0.25, 0.25


def generate_stakeholder_map(
    stakeholders: Iterable[dict],
) -> list[MapPoint]:
    """Generate map points from stakeholder payloads."""
    points: list[MapPoint] = []
    for stakeholder in stakeholders:
        if not isinstance(stakeholder, dict):
            continue
        stakeholder_id = stakeholder.get("id")
        name = stakeholder.get("name")
        quadrant = stakeholder.get("quadrant")
        if not isinstance(stakeholder_id, UUID):
            continue
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(quadrant, StakeholderQuadrant):
            continue
        x, y = _quadrant_anchor(quadrant)
        points.append(
            MapPoint(
                stakeholder_id=stakeholder_id,
                label=name,
                quadrant=quadrant,
                x=x,
                y=y,
            )
        )
    return points
