"""Integration tests for DocumentRevision lineage (ADR-015 / TASK-V3-015-01)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.temporal.adapters.persistence.document_revision_repository import (
    SqlAlchemyDocumentRevisionRepository,
)
from src.temporal.domain.document_revision import DocumentRevision

pytestmark = pytest.mark.asyncio


def _now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def _create_project(db: AsyncSession, proj_id, tid):
    await db.execute(
        text("INSERT INTO projects (id, tenant_id, name, code, project_type, status, currency, created_at, updated_at) "
             "VALUES (:id, :tid, 'test', :code, 'construction', 'active', 'EUR', now(), now()) "
             "ON CONFLICT (id) DO NOTHING"),
        {"id": proj_id, "tid": tid, "code": f"P-{proj_id.hex[:8]}"},
    )
    await db.commit()


async def _create_document(db: AsyncSession, doc_id, proj_id, tid):
    await _create_project(db, proj_id, tid)
    await db.execute(
        text(
            "INSERT INTO documents (id, tenant_id, project_id, document_type, filename, "
            "upload_status, storage_encrypted, document_metadata, created_at, updated_at) "
            "VALUES (:id, :tid, :pid, 'contract', 'test.pdf', 'uploaded', true, '{}'::jsonb, now(), now())"
        ),
        {"id": doc_id, "tid": tid, "pid": proj_id},
    )
    await db.commit()


@pytest.mark.asyncio
async def test_first_revision_append_and_get(db: AsyncSession):
    repo = SqlAlchemyDocumentRevisionRepository(db)
    doc_id = uuid4()
    proj_id = uuid4()
    tid = uuid4()
    now = _now_naive()
    await _create_document(db, doc_id, proj_id, tid)

    rev = DocumentRevision(
        revision_id=uuid4(), document_id=doc_id, project_id=proj_id,
        tenant_id=tid, rev_no=1, blob_hash="sha256_111",
        blob_key="revisions/sha256_111.pdf", valid_from=now, created_at=now,
    )
    await repo.append_revision(rev)
    await db.commit()

    current = await repo.get_current(doc_id, tid)
    assert current is not None and current.rev_no == 1
    assert current.parent_revision_id is None
    assert current.valid_to is None

    lineage = await repo.list_lineage(doc_id, tid)
    assert len(lineage) == 1
    assert lineage[0].revision_id == rev.revision_id


@pytest.mark.asyncio
async def test_second_revision_supersedes_first(db: AsyncSession):
    repo = SqlAlchemyDocumentRevisionRepository(db)
    doc_id = uuid4()
    proj_id = uuid4()
    tid = uuid4()
    now = _now_naive()
    await _create_document(db, doc_id, proj_id, tid)

    rev1 = DocumentRevision(
        revision_id=uuid4(), document_id=doc_id, project_id=proj_id,
        tenant_id=tid, rev_no=1, blob_hash="h1", blob_key="k1",
        valid_from=now, created_at=now,
    )
    await repo.append_revision(rev1)
    await db.commit()

    rev2 = DocumentRevision(
        revision_id=uuid4(), document_id=doc_id, project_id=proj_id,
        tenant_id=tid, rev_no=2, parent_revision_id=rev1.revision_id,
        blob_hash="h2", blob_key="k2", valid_from=_now_naive(), created_at=_now_naive(),
    )
    await repo.close_current(doc_id, tid, rev2.valid_from)
    await repo.append_revision(rev2)
    await db.commit()

    current = await repo.get_current(doc_id, tid)
    assert current is not None and current.rev_no == 2

    lineage = await repo.list_lineage(doc_id, tid)
    assert len(lineage) == 2
    assert lineage[0].rev_no == 1 and lineage[1].rev_no == 2
    assert lineage[0].valid_to is not None


@pytest.mark.asyncio
async def test_get_current_excludes_closed_revisions(db: AsyncSession):
    repo = SqlAlchemyDocumentRevisionRepository(db)
    doc_id = uuid4()
    proj_id = uuid4()
    tid = uuid4()
    await _create_document(db, doc_id, proj_id, tid)

    rev1 = DocumentRevision(
        revision_id=uuid4(), document_id=doc_id, project_id=proj_id,
        tenant_id=tid, rev_no=1, blob_hash="h1", blob_key="k1",
        valid_from=_now_naive(), created_at=_now_naive(),
    )
    await repo.append_revision(rev1)
    await repo.close_current(doc_id, tid, _now_naive())
    await db.commit()

    current = await repo.get_current(doc_id, tid)
    assert current is None


@pytest.mark.asyncio
async def test_tenant_isolation_in_repo(db: AsyncSession):
    repo = SqlAlchemyDocumentRevisionRepository(db)
    doc_a = uuid4()
    proj_a = uuid4()
    tid_a = uuid4()
    tid_b = uuid4()
    now = _now_naive()
    await _create_document(db, doc_a, proj_a, tid_a)

    rev_a = DocumentRevision(
        revision_id=uuid4(), document_id=doc_a, project_id=proj_a,
        tenant_id=tid_a, rev_no=1, blob_hash="ha", blob_key="ka",
        valid_from=now, created_at=now,
    )
    await repo.append_revision(rev_a)
    await db.commit()

    assert await repo.get_current(doc_a, tid_b) is None
    assert await repo.list_lineage(doc_a, tid_b) == []
