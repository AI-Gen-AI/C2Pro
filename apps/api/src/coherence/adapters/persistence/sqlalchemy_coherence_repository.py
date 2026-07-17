"""
SQLAlchemy Coherence Repository Implementation.

Concrete implementation of ICoherenceRepository using SQLAlchemy.
Refers to Suite ID: TS-INT-DB-COH-001.

IMPORTANT: All methods implement tenant isolation via JOIN with ProjectORM.
TASK-REV-003: Fixed tenant isolation in all methods.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.coherence.adapters.persistence.models import CoherenceResultORM
from src.coherence.application.dtos import (
    CategoryScoreDetail,
    CoherenceCalculationResult,
)
from src.coherence.domain.alert_mapping import CoherenceAlert
from src.coherence.domain.category_weights import CoherenceCategory
from src.coherence.ports.coherence_repository import ICoherenceRepository
from src.core.tenants.types import TenantId
from src.projects.adapters.persistence.models import ProjectORM


def _utcnow_naive() -> datetime:
    """Return naive UTC for TIMESTAMP WITHOUT TIME ZONE persistence."""
    return datetime.now(UTC).replace(tzinfo=None)


class SqlAlchemyCoherenceRepository(ICoherenceRepository):
    """SQLAlchemy implementation of coherence repository with tenant isolation."""

    def __init__(self, db: AsyncSession, tenant_id: TenantId | None = None) -> None:
        self._db = db
        self._tenant_id = tenant_id

    def _apply_tenant_filter(self, stmt: Select[Any]) -> tuple[Select[Any], bool]:
        """Apply tenant filter by joining with ProjectORM."""
        if self._tenant_id is None:
            return stmt, False
        return (
            stmt.join(ProjectORM, ProjectORM.id == CoherenceResultORM.project_id)
            .where(ProjectORM.tenant_id == self._tenant_id)
        ), True

    async def save(self, result: CoherenceCalculationResult) -> UUID:
        """Save a coherence calculation result with tenant verification."""
        if self._tenant_id is not None:
            project_tenant = await self.get_project_tenant_id(result.project_id)
            if project_tenant is None or project_tenant != self._tenant_id:
                raise PermissionError("Cannot save coherence result for project outside tenant")
        # Resolve tenant_id for the NOT NULL column. Prefer the repository's
        # constructor-injected tenant; fall back to a project lookup so callers
        # without explicit tenant scope still write a consistent row.
        tenant_id_for_row: UUID | None = self._tenant_id
        if tenant_id_for_row is None:
            tenant_id_for_row = await self.get_project_tenant_id(result.project_id)
            if tenant_id_for_row is None:
                raise ValueError(
                    f"Cannot persist coherence result: project {result.project_id} "
                    "has no resolvable tenant_id."
                )

        orm_result = CoherenceResultORM(
            project_id=result.project_id,
            tenant_id=tenant_id_for_row,
            global_score=result.global_score,
            category_scores=self._serialize_category_scores(result.category_scores),
            category_details=self._serialize_category_details(result.category_details),
            alerts=self._serialize_alerts(result.alerts),
            is_gaming_detected=result.is_gaming_detected,
            gaming_violations=result.gaming_violations,
            penalty_points=result.penalty_points,
            score_version=result.score_version,
            score_reason=result.score_reason,
            score_missing_dimensions=result.score_missing_dimensions,
            calculated_at=_utcnow_naive(),
        )

        self._db.add(orm_result)
        await self._db.commit()
        await self._db.refresh(orm_result)

        # ADR-009 §G / Phase D: invalidate cached coherence keys for this
        # project so the next dashboard read recomputes. Fire-and-forget;
        # never propagate cache failures to the caller (the DB write is
        # already committed and authoritative).
        if self._tenant_id is not None:
            try:
                from src.coherence import cache_invalidation as _cache_invalidation
                from src.core.cache import get_redis_client as _get_redis_client
                redis = _get_redis_client()
                if redis is not None:
                    await _cache_invalidation.on_result_persisted(
                        redis,
                        tenant_id=self._tenant_id,
                        project_id=result.project_id,
                    )
            except Exception:  # noqa: BLE001 — cache is best-effort
                import structlog as _structlog
                _structlog.get_logger().warning(
                    "coherence.on_result_persisted.cache_invalidation_failed",
                    tenant_id=str(self._tenant_id),
                    project_id=str(result.project_id),
                )

        return orm_result.id

    async def get_by_id(self, result_id: UUID) -> CoherenceCalculationResult | None:
        """Get a coherence result by ID with tenant isolation."""
        stmt = select(CoherenceResultORM).where(CoherenceResultORM.id == result_id)
        if self._tenant_id is not None:
            stmt = stmt.join(ProjectORM, ProjectORM.id == CoherenceResultORM.project_id).where(
                ProjectORM.tenant_id == self._tenant_id
            )
        result = await self._db.execute(stmt)
        orm_result = result.scalar_one_or_none()

        if not orm_result:
            return None

        return self._to_domain(orm_result)

    async def get_latest_for_project(
        self, project_id: UUID
    ) -> CoherenceCalculationResult | None:
        """Get the most recent coherence result for a project with tenant isolation."""
        stmt = (
            select(CoherenceResultORM)
            .where(CoherenceResultORM.project_id == project_id)
            .order_by(desc(CoherenceResultORM.calculated_at))
            .limit(1)
        )
        if self._tenant_id is not None:
            stmt = stmt.join(ProjectORM, ProjectORM.id == CoherenceResultORM.project_id).where(
                ProjectORM.tenant_id == self._tenant_id
            )
        result = await self._db.execute(stmt)
        orm_result = result.scalar_one_or_none()

        if not orm_result:
            return None

        return self._to_domain(orm_result)

    async def list_for_project(
        self, project_id: UUID, skip: int = 0, limit: int = 10
    ) -> tuple[list[CoherenceCalculationResult], int]:
        """List coherence results for a project with pagination and tenant isolation."""
        base_filter = CoherenceResultORM.project_id == project_id

        count_stmt = select(func.count()).select_from(CoherenceResultORM).where(base_filter)
        if self._tenant_id is not None:
            count_stmt = count_stmt.join(ProjectORM, ProjectORM.id == CoherenceResultORM.project_id).where(
                ProjectORM.tenant_id == self._tenant_id
            )
        count_result = await self._db.execute(count_stmt)
        total = count_result.scalar_one()

        stmt = (
            select(CoherenceResultORM)
            .where(base_filter)
            .order_by(desc(CoherenceResultORM.calculated_at))
            .offset(skip)
            .limit(limit)
        )
        if self._tenant_id is not None:
            stmt = stmt.join(ProjectORM, ProjectORM.id == CoherenceResultORM.project_id).where(
                ProjectORM.tenant_id == self._tenant_id
            )
        result = await self._db.execute(stmt)
        orm_results = list(result.scalars().all())

        domain_results = [self._to_domain(orm) for orm in orm_results]

        return domain_results, total

    async def delete(self, result_id: UUID) -> bool:
        """Delete a coherence result with tenant isolation."""
        stmt = select(CoherenceResultORM).where(CoherenceResultORM.id == result_id)
        if self._tenant_id is not None:
            stmt = stmt.join(ProjectORM, ProjectORM.id == CoherenceResultORM.project_id).where(
                ProjectORM.tenant_id == self._tenant_id
            )
        result = await self._db.execute(stmt)
        orm_result = result.scalar_one_or_none()

        if not orm_result:
            return False

        await self._db.delete(orm_result)
        await self._db.commit()

        return True

    async def get_project_tenant_id(self, project_id: UUID) -> TenantId | None:
        """Get the tenant ID for a project."""
        stmt = select(ProjectORM.tenant_id).where(ProjectORM.id == project_id)
        result = await self._db.execute(stmt)
        res = result.scalar_one_or_none()
        return TenantId(res) if res is not None else None

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
            score_version=orm_result.score_version,
            score_reason=orm_result.score_reason,
            score_missing_dimensions=orm_result.score_missing_dimensions,
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
    ) -> list[dict[str, Any]]:
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
        self, details_list: list[dict[str, Any]]
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

    def _serialize_alerts(self, alerts: list[CoherenceAlert]) -> list[dict[str, Any]]:
        """Convert alerts to JSON-serializable format."""
        return [alert.model_dump() for alert in alerts]

    def _deserialize_alerts(self, alerts_list: list[dict[str, Any]]) -> list[CoherenceAlert]:
        """Convert JSON format back to domain model."""
        return [CoherenceAlert.model_validate(alert) for alert in alerts_list]
