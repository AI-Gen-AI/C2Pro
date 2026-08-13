"""
TS-UA-DOC-UC-001: Upload Document Use Case tests.
"""

from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from src.config import settings
from src.documents.application.upload_document_use_case import UploadDocumentUseCase
from src.documents.domain.models import DocumentStatus, DocumentType


class TestUploadDocumentUseCase:
    """Refers to Suite ID: TS-UA-DOC-UC-001."""

    def _make_upload_file(self, filename: str, size: int):
        file_obj = BytesIO(b"x" * size)
        file_obj.seek = Mock(wraps=file_obj.seek)

        async def read() -> bytes:
            return file_obj.read()

        return SimpleNamespace(filename=filename, size=size, file=file_obj, read=read)

    @pytest.mark.asyncio
    async def test_001_rejects_file_over_size_limit(self):
        file = self._make_upload_file(
            "contract.pdf",
            settings.max_upload_size_bytes + 1,
        )

        repo = AsyncMock()
        storage = AsyncMock()
        project_repository = AsyncMock()
        use_case = UploadDocumentUseCase(repo, storage, project_repository)

        with pytest.raises(HTTPException) as exc:
            await use_case.execute(
                project_id=uuid4(),
                file=file,
                document_type=DocumentType.CONTRACT,
                user_id=uuid4(),
                tenant_id=uuid4(),
            )

        assert exc.value.status_code == 413

    @pytest.mark.asyncio
    async def test_002_rejects_unsupported_file_type(self, monkeypatch):
        monkeypatch.setattr(settings, "allowed_document_types", [".pdf"])
        file = self._make_upload_file("contract.exe", 1)

        repo = AsyncMock()
        storage = AsyncMock()
        project_repository = AsyncMock()
        use_case = UploadDocumentUseCase(repo, storage, project_repository)

        with pytest.raises(HTTPException) as exc:
            await use_case.execute(
                project_id=uuid4(),
                file=file,
                document_type=DocumentType.CONTRACT,
                user_id=uuid4(),
                tenant_id=uuid4(),
            )

        assert exc.value.status_code == 415

    @pytest.mark.asyncio
    async def test_003_project_not_found_raises(self):
        file = self._make_upload_file("contract.pdf", 1)

        repo = AsyncMock()
        storage = AsyncMock()
        project_repository = AsyncMock()
        project_repository.exists_by_id.return_value = False
        use_case = UploadDocumentUseCase(repo, storage, project_repository)

        with pytest.raises(HTTPException) as exc:
            await use_case.execute(
                project_id=uuid4(),
                file=file,
                document_type=DocumentType.CONTRACT,
                user_id=uuid4(),
                tenant_id=uuid4(),
            )

        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_004_successful_upload_persists_and_updates(self, monkeypatch):
        monkeypatch.setattr(settings, "allowed_document_types", [".pdf"])
        monkeypatch.setattr(settings, "max_upload_size_mb", 1)

        file = self._make_upload_file("contract.pdf", 4)
        project_id = uuid4()
        user_id = uuid4()
        tenant_id = uuid4()

        repo = AsyncMock()
        storage = AsyncMock()
        storage.upload_file.return_value = "/local-storage/contract.pdf"
        project_repository = AsyncMock()
        project_repository.exists_by_id.return_value = True

        use_case = UploadDocumentUseCase(repo, storage, project_repository)

        document = await use_case.execute(
            project_id=project_id,
            file=file,
            document_type=DocumentType.CONTRACT,
            user_id=user_id,
            tenant_id=tenant_id,
        )

        repo.add.assert_awaited_once()
        added_tenant_id, added_doc = repo.add.call_args.args
        assert added_tenant_id == tenant_id
        assert added_doc.project_id == project_id
        assert added_doc.tenant_id == tenant_id
        assert added_doc.filename == "contract.pdf"
        assert added_doc.upload_status == DocumentStatus.QUEUED

        storage.upload_file.assert_awaited_once()
        upload_kwargs = storage.upload_file.call_args.kwargs
        assert upload_kwargs["file_id"] == added_doc.id
        assert upload_kwargs["file_extension"] == ".pdf"

        repo.update_storage_path.assert_awaited_once_with(
            tenant_id, added_doc.id, "/local-storage/contract.pdf"
        )
        repo.update_status.assert_awaited_once_with(
            tenant_id, added_doc.id, DocumentStatus.UPLOADED
        )
        project_repository.exists_by_id.assert_awaited_once_with(project_id, tenant_id)
        repo.refresh.assert_awaited_once_with(added_doc)
        assert isinstance(document.id, UUID)

    @pytest.mark.asyncio
    async def test_004b_snapshot_enqueue_failure_does_not_fail_upload(self, monkeypatch):
        """A Celery/broker outage on the snapshot enqueue must NOT fail the upload.

        Regression: on Railway the synchronous `enqueue_project_snapshot` raised
        (broker unreachable) -> HTTP 500, rolling back the genesis revision while
        the document row remained. The enqueue is now best-effort.
        """
        monkeypatch.setattr(settings, "allowed_document_types", [".pdf"])
        monkeypatch.setattr(settings, "max_upload_size_mb", 1)
        monkeypatch.setattr(
            "src.documents.application.upload_document_use_case.enqueue_project_snapshot",
            Mock(side_effect=RuntimeError("broker down")),
        )

        file = self._make_upload_file("contract.pdf", 4)
        repo = AsyncMock()
        storage = AsyncMock()
        storage.upload_file.return_value = "/local-storage/contract.pdf"
        storage.file_exists.return_value = False
        project_repository = AsyncMock()
        project_repository.exists_by_id.return_value = True
        revision_repository = AsyncMock()

        use_case = UploadDocumentUseCase(
            repo, storage, project_repository, revision_repository=revision_repository
        )

        document = await use_case.execute(
            project_id=uuid4(),
            file=file,
            document_type=DocumentType.CONTRACT,
            user_id=uuid4(),
            tenant_id=uuid4(),
        )

        # Upload succeeded despite the enqueue raising.
        assert isinstance(document.id, UUID)
        # The genesis revision was still appended (it must persist).
        revision_repository.append_revision.assert_awaited_once()
        repo.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_005_contract_docx_upload_is_allowed(self, monkeypatch):
        monkeypatch.setattr(settings, "allowed_document_types", [".pdf", ".docx"])

        file = self._make_upload_file("contract.docx", 4)
        project_id = uuid4()
        user_id = uuid4()
        tenant_id = uuid4()

        repo = AsyncMock()
        storage = AsyncMock()
        storage.upload_file.return_value = "/local-storage/contract.docx"
        project_repository = AsyncMock()
        project_repository.exists_by_id.return_value = True

        use_case = UploadDocumentUseCase(repo, storage, project_repository)

        document = await use_case.execute(
            project_id=project_id,
            file=file,
            document_type=DocumentType.CONTRACT,
            user_id=user_id,
            tenant_id=tenant_id,
        )

        assert document.file_format == ".docx"
        storage.upload_file.assert_awaited_once()
        assert storage.upload_file.call_args.kwargs["file_extension"] == ".docx"

    @pytest.mark.asyncio
    async def test_006_budget_docx_upload_is_rejected(self, monkeypatch):
        monkeypatch.setattr(settings, "allowed_document_types", [".pdf", ".docx", ".xlsx", ".bc3"])
        file = self._make_upload_file("budget.docx", 4)

        repo = AsyncMock()
        storage = AsyncMock()
        project_repository = AsyncMock()
        use_case = UploadDocumentUseCase(repo, storage, project_repository)

        with pytest.raises(HTTPException) as exc:
            await use_case.execute(
                project_id=uuid4(),
                file=file,
                document_type=DocumentType.BUDGET,
                user_id=uuid4(),
                tenant_id=uuid4(),
            )

        assert exc.value.status_code == 400
        assert exc.value.detail == "budget/schedule require .xlsx/.bc3"
        project_repository.exists_by_id.assert_not_awaited()
