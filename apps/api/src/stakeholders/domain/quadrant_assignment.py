"""
Stakeholder quadrant assignment rules.

Refers to Suite ID: TS-UD-STK-CLS-002.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.stakeholders.domain.models import InterestLevel, PowerLevel, StakeholderQuadrant


@dataclass(frozen=True)
class QuadrantAssignment:
    """Assignment result with rationale."""

    quadrant: StakeholderQuadrant
    rationale: str


class QuadrantAssigner:
    """Assigns a stakeholder to a Mendelow quadrant."""

    def assign(
        self,
        power_level: PowerLevel,
        interest_level: InterestLevel,
        has_critical_clause: bool = False,
        is_executive_sponsor: bool = False,
    ) -> QuadrantAssignment:
        if has_critical_clause:
            return QuadrantAssignment(
                quadrant=StakeholderQuadrant.KEY_PLAYER,
                rationale="Critical contractual clause involvement.",
            )

        if is_executive_sponsor:
            return QuadrantAssignment(
                quadrant=StakeholderQuadrant.KEEP_SATISFIED,
                rationale="Executive sponsor requires proactive alignment.",
            )

        if power_level == PowerLevel.HIGH and interest_level == InterestLevel.HIGH:
            return QuadrantAssignment(StakeholderQuadrant.KEY_PLAYER, "High power and high interest.")
        if power_level == PowerLevel.HIGH and interest_level != InterestLevel.HIGH:
            return QuadrantAssignment(StakeholderQuadrant.KEEP_SATISFIED, "High power with lower interest.")
        if power_level != PowerLevel.HIGH and interest_level == InterestLevel.HIGH:
            return QuadrantAssignment(StakeholderQuadrant.KEEP_INFORMED, "Lower power with high interest.")
        return QuadrantAssignment(StakeholderQuadrant.MONITOR, "Low engagement and influence profile.")
