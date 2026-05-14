"""
TS-INT-DB-CLS-001: Bulk alert resolve contract tests.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.alerts.application.use_cases.bulk_resolve_alerts_use_case import (
    BulkResolveAlertsUseCase,
)
from src.alerts.domain.enums import AlertSeverity, AlertStatus, ApprovalStatus


class _FakeAlert:
    def __init__(self, alert_id: str, severity: AlertSeverity) -> None:
        self.id = uuid4() if alert_id == "uuid" else alert_id
        self.project_id = uuid4()
        self.severity = severity
        self.category = "LEGAL"
        self.rule_id = "R1"
        self.title = f"Alert {alert_id}"
        self.description = f"Alert {alert_id}"
        self.status = AlertStatus.OPEN
        self.approval_status = ApprovalStatus.PENDING
        self.affected_entities = {}
        self.alert_metadata: dict = {}
        self.reviewed_by = None
        self.reviewed_at = None
        self.created_at = datetime(2026, 4, 2, 9, 0, 0)
        self.resolved_at = None
        self.resolved_by = None
        self.resolution_notes = None


class _FakeResolveAlertUseCase:
    def __init__(self, alerts: list[_FakeAlert]) -> None:
        self.alerts = {str(alert.id): alert for alert in alerts}
        self.calls: list[dict] = []

    async def execute(self, alert_id, tenant_id, user_id, resolution, root_cause):
        alert = self.alerts[str(alert_id)]
        if alert.severity in {AlertSeverity.CRITICAL, AlertSeverity.HIGH} and not root_cause:
            raise HTTPException(status_code=400, detail="Root cause is required for high or critical alerts")
        alert.status = AlertStatus.RESOLVED
        alert.resolution_notes = resolution
        alert.alert_metadata["root_cause"] = root_cause
        alert.alert_metadata.setdefault("history", []).append({"action": "resolved"})
        self.calls.append(
            {
                "alert_id": alert_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "resolution": resolution,
                "root_cause": root_cause,
            }
        )
        return alert


@pytest.mark.asyncio
async def test_bulk_resolve_alerts_resolves_selected_alerts_and_records_history(monkeypatch) -> None:
    alerts = [
        _FakeAlert(str(uuid4()), AlertSeverity.HIGH),
        _FakeAlert(str(uuid4()), AlertSeverity.MEDIUM),
    ]
    tenant_id = uuid4()
    user_id = uuid4()
    resolve_use_case = _FakeResolveAlertUseCase(alerts)
    use_case = BulkResolveAlertsUseCase(resolve_use_case=resolve_use_case)

    response = await use_case.execute(
        alert_ids=[str(alert.id) for alert in alerts],
        tenant_id=tenant_id,
        user_id=user_id,
        resolution="Validated the grouped recovery plan across the selected alerts.",
        root_cause="schedule_delay",
    )

    assert response.processed_count == 2
    assert response.status == "resolved"
    assert response.alert_ids == [str(alert.id) for alert in alerts]
    assert len(resolve_use_case.calls) == 2
    for alert in alerts:
        assert alert.status == AlertStatus.RESOLVED
        assert alert.resolution_notes == "Validated the grouped recovery plan across the selected alerts."
        assert alert.alert_metadata["root_cause"] == "schedule_delay"
        assert alert.alert_metadata["history"][-1]["action"] == "resolved"


@pytest.mark.asyncio
async def test_bulk_resolve_alerts_requires_root_cause_for_high_or_critical_selection(monkeypatch) -> None:
    alerts = [_FakeAlert(str(uuid4()), AlertSeverity.HIGH)]
    use_case = BulkResolveAlertsUseCase(resolve_use_case=_FakeResolveAlertUseCase(alerts))

    with pytest.raises(HTTPException, match="Root cause is required"):
        await use_case.execute(
            alert_ids=[str(alerts[0].id)],
            tenant_id=uuid4(),
            user_id=uuid4(),
            resolution="Validated the grouped recovery plan across the selected alerts.",
            root_cause=None,
        )
