"""
TS-UA-STK-RACI-GLB-001

Use case for building the global RACI matrix view across all tenant projects.
"""

from __future__ import annotations

from uuid import UUID

from src.projects.ports.project_repository import ProjectRepository
from src.stakeholders.application.dtos import RaciMatrixTaskRow, RaciMatrixViewResponse
from src.stakeholders.application.get_raci_matrix_use_case import GetRaciMatrixUseCase


class GetGlobalRaciMatrixUseCase:
    """Aggregate per-project RACI matrices into the existing global matrix response shape."""

    def __init__(
        self,
        project_repository: ProjectRepository,
        project_matrix_use_case: GetRaciMatrixUseCase,
    ) -> None:
        self.project_repository = project_repository
        self.project_matrix_use_case = project_matrix_use_case

    async def execute(self, tenant_id: UUID) -> RaciMatrixViewResponse:
        projects, _ = await self.project_repository.list(tenant_id=tenant_id, page=1, page_size=1000)
        all_rows: list[RaciMatrixTaskRow] = []

        for project in projects:
            try:
                matrix = await self.project_matrix_use_case.execute(
                    project_id=project.id,
                    tenant_id=tenant_id,
                )
            except ValueError as exc:
                if str(exc) == "project_not_found":
                    continue
                raise
            all_rows.extend(matrix.matrix)

        return RaciMatrixViewResponse(matrix=all_rows)
