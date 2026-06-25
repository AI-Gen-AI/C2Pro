# ruff: noqa: S101
"""
Test Suite: Document Use Cases
Component: Documents Module - Application Layer Use Cases
Priority: P2

Tests to improve coverage for document use cases.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException


class TestExtractEntitiesUseCase:
    """Tests for ExtractEntitiesUseCase."""

    @pytest.mark.asyncio
    async def test_execute_finds_document(self):
        """Test execute finds and processes document."""
        from src.documents.application.extract_entities_use_case import ExtractEntitiesUseCase
        from src.documents.domain.models import Document, DocumentType

        mock_repo = MagicMock()
        mock_extraction = MagicMock()

        document_id = uuid4()
        project_id = uuid4()
        tenant_id = uuid4()

        mock_doc = Document(
            id=document_id,
            project_id=project_id,
            tenant_id=tenant_id,
            document_type=DocumentType.CONTRACT,
            filename="test.pdf",
            file_format=".pdf",
            upload_status="uploaded",
        )

        mock_repo.get_by_id = AsyncMock(return_value=mock_doc)
        mock_repo.get_project_tenant_id = AsyncMock(return_value=tenant_id)
        mock_extraction.extract_entities_from_document = AsyncMock(
            return_value={"companies": 2, "dates": 5}
        )

        use_case = ExtractEntitiesUseCase(
            document_repository=mock_repo,
            entity_extraction_service=mock_extraction,
        )

        result = await use_case.execute(tenant_id, document_id, {"text": "test"})

        assert result == {"companies": 2, "dates": 5}

    @pytest.mark.asyncio
    async def test_execute_document_not_found(self):
        """Test execute raises 404 when document not found."""
        from src.documents.application.extract_entities_use_case import ExtractEntitiesUseCase

        mock_repo = MagicMock()
        mock_extraction = MagicMock()

        mock_repo.get_by_id = AsyncMock(return_value=None)

        use_case = ExtractEntitiesUseCase(
            document_repository=mock_repo,
            entity_extraction_service=mock_extraction,
        )

        with pytest.raises(HTTPException) as exc_info:
            await use_case.execute(uuid4(), uuid4(), {})

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_execute_access_denied(self):
        """Test execute raises 404 when tenant-scoped document lookup fails."""
        from src.documents.application.extract_entities_use_case import ExtractEntitiesUseCase

        mock_repo = MagicMock()
        mock_extraction = MagicMock()

        tenant_id = uuid4()
        document_id = uuid4()
        mock_repo.get_by_id = AsyncMock(return_value=None)

        use_case = ExtractEntitiesUseCase(
            document_repository=mock_repo,
            entity_extraction_service=mock_extraction,
        )

        with pytest.raises(HTTPException) as exc_info:
            await use_case.execute(tenant_id, document_id, {})

        assert exc_info.value.status_code == 404
        mock_repo.get_by_id.assert_awaited_once_with(tenant_id, document_id)


class TestListProjectDocumentsUseCase:
    """Tests for ListProjectDocumentsUseCase."""

    @pytest.mark.asyncio
    async def test_execute_returns_documents(self):
        """Test execute returns list of documents."""
        from src.documents.application.list_project_documents_use_case import (
            ListProjectDocumentsUseCase,
        )
        from src.documents.domain.models import Document, DocumentType

        mock_repo = MagicMock()
        mock_project_repo = MagicMock()

        project_id = uuid4()
        tenant_id = uuid4()
        docs = [
            Document(
                id=uuid4(),
                project_id=project_id,
                tenant_id=uuid4(),
                document_type=DocumentType.CONTRACT,
                filename="doc1.pdf",
                file_format=".pdf",
                upload_status="uploaded",
            ),
        ]

        mock_repo.list_for_project = AsyncMock(return_value=(docs, 1))
        mock_project_repo.get_by_id = AsyncMock(return_value=object())

        use_case = ListProjectDocumentsUseCase(
            document_repository=mock_repo,
            project_repository=mock_project_repo,
        )
        result, _ = await use_case.execute(project_id, tenant_id, skip=0, limit=10)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_execute_empty_list(self):
        """Test execute returns empty list when no documents."""
        from src.documents.application.list_project_documents_use_case import (
            ListProjectDocumentsUseCase,
        )

        mock_repo = MagicMock()
        mock_project_repo = MagicMock()
        mock_repo.list_for_project = AsyncMock(return_value=([], 0))
        mock_project_repo.get_by_id = AsyncMock(return_value=object())

        use_case = ListProjectDocumentsUseCase(
            document_repository=mock_repo,
            project_repository=mock_project_repo,
        )
        result, _ = await use_case.execute(uuid4(), uuid4())

        assert result == []


class TestAnswerRagQuestionUseCase:
    """Tests for AnswerRagQuestionUseCase."""

    @pytest.mark.asyncio
    async def test_execute_returns_answer(self):
        """Test execute returns answer from RAG."""
        from src.documents.application.answer_rag_question_use_case import (
            AnswerRagQuestionUseCase,
        )
        from src.documents.application.dtos import RagAnswer, RetrievedChunk

        mock_rag = MagicMock()

        mock_rag.answer_question = AsyncMock(
            return_value=RagAnswer(
                answer="The total is 1000 euros.",
                sources=[
                    RetrievedChunk(content="Page 1: total 1000", metadata={}, similarity=0.9)
                ],
            )
        )

        use_case = AnswerRagQuestionUseCase(rag_service=mock_rag)
        result = await use_case.execute(
            question="What is the total?",
            project_id=uuid4(),
            tenant_id=uuid4(),
            top_k=5,
        )

        assert "total" in result.answer.lower()

    @pytest.mark.asyncio
    async def test_execute_no_results(self):
        """Test execute handles no results."""
        from src.documents.application.answer_rag_question_use_case import (
            AnswerRagQuestionUseCase,
        )
        from src.documents.application.dtos import RagAnswer

        mock_rag = MagicMock()

        mock_rag.answer_question = AsyncMock(
            return_value=RagAnswer(answer="No lo encuentro en el documento", sources=[])
        )

        use_case = AnswerRagQuestionUseCase(rag_service=mock_rag)
        result = await use_case.execute(
            question="What is the total?",
            project_id=uuid4(),
            tenant_id=uuid4(),
            top_k=5,
        )

        assert "No lo encuentro" in result.answer


class TestCheckClauseExistsUseCase:
    """Tests for CheckClauseExistsUseCase."""

    @pytest.mark.asyncio
    async def test_execute_returns_true(self):
        """Test execute returns true when clause exists."""
        from src.documents.application.check_clause_exists_use_case import (
            CheckClauseExistsUseCase,
        )

        mock_repo = MagicMock()

        clause_id = uuid4()
        mock_repo.clause_exists = AsyncMock(return_value=True)

        use_case = CheckClauseExistsUseCase(document_repository=mock_repo)
        result = await use_case.execute(tenant_id=uuid4(), clause_id=clause_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_execute_returns_false(self):
        """Test execute returns false when clause not found."""
        from src.documents.application.check_clause_exists_use_case import (
            CheckClauseExistsUseCase,
        )

        mock_repo = MagicMock()

        clause_id = uuid4()
        mock_repo.clause_exists = AsyncMock(return_value=False)

        use_case = CheckClauseExistsUseCase(document_repository=mock_repo)
        result = await use_case.execute(tenant_id=uuid4(), clause_id=clause_id)

        assert result is False


class TestGetClauseTextMapUseCase:
    """Tests for GetClauseTextMapUseCase."""

    @pytest.mark.asyncio
    async def test_execute_returns_mapping(self):
        """Test execute returns clause text mapping."""
        from src.documents.application.get_clause_text_map_use_case import (
            GetClauseTextMapUseCase,
        )

        mock_repo = MagicMock()

        clause_ids = [uuid4(), uuid4()]
        mock_repo.get_clause_text_map = AsyncMock(
            return_value={clause_ids[0]: "text1", clause_ids[1]: "text2"}
        )

        use_case = GetClauseTextMapUseCase(document_repository=mock_repo)
        result = await use_case.execute(tenant_id=uuid4(), clause_ids=clause_ids)

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_execute_empty_input(self):
        """Test execute handles empty input."""
        from src.documents.application.get_clause_text_map_use_case import (
            GetClauseTextMapUseCase,
        )

        mock_repo = MagicMock()

        use_case = GetClauseTextMapUseCase(document_repository=mock_repo)
        result = await use_case.execute(tenant_id=uuid4(), clause_ids=[])

        assert result == {}
