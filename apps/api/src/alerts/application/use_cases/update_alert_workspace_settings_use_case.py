"""
Update Alert Workspace Settings Use Case.
"""
from __future__ import annotations

from uuid import UUID

from src.alerts.application.dtos import AlertWorkspaceSettingsPayload
from src.alerts.application.ports.tenant_repository import ITenantRepository


class UpdateAlertWorkspaceSettingsUseCase:
    def __init__(self, repository: ITenantRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        tenant_id: UUID,
        payload: AlertWorkspaceSettingsPayload
    ) -> AlertWorkspaceSettingsPayload:
        """Update alert workspace settings for a tenant."""
        tenant = await self._repository.get_by_id(tenant_id)
        if tenant is None:
            raise ValueError("Tenant not found")

        settings = dict(tenant.settings or {})
        settings["alerts_workspace"] = payload.model_dump(mode="json")

        await self._repository.update_settings(tenant_id, settings)
        await self._repository.commit()

        return payload
