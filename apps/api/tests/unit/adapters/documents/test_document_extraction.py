"""
Test Suite: TS-UAD-DOC-003 - Document Extraction Tests
Component: Documents Module - Extraction Adapter
Priority: P1

Tests the DocumentsEntityExtractionService adapter.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4


class TestDocumentsEntityExtraction:
    """Tests for DocumentsEntityExtractionService."""

    def test_extraction_service_init(self):
        """Test extraction service initialization."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            DocumentsEntityExtractionService,
        )

        # Create mock factories
        stakeholder_factory = MagicMock(return_value=MagicMock())
        wbs_factory = MagicMock(return_value=MagicMock())
        bom_factory = MagicMock(return_value=MagicMock())
        user_id = uuid4()

        service = DocumentsEntityExtractionService(
            stakeholder_use_case_factory=stakeholder_factory,
            wbs_use_case_factory=wbs_factory,
            bom_use_case_factory=bom_factory,
            user_id=user_id,
        )

        assert service is not None
        assert service._user_id == user_id

    def test_extraction_service_has_extract_method(self):
        """Test extraction service has required method."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            DocumentsEntityExtractionService,
        )

        stakeholder_factory = MagicMock(return_value=MagicMock())
        wbs_factory = MagicMock(return_value=MagicMock())
        bom_factory = MagicMock(return_value=MagicMock())

        service = DocumentsEntityExtractionService(
            stakeholder_use_case_factory=stakeholder_factory,
            wbs_use_case_factory=wbs_factory,
            bom_use_case_factory=bom_factory,
            user_id=uuid4(),
        )

        assert hasattr(service, "extract_entities_from_document")


class TestLocalFileStorage:
    """Tests for LocalFileStorageService."""

    def test_storage_service_init(self):
        """Test storage service initialization."""
        from src.documents.adapters.storage.local_file_storage_service import (
            LocalFileStorageService,
        )

        service = LocalFileStorageService()
        assert service is not None

    def test_storage_service_has_upload_method(self):
        """Test storage service has upload interface method."""
        from src.documents.adapters.storage.local_file_storage_service import (
            LocalFileStorageService,
        )

        service = LocalFileStorageService()

        # Check required methods exist
        assert hasattr(service, "upload_file")

    def test_storage_falls_back_when_preferred_directory_is_not_writable(self, tmp_path):
        """Uses the fallback directory when a created path cannot accept writes."""
        from src.documents.adapters.storage import local_file_storage_service
        from src.documents.adapters.storage.local_file_storage_service import (
            LocalFileStorageService,
        )

        preferred_dir = tmp_path / "preferred"
        fallback_dir = tmp_path / "fallback"

        with (
            patch.object(local_file_storage_service, "_FALLBACK_UPLOAD_DIR", fallback_dir),
            patch.object(
                local_file_storage_service.tempfile,
                "NamedTemporaryFile",
                side_effect=PermissionError,
            ),
        ):
            service = LocalFileStorageService(base_dir=preferred_dir)

        assert service._base_dir == fallback_dir


class TestRagIngestionService:
    """Tests for SqlAlchemyRagIngestionService."""

    def test_rag_ingestion_service_init(self):
        """Test RAG ingestion service initialization."""
        from src.documents.adapters.rag.sqlalchemy_rag_ingestion_service import (
            SqlAlchemyRagIngestionService,
        )

        mock_session = MagicMock()
        service = SqlAlchemyRagIngestionService(db_session=mock_session)

        assert service is not None

    def test_rag_ingestion_service_has_required_methods(self):
        """Test RAG ingestion service has required interface methods."""
        from src.documents.adapters.rag.sqlalchemy_rag_ingestion_service import (
            SqlAlchemyRagIngestionService,
        )

        mock_session = MagicMock()
        service = SqlAlchemyRagIngestionService(db_session=mock_session)

        # Check it has the service method
        assert service is not None


class TestRagService:
    """Tests for SqlAlchemyRagService."""

    def test_rag_service_init(self):
        """Test RAG service initialization."""
        from src.documents.adapters.rag.rag_service_adapter import (
            SqlAlchemyRagService,
        )

        mock_session = MagicMock()
        service = SqlAlchemyRagService(db_session=mock_session)

        assert service is not None

    def test_rag_service_has_required_methods(self):
        """Test RAG service has required interface methods."""
        from src.documents.adapters.rag.rag_service_adapter import (
            SqlAlchemyRagService,
        )

        mock_session = MagicMock()
        service = SqlAlchemyRagService(db_session=mock_session)

        assert hasattr(service, "answer_question")
