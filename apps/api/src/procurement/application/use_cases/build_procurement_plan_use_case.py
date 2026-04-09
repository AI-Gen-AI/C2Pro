"""
TS-I9-PROC-UC-003

Use case for procurement planning orchestration.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from src.procurement.application.dtos import PlanningDecision
from src.procurement.application.planning_service import ProcurementPlanningService


class BuildProcurementPlanUseCase:
    """Wrap procurement planning service logic behind a use-case boundary for HTTP adapters."""

    def __init__(self, planning_service: ProcurementPlanningService) -> None:
        self.planning_service = planning_service

    async def execute(
        self,
        *,
        project_id: UUID,
        tenant_id: UUID,
        required_on_site: date | datetime,
    ) -> PlanningDecision:
        return await self.planning_service.build_procurement_plan(
            project_id=project_id,
            tenant_id=tenant_id,
            required_on_site=required_on_site,
        )
