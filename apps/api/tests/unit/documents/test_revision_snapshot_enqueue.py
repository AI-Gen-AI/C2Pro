"""Revision-ingested snapshot lineage tests (ADR-015 / TASK-V3-015-05).

Proves the corrected lineage contract:

    DocumentRevision.revision_id -> ProjectEvent.source_revision_id
    ProjectEvent.event_id        -> ProjectSnapshot.source_event_id

The old behaviour encoded ``source_event_id = revision.revision_id``, which
violates the ``project_snapshots.source_event_id -> project_events.event_id``
foreign key. These tests lock the corrected contract in.

Test Suite ID: TS-UT-DOC-REV-LINEAGE-001
"""

from __future__ import annotations

from io import BytesIO
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import UploadFile

from src.documents.application.reupload_document_use_case import ReuploadDocumentUseCase
from src.documents.application.upload_document_use_case import UploadDocumentUseCase
from src.documents.domain.models import Document, DocumentStatus, DocumentType
from src.temporal.domain.project_snapshot import SnapshotTrigger


class _Storage:
    async def upload_file(self, **_kwargs):
        return "documents/file.pdf"

    async def file_exists(self, _key):
        return True

    async def upload_bytes(self, _content, _key):
        return None


class _ProjectRepo:
    async def exists_by_id(self, _project_id, _tenant_id):
        return True


class _UploadDocRepo:
    def __init__(self, order: list[str] | None = None) -> None:
        self.document: Document | None = None
        self.commit_calls = 0
        self.fail_on_commit_at: int | None = None
        self.order = order if order is not None else []

    async def add(self, _tenant_id, document):
        self.document = document

    async def commit(self):
        self.commit_calls += 1
        self.order.append("commit")
        if self.fail_on_commit_at == self.commit_calls:
            raise RuntimeError("commit failed")

    async def update_storage_path(self, _tenant_id, _document_id, _path):
        return None

    async def update_status(self, _tenant_id, _document_id, status):
        assert self.document is not None
        self.document.upload_status = status

    async def update_metadata(self, _tenant_id, _document_id, _metadata):
        return None

    async def refresh(self, _document):
        return None


class _RevisionRepo:
    def __init__(self) -> None:
        self.appended = []

    async def append_revision(self, revision):
        self.appended.append(revision)

    async def get_current(self, _document_id, _tenant_id):
        return self.appended[-1] if self.appended else None

    async def close_current(self, _document_id, _tenant_id, _valid_to):
        return None


class _EventRepo:
    def __init__(self) -> None:
        self.appended = []
        self.fail_on_append = False

    async def append(self, event):
        if self.fail_on_append:
            raise RuntimeError("event append failed")
        self.appended.append(event)
        return event


class _ReuploadDocRepo:
    def __init__(self, current_doc: Document, order: list[str] | None = None) -> None:
        self.current_doc = current_doc
        self.commit_calls = 0
        self.fail_on_commit_at: int | None = None
        self.order = order if order is not None else []

    async def get_by_id(self, _tenant_id, _document_id):
        return self.current_doc

    async def update_version(self, **kwargs):
        self.current_doc.version = kwargs["version"]
        self.current_doc.file_hash = kwargs["file_hash"]
        self.current_doc.filename = kwargs["filename"]
        self.current_doc.upload_status = DocumentStatus.UPLOADED
        return self.current_doc

    async def commit(self):
        self.commit_calls += 1
        self.order.append("commit")
        if self.fail_on_commit_at == self.commit_calls:
            raise RuntimeError("commit failed")


def _make_document(document_id, project_id, tenant_id) -> Document:
    return Document(
        id=document_id,
        project_id=project_id,
        tenant_id=tenant_id,
        document_type=DocumentType.CONTRACT,
        filename="contract.pdf",
        file_hash="old",
        version=1,
        upload_status=DocumentStatus.UPLOADED,
    )


@pytest.mark.asyncio
async def test_upload_enqueues_snapshot_with_event_id_not_revision_id(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        "src.documents.application.upload_document_use_case.enqueue_project_snapshot",
        lambda **kwargs: calls.append(kwargs),
    )
    tenant_id = uuid4()
    project_id = uuid4()
    user_id = uuid4()
    revision_repo = _RevisionRepo()
    event_repo = _EventRepo()

    await UploadDocumentUseCase(
        document_repository=_UploadDocRepo(),
        storage_service=_Storage(),
        project_repository=_ProjectRepo(),
        revision_repository=revision_repo,
        event_repository=event_repo,
    ).execute(
        project_id=project_id,
        file=UploadFile(filename="contract.pdf", file=BytesIO(b"contract")),
        document_type=DocumentType.CONTRACT,
        user_id=user_id,
        tenant_id=tenant_id,
    )

    revision = revision_repo.appended[-1]
    event = event_repo.appended[-1]
    assert event.event_type == "revision.ingested"
    assert event.source_revision_id == revision.revision_id
    assert event.actor == str(user_id)
    assert event.event_id != revision.revision_id
    assert calls == [
        {
            "project_id": project_id,
            "tenant_id": tenant_id,
            "trigger": SnapshotTrigger.REVISION_INGESTED,
            "source_event_id": event.event_id,
        }
    ]


@pytest.mark.asyncio
async def test_upload_enqueues_after_successful_commit(monkeypatch) -> None:
    order: list[str] = []
    doc_repo = _UploadDocRepo(order=order)
    monkeypatch.setattr(
        "src.documents.application.upload_document_use_case.enqueue_project_snapshot",
        lambda **kwargs: order.append("enqueue"),
    )

    await UploadDocumentUseCase(
        document_repository=doc_repo,
        storage_service=_Storage(),
        project_repository=_ProjectRepo(),
        revision_repository=_RevisionRepo(),
        event_repository=_EventRepo(),
    ).execute(
        project_id=uuid4(),
        file=UploadFile(filename="contract.pdf", file=BytesIO(b"contract")),
        document_type=DocumentType.CONTRACT,
        user_id=uuid4(),
        tenant_id=uuid4(),
    )

    assert order[-1] == "enqueue"
    assert order.count("commit") == 3
    assert order.index("commit") < order.index("enqueue")


@pytest.mark.asyncio
async def test_upload_event_append_failure_never_enqueues(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        "src.documents.application.upload_document_use_case.enqueue_project_snapshot",
        lambda **kwargs: calls.append(kwargs),
    )
    event_repo = _EventRepo()
    event_repo.fail_on_append = True

    with pytest.raises(RuntimeError, match="event append failed"):
        await UploadDocumentUseCase(
            document_repository=_UploadDocRepo(),
            storage_service=_Storage(),
            project_repository=_ProjectRepo(),
            revision_repository=_RevisionRepo(),
            event_repository=event_repo,
        ).execute(
            project_id=uuid4(),
            file=UploadFile(filename="contract.pdf", file=BytesIO(b"contract")),
            document_type=DocumentType.CONTRACT,
            user_id=uuid4(),
            tenant_id=uuid4(),
        )

    assert calls == []


@pytest.mark.asyncio
async def test_upload_revision_event_commit_failure_never_enqueues(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        "src.documents.application.upload_document_use_case.enqueue_project_snapshot",
        lambda **kwargs: calls.append(kwargs),
    )
    doc_repo = _UploadDocRepo()
    doc_repo.fail_on_commit_at = 3

    with pytest.raises(RuntimeError, match="commit failed"):
        await UploadDocumentUseCase(
            document_repository=doc_repo,
            storage_service=_Storage(),
            project_repository=_ProjectRepo(),
            revision_repository=_RevisionRepo(),
            event_repository=_EventRepo(),
        ).execute(
            project_id=uuid4(),
            file=UploadFile(filename="contract.pdf", file=BytesIO(b"contract")),
            document_type=DocumentType.CONTRACT,
            user_id=uuid4(),
            tenant_id=uuid4(),
        )

    assert calls == []


@pytest.mark.asyncio
async def test_reupload_enqueues_snapshot_with_event_id_not_revision_id(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        "src.documents.application.reupload_document_use_case.enqueue_project_snapshot",
        lambda **kwargs: calls.append(kwargs),
    )
    tenant_id = uuid4()
    project_id = uuid4()
    document_id = uuid4()
    user_id = uuid4()
    revision_repo = _RevisionRepo()
    event_repo = _EventRepo()

    await ReuploadDocumentUseCase(
        document_repository=_ReuploadDocRepo(_make_document(document_id, project_id, tenant_id)),
        revision_repository=revision_repo,
        storage_service=_Storage(),
        event_repository=event_repo,
    ).execute(
        tenant_id=tenant_id,
        document_id=document_id,
        file_content=b"new content",
        filename="contract.pdf",
        user_id=user_id,
    )

    revision = revision_repo.appended[-1]
    event = event_repo.appended[-1]
    assert event.event_type == "revision.ingested"
    assert event.source_revision_id == revision.revision_id
    assert event.actor == str(user_id)
    assert event.event_id != revision.revision_id
    assert calls == [
        {
            "project_id": project_id,
            "tenant_id": tenant_id,
            "trigger": SnapshotTrigger.REVISION_INGESTED,
            "source_event_id": event.event_id,
        }
    ]


@pytest.mark.asyncio
async def test_reupload_enqueues_after_successful_commit(monkeypatch) -> None:
    order: list[str] = []
    tenant_id = uuid4()
    project_id = uuid4()
    document_id = uuid4()
    doc_repo = _ReuploadDocRepo(_make_document(document_id, project_id, tenant_id), order=order)
    monkeypatch.setattr(
        "src.documents.application.reupload_document_use_case.enqueue_project_snapshot",
        lambda **kwargs: order.append("enqueue"),
    )

    await ReuploadDocumentUseCase(
        document_repository=doc_repo,
        revision_repository=_RevisionRepo(),
        storage_service=_Storage(),
        event_repository=_EventRepo(),
    ).execute(
        tenant_id=tenant_id,
        document_id=document_id,
        file_content=b"new content",
        filename="contract.pdf",
        user_id=uuid4(),
    )

    assert order == ["commit", "enqueue"]


@pytest.mark.asyncio
async def test_reupload_event_append_failure_never_enqueues(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        "src.documents.application.reupload_document_use_case.enqueue_project_snapshot",
        lambda **kwargs: calls.append(kwargs),
    )
    tenant_id = uuid4()
    project_id = uuid4()
    document_id = uuid4()
    event_repo = _EventRepo()
    event_repo.fail_on_append = True

    with pytest.raises(RuntimeError, match="event append failed"):
        await ReuploadDocumentUseCase(
            document_repository=_ReuploadDocRepo(_make_document(document_id, project_id, tenant_id)),
            revision_repository=_RevisionRepo(),
            storage_service=_Storage(),
            event_repository=event_repo,
        ).execute(
            tenant_id=tenant_id,
            document_id=document_id,
            file_content=b"new content",
            filename="contract.pdf",
            user_id=uuid4(),
        )

    assert calls == []


@pytest.mark.asyncio
async def test_reupload_commit_failure_never_enqueues(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        "src.documents.application.reupload_document_use_case.enqueue_project_snapshot",
        lambda **kwargs: calls.append(kwargs),
    )
    tenant_id = uuid4()
    project_id = uuid4()
    document_id = uuid4()
    doc_repo = _ReuploadDocRepo(_make_document(document_id, project_id, tenant_id))
    doc_repo.fail_on_commit_at = 1

    with pytest.raises(RuntimeError, match="commit failed"):
        await ReuploadDocumentUseCase(
            document_repository=doc_repo,
            revision_repository=_RevisionRepo(),
            storage_service=_Storage(),
            event_repository=_EventRepo(),
        ).execute(
            tenant_id=tenant_id,
            document_id=document_id,
            file_content=b"new content",
            filename="contract.pdf",
            user_id=uuid4(),
        )

    assert calls == []


@pytest.mark.asyncio
async def test_reupload_enqueue_failure_does_not_fail_operation(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.documents.application.reupload_document_use_case.enqueue_project_snapshot",
        Mock(side_effect=RuntimeError("broker down")),
    )
    tenant_id = uuid4()
    project_id = uuid4()
    document_id = uuid4()
    doc_repo = _ReuploadDocRepo(_make_document(document_id, project_id, tenant_id))

    result = await ReuploadDocumentUseCase(
        document_repository=doc_repo,
        revision_repository=_RevisionRepo(),
        storage_service=_Storage(),
        event_repository=_EventRepo(),
    ).execute(
        tenant_id=tenant_id,
        document_id=document_id,
        file_content=b"new content",
        filename="contract.pdf",
        user_id=uuid4(),
    )

    assert result.version == 2


def test_upload_requires_event_repository_when_revision_repository_present() -> None:
    with pytest.raises(ValueError, match="event_repository"):
        UploadDocumentUseCase(
            document_repository=_UploadDocRepo(),
            storage_service=_Storage(),
            project_repository=_ProjectRepo(),
            revision_repository=_RevisionRepo(),
        )


def test_reupload_requires_event_repository() -> None:
    with pytest.raises(TypeError):
        ReuploadDocumentUseCase(
            document_repository=_ReuploadDocRepo(_make_document(uuid4(), uuid4(), uuid4())),
            revision_repository=_RevisionRepo(),
            storage_service=_Storage(),
        )


@pytest.mark.asyncio
async def test_reupload_rejects_docx_for_schedule_document() -> None:
    tenant_id = uuid4()
    project_id = uuid4()
    document_id = uuid4()
    current_doc = Document(
        id=document_id,
        project_id=project_id,
        tenant_id=tenant_id,
        document_type=DocumentType.SCHEDULE,
        filename="schedule.xlsx",
        file_hash="old",
        version=1,
        upload_status=DocumentStatus.UPLOADED,
    )

    with pytest.raises(ValueError, match="budget/schedule require .xlsx/.bc3"):
        await ReuploadDocumentUseCase(
            document_repository=_ReuploadDocRepo(current_doc),
            revision_repository=_RevisionRepo(),
            storage_service=_Storage(),
            event_repository=_EventRepo(),
        ).execute(
            tenant_id=tenant_id,
            document_id=document_id,
            file_content=b"new content",
            filename="schedule.docx",
            user_id=uuid4(),
        )
