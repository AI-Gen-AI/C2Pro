"""
SQLAlchemy implementation of the ReviewQueueRepository port.
Test Suite ID: TS-I11-HITL-HTTP-002
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.hitl.adapters.persistence.models import ReviewItemORM
from src.modules.hitl.application.ports import ReviewQueueRepository
from src.modules.hitl.domain.entities import ImpactLevel, ReviewItem, ReviewStatus


class SqlAlchemyReviewQueueRepository(ReviewQueueRepository):
    def __init__(self, session: AsyncSession, tenant_id: UUID | None = None) -> None:
        self.session = session
        self.tenant_id = tenant_id

    @staticmethod
    def _normalize_naive_utc(value: datetime | None) -> datetime | None:
        """Persist naive UTC values for columns declared without timezone support."""
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)

    # -- mapper helpers -------------------------------------------------------

    @staticmethod
    def _to_domain(orm: ReviewItemORM) -> ReviewItem:
        # TASK-BCK-024: Include checkpoint tracking fields in metadata
        metadata = dict(orm.review_metadata or {})
        if orm.checkpoint_id:
            metadata["checkpoint_id"] = orm.checkpoint_id
        if orm.thread_id:
            metadata["thread_id"] = orm.thread_id
        if orm.project_id:
            metadata["project_id"] = str(orm.project_id)
        if orm.document_id:
            metadata["document_id"] = str(orm.document_id)
        if orm.review_type:
            metadata["review_type"] = orm.review_type
        if orm.review_decision:
            metadata["review_decision"] = orm.review_decision

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
            metadata=metadata,
        )

    def _to_orm(self, item: ReviewItem) -> ReviewItemORM:
        # TASK-BCK-024: Extract checkpoint fields from metadata
        metadata = dict(item.metadata)
        checkpoint_id = metadata.pop("checkpoint_id", None)
        thread_id = metadata.pop("thread_id", None)
        project_id_str = metadata.pop("project_id", None)
        document_id_str = metadata.pop("document_id", None)
        review_type = metadata.pop("review_type", None)
        review_decision = metadata.pop("review_decision", None)

        # Convert string UUIDs back to UUID objects
        from uuid import UUID as UUIDType

        project_id = UUIDType(project_id_str) if project_id_str else None
        document_id = UUIDType(document_id_str) if document_id_str else None

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
            review_metadata=metadata,  # Store remaining metadata
            # TASK-BCK-024: Checkpoint tracking fields
            checkpoint_id=checkpoint_id,
            thread_id=thread_id,
            project_id=project_id,
            document_id=document_id,
            review_type=review_type,
            review_decision=review_decision,
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

        # TASK-BCK-024: Extract checkpoint fields from metadata before storing
        metadata = dict(item.metadata)
        checkpoint_id = metadata.pop("checkpoint_id", None)
        thread_id = metadata.pop("thread_id", None)
        project_id_str = metadata.pop("project_id", None)
        document_id_str = metadata.pop("document_id", None)
        review_type = metadata.pop("review_type", None)
        review_decision = metadata.pop("review_decision", None)

        from uuid import UUID as UUIDType

        project_id = (
            UUIDType(project_id_str) if project_id_str and isinstance(project_id_str, str) else None
        )
        document_id = (
            UUIDType(document_id_str)
            if document_id_str and isinstance(document_id_str, str)
            else None
        )

        orm.current_status = item.current_status
        orm.confidence = item.confidence
        orm.impact_level = item.impact_level
        orm.approved_by = item.approved_by
        approved_at_value = self._normalize_naive_utc(item.approved_at)
        orm.approved_at = approved_at_value
        orm.item_data = item.item_data
        orm.review_metadata = metadata  # Store remaining metadata
        # TASK-BCK-024: Update checkpoint tracking fields
        if checkpoint_id is not None:
            orm.checkpoint_id = checkpoint_id
        if thread_id is not None:
            orm.thread_id = thread_id
        if project_id is not None:
            orm.project_id = project_id
        if document_id is not None:
            orm.document_id = document_id
        if review_type is not None:
            orm.review_type = review_type
        if review_decision is not None:
            orm.review_decision = review_decision
        orm.updated_at = datetime.now(UTC).replace(tzinfo=None)
        await self.session.flush()

    async def get_overdue_items(self) -> list[ReviewItem]:
        now: datetime = datetime.now(UTC).replace(tzinfo=None)
        stmt = select(ReviewItemORM).where(
            ReviewItemORM.sla_due_date < now,
            ReviewItemORM.current_status.in_(
                [
                    ReviewStatus.PENDING_REVIEW_REQUIRED,
                    ReviewStatus.PENDING_REVIEW_CONDITIONAL,
                ]
            ),
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
        project_id: UUID | None = None,
    ) -> list[ReviewItem]:
        stmt = select(ReviewItemORM)
        if self.tenant_id is not None:
            stmt = stmt.where(ReviewItemORM.tenant_id == self.tenant_id)
        if project_id is not None:
            stmt = stmt.where(ReviewItemORM.project_id == project_id)
        if status is not None:
            stmt = stmt.where(ReviewItemORM.current_status == status)
        stmt = stmt.order_by(ReviewItemORM.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def count_by_status(
        self,
        status: ReviewStatus | None = None,
        *,
        project_id: UUID | None = None,
    ) -> int:
        """TASK-BCK-092: Return true filtered count, not page size."""
        from sqlalchemy import func

        stmt = select(func.count()).select_from(ReviewItemORM)
        if self.tenant_id is not None:
            stmt = stmt.where(ReviewItemORM.tenant_id == self.tenant_id)
        if project_id is not None:
            stmt = stmt.where(ReviewItemORM.project_id == project_id)
        if status is not None:
            stmt = stmt.where(ReviewItemORM.current_status == status)
        result = await self.session.execute(stmt)
        return result.scalar() or 0
