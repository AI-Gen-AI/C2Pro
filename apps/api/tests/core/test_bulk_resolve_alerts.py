"""
TS-INT-DB-CLS-001: Bulk alert resolve contract tests.
"""

from __future__ import annotations

import importlib
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.alerts.router import BulkResolveRequest, bulk_resolve_alerts

alerts_router_module = importlib.import_module("src.alerts.router")
from src.analysis.domain.enums import AlertSeverity, AlertStatus
from src.core.approval import ApprovalStatus


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


class _FakeResult:
    def __init__(self, alerts: list[_FakeAlert]) -> None:
        self._alerts = alerts

    def scalars(self) -> _FakeResult:
        return self

    def all(self) -> list[_FakeAlert]:
        return self._alerts


class _FakeSession:
    def __init__(self, alerts: list[_FakeAlert]) -> None:
        self.alerts = alerts
        self.committed = False

    async def execute(self, _query: object) -> _FakeResult:
        return _FakeResult(self.alerts)

    async def commit(self) -> None:
        self.committed = True


class _FakeSessionContext:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FakeSession:
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


@pytest.mark.asyncio
async def test_bulk_resolve_alerts_resolves_selected_alerts_and_records_history(monkeypatch) -> None:
    alerts = [
        _FakeAlert(str(uuid4()), AlertSeverity.HIGH),
        _FakeAlert(str(uuid4()), AlertSeverity.MEDIUM),
    ]
    session = _FakeSession(alerts)
    current_user = SimpleNamespace(id=uuid4(), tenant_id=uuid4())

    monkeypatch.setattr(
        alerts_router_module,
        "get_session_with_tenant",
        lambda _tenant_id: _FakeSessionContext(session),
    )

    response = await bulk_resolve_alerts(
        request=BulkResolveRequest(
            alert_ids=[str(alert.id) for alert in alerts],
            resolution="Validated the grouped recovery plan across the selected alerts.",
            root_cause="schedule_delay",
        ),
        current_user=current_user,
    )

    assert response == {
        "processed_count": 2,
        "status": "resolved",
        "alert_ids": [str(alert.id) for alert in alerts],
    }
    assert session.committed is True
    for alert in alerts:
        assert alert.status == AlertStatus.RESOLVED
        assert alert.resolution_notes == "Validated the grouped recovery plan across the selected alerts."
        assert alert.alert_metadata["root_cause"] == "schedule_delay"
        assert alert.alert_metadata["history"][-1]["action"] == "bulk_resolved"


@pytest.mark.asyncio
async def test_bulk_resolve_alerts_requires_root_cause_for_high_or_critical_selection(monkeypatch) -> None:
    alerts = [_FakeAlert(str(uuid4()), AlertSeverity.HIGH)]
    session = _FakeSession(alerts)
    current_user = SimpleNamespace(id=uuid4(), tenant_id=uuid4())

    monkeypatch.setattr(
        alerts_router_module,
        "get_session_with_tenant",
        lambda _tenant_id: _FakeSessionContext(session),
    )

    with pytest.raises(HTTPException, match="Root cause is required"):
        await bulk_resolve_alerts(
            request=BulkResolveRequest(
                alert_ids=[str(alerts[0].id)],
                resolution="Validated the grouped recovery plan across the selected alerts.",
                root_cause=None,
            ),
            current_user=current_user,
        )
