"""
I6 - Alert Payload Contract (Domain)
Test Suite ID: TS-I6-COH-CONTRACT-001
"""

from typing import Any, Optional
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

try:
    from src.modules.coherence.domain.entities import CoherenceAlert, CoherenceAlertEvidence
except ImportError:
    class CoherenceAlertEvidence(dict[str, Any]):
        pass

    class CoherenceAlert(BaseModel):
        alert_id: Any
        type: Any
        severity: Any
        message: Any
        evidence: Any = {}
        triggered_by_rule: Any
        doc_id: Optional[Any] = None
        metadata: dict[str, Any] = {}


def test_i6_coherence_alert_schema_validates_correct_data() -> None:
    """Refers to I6.3: standardized alert payload format accepts valid input."""
    alert_data = {
        "alert_id": uuid4(),
        "type": "Schedule Mismatch",
        "severity": "Critical",
        "message": "Project end date exceeds contractual deadline.",
        "evidence": {
            "scheduled_end": "2024-12-31",
            "actual_end": "2025-01-15",
            "relevant_clauses": [str(uuid4()), str(uuid4())],
        },
        "triggered_by_rule": "ScheduleComplianceRule",
        "doc_id": uuid4(),
        "metadata": {"action_required": "Review timeline"},
    }

    alert = CoherenceAlert(**alert_data)

    assert isinstance(alert.alert_id, UUID)
    assert alert.type == "Schedule Mismatch"
    assert alert.severity == "Critical"
    assert isinstance(alert.evidence, CoherenceAlertEvidence)


def test_i6_coherence_alert_schema_fails_on_invalid_data() -> None:
    """Refers to I6.3: standardized alert payload format rejects invalid input."""
    with pytest.raises(ValidationError):
        CoherenceAlert(
            alert_id="not-a-uuid",
            type=123,
            severity="Unknown",
            message="",
            evidence={"invalid_field": "data"},
            triggered_by_rule=None,
            doc_id=uuid4(),
            metadata={},
        )
