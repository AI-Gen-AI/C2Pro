"""
Use case for building the RACI matrix view for a project.
"""
from __future__ import annotations

from uuid import UUID

from src.procurement.ports.wbs_repository import IWBSRepository
from src.projects.ports.project_repository import ProjectRepository
from src.stakeholders.application.dtos import (
    RaciMatrixAssignment,
    RaciMatrixTaskRow,
    RaciMatrixViewResponse,
)
from src.stakeholders.domain.models import RACIRole
from src.stakeholders.ports.stakeholder_repository import IStakeholderRepository


ROLE_LABELS = {
    RACIRole.RESPONSIBLE: "RESPONSIBLE",
    RACIRole.ACCOUNTABLE: "ACCOUNTABLE",
    RACIRole.CONSULTED: "CONSULTED",
    RACIRole.INFORMED: "INFORMED",
}


class GetRaciMatrixUseCase:
    def __init__(
        self,
        stakeholder_repository: IStakeholderRepository,
        wbs_repository: IWBSRepository,
        project_repository: ProjectRepository,
    ) -> None:
        self.stakeholder_repository = stakeholder_repository
        self.wbs_repository = wbs_repository
        self.project_repository = project_repository

    async def execute(self, project_id: UUID, tenant_id: UUID) -> RaciMatrixViewResponse:
        project_exists = await self.project_repository.exists_by_id(
            project_id=project_id,
            tenant_id=tenant_id,
        )
        if not project_exists:
            raise ValueError("project_not_found")

        wbs_items = await self.wbs_repository.get_by_project(project_id, tenant_id)
        if not wbs_items:
            return RaciMatrixViewResponse(matrix=[])

        assignments = await self.stakeholder_repository.list_raci_assignments(project_id)
        assignments_by_task: dict[UUID, list[RaciMatrixAssignment]] = {}
        for assignment in assignments:
            assignments_by_task.setdefault(assignment.wbs_item_id, []).append(
                RaciMatrixAssignment(
                    stakeholder_id=assignment.stakeholder_id,
                    role=ROLE_LABELS.get(assignment.raci_role, assignment.raci_role.value),
                    is_verified=assignment.manually_verified,
                )
            )

        matrix = [
            RaciMatrixTaskRow(
                task_id=item.id,
                task_name=item.name,
                assignments=assignments_by_task.get(item.id, []),
            )
            for item in wbs_items
        ]

        return RaciMatrixViewResponse(matrix=matrix)
