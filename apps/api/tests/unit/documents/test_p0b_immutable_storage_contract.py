"""P0b immutable document storage contract.

Refers to Suite ID: TS-UT-P0B-STORAGE-001.

One contract for initial upload and re-upload:

* every revision's bytes live at an immutable, tenant/project/document-scoped,
  content-addressed key: ``tenants/{t}/projects/{p}/documents/{d}/revisions/{sha256}{ext}``;
* a later upload never overwrites, moves or deletes an earlier revision's object;
* the mutable ``Document.storage_url`` is only a pointer to the current revision
  object and is never read as revision history;
* the worker reads the pinned (or current) revision object by its exact key and
  fails closed when the bytes do not match the revision hash;
* deleting a document never removes bytes of a document row that still exists.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import UploadFile

from src.documents.application.delete_document_use_case import DeleteDocumentUseCase
from src.documents.application.document_source import (
    RevisionSourceError,
    fetch_source_file,
    resolve_source_revision,
)
from src.documents.application.download_document_use_case import DownloadDocumentUseCase
from src.documents.application.reupload_document_use_case import ReuploadDocumentUseCase
from src.documents.application.upload_document_use_case import UploadDocumentUseCase
from src.documents.domain.models import Document, DocumentStatus, DocumentType
from src.documents.domain.storage_keys import (
    document_object_prefix,
    legacy_document_object_key,
    revision_object_key,
)
from src.temporal.domain.document_revision import DocumentRevision


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class _MemoryStorage:
    """Object store that fails the test if an immutable object is overwritten."""

    def __init__(self, download_dir: Path) -> None:
        self.objects: dict[str, bytes] = {}
        self.writes: list[str] = []
        self.deleted_prefixes: list[str] = []
        self.deleted_files: list[str] = []
        self.fail_cleanup = False
        self._download_dir = download_dir

    async def file_exists(self, key: str) -> bool:
        return key in self.objects

    async def upload_bytes(self, data: bytes, key: str) -> str:
        if key in self.objects and self.objects[key] != data:
            raise AssertionError(f"immutable object {key} overwritten with different bytes")
        self.objects[key] = data
        self.writes.append(key)
        return f"mem://{key}"

    async def upload_file(self, **_kwargs: object) -> str:
        raise AssertionError("the mutable per-document path must never be written")

    async def download_object(self, key: str) -> Path:
        if key not in self.objects:
            raise FileNotFoundError(key)
        path = self._download_dir / f"{uuid4().hex}{Path(key).suffix}"
        path.write_bytes(self.objects[key])
        return path

    async def download_file(self, file_name_in_storage: str) -> Path:
        return await self.download_object(file_name_in_storage)

    async def delete_prefix(self, prefix: str) -> None:
        if self.fail_cleanup:
            raise RuntimeError("object store unavailable")
        self.deleted_prefixes.append(prefix)
        for key in [key for key in self.objects if key.startswith(prefix)]:
            del self.objects[key]

    async def delete_file(self, file_name_in_storage: str) -> None:
        if self.fail_cleanup:
            raise RuntimeError("object store unavailable")
        self.deleted_files.append(file_name_in_storage)
        self.objects.pop(file_name_in_storage, None)


class _DocumentRepo:
    """Document repository fake shared by upload, re-upload, download and delete."""

    def __init__(self, order: list[str] | None = None) -> None:
        self.documents: dict[UUID, Document] = {}
        self.order = order if order is not None else []
        self.fail_delete: Exception | None = None

    async def add(self, _tenant_id: UUID, document: Document) -> None:
        self.documents[document.id] = document

    async def get_by_id(self, tenant_id: UUID, document_id: UUID) -> Document | None:
        document = self.documents.get(document_id)
        return document if document and document.tenant_id == tenant_id else None

    async def commit(self) -> None:
        self.order.append("commit")

    async def refresh(self, _document: Document) -> None:
        return None

    async def update_storage_path(self, _tenant_id: UUID, document_id: UUID, storage_url: str) -> None:
        self.documents[document_id].storage_url = storage_url

    async def update_status(self, _tenant_id: UUID, document_id: UUID, status: DocumentStatus) -> None:
        self.documents[document_id].upload_status = status

    async def update_metadata(self, _tenant_id: UUID, document_id: UUID, metadata: dict) -> None:
        self.documents[document_id].document_metadata = metadata

    async def update_version(self, **kwargs: object) -> Document:
        document = self.documents[kwargs["document_id"]]  # type: ignore[index]
        document.version = kwargs["version"]  # type: ignore[assignment]
        document.file_hash = kwargs["file_hash"]  # type: ignore[assignment]
        document.filename = kwargs["filename"]  # type: ignore[assignment]
        document.upload_status = DocumentStatus.UPLOADED
        return document

    async def delete(self, _tenant_id: UUID, document_id: UUID) -> None:
        self.order.append("db_delete")
        if self.fail_delete is not None:
            raise self.fail_delete
        self.documents.pop(document_id, None)


class _RevisionRepo:
    def __init__(self) -> None:
        self.revisions: list[DocumentRevision] = []

    async def lock_lineage(self, _document_id: UUID, _tenant_id: UUID) -> None:
        return None

    async def append_revision(self, revision: DocumentRevision) -> DocumentRevision:
        self.revisions.append(revision)
        return revision

    async def get_current(self, document_id: UUID, tenant_id: UUID) -> DocumentRevision | None:
        open_revisions = [
            r for r in self.revisions
            if r.document_id == document_id and r.tenant_id == tenant_id and r.valid_to is None
        ]
        return open_revisions[-1] if open_revisions else None

    async def get_by_id(self, revision_id: UUID, tenant_id: UUID) -> DocumentRevision | None:
        for revision in self.revisions:
            if revision.revision_id == revision_id and revision.tenant_id == tenant_id:
                return revision
        return None

    async def close_current(self, document_id: UUID, tenant_id: UUID, valid_to: datetime) -> None:
        for index, revision in enumerate(self.revisions):
            if revision.document_id == document_id and revision.tenant_id == tenant_id and revision.valid_to is None:
                self.revisions[index] = revision.model_copy(update={"valid_to": valid_to})


class _EventRepo:
    def __init__(self) -> None:
        self.events: list[object] = []

    async def append(self, event: object) -> object:
        self.events.append(event)
        return event


class _ProjectRepo:
    async def exists_by_id(self, _project_id: UUID, _tenant_id: UUID) -> bool:
        return True


@pytest.fixture(autouse=True)
def _no_snapshot_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    for module in ("upload_document_use_case", "reupload_document_use_case"):
        monkeypatch.setattr(
            f"src.documents.application.{module}.enqueue_project_snapshot", lambda **_kwargs: None
        )


async def _upload(
    storage: _MemoryStorage,
    doc_repo: _DocumentRepo,
    rev_repo: _RevisionRepo,
    *,
    tenant_id: UUID,
    project_id: UUID,
    content: bytes,
    filename: str = "Contract.PDF",
) -> tuple[UploadDocumentUseCase, Document]:
    use_case = UploadDocumentUseCase(
        document_repository=doc_repo,
        storage_service=storage,  # type: ignore[arg-type]
        project_repository=_ProjectRepo(),  # type: ignore[arg-type]
        revision_repository=rev_repo,  # type: ignore[arg-type]
        event_repository=_EventRepo(),  # type: ignore[arg-type]
    )
    document = await use_case.execute(
        project_id=project_id,
        file=UploadFile(filename=filename, file=BytesIO(content)),
        document_type=DocumentType.CONTRACT,
        user_id=uuid4(),
        tenant_id=tenant_id,
    )
    return use_case, document


def _reupload_use_case(storage: _MemoryStorage, doc_repo: _DocumentRepo, rev_repo: _RevisionRepo) -> ReuploadDocumentUseCase:
    return ReuploadDocumentUseCase(
        document_repository=doc_repo,  # type: ignore[arg-type]
        revision_repository=rev_repo,  # type: ignore[arg-type]
        storage_service=storage,  # type: ignore[arg-type]
        event_repository=_EventRepo(),  # type: ignore[arg-type]
    )


# --- key contract --------------------------------------------------------------------------


def test_revision_key_is_tenant_project_document_scoped_and_content_addressed() -> None:
    tenant_id, project_id, document_id = uuid4(), uuid4(), uuid4()
    digest = _sha(b"revision bytes")

    key = revision_object_key(
        tenant_id=tenant_id, project_id=project_id, document_id=document_id,
        blob_hash=digest, filename="Signed Contract.PDF",
    )

    assert key == f"tenants/{tenant_id}/projects/{project_id}/documents/{document_id}/revisions/{digest}.pdf"
    assert key.startswith(document_object_prefix(tenant_id, project_id, document_id))
    assert document_object_prefix(tenant_id, project_id, document_id).endswith("/")


@pytest.mark.parametrize("bad_hash", ["", "abc", "A" * 64, "../" + "a" * 61, "g" * 64])
def test_revision_key_rejects_anything_but_a_sha256_digest(bad_hash: str) -> None:
    with pytest.raises(ValueError):
        revision_object_key(
            tenant_id=uuid4(), project_id=uuid4(), document_id=uuid4(),
            blob_hash=bad_hash, filename="contract.pdf",
        )


def test_identical_bytes_in_two_tenants_never_share_an_object_key() -> None:
    digest = _sha(b"the same standard contract")
    project_id = uuid4()
    key_a = revision_object_key(tenant_id=uuid4(), project_id=project_id, document_id=uuid4(), blob_hash=digest, filename="c.pdf")
    key_b = revision_object_key(tenant_id=uuid4(), project_id=project_id, document_id=uuid4(), blob_hash=digest, filename="c.pdf")

    assert key_a != key_b


# --- initial upload and re-upload ----------------------------------------------------------


@pytest.mark.asyncio
async def test_initial_upload_stores_bytes_once_at_the_immutable_revision_key(tmp_path: Path) -> None:
    storage, doc_repo, rev_repo = _MemoryStorage(tmp_path), _DocumentRepo(), _RevisionRepo()
    tenant_id, project_id, content = uuid4(), uuid4(), b"%PDF revision A"

    use_case, document = await _upload(storage, doc_repo, rev_repo, tenant_id=tenant_id, project_id=project_id, content=content)

    expected_key = revision_object_key(
        tenant_id=tenant_id, project_id=project_id, document_id=document.id,
        blob_hash=_sha(content), filename="Contract.PDF",
    )
    [genesis] = rev_repo.revisions
    assert storage.writes == [expected_key]
    assert storage.objects[expected_key] == content
    assert genesis.rev_no == 1
    assert genesis.blob_key == expected_key
    assert genesis.blob_hash == _sha(content)
    assert doc_repo.documents[document.id].storage_url == expected_key
    assert use_case.created_revision_id == genesis.revision_id


@pytest.mark.asyncio
async def test_reupload_writes_revision_b_without_touching_revision_a(tmp_path: Path) -> None:
    storage, doc_repo, rev_repo = _MemoryStorage(tmp_path), _DocumentRepo(), _RevisionRepo()
    tenant_id, project_id = uuid4(), uuid4()
    content_a, content_b = b"%PDF revision A", b"%PDF revision B"

    _, document = await _upload(storage, doc_repo, rev_repo, tenant_id=tenant_id, project_id=project_id, content=content_a)
    doc_repo.documents[document.id].file_hash = _sha(content_a)
    key_a = rev_repo.revisions[0].blob_key

    await _reupload_use_case(storage, doc_repo, rev_repo).execute(
        tenant_id=tenant_id, document_id=document.id, file_content=content_b,
        user_id=uuid4(), filename="Contract v2.pdf",
    )

    revision_a, revision_b = rev_repo.revisions
    assert revision_b.rev_no == 2 and revision_b.parent_revision_id == revision_a.revision_id
    assert revision_b.blob_key == revision_object_key(
        tenant_id=tenant_id, project_id=project_id, document_id=document.id,
        blob_hash=_sha(content_b), filename="Contract v2.pdf",
    )
    assert revision_b.blob_key != key_a
    assert storage.objects[key_a] == content_a, "revision A must stay retrievable after revision B"
    assert storage.objects[revision_b.blob_key] == content_b
    assert storage.writes == [key_a, revision_b.blob_key]
    assert doc_repo.documents[document.id].storage_url == revision_b.blob_key


@pytest.mark.asyncio
async def test_legacy_document_genesis_points_at_its_real_legacy_object(tmp_path: Path) -> None:
    """A document uploaded before revisions existed keeps its bytes at ``{id}{ext}``."""
    storage, doc_repo, rev_repo = _MemoryStorage(tmp_path), _DocumentRepo(), _RevisionRepo()
    tenant_id, project_id, document_id = uuid4(), uuid4(), uuid4()
    legacy_bytes = b"%PDF legacy original"
    legacy_key = legacy_document_object_key(document_id, "contract.pdf")
    storage.objects[legacy_key] = legacy_bytes
    doc_repo.documents[document_id] = Document(
        id=document_id, project_id=project_id, tenant_id=tenant_id,
        document_type=DocumentType.CONTRACT, filename="contract.pdf",
        upload_status=DocumentStatus.ANALYZED, file_hash=_sha(legacy_bytes),
    )

    await _reupload_use_case(storage, doc_repo, rev_repo).execute(
        tenant_id=tenant_id, document_id=document_id, file_content=b"%PDF new", user_id=uuid4(),
    )

    genesis, current = rev_repo.revisions
    assert legacy_key == f"{document_id}.pdf"
    assert genesis.blob_key == legacy_key
    assert storage.objects[legacy_key] == legacy_bytes
    source = await fetch_source_file(storage=storage, document=doc_repo.documents[document_id], revision=genesis)  # type: ignore[arg-type]
    assert source.read_bytes() == legacy_bytes
    assert current.blob_key.startswith(document_object_prefix(tenant_id, project_id, document_id))


# --- worker object lookup ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_worker_reads_the_pinned_revision_object_after_a_later_revision_is_current(tmp_path: Path) -> None:
    storage, doc_repo, rev_repo = _MemoryStorage(tmp_path), _DocumentRepo(), _RevisionRepo()
    tenant_id, project_id = uuid4(), uuid4()
    upload, document = await _upload(storage, doc_repo, rev_repo, tenant_id=tenant_id, project_id=project_id, content=b"%PDF A")
    doc_repo.documents[document.id].file_hash = _sha(b"%PDF A")
    await _reupload_use_case(storage, doc_repo, rev_repo).execute(
        tenant_id=tenant_id, document_id=document.id, file_content=b"%PDF B", user_id=uuid4(),
    )

    pinned = await resolve_source_revision(
        revision_repository=rev_repo, document_id=document.id, tenant_id=tenant_id,  # type: ignore[arg-type]
        revision_id=upload.created_revision_id,
    )
    current = await resolve_source_revision(
        revision_repository=rev_repo, document_id=document.id, tenant_id=tenant_id, revision_id=None,  # type: ignore[arg-type]
    )

    assert pinned is not None and pinned.rev_no == 1
    assert current is not None and current.rev_no == 2
    assert (await fetch_source_file(storage=storage, document=document, revision=pinned)).read_bytes() == b"%PDF A"  # type: ignore[arg-type]
    assert (await fetch_source_file(storage=storage, document=document, revision=current)).read_bytes() == b"%PDF B"  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_worker_rejects_a_revision_from_another_document_or_tenant(tmp_path: Path) -> None:
    storage, doc_repo, rev_repo = _MemoryStorage(tmp_path), _DocumentRepo(), _RevisionRepo()
    tenant_a, tenant_b = uuid4(), uuid4()
    upload_a, doc_a = await _upload(storage, doc_repo, rev_repo, tenant_id=tenant_a, project_id=uuid4(), content=b"%PDF tenant A")
    _, doc_b = await _upload(storage, doc_repo, rev_repo, tenant_id=tenant_b, project_id=uuid4(), content=b"%PDF tenant B")

    with pytest.raises(RevisionSourceError, match="revision not found or access denied"):
        await resolve_source_revision(
            revision_repository=rev_repo, document_id=doc_a.id, tenant_id=tenant_b,  # type: ignore[arg-type]
            revision_id=upload_a.created_revision_id,
        )
    with pytest.raises(RevisionSourceError, match="revision not found or access denied"):
        await resolve_source_revision(
            revision_repository=rev_repo, document_id=doc_b.id, tenant_id=tenant_a,  # type: ignore[arg-type]
            revision_id=upload_a.created_revision_id,
        )


@pytest.mark.asyncio
async def test_worker_fails_closed_when_object_bytes_do_not_match_the_revision(tmp_path: Path) -> None:
    storage, doc_repo, rev_repo = _MemoryStorage(tmp_path), _DocumentRepo(), _RevisionRepo()
    _, document = await _upload(storage, doc_repo, rev_repo, tenant_id=uuid4(), project_id=uuid4(), content=b"%PDF A")
    [revision] = rev_repo.revisions
    storage.objects[revision.blob_key] = b"tampered bytes"

    with pytest.raises(RevisionSourceError, match="immutable revision blob hash mismatch"):
        await fetch_source_file(storage=storage, document=document, revision=revision)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_document_without_revisions_reads_only_its_legacy_object(tmp_path: Path) -> None:
    storage, rev_repo = _MemoryStorage(tmp_path), _RevisionRepo()
    document = Document(
        id=uuid4(), project_id=uuid4(), tenant_id=uuid4(), document_type=DocumentType.CONTRACT,
        filename="legacy.docx", upload_status=DocumentStatus.UPLOADED,
    )
    storage.objects[f"{document.id}.docx"] = b"legacy docx"

    revision = await resolve_source_revision(
        revision_repository=rev_repo, document_id=document.id, tenant_id=document.tenant_id, revision_id=None,  # type: ignore[arg-type]
    )

    assert revision is None
    assert (await fetch_source_file(storage=storage, document=document, revision=None)).read_bytes() == b"legacy docx"  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_download_serves_the_current_revision_object(tmp_path: Path) -> None:
    storage, doc_repo, rev_repo = _MemoryStorage(tmp_path), _DocumentRepo(), _RevisionRepo()
    tenant_id = uuid4()
    _, document = await _upload(storage, doc_repo, rev_repo, tenant_id=tenant_id, project_id=uuid4(), content=b"%PDF A")
    doc_repo.documents[document.id].file_hash = _sha(b"%PDF A")
    await _reupload_use_case(storage, doc_repo, rev_repo).execute(
        tenant_id=tenant_id, document_id=document.id, file_content=b"%PDF B", user_id=uuid4(),
    )
    get_document = AsyncMock()
    get_document.execute = AsyncMock(return_value=doc_repo.documents[document.id])

    path, _media_type = await DownloadDocumentUseCase(
        document_repository=doc_repo,  # type: ignore[arg-type]
        storage_service=storage,  # type: ignore[arg-type]
        get_document_use_case=get_document,
        revision_repository=rev_repo,  # type: ignore[arg-type]
    ).execute(document.id, uuid4(), tenant_id)

    assert path.read_bytes() == b"%PDF B"


# --- delete semantics ----------------------------------------------------------------------


def _delete_use_case(storage: _MemoryStorage, doc_repo: _DocumentRepo, document: Document) -> DeleteDocumentUseCase:
    get_document = AsyncMock()
    get_document.execute = AsyncMock(return_value=document)
    return DeleteDocumentUseCase(
        document_repository=doc_repo,  # type: ignore[arg-type]
        storage_service=storage,  # type: ignore[arg-type]
        get_document_use_case=get_document,
    )


@pytest.mark.asyncio
async def test_delete_commits_the_database_delete_before_removing_any_object(tmp_path: Path) -> None:
    order: list[str] = []
    storage, doc_repo, rev_repo = _MemoryStorage(tmp_path), _DocumentRepo(order), _RevisionRepo()
    tenant_id, project_id = uuid4(), uuid4()
    _, document = await _upload(storage, doc_repo, rev_repo, tenant_id=tenant_id, project_id=project_id, content=b"%PDF A")
    order.clear()
    original_delete_prefix = storage.delete_prefix

    async def _recording_delete_prefix(prefix: str) -> None:
        order.append("storage_delete")
        await original_delete_prefix(prefix)

    storage.delete_prefix = _recording_delete_prefix  # type: ignore[method-assign]

    await _delete_use_case(storage, doc_repo, document).execute(document.id, uuid4(), tenant_id)

    assert order.index("db_delete") < order.index("commit") < order.index("storage_delete")
    assert storage.deleted_prefixes == [document_object_prefix(tenant_id, project_id, document.id)]
    assert storage.deleted_files == [legacy_document_object_key(document.id, document.filename)]
    assert storage.objects == {}


@pytest.mark.asyncio
async def test_delete_refused_by_the_database_leaves_every_revision_object(tmp_path: Path) -> None:
    """Append-only history (project_events -> document_revisions) can refuse the delete."""
    storage, doc_repo, rev_repo = _MemoryStorage(tmp_path), _DocumentRepo(), _RevisionRepo()
    tenant_id = uuid4()
    _, document = await _upload(storage, doc_repo, rev_repo, tenant_id=tenant_id, project_id=uuid4(), content=b"%PDF A")
    doc_repo.fail_delete = RuntimeError("violates foreign key constraint project_events_source_revision_id_fkey")
    objects_before = dict(storage.objects)

    with pytest.raises(RuntimeError, match="foreign key"):
        await _delete_use_case(storage, doc_repo, document).execute(document.id, uuid4(), tenant_id)

    assert storage.objects == objects_before
    assert storage.deleted_prefixes == [] and storage.deleted_files == []


@pytest.mark.asyncio
async def test_delete_only_removes_objects_of_that_document(tmp_path: Path) -> None:
    storage, doc_repo, rev_repo = _MemoryStorage(tmp_path), _DocumentRepo(), _RevisionRepo()
    tenant_id, project_id = uuid4(), uuid4()
    same_bytes = b"%PDF identical standard form"
    _, doc_one = await _upload(storage, doc_repo, rev_repo, tenant_id=tenant_id, project_id=project_id, content=same_bytes)
    _, doc_two = await _upload(storage, doc_repo, rev_repo, tenant_id=tenant_id, project_id=project_id, content=same_bytes)
    _, other_tenant_doc = await _upload(storage, doc_repo, rev_repo, tenant_id=uuid4(), project_id=project_id, content=same_bytes)

    await _delete_use_case(storage, doc_repo, doc_one).execute(doc_one.id, uuid4(), tenant_id)

    remaining = set(storage.objects)
    assert rev_repo.revisions[1].blob_key in remaining
    assert rev_repo.revisions[2].blob_key in remaining
    assert rev_repo.revisions[0].blob_key not in remaining
    assert doc_two.id in doc_repo.documents and other_tenant_doc.id in doc_repo.documents


@pytest.mark.asyncio
async def test_storage_cleanup_failure_after_commit_does_not_fail_the_delete(tmp_path: Path) -> None:
    storage, doc_repo, rev_repo = _MemoryStorage(tmp_path), _DocumentRepo(), _RevisionRepo()
    tenant_id = uuid4()
    _, document = await _upload(storage, doc_repo, rev_repo, tenant_id=tenant_id, project_id=uuid4(), content=b"%PDF A")
    storage.fail_cleanup = True

    await _delete_use_case(storage, doc_repo, document).execute(document.id, uuid4(), tenant_id)

    assert document.id not in doc_repo.documents


# --- dispatch pins the immutable revision --------------------------------------------------


@pytest.mark.asyncio
async def test_upload_dispatch_pins_the_created_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.documents.adapters.http import router as router_module

    revision_id = uuid4()
    document = Document(
        id=uuid4(), project_id=uuid4(), tenant_id=uuid4(), document_type=DocumentType.CONTRACT,
        filename="contract.pdf", upload_status=DocumentStatus.UPLOADED, created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    use_case = AsyncMock()
    use_case.execute = AsyncMock(return_value=document)
    use_case.created_revision_id = revision_id
    dispatched: list[tuple[UUID, UUID | None]] = []
    monkeypatch.setattr(
        router_module, "_enqueue_document_processing",
        lambda document_id, revision_id=None: dispatched.append((document_id, revision_id)) or "task-1",
    )

    await router_module.upload_document_for_processing(
        project_id=document.project_id, user_id=uuid4(), tenant_id=document.tenant_id,
        document_type=DocumentType.CONTRACT,
        file=UploadFile(filename="contract.pdf", file=BytesIO(b"%PDF A")),
        upload_use_case=use_case,
    )

    assert dispatched == [(document.id, revision_id)]


def test_processing_task_forwards_the_pinned_revision_to_the_worker() -> None:
    from src.core.tasks import ingestion_tasks

    document_id, revision_id = uuid4(), uuid4()
    task = ingestion_tasks.process_document_async
    run = getattr(task, "run", None)
    with patch.object(ingestion_tasks, "_process", new=AsyncMock(return_value={"status": "ok"})) as process:
        if run is not None:
            run(document_id=str(document_id), revision_id=str(revision_id))
        else:  # the Celery decorator is isolated to a plain bound function in unit runs
            task(SimpleNamespace(request=SimpleNamespace(id=None)), document_id=str(document_id), revision_id=str(revision_id))

    process.assert_awaited_once_with(document_id, revision_id)
