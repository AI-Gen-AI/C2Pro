"""
Power/interest classification domain tests.
"""

from src.stakeholders.domain.models import InterestLevel, PowerLevel, StakeholderQuadrant
from src.stakeholders.domain.power_interest_classifier import (
    ClassificationSignals,
    PowerInterestClassifier,
)


class TestPowerInterestClassification:
    """Refers to Suite ID: TS-UD-STK-CLS-001"""

    def test_001_score_10_maps_to_high_power(self) -> None:
        result = PowerInterestClassifier().score_to_power_level(10)
        assert result == PowerLevel.HIGH

    def test_002_score_8_maps_to_high_power(self) -> None:
        result = PowerInterestClassifier().score_to_power_level(8)
        assert result == PowerLevel.HIGH

    def test_003_score_5_maps_to_medium_power(self) -> None:
        result = PowerInterestClassifier().score_to_power_level(5)
        assert result == PowerLevel.MEDIUM

    def test_004_score_4_maps_to_low_power(self) -> None:
        result = PowerInterestClassifier().score_to_power_level(4)
        assert result == PowerLevel.LOW

    def test_005_score_9_maps_to_high_interest(self) -> None:
        result = PowerInterestClassifier().score_to_interest_level(9)
        assert result == InterestLevel.HIGH

    def test_006_score_6_maps_to_medium_interest(self) -> None:
        result = PowerInterestClassifier().score_to_interest_level(6)
        assert result == InterestLevel.MEDIUM

    def test_007_score_2_maps_to_low_interest(self) -> None:
        result = PowerInterestClassifier().score_to_interest_level(2)
        assert result == InterestLevel.LOW

    def test_008_high_high_is_key_player(self) -> None:
        quadrant = PowerInterestClassifier().quadrant_from_levels(PowerLevel.HIGH, InterestLevel.HIGH)
        assert quadrant == StakeholderQuadrant.KEY_PLAYER

    def test_009_high_low_is_keep_satisfied(self) -> None:
        quadrant = PowerInterestClassifier().quadrant_from_levels(PowerLevel.HIGH, InterestLevel.LOW)
        assert quadrant == StakeholderQuadrant.KEEP_SATISFIED

    def test_010_low_high_is_keep_informed(self) -> None:
        quadrant = PowerInterestClassifier().quadrant_from_levels(PowerLevel.LOW, InterestLevel.HIGH)
        assert quadrant == StakeholderQuadrant.KEEP_INFORMED

    def test_011_low_low_is_monitor(self) -> None:
        quadrant = PowerInterestClassifier().quadrant_from_levels(PowerLevel.LOW, InterestLevel.LOW)
        assert quadrant == StakeholderQuadrant.MONITOR

    def test_012_clause_signal_increases_power_level(self) -> None:
        classifier = PowerInterestClassifier()
        signals = ClassificationSignals(
            decision_authority=False,
            budget_authority=False,
            communication_frequency=3,
            contractual_clause_mentions=2,
            project_dependency_level=3,
        )
        result = classifier.classify(signals)
        assert result.power_level == PowerLevel.MEDIUM

    def test_013_high_dependency_increases_interest_level(self) -> None:
        classifier = PowerInterestClassifier()
        signals = ClassificationSignals(
            decision_authority=False,
            budget_authority=False,
            communication_frequency=2,
            contractual_clause_mentions=0,
            project_dependency_level=9,
        )
        result = classifier.classify(signals)
        assert result.interest_level == InterestLevel.HIGH

    def test_014_full_classification_returns_quadrant(self) -> None:
        classifier = PowerInterestClassifier()
        signals = ClassificationSignals(
            decision_authority=True,
            budget_authority=True,
            communication_frequency=8,
            contractual_clause_mentions=3,
            project_dependency_level=8,
        )
        result = classifier.classify(signals)
        assert result.quadrant == StakeholderQuadrant.KEY_PLAYER
