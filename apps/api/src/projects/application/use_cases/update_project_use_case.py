"""
Update Project Use Case.

Handles updating an existing project with business rule validation.
"""
from datetime import datetime
from uuid import UUID

import structlog

from src.projects.domain.models import Project, ProjectStatus, ProjectType
from src.projects.ports.project_repository import ProjectRepository


logger = structlog.get_logger()


class UpdateProjectUseCase:
    """
    Use case for updating an existing project.

    Business rules enforced:
    - Project must exist
    - Project code must be unique (if changed)
    - Tenant isolation
    """

    def __init__(self, repository: ProjectRepository):
        self.repository = repository

    async def execute(
        self,
        project_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        name: str | None = None,
        description: str | None = None,
        code: str | None = None,
        project_type: ProjectType | None = None,
        status: ProjectStatus | None = None,
        estimated_budget: float | None = None,
        currency: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> Project:
        """
        Update an existing project.

        Only provided fields will be updated (partial update).

        Args:
            project_id: ID of project to update
            tenant_id: Tenant ID for isolation
            user_id: ID of user making the update
            name: Optional new name
            description: Optional new description
            code: Optional new code
            project_type: Optional new project type
            status: Optional new status
            estimated_budget: Optional new budget
            currency: Optional new currency
            start_date: Optional new start date
            end_date: Optional new end date

        Returns:
            The updated Project entity

        Raises:
            ValueError: If project not found or business rules violated
        """
        # Fetch existing project
        project = await self.repository.get_by_id(project_id, tenant_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        # Check for duplicate code if changing
        if code and code != project.code:
            exists = await self.repository.exists_by_code(code, tenant_id, exclude_id=project_id)
            if exists:
                raise ValueError(f"Project with code '{code}' already exists")

        # Update fields (only if provided)
        if name is not None:
            if not name.strip():
                raise ValueError("Project name cannot be empty")
            project.name = name.strip()

        if description is not None:
            project.description = description

        if code is not None:
            project.code = code

        if project_type is not None:
            project.project_type = project_type

        if status is not None:
            project.status = status

        if estimated_budget is not None:
            project.estimated_budget = estimated_budget

        if currency is not None:
            project.currency = currency

        if start_date is not None:
            project.start_date = start_date

        if end_date is not None:
            project.end_date = end_date

        # Update timestamp
        project.updated_at = datetime.utcnow()

        # Persist
        updated_project = await self.repository.update(project)

        logger.info(
            "project_updated",
            project_id=str(project_id),
            tenant_id=str(tenant_id),
            user_id=str(user_id),
        )

        return updated_project
