"""
Create Project Use Case.

Handles the creation of a new project with business rule validation.
"""
from datetime import datetime
from uuid import UUID, uuid4

import structlog

from src.projects.domain.models import Project, ProjectStatus, ProjectType
from src.projects.ports.project_repository import ProjectRepository


logger = structlog.get_logger()


class CreateProjectUseCase:
    """
    Use case for creating a new project.

    Business rules enforced:
    - Project code must be unique within tenant
    - Name is required
    - Default status is DRAFT
    """

    def __init__(self, repository: ProjectRepository):
        self.repository = repository

    async def execute(
        self,
        tenant_id: UUID,
        user_id: UUID,
        name: str,
        description: str | None = None,
        code: str | None = None,
        project_type: ProjectType = ProjectType.CONSTRUCTION,
        estimated_budget: float | None = None,
        currency: str = "EUR",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> Project:
        """
        Create a new project.

        Args:
            tenant_id: Tenant ID for multi-tenancy
            user_id: ID of user creating the project
            name: Project name (required)
            description: Optional project description
            code: Optional unique project code
            project_type: Type of project
            estimated_budget: Optional budget estimate
            currency: Currency code (default EUR)
            start_date: Optional project start date
            end_date: Optional project end date

        Returns:
            The created Project entity

        Raises:
            ValueError: If business rules are violated
        """
        # Validate business rules
        if not name or not name.strip():
            raise ValueError("Project name is required")

        # Check for duplicate code
        if code:
            exists = await self.repository.exists_by_code(code, tenant_id)
            if exists:
                raise ValueError(f"Project with code '{code}' already exists")

        # Create domain entity
        now = datetime.utcnow()
        project = Project(
            id=uuid4(),
            tenant_id=tenant_id,
            name=name.strip(),
            description=description,
            code=code,
            project_type=project_type,
            status=ProjectStatus.DRAFT,
            estimated_budget=estimated_budget,
            currency=currency,
            start_date=start_date,
            end_date=end_date,
            coherence_score=None,
            last_analysis_at=None,
            created_at=now,
            updated_at=now,
        )

        # Persist
        created_project = await self.repository.create(project)

        logger.info(
            "project_created",
            project_id=str(created_project.id),
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            name=name,
        )

        return created_project
