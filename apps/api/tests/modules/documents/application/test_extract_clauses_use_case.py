"""
TS-UA-DOC-UC-002: Extract Clauses Use Case tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from src.documents.application.extract_clauses_use_case import ExtractClausesUseCase
from src.documents.domain.models import Clause, ClauseType, Document, DocumentStatus, DocumentType


class TestExtractClausesUseCase:
    """Refers to Suite ID: TS-UA-DOC-UC-002."""

    def _make_document(self) -> Document:
        return Document(
            id=uuid4(),
            project_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="contract.pdf",
            upload_status=DocumentStatus.PARSED,
        )

    @pytest.mark.asyncio
    async def test_001_extract_clauses_use_case_success(self):
        document = self._make_document()
        clause = Clause(
            id=uuid4(),
            project_id=document.project_id,
            document_id=document.id,
            clause_code="1.1",
            clause_type=ClauseType.SCOPE,
            title="Scope",
            full_text="Scope text",
        )

        repo = AsyncMock()
        repo.get_by_id.return_value = document
        repo.get_project_tenant_id.return_value = uuid4()

        service = AsyncMock()
        service.extract_from_text.return_value = [clause]

        use_case = ExtractClausesUseCase(repo, service)

        result = await use_case.execute(document_id=document.id, text="Clause 1.1 text")

        service.extract_from_text.assert_awaited_once()
        repo.add_clause.assert_awaited_once_with(clause)
        repo.commit.assert_awaited_once()
        assert result == [clause]

    @pytest.mark.asyncio
    async def test_002_extract_clauses_use_case_no_clauses_found(self):
        document = self._make_document()

        repo = AsyncMock()
        repo.get_by_id.return_value = document
        repo.get_project_tenant_id.return_value = uuid4()

        service = AsyncMock()
        service.extract_from_text.return_value = []

        use_case = ExtractClausesUseCase(repo, service)

        result = await use_case.execute(document_id=document.id, text="No clauses")

        repo.add_clause.assert_not_awaited()
        repo.commit.assert_not_awaited()
        assert result == []

    @pytest.mark.asyncio
    async def test_003_document_not_found_raises(self):
        repo = AsyncMock()
        repo.get_by_id.return_value = None

        service = AsyncMock()
        use_case = ExtractClausesUseCase(repo, service)

        with pytest.raises(HTTPException) as exc:
            await use_case.execute(document_id=uuid4(), text="text")

        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_004_project_not_found_raises(self):
        document = self._make_document()
        repo = AsyncMock()
        repo.get_by_id.return_value = document
        repo.get_project_tenant_id.return_value = None

        service = AsyncMock()
        use_case = ExtractClausesUseCase(repo, service)

        with pytest.raises(HTTPException) as exc:
            await use_case.execute(document_id=document.id, text="text")

        assert exc.value.status_code == 404
