"""PostgreSQL FK lineage regression (ADR-015).

Proves the corrected FK path end-to-end without mocking the snapshot
repository:

    document_revisions.revision_id   (durably committed)
    project_events.source_revision_id -> revision_id  (event_type revision.ingested)
    project_snapshots.source_event_id -> event.event_id  (commits, no SQLSTATE 23503)

Test Suite ID: TS-INT-TEMPORAL-REV-LINEAGE-001
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.documents.application.upload_document_use_case import UploadDocumentUseCase
from src.documents.domain.models import DocumentType
from src.temporal.adapters.persistence.document_revision_repository import (
    SqlAlchemyDocumentRevisionRepository,
)
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.adapters.persistence.project_snapshot_repository import (
    SqlAlchemyProjectSnapshotRepository,
)
from src.temporal.domain.project_snapshot import ProjectSnapshot, SnapshotTrigger

pytestmark = pytest.mark.asyncio


def _now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def _create_project(db: AsyncSession, proj_id, tid) -> None:
    await db.execute(
        text(
            "INSERT INTO projects (id, tenant_id, name, code, project_type, status, "
            "currency, created_at, updated_at) "
            "VALUES (:id, :tid, 'test', :code, 'construction', 'active', 'EUR', now(), now()) "
            "ON CONFLICT (id) DO NOTHING"
        ),
        {"id": proj_id, "tid": tid, "code": f"P-{proj_id.hex[:8]}"},
    )
    await db.commit()


async def _create_tenant_and_user(db: AsyncSession, tid, user_id) -> None:
    from src.core.auth.models import SubscriptionPlan, Tenant, User

    tenant = Tenant(
        id=tid,
        name="t",
        slug=f"t-{tid.hex[:8]}",
        subscription_plan=SubscriptionPlan.PROFESSIONAL,
        ai_budget_monthly=100.0,
    )
    user = User(
        id=user_id,
        tenant_id=tid,
        email=f"u-{user_id.hex[:8]}@test.com",
        hashed_password="h",
        first_name="t",
        last_name="t",
        role="admin",
    )
    db.add_all([tenant, user])
    await db.commit()


class _FakeProjectRepo:
    async def exists_by_id(self, _pid, _tid):
        return True


def _fake_file(content: bytes):
    class _IO:
        def read(self):
            return content

        def seek(self, _pos):
            pass

        def tell(self):
            return len(content)

    async def _read(self=None):
        return content

    return type(
        "FakeFile",
        (),
        {"filename": "contract.pdf", "file": _IO(), "size": len(content), "read": _read},
    )()


def _fake_storage():
    storage = AsyncMock()
    storage.file_exists = AsyncMock(return_value=False)
    storage.upload_bytes = AsyncMock(return_value="mock://blob")
    storage.upload_file = AsyncMock(return_value="/fake/contract.pdf")
    return storage


async def test_upload_lineage_commits_revision_event_and_snapshot_fk(db: AsyncSession) -> None:
    tid = uuid4()
    proj_id = uuid4()
    user_id = uuid4()
    await _create_tenant_and_user(db, tid, user_id)
    await _create_project(db, proj_id, tid)

    doc_repo = SqlAlchemyDocumentRepository(db)
    rev_repo = SqlAlchemyDocumentRevisionRepository(db)
    event_repo = SqlAlchemyProjectEventRepository(db)
    snapshot_repo = SqlAlchemyProjectSnapshotRepository(db)
    storage = _fake_storage()

    uc = UploadDocumentUseCase(
        document_repository=doc_repo,
        storage_service=storage,
        project_repository=_FakeProjectRepo(),
        revision_repository=rev_repo,
        event_repository=event_repo,
    )
    document = await uc.execute(
        project_id=proj_id,
        file=_fake_file(b"lineage fk test content"),
        document_type=DocumentType.CONTRACT,
        user_id=user_id,
        tenant_id=tid,
    )

    # 1. The document revision is durably committed.
    lineage = await rev_repo.list_lineage(document.id, tid)
    assert len(lineage) == 1
    revision = lineage[0]
    assert revision.rev_no == 1

    # 2. A revision.ingested ProjectEvent references the revision.
    events = await event_repo.list_for_project(proj_id, tid)
    assert len(events) == 1
    event = events[0]
    assert event.event_type == "revision.ingested"
    assert event.source_revision_id == revision.revision_id
    assert event.actor == str(user_id)

    # 3. A snapshot can reference the event via the FK without SQLSTATE 23503.
    now = _now_naive()
    snapshot = ProjectSnapshot(
        snapshot_id=uuid4(),
        project_id=proj_id,
        tenant_id=tid,
        captured_at=now,
        trigger=SnapshotTrigger.REVISION_INGESTED,
        health_vector={},
        counts={},
        totals={},
        source_event_id=event.event_id,
        created_at=now,
    )
    await snapshot_repo.append_snapshot(snapshot)
    await db.commit()  # must NOT raise IntegrityError (23503)

    latest = await snapshot_repo.latest(proj_id, tid)
    assert latest is not None
    assert latest.source_event_id == event.event_id


async def test_snapshot_source_event_fk_is_enforced(db: AsyncSession) -> None:
    """A snapshot pointing at a non-existent event must violate the FK."""
    snapshot_repo = SqlAlchemyProjectSnapshotRepository(db)
    now = _now_naive()
    snapshot = ProjectSnapshot(
        snapshot_id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        captured_at=now,
        trigger=SnapshotTrigger.SCHEDULED,
        health_vector={},
        counts={},
        totals={},
        source_event_id=uuid4(),
        created_at=now,
    )
    with pytest.raises(IntegrityError):
        await snapshot_repo.append_snapshot(snapshot)
        await db.commit()
    await db.rollback()
