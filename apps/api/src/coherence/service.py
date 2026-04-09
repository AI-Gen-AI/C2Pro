"""
C2Pro - Coherence Service

Thin façade over the real persistence layer.
Replaces the former MOCK_PROJECT_DB / MOCK_SCORE_DB dictionaries
with proper async repository queries.

IMPORTANT: All methods implement tenant isolation.
TASK-REV-003: Fixed to pass tenant_id to repository.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.coherence.adapters.persistence.sqlalchemy_coherence_repository import (
    SqlAlchemyCoherenceRepository,
)
from src.coherence.application.dtos import CoherenceCalculationResult
from src.projects.adapters.persistence.project_repository import (
    SQLAlchemyProjectRepository,
)


class CoherenceService:
    """Async service that delegates to SQLAlchemy repositories."""

    def __init__(self, db: AsyncSession, tenant_id: UUID | None = None) -> None:
        self._project_repo = SQLAlchemyProjectRepository(session=db)
        self._coherence_repo = SqlAlchemyCoherenceRepository(db=db, tenant_id=tenant_id)

    async def project_exists(self, project_id: UUID, tenant_id: UUID) -> bool:
        """Check whether a project exists (with tenant isolation)."""
        return await self._project_repo.exists_by_id(project_id, tenant_id)

    async def get_latest_score(
        self, project_id: UUID
    ) -> CoherenceCalculationResult | None:
        """Return the most recent coherence result for a project, or None."""
        return await self._coherence_repo.get_latest_for_project(project_id)
