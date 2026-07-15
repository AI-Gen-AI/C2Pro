"""
Unit tests for ResolveAlertUseCase.

TS-UD-ALR-RES-001

Tests the use case directly with mocked repository - no HTTP/DB dependencies.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from alerts.application.use_cases.resolve_alert_use_case import (
    AlertNotFoundError,
    ResolveAlertUseCase,
)
from alerts.domain.enums import AlertSeverity, AlertStatus, ApprovalStatus
from alerts.domain.models import Alert


class MockAlertRepository:
    """Mock implementation of IAlertRepository for testing."""

    def __init__(self, alerts: list[Alert] | None = None) -> None:
        self._alerts = {alert.id: alert for alert in (alerts or [])}
        self._saved = []
        self._committed = False

    async def get_by_id(self, alert_id: UUID, tenant_id: UUID) -> Alert | None:
        return self._alerts.get(alert_id)

    async def save(self, alert: Alert) -> None:
        self._saved.append(alert)

    async def commit(self) -> None:
        self._committed = True


def _create_test_alert(
    alert_id: UUID | None = None,
    severity: AlertSeverity = AlertSeverity.LOW,
    title: str = "Test Alert",
) -> Alert:
    return Alert(
        id=alert_id or uuid4(),
        project_id=uuid4(),
        severity=severity,
        category="SCOPE",
        status=AlertStatus.OPEN,
        approval_status=ApprovalStatus.PENDING,
        rule_id="TEST-001",
        title=title,
        description="Test description",
        affected_entities={},
        alert_metadata={},
        created_at=datetime.now(UTC),
    )


class TestResolveAlertUseCaseExecute:
    """Tests for execute method."""

    @pytest.mark.asyncio
    async def test_resolve_alert_sets_status_to_resolved(self) -> None:
        """Test that resolving sets status to RESOLVED."""
        alert = _create_test_alert()
        repository = MockAlertRepository([alert])
        use_case = ResolveAlertUseCase(repository=repository)

        result = await use_case.execute(
            alert_id=alert.id,
            tenant_id=uuid4(),
            user_id=uuid4(),
            resolution="Fixed the issue",
            root_cause=None,
        )

        assert result.status == AlertStatus.RESOLVED.value
        assert result.root_cause is None

    @pytest.mark.asyncio
    async def test_resolve_alert_sets_resolved_by_and_at(self) -> None:
        """Test that resolving sets resolved_by and resolved_at."""
        alert = _create_test_alert()
        repository = MockAlertRepository([alert])
        use_case = ResolveAlertUseCase(repository=repository)
        user_id = uuid4()

        await use_case.execute(
            alert_id=alert.id,
            tenant_id=uuid4(),
            user_id=user_id,
            resolution="Fixed the issue",
            root_cause=None,
        )

        saved_alert = repository._saved[0]
        assert saved_alert.resolved_by == user_id
        assert saved_alert.resolved_at is not None

    @pytest.mark.asyncio
    async def test_resolve_alert_adds_history(self) -> None:
        """Test that resolving adds history entry."""
        alert = _create_test_alert()
        repository = MockAlertRepository([alert])
        use_case = ResolveAlertUseCase(repository=repository)

        await use_case.execute(
            alert_id=alert.id,
            tenant_id=uuid4(),
            user_id=uuid4(),
            resolution="Fixed the issue",
            root_cause=None,
        )

        saved_alert = repository._saved[0]
        history = saved_alert.alert_metadata.get("history", [])
        assert len(history) >= 1
        assert history[-1]["action"] == "resolved"

    @pytest.mark.asyncio
    async def test_resolve_alert_commits_repository(self) -> None:
        """Test that repository is committed after resolve."""
        alert = _create_test_alert()
        repository = MockAlertRepository([alert])
        use_case = ResolveAlertUseCase(repository=repository)

        await use_case.execute(
            alert_id=alert.id,
            tenant_id=uuid4(),
            user_id=uuid4(),
            resolution="Fixed the issue",
            root_cause=None,
        )

        assert repository._committed is True

    @pytest.mark.asyncio
    async def test_resolve_alert_not_found_raises_error(self) -> None:
        """Test that non-existent alert raises AlertNotFoundError."""
        repository = MockAlertRepository([])
        use_case = ResolveAlertUseCase(repository=repository)

        with pytest.raises(AlertNotFoundError):
            await use_case.execute(
                alert_id=uuid4(),
                tenant_id=uuid4(),
                user_id=uuid4(),
                resolution="Fixed",
                root_cause=None,
            )


class TestResolveAlertValidation:
    """Tests for resolution validation."""

    @pytest.mark.asyncio
    async def test_high_alert_requires_min_20_chars_resolution(self) -> None:
        """Test that HIGH severity requires at least 20 character resolution."""
        alert = _create_test_alert(severity=AlertSeverity.HIGH)
        repository = MockAlertRepository([alert])
        use_case = ResolveAlertUseCase(repository=repository)

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await use_case.execute(
                alert_id=alert.id,
                tenant_id=uuid4(),
                user_id=uuid4(),
                resolution="Short",  # Less than 20 chars
                root_cause=None,
            )

        assert "20 characters" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_critical_alert_requires_min_50_chars_resolution(self) -> None:
        """Test that CRITICAL severity requires at least 50 character resolution."""
        alert = _create_test_alert(severity=AlertSeverity.CRITICAL)
        repository = MockAlertRepository([alert])
        use_case = ResolveAlertUseCase(repository=repository)

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await use_case.execute(
                alert_id=alert.id,
                tenant_id=uuid4(),
                user_id=uuid4(),
                resolution="Short",  # Less than 50 chars
                root_cause="cause",
            )

        assert "50 characters" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_low_alert_requires_no_min_resolution(self) -> None:
        """Test that LOW severity requires no minimum resolution length."""
        alert = _create_test_alert(severity=AlertSeverity.LOW)
        repository = MockAlertRepository([alert])
        use_case = ResolveAlertUseCase(repository=repository)

        result = await use_case.execute(
            alert_id=alert.id,
            tenant_id=uuid4(),
            user_id=uuid4(),
            resolution="OK",
            root_cause=None,
        )

        assert result.status == AlertStatus.RESOLVED.value

    @pytest.mark.asyncio
    async def test_high_alert_requires_root_cause(self) -> None:
        """Test that HIGH severity requires root cause."""
        alert = _create_test_alert(severity=AlertSeverity.HIGH)
        repository = MockAlertRepository([alert])
        use_case = ResolveAlertUseCase(repository=repository)

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await use_case.execute(
                alert_id=alert.id,
                tenant_id=uuid4(),
                user_id=uuid4(),
                resolution="A" * 25,  # Sufficient length
                root_cause=None,  # Missing root cause
            )

        assert "Root cause is required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_critical_alert_requires_root_cause(self) -> None:
        """Test that CRITICAL severity requires root cause."""
        alert = _create_test_alert(severity=AlertSeverity.CRITICAL)
        repository = MockAlertRepository([alert])
        use_case = ResolveAlertUseCase(repository=repository)

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await use_case.execute(
                alert_id=alert.id,
                tenant_id=uuid4(),
                user_id=uuid4(),
                resolution="A" * 55,  # Sufficient length
                root_cause=None,  # Missing root cause
            )

        assert "Root cause is required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_medium_alert_does_not_require_root_cause(self) -> None:
        """Test that MEDIUM severity does not require root cause."""
        alert = _create_test_alert(severity=AlertSeverity.MEDIUM)
        repository = MockAlertRepository([alert])
        use_case = ResolveAlertUseCase(repository=repository)

        result = await use_case.execute(
            alert_id=alert.id,
            tenant_id=uuid4(),
            user_id=uuid4(),
            resolution="A" * 15,  # Sufficient length
            root_cause=None,  # Not required
        )

        assert result.status == AlertStatus.RESOLVED.value

    @pytest.mark.asyncio
    async def test_low_alert_does_not_require_root_cause(self) -> None:
        """Test that LOW severity does not require root cause."""
        alert = _create_test_alert(severity=AlertSeverity.LOW)
        repository = MockAlertRepository([alert])
        use_case = ResolveAlertUseCase(repository=repository)

        result = await use_case.execute(
            alert_id=alert.id,
            tenant_id=uuid4(),
            user_id=uuid4(),
            resolution="OK",
            root_cause=None,  # Not required
        )

        assert result.status == AlertStatus.RESOLVED.value


class TestResolveAlertWithRootCause:
    """Tests for root cause handling."""

    @pytest.mark.asyncio
    async def test_root_cause_is_stored_in_metadata(self) -> None:
        """Test that root cause is stored in alert metadata."""
        alert = _create_test_alert(severity=AlertSeverity.HIGH)
        repository = MockAlertRepository([alert])
        use_case = ResolveAlertUseCase(repository=repository)

        await use_case.execute(
            alert_id=alert.id,
            tenant_id=uuid4(),
            user_id=uuid4(),
            resolution="A" * 25,
            root_cause="schedule_delay",
        )

        saved_alert = repository._saved[0]
        assert saved_alert.alert_metadata.get("root_cause") == "schedule_delay"

    @pytest.mark.asyncio
    async def test_root_cause_whitespace_is_trimmed(self) -> None:
        """Test that root cause whitespace is trimmed."""
        alert = _create_test_alert(severity=AlertSeverity.HIGH)
        repository = MockAlertRepository([alert])
        use_case = ResolveAlertUseCase(repository=repository)

        await use_case.execute(
            alert_id=alert.id,
            tenant_id=uuid4(),
            user_id=uuid4(),
            resolution="A" * 25,
            root_cause="  schedule_delay  ",
        )

        saved_alert = repository._saved[0]
        assert saved_alert.alert_metadata.get("root_cause") == "schedule_delay"

    @pytest.mark.asyncio
    async def test_empty_root_cause_becomes_none(self) -> None:
        """Test that empty root cause becomes None."""
        alert = _create_test_alert(severity=AlertSeverity.MEDIUM)
        repository = MockAlertRepository([alert])
        use_case = ResolveAlertUseCase(repository=repository)

        await use_case.execute(
            alert_id=alert.id,
            tenant_id=uuid4(),
            user_id=uuid4(),
            resolution="A" * 15,
            root_cause="   ",
        )

        saved_alert = repository._saved[0]
        # Empty string after strip becomes None
        assert saved_alert.alert_metadata.get("root_cause") is None


class TestResolveAlertResponse:
    """Tests for response format."""

    @pytest.mark.asyncio
    async def test_response_includes_sla_info(self) -> None:
        """Test that SLA policy info is included in response."""
        alert = _create_test_alert(severity=AlertSeverity.CRITICAL)
        repository = MockAlertRepository([alert])
        use_case = ResolveAlertUseCase(repository=repository)

        result = await use_case.execute(
            alert_id=alert.id,
            tenant_id=uuid4(),
            user_id=uuid4(),
            resolution="A" * 55,
            root_cause="cause",
        )

        assert result.sla_policy_name is not None
        assert "2 hours" in result.sla_policy_name

    @pytest.mark.asyncio
    async def test_response_includes_tenant_id(self) -> None:
        """Test that tenant_id is included in response."""
        alert = _create_test_alert()
        repository = MockAlertRepository([alert])
        use_case = ResolveAlertUseCase(repository=repository)
        tenant_id = uuid4()

        result = await use_case.execute(
            alert_id=alert.id,
            tenant_id=tenant_id,
            user_id=uuid4(),
            resolution="Fixed",
            root_cause=None,
        )

        assert result.tenant_id == tenant_id
