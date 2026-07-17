"""
Use case for deleting a stakeholder.
"""
from __future__ import annotations

from uuid import UUID

from src.core.tenants.types import require_tenant_id
from src.stakeholders.ports.stakeholder_repository import IStakeholderRepository


class DeleteStakeholderUseCase:
    def __init__(self, repository: IStakeholderRepository):
        self.repository = repository

    async def execute(self, stakeholder_id: UUID, tenant_id: UUID) -> None:
        scoped_tenant_id = require_tenant_id(tenant_id)
        await self.repository.delete(stakeholder_id, tenant_id=scoped_tenant_id)
        await self.repository.commit()
