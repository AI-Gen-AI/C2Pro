"""
Get Project Use Case.

Retrieves a single project by ID with tenant isolation.
"""
from uuid import UUID

import structlog

from src.projects.domain.models import Project
from src.projects.ports.project_repository import ProjectRepository


logger = structlog.get_logger()


class GetProjectUseCase:
    """
    Use case for retrieving a project by ID.

    Business rules enforced:
    - Tenant isolation (can only access own projects)
    """

    def __init__(self, repository: ProjectRepository):
        self.repository = repository

    async def execute(self, project_id: UUID, tenant_id: UUID) -> Project:
        """
        Get a project by ID.

        Args:
            project_id: The project's unique identifier
            tenant_id: Tenant ID for isolation

        Returns:
            The Project entity

        Raises:
            ValueError: If project not found
        """
        project = await self.repository.get_by_id(project_id, tenant_id)

        if not project:
            raise ValueError(f"Project {project_id} not found")

        logger.info(
            "project_retrieved",
            project_id=str(project_id),
            tenant_id=str(tenant_id),
        )

        return project
