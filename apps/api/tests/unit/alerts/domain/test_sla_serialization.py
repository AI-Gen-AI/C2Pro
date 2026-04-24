"""
Migrated SLA serialization tests using domain services.

TS-UD-ALR-SLA-002

Replaces test_alert_sla_serialization.py (OLD) which imported from src.alerts.router.
Now uses domain services directly (SLACalculator, Alert model).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from alerts.domain.enums import AlertSeverity, AlertStatus, ApprovalStatus
from alerts.domain.models import Alert
from alerts.domain.services.sla_calculator import SLACalculator


class TestSLAFromDomainModel:
    """Tests for SLA calculation using domain model and service."""

    def test_calculate_sla_policy_for_critical_severity(self) -> None:
        """Test SLA policy calculation for critical severity."""
        created_at = datetime(2026, 4, 1, 8, 30, 0, tzinfo=UTC)

        policy_name, due_at = SLACalculator.calculate_due_at(
            AlertSeverity.CRITICAL, created_at
        )

        assert policy_name == "Critical severity: first response in 2 hours"
        assert due_at == datetime(2026, 4, 1, 10, 30, 0, tzinfo=UTC)

    def test_calculate_sla_policy_for_high_severity(self) -> None:
        """Test SLA policy calculation for high severity."""
        created_at = datetime(2026, 4, 1, 8, 30, 0, tzinfo=UTC)

        policy_name, due_at = SLACalculator.calculate_due_at(
            AlertSeverity.HIGH, created_at
        )

        assert policy_name == "High severity: response in 24 hours"
        assert due_at == datetime(2026, 4, 2, 8, 30, 0, tzinfo=UTC)

    def test_calculate_sla_policy_for_medium_severity(self) -> None:
        """Test SLA policy calculation for medium severity."""
        created_at = datetime(2026, 4, 1, 8, 30, 0, tzinfo=UTC)

        policy_name, due_at = SLACalculator.calculate_due_at(
            AlertSeverity.MEDIUM, created_at
        )

        assert policy_name == "Medium severity: response in 72 hours"
        assert due_at == datetime(2026, 4, 4, 8, 30, 0, tzinfo=UTC)

    def test_calculate_sla_policy_for_low_severity(self) -> None:
        """Test SLA policy calculation for low severity."""
        created_at = datetime(2026, 4, 1, 8, 30, 0, tzinfo=UTC)

        policy_name, due_at = SLACalculator.calculate_due_at(
            AlertSeverity.LOW, created_at
        )

        assert policy_name == "Low severity: response in 120 hours"
        assert due_at == datetime(2026, 4, 6, 8, 30, 0, tzinfo=UTC)


class TestAlertSLAIntegration:
    """Integration tests combining Alert model with SLACalculator."""

    def test_alert_calculate_sla_due_at(self) -> None:
        """Test that Alert.calculate_sla_due_at works correctly."""
        created_at = datetime(2026, 4, 1, 8, 30, 0, tzinfo=UTC)
        alert = Alert(
            id=uuid4(),
            project_id=uuid4(),
            severity=AlertSeverity.CRITICAL,
            category="LEGAL",
            status=AlertStatus.OPEN,
            approval_status=ApprovalStatus.PENDING,
            rule_id="R1",
            title="Missing permit",
            description="Missing permit",
            affected_entities={},
            alert_metadata={},
            created_at=created_at,
        )

        policy_name, due_at = alert.calculate_sla_due_at()

        assert policy_name == "Critical severity: first response in 2 hours"
        assert due_at == created_at + timedelta(hours=2)

    def test_sla_calculation_with_string_severity(self) -> None:
        """Test SLACalculator with string severity (case insensitive)."""
        created_at = datetime(2026, 4, 1, 8, 30, 0, tzinfo=UTC)

        policy_name, due_at = SLACalculator.calculate_due_at("CRITICAL", created_at)

        assert policy_name == "Critical severity: first response in 2 hours"

    def test_sla_calculation_invalid_severity(self) -> None:
        """Test SLACalculator with invalid severity returns None."""
        created_at = datetime(2026, 4, 1, 8, 30, 0, tzinfo=UTC)

        policy_name, due_at = SLACalculator.calculate_due_at("INVALID", created_at)

        assert policy_name is None


class TestNormalizeAffectedEntities:
    """Tests for affected_entities normalization (migrated from old router)."""

    def test_normalize_list_to_dict(self) -> None:
        """Test that list is converted to {"items": list}."""
        result = Alert.normalize_affected_entities(["doc-1", "doc-2"])

        assert result == {"items": ["doc-1", "doc-2"]}

    def test_normalize_dict_unchanged(self) -> None:
        """Test that dict is returned unchanged."""
        input_dict = {"items": ["doc-1", "doc-2"]}

        result = Alert.normalize_affected_entities(input_dict)

        assert result == input_dict

    def test_normalize_none_returns_empty_dict(self) -> None:
        """Test that None returns empty dict."""
        result = Alert.normalize_affected_entities(None)

        assert result == {}


class TestMigrationFromOldRouter:
    """Verify migration from old router._serialize_alert function."""

    def test_sla_policy_matches_old_router_2h(self) -> None:
        """
        Verify SLA policy matches old router:
        - critical: 2 hours (was 2h in old _get_sla_policy)
        """
        created_at = datetime(2026, 4, 1, 8, 30, 0, tzinfo=UTC)

        policy_name, due_at = SLACalculator.calculate_due_at("critical", created_at)

        assert "2 hours" in policy_name
        assert due_at == created_at + timedelta(hours=2)

    def test_sla_policy_matches_old_router_24h(self) -> None:
        """
        Verify SLA policy matches old router:
        - high: 24 hours (NOTE: backlog says 8h but old code has 24h)
        """
        created_at = datetime(2026, 4, 1, 8, 30, 0, tzinfo=UTC)

        policy_name, due_at = SLACalculator.calculate_due_at("high", created_at)

        assert "24 hours" in policy_name
        assert due_at == created_at + timedelta(hours=24)

    def test_entity_normalization_matches_old_router(self) -> None:
        """
        Verify entity normalization matches old _normalize_affected_entities:
        - list: ["a", "b"] -> {"items": ["a", "b"]}
        """
        result = Alert.normalize_affected_entities(["doc-legacy-1", "doc-legacy-2"])

        assert result == {"items": ["doc-legacy-1", "doc-legacy-2"]}
