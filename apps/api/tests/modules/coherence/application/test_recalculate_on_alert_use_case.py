"""
Recalculate on Alert Use Case Tests (TDD).

Refers to Suite ID: TS-UA-COH-UC-002.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.coherence.application.dtos import (
    AlertAction,
    RecalculateOnAlertCommand,
)
from src.coherence.application.use_cases import RecalculateOnAlertUseCase
from src.coherence.domain.category_weights import CoherenceCategory


class TestRecalculateOnAlertUseCase:
    """Refers to Suite ID: TS-UA-COH-UC-002"""

    def test_001_execute_resolved_action_triggers_recalculation(self) -> None:
        """RESOLVED action with alert_ids triggers recalculation."""
        command = RecalculateOnAlertCommand(
            project_id=uuid4(),
            alert_ids=["R11"],
            alert_action=AlertAction.RESOLVED,
        )

        use_case = RecalculateOnAlertUseCase()
        result = use_case.execute(command)

        assert result.recalculation_triggered is True
        assert result.project_id == command.project_id

    def test_002_execute_returns_score_delta(self) -> None:
        """Result includes score delta between previous and new scores."""
        command = RecalculateOnAlertCommand(
            project_id=uuid4(),
            alert_ids=["R11"],
            alert_action=AlertAction.RESOLVED,
            scope_defined=False,  # Creates violation
        )

        use_case = RecalculateOnAlertUseCase()
        result = use_case.execute(command)

        # Score delta is new - previous
        assert result.score_delta == result.new_global_score - result.previous_global_score
        assert isinstance(result.score_delta, int)

    def test_003_execute_stores_previous_scores(self) -> None:
        """Result includes previous global and category scores."""
        command = RecalculateOnAlertCommand(
            project_id=uuid4(),
            alert_ids=["R6"],
            alert_action=AlertAction.RESOLVED,
        )

        use_case = RecalculateOnAlertUseCase()
        result = use_case.execute(command)

        assert result.previous_global_score >= 0
        assert len(result.previous_category_scores) == 6
        assert CoherenceCategory.SCOPE in result.previous_category_scores

    def test_004_execute_stores_new_scores(self) -> None:
        """Result includes new global and category scores after recalculation."""
        command = RecalculateOnAlertCommand(
            project_id=uuid4(),
            alert_ids=["R11"],
            alert_action=AlertAction.RESOLVED,
        )

        use_case = RecalculateOnAlertUseCase()
        result = use_case.execute(command)

        assert result.new_global_score >= 0
        assert len(result.new_category_scores) == 6
        assert CoherenceCategory.BUDGET in result.new_category_scores

    def test_005_acknowledged_action_does_not_trigger_recalculation(self) -> None:
        """ACKNOWLEDGED action does not trigger recalculation."""
        command = RecalculateOnAlertCommand(
            project_id=uuid4(),
            alert_ids=["R11"],
            alert_action=AlertAction.ACKNOWLEDGED,
        )

        use_case = RecalculateOnAlertUseCase()
        result = use_case.execute(command)

        assert result.recalculation_triggered is False

    def test_006_dismissed_action_with_alerts_triggers_recalculation(self) -> None:
        """DISMISSED action with alert_ids triggers recalculation."""
        command = RecalculateOnAlertCommand(
            project_id=uuid4(),
            alert_ids=["R17"],
            alert_action=AlertAction.DISMISSED,
        )

        use_case = RecalculateOnAlertUseCase()
        result = use_case.execute(command)

        assert result.recalculation_triggered is True

    def test_007_resolved_alerts_filtered_from_remaining_alerts(self) -> None:
        """Resolved alert IDs are excluded from remaining_alerts."""
        command = RecalculateOnAlertCommand(
            project_id=uuid4(),
            alert_ids=["R11"],
            alert_action=AlertAction.RESOLVED,
            scope_defined=False,  # Creates R11 violation
        )

        use_case = RecalculateOnAlertUseCase()
        result = use_case.execute(command)

        # R11 should be in resolved_alert_ids
        assert "R11" in result.resolved_alert_ids
        # R11 should NOT be in remaining_alerts
        remaining_rule_ids = {alert.rule_id for alert in result.remaining_alerts}
        assert "R11" not in remaining_rule_ids

    def test_008_empty_alert_ids_does_not_trigger_recalculation(self) -> None:
        """RESOLVED action with empty alert_ids does not trigger recalculation."""
        command = RecalculateOnAlertCommand(
            project_id=uuid4(),
            alert_ids=[],
            alert_action=AlertAction.RESOLVED,
        )

        use_case = RecalculateOnAlertUseCase()
        result = use_case.execute(command)

        assert result.recalculation_triggered is False
        assert len(result.resolved_alert_ids) == 0

    def test_009_custom_weights_preserved_in_recalculation(self) -> None:
        """Custom weights are used in recalculation."""
        command = RecalculateOnAlertCommand(
            project_id=uuid4(),
            alert_ids=["R11"],
            alert_action=AlertAction.RESOLVED,
            scope_defined=False,  # SCOPE = 70
            custom_weights={
                CoherenceCategory.SCOPE: 0.50,
                CoherenceCategory.BUDGET: 0.10,
                CoherenceCategory.QUALITY: 0.10,
                CoherenceCategory.TECHNICAL: 0.10,
                CoherenceCategory.LEGAL: 0.10,
                CoherenceCategory.TIME: 0.10,
            },
        )

        use_case = RecalculateOnAlertUseCase()
        result = use_case.execute(command)

        # With 50% weight on SCOPE (70) and 50% on others (100), score should be ~85
        assert result.new_global_score < 90

    def test_010_gaming_detection_in_recalculation(self) -> None:
        """Gaming detection runs during recalculation."""
        command = RecalculateOnAlertCommand(
            project_id=uuid4(),
            alert_ids=["R11"],
            alert_action=AlertAction.RESOLVED,
            document_count=3,  # Few documents
        )

        use_case = RecalculateOnAlertUseCase()
        result = use_case.execute(command)

        # Perfect score with few docs triggers gaming detection
        if result.new_global_score >= 90:
            assert result.is_gaming_detected is True
            assert "suspicious_high_score" in result.gaming_violations

    def test_011_acknowledged_action_returns_empty_resolved_ids(self) -> None:
        """ACKNOWLEDGED action returns empty resolved_alert_ids."""
        command = RecalculateOnAlertCommand(
            project_id=uuid4(),
            alert_ids=["R11", "R6"],
            alert_action=AlertAction.ACKNOWLEDGED,
        )

        use_case = RecalculateOnAlertUseCase()
        result = use_case.execute(command)

        # Acknowledged alerts are not resolved
        assert len(result.resolved_alert_ids) == 0
        assert result.recalculation_triggered is False
