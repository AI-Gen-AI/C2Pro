"""
Stakeholder quadrant assignment tests.
"""

from src.stakeholders.domain.models import InterestLevel, PowerLevel, StakeholderQuadrant
from src.stakeholders.domain.quadrant_assignment import QuadrantAssigner


class TestQuadrantAssignment:
    """Refers to Suite ID: TS-UD-STK-CLS-002"""

    def test_001_high_power_high_interest_is_key_player(self) -> None:
        result = QuadrantAssigner().assign(PowerLevel.HIGH, InterestLevel.HIGH)
        assert result.quadrant == StakeholderQuadrant.KEY_PLAYER

    def test_002_high_power_low_interest_is_keep_satisfied(self) -> None:
        result = QuadrantAssigner().assign(PowerLevel.HIGH, InterestLevel.LOW)
        assert result.quadrant == StakeholderQuadrant.KEEP_SATISFIED

    def test_003_low_power_high_interest_is_keep_informed(self) -> None:
        result = QuadrantAssigner().assign(PowerLevel.LOW, InterestLevel.HIGH)
        assert result.quadrant == StakeholderQuadrant.KEEP_INFORMED

    def test_004_low_power_low_interest_is_monitor(self) -> None:
        result = QuadrantAssigner().assign(PowerLevel.LOW, InterestLevel.LOW)
        assert result.quadrant == StakeholderQuadrant.MONITOR

    def test_005_high_power_medium_interest_is_keep_satisfied(self) -> None:
        result = QuadrantAssigner().assign(PowerLevel.HIGH, InterestLevel.MEDIUM)
        assert result.quadrant == StakeholderQuadrant.KEEP_SATISFIED

    def test_006_medium_power_high_interest_is_keep_informed(self) -> None:
        result = QuadrantAssigner().assign(PowerLevel.MEDIUM, InterestLevel.HIGH)
        assert result.quadrant == StakeholderQuadrant.KEEP_INFORMED

    def test_007_medium_power_medium_interest_is_monitor(self) -> None:
        result = QuadrantAssigner().assign(PowerLevel.MEDIUM, InterestLevel.MEDIUM)
        assert result.quadrant == StakeholderQuadrant.MONITOR

    def test_008_critical_clause_override_promotes_to_key_player(self) -> None:
        result = QuadrantAssigner().assign(
            PowerLevel.MEDIUM,
            InterestLevel.HIGH,
            has_critical_clause=True,
        )
        assert result.quadrant == StakeholderQuadrant.KEY_PLAYER

    def test_009_executive_sponsor_override_promotes_to_keep_satisfied(self) -> None:
        result = QuadrantAssigner().assign(
            PowerLevel.LOW,
            InterestLevel.LOW,
            is_executive_sponsor=True,
        )
        assert result.quadrant == StakeholderQuadrant.KEEP_SATISFIED

    def test_010_assignment_returns_rationale(self) -> None:
        result = QuadrantAssigner().assign(PowerLevel.HIGH, InterestLevel.HIGH)
        assert result.rationale
