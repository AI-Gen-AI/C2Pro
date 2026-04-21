"""
Unit tests for SLACalculator domain service.

TS-UD-ALR-SLA-001
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from freezegun import freeze_time

from alerts.domain.services.sla_calculator import (
    CRITICAL_SLA,
    HIGH_SLA,
    LOW_SLA,
    MEDIUM_SLA,
    SLACalculator,
    SLACalculation,
    AlertSeverityLevel,
)


class TestSLACalculatorGetPolicy:
    """Tests for get_sla_policy method."""

    @pytest.mark.parametrize("severity,expected_hours", [
        ("critical", 2),
        ("CRITICAL", 2),
        ("Critical", 2),
        ("high", 24),
        ("HIGH", 24),
        ("medium", 72),
        ("MEDIUM", 72),
        ("low", 120),
        ("LOW", 120),
    ])
    def test_get_policy_by_string_severity(self, severity: str, expected_hours: int) -> None:
        """Test getting SLA policy by string severity (case insensitive)."""
        policy = SLACalculator.get_sla_policy(severity)
        
        assert policy is not None
        assert policy.response_hours == expected_hours

    @pytest.mark.parametrize("severity,expected_hours", [
        (AlertSeverityLevel.CRITICAL, 2),
        (AlertSeverityLevel.HIGH, 24),
        (AlertSeverityLevel.MEDIUM, 72),
        (AlertSeverityLevel.LOW, 120),
    ])
    def test_get_policy_by_enum_severity(
        self, severity: AlertSeverityLevel, expected_hours: int
    ) -> None:
        """Test getting SLA policy by enum severity."""
        policy = SLACalculator.get_sla_policy(severity)
        
        assert policy is not None
        assert policy.response_hours == expected_hours

    @pytest.mark.parametrize("invalid_severity", [
        "invalid",
        "blocker",
        "warning",
        "",
        "  ",
    ])
    def test_get_policy_returns_none_for_invalid_severity(
        self, invalid_severity: str
    ) -> None:
        """Test that invalid severity returns None."""
        policy = SLACalculator.get_sla_policy(invalid_severity)
        
        assert policy is None

    def test_get_policy_with_random_string(self) -> None:
        """Test that random strings return None."""
        policy = SLACalculator.get_sla_policy(str(uuid4()))
        
        assert policy is None


class TestSLACalculatorCalculateDueAt:
    """Tests for calculate_due_at method."""

    def test_calculate_critical_due_at(self) -> None:
        """Test SLA due date calculation for critical severity."""
        created_at = datetime(2026, 4, 8, 10, 0, 0, tzinfo=UTC)
        
        policy_name, due_at = SLACalculator.calculate_due_at("critical", created_at)
        
        assert policy_name == "Critical severity: first response in 2 hours"
        assert due_at == datetime(2026, 4, 8, 12, 0, 0, tzinfo=UTC)

    def test_calculate_high_due_at(self) -> None:
        """Test SLA due date calculation for high severity."""
        created_at = datetime(2026, 4, 8, 10, 0, 0, tzinfo=UTC)
        
        policy_name, due_at = SLACalculator.calculate_due_at("high", created_at)
        
        assert policy_name == "High severity: response in 24 hours"
        assert due_at == datetime(2026, 4, 9, 10, 0, 0, tzinfo=UTC)

    def test_calculate_medium_due_at(self) -> None:
        """Test SLA due date calculation for medium severity."""
        created_at = datetime(2026, 4, 8, 10, 0, 0, tzinfo=UTC)
        
        policy_name, due_at = SLACalculator.calculate_due_at("medium", created_at)
        
        assert policy_name == "Medium severity: response in 72 hours"
        assert due_at == datetime(2026, 4, 11, 10, 0, 0, tzinfo=UTC)

    def test_calculate_low_due_at(self) -> None:
        """Test SLA due date calculation for low severity."""
        created_at = datetime(2026, 4, 8, 10, 0, 0, tzinfo=UTC)
        
        policy_name, due_at = SLACalculator.calculate_due_at("low", created_at)
        
        assert policy_name == "Low severity: response in 120 hours"
        assert due_at == datetime(2026, 4, 13, 10, 0, 0, tzinfo=UTC)

    def test_calculate_due_at_invalid_severity(self) -> None:
        """Test that invalid severity returns (None, datetime.min)."""
        created_at = datetime(2026, 4, 8, 10, 0, 0, tzinfo=UTC)
        
        policy_name, due_at = SLACalculator.calculate_due_at("invalid", created_at)
        
        assert policy_name is None
        assert due_at == datetime.min


class TestSLACalculatorCalculate:
    """Tests for calculate method with full SLA information."""

    def test_calculate_not_overdue(self) -> None:
        """Test calculation for alert that is not yet overdue."""
        created_at = datetime.now(UTC) - timedelta(hours=1)
        
        result = SLACalculator.calculate("critical", created_at)
        
        assert result.policy_name is not None
        assert result.due_at is not None
        assert result.hours_remaining == 1
        assert result.is_overdue is False

    def test_calculate_overdue(self) -> None:
        """Test calculation for alert that is overdue."""
        created_at = datetime.now(UTC) - timedelta(hours=3)
        
        result = SLACalculator.calculate("critical", created_at)
        
        assert result.policy_name is not None
        assert result.due_at is not None
        assert result.hours_remaining == -1
        assert result.is_overdue is True

    @freeze_time("2026-04-08T12:00:00+00:00")
    def test_calculate_at_exact_due_time(self) -> None:
        """Test calculation at exact SLA due time.

        Time is frozen so that the calculator's internal `datetime.now(UTC)`
        matches the test's reference instant exactly, eliminating microsecond
        drift that previously caused intermittent `is_overdue=True` failures
        on slow runners.
        """
        now = datetime.now(UTC)
        created_at = now - timedelta(hours=2)

        result = SLACalculator.calculate("critical", created_at)

        assert result.policy_name is not None
        assert result.due_at == now
        assert result.hours_remaining == 0
        assert result.is_overdue is False

    def test_calculate_invalid_severity(self) -> None:
        """Test calculation with invalid severity returns empty result."""
        created_at = datetime.now(UTC)
        
        result = SLACalculator.calculate("invalid", created_at)
        
        assert result.policy_name is None
        assert result.due_at is None
        assert result.hours_remaining is None
        assert result.is_overdue is False


class TestSLACalculatorGetAllPolicies:
    """Tests for get_all_policies method."""

    def test_get_all_policies_returns_four_policies(self) -> None:
        """Test that all four SLA policies are returned."""
        policies = SLACalculator.get_all_policies()
        
        assert len(policies) == 4

    def test_get_all_policies_contains_all_severities(self) -> None:
        """Test that all severity levels are present."""
        policies = SLACalculator.get_all_policies()
        policy_names = [p.name for p in policies]
        
        assert CRITICAL_SLA.name in policy_names
        assert HIGH_SLA.name in policy_names
        assert MEDIUM_SLA.name in policy_names
        assert LOW_SLA.name in policy_names

    def test_get_all_policies_response_hours(self) -> None:
        """Test response hours for each policy."""
        policies = SLACalculator.get_all_policies()
        hours_map = {p.name: p.response_hours for p in policies}
        
        assert hours_map[CRITICAL_SLA.name] == 2
        assert hours_map[HIGH_SLA.name] == 24
        assert hours_map[MEDIUM_SLA.name] == 72
        assert hours_map[LOW_SLA.name] == 120


class TestSLACalculatorValidateSeverity:
    """Tests for validate_severity method."""

    @pytest.mark.parametrize("valid_severity", [
        "critical", "CRITICAL", "Critical",
        "high", "HIGH", "High",
        "medium", "MEDIUM", "Medium",
        "low", "LOW", "Low",
        AlertSeverityLevel.CRITICAL,
        AlertSeverityLevel.HIGH,
        AlertSeverityLevel.MEDIUM,
        AlertSeverityLevel.LOW,
    ])
    def test_validate_severity_returns_true_for_valid(
        self, valid_severity: str | AlertSeverityLevel
    ) -> None:
        """Test that all valid severity levels return True."""
        assert SLACalculator.validate_severity(valid_severity) is True

    @pytest.mark.parametrize("invalid_severity", [
        "invalid",
        "warning",
        "info",
        "",
        "  ",
        "blocker",
    ])
    def test_validate_severity_returns_false_for_invalid(
        self, invalid_severity: str
    ) -> None:
        """Test that invalid severity levels return False."""
        assert SLACalculator.validate_severity(invalid_severity) is False


class TestSLAPolicyConstants:
    """Tests for SLA policy constants."""

    def test_critical_sla(self) -> None:
        """Test critical SLA policy definition."""
        assert CRITICAL_SLA.name == "Critical severity: first response in 2 hours"
        assert CRITICAL_SLA.response_hours == 2

    def test_high_sla(self) -> None:
        """Test high SLA policy definition."""
        assert HIGH_SLA.name == "High severity: response in 24 hours"
        assert HIGH_SLA.response_hours == 24

    def test_medium_sla(self) -> None:
        """Test medium SLA policy definition."""
        assert MEDIUM_SLA.name == "Medium severity: response in 72 hours"
        assert MEDIUM_SLA.response_hours == 72

    def test_low_sla(self) -> None:
        """Test low SLA policy definition."""
        assert LOW_SLA.name == "Low severity: response in 120 hours"
        assert LOW_SLA.response_hours == 120


class TestSLACalculationDataclass:
    """Tests for SLACalculation result object."""

    def test_sla_calculation_with_all_fields(self) -> None:
        """Test SLACalculation with all fields populated."""
        due_at = datetime(2026, 4, 8, 12, 0, 0, tzinfo=UTC)
        
        result = SLACalculation(
            policy_name="Test Policy",
            due_at=due_at,
            hours_remaining=5,
            is_overdue=False,
        )
        
        assert result.policy_name == "Test Policy"
        assert result.due_at == due_at
        assert result.hours_remaining == 5
        assert result.is_overdue is False

    def test_sla_calculation_overdue(self) -> None:
        """Test SLACalculation for overdue alert."""
        result = SLACalculation(
            policy_name="Critical",
            due_at=datetime.now(UTC) - timedelta(hours=1),
            hours_remaining=-1,
            is_overdue=True,
        )
        
        assert result.is_overdue is True
        assert result.hours_remaining == -1

    def test_sla_calculation_no_policy(self) -> None:
        """Test SLACalculation when no policy is found."""
        result = SLACalculation(
            policy_name=None,
            due_at=None,
            hours_remaining=None,
            is_overdue=False,
        )
        
        assert result.policy_name is None
        assert result.due_at is None
        assert result.hours_remaining is None
        assert result.is_overdue is False
