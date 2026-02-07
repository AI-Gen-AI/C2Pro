"""
TS-UA-DOC-UC-001: Upload Document Use Case tests.
"""

from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, Mock

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
        return SimpleNamespace(filename=filename, size=size, file=file_obj)

    @pytest.mark.asyncio
    async def test_001_rejects_file_over_size_limit(self, monkeypatch):
        monkeypatch.setattr(settings, "max_upload_size_mb", 0)
        file = self._make_upload_file("contract.pdf", 2)

        repo = AsyncMock()
        storage = AsyncMock()
        use_case = UploadDocumentUseCase(repo, storage)

        with pytest.raises(HTTPException) as exc:
            await use_case.execute(
                project_id=uuid4(),
                file=file,
                document_type=DocumentType.CONTRACT,
                user_id=uuid4(),
            )

        assert exc.value.status_code == 413

    @pytest.mark.asyncio
    async def test_002_rejects_unsupported_file_type(self, monkeypatch):
        monkeypatch.setattr(settings, "allowed_document_types", [".pdf"])
        file = self._make_upload_file("contract.exe", 1)

        repo = AsyncMock()
        storage = AsyncMock()
        use_case = UploadDocumentUseCase(repo, storage)

        with pytest.raises(HTTPException) as exc:
            await use_case.execute(
                project_id=uuid4(),
                file=file,
                document_type=DocumentType.CONTRACT,
                user_id=uuid4(),
            )

        assert exc.value.status_code == 415

    @pytest.mark.asyncio
    async def test_003_project_not_found_raises(self):
        file = self._make_upload_file("contract.pdf", 1)

        repo = AsyncMock()
        repo.get_project_tenant_id.return_value = None
        storage = AsyncMock()
        use_case = UploadDocumentUseCase(repo, storage)

        with pytest.raises(HTTPException) as exc:
            await use_case.execute(
                project_id=uuid4(),
                file=file,
                document_type=DocumentType.CONTRACT,
                user_id=uuid4(),
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
        repo.get_project_tenant_id.return_value = tenant_id
        storage = AsyncMock()
        storage.upload_file.return_value = "/local-storage/contract.pdf"

        use_case = UploadDocumentUseCase(repo, storage)

        document = await use_case.execute(
            project_id=project_id,
            file=file,
            document_type=DocumentType.CONTRACT,
            user_id=user_id,
        )

        repo.add.assert_awaited_once()
        added_doc = repo.add.call_args.args[0]
        assert added_doc.project_id == project_id
        assert added_doc.filename == "contract.pdf"
        assert added_doc.upload_status == DocumentStatus.QUEUED

        storage.upload_file.assert_awaited_once()
        upload_kwargs = storage.upload_file.call_args.kwargs
        assert upload_kwargs["file_id"] == added_doc.id
        assert upload_kwargs["file_extension"] == ".pdf"

        repo.update_storage_path.assert_awaited_once_with(added_doc.id, "/local-storage/contract.pdf")
        repo.update_status.assert_awaited_once_with(added_doc.id, DocumentStatus.UPLOADED)
        repo.refresh.assert_awaited_once_with(added_doc)
        assert isinstance(document.id, UUID)
