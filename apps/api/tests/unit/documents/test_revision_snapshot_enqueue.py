"""Revision-ingested snapshot enqueue tests (ADR-015 / TASK-V3-015-05)."""

from __future__ import annotations

from io import BytesIO
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
    def __init__(self) -> None:
        self.document: Document | None = None

    async def add(self, _tenant_id, document):
        self.document = document

    async def commit(self):
        return None

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


@pytest.mark.asyncio
async def test_upload_enqueues_revision_ingested_snapshot(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        "src.documents.application.upload_document_use_case.enqueue_project_snapshot",
        lambda **kwargs: calls.append(kwargs),
    )
    tenant_id = uuid4()
    project_id = uuid4()
    revision_repo = _RevisionRepo()
    doc_repo = _UploadDocRepo()

    await UploadDocumentUseCase(
        document_repository=doc_repo,
        storage_service=_Storage(),
        project_repository=_ProjectRepo(),
        revision_repository=revision_repo,
    ).execute(
        project_id=project_id,
        file=UploadFile(filename="contract.pdf", file=BytesIO(b"contract")),
        document_type=DocumentType.CONTRACT,
        user_id=uuid4(),
        tenant_id=tenant_id,
    )

    assert calls == [
        {
            "project_id": project_id,
            "tenant_id": tenant_id,
            "trigger": SnapshotTrigger.REVISION_INGESTED,
            "source_event_id": revision_repo.appended[-1].revision_id,
        }
    ]


@pytest.mark.asyncio
async def test_reupload_enqueues_revision_ingested_snapshot(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        "src.documents.application.reupload_document_use_case.enqueue_project_snapshot",
        lambda **kwargs: calls.append(kwargs),
    )
    tenant_id = uuid4()
    project_id = uuid4()
    document_id = uuid4()
    revision_repo = _RevisionRepo()
    current_doc = Document(
        id=document_id,
        project_id=project_id,
        tenant_id=tenant_id,
        document_type=DocumentType.CONTRACT,
        filename="contract.pdf",
        file_hash="old",
        version=1,
        upload_status=DocumentStatus.UPLOADED,
    )

    class _DocRepo:
        async def get_by_id(self, _tenant_id, _document_id):
            return current_doc

        async def update_version(self, **kwargs):
            current_doc.version = kwargs["version"]
            current_doc.file_hash = kwargs["file_hash"]
            current_doc.filename = kwargs["filename"]
            current_doc.upload_status = DocumentStatus.UPLOADED
            return current_doc

        async def commit(self):
            return None

    await ReuploadDocumentUseCase(
        document_repository=_DocRepo(),
        revision_repository=revision_repo,
        storage_service=_Storage(),
    ).execute(
        tenant_id=tenant_id,
        document_id=document_id,
        file_content=b"new content",
        filename="contract.pdf",
    )

    assert calls == [
        {
            "project_id": project_id,
            "tenant_id": tenant_id,
            "trigger": SnapshotTrigger.REVISION_INGESTED,
            "source_event_id": revision_repo.appended[-1].revision_id,
        }
    ]
