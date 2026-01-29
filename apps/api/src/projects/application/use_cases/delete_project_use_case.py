"""
Delete Project Use Case.

Handles deletion of a project.
"""
from uuid import UUID

import structlog

from src.projects.ports.project_repository import ProjectRepository


logger = structlog.get_logger()


class DeleteProjectUseCase:
    """
    Use case for deleting a project.

    Business rules enforced:
    - Project must exist
    - Tenant isolation
    - (Future: Could add constraints like "cannot delete if has active contracts")
    """

    def __init__(self, repository: ProjectRepository):
        self.repository = repository

    async def execute(self, project_id: UUID, tenant_id: UUID, user_id: UUID) -> bool:
        """
        Delete a project by ID.

        Args:
            project_id: ID of project to delete
            tenant_id: Tenant ID for isolation
            user_id: ID of user performing deletion

        Returns:
            True if deleted, False if not found

        Raises:
            ValueError: If business rules prevent deletion
        """
        # Future business rule: Check if project can be deleted
        # For example, prevent deletion if project has active documents or contracts
        # project = await self.repository.get_by_id(project_id, tenant_id)
        # if project and project.status == ProjectStatus.ACTIVE:
        #     raise ValueError("Cannot delete active project")

        deleted = await self.repository.delete(project_id, tenant_id)

        if deleted:
            logger.info(
                "project_deleted",
                project_id=str(project_id),
                tenant_id=str(tenant_id),
                user_id=str(user_id),
            )
        else:
            logger.warning(
                "project_delete_failed_not_found",
                project_id=str(project_id),
                tenant_id=str(tenant_id),
            )

        return deleted
