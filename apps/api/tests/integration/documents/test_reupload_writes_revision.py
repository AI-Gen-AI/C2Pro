"""Integration tests for reupload-document writing revisions (ADR-015 / TASK-V3-015-02).

Verifies that ReuploadDocumentUseCase creates DocumentRevision lineage,
preserves genesis, stores content-addressed blobs, and never resets history.
"""

from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.documents.domain.models import DocumentStatus
from src.temporal.adapters.persistence.document_revision_repository import (
    SqlAlchemyDocumentRevisionRepository,
)

pytestmark = pytest.mark.asyncio


async def _create_document_orm(db: AsyncSession, doc_id, proj_id, tid, file_hash="abc", version=1):
    await db.execute(
        text("INSERT INTO projects (id, tenant_id, name, code, project_type, status, currency, created_at, updated_at) "
             "VALUES (:id, :tid, 'test', :code, 'construction', 'active', 'EUR', now(), now()) ON CONFLICT (id) DO NOTHING"),
        {"id": proj_id, "tid": tid, "code": f"P-{proj_id.hex[:8]}"},
    )
    await db.commit()
    await db.execute(
        text(
            "INSERT INTO documents (id, tenant_id, project_id, document_type, filename, "
            "upload_status, version, file_hash, storage_encrypted, document_metadata, created_at, updated_at) "
            "VALUES (:id, :tid, :pid, 'contract', 'test.pdf', 'uploaded', :ver, :hash, true, '{}'::jsonb, now(), now())"
        ),
        {"id": doc_id, "tid": tid, "pid": proj_id, "ver": version, "hash": file_hash},
    )
    await db.commit()


def _mock_storage():
    s = AsyncMock()
    s.file_exists = AsyncMock(return_value=False)
    s.upload_bytes = AsyncMock(return_value="mock://url")
    return s


@pytest.mark.asyncio
async def test_reupload_different_content_preserves_genesis(db: AsyncSession):
    """Re-uploading with DIFFERENT content: genesis (rev 1 = old hash) synthesized,
    new content becomes rev 2. Prior history preserved."""
    from src.documents.adapters.persistence.sqlalchemy_document_repository import (
        SqlAlchemyDocumentRepository,
    )
    from src.documents.application.reupload_document_use_case import ReuploadDocumentUseCase

    doc_id = uuid4()
    proj_id = uuid4()
    tid = uuid4()
    await _create_document_orm(db, doc_id, proj_id, tid, file_hash="old_hash", version=1)

    doc_repo = SqlAlchemyDocumentRepository(db)
    rev_repo = SqlAlchemyDocumentRevisionRepository(db)
    storage = _mock_storage()

    new_content = b"new content for reupload test"
    new_hash = hashlib.sha256(new_content).hexdigest()

    uc = ReuploadDocumentUseCase(
        document_repository=doc_repo,
        revision_repository=rev_repo,
        storage_service=storage,
    )
    result = await uc.execute(tenant_id=tid, document_id=doc_id, file_content=new_content)

    assert result.version == 2
    assert result.file_hash == new_hash
    assert result.upload_status == DocumentStatus.UPLOADED

    lineage = await rev_repo.list_lineage(doc_id, tid)
    assert len(lineage) == 2, f"Expected 2 revisions (genesis + new), got {len(lineage)}"
    assert lineage[0].rev_no == 1
    assert lineage[0].blob_hash == "old_hash"
    assert lineage[0].parent_revision_id is None
    assert lineage[0].valid_to is not None  # genesis closed
    assert lineage[1].rev_no == 2
    assert lineage[1].blob_hash == new_hash
    assert lineage[1].parent_revision_id == lineage[0].revision_id
    assert lineage[1].valid_to is None  # current open

    # Verify blob was stored
    storage.upload_bytes.assert_called_once()


@pytest.mark.asyncio
async def test_reupload_same_content_idempotent(db: AsyncSession):
    """Re-uploading with SAME content returns existing, no new revision, no genesis synthesized."""
    from src.documents.adapters.persistence.sqlalchemy_document_repository import (
        SqlAlchemyDocumentRepository,
    )
    from src.documents.application.reupload_document_use_case import ReuploadDocumentUseCase

    doc_id = uuid4()
    proj_id = uuid4()
    tid = uuid4()
    content = b"same content"
    same_hash = hashlib.sha256(content).hexdigest()
    await _create_document_orm(db, doc_id, proj_id, tid, file_hash=same_hash, version=1)

    doc_repo = SqlAlchemyDocumentRepository(db)
    rev_repo = SqlAlchemyDocumentRevisionRepository(db)
    storage = _mock_storage()

    uc = ReuploadDocumentUseCase(
        document_repository=doc_repo,
        revision_repository=rev_repo,
        storage_service=storage,
    )
    result = await uc.execute(tenant_id=tid, document_id=doc_id, file_content=content)

    assert result.version == 1
    assert result.file_hash == same_hash

    lineage = await rev_repo.list_lineage(doc_id, tid)
    assert len(lineage) == 0

    storage.upload_bytes.assert_not_called()


@pytest.mark.asyncio
async def test_reupload_twice_builds_full_lineage(db: AsyncSession):
    """Two re-uploads: genesis (rev 1 = v0), content1 (rev 2), content2 (rev 3)."""
    from src.documents.adapters.persistence.sqlalchemy_document_repository import (
        SqlAlchemyDocumentRepository,
    )
    from src.documents.application.reupload_document_use_case import ReuploadDocumentUseCase

    doc_id = uuid4()
    proj_id = uuid4()
    tid = uuid4()
    await _create_document_orm(db, doc_id, proj_id, tid, file_hash="v0", version=1)

    doc_repo = SqlAlchemyDocumentRepository(db)
    rev_repo = SqlAlchemyDocumentRevisionRepository(db)
    storage = _mock_storage()

    c1 = b"content v1"
    c2 = b"content v2"
    h1 = hashlib.sha256(c1).hexdigest()
    h2 = hashlib.sha256(c2).hexdigest()

    uc = ReuploadDocumentUseCase(
        document_repository=doc_repo,
        revision_repository=rev_repo,
        storage_service=storage,
    )
    await uc.execute(tenant_id=tid, document_id=doc_id, file_content=c1)
    await uc.execute(tenant_id=tid, document_id=doc_id, file_content=c2)

    lineage = await rev_repo.list_lineage(doc_id, tid)
    assert len(lineage) == 3, f"Expected 3 revisions, got {len(lineage)}"
    assert lineage[0].rev_no == 1 and lineage[0].blob_hash == "v0"
    assert lineage[1].rev_no == 2 and lineage[1].blob_hash == h1
    assert lineage[2].rev_no == 3 and lineage[2].blob_hash == h2
    assert lineage[2].parent_revision_id == lineage[1].revision_id
    assert lineage[1].parent_revision_id == lineage[0].revision_id
    assert lineage[0].valid_to is not None
    assert lineage[1].valid_to is not None
    assert lineage[2].valid_to is None

    assert storage.upload_bytes.call_count == 2


@pytest.mark.asyncio
async def test_blob_key_is_retrievable(db: AsyncSession):
    """After reupload, the blob_key in the revision matches content hash."""
    from src.documents.adapters.persistence.sqlalchemy_document_repository import (
        SqlAlchemyDocumentRepository,
    )
    from src.documents.application.reupload_document_use_case import ReuploadDocumentUseCase

    doc_id = uuid4()
    proj_id = uuid4()
    tid = uuid4()
    await _create_document_orm(db, doc_id, proj_id, tid, file_hash="old", version=1)

    doc_repo = SqlAlchemyDocumentRepository(db)
    rev_repo = SqlAlchemyDocumentRevisionRepository(db)
    storage = _mock_storage()

    new_content = b"blob test content"
    new_hash = hashlib.sha256(new_content).hexdigest()

    uc = ReuploadDocumentUseCase(
        document_repository=doc_repo,
        revision_repository=rev_repo,
        storage_service=storage,
    )
    await uc.execute(tenant_id=tid, document_id=doc_id, file_content=new_content)

    current = await rev_repo.get_current(doc_id, tid)
    assert current is not None
    expected_key = f"revisions/{new_hash}.pdf"
    assert current.blob_key == expected_key

    storage.file_exists.assert_called_with(expected_key)
    storage.upload_bytes.assert_called_with(new_content, expected_key)


@pytest.mark.asyncio
async def test_storage_skip_when_blob_exists(db: AsyncSession):
    """When blob already exists in storage, skip upload but still create revision row."""
    from src.documents.adapters.persistence.sqlalchemy_document_repository import (
        SqlAlchemyDocumentRepository,
    )
    from src.documents.application.reupload_document_use_case import ReuploadDocumentUseCase

    doc_id = uuid4()
    proj_id = uuid4()
    tid = uuid4()
    await _create_document_orm(db, doc_id, proj_id, tid, file_hash="old", version=1)

    doc_repo = SqlAlchemyDocumentRepository(db)
    rev_repo = SqlAlchemyDocumentRevisionRepository(db)

    storage = AsyncMock()
    storage.file_exists = AsyncMock(return_value=True)
    storage.upload_bytes = AsyncMock()

    new_content = b"already exists"
    uc = ReuploadDocumentUseCase(
        document_repository=doc_repo,
        revision_repository=rev_repo,
        storage_service=storage,
    )
    await uc.execute(tenant_id=tid, document_id=doc_id, file_content=new_content)

    storage.upload_bytes.assert_not_called()

    lineage = await rev_repo.list_lineage(doc_id, tid)
    assert len(lineage) == 2  # genesis + new revision row


@pytest.mark.asyncio
async def test_di_wiring_produces_working_use_case(db: AsyncSession):
    """Verify the router DI provider functions wire a working use case with
    revision_repository + storage_service bound to the same session."""

    from src.documents.adapters.http.router import (
        get_document_repository,
        get_document_revision_repository,
        get_reupload_use_case,
        get_storage_service,
    )
    from src.documents.adapters.persistence.sqlalchemy_document_repository import (
        SqlAlchemyDocumentRepository,
    )
    from src.temporal.adapters.persistence.document_revision_repository import (
        SqlAlchemyDocumentRevisionRepository,
    )

    doc_id = uuid4()
    proj_id = uuid4()
    tid = uuid4()
    await _create_document_orm(db, doc_id, proj_id, tid, file_hash="old", version=1)

    # Simulate the FastAPI DI chain manually
    doc_repo = get_document_repository(db=db)
    rev_repo = get_document_revision_repository(db=db)
    assert isinstance(doc_repo, SqlAlchemyDocumentRepository)
    assert isinstance(rev_repo, SqlAlchemyDocumentRevisionRepository)

    storage = get_storage_service()
    uc = get_reupload_use_case(repo=doc_repo, rev_repo=rev_repo, storage=storage)

    new_content = b"di test content"
    result = await uc.execute(tenant_id=tid, document_id=doc_id, file_content=new_content)

    assert result.version == 2
    lineage = await rev_repo.list_lineage(doc_id, tid)
    assert len(lineage) == 2  # genesis + new


@pytest.mark.asyncio
async def test_upload_creates_genesis_revision_with_storage(db: AsyncSession):
    """UploadDocumentUseCase with revision_repository creates genesis rev_no==1
    and stores the content-addressed blob."""
    import hashlib
    from unittest.mock import AsyncMock

    from src.documents.adapters.persistence.sqlalchemy_document_repository import (
        SqlAlchemyDocumentRepository,
    )
    from src.documents.application.upload_document_use_case import UploadDocumentUseCase
    from src.documents.domain.models import DocumentType
    from src.temporal.adapters.persistence.document_revision_repository import (
        SqlAlchemyDocumentRevisionRepository,
    )

    proj_id = uuid4()
    tid = uuid4()
    user_id = uuid4()

    # Create tenant + user via ORM to get all NOT NULL defaults
    from src.core.auth.models import SubscriptionPlan, Tenant, User
    tenant = Tenant(id=tid, name="t", slug=f"t-{tid.hex[:8]}", subscription_plan=SubscriptionPlan.PROFESSIONAL, ai_budget_monthly=100.0)
    user = User(id=user_id, tenant_id=tid, email=f"u-{user_id.hex[:8]}@test.com", hashed_password="h", first_name="t", last_name="t", role="admin")
    db.add_all([tenant, user])
    await db.commit()

    await db.execute(
        text("INSERT INTO projects (id, tenant_id, name, code, project_type, status, currency, created_at, updated_at) "
             "VALUES (:id, :tid, 'test', :code, 'construction', 'active', 'EUR', now(), now()) ON CONFLICT (id) DO NOTHING"),
        {"id": proj_id, "tid": tid, "code": f"P-{proj_id.hex[:8]}"},
    )
    await db.commit()

    doc_repo = SqlAlchemyDocumentRepository(db)
    rev_repo = SqlAlchemyDocumentRevisionRepository(db)

    content = b"upload genesis test content"
    content_hash = hashlib.sha256(content).hexdigest()
    expected_key = f"revisions/{content_hash}.pdf"

    storage = AsyncMock()
    storage.file_exists = AsyncMock(return_value=False)
    storage.upload_bytes = AsyncMock(return_value=f"mock://{expected_key}")
    storage.upload_file = AsyncMock(return_value="/fake/path.pdf")

    class _FakeProjectRepo:
        async def exists_by_id(self, pid, _tid):
            return True

    class _FakeIO:
        def read(self):
            return content
        def seek(self, _pos):
            pass
        def tell(self):
            return len(content)

    async def _async_read(self=None):
        return content

    fake_file = type("FakeFile", (), {
        "filename": "test.pdf",
        "file": _FakeIO(),
        "size": len(content),
        "read": _async_read,
    })()

    uc = UploadDocumentUseCase(
        document_repository=doc_repo,
        storage_service=storage,
        project_repository=_FakeProjectRepo(),
        revision_repository=rev_repo,
    )
    result = await uc.execute(
        project_id=proj_id,
        file=fake_file,
        document_type=DocumentType.CONTRACT,
        user_id=user_id,
        tenant_id=tid,
    )

    assert result is not None

    current = await rev_repo.get_current(result.id, tid)
    assert current is not None, "Genesis revision must exist after upload"
    assert current.rev_no == 1
    assert current.blob_hash == content_hash
    assert current.blob_key == expected_key

    storage.file_exists.assert_called_with(expected_key)
    storage.upload_bytes.assert_called_with(content, expected_key)
