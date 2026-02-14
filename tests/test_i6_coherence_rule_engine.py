# Path: apps/api/src/coherence/tests/integration/test_i6_coherence_rule_engine.py
import pytest
from unittest.mock import MagicMock
from uuid import uuid4
from datetime import date, timedelta

# TDD: These imports will fail until the application services, DTOs, and ports are created.
try:
    from src.coherence.application.services import CoherenceRuleEngine
    from src.coherence.application.ports import BaseRule
    from src.coherence.application.dtos import (
        Alert,
        AlertCategory,
        AlertSeverity,
        ContractData,
        ProjectPlanData,
    )
    from src.coherence.application.rules import ScheduleMismatchRule
except ImportError:
    # Define dummy classes to allow the test file to be parsed before implementation
    CoherenceRuleEngine = type("CoherenceRuleEngine", (), {})
    BaseRule = type("BaseRule", (), {})
    Alert = type("Alert", (), {})
    AlertCategory = type("AlertCategory", (), {})
    AlertSeverity = type("AlertSeverity", (), {})
    ContractData = type("ContractData", (), {})
    ProjectPlanData = type("ProjectPlanData", (), {})
    ScheduleMismatchRule = type("ScheduleMismatchRule", (BaseRule,), {})


@pytest.fixture
def contract_data_fixture() -> ContractData:
    """Provides a fixture representing contractual data."""
    return ContractData(
        contract_id=uuid4(),
        final_deadline=date(2025, 12, 31),
        milestones={"M1": date(2025, 6, 30)},
    )


@pytest.fixture
def project_plan_fixture() -> ProjectPlanData:
    """Provides a fixture representing project execution data."""
    return ProjectPlanData(
        project_id=uuid4(),
        planned_completion_date=date(2026, 1, 15),  # Mismatched with contract
        tasks={"T1": {"end_date": date(2025, 7, 1)}},
    )


@pytest.mark.integration
@pytest.mark.tdd
class TestCoherenceRuleEngine:
    """
    Test suite for I6 - Coherence Rule Engine.
    """

    def test_i6_01_triggered_alert_adheres_to_contract(
        self, contract_data_fixture, project_plan_fixture
    ):
        """
        [TEST-I6-01] Verifies a triggered alert DTO adheres to the required contract.
        """
        # Arrange: This test expects a `ScheduleMismatchRule` to exist.
        rule = ScheduleMismatchRule()

        # Act: This call will fail until the rule's `evaluate` method is implemented.
        alert: Alert = rule.evaluate(contract_data_fixture, project_plan_fixture)

        # Assert
        assert isinstance(alert, Alert)
        assert hasattr(alert, "rule_id") and alert.rule_id == "R1"
        assert hasattr(alert, "category") and alert.category == AlertCategory.TIME
        assert hasattr(alert, "severity") and alert.severity == AlertSeverity.HIGH
        assert hasattr(alert, "message")
        assert hasattr(alert, "evidence_links") and isinstance(alert.evidence_links, dict)

    def test_i6_02_schedule_mismatch_rule_triggers_on_misalignment(
        self, contract_data_fixture, project_plan_fixture
    ):
        """
        [TEST-I6-02] Verifies the schedule rule triggers when dates are misaligned.
        """
        # Arrange
        rule = ScheduleMismatchRule()

        # Act
        alert = rule.evaluate(contract_data_fixture, project_plan_fixture)

        # Assert
        assert alert is not None, "Rule should have triggered an alert for the date mismatch."
        assert "exceeds contract deadline" in alert.message

    def test_i6_03_schedule_mismatch_rule_does_not_trigger_on_alignment(
        self, contract_data_fixture
    ):
        """
        [TEST-I6-03] Verifies the schedule rule does not trigger when dates are aligned.
        """
        # Arrange
        aligned_plan = ProjectPlanData(
            project_id=uuid4(),
            planned_completion_date=contract_data_fixture.final_deadline - timedelta(days=10),
        )
        rule = ScheduleMismatchRule()

        # Act
        alert = rule.evaluate(contract_data_fixture, aligned_plan)

        # Assert
        assert alert is None, "Rule should not trigger when dates are aligned."

    @pytest.mark.xfail(reason="[TDD] Drives graceful degradation logic.", strict=True)
    def test_i6_04_engine_is_graceful_when_data_is_missing(
        self, contract_data_fixture
    ):
        """
        [TEST-I6-04] Verifies the engine returns no alerts if required data is missing.
        """
        # Arrange: This test expects the main `CoherenceRuleEngine` service to exist.
        mock_rule = MagicMock(spec=BaseRule)
        engine = CoherenceRuleEngine(rules=[mock_rule])
        # The project plan is missing (None)
        missing_data_context = {"contract": contract_data_fixture, "plan": None}

        # Act
        alerts = engine.run(missing_data_context)

        # Assert
        assert isinstance(alerts, list)
        assert len(alerts) == 0, "Engine should not produce alerts or crash with missing data."
        mock_rule.evaluate.assert_not_called()
        assert False, "Remove this line once the engine's graceful handling is implemented."