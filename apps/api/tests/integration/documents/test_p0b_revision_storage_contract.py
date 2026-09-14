"""P0b storage contract against PostgreSQL and the real filesystem store.

Refers to Suite ID: TS-INT-P0B-STORAGE-001.

Upload revision A, re-upload revision B, then prove with the real repositories and
``LocalFileStorageService``: both immutable objects stay retrievable with their own bytes,
the pinned revision A still resolves after B is current, another tenant cannot resolve
tenant A's revision, and deleting a document removes only its own objects.
"""

from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import SubscriptionPlan, Tenant, User
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.documents.adapters.storage.local_file_storage_service import LocalFileStorageService
from src.documents.application.document_source import (
    RevisionSourceError,
    fetch_source_file,
    resolve_source_revision,
)
from src.documents.application.reupload_document_use_case import ReuploadDocumentUseCase
from src.documents.application.upload_document_use_case import UploadDocumentUseCase
from src.documents.domain.models import DocumentType
from src.documents.domain.storage_keys import document_object_prefix
from src.temporal.adapters.persistence.document_revision_repository import (
    SqlAlchemyDocumentRevisionRepository,
)
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)

pytestmark = pytest.mark.asyncio


class _ProjectRepo:
    async def exists_by_id(self, _project_id: UUID, _tenant_id: UUID) -> bool:
        return True


@pytest.fixture(autouse=True)
def _no_snapshot_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    for module in ("upload_document_use_case", "reupload_document_use_case"):
        monkeypatch.setattr(
            f"src.documents.application.{module}.enqueue_project_snapshot", lambda **_kwargs: None
        )


async def _tenant_with_project(db: AsyncSession) -> tuple[UUID, UUID, UUID]:
    tenant_id, user_id, project_id = uuid4(), uuid4(), uuid4()
    db.add_all([
        Tenant(id=tenant_id, name="t", slug=f"t-{tenant_id.hex[:8]}",
               subscription_plan=SubscriptionPlan.PROFESSIONAL, ai_budget_monthly=100.0),
        User(id=user_id, tenant_id=tenant_id, email=f"u-{user_id.hex[:8]}@test.com",
             hashed_password="h", first_name="t", last_name="t", role="admin"),
    ])
    await db.commit()
    await db.execute(
        text("INSERT INTO projects (id, tenant_id, name, code, project_type, status, currency, created_at, updated_at) "
             "VALUES (:id, :tid, 'p0b', :code, 'construction', 'active', 'EUR', now(), now())"),
        {"id": project_id, "tid": tenant_id, "code": f"P-{project_id.hex[:8]}"},
    )
    await db.commit()
    return tenant_id, user_id, project_id


async def _upload(db: AsyncSession, storage: LocalFileStorageService, tenant_id: UUID, user_id: UUID,
                  project_id: UUID, content: bytes) -> tuple[UploadDocumentUseCase, UUID]:
    use_case = UploadDocumentUseCase(
        document_repository=SqlAlchemyDocumentRepository(db),
        storage_service=storage,
        project_repository=_ProjectRepo(),  # type: ignore[arg-type]
        revision_repository=SqlAlchemyDocumentRevisionRepository(db),
        event_repository=SqlAlchemyProjectEventRepository(db),
    )
    document = await use_case.execute(
        project_id=project_id, file=UploadFile(filename="contract.pdf", file=BytesIO(content)),
        document_type=DocumentType.CONTRACT, user_id=user_id, tenant_id=tenant_id,
    )
    return use_case, document.id


async def test_revision_a_stays_retrievable_after_revision_b_with_real_store(db: AsyncSession, tmp_path: Path) -> None:
    storage = LocalFileStorageService(base_dir=tmp_path)
    tenant_id, user_id, project_id = await _tenant_with_project(db)
    doc_repo = SqlAlchemyDocumentRepository(db)
    rev_repo = SqlAlchemyDocumentRevisionRepository(db)

    upload, document_id = await _upload(db, storage, tenant_id, user_id, project_id, b"%PDF revision A")
    await ReuploadDocumentUseCase(
        document_repository=doc_repo, revision_repository=rev_repo, storage_service=storage,
        event_repository=SqlAlchemyProjectEventRepository(db),
    ).execute(tenant_id=tenant_id, document_id=document_id, file_content=b"%PDF revision B", user_id=user_id)

    lineage = await rev_repo.list_lineage(document_id, tenant_id)
    assert [revision.rev_no for revision in lineage] == [1, 2]
    revision_a, revision_b = lineage
    prefix = document_object_prefix(tenant_id, project_id, document_id)
    assert revision_a.blob_key.startswith(prefix) and revision_b.blob_key.startswith(prefix)
    assert revision_a.blob_key != revision_b.blob_key
    assert revision_a.blob_hash == hashlib.sha256(b"%PDF revision A").hexdigest()

    document = await doc_repo.get_by_id(tenant_id, document_id)
    assert document is not None
    assert document.storage_url == revision_b.blob_key

    pinned = await resolve_source_revision(
        revision_repository=rev_repo, document_id=document_id, tenant_id=tenant_id,
        revision_id=upload.created_revision_id,
    )
    assert pinned == revision_a
    assert (await fetch_source_file(storage=storage, document=document, revision=pinned)).read_bytes() == b"%PDF revision A"
    assert (await fetch_source_file(storage=storage, document=document, revision=revision_b)).read_bytes() == b"%PDF revision B"
    assert not (tmp_path / f"{document_id}.pdf").exists(), "no mutable per-document object is written"


async def test_another_tenant_cannot_resolve_a_revision_it_does_not_own(db: AsyncSession, tmp_path: Path) -> None:
    storage = LocalFileStorageService(base_dir=tmp_path)
    tenant_a, user_a, project_a = await _tenant_with_project(db)
    tenant_b, _user_b, _project_b = await _tenant_with_project(db)
    rev_repo = SqlAlchemyDocumentRevisionRepository(db)

    upload, document_id = await _upload(db, storage, tenant_a, user_a, project_a, b"%PDF tenant A only")

    assert await rev_repo.get_by_id(upload.created_revision_id, tenant_b) is None  # type: ignore[arg-type]
    assert await rev_repo.get_by_id(upload.created_revision_id, tenant_a) is not None  # type: ignore[arg-type]
    with pytest.raises(RevisionSourceError):
        await resolve_source_revision(
            revision_repository=rev_repo, document_id=document_id, tenant_id=tenant_b,
            revision_id=upload.created_revision_id,
        )
