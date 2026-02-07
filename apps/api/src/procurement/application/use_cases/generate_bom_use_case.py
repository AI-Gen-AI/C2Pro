"""
Generate BOM Use Case.

Refers to Suite ID: TS-UA-PROC-UC-001.
"""

from __future__ import annotations

from uuid import UUID

from src.procurement.domain.models import BOMItem, BudgetItem
from src.procurement.ports.bom_generation_service import IBOMGenerationService
from src.procurement.ports.bom_repository import IBOMRepository
from src.procurement.ports.wbs_repository import IWBSRepository


class GenerateBOMUseCase:
    """Refers to Suite ID: TS-UA-PROC-UC-001."""

    def __init__(
        self,
        *,
        wbs_repository: IWBSRepository,
        bom_repository: IBOMRepository,
        bom_generation_service: IBOMGenerationService,
    ) -> None:
        self.wbs_repository = wbs_repository
        self.bom_repository = bom_repository
        self.bom_generation_service = bom_generation_service

    async def execute(
        self,
        *,
        project_id: UUID,
        budget_items: list[BudgetItem],
        tenant_id: UUID,
    ) -> list[BOMItem]:
        """
        Generate BOM items for a project and persist them.
        """
        wbs_items = await self.wbs_repository.get_by_project(project_id, tenant_id)
        if not wbs_items:
            return []

        bom_items = await self.bom_generation_service.generate_bom(
            wbs_items=wbs_items,
            budget_items=budget_items,
        )
        if not bom_items:
            return []

        return await self.bom_repository.bulk_create(bom_items)
