"""
TS-UA-DOC-UC-003: Extract Entities Use Case tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.documents.application.extract_entities_use_case import ExtractEntitiesUseCase
from src.documents.domain.models import Document, DocumentStatus, DocumentType


class TestExtractEntitiesUseCase:
    """Refers to Suite ID: TS-UA-DOC-UC-003."""

    def _make_document(self) -> Document:
        return Document(
            id=uuid4(),
            project_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="contract.pdf",
            upload_status=DocumentStatus.PARSED,
        )

    @pytest.mark.asyncio
    async def test_001_extract_entities_success_returns_summary(self):
        document = self._make_document()
        summary = {"stakeholders": 2, "wbs_items": 1, "bom_items": 0}

        repo = AsyncMock()
        repo.get_by_id.return_value = document
        repo.get_project_tenant_id.return_value = uuid4()

        service = AsyncMock()
        service.extract_entities_from_document.return_value = summary

        use_case = ExtractEntitiesUseCase(repo, service)

        result = await use_case.execute(document_id=document.id, parsed_payload={"text": "value"})

        service.extract_entities_from_document.assert_awaited_once()
        repo.get_project_tenant_id.assert_awaited_once_with(document.project_id)
        repo.commit.assert_not_awaited()
        assert result == summary

    @pytest.mark.asyncio
    async def test_002_document_not_found_raises(self):
        repo = AsyncMock()
        repo.get_by_id.return_value = None

        service = AsyncMock()
        use_case = ExtractEntitiesUseCase(repo, service)

        with pytest.raises(HTTPException) as exc:
            await use_case.execute(document_id=uuid4(), parsed_payload={})

        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_003_project_not_found_raises(self):
        document = self._make_document()

        repo = AsyncMock()
        repo.get_by_id.return_value = document
        repo.get_project_tenant_id.return_value = None

        service = AsyncMock()
        use_case = ExtractEntitiesUseCase(repo, service)

        with pytest.raises(HTTPException) as exc:
            await use_case.execute(document_id=document.id, parsed_payload={})

        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_004_service_called_with_expected_arguments(self):
        document = self._make_document()
        tenant_id = uuid4()
        payload = {"sections": ["a", "b"]}

        repo = AsyncMock()
        repo.get_by_id.return_value = document
        repo.get_project_tenant_id.return_value = tenant_id

        service = AsyncMock()
        service.extract_entities_from_document.return_value = {"stakeholders": 0, "wbs_items": 0, "bom_items": 0}

        use_case = ExtractEntitiesUseCase(repo, service)

        await use_case.execute(document_id=document.id, parsed_payload=payload)

        service.extract_entities_from_document.assert_awaited_once_with(
            document=document,
            parsed_payload=payload,
            tenant_id=tenant_id,
        )
