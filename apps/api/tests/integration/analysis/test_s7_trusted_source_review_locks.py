"""ACC-01 S7: real PostgreSQL serialization and durable event compatibility.

Uses TWO separate asyncpg PostgreSQL sessions. A review's FOR SHARE row
lock must prevent the normal trust-writer's active-row UPDATE until review
ends. This cannot be established by mocked single-session unit tests.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import DocumentArtifactORM
from src.analysis.application.record_technical_wbs_review import (
    TechnicalMappingReviewError,
    require_locked_trusted_artifact,
)
from src.documents.adapters.persistence.models import DocumentORM
from src.documents.domain.models import DocumentType
from src.projects.adapters.persistence.models import ProjectORM
from src.temporal.adapters.persistence.models import DocumentRevisionORM, ProjectEventORM
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.domain.project_event import ProjectEvent

pytestmark = pytest.mark.asyncio


async def _seed(db: AsyncSession, test_tenant) -> tuple:
    tenant_id, project_id, doc_id, revision_id, artifact_id = (
        test_tenant.id, uuid4(), uuid4(), uuid4(), uuid4()
    )
    db.add(ProjectORM(
        id=project_id,
        tenant_id=tenant_id,
        name="S7 trusted-review lock",
        code=f"S7-{project_id.hex[:8]}",
        project_type="construction",
        status="active",
        currency="EUR",
    ))
    db.add(DocumentORM(
        id=doc_id,
        tenant_id=tenant_id,
        project_id=project_id,
        document_type=DocumentType.TECHNICAL_SPEC,
        filename="technical.docx",
        file_format=".docx",
    ))
    await db.flush()
    now = datetime.now(UTC).replace(tzinfo=None)
    db.add(DocumentRevisionORM(
        revision_id=revision_id,
        tenant_id=tenant_id,
        project_id=project_id,
        document_id=doc_id,
        rev_no=1,
        blob_hash="a" * 64,
        blob_key=f"revisions/{revision_id}.docx",
        valid_from=now,
        created_at=now,
    ))
    await db.flush()
    db.add(DocumentArtifactORM(
        artifact_id=artifact_id,
        tenant_id=tenant_id,
        project_id=project_id,
        document_id=doc_id,
        document_revision_id=revision_id,
        trust_state="trusted",
        lifecycle_status="active",
        artifact_version=1,
        artifact_hash="b" * 64,
        payload={"doc_type": "technical_spec"},
    ))
    await db.commit()
    return tenant_id, project_id, doc_id, revision_id, artifact_id


async def test_review_source_lock_blocks_competing_trust_supersede(
    db: AsyncSession, test_tenant, test_session_factory
) -> None:
    tenant, project, document, revision, artifact = await _seed(db, test_tenant)
    async with test_session_factory() as review, test_session_factory() as promotion:
        locked = await require_locked_trusted_artifact(
            review, tenant_id=tenant, project_id=project,
            document_id=document, revision_id=revision,
        )
        assert locked == artifact
        # This is the SAME update action every trust promotion takes before
        # replacing active trusted authority. The 150 ms lock timeout is
        # PostgreSQL's deterministic refusal, not a Playwright retry/wait.
        await promotion.execute(text("SET LOCAL lock_timeout = '150ms'"))
        with pytest.raises(DBAPIError, match="lock timeout"):
            await promotion.execute(
                update(DocumentArtifactORM)
                .where(DocumentArtifactORM.artifact_id == artifact)
                .values(trust_state="superseded", lifecycle_status="superseded")
            )
        await promotion.rollback()

        # The original review sees the same pinned active trusted source.
        still_current = await review.scalar(
            select(DocumentArtifactORM.trust_state).where(
                DocumentArtifactORM.artifact_id == artifact
            )
        )
        assert still_current == "trusted"
        await review.rollback()  # releases the FOR SHARE lock

        # Once the review transaction is done, an actual trust supersede works.
        changed = await promotion.execute(
            update(DocumentArtifactORM)
            .where(DocumentArtifactORM.artifact_id == artifact)
            .values(trust_state="superseded", lifecycle_status="superseded")
        )
        assert changed.rowcount == 1
        await promotion.commit()

        with pytest.raises(TechnicalMappingReviewError, match="active trusted artifact"):
            await require_locked_trusted_artifact(
                review, tenant_id=tenant, project_id=project,
                document_id=document, revision_id=revision,
            )
        await review.rollback()


async def test_review_source_lock_is_scoped_to_current_tenant(
    db: AsyncSession, test_tenant, test_session_factory
) -> None:
    tenant, project, document, revision, _artifact = await _seed(db, test_tenant)
    async with test_session_factory() as review:
        with pytest.raises(TechnicalMappingReviewError, match="active trusted artifact"):
            await require_locked_trusted_artifact(
                review, tenant_id=uuid4(), project_id=project,
                document_id=document, revision_id=revision,
            )
        await review.rollback()


async def test_review_event_survives_real_postgresql_timestamp_columns(
    db: AsyncSession, test_tenant
) -> None:
    tenant, project, _document, revision, _artifact = await _seed(db, test_tenant)
    timestamp = datetime.now(UTC).replace(tzinfo=None)
    event = ProjectEvent(
        event_id=uuid4(),
        project_id=project,
        tenant_id=tenant,
        source_revision_id=revision,
        event_type="technical.wbs_link_reviewed",
        payload={
            "authority": "AUDIT_ONLY_NOT_CANONICAL_LINK",
            "technical_assessment": "NOT_ASSESSED",
        },
        actor=f"user:{uuid4()}",
        occurred_at=timestamp,
        created_at=timestamp,
    )
    await SqlAlchemyProjectEventRepository(db).append(event)
    await db.commit()
    saved = await db.scalar(
        select(ProjectEventORM).where(ProjectEventORM.event_id == event.event_id)
    )
    assert saved is not None
    assert saved.occurred_at == timestamp
    assert saved.created_at == timestamp
    assert saved.payload["technical_assessment"] == "NOT_ASSESSED"
