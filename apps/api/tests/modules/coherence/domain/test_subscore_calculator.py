"""
Subscore calculator tests.

Refers to Suite ID: TS-UD-COH-SCR-001.
"""

from __future__ import annotations

from uuid import uuid4

from src.coherence.domain.subscore_calculator import (
    CoherenceAlert,
    CoherenceSeverity,
    ScoreScope,
    SubscoreCalculator,
)


class TestSubscoreCalculator:
    """Refers to Suite ID: TS-UD-COH-SCR-001"""

    def test_001_subscore_no_alerts_100_percent(self) -> None:
        score = SubscoreCalculator().calculate_subscore(alerts=[], scope=ScoreScope.BUDGET)
        assert score == 100.0

    def test_002_subscore_one_alert_penalized(self) -> None:
        alerts = [
            CoherenceAlert.model_validate(
                {"rule_id": "R6", "severity": CoherenceSeverity.MEDIUM, "scope": ScoreScope.BUDGET}
            )
        ]
        score = SubscoreCalculator().calculate_subscore(alerts=alerts, scope=ScoreScope.BUDGET)
        assert score == 90.0

    def test_003_subscore_multiple_alerts_cumulative(self) -> None:
        alerts = [
            CoherenceAlert.model_validate(
                {"rule_id": "R6", "severity": CoherenceSeverity.MEDIUM, "scope": ScoreScope.BUDGET}
            ),
            CoherenceAlert.model_validate(
                {"rule_id": "R15", "severity": CoherenceSeverity.HIGH, "scope": ScoreScope.BUDGET}
            ),
        ]
        score = SubscoreCalculator().calculate_subscore(alerts=alerts, scope=ScoreScope.BUDGET)
        assert score == 70.0

    def test_004_subscore_severity_low_penalty_5(self) -> None:
        alerts = [
            CoherenceAlert.model_validate(
                {"rule_id": "R11", "severity": CoherenceSeverity.LOW, "scope": ScoreScope.SCOPE}
            )
        ]
        score = SubscoreCalculator().calculate_subscore(alerts=alerts, scope=ScoreScope.SCOPE)
        assert score == 95.0

    def test_005_subscore_severity_medium_penalty_10(self) -> None:
        alerts = [
            CoherenceAlert.model_validate(
                {"rule_id": "R6", "severity": CoherenceSeverity.MEDIUM, "scope": ScoreScope.BUDGET}
            )
        ]
        score = SubscoreCalculator().calculate_subscore(alerts=alerts, scope=ScoreScope.BUDGET)
        assert score == 90.0

    def test_006_subscore_severity_high_penalty_20(self) -> None:
        alerts = [
            CoherenceAlert.model_validate(
                {"rule_id": "R1", "severity": CoherenceSeverity.HIGH, "scope": ScoreScope.TIME}
            )
        ]
        score = SubscoreCalculator().calculate_subscore(alerts=alerts, scope=ScoreScope.TIME)
        assert score == 80.0

    def test_007_subscore_severity_critical_penalty_30(self) -> None:
        alerts = [
            CoherenceAlert.model_validate(
                {"rule_id": "R14", "severity": CoherenceSeverity.CRITICAL, "scope": ScoreScope.TIME}
            )
        ]
        score = SubscoreCalculator().calculate_subscore(alerts=alerts, scope=ScoreScope.TIME)
        assert score == 70.0

    def test_008_subscore_scope_calculation(self) -> None:
        alerts = [
            CoherenceAlert.model_validate(
                {"rule_id": "R11", "severity": CoherenceSeverity.HIGH, "scope": ScoreScope.SCOPE}
            ),
            CoherenceAlert.model_validate(
                {"rule_id": "R6", "severity": CoherenceSeverity.CRITICAL, "scope": ScoreScope.BUDGET}
            ),
        ]
        score = SubscoreCalculator().calculate_subscore(alerts=alerts, scope=ScoreScope.SCOPE)
        assert score == 80.0

    def test_009_subscore_budget_calculation(self) -> None:
        alerts = [
            CoherenceAlert.model_validate(
                {"rule_id": "R6", "severity": CoherenceSeverity.MEDIUM, "scope": ScoreScope.BUDGET}
            )
        ]
        score = SubscoreCalculator().calculate_subscore(alerts=alerts, scope=ScoreScope.BUDGET)
        assert score == 90.0

    def test_010_subscore_quality_calculation(self) -> None:
        alerts = [
            CoherenceAlert.model_validate(
                {"rule_id": "R17", "severity": CoherenceSeverity.HIGH, "scope": ScoreScope.QUALITY}
            )
        ]
        score = SubscoreCalculator().calculate_subscore(alerts=alerts, scope=ScoreScope.QUALITY)
        assert score == 80.0

    def test_011_subscore_technical_calculation(self) -> None:
        alerts = [
            CoherenceAlert.model_validate(
                {"rule_id": "R3", "severity": CoherenceSeverity.LOW, "scope": ScoreScope.TECHNICAL}
            )
        ]
        score = SubscoreCalculator().calculate_subscore(alerts=alerts, scope=ScoreScope.TECHNICAL)
        assert score == 95.0

    def test_012_subscore_legal_calculation(self) -> None:
        alerts = [
            CoherenceAlert.model_validate(
                {"rule_id": "R8", "severity": CoherenceSeverity.HIGH, "scope": ScoreScope.LEGAL}
            )
        ]
        score = SubscoreCalculator().calculate_subscore(alerts=alerts, scope=ScoreScope.LEGAL)
        assert score == 80.0

    def test_013_subscore_time_calculation(self) -> None:
        alerts = [
            CoherenceAlert.model_validate(
                {"rule_id": "R2", "severity": CoherenceSeverity.MEDIUM, "scope": ScoreScope.TIME}
            )
        ]
        score = SubscoreCalculator().calculate_subscore(alerts=alerts, scope=ScoreScope.TIME)
        assert score == 90.0

    def test_014_subscore_floor_at_zero(self) -> None:
        alerts = [
            CoherenceAlert.model_validate(
                {
                    "rule_id": f"R-C-{index}",
                    "severity": CoherenceSeverity.CRITICAL,
                    "scope": ScoreScope.BUDGET,
                }
            )
            for index in range(4)
        ]
        score = SubscoreCalculator().calculate_subscore(alerts=alerts, scope=ScoreScope.BUDGET)
        assert score == 0.0
