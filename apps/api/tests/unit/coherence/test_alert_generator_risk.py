"""
TDD tests for AlertGenerator risk alert generation.
Part of TASK-BCK-026: Unify AlertGenerator with pipeline save_to_db_node.

Test Suite ID: TS-ALERT-GEN-RISK-001
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.analysis.domain.enums import AlertSeverity, AlertType
from src.coherence.alert_generator import AlertGenerator


@pytest.fixture
def project_id():
    """Test project ID."""
    return uuid4()


@pytest.fixture
def analysis_id():
    """Test analysis ID."""
    return uuid4()


@pytest.fixture
def sample_risk_items():
    """Sample risk items from AI extraction."""
    return [
        {
            "summary": "Schedule delay risk",
            "description": "Project may be delayed due to resource constraints.",
            "impact_level": "high",
            "confidence": 0.85,
            "category": "schedule",
        },
        {
            "title": "Budget overrun risk",
            "description": "Current spend rate exceeds budget allocation.",
            "impact_level": "critical",
            "confidence": 0.92,
            "category": "financial",
        },
        {
            "summary": "Compliance risk",
            "description": "Missing required permits for Phase 2.",
            "impact_level": "medium",
            "confidence": 0.78,
            "category": "legal",
        },
    ]


class TestAlertGeneratorRiskAlerts:
    """Unit tests for risk alert generation."""

    def test_generate_risk_alerts_sets_alert_type_risk(
        self, project_id, analysis_id, sample_risk_items
    ):
        """AlertGenerator should set alert_type='risk' for risk alerts."""
        generator = AlertGenerator(project_id=project_id, analysis_id=analysis_id)

        alerts = generator.generate_risk_alerts(sample_risk_items)

        assert len(alerts) == 3
        for alert in alerts:
            assert alert.alert_type == AlertType.RISK

    def test_generate_risk_alerts_maps_severity_correctly(
        self, project_id, analysis_id, sample_risk_items
    ):
        """Risk alerts should map impact_level to severity correctly."""
        generator = AlertGenerator(project_id=project_id, analysis_id=analysis_id)

        alerts = generator.generate_risk_alerts(sample_risk_items)

        # First item: impact_level="high" -> AlertSeverity.HIGH
        assert alerts[0].severity == AlertSeverity.HIGH

        # Second item: impact_level="critical" -> AlertSeverity.CRITICAL
        assert alerts[1].severity == AlertSeverity.CRITICAL

        # Third item: impact_level="medium" -> AlertSeverity.MEDIUM
        assert alerts[2].severity == AlertSeverity.MEDIUM

    def test_generate_risk_alerts_uses_risk_category_as_default(
        self, project_id, analysis_id
    ):
        """Risk alerts without category should default to 'risk' category."""
        generator = AlertGenerator(project_id=project_id, analysis_id=analysis_id)

        risk_items = [
            {
                "summary": "Generic risk",
                "description": "No specific category provided.",
                "impact_level": "low",
                "confidence": 0.65,
                # No category field
            }
        ]

        alerts = generator.generate_risk_alerts(risk_items)

        assert len(alerts) == 1
        assert alerts[0].category == "risk"

    def test_generate_risk_alerts_includes_confidence_in_metadata(
        self, project_id, analysis_id, sample_risk_items
    ):
        """Risk alerts should include confidence score in metadata."""
        generator = AlertGenerator(project_id=project_id, analysis_id=analysis_id)

        alerts = generator.generate_risk_alerts(sample_risk_items)

        for i, alert in enumerate(alerts):
            assert "confidence" in alert.alert_metadata
            assert alert.alert_metadata["confidence"] == sample_risk_items[i]["confidence"]

    def test_generate_risk_alerts_handles_empty_list(self, project_id, analysis_id):
        """AlertGenerator should handle empty risk list gracefully."""
        generator = AlertGenerator(project_id=project_id, analysis_id=analysis_id)

        alerts = generator.generate_risk_alerts([])

        assert alerts == []

    def test_generate_risk_alerts_maps_impact_level(
        self, project_id, analysis_id
    ):
        """Risk alerts should correctly map all impact levels."""
        generator = AlertGenerator(project_id=project_id, analysis_id=analysis_id)

        risk_items = [
            {"summary": "Low risk", "description": "Low impact", "impact_level": "low", "confidence": 0.7},
            {"summary": "Medium risk", "description": "Medium impact", "impact_level": "medium", "confidence": 0.75},
            {"summary": "High risk", "description": "High impact", "impact_level": "high", "confidence": 0.8},
            {"summary": "Critical risk", "description": "Critical impact", "impact_level": "critical", "confidence": 0.9},
        ]

        alerts = generator.generate_risk_alerts(risk_items)

        assert alerts[0].severity == AlertSeverity.LOW
        assert alerts[0].impact_level == "low"

        assert alerts[1].severity == AlertSeverity.MEDIUM
        assert alerts[1].impact_level == "medium"

        assert alerts[2].severity == AlertSeverity.HIGH
        assert alerts[2].impact_level == "high"

        assert alerts[3].severity == AlertSeverity.CRITICAL
        assert alerts[3].impact_level == "critical"

    def test_generate_risk_alerts_uses_custom_category_when_provided(
        self, project_id, analysis_id
    ):
        """Risk alerts should use custom category when provided."""
        generator = AlertGenerator(project_id=project_id, analysis_id=analysis_id)

        risk_items = [
            {
                "summary": "Schedule risk",
                "description": "Timeline delay.",
                "impact_level": "high",
                "confidence": 0.85,
                "category": "schedule",
            },
            {
                "summary": "Financial risk",
                "description": "Budget overrun.",
                "impact_level": "high",
                "confidence": 0.88,
                "category": "financial",
            },
            {
                "summary": "Legal risk",
                "description": "Compliance issue.",
                "impact_level": "medium",
                "confidence": 0.82,
                "category": "legal",
            },
        ]

        alerts = generator.generate_risk_alerts(risk_items)

        assert alerts[0].category == "schedule"
        assert alerts[1].category == "financial"
        assert alerts[2].category == "legal"

    def test_generate_risk_alerts_uses_summary_or_title_for_alert_title(
        self, project_id, analysis_id
    ):
        """Risk alerts should prefer 'summary' over 'title' for alert title."""
        generator = AlertGenerator(project_id=project_id, analysis_id=analysis_id)

        risk_items = [
            {"summary": "Risk summary", "title": "Risk title", "description": "Description", "impact_level": "low", "confidence": 0.7},
            {"title": "Risk title only", "description": "Description", "impact_level": "low", "confidence": 0.7},
            {"description": "No title or summary", "impact_level": "low", "confidence": 0.7},
        ]

        alerts = generator.generate_risk_alerts(risk_items)

        assert alerts[0].title == "Risk summary"  # Prefers summary
        assert alerts[1].title == "Risk title only"  # Falls back to title
        assert alerts[2].title == "Risk identified"  # Falls back to default

    def test_generate_risk_alerts_stores_raw_item_in_metadata(
        self, project_id, analysis_id, sample_risk_items
    ):
        """Risk alerts should store raw risk item in metadata for traceability."""
        generator = AlertGenerator(project_id=project_id, analysis_id=analysis_id)

        alerts = generator.generate_risk_alerts(sample_risk_items)

        for i, alert in enumerate(alerts):
            assert "raw" in alert.alert_metadata
            assert alert.alert_metadata["raw"] == sample_risk_items[i]

    def test_generate_risk_alerts_assigns_project_and_analysis_ids(
        self, project_id, analysis_id, sample_risk_items
    ):
        """Risk alerts should have correct project_id and analysis_id."""
        generator = AlertGenerator(project_id=project_id, analysis_id=analysis_id)

        alerts = generator.generate_risk_alerts(sample_risk_items)

        for alert in alerts:
            assert alert.project_id == project_id
            assert alert.analysis_id == analysis_id
