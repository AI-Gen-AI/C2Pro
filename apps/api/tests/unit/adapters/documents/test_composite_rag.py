"""
Test Suite: Composite Parser and RAG Service Additional Tests
Component: Documents Module - Composite Parser & RAG
Priority: P1

Additional tests to improve coverage.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

# ===========================================
# COMPOSITE PARSER TESTS
# ===========================================

class TestCompositeParserAdvanced:
    """Advanced tests for CompositeFileParser."""

    def test_create_factory_method(self):
        """Test factory method creates parser with default instances."""
        from src.documents.adapters.parsers.composite_file_parser import CompositeFileParser

        parser = CompositeFileParser.create()

        assert parser is not None
        assert parser.bc3_parser is not None
        assert parser.excel_parser is not None
        assert parser.pdf_parser is not None

    def test_parser_delegates_to_pdf(self):
        """Test parser delegates to PDF parser for .pdf files."""
        from src.documents.adapters.parsers.composite_file_parser import CompositeFileParser
        from src.documents.domain.models import Document, DocumentType

        mock_pdf = MagicMock()
        mock_pdf.extract_text_and_offsets = AsyncMock(return_value=[{"text": "test", "bbox": (0,0,100,20)}])

        parser = CompositeFileParser(
            bc3_parser=MagicMock(),
            excel_parser=MagicMock(),
            pdf_parser=mock_pdf,
        )

        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="test.pdf",
            file_format=".pdf",
            upload_status="uploaded",
        )

        # Create temp file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(b'%PDF-1.4')
            tmp_path = tmp.name

        try:
            import asyncio
            result = asyncio.run(parser.parse_document_file(doc, Path(tmp_path)))
            assert "file_format" in result
        finally:
            os.unlink(tmp_path)

    def test_parser_delegates_to_bc3(self):
        """Test parser delegates to BC3 parser for .bc3 files."""
        from src.documents.adapters.parsers.composite_file_parser import CompositeFileParser
        from src.documents.domain.models import Document, DocumentType

        mock_bc3 = MagicMock()
        mock_bc3.parse = AsyncMock(return_value=[{"item": "Item 1", "quantity": 10}])

        parser = CompositeFileParser(
            bc3_parser=mock_bc3,
            excel_parser=MagicMock(),
            pdf_parser=MagicMock(),
        )

        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            document_type=DocumentType.BUDGET,
            filename="test.bc3",
            file_format=".bc3",
            upload_status="uploaded",
        )

        with tempfile.NamedTemporaryFile(suffix='.bc3', delete=False) as tmp:
            tmp.write(b'*')
            tmp_path = tmp.name

        try:
            import asyncio
            result = asyncio.run(parser.parse_document_file(doc, Path(tmp_path)))
            assert "file_format" in result
        finally:
            os.unlink(tmp_path)

    def test_parser_unsupported_format(self):
        """Test parser raises error for unsupported format."""
        from src.documents.adapters.parsers.composite_file_parser import CompositeFileParser
        from src.documents.domain.models import Document, DocumentType

        parser = CompositeFileParser(
            bc3_parser=MagicMock(),
            excel_parser=MagicMock(),
            pdf_parser=MagicMock(),
        )

        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            document_type=DocumentType.OTHER,
            filename="test.txt",
            file_format=".txt",
            upload_status="uploaded",
        )

        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with pytest.raises(ValueError) as exc_info:
                import asyncio
                asyncio.run(parser.parse_document_file(doc, Path(tmp_path)))
            assert "no parser available" in str(exc_info.value).lower()
        finally:
            os.unlink(tmp_path)


# ===========================================
# RAG SERVICE TESTS
# ===========================================

class TestRagService:
    """Tests for RagService."""

    def test_rag_service_initialization(self):
        """Test RagService initialization."""
        from src.documents.adapters.rag.rag_service import RagService

        mock_session = MagicMock()
        service = RagService(mock_session)

        assert service is not None

    def test_rag_service_has_required_methods(self):
        """Test RagService has required methods."""
        from src.documents.adapters.rag.rag_service import RagService

        mock_session = MagicMock()
        service = RagService(mock_session)

        assert hasattr(service, "ingest_document")
        assert hasattr(service, "answer_question")


class TestRagIngestionServiceAdvanced:
    """Advanced tests for SqlAlchemyRagIngestionService."""

    def test_service_initialization(self):
        """Test service initialization."""
        from src.documents.adapters.rag.sqlalchemy_rag_ingestion_service import (
            SqlAlchemyRagIngestionService,
        )

        mock_session = MagicMock()
        service = SqlAlchemyRagIngestionService(db_session=mock_session)

        assert service.db_session is mock_session
        assert service._rag_service is not None

    def test_service_has_ingest_method(self):
        """Test service has ingest method."""
        from src.documents.adapters.rag.sqlalchemy_rag_ingestion_service import (
            SqlAlchemyRagIngestionService,
        )

        mock_session = MagicMock()
        service = SqlAlchemyRagIngestionService(db_session=mock_session)

        assert hasattr(service, "ingest_document_chunks")


class TestRagServiceAdapter:
    """Tests for SqlAlchemyRagService adapter."""

    def test_adapter_initialization(self):
        """Test adapter initialization."""
        from src.documents.adapters.rag.rag_service_adapter import SqlAlchemyRagService

        mock_session = MagicMock()
        adapter = SqlAlchemyRagService(db_session=mock_session)

        assert adapter.rag_service is not None

    def test_adapter_has_answer_method(self):
        """Test adapter has answer_question method."""
        from src.documents.adapters.rag.rag_service_adapter import SqlAlchemyRagService

        mock_session = MagicMock()
        adapter = SqlAlchemyRagService(db_session=mock_session)

        assert hasattr(adapter, "answer_question")


class TestRagServicePureFunctions:
    """Tests for RAG service pure functions."""

    def test_split_text_empty(self):
        """Test _split_text returns empty list for empty string."""
        from src.documents.adapters.rag.rag_service import _split_text

        result = _split_text("", chunk_size=1000, overlap=200)
        assert result == []

    def test_split_text_none(self):
        """Test _split_text returns empty list for None."""
        from src.documents.adapters.rag.rag_service import _split_text

        result = _split_text(None, chunk_size=1000, overlap=200)  # type: ignore
        assert result == []

    def test_split_text_short_text(self):
        """Test _split_text returns single chunk for short text."""
        from src.documents.adapters.rag.rag_service import _split_text

        short_text = "This is a short text"
        result = _split_text(short_text, chunk_size=1000, overlap=200)
        assert len(result) == 1
        assert result[0] == short_text

    def test_split_text_with_whitespace(self):
        """Test _split_text normalizes whitespace."""
        from src.documents.adapters.rag.rag_service import _split_text

        text_with_whitespace = "  Multiple   spaces   and\n\nnewlines  "
        result = _split_text(text_with_whitespace, chunk_size=1000, overlap=200)
        assert "Multiple spaces and newlines" in result[0]

    def test_split_text_long_text(self):
        """Test _split_text splits long text into multiple chunks."""
        from src.documents.adapters.rag.rag_service import _split_text

        long_text = "A" * 3000
        result = _split_text(long_text, chunk_size=1000, overlap=200)
        assert len(result) > 1

    def test_split_text_with_overlap(self):
        """Test _split_text uses overlap parameter."""
        from src.documents.adapters.rag.rag_service import _split_text

        text = "ABCDEFGHIJ" * 200
        result_no_overlap = _split_text(text, chunk_size=100, overlap=0)
        result_with_overlap = _split_text(text, chunk_size=100, overlap=50)

        assert len(result_with_overlap) >= len(result_no_overlap)

    def test_format_vector(self):
        """Test _format_vector formats embedding correctly."""
        from src.documents.adapters.rag.rag_service import _format_vector

        embedding = [0.1, 0.2, 0.3]
        result = _format_vector(embedding)

        assert result.startswith("[")
        assert result.endswith("]")
        assert "0.100000" in result or "0.100000" in result

    def test_format_vector_truncates_long(self):
        """Test _format_vector truncates to EMBEDDING_DIMENSION."""
        from src.documents.adapters.rag.rag_service import EMBEDDING_DIMENSION, _format_vector

        long_embedding = [0.1] * 2000
        result = _format_vector(long_embedding)

        count = result.count(",") + 1
        assert count == EMBEDDING_DIMENSION

    def test_build_answer_prompt(self):
        """Test _build_answer_prompt builds correct prompt."""
        from src.documents.adapters.rag.rag_service import _build_answer_prompt

        question = "What is the total?"
        context = "The total is 1000 euros."
        result = _build_answer_prompt(question=question, context=context)

        assert "CONTEXTO" in result
        assert "PREGUNTA" in result
        assert "What is the total?" in result
        assert "The total is 1000 euros." in result
        assert "No lo encuentro" in result

    def test_build_answer_prompt_empty_context(self):
        """Test _build_answer_prompt with empty context."""
        from src.documents.adapters.rag.rag_service import _build_answer_prompt

        result = _build_answer_prompt(question="Test?", context="")
        assert "Test?" in result
