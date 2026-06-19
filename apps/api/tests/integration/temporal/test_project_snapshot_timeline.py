"""Integration tests for ProjectSnapshot timeline (ADR-015 / TASK-V3-015-04)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from src.temporal.adapters.persistence.document_revision_repository import (
    SqlAlchemyDocumentRevisionRepository,
)
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.adapters.persistence.project_snapshot_repository import (
    SqlAlchemyProjectSnapshotRepository,
)
from src.temporal.domain.document_revision import DocumentRevision
from src.temporal.domain.project_event import ProjectEvent
from src.temporal.domain.project_snapshot import ProjectSnapshot, SnapshotTrigger

pytestmark = pytest.mark.asyncio


def _now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def _create_project(db: AsyncSession, project_id: UUID, tenant_id: UUID) -> None:
    await db.execute(
        text(
            "INSERT INTO projects "
            "(id, tenant_id, name, code, project_type, status, currency, created_at, updated_at) "
            "VALUES (:id, :tid, 'test', :code, 'construction', 'active', 'EUR', now(), now()) "
            "ON CONFLICT (id) DO NOTHING"
        ),
        {"id": project_id, "tid": tenant_id, "code": f"P-{project_id.hex[:8]}"},
    )


async def _create_document(
    db: AsyncSession, document_id: UUID, project_id: UUID, tenant_id: UUID
) -> None:
    await _create_project(db, project_id, tenant_id)
    await db.execute(
        text(
            "INSERT INTO documents "
            "(id, tenant_id, project_id, document_type, filename, upload_status, "
            "storage_encrypted, document_metadata, created_at, updated_at) "
            "VALUES (:id, :tid, :pid, 'contract', 'test.pdf', 'uploaded', true, "
            "'{}'::jsonb, now(), now())"
        ),
        {"id": document_id, "tid": tenant_id, "pid": project_id},
    )


def _snapshot(
    project_id: UUID,
    tenant_id: UUID,
    captured_at: datetime,
    source_event_id: UUID | None = None,
) -> ProjectSnapshot:
    return ProjectSnapshot(
        snapshot_id=uuid4(),
        project_id=project_id,
        tenant_id=tenant_id,
        captured_at=captured_at,
        trigger=SnapshotTrigger.GRAPH_COMPLETED,
        health_vector={"risk": {"score": 0.7}},
        counts={"risks": 2},
        totals={"budget": 100},
        source_event_id=source_event_id,
        created_at=_now_naive(),
    )


async def test_append_snapshots_latest_and_list_since(db: AsyncSession) -> None:
    repo = SqlAlchemyProjectSnapshotRepository(db)
    project_id = uuid4()
    tenant_id = uuid4()
    base = _now_naive()
    first = _snapshot(project_id, tenant_id, base - timedelta(days=1))
    second = _snapshot(project_id, tenant_id, base)

    await repo.append_snapshot(first)
    await repo.append_snapshot(second)
    await db.commit()

    latest = await repo.latest(project_id, tenant_id)
    assert latest is not None
    assert latest.snapshot_id == second.snapshot_id

    tail = await repo.list_since(project_id, tenant_id, since=base - timedelta(hours=1))
    assert [snapshot.snapshot_id for snapshot in tail] == [second.snapshot_id]


async def test_project_snapshots_reject_update_but_allow_delete(db: AsyncSession) -> None:
    repo = SqlAlchemyProjectSnapshotRepository(db)
    snapshot = _snapshot(uuid4(), uuid4(), _now_naive())
    await repo.append_snapshot(snapshot)
    await db.commit()

    with pytest.raises(DBAPIError):
        await db.execute(
            text(
                "UPDATE project_snapshots SET coherence_subscore = 0.4 "
                "WHERE snapshot_id = :snapshot_id"
            ),
            {"snapshot_id": snapshot.snapshot_id},
        )
        await db.commit()
    await db.rollback()

    await db.execute(
        text("DELETE FROM project_snapshots WHERE snapshot_id = :snapshot_id"),
        {"snapshot_id": snapshot.snapshot_id},
    )
    await db.commit()
    assert await repo.latest(snapshot.project_id, snapshot.tenant_id) is None


async def test_snapshot_lineage_references_event_and_document_revision(
    db: AsyncSession,
) -> None:
    project_id = uuid4()
    tenant_id = uuid4()
    document_id = uuid4()
    now = _now_naive()
    await _create_document(db, document_id, project_id, tenant_id)
    await db.commit()

    revision = DocumentRevision(
        revision_id=uuid4(),
        document_id=document_id,
        project_id=project_id,
        tenant_id=tenant_id,
        rev_no=1,
        blob_hash="h1",
        blob_key="k1",
        valid_from=now,
        created_at=now,
    )
    await SqlAlchemyDocumentRevisionRepository(db).append_revision(revision)

    event = ProjectEvent(
        event_id=uuid4(),
        project_id=project_id,
        tenant_id=tenant_id,
        event_type="revision.ingested",
        payload={"revision_id": str(revision.revision_id)},
        source_revision_id=revision.revision_id,
        occurred_at=now,
        created_at=now,
    )
    await SqlAlchemyProjectEventRepository(db).append(event)
    snapshot = _snapshot(project_id, tenant_id, now, source_event_id=event.event_id)
    await SqlAlchemyProjectSnapshotRepository(db).append_snapshot(snapshot)
    await db.commit()

    loaded_snapshot = await SqlAlchemyProjectSnapshotRepository(db).latest(project_id, tenant_id)
    loaded_event = (
        await SqlAlchemyProjectEventRepository(db).list_for_project(project_id, tenant_id)
    )[0]

    assert loaded_snapshot is not None
    assert loaded_snapshot.source_event_id == event.event_id
    assert loaded_event.source_revision_id == revision.revision_id
