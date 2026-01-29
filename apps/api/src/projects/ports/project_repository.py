"""
Port (interface) for Project repository.

This defines the contract that any persistence adapter must fulfill.
Following the Dependency Inversion Principle, the domain/application layers
depend on this abstraction, not on concrete implementations.
"""
from abc import ABC, abstractmethod
from uuid import UUID

from src.projects.domain.models import Project, ProjectStatus, ProjectType


class ProjectRepository(ABC):
    """
    Repository interface for Project aggregate.

    All persistence operations for projects must go through this interface.
    Concrete implementations (e.g., SQLAlchemy) are in adapters/persistence/.
    """

    @abstractmethod
    async def create(self, project: Project) -> Project:
        """
        Persist a new project.

        Args:
            project: Project entity to create

        Returns:
            The created project with persisted state
        """
        pass

    @abstractmethod
    async def get_by_id(self, project_id: UUID, tenant_id: UUID) -> Project | None:
        """
        Retrieve a project by ID, enforcing tenant isolation.

        Args:
            project_id: The project's unique identifier
            tenant_id: The tenant ID for isolation

        Returns:
            Project entity if found, None otherwise
        """
        pass

    @abstractmethod
    async def list(
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
            tenant_id: The tenant ID for isolation
            page: Page number (1-indexed)
            page_size: Items per page
            search: Search term for name/code
            status: Filter by project status
            project_type: Filter by project type

        Returns:
            Tuple of (list of projects, total count)
        """
        pass

    @abstractmethod
    async def update(self, project: Project) -> Project:
        """
        Update an existing project.

        Args:
            project: Project entity with updated data

        Returns:
            The updated project
        """
        pass

    @abstractmethod
    async def delete(self, project_id: UUID, tenant_id: UUID) -> bool:
        """
        Delete a project by ID.

        Args:
            project_id: The project's unique identifier
            tenant_id: The tenant ID for isolation

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def exists_by_code(self, code: str, tenant_id: UUID, exclude_id: UUID | None = None) -> bool:
        """
        Check if a project with the given code already exists.

        Args:
            code: The project code to check
            tenant_id: The tenant ID for isolation
            exclude_id: Optional project ID to exclude from check (for updates)

        Returns:
            True if exists, False otherwise
        """
        pass
