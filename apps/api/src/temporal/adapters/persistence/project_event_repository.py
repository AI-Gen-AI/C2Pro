"""SqlAlchemyProjectEventRepository (ADR-015 / TASK-V3-015-03).

LOCKED INVARIANT: NEVER call session commit(). The use case owns the transaction.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from src.documents.adapters.persistence.models import DocumentORM
from src.documents.domain.models import DocumentType
from src.evidence.domain.runtime_trust import EvidenceRef
from src.temporal.adapters.persistence.models import DocumentRevisionORM, ProjectEventORM
from src.temporal.application.timeline import TimelineKey
from src.temporal.domain.project_event import ProjectEvent
from src.temporal.ports.project_event_repository import IProjectEventRepository

# Revision outcomes a user can act on. Bookkeeping events (every upload's
# ``revision.ingested`` and every ready ``revision.analyzed`` snapshot) stay in the append-only
# log but are not timeline results: shown as items they claimed "being compared" forever and
# "No material change found" for revisions that were never compared.
_OUTCOME_EVENT_TYPES = ("revision.changed", "revision.reinterpreted", "revision.analysis_failed")
_REVISION_SETTLED_EVENT_TYPES = ("revision.analyzed", *_OUTCOME_EVENT_TYPES)


def _timeline_visible() -> ColumnElement[bool]:
    """Per revision, only honest outcomes: a result, an error, a needed review, or processing."""
    later = aliased(ProjectEventORM)
    needs_review = and_(
        ProjectEventORM.event_type == "revision.analyzed",
        ProjectEventORM.payload["state"].astext == "needs_review",
    )
    # An upload is "being compared" only for a contract revision (the only kind compared) that
    # has not settled yet; once any analysis/outcome event exists it stops being shown.
    contract_revision = exists().where(
        DocumentRevisionORM.revision_id == ProjectEventORM.source_revision_id,
        DocumentRevisionORM.tenant_id == ProjectEventORM.tenant_id,
        DocumentORM.id == DocumentRevisionORM.document_id,
        DocumentORM.document_type == DocumentType.CONTRACT,
    )
    settled = exists().where(
        later.source_revision_id == ProjectEventORM.source_revision_id,
        later.tenant_id == ProjectEventORM.tenant_id,
        later.event_type.in_(_REVISION_SETTLED_EVENT_TYPES),
    )
    pending_upload = and_(ProjectEventORM.event_type == "revision.ingested", contract_revision, ~settled)
    return or_(ProjectEventORM.event_type.in_(_OUTCOME_EVENT_TYPES), needs_review, pending_upload)


class SqlAlchemyProjectEventRepository(IProjectEventRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_domain(orm: ProjectEventORM) -> ProjectEvent:
        return ProjectEvent(
            event_id=orm.event_id,
            project_id=orm.project_id,
            tenant_id=orm.tenant_id,
            event_type=orm.event_type,
            payload=orm.payload,
            actor=orm.actor,
            confidence=orm.confidence,
            source_revision_id=orm.source_revision_id,
            evidence_refs=[EvidenceRef.model_validate(ref) for ref in (orm.evidence_refs or []) if isinstance(ref, dict)],
            occurred_at=orm.occurred_at,
            created_at=orm.created_at,
        )

    async def append(self, event: ProjectEvent) -> ProjectEvent:
        self._session.add(
            ProjectEventORM(
                event_id=event.event_id,
                project_id=event.project_id,
                tenant_id=event.tenant_id,
                event_type=event.event_type,
                payload=event.payload,
                actor=event.actor,
                confidence=event.confidence,
                source_revision_id=event.source_revision_id,
                evidence_refs=[ref.model_dump(mode="json") for ref in event.evidence_refs],
                occurred_at=event.occurred_at,
                created_at=event.created_at,
            )
        )
        await self._session.flush()
        return event

    async def get(self, event_id: UUID, tenant_id: UUID) -> ProjectEvent | None:
        stmt = select(ProjectEventORM).where(
            ProjectEventORM.event_id == event_id,
            ProjectEventORM.tenant_id == tenant_id,
        )
        result = await self._session.execute(stmt)
        orm = result.scalars().first()
        return self._to_domain(orm) if orm is not None else None

    async def list_for_project(
        self,
        project_id: UUID,
        tenant_id: UUID,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[ProjectEvent]:
        stmt = (
            select(ProjectEventORM)
            .where(
                ProjectEventORM.project_id == project_id,
                ProjectEventORM.tenant_id == tenant_id,
            )
            .order_by(ProjectEventORM.occurred_at.asc(), ProjectEventORM.event_id.asc())
        )
        if since is not None:
            stmt = stmt.where(ProjectEventORM.occurred_at >= since)
        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self._session.execute(stmt)
        return [self._to_domain(orm) for orm in result.scalars().all()]

    async def page_for_project(
        self,
        project_id: UUID,
        tenant_id: UUID,
        *,
        after: TimelineKey | None,
        limit: int,
    ) -> list[ProjectEvent]:
        stmt = (
            select(ProjectEventORM)
            .where(
                ProjectEventORM.project_id == project_id,
                ProjectEventORM.tenant_id == tenant_id,
                _timeline_visible(),
            )
            .order_by(ProjectEventORM.occurred_at.asc(), ProjectEventORM.event_id.asc())
            .limit(limit + 1)
        )
        if after is not None:
            stmt = stmt.where(
                or_(
                    ProjectEventORM.occurred_at > after.occurred_at,
                    and_(
                        ProjectEventORM.occurred_at == after.occurred_at,
                        ProjectEventORM.event_id > after.event_id,
                    ),
                )
            )
        result = await self._session.execute(stmt)
        return [self._to_domain(orm) for orm in result.scalars().all()]

    async def get_change_for_revision(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        document_id: UUID,
        revision_id: UUID,
    ) -> ProjectEvent | None:
        stmt = (
            select(ProjectEventORM)
            .join(
                DocumentRevisionORM,
                ProjectEventORM.source_revision_id == DocumentRevisionORM.revision_id,
            )
            .where(
                ProjectEventORM.event_type.in_(("revision.changed", "revision.reinterpreted")),
                ProjectEventORM.tenant_id == tenant_id,
                ProjectEventORM.project_id == project_id,
                ProjectEventORM.source_revision_id == revision_id,
                DocumentRevisionORM.tenant_id == tenant_id,
                DocumentRevisionORM.project_id == project_id,
                DocumentRevisionORM.document_id == document_id,
            )
            .order_by(ProjectEventORM.occurred_at.desc(), ProjectEventORM.event_id.desc())
        )
        result = await self._session.execute(stmt)
        orm = result.scalars().first()
        return self._to_domain(orm) if orm is not None else None
