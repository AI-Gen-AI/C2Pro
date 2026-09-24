"""
SQLAlchemy implementation of the ReviewQueueRepository port.
Test Suite ID: TS-I11-HITL-HTTP-002
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, Select, case, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.hitl.adapters.persistence.models import ResumeOperationORM, ReviewItemORM
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
        # C2PRO P0b HITL persist hotfix: carry the actual persistent row
        # identity (the primary key) through the domain layer. item_id is a
        # BUSINESS identifier (for review_type="analysis_critique" it is set
        # to the document_id, see human_interrupt_node) -- NOT unique, by
        # design, since a document can legitimately have had more than one
        # review row over time (retries before this hotfix, re-reviews after
        # rejection). update_review_item() must key off this real row id, or
        # it either updates the wrong row among duplicates or raises
        # MultipleResultsFound on one that item_id alone cannot resolve.
        metadata["row_id"] = str(orm.id)
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
        # row_id is a read-only artifact of _to_domain (the PK is already a
        # first-class column); never persist it back into review_metadata,
        # and never let it influence a fresh INSERT's generated id.
        metadata.pop("row_id", None)
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

    @staticmethod
    def _canonical_priority() -> ColumnElement[int]:
        """Rank a row's lifecycle stage for canonical selection among
        duplicates sharing one item_id.

        C2PRO P0b legacy review canonical-selection hotfix: an ACTIVE row
        awaiting a human decision (PENDING_REVIEW_REQUIRED /
        PENDING_REVIEW_CONDITIONAL) must always outrank a HISTORICAL row
        that has already been decided (APPROVED/REJECTED/CLOSED/ESCALATED),
        regardless of which was created more recently or which happens to
        carry a thread_id. Without this, an old APPROVED row created after
        (in wall-clock time) a still-active PENDING row -- e.g. a stale
        audit entry from a prior reprocess -- silently outranks the row the
        user actually needs to act on, hiding it from the queue and, worse,
        letting approve/reject resolve and mutate the wrong row entirely.
        """
        return case(
            (
                ReviewItemORM.current_status.in_(
                    [
                        ReviewStatus.PENDING_REVIEW_REQUIRED,
                        ReviewStatus.PENDING_REVIEW_CONDITIONAL,
                    ]
                ),
                0,
            ),
            else_=1,
        )

    @staticmethod
    def _v3_finalized() -> ColumnElement[bool]:
        """True when a durable V3 resume operation FINALIZED this exact row.

        C2PRO #649: resume_operations.review_row_id is the strongest
        provenance there is for "this row carries the effective human
        decision" -- it is written per EXACT row and reaches a FINALIZED
        phase in the same fenced transaction that flips the review's
        status. Operations that never finalized (RUNNING, FAILED_RETRYABLE,
        OPERATOR_REQUIRED, ...) prove nothing about the decision and do not
        count.
        """
        return exists().where(
            ResumeOperationORM.review_row_id == ReviewItemORM.id,
            ResumeOperationORM.tenant_id == ReviewItemORM.tenant_id,
            ResumeOperationORM.phase.in_(["FINALIZED_APPROVED", "FINALIZED_REJECTED"]),
        )

    @classmethod
    def _canonical_tiebreakers(cls) -> tuple[Any, ...]:
        """Full canonical ordering among rows sharing one item_id.

        1. ACTIVE before decided (`_canonical_priority()`) -- unchanged.
        2. C2PRO #649: among decided rows, a row finalized by a durable V3
           operation before any legacy row. Once the active row B is
           finalized it ties on status with historical APPROVED rows; the
           old created_at tiebreak then surfaced a historical row A that
           merely happened to be created later ("Reviewed: Sep 20" shown
           for a Sep 24 decision).
        3. Among V3-finalized rows, the most recent finalization
           (approved_at, stamped by that same transaction) -- a re-review's
           decision supersedes the earlier one. NULL for every other row,
           so it never reorders pending or legacy rows.
        4. Legacy fallback, unchanged: the resumable (real thread_id) row,
           then the most recently created.
        5. Primary key, so exact ties resolve identically on every call.

        Shared by every call site that must resolve "the" canonical row for
        an item_id, so the queue list, single-item lookup, and mutation
        targeting can never disagree about which row that is.
        """
        finalized = cls._v3_finalized()
        return (
            cls._canonical_priority(),
            case((finalized, 0), else_=1),
            case((finalized, ReviewItemORM.approved_at), else_=None).desc().nulls_last(),
            ReviewItemORM.thread_id.isnot(None).desc(),
            ReviewItemORM.created_at.desc(),
            ReviewItemORM.id.desc(),
        )

    async def add_review_item(self, item: ReviewItem) -> UUID:
        orm = self._to_orm(item)
        self.session.add(orm)
        await self.session.flush()
        return orm.id

    async def get_review_item(self, item_id: UUID) -> ReviewItem | None:
        # C2PRO P0b HITL approve/resume + review UX hotfix: try the actual
        # row primary key FIRST. This is how a caller that already has a
        # domain ReviewItem (its metadata["row_id"], now also exposed over
        # the API as ReviewItemResponse.row_id) targets ONE EXACT row,
        # unambiguously -- "id" is globally unique, so this can never raise
        # or resolve to a sibling. Falls back to item_id -- a BUSINESS
        # identifier, not guaranteed unique (review_type="analysis_critique"
        # sets it to document_id, and pre-hotfix duplicate creation left
        # several rows sharing one item_id in production) -- for legacy
        # callers that only ever knew item_id. A bare scalar_one_or_none on
        # that fallback raises MultipleResultsFound on the legacy shape;
        # resolve deterministically instead (most recently created),
        # matching find_active_review's own precedence so the two never
        # disagree about which row is "the" active one.
        # C2PRO P0b crash-safe resume: populate_existing so a row already in
        # the session's identity map is REFRESHED from the database.
        # Finalization commits in its own transaction, so without this a
        # caller re-reading the review it just finalized would be served the
        # stale, pre-finalization copy.
        stmt = select(ReviewItemORM).where(ReviewItemORM.id == item_id)
        if self.tenant_id is not None:
            stmt = stmt.where(ReviewItemORM.tenant_id == self.tenant_id)
        result = await self.session.execute(
            stmt.execution_options(populate_existing=True)
        )
        orm = result.scalar_one_or_none()
        if orm is not None:
            return self._to_domain(orm)

        stmt = select(ReviewItemORM).where(ReviewItemORM.item_id == item_id)
        if self.tenant_id is not None:
            stmt = stmt.where(ReviewItemORM.tenant_id == self.tenant_id)
        stmt = stmt.order_by(*self._canonical_tiebreakers())
        result = await self.session.execute(
            stmt.execution_options(populate_existing=True)
        )
        orm = result.scalars().first()
        return self._to_domain(orm) if orm else None

    async def update_review_item(self, item: ReviewItem) -> None:
        row_id_raw = item.metadata.get("row_id")
        stmt = select(ReviewItemORM)
        if row_id_raw:
            # Authoritative: update the EXACT row find_active_review /
            # get_review_item returned, by primary key. Never ambiguous,
            # even when other rows share this item's item_id (see
            # _to_domain's row_id note) -- this is the fix for
            # "find_active_review succeeds, update_review_item can't update
            # that same row" (C2PRO P0b HITL persist hotfix).
            stmt = stmt.where(ReviewItemORM.id == UUID(str(row_id_raw)))
        else:
            # Defensive fallback for a ReviewItem never round-tripped
            # through _to_domain (no current caller does this -- every
            # update_review_item call site fetches first). Deterministic
            # tie-break instead of raising, consistent with get_review_item.
            stmt = stmt.where(ReviewItemORM.item_id == item.item_id).order_by(
                *self._canonical_tiebreakers()
            )
        if self.tenant_id is not None:
            stmt = stmt.where(ReviewItemORM.tenant_id == self.tenant_id)
        result = await self.session.execute(stmt)
        orm = result.scalars().first()
        if orm is None:
            raise ValueError(f"Review item {item.item_id} not found.")

        # TASK-BCK-024: Extract checkpoint fields from metadata before storing
        metadata = dict(item.metadata)
        metadata.pop("row_id", None)
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

    async def find_active_review(
        self,
        document_id: UUID,
        review_type: str,
    ) -> ReviewItem | None:
        """TASK P0b HITL resume hotfix: idempotency lookup for HITL routing.

        Finds the single active (pending) review for a document+review_type,
        if any, so callers never create a second one for a document that is
        already awaiting human review (e.g. a duplicate graph re-run/retry).
        """
        stmt = select(ReviewItemORM).where(
            ReviewItemORM.document_id == document_id,
            ReviewItemORM.review_type == review_type,
            ReviewItemORM.current_status.in_(
                [
                    ReviewStatus.PENDING_REVIEW_REQUIRED,
                    ReviewStatus.PENDING_REVIEW_CONDITIONAL,
                ]
            ),
        )
        if self.tenant_id is not None:
            stmt = stmt.where(ReviewItemORM.tenant_id == self.tenant_id)
        # Same precedence as every other canonical lookup (C2PRO #649), so
        # the routing idempotency guard and the queue agree on which pending
        # row is "the" active one.
        stmt = stmt.order_by(*self._canonical_tiebreakers())
        result = await self.session.execute(stmt)
        orm = result.scalars().first()
        return self._to_domain(orm) if orm else None

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

    def _canonical_rows_subquery(
        self,
        *,
        status: ReviewStatus | None,
        project_id: UUID | None,
    ) -> Select[tuple[ReviewItemORM]]:
        """One row per item_id: the canonical, actionable review.

        C2PRO P0b review UX hotfix: item_id is a business identifier, not
        guaranteed unique (see _to_domain's row_id note) -- historical
        duplicate rows for the same item_id (pre-hotfix retries) must not
        render as separate actionable decisions in the review queue.
        Collapse to one row per item_id via Postgres DISTINCT ON.

        C2PRO P0b legacy review canonical-selection hotfix: an ACTIVE row
        (PENDING_REVIEW_REQUIRED/PENDING_REVIEW_CONDITIONAL) must always be
        preferred over a HISTORICAL, already-decided row for the same
        item_id -- see _canonical_priority(). Only once rows tie on that
        (e.g. an explicit status=APPROVED filter, where every candidate is
        already historical) do thread_id presence and recency break the
        tie. This is the exact same precedence get_review_item's item_id
        fallback and update_review_item's fallback use, so the queue never
        shows a row other than the one approve/reject would actually act
        on.
        """
        stmt = select(ReviewItemORM).distinct(ReviewItemORM.item_id)
        if self.tenant_id is not None:
            stmt = stmt.where(ReviewItemORM.tenant_id == self.tenant_id)
        if project_id is not None:
            stmt = stmt.where(ReviewItemORM.project_id == project_id)
        if status is not None:
            stmt = stmt.where(ReviewItemORM.current_status == status)
        # DISTINCT ON requires its expression(s) as the leading ORDER BY.
        return stmt.order_by(ReviewItemORM.item_id, *self._canonical_tiebreakers())

    async def list_by_status(
        self,
        status: ReviewStatus | None = None,
        *,
        skip: int = 0,
        limit: int = 50,
        project_id: UUID | None = None,
    ) -> list[ReviewItem]:
        canonical = self._canonical_rows_subquery(status=status, project_id=project_id).subquery()
        stmt = (
            select(ReviewItemORM)
            .join(canonical, ReviewItemORM.id == canonical.c.id)
            .order_by(ReviewItemORM.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def count_by_status(
        self,
        status: ReviewStatus | None = None,
        *,
        project_id: UUID | None = None,
    ) -> int:
        """TASK-BCK-092: Return true filtered count, not page size.

        Counts canonical (deduplicated) rows, consistent with list_by_status
        -- otherwise the queue's reported total would outnumber the items it
        actually renders.
        """
        from sqlalchemy import func

        canonical = self._canonical_rows_subquery(status=status, project_id=project_id).subquery()
        stmt = select(func.count()).select_from(canonical)
        result = await self.session.execute(stmt)
        return result.scalar() or 0
