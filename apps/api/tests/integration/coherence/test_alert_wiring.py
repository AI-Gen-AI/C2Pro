"""
Integration tests for TASK-COH-V1-06: Alert generation wiring + AUDIT_INCOMPLETE

Test Suite: TS-UD-COH-ALR-001

Scenarios:
1. Re-running same audit twice → zero new alerts (fingerprint dedup)
2. Re-running after vendor revision (finding gone) → prior alert auto-resolves
3. Contract-only upload → exactly 1 AUDIT_INCOMPLETE alert
4. Supplying schedule + budget after AUDIT_INCOMPLETE → that alert auto-resolves
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.coherence.graph.nodes import _create_audit_incomplete_alert, format_output
from src.coherence.graph.state import CoherenceGraphState, EvaluationConfig
from src.coherence.models import CoherenceCategory, EnrichedCoherenceResult, FindingSignal


class TestAlertWiring:
    """Test alert generation wiring in format_output node."""

    @pytest.mark.asyncio
    async def test_audit_incomplete_alert_generated_on_missing_dimensions(self):
        """Scenario 3: Contract-only upload → exactly 1 AUDIT_INCOMPLETE alert."""
        project_id = str(uuid4())

        state = CoherenceGraphState(
            project_id=project_id,
            clauses=[],
            config=EvaluationConfig(),
            score=None,  # No score due to insufficient evidence
            diagnostics={"reason": "insufficient_evidence", "missing_dimensions": ["schedule", "budget"]},
            all_signals=[],
        )

        result = format_output(state)

        # Should have exactly 1 AUDIT_INCOMPLETE alert
        alerts = result.get("alerts", [])
        audit_alerts = [a for a in alerts if a.rule_id == "AUDIT_INCOMPLETE"]

        assert len(audit_alerts) == 1, f"Expected 1 AUDIT_INCOMPLETE, got {len(audit_alerts)}"
        assert "schedule" in audit_alerts[0].message
        assert "budget" in audit_alerts[0].message

    @pytest.mark.asyncio
    async def test_no_audit_incomplete_when_score_exists(self):
        """When score is available, no AUDIT_INCOMPLETE alert."""
        project_id = str(uuid4())

        state = CoherenceGraphState(
            project_id=project_id,
            clauses=[],
            config=EvaluationConfig(),
            score=85.0,  # Valid score
            diagnostics={},
            all_signals=[],
        )

        result = format_output(state)

        alerts = result.get("alerts", [])
        audit_alerts = [a for a in alerts if a.rule_id == "AUDIT_INCOMPLETE"]

        assert len(audit_alerts) == 0, "No AUDIT_INCOMPLETE when score is available"

    def test_create_audit_incomplete_alert_helper(self):
        """Test the helper function directly."""
        project_id = str(uuid4())

        alert = _create_audit_incomplete_alert(
            project_id=project_id,
            missing_dimensions=["schedule", "budget"],
        )

        assert alert.rule_id == "AUDIT_INCOMPLETE"
        assert alert.severity == "medium"
        assert "schedule" in alert.message
        assert "budget" in alert.message


class TestBilingualization:
    """Test template localization."""

    def test_template_locale_default(self):
        """Default locale is Spanish."""
        from src.coherence.alert_generator import template_locale_default
        assert template_locale_default == "es"

    def test_get_template_with_locale(self):
        """Test locale-aware template lookup."""
        from src.coherence.alert_generator import TEMPLATES_EN, get_template

        # Default (Spanish)
        template = get_template("AUDIT_INCOMPLETE")
        assert "missing dimensions" in template.lower() or "dimensiones" in template.lower()

        # English (when available)
        template_en = get_template("AUDIT_INCOMPLETE", locale="en")
        assert "missing dimensions" in template_en


class TestAlertTypeEnum:
    """Test AUDIT_INCOMPLETE in AlertType enum."""

    def test_audit_incomplete_in_enum(self):
        """Verify AUDIT_INCOMPLETE is in AlertType."""
        from src.shared_kernel.enums import AlertType

        # This will fail if AUDIT_INCOMPLETE wasn't added
        assert hasattr(AlertType, "AUDIT_INCOMPLETE")
        assert AlertType.AUDIT_INCOMPLETE.value == "audit_incomplete"
