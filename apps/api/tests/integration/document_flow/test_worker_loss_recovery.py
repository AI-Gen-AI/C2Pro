"""#711 deterministic worker-loss recovery acceptance.

A native process death is nondeterministic to time in CI. These tests seed the
exact durable states a death can leave behind, then exercise the production
reconciler against PostgreSQL. Celery dispatch itself is replaced only at the
broker boundary so assertions can prove what would be enqueued.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.tasks.document_recovery import (
    _sweep_async,
    MAX_RECOVERY_ATTEMPTS,
)
from src.documents.adapters.persistence.models import DocumentORM
from src.documents.domain.models import DocumentStatus, DocumentType
from src.modules.hitl.adapters.persistence.models import ReviewItemORM
from src.modules.hitl.domain.entities import ImpactLevel, ReviewStatus
from src.projects.adapters.persistence.models import ProjectORM


# The normal integration bootstrap recreates the public schema from ORM
# metadata after Alembic. That is intentional, but PostgreSQL triggers are not
# represented in ORM metadata, so the #711 documents trigger is removed while
# its migration-owned function/projection in system_recovery remains. Restore
# only that trigger here; Migrations Check independently proves the migration
# creates the function/table/privileges from scratch.
@pytest_asyncio.fixture(autouse=True)
async def _recovery_migration_surface(db: AsyncSession, test_user):
    artifacts = (
        await db.execute(
            text(
                """
                SELECT
                    to_regclass('system_recovery.document_work_index') AS work_index,
                    to_regprocedure(
                        'system_recovery.sync_document_work_index()'
                    ) AS sync_function
                """
            )
        )
    ).one()
    assert artifacts.work_index is not None
    assert artifacts.sync_function is not None

    await db.execute(
        text("DROP TRIGGER IF EXISTS trg_documents_recovery_index ON public.documents")
    )
    await db.execute(
        text(
            """
            CREATE TRIGGER trg_documents_recovery_index
            AFTER INSERT OR UPDATE ON public.documents
            FOR EACH ROW
            EXECUTE FUNCTION system_recovery.sync_document_work_index()
            """
        )
    )
    await db.commit()

    yield

    await db.rollback()
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tenant, true)"),
        {"tenant": str(test_user.tenant_id)},
    )
    await db.execute(
        text("DELETE FROM review_items WHERE tenant_id = CAST(:tenant AS uuid)"),
        {"tenant": str(test_user.tenant_id)},
    )
    await db.execute(
        text("DELETE FROM documents WHERE tenant_id = CAST(:tenant AS uuid)"),
        {"tenant": str(test_user.tenant_id)},
    )
    await db.execute(
        text("DELETE FROM projects WHERE tenant_id = CAST(:tenant AS uuid)"),
        {"tenant": str(test_user.tenant_id)},
    )
    await db.commit()


def _stale_time() -> datetime:
    return (datetime.now(UTC) - timedelta(minutes=30)).replace(tzinfo=None)


def _session_factory(db: AsyncSession):
    @asynccontextmanager
    async def _factory(tenant_id):
        if tenant_id is not None:
            await db.execute(
                text("SELECT set_config('app.current_tenant', :tenant, true)"),
                {"tenant": str(tenant_id)},
            )
        yield db
        await db.commit()

    return _factory


async def _seed_document(
    db: AsyncSession,
    *,
    tenant_id,
    user_id,
    status: DocumentStatus,
    metadata: dict | None = None,
) -> tuple[ProjectORM, DocumentORM]:
    project = ProjectORM(
        id=uuid4(),
        tenant_id=tenant_id,
        name=f"Recovery {uuid4().hex[:8]}",
        project_type="construction",
        status="active",
    )
    document = DocumentORM(
        id=uuid4(),
        tenant_id=tenant_id,
        project_id=project.id,
        document_type=DocumentType.CONTRACT,
        filename="recovery-contract.pdf",
        upload_status=status,
        document_metadata=metadata or {},
        created_by=user_id,
        updated_at=_stale_time(),
    )
    # ProjectORM/DocumentORM do not expose an ORM relationship that lets
    # SQLAlchemy infer flush ordering here. Persist the FK parent explicitly
    # before the document so this acceptance test exercises recovery semantics,
    # not unit-of-work ordering.
    db.add(project)
    await db.flush()
    db.add(document)
    await db.commit()

    projected = (
        await db.execute(
            text(
                """
                SELECT tenant_id, upload_status, updated_at
                  FROM system_recovery.document_work_index
                 WHERE document_id = :document_id
                """
            ),
            {"document_id": document.id},
        )
    ).one()
    assert projected.tenant_id == tenant_id
    assert projected.upload_status == status.value
    assert projected.updated_at <= datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=20)

    return project, document


@pytest.mark.asyncio
async def test_stale_parsing_is_requeued_once_and_terminal_state_stops_recovery(
    db: AsyncSession,
    test_user,
) -> None:
    _, document = await _seed_document(
        db,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        status=DocumentStatus.PARSING,
    )
    ingestion = Mock()
    ingestion.apply_async = Mock()
    analysis = Mock()
    analysis.apply_async = Mock()

    first = await _sweep_async(
        stale_after_seconds=60,
        session_factory=_session_factory(db),
        ingestion_task=ingestion,
        analysis_task=analysis,
    )

    assert first["requeued_ingestion"] == 1
    ingestion.apply_async.assert_called_once_with(
        kwargs={"document_id": str(document.id), "revision_id": None},
        queue="document_parsing",
    )
    await db.refresh(document)
    recovery = document.document_metadata["processing_recovery"]
    assert recovery["attempts"] == 1
    assert recovery["stage"] == DocumentStatus.PARSING.value

    document.upload_status = DocumentStatus.ANALYZED
    document.updated_at = _stale_time()
    await db.commit()

    second = await _sweep_async(
        stale_after_seconds=60,
        session_factory=_session_factory(db),
        ingestion_task=ingestion,
        analysis_task=analysis,
    )

    assert second["scanned"] == 0
    assert ingestion.apply_async.call_count == 1
    analysis.apply_async.assert_not_called()


@pytest.mark.asyncio
async def test_stale_analysis_pending_requeues_analysis_not_parsing(
    db: AsyncSession,
    test_user,
) -> None:
    _, document = await _seed_document(
        db,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        status=DocumentStatus.PARSED_PENDING_ANALYSIS,
        metadata={"rag_ingestion_outcome": "ingested"},
    )
    ingestion = Mock()
    ingestion.apply_async = Mock()
    analysis = Mock()
    analysis.apply_async = Mock()

    result = await _sweep_async(
        stale_after_seconds=60,
        session_factory=_session_factory(db),
        ingestion_task=ingestion,
        analysis_task=analysis,
    )

    assert result["requeued_analysis"] == 1
    ingestion.apply_async.assert_not_called()
    analysis.apply_async.assert_called_once_with(
        kwargs={
            "tenant_id": str(test_user.tenant_id),
            "document_id": str(document.id),
        },
        queue="document_parsing",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "review_status",
    [
        ReviewStatus.PENDING_REVIEW_REQUIRED,
        ReviewStatus.PENDING_REVIEW_CONDITIONAL,
        ReviewStatus.ESCALATED,
    ],
)
async def test_pending_hitl_is_excluded_from_stale_analysis_recovery(
    db: AsyncSession,
    test_user,
    review_status: ReviewStatus,
) -> None:
    project, document = await _seed_document(
        db,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        status=DocumentStatus.PARSED_PENDING_ANALYSIS,
        metadata={"rag_ingestion_outcome": "ingested"},
    )
    review = ReviewItemORM(
        id=uuid4(),
        item_id=uuid4(),
        item_type="analysis_finding",
        current_status=review_status,
        confidence=0.5,
        impact_level=ImpactLevel.HIGH,
        tenant_id=test_user.tenant_id,
        sla_due_date=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1),
        item_data={},
        review_metadata={},
        project_id=project.id,
        document_id=document.id,
        review_type="analysis",
    )
    db.add(review)
    await db.commit()

    ingestion = Mock()
    ingestion.apply_async = Mock()
    analysis = Mock()
    analysis.apply_async = Mock()

    result = await _sweep_async(
        stale_after_seconds=60,
        session_factory=_session_factory(db),
        ingestion_task=ingestion,
        analysis_task=analysis,
    )

    assert result["skipped_hitl"] == 1
    ingestion.apply_async.assert_not_called()
    analysis.apply_async.assert_not_called()


@pytest.mark.asyncio
async def test_exhausted_recovery_becomes_error_and_preserves_retry_path(
    db: AsyncSession,
    test_user,
) -> None:
    metadata = {
        "processing_recovery": {
            "stage": DocumentStatus.PARSING.value,
            "generation": "v1:legacy",
            "attempts": MAX_RECOVERY_ATTEMPTS,
            "outcome": "requeue_ingestion",
        }
    }
    _, document = await _seed_document(
        db,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        status=DocumentStatus.PARSING,
        metadata=metadata,
    )
    ingestion = Mock()
    ingestion.apply_async = Mock()
    analysis = Mock()
    analysis.apply_async = Mock()

    result = await _sweep_async(
        stale_after_seconds=60,
        session_factory=_session_factory(db),
        ingestion_task=ingestion,
        analysis_task=analysis,
    )

    assert result["failed_retryable"] == 1
    ingestion.apply_async.assert_not_called()
    analysis.apply_async.assert_not_called()

    row = (
        await db.execute(select(DocumentORM).where(DocumentORM.id == document.id))
    ).scalar_one()
    assert row.upload_status is DocumentStatus.ERROR
    assert "retry is available" in (row.parsing_error or "").lower()
    assert (
        row.document_metadata["processing_recovery"]["outcome"]
        == "fail_retryable"
    )
