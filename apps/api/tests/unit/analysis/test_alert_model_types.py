"""
TDD tests for Alert model with alert_type discriminator.
Part of TASK-BCK-026: Unify AlertGenerator with pipeline save_to_db_node.

Test Suite ID: TS-ALERT-MODEL-TYPES-001
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.analysis.adapters.persistence.models import Alert
from src.analysis.domain.enums import AlertSeverity, AlertType


@pytest.fixture
def project_id():
    """Test project ID."""
    return uuid4()


@pytest.fixture
def analysis_id():
    """Test analysis ID."""
    return uuid4()


class TestAlertModelTypes:
    """Unit tests for Alert model with alert_type field."""

    def test_alert_type_defaults_to_risk(self, project_id, analysis_id):
        """Alert model should default alert_type to RISK for backward compatibility."""
        alert = Alert(
            project_id=project_id,
            analysis_id=analysis_id,
            severity=AlertSeverity.HIGH,
            title="Test alert",
            description="Test description",
            # alert_type not specified - should default to RISK
        )

        assert alert.alert_type == AlertType.RISK

    def test_alert_type_can_be_set_to_coherence(self, project_id, analysis_id):
        """Alert model should accept alert_type=COHERENCE."""
        alert = Alert(
            project_id=project_id,
            analysis_id=analysis_id,
            severity=AlertSeverity.HIGH,
            title="Test coherence alert",
            description="Test description",
            alert_type=AlertType.COHERENCE,
        )

        assert alert.alert_type == AlertType.COHERENCE

    def test_alert_type_can_be_set_to_budget(self, project_id, analysis_id):
        """Alert model should accept alert_type=BUDGET."""
        alert = Alert(
            project_id=project_id,
            analysis_id=analysis_id,
            severity=AlertSeverity.HIGH,
            title="Test budget alert",
            description="Test description",
            alert_type=AlertType.BUDGET,
        )

        assert alert.alert_type == AlertType.BUDGET

    def test_alert_type_can_be_set_to_wbs(self, project_id, analysis_id):
        """Alert model should accept alert_type=WBS."""
        alert = Alert(
            project_id=project_id,
            analysis_id=analysis_id,
            severity=AlertSeverity.HIGH,
            title="Test WBS alert",
            description="Test description",
            alert_type=AlertType.WBS,
        )

        assert alert.alert_type == AlertType.WBS

    def test_alert_type_validates_enum_values(self, project_id, analysis_id):
        """Alert model should only accept valid AlertType enum values."""
        # This test verifies enum validation at the model level
        # Invalid values should raise ValueError or similar
        with pytest.raises((ValueError, TypeError)):
            Alert(
                project_id=project_id,
                analysis_id=analysis_id,
                severity=AlertSeverity.HIGH,
                title="Test alert",
                description="Test description",
                alert_type="invalid_type",  # Invalid enum value
            )

    def test_alert_can_have_risk_type_and_schedule_category(
        self, project_id, analysis_id
    ):
        """Alert can have alert_type=RISK and category=schedule (independent fields)."""
        alert = Alert(
            project_id=project_id,
            analysis_id=analysis_id,
            severity=AlertSeverity.HIGH,
            title="Schedule risk alert",
            description="AI detected schedule risk.",
            alert_type=AlertType.RISK,
            category="schedule",
        )

        assert alert.alert_type == AlertType.RISK
        assert alert.category == "schedule"

    def test_alert_can_have_coherence_type_and_financial_category(
        self, project_id, analysis_id
    ):
        """Alert can have alert_type=COHERENCE and category=financial (independent fields)."""
        alert = Alert(
            project_id=project_id,
            analysis_id=analysis_id,
            severity=AlertSeverity.HIGH,
            title="Budget coherence alert",
            description="Coherence rule R2 violated.",
            alert_type=AlertType.COHERENCE,
            category="financial",
            rule_id="R2",
        )

        assert alert.alert_type == AlertType.COHERENCE
        assert alert.category == "financial"
        assert alert.rule_id == "R2"

    def test_alert_can_have_coherence_type_and_legal_category(
        self, project_id, analysis_id
    ):
        """Alert can have alert_type=COHERENCE and category=legal."""
        alert = Alert(
            project_id=project_id,
            analysis_id=analysis_id,
            severity=AlertSeverity.MEDIUM,
            title="Legal coherence alert",
            description="Coherence rule R6 violated.",
            alert_type=AlertType.COHERENCE,
            category="legal",
            rule_id="R6",
        )

        assert alert.alert_type == AlertType.COHERENCE
        assert alert.category == "legal"

    def test_alert_can_have_risk_type_and_null_category(
        self, project_id, analysis_id
    ):
        """Alert can have alert_type=RISK with null category."""
        alert = Alert(
            project_id=project_id,
            analysis_id=analysis_id,
            severity=AlertSeverity.LOW,
            title="Generic risk",
            description="Uncategorized risk.",
            alert_type=AlertType.RISK,
            category=None,
        )

        assert alert.alert_type == AlertType.RISK
        assert alert.category is None

    def test_alert_type_field_is_indexed(self, project_id, analysis_id):
        """Alert model should have index on alert_type for efficient filtering."""
        # This test verifies that the alert_type field has an index
        # Check model's __table_args__ for index definition
        from src.analysis.adapters.persistence.models import Alert

        table_args = Alert.__table_args__
        # Index should be defined for alert_type
        index_names = [
            idx.name for idx in table_args if hasattr(idx, "name")
        ]
        # Should have ix_alerts_alert_type or similar
        assert any("alert_type" in name for name in index_names), (
            "alert_type field should have an index for efficient filtering"
        )
