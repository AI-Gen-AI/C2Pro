"""
Get Alert Workspace Settings Use Case.
"""
from __future__ import annotations

from uuid import UUID

from src.alerts.application.dtos import AlertWorkspaceSettingsPayload
from src.alerts.application.ports.tenant_repository import ITenantRepository


class GetAlertWorkspaceSettingsUseCase:
    def __init__(self, repository: ITenantRepository) -> None:
        self._repository = repository

    async def execute(self, tenant_id: UUID) -> AlertWorkspaceSettingsPayload:
        """Get alert workspace settings for a tenant."""
        tenant = await self._repository.get_by_id(tenant_id)
        if tenant is None:
            raise ValueError("Tenant not found")

        settings = dict(tenant.settings or {})
        workspace_settings = settings.get("alerts_workspace", {})

        return AlertWorkspaceSettingsPayload.model_validate(
            {
                "rules": workspace_settings.get("rules", []),
                "subscriptions": workspace_settings.get("subscriptions"),
            }
        )
