"""
List Projects Use Case.

Retrieves a paginated list of projects with optional filters.
"""
from uuid import UUID

import structlog

from src.projects.domain.models import Project, ProjectStatus, ProjectType
from src.projects.ports.project_repository import ProjectRepository


logger = structlog.get_logger()


class ListProjectsUseCase:
    """
    Use case for listing projects with pagination and filters.

    Business rules enforced:
    - Tenant isolation (only see own projects)
    - Pagination constraints
    """

    def __init__(self, repository: ProjectRepository):
        self.repository = repository

    async def execute(
        self,
        tenant_id: UUID,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        status: ProjectStatus | None = None,
        project_type: ProjectType | None = None,
    ) -> tuple[list[Project], int]:
        """
        List projects with pagination and filters.

        Args:
            tenant_id: Tenant ID for isolation
            page: Page number (1-indexed, default 1)
            page_size: Items per page (default 20, max 100)
            search: Optional search term for name/code/description
            status: Optional status filter
            project_type: Optional project type filter

        Returns:
            Tuple of (list of projects, total count)

        Raises:
            ValueError: If pagination parameters are invalid
        """
        # Validate pagination
        if page < 1:
            raise ValueError("Page must be >= 1")

        if page_size < 1 or page_size > 100:
            raise ValueError("Page size must be between 1 and 100")

        # Fetch from repository
        projects, total = await self.repository.list(
            tenant_id=tenant_id,
            page=page,
            page_size=page_size,
            search=search,
            status=status,
            project_type=project_type,
        )

        logger.info(
            "projects_listed",
            tenant_id=str(tenant_id),
            total=total,
            page=page,
            page_size=page_size,
            filters={
                "search": search,
                "status": status.value if status else None,
                "project_type": project_type.value if project_type else None,
            },
        )

        return projects, total
