"""
Unit tests for ListAlertsUseCase.

TS-UD-ALR-LST-001

Tests the use case directly with mocked repository - no HTTP/DB dependencies.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from alerts.application.use_cases.list_alerts_use_case import ListAlertsUseCase
from alerts.domain.enums import AlertSeverity, AlertStatus, ApprovalStatus
from alerts.domain.models import Alert


class MockAlertRepository:
    """Mock implementation of IAlertRepository for testing."""

    def __init__(self, alerts: list[Alert] | None = None) -> None:
        self._alerts = alerts or []
        self._list_for_project_calls: list[dict] = []
        self._list_for_tenant_calls: list[dict] = []

    async def list_for_project(
        self,
        project_id: UUID,
        tenant_id: UUID,
        status: AlertStatus | None = None,
        category: str | None = None,
        severity: AlertSeverity | None = None,
    ) -> list[Alert]:
        self._list_for_project_calls.append({
            "project_id": project_id,
            "tenant_id": tenant_id,
            "status": status,
            "category": category,
            "severity": severity,
        })
        result = [a for a in self._alerts if a.project_id == project_id]
        if status:
            result = [a for a in result if a.status == status]
        if severity:
            result = [a for a in result if a.severity == severity]
        return result

    async def list_for_tenant(
        self,
        tenant_id: UUID,
        project_id: UUID | None = None,
        document_id: UUID | None = None,
        status: AlertStatus | None = None,
        category: str | None = None,
        severity: AlertSeverity | None = None,
    ) -> list[Alert]:
        self._list_for_tenant_calls.append({
            "tenant_id": tenant_id,
            "project_id": project_id,
            "document_id": document_id,
            "status": status,
            "category": category,
            "severity": severity,
        })
        return self._alerts


def _create_test_alert(
    alert_id: UUID | None = None,
    project_id: UUID | None = None,
    severity: AlertSeverity = AlertSeverity.HIGH,
    status: AlertStatus = AlertStatus.OPEN,
    title: str = "Test Alert",
) -> Alert:
    return Alert(
        id=alert_id or uuid4(),
        project_id=project_id or uuid4(),
        severity=severity,
        category="SCOPE",
        status=status,
        approval_status=ApprovalStatus.PENDING,
        rule_id="TEST-001",
        title=title,
        description="Test description",
        affected_entities={"items": ["doc-1"]},
        alert_metadata={},
        created_at=datetime.now(UTC),
    )


class TestListAlertsUseCaseExecuteForProject:
    """Tests for execute_for_project method."""

    @pytest.mark.asyncio
    async def test_returns_alerts_for_project(self) -> None:
        """Test that alerts are returned for the specified project."""
        project_id = uuid4()
        tenant_id = uuid4()
        alert1 = _create_test_alert(project_id=project_id, title="Alert 1")
        alert2 = _create_test_alert(project_id=project_id, title="Alert 2")
        other_project = uuid4()
        alert3 = _create_test_alert(project_id=other_project, title="Alert 3")

        repository = MockAlertRepository(alerts=[alert1, alert2, alert3])
        use_case = ListAlertsUseCase(repository=repository)

        result = await use_case.execute_for_project(
            project_id=project_id,
            tenant_id=tenant_id,
        )

        assert result.total == 2
        assert len(result.items) == 2
        assert result.items[0].message == "Alert 1"
        assert result.items[1].message == "Alert 2"

    @pytest.mark.asyncio
    async def test_filters_by_status(self) -> None:
        """Test that status filter is applied."""
        project_id = uuid4()
        tenant_id = uuid4()
        open_alert = _create_test_alert(
            project_id=project_id, status=AlertStatus.OPEN, title="Open Alert"
        )
        resolved_alert = _create_test_alert(
            project_id=project_id, status=AlertStatus.RESOLVED, title="Resolved Alert"
        )

        repository = MockAlertRepository(alerts=[open_alert, resolved_alert])
        use_case = ListAlertsUseCase(repository=repository)

        result = await use_case.execute_for_project(
            project_id=project_id,
            tenant_id=tenant_id,
            status="open",
        )

        assert result.total == 1
        assert result.items[0].message == "Open Alert"

    @pytest.mark.asyncio
    async def test_filters_by_severity(self) -> None:
        """Test that severity filter is applied."""
        project_id = uuid4()
        tenant_id = uuid4()
        critical_alert = _create_test_alert(
            project_id=project_id, severity=AlertSeverity.CRITICAL, title="Critical"
        )
        low_alert = _create_test_alert(
            project_id=project_id, severity=AlertSeverity.LOW, title="Low"
        )

        repository = MockAlertRepository(alerts=[critical_alert, low_alert])
        use_case = ListAlertsUseCase(repository=repository)

        result = await use_case.execute_for_project(
            project_id=project_id,
            tenant_id=tenant_id,
            severity="critical",
        )

        assert result.total == 1
        assert result.items[0].message == "Critical"

    @pytest.mark.asyncio
    async def test_returns_empty_for_no_matching_alerts(self) -> None:
        """Test that empty response is returned when no alerts match."""
        project_id = uuid4()
        tenant_id = uuid4()
        other_project = uuid4()
        alert = _create_test_alert(project_id=other_project)

        repository = MockAlertRepository(alerts=[alert])
        use_case = ListAlertsUseCase(repository=repository)

        result = await use_case.execute_for_project(
            project_id=project_id,
            tenant_id=tenant_id,
        )

        assert result.total == 0
        assert len(result.items) == 0


class TestListAlertsUseCaseExecuteForTenant:
    """Tests for execute_for_tenant method."""

    @pytest.mark.asyncio
    async def test_returns_all_alerts_for_tenant(self) -> None:
        """Test that all alerts are returned for tenant."""
        tenant_id = uuid4()
        project1 = uuid4()
        project2 = uuid4()
        alert1 = _create_test_alert(project_id=project1, title="Alert 1")
        alert2 = _create_test_alert(project_id=project2, title="Alert 2")

        repository = MockAlertRepository(alerts=[alert1, alert2])
        use_case = ListAlertsUseCase(repository=repository)

        result = await use_case.execute_for_tenant(tenant_id=tenant_id)

        assert result.total == 2
        assert len(result.items) == 2

    @pytest.mark.asyncio
    async def test_passes_filters_to_repository(self) -> None:
        """Test that filters are passed to repository."""
        tenant_id = uuid4()
        alert = _create_test_alert()

        repository = MockAlertRepository(alerts=[alert])
        use_case = ListAlertsUseCase(repository=repository)

        await use_case.execute_for_tenant(
            tenant_id=tenant_id,
            status="open",
            category="SCOPE",
            severity="high",
        )

        assert len(repository._list_for_tenant_calls) == 1
        call = repository._list_for_tenant_calls[0]
        assert call["tenant_id"] == tenant_id
        assert call["status"] == AlertStatus.OPEN
        assert call["category"] == "SCOPE"
        assert call["severity"] == AlertSeverity.HIGH


class TestListAlertsUseCaseResponseFormat:
    """Tests for response DTO format."""

    @pytest.mark.asyncio
    async def test_response_includes_sla_info(self) -> None:
        """Test that SLA policy info is included in response."""
        project_id = uuid4()
        tenant_id = uuid4()
        alert = _create_test_alert(
            project_id=project_id,
            severity=AlertSeverity.CRITICAL,
        )

        repository = MockAlertRepository(alerts=[alert])
        use_case = ListAlertsUseCase(repository=repository)

        result = await use_case.execute_for_project(
            project_id=project_id,
            tenant_id=tenant_id,
        )

        assert result.items[0].sla_policy_name is not None
        assert "2 hours" in result.items[0].sla_policy_name

    @pytest.mark.asyncio
    async def test_response_includes_tenant_id(self) -> None:
        """Test that tenant_id is included in response."""
        project_id = uuid4()
        tenant_id = uuid4()
        alert = _create_test_alert(project_id=project_id)

        repository = MockAlertRepository(alerts=[alert])
        use_case = ListAlertsUseCase(repository=repository)

        result = await use_case.execute_for_project(
            project_id=project_id,
            tenant_id=tenant_id,
        )

        assert result.items[0].tenant_id == tenant_id

    @pytest.mark.asyncio
    async def test_response_uses_rule_id_as_code(self) -> None:
        """Test that rule_id is used as rule_code in response."""
        project_id = uuid4()
        tenant_id = uuid4()
        alert = _create_test_alert(project_id=project_id)
        alert.rule_id = "BUD-001"

        repository = MockAlertRepository(alerts=[alert])
        use_case = ListAlertsUseCase(repository=repository)

        result = await use_case.execute_for_project(
            project_id=project_id,
            tenant_id=tenant_id,
        )

        assert result.items[0].rule_code == "BUD-001"

    @pytest.mark.asyncio
    async def test_response_defaults_rule_code_for_none(self) -> None:
        """Test that AI_EXTRACTED is used when rule_id is None."""
        project_id = uuid4()
        tenant_id = uuid4()
        alert = _create_test_alert(project_id=project_id)
        alert.rule_id = None

        repository = MockAlertRepository(alerts=[alert])
        use_case = ListAlertsUseCase(repository=repository)

        result = await use_case.execute_for_project(
            project_id=project_id,
            tenant_id=tenant_id,
        )

        assert result.items[0].rule_code == "AI_EXTRACTED"
