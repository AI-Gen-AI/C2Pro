"""
Test Suite: Additional Coverage Tests
Component: Documents Module
Priority: P2

Additional tests to push coverage to 70%.
"""

from datetime import datetime
from uuid import uuid4

import pytest


class TestDocumentModelsEdgeCases:
    """Test edge cases in document models."""

    def test_document_with_minimal_fields(self):
        """Test creating document with only required fields."""
        from src.documents.domain.models import Document, DocumentStatus, DocumentType

        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.OTHER,
            filename="test.txt",
            upload_status=DocumentStatus.UPLOADED,
        )

        assert doc.id is not None
        assert doc.filename == "test.txt"
        assert doc.is_parsed() is False

    def test_document_with_all_optional_fields(self):
        """Test creating document with all optional fields."""
        from src.documents.domain.models import Document, DocumentStatus, DocumentType

        doc_id = uuid4()
        created_at = datetime.now()

        doc = Document(
            id=doc_id,
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="test.pdf",
            upload_status=DocumentStatus.PARSED,
            file_format=".pdf",
            storage_url="https://storage.example.com/test.pdf",
            storage_encrypted=True,
            file_size_bytes=1024,
            parsed_at=datetime.now(),
            parsing_error=None,
            created_by=uuid4(),
            created_at=created_at,
            updated_at=datetime.now(),
            document_metadata={"key": "value"},
            clauses=[],
        )

        assert doc.is_parsed() is True
        assert doc.has_error() is False
        assert doc.file_size_bytes == 1024

    def test_document_error_status(self):
        """Test document with error status."""
        from src.documents.domain.models import Document, DocumentStatus, DocumentType

        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.BUDGET,
            filename="budget.bc3",
            upload_status=DocumentStatus.ERROR,
            parsing_error="Failed to parse",
        )

        assert doc.has_error() is True
        assert doc.is_parsed() is False

    def test_document_clause_operations(self):
        """Test adding and counting clauses."""
        from src.documents.domain.models import (
            Clause,
            ClauseType,
            Document,
            DocumentStatus,
            DocumentType,
        )

        doc_id = uuid4()
        tenant_id = uuid4()
        doc = Document(
            id=doc_id,
            project_id=uuid4(),
            tenant_id=tenant_id,
            document_type=DocumentType.CONTRACT,
            filename="test.pdf",
            upload_status=DocumentStatus.PARSED,
        )

        clause1 = Clause(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=tenant_id,
            document_id=doc_id,
            clause_code="1.0",
            clause_type=ClauseType.SCOPE,
            title="Scope",
            full_text="Scope text",
        )

        clause2 = Clause(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=tenant_id,
            document_id=doc_id,
            clause_code="2.0",
            clause_type=ClauseType.PAYMENT,
            title="Payment",
            full_text="Payment text",
        )

        doc.add_clause(clause1)
        doc.add_clause(clause2)

        assert doc.clause_count() == 2


class TestDocumentDTOCreation:
    """Test DTO creation and behavior."""

    def test_create_document_dto_minimal(self):
        """Test CreateDocumentDTO with minimal fields."""
        from src.documents.application.dtos import CreateDocumentDTO
        from src.documents.domain.models import DocumentType

        dto = CreateDocumentDTO(
            project_id=uuid4(),
            tenant_id=uuid4(),
            filename="test.pdf",
            document_type=DocumentType.CONTRACT,
        )

        assert dto.filename == "test.pdf"
        assert dto.file_format is None

    def test_create_document_dto_full(self):
        """Test CreateDocumentDTO with all fields."""
        from src.documents.application.dtos import CreateDocumentDTO
        from src.documents.domain.models import DocumentType

        dto = CreateDocumentDTO(
            project_id=uuid4(),
            tenant_id=uuid4(),
            filename="test.pdf",
            document_type=DocumentType.CONTRACT,
            file_format=".pdf",
            storage_url="https://storage.example.com/test.pdf",
            file_size_bytes=2048,
            created_by=uuid4(),
            document_metadata={"source": "upload"},
        )

        assert dto.file_size_bytes == 2048
        assert dto.storage_url == "https://storage.example.com/test.pdf"

    def test_retrieved_chunk_dto(self):
        """Test RetrievedChunk DTO."""
        from src.documents.application.dtos import RetrievedChunk

        chunk = RetrievedChunk(
            content="Test content",
            metadata={"page": 1},
            similarity=0.95,
        )

        assert chunk.content == "Test content"
        assert chunk.similarity == 0.95

    def test_rag_answer_dto_empty(self):
        """Test RagAnswer DTO with empty sources."""
        from src.documents.application.dtos import RagAnswer

        answer = RagAnswer(answer="Test answer", sources=[])

        assert answer.answer == "Test answer"
        assert len(answer.sources) == 0


class TestDocumentStatusEnums:
    """Test DocumentStatus enum values."""

    def test_document_status_values(self):
        """Test DocumentStatus enum has expected values."""
        from src.documents.domain.models import DocumentStatus

        assert DocumentStatus.UPLOADED.value == "uploaded"
        assert DocumentStatus.QUEUED.value == "queued"
        assert DocumentStatus.PARSING.value == "processing"
        assert DocumentStatus.PARSED.value == "parsed"
        assert DocumentStatus.ERROR.value == "error"

    def test_document_type_values(self):
        """Test DocumentType enum has expected values."""
        from src.documents.domain.models import DocumentType

        assert DocumentType.CONTRACT.value == "contract"
        assert DocumentType.SCHEDULE.value == "schedule"
        assert DocumentType.BUDGET.value == "budget"
        assert DocumentType.DRAWING.value == "drawing"
        assert DocumentType.SPECIFICATION.value == "specification"
        assert DocumentType.OTHER.value == "other"

    def test_clause_type_values(self):
        """Test ClauseType enum has expected values."""
        from src.documents.domain.models import ClauseType

        assert ClauseType.SCOPE.value == "scope"
        assert ClauseType.PAYMENT.value == "payment"
        assert ClauseType.QUALITY.value == "quality"
        assert ClauseType.PENALTY.value == "penalty"
        assert ClauseType.TERMINATION.value == "termination"


class TestDocumentPersistenceModel:
    """Test SQLAlchemy persistence models."""

    def test_document_orm_model_columns(self):
        """Test DocumentORM has expected columns."""
        from src.documents.adapters.persistence.models import DocumentORM

        columns = [c.name for c in DocumentORM.__table__.columns]

        assert "id" in columns
        assert "project_id" in columns
        assert "document_type" in columns
        assert "filename" in columns
        assert "upload_status" in columns
        assert "file_format" in columns
        assert "storage_url" in columns

    def test_clause_orm_model_columns(self):
        """Test ClauseORM has expected columns."""
        from src.documents.adapters.persistence.models import ClauseORM

        columns = [c.name for c in ClauseORM.__table__.columns]

        assert "id" in columns
        assert "document_id" in columns
        assert "clause_code" in columns
        assert "clause_type" in columns
        assert "title" in columns
        assert "full_text" in columns


class TestStorageServiceEdgeCases:
    """Test storage service edge cases."""

    @pytest.mark.asyncio
    async def test_storage_service_initialization(self):
        """Test LocalFileStorageService can be initialized."""
        import tempfile
        from pathlib import Path

        from src.documents.adapters.storage.local_file_storage_service import (
            LocalFileStorageService,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            service = LocalFileStorageService(base_dir=Path(tmpdir))

            assert service is not None

    @pytest.mark.asyncio
    async def test_storage_service_default_base_dir(self):
        """Test LocalFileStorageService with default base directory."""
        from src.documents.adapters.storage.local_file_storage_service import (
            LocalFileStorageService,
        )

        service = LocalFileStorageService()

        assert service is not None


class TestBC3ParserEdgeCases:
    """Test BC3 parser edge cases."""

    @pytest.mark.asyncio
    async def test_bc3_parser_empty_content(self):
        """Test BC3 parser handles empty content."""
        import tempfile
        from pathlib import Path

        from src.documents.adapters.parsers.bc3_file_parser import BC3FileParser

        parser = BC3FileParser()

        with tempfile.NamedTemporaryFile(suffix='.bc3', delete=False, mode='w') as tmp:
            tmp.write("")
            tmp_path = tmp.name

        try:
            result = await parser.parse(Path(tmp_path))
            assert isinstance(result, dict)
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestPDFParserEdgeCases:
    """Test PDF parser edge cases."""

    def test_pdf_parser_initialization(self):
        """Test PDF parser can be initialized."""
        from src.documents.adapters.parsers.pdf_file_parser import PDFFileParser

        parser = PDFFileParser()

        assert parser is not None
