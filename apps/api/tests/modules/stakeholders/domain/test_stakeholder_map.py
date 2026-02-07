"""
Stakeholder map data tests.

Refers to Suite ID: TS-UD-STK-MAP-001.
"""

from __future__ import annotations

from uuid import uuid4

from src.stakeholders.domain.models import StakeholderQuadrant
from src.stakeholders.domain.services.stakeholder_map import MapPoint, generate_stakeholder_map


def test_001_generates_map_points_for_quadrants() -> None:
    stakeholders = [
        {
            "id": uuid4(),
            "name": "Stake A",
            "quadrant": StakeholderQuadrant.KEY_PLAYER,
        },
        {
            "id": uuid4(),
            "name": "Stake B",
            "quadrant": StakeholderQuadrant.KEEP_INFORMED,
        },
    ]

    points = generate_stakeholder_map(stakeholders)

    assert len(points) == 2
    assert all(isinstance(point, MapPoint) for point in points)
    assert points[0].label == "Stake A"
    assert points[1].label == "Stake B"


def test_002_assigns_coordinates_by_quadrant() -> None:
    stakeholders = [
        {
            "id": uuid4(),
            "name": "Stake A",
            "quadrant": StakeholderQuadrant.KEY_PLAYER,
        },
        {
            "id": uuid4(),
            "name": "Stake B",
            "quadrant": StakeholderQuadrant.MONITOR,
        },
    ]

    points = generate_stakeholder_map(stakeholders)

    key_player = next(point for point in points if point.quadrant == StakeholderQuadrant.KEY_PLAYER)
    monitor = next(point for point in points if point.quadrant == StakeholderQuadrant.MONITOR)

    assert key_player.x > 0.5
    assert key_player.y > 0.5
    assert monitor.x < 0.5
    assert monitor.y < 0.5
