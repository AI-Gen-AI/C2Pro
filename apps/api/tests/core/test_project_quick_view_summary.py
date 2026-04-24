
"""Test Suite ID: TASK-1469."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.analysis.domain.enums import AlertSeverity, AlertStatus
from src.core.approval import ApprovalStatus
from src.projects.adapters.http import router as projects_router_module


@dataclass
class _FakeProject:
    id: object
    tenant_id: object
    name: str
    code: str | None
    description: str | None
    project_type: str
    status: str
    coherence_score: float | None
    estimated_budget: float | None
    currency: str
    metadata_json: dict
    created_at: datetime
    updated_at: datetime
    last_analysis_at: datetime | None = None


@dataclass
class _FakeAlert:
    id: object
    project_id: object
    severity: AlertSeverity
    status: AlertStatus
    title: str
    created_at: datetime
    category: str = "LEGAL"
    rule_id: str = "R-001"
    description: str = "Alert description"
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    alert_metadata: dict | None = None


class _FakeResult:
    def __init__(self, items):
        self._items = items

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def scalars(self):
        return self

    def all(self):
        return list(self._items)


class _FakeSession:
    def __init__(self, project, alerts):
        self.project = project
        self.alerts = alerts

    async def execute(self, query):
        query_text = str(query)
        if "FROM projects" in query_text:
            return _FakeResult([self.project] if self.project else [])
        if "FROM alerts" in query_text:
            return _FakeResult(self.alerts)
        raise AssertionError(f"Unexpected query: {query_text}")


class _FakeSessionContext:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_get_project_summary_returns_ranked_open_alerts(monkeypatch) -> None:
    project_id = uuid4()
    tenant_id = uuid4()
    now = datetime.now(UTC)
    project = _FakeProject(
        id=project_id,
        tenant_id=tenant_id,
        name="Atlas Ridge",
        code="ATR-500",
        description="Phase one delivery",
        project_type="engineering",
        status="active",
        coherence_score=87.0,
        estimated_budget=250000.0,
        currency="USD",
        metadata_json={"version": 3, "client_name": "Client Corp"},
        created_at=now - timedelta(days=3),
        updated_at=now,
    )
    alerts = [
        _FakeAlert(
            id=uuid4(),
            project_id=project_id,
            severity=AlertSeverity.MEDIUM,
            status=AlertStatus.OPEN,
            title="Budget drift detected",
            created_at=now - timedelta(hours=2),
        ),
        _FakeAlert(
            id=uuid4(),
            project_id=project_id,
            severity=AlertSeverity.CRITICAL,
            status=AlertStatus.OPEN,
            title="Permit missing",
            created_at=now - timedelta(hours=1),
        ),
        _FakeAlert(
            id=uuid4(),
            project_id=project_id,
            severity=AlertSeverity.HIGH,
            status=AlertStatus.RESOLVED,
            title="Recovered schedule conflict",
            created_at=now - timedelta(hours=3),
        ),
    ]

    monkeypatch.setattr(
        projects_router_module,
        "get_session_with_tenant",
        lambda tenant: _FakeSessionContext(_FakeSession(project, alerts)),
    )

    response = await projects_router_module.get_project_summary(
        project_id=project_id,
        current_user=SimpleNamespace(tenant_id=tenant_id),
    )

    assert response.project_id == project_id
    assert response.coherence_score == 87.0
    assert response.open_alert_count == 2
    assert response.critical_alert_count == 1
    assert [alert.title for alert in response.top_alerts] == [
        "Permit missing",
        "Budget drift detected",
    ]


@pytest.mark.asyncio
async def test_get_project_summary_raises_404_for_other_tenant(monkeypatch) -> None:
    tenant_id = uuid4()
    project_id = uuid4()

    monkeypatch.setattr(
        projects_router_module,
        "get_session_with_tenant",
        lambda tenant: _FakeSessionContext(_FakeSession(None, [])),
    )

    with pytest.raises(projects_router_module.HTTPException) as exc_info:
        await projects_router_module.get_project_summary(
            project_id=project_id,
            current_user=SimpleNamespace(tenant_id=tenant_id),
        )

    assert exc_info.value.status_code == 404
