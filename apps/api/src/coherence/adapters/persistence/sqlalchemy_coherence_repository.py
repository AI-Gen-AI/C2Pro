"""
SQLAlchemy Coherence Repository Implementation.

Concrete implementation of ICoherenceRepository using SQLAlchemy.
Refers to Suite ID: TS-INT-DB-COH-001.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.coherence.adapters.persistence.models import CoherenceResultORM
from src.coherence.application.dtos import (
    CategoryScoreDetail,
    CoherenceCalculationResult,
)
from src.coherence.domain.alert_mapping import CoherenceAlert
from src.coherence.domain.category_weights import CoherenceCategory
from src.coherence.ports.coherence_repository import ICoherenceRepository
from src.projects.adapters.persistence.models import ProjectORM


class SqlAlchemyCoherenceRepository(ICoherenceRepository):
    """SQLAlchemy implementation of coherence repository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def save(self, result: CoherenceCalculationResult) -> UUID:
        """Save a coherence calculation result."""
        # Convert domain model to ORM
        orm_result = CoherenceResultORM(
            project_id=result.project_id,
            global_score=result.global_score,
            category_scores=self._serialize_category_scores(result.category_scores),
            category_details=self._serialize_category_details(result.category_details),
            alerts=self._serialize_alerts(result.alerts),
            is_gaming_detected=result.is_gaming_detected,
            gaming_violations=result.gaming_violations,
            penalty_points=result.penalty_points,
            calculated_at=datetime.utcnow(),
        )

        self._db.add(orm_result)
        await self._db.commit()
        await self._db.refresh(orm_result)

        return orm_result.id

    async def get_by_id(self, result_id: UUID) -> CoherenceCalculationResult | None:
        """Get a coherence result by ID."""
        # Query all tenants (simplified - in production, would need tenant context)
        stmt = select(CoherenceResultORM).where(CoherenceResultORM.id == result_id)
        result = await self._db.execute(stmt)
        orm_result = result.scalar_one_or_none()

        if not orm_result:
            return None

        return self._to_domain(orm_result)

    async def get_latest_for_project(
        self, project_id: UUID
    ) -> CoherenceCalculationResult | None:
        """Get the most recent coherence result for a project."""
        stmt = (
            select(CoherenceResultORM)
            .where(CoherenceResultORM.project_id == project_id)
            .order_by(desc(CoherenceResultORM.calculated_at))
            .limit(1)
        )
        result = await self._db.execute(stmt)
        orm_result = result.scalar_one_or_none()

        if not orm_result:
            return None

        return self._to_domain(orm_result)

    async def list_for_project(
        self, project_id: UUID, skip: int = 0, limit: int = 10
    ) -> tuple[list[CoherenceCalculationResult], int]:
        """List coherence results for a project with pagination."""
        # Count query
        count_stmt = (
            select(func.count())
            .select_from(CoherenceResultORM)
            .where(CoherenceResultORM.project_id == project_id)
        )
        count_result = await self._db.execute(count_stmt)
        total = count_result.scalar_one()

        # Data query
        stmt = (
            select(CoherenceResultORM)
            .where(CoherenceResultORM.project_id == project_id)
            .order_by(desc(CoherenceResultORM.calculated_at))
            .offset(skip)
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        orm_results = list(result.scalars().all())

        domain_results = [self._to_domain(orm) for orm in orm_results]

        return domain_results, total

    async def delete(self, result_id: UUID) -> bool:
        """Delete a coherence result."""
        stmt = select(CoherenceResultORM).where(CoherenceResultORM.id == result_id)
        result = await self._db.execute(stmt)
        orm_result = result.scalar_one_or_none()

        if not orm_result:
            return False

        await self._db.delete(orm_result)
        await self._db.commit()

        return True

    async def get_project_tenant_id(self, project_id: UUID) -> UUID | None:
        """Get the tenant ID for a project."""
        stmt = select(ProjectORM.tenant_id).where(ProjectORM.id == project_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def commit(self) -> None:
        """Commit pending changes."""
        await self._db.commit()

    def _to_domain(self, orm_result: CoherenceResultORM) -> CoherenceCalculationResult:
        """Convert ORM model to domain DTO."""
        return CoherenceCalculationResult(
            project_id=orm_result.project_id,
            global_score=orm_result.global_score,
            category_scores=self._deserialize_category_scores(
                orm_result.category_scores
            ),
            category_details=self._deserialize_category_details(
                orm_result.category_details
            ),
            alerts=self._deserialize_alerts(orm_result.alerts),
            is_gaming_detected=orm_result.is_gaming_detected,
            gaming_violations=orm_result.gaming_violations,
            penalty_points=orm_result.penalty_points,
        )

    def _serialize_category_scores(
        self, scores: dict[CoherenceCategory, int]
    ) -> dict[str, int]:
        """Convert category scores to JSON-serializable format."""
        return {category.value: score for category, score in scores.items()}

    def _deserialize_category_scores(
        self, scores_dict: dict[str, int]
    ) -> dict[CoherenceCategory, int]:
        """Convert JSON format back to domain model."""
        return {CoherenceCategory(key): value for key, value in scores_dict.items()}

    def _serialize_category_details(
        self, details: list[CategoryScoreDetail]
    ) -> list[dict]:
        """Convert category details to JSON-serializable format."""
        return [
            {
                "category": detail.category.value,
                "score": detail.score,
                "violations": detail.violations,
            }
            for detail in details
        ]

    def _deserialize_category_details(
        self, details_list: list[dict]
    ) -> list[CategoryScoreDetail]:
        """Convert JSON format back to domain model."""
        return [
            CategoryScoreDetail(
                category=CoherenceCategory(detail["category"]),
                score=detail["score"],
                violations=detail["violations"],
            )
            for detail in details_list
        ]

    def _serialize_alerts(self, alerts: list[CoherenceAlert]) -> list[dict]:
        """Convert alerts to JSON-serializable format."""
        return [alert.model_dump() for alert in alerts]

    def _deserialize_alerts(self, alerts_list: list[dict]) -> list[CoherenceAlert]:
        """Convert JSON format back to domain model."""
        return [CoherenceAlert.model_validate(alert) for alert in alerts_list]
