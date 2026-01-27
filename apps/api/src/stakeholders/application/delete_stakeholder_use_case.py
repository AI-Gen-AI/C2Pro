"""
Use case for deleting a stakeholder.
"""
from __future__ import annotations

from uuid import UUID

from src.stakeholders.ports.stakeholder_repository import IStakeholderRepository


class DeleteStakeholderUseCase:
    def __init__(self, repository: IStakeholderRepository):
        self.repository = repository

    async def execute(self, stakeholder_id: UUID) -> None:
        await self.repository.delete(stakeholder_id)
        await self.repository.commit()
