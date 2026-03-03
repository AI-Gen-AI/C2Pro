"""SQLAlchemy implementation of the ReviewQueueRepository port."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.hitl.application.ports import ReviewQueueRepository
from src.modules.hitl.domain.entities import ImpactLevel, ReviewItem, ReviewStatus
from src.modules.hitl.adapters.persistence.models import ReviewItemORM


class SqlAlchemyReviewQueueRepository(ReviewQueueRepository):
    def __init__(self, session: AsyncSession, tenant_id: UUID | None = None) -> None:
        self.session = session
        self.tenant_id = tenant_id

    # -- mapper helpers -------------------------------------------------------

    @staticmethod
    def _to_domain(orm: ReviewItemORM) -> ReviewItem:
        return ReviewItem(
            item_id=orm.item_id,
            item_type=orm.item_type,
            current_status=ReviewStatus(orm.current_status)
            if isinstance(orm.current_status, str)
            else orm.current_status,
            confidence=orm.confidence,
            impact_level=ImpactLevel(orm.impact_level)
            if isinstance(orm.impact_level, str)
            else orm.impact_level,
            created_at=orm.created_at,
            sla_due_date=orm.sla_due_date,
            approved_by=orm.approved_by,
            approved_at=orm.approved_at,
            item_data=orm.item_data or {},
            metadata=orm.review_metadata or {},
        )

    def _to_orm(self, item: ReviewItem) -> ReviewItemORM:
        return ReviewItemORM(
            item_id=item.item_id,
            item_type=item.item_type,
            current_status=item.current_status,
            confidence=item.confidence,
            impact_level=item.impact_level,
            tenant_id=self.tenant_id,
            sla_due_date=item.sla_due_date,
            approved_by=item.approved_by,
            approved_at=item.approved_at,
            item_data=item.item_data,
            review_metadata=item.metadata,
        )

    # -- port implementation --------------------------------------------------

    async def add_review_item(self, item: ReviewItem) -> UUID:
        orm = self._to_orm(item)
        self.session.add(orm)
        await self.session.flush()
        return orm.id

    async def get_review_item(self, item_id: UUID) -> ReviewItem | None:
        stmt = select(ReviewItemORM).where(ReviewItemORM.item_id == item_id)
        if self.tenant_id is not None:
            stmt = stmt.where(ReviewItemORM.tenant_id == self.tenant_id)
        result = await self.session.execute(stmt)
        orm = result.scalar_one_or_none()
        return self._to_domain(orm) if orm else None

    async def update_review_item(self, item: ReviewItem) -> None:
        stmt = select(ReviewItemORM).where(ReviewItemORM.item_id == item.item_id)
        if self.tenant_id is not None:
            stmt = stmt.where(ReviewItemORM.tenant_id == self.tenant_id)
        result = await self.session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            raise ValueError(f"Review item {item.item_id} not found.")
        orm.current_status = item.current_status
        orm.confidence = item.confidence
        orm.impact_level = item.impact_level
        orm.approved_by = item.approved_by
        orm.approved_at = item.approved_at
        orm.item_data = item.item_data
        orm.review_metadata = item.metadata
        orm.updated_at = datetime.utcnow()
        await self.session.flush()

    async def get_overdue_items(self) -> list[ReviewItem]:
        now = datetime.utcnow()
        stmt = (
            select(ReviewItemORM)
            .where(
                ReviewItemORM.sla_due_date < now,
                ReviewItemORM.current_status.in_([
                    ReviewStatus.PENDING_REVIEW_REQUIRED,
                    ReviewStatus.PENDING_REVIEW_CONDITIONAL,
                ]),
            )
        )
        if self.tenant_id is not None:
            stmt = stmt.where(ReviewItemORM.tenant_id == self.tenant_id)
        result = await self.session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def list_by_status(
        self,
        status: ReviewStatus | None = None,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> list[ReviewItem]:
        stmt = select(ReviewItemORM)
        if self.tenant_id is not None:
            stmt = stmt.where(ReviewItemORM.tenant_id == self.tenant_id)
        if status is not None:
            stmt = stmt.where(ReviewItemORM.current_status == status)
        stmt = stmt.order_by(ReviewItemORM.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]
