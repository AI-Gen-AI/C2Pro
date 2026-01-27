"""
Use case for listing stakeholders in a project.
"""
from __future__ import annotations

from typing import List, Tuple
from uuid import UUID

from src.stakeholders.domain.models import Stakeholder
from src.stakeholders.ports.stakeholder_repository import IStakeholderRepository


class ListProjectStakeholdersUseCase:
    def __init__(self, repository: IStakeholderRepository):
        self.repository = repository

    async def execute(
        self,
        project_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[Stakeholder], int]:
        return await self.repository.get_stakeholders_by_project(
            project_id=project_id, skip=skip, limit=limit
        )
