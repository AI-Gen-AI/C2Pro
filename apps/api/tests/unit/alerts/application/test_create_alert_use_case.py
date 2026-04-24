"""
TS-E2E-FLW-JRN-001

Unit tests for CreateAlertUseCase lifecycle history behavior.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from alerts.application.use_cases.create_alert_use_case import CreateAlertUseCase
from alerts.domain.models import Alert


class MockAlertRepository:
    """Mock implementation of IAlertRepository for testing."""

    def __init__(self) -> None:
        self.created_alert: Alert | None = None
        self.created_tenant_id: UUID | None = None
        self.committed = False

    async def create(self, alert: Alert, tenant_id: UUID | None = None) -> Alert:
        self.created_alert = alert
        self.created_tenant_id = tenant_id
        return alert

    async def commit(self) -> None:
        self.committed = True


@pytest.mark.asyncio
async def test_execute_records_created_history_entry() -> None:
    """Created alerts should include an initial lifecycle history event."""
    repository = MockAlertRepository()
    use_case = CreateAlertUseCase(repository=repository)
    tenant_id = uuid4()
    user_id = uuid4()

    alert = await use_case.execute(
        project_id=uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        rule_code="R-JRN-001",
        category="TIME",
        severity="high",
        message="Schedule mismatch detected against contractual deadline",
        affected_entities={"contract_end_date": "2026-12-31"},
    )

    assert repository.created_tenant_id == tenant_id
    assert repository.committed is True
    history = alert.alert_metadata["history"]
    assert len(history) == 1
    assert history[0]["action"] == "created"
    assert history[0]["user_id"] == str(user_id)
