"""
Alert Repository Port.

Interface for alert persistence operations.
Refers to Suite ID: TS-BUG-ALRT-IMPORT-001.
"""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.alerts.domain.enums import AlertSeverity, AlertStatus
from src.alerts.domain.models import Alert


class IAlertRepository(Protocol):
    """Repository interface for Alert persistence."""

    async def get_by_id(self, alert_id: UUID, tenant_id: UUID) -> Alert | None:
        """Get alert by ID with tenant isolation."""
        ...

    async def list_for_project(
        self,
        project_id: UUID,
        tenant_id: UUID,
        status: AlertStatus | None = None,
        category: str | None = None,
        severity: AlertSeverity | None = None,
    ) -> list[Alert]:
        """List alerts for a project with filters."""
        ...

    async def list_for_tenant(
        self,
        tenant_id: UUID,
        project_id: UUID | None = None,
        document_id: UUID | None = None,
        status: AlertStatus | None = None,
        category: str | None = None,
        severity: AlertSeverity | None = None,
    ) -> list[Alert]:
        """List alerts for a tenant with optional filters."""
        ...

    async def create(self, alert: Alert, tenant_id: UUID | None = None) -> Alert:
        """Create a new alert with tenant verification."""
        ...

    async def save(self, alert: Alert, tenant_id: UUID | None = None) -> None:
        """Save changes to an alert with tenant verification."""
        ...

    async def delete(self, alert_id: UUID, tenant_id: UUID) -> bool:
        """Delete an alert with tenant isolation."""
        ...

    async def commit(self) -> None:
        """Commit pending changes."""
        ...
