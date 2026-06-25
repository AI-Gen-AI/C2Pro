# ruff: noqa: S101
"""
Test Suite: Document Ports/Interfaces Tests
Component: Documents Module - Port Interfaces
Priority: P2

Tests for all document port interfaces.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.documents.domain.models import Document, DocumentStatus, DocumentType


class TestIEntityExtractionServicePort:
    """Tests for IEntityExtractionService interface."""

    @pytest.mark.asyncio
    async def test_extract_entities_from_document(self):
        """Test extract_entities_from_document method."""
        from src.documents.ports.entity_extraction_service import IEntityExtractionService

        mock_service = MagicMock(spec=IEntityExtractionService)
        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="test.pdf",
            upload_status=DocumentStatus.UPLOADED,
        )

        mock_service.extract_entities_from_document = AsyncMock(return_value={"stakeholders": 2})
        result = await mock_service.extract_entities_from_document(doc, {}, uuid4())

        assert result == {"stakeholders": 2}


class TestIFileParserServicePort:
    """Tests for IFileParserService interface."""

    @pytest.mark.asyncio
    async def test_parse_document_file(self, tmp_path):
        """Test parse_document_file method."""
        from src.documents.ports.file_parser_service import IFileParserService

        mock_service = MagicMock(spec=IFileParserService)

        mock_service.parse_document_file = AsyncMock(return_value={"pages": 1})
        test_file = tmp_path / "file.pdf"
        result = await mock_service.parse_document_file(
            Document(
                id=uuid4(),
                project_id=uuid4(),
                tenant_id=uuid4(),
                document_type=DocumentType.CONTRACT,
                filename="test.pdf",
                upload_status=DocumentStatus.UPLOADED,
            ),
            str(test_file),
        )

        assert "pages" in result


class TestIRagServicePort:
    """Tests for IRagService interface."""

    @pytest.mark.asyncio
    async def test_ingest_document(self):
        """Test ingest_document method."""
        from src.documents.ports.rag_service import IRagService

        mock_service = MagicMock(spec=IRagService)

        mock_service.ingest_document = AsyncMock(return_value=10)
        result = await mock_service.ingest_document(
            document_id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            text_content="Test content"
        )

        assert result == 10

    @pytest.mark.asyncio
    async def test_answer_question(self):
        """Test answer_question method."""
        from src.documents.application.dtos import RagAnswer
        from src.documents.ports.rag_service import IRagService

        mock_service = MagicMock(spec=IRagService)

        mock_service.answer_question = AsyncMock(
            return_value=RagAnswer(answer="Test answer", sources=[])
        )
        result = await mock_service.answer_question(
            question="What is this?",
            project_id=uuid4()
        )

        assert result.answer == "Test answer"


class TestIRagIngestionServicePort:
    """Tests for IRagIngestionService interface."""

    @pytest.mark.asyncio
    async def test_ingest_document_chunks(self):
        """Test ingest_document_chunks method."""
        from src.documents.ports.rag_ingestion_service import IRagIngestionService

        mock_service = MagicMock(spec=IRagIngestionService)

        mock_service.ingest_document_chunks = AsyncMock(return_value=5)
        result = await mock_service.ingest_document_chunks(
            document_id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            text_content="Test content"
        )

        assert result == 5


class TestIStorageServicePort:
    """Tests for IStorageService interface."""

    @pytest.mark.asyncio
    async def test_upload_file(self):
        """Test upload_file method."""
        from io import BytesIO

        from src.documents.ports.storage_service import IStorageService

        mock_service = MagicMock(spec=IStorageService)

        mock_service.upload_file = AsyncMock(return_value="/path/to/file.pdf")
        result = await mock_service.upload_file(
            file_content=BytesIO(b"test"),
            file_id=uuid4(),
            file_extension=".pdf"
        )

        assert result == "/path/to/file.pdf"

    @pytest.mark.asyncio
    async def test_delete_file(self):
        """Test delete_file method."""
        from src.documents.ports.storage_service import IStorageService

        mock_service = MagicMock(spec=IStorageService)

        mock_service.delete_file = AsyncMock()
        await mock_service.delete_file("/path/to/file.pdf")

        mock_service.delete_file.assert_called_once_with("/path/to/file.pdf")

    @pytest.mark.asyncio
    async def test_get_file_path(self):
        """Test get_file_path method."""
        from src.documents.ports.storage_service import IStorageService

        mock_service = MagicMock(spec=IStorageService)

        mock_service.get_file_path = AsyncMock(return_value="/path/to/file.pdf")
        result = await mock_service.get_file_path("file-id", ".pdf")

        assert result == "/path/to/file.pdf"


class TestIStorageServiceMethods:
    """Tests for IStorageService method signatures."""

    def test_storage_service_has_required_methods(self):
        """Test IStorageService has all required methods."""
        from src.documents.ports.storage_service import IStorageService

        assert hasattr(IStorageService, "upload_file")
        assert hasattr(IStorageService, "delete_file")
        assert hasattr(IStorageService, "get_file_path")

    def test_storage_service_upload_file_signature(self):
        """Test upload_file method signature."""
        import inspect

        from src.documents.ports.storage_service import IStorageService

        sig = inspect.signature(IStorageService.upload_file)
        params = list(sig.parameters.keys())

        assert "file_content" in params
        assert "file_id" in params
        assert "file_extension" in params

    def test_storage_service_delete_file_signature(self):
        """Test delete_file method signature."""
        import inspect

        from src.documents.ports.storage_service import IStorageService

        sig = inspect.signature(IStorageService.delete_file)
        params = list(sig.parameters.keys())

        assert "file_name_in_storage" in params

    def test_storage_service_get_file_path_signature(self):
        """Test get_file_path method signature."""
        import inspect

        from src.documents.ports.storage_service import IStorageService

        sig = inspect.signature(IStorageService.get_file_path)
        params = list(sig.parameters.keys())

        assert "file_name_in_storage" in params

    def test_storage_service_download_file_signature(self):
        """Test download_file method signature."""
        import inspect

        from src.documents.ports.storage_service import IStorageService

        sig = inspect.signature(IStorageService.download_file)
        params = list(sig.parameters.keys())

        assert "file_name_in_storage" in params


class TestIClauseExtractionServicePort:
    """Tests for IClauseExtractionService interface."""

    @pytest.mark.asyncio
    async def test_extract_from_text(self):
        """Test extract_from_text method."""
        from src.documents.ports.clause_extraction_service import IClauseExtractionService

        mock_service = MagicMock(spec=IClauseExtractionService)

        mock_service.extract_from_text = AsyncMock(return_value=[])
        result = await mock_service.extract_from_text(
            text="Contract text",
            document_id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4()
        )

        assert result == []

    def test_clause_extraction_service_signature(self):
        """Test extract_from_text method signature."""
        import inspect

        from src.documents.ports.clause_extraction_service import IClauseExtractionService

        sig = inspect.signature(IClauseExtractionService.extract_from_text)
        params = list(sig.parameters.keys())

        assert "text" in params
        assert "document_id" in params
        assert "project_id" in params
        assert "tenant_id" in params
