"""
Quadrant assignment service wrapper.

Refers to Suite ID: TS-UD-STK-CLS-001.
"""

from __future__ import annotations

from src.stakeholders.domain.models import InterestLevel, PowerLevel, StakeholderQuadrant
from src.stakeholders.domain.quadrant_assignment import QuadrantAssigner


def assign_quadrant(
    power_level: PowerLevel,
    interest_level: InterestLevel,
) -> StakeholderQuadrant:
    """Return the Mendelow quadrant for given power/interest levels."""
    return QuadrantAssigner().assign(power_level, interest_level).quadrant
