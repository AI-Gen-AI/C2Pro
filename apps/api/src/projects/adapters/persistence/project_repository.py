"""
SQLAlchemy implementation of ProjectRepository.

This adapter implements the repository port using SQLAlchemy ORM.
It handles mapping between domain entities and ORM models.
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.projects.domain.models import Project, ProjectStatus, ProjectType
from src.projects.ports.project_repository import ProjectRepository
from src.projects.adapters.persistence.models import ProjectORM


class SQLAlchemyProjectRepository(ProjectRepository):
    """
    SQLAlchemy-based implementation of the Project repository.

    This adapter is responsible for:
    - Mapping between Project entities and ProjectORM models
    - Executing database queries
    - Enforcing tenant isolation at the persistence layer
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, orm: ProjectORM) -> Project:
        """
        Map ORM model to domain entity.

        Args:
            orm: ProjectORM instance

        Returns:
            Project domain entity
        """
        return Project(
            id=orm.id,
            tenant_id=orm.tenant_id,
            name=orm.name,
            description=orm.description,
            code=orm.code,
            project_type=ProjectType(orm.project_type),
            status=ProjectStatus(orm.status),
            estimated_budget=orm.estimated_budget,
            currency=orm.currency,
            start_date=orm.start_date,
            end_date=orm.end_date,
            coherence_score=orm.coherence_score,
            last_analysis_at=orm.last_analysis_at,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    def _to_orm(self, entity: Project) -> ProjectORM:
        """
        Map domain entity to ORM model.

        Args:
            entity: Project domain entity

        Returns:
            ProjectORM instance
        """
        return ProjectORM(
            id=entity.id,
            tenant_id=entity.tenant_id,
            name=entity.name,
            description=entity.description,
            code=entity.code,
            project_type=entity.project_type.value,
            status=entity.status.value,
            estimated_budget=entity.estimated_budget,
            currency=entity.currency,
            start_date=entity.start_date,
            end_date=entity.end_date,
            coherence_score=entity.coherence_score,
            last_analysis_at=entity.last_analysis_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def create(self, project: Project) -> Project:
        """Create a new project in the database."""
        orm = self._to_orm(project)
        self.session.add(orm)
        await self.session.flush()
        await self.session.refresh(orm)
        return self._to_entity(orm)

    async def get_by_id(self, project_id: UUID, tenant_id: UUID) -> Project | None:
        """Retrieve a project by ID with tenant isolation."""
        result = await self.session.execute(
            select(ProjectORM).where(
                ProjectORM.id == project_id,
                ProjectORM.tenant_id == tenant_id,
            )
        )
        orm = result.scalar_one_or_none()
        return self._to_entity(orm) if orm else None

    async def list(
        self,
        tenant_id: UUID,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        status: ProjectStatus | None = None,
        project_type: ProjectType | None = None,
    ) -> tuple[list[Project], int]:
        """List projects with pagination and filters."""
        # Build base query
        query = select(ProjectORM).where(ProjectORM.tenant_id == tenant_id)

        # Apply filters
        if search:
            query = query.where(
                ProjectORM.name.ilike(f"%{search}%") |
                ProjectORM.code.ilike(f"%{search}%") |
                ProjectORM.description.ilike(f"%{search}%")
            )

        if status:
            query = query.where(ProjectORM.status == status.value)

        if project_type:
            query = query.where(ProjectORM.project_type == project_type.value)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size).order_by(ProjectORM.created_at.desc())

        # Execute
        result = await self.session.execute(query)
        orms = result.scalars().all()

        # Map to entities
        projects = [self._to_entity(orm) for orm in orms]

        return projects, total

    async def update(self, project: Project) -> Project:
        """Update an existing project."""
        result = await self.session.execute(
            select(ProjectORM).where(
                ProjectORM.id == project.id,
                ProjectORM.tenant_id == project.tenant_id,
            )
        )
        orm = result.scalar_one_or_none()

        if not orm:
            raise ValueError(f"Project {project.id} not found")

        # Update fields
        orm.name = project.name
        orm.description = project.description
        orm.code = project.code
        orm.project_type = project.project_type.value
        orm.status = project.status.value
        orm.estimated_budget = project.estimated_budget
        orm.currency = project.currency
        orm.start_date = project.start_date
        orm.end_date = project.end_date
        orm.coherence_score = project.coherence_score
        orm.last_analysis_at = project.last_analysis_at
        orm.updated_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(orm)
        return self._to_entity(orm)

    async def delete(self, project_id: UUID, tenant_id: UUID) -> bool:
        """Delete a project by ID."""
        result = await self.session.execute(
            select(ProjectORM).where(
                ProjectORM.id == project_id,
                ProjectORM.tenant_id == tenant_id,
            )
        )
        orm = result.scalar_one_or_none()

        if not orm:
            return False

        await self.session.delete(orm)
        await self.session.flush()
        return True

    async def exists_by_code(
        self, code: str, tenant_id: UUID, exclude_id: UUID | None = None
    ) -> bool:
        """Check if a project with the given code exists."""
        query = select(ProjectORM).where(
            ProjectORM.code == code,
            ProjectORM.tenant_id == tenant_id,
        )

        if exclude_id:
            query = query.where(ProjectORM.id != exclude_id)

        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None
