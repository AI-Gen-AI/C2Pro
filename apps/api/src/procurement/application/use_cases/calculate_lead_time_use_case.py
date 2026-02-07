"""
Calculate Lead Time Use Case.

Refers to Suite ID: TS-UA-PROC-UC-002.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from src.procurement.domain.lead_time_calculator import LeadTimeResult
from src.procurement.ports.bom_repository import IBOMRepository
from src.procurement.ports.lead_time_calculator import ILeadTimeCalculator


class CalculateLeadTimeUseCase:
    """Refers to Suite ID: TS-UA-PROC-UC-002."""

    def __init__(
        self,
        *,
        bom_repository: IBOMRepository,
        lead_time_calculator: ILeadTimeCalculator,
    ) -> None:
        self.bom_repository = bom_repository
        self.lead_time_calculator = lead_time_calculator

    async def execute(
        self,
        *,
        project_id: UUID,
        required_on_site: date,
        tenant_id: UUID,
    ) -> dict[UUID, LeadTimeResult]:
        """
        Calculate lead times for all BOM items in a project.
        """
        bom_items = await self.bom_repository.get_by_project(project_id, tenant_id)
        if not bom_items:
            return {}

        results: dict[UUID, LeadTimeResult] = {}
        for bom_item in bom_items:
            result = await self.lead_time_calculator.calculate_lead_time(
                bom_item=bom_item,
                required_on_site=required_on_site,
            )
            if result is None:
                continue
            results[bom_item.id] = result

        return results
