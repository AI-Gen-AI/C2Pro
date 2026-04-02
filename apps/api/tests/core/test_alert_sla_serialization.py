"""
TS-INT-DB-CLS-001: Alert SLA serialization contract tests.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from src.alerts.router import _serialize_alert
from src.analysis.adapters.persistence.models import Alert
from src.analysis.domain.enums import AlertSeverity, AlertStatus
from src.core.approval import ApprovalStatus


def test_serialize_alert_exposes_sla_policy_and_due_date() -> None:
    created_at = datetime(2026, 4, 1, 8, 30, 0)
    alert = Alert(
        id=uuid4(),
        project_id=uuid4(),
        severity=AlertSeverity.CRITICAL,
        category="LEGAL",
        rule_id="R1",
        title="Missing permit",
        description="Missing permit",
        status=AlertStatus.OPEN,
        approval_status=ApprovalStatus.PENDING,
        affected_entities={},
        alert_metadata={},
        created_at=created_at,
    )

    response = _serialize_alert(alert, uuid4())

    assert response.sla_policy_name == "Critical severity: first response in 2 hours"
    assert response.sla_due_at == created_at + timedelta(hours=2)
