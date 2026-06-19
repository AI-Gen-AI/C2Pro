"""TS-E2E-FLW-JRN-001

Test Suite: Document Repository Additional Tests
Component: Documents Module - Document Repository Adapter
Priority: P0

Additional tests to improve document repository coverage.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


class TestSqlAlchemyDocumentRepository:
    """Tests for SqlAlchemyDocumentRepository."""

    def test_repository_initialization(self):
        """Test repository initialization."""
        from src.documents.adapters.persistence.sqlalchemy_document_repository import (
            SqlAlchemyDocumentRepository,
        )

        mock_session = MagicMock()
        repo = SqlAlchemyDocumentRepository(session=mock_session)

        assert repo.session is mock_session

    def test_has_required_interface_methods(self):
        """Test repository has required interface methods."""
        from src.documents.adapters.persistence.sqlalchemy_document_repository import (
            SqlAlchemyDocumentRepository,
        )

        mock_session = MagicMock()
        repo = SqlAlchemyDocumentRepository(session=mock_session)

        # Check IDocumentRepository interface methods
        assert hasattr(repo, "add")
        assert hasattr(repo, "get_by_id")
        assert hasattr(repo, "get_document_with_clauses")
        assert hasattr(repo, "update_status")
        assert hasattr(repo, "update_storage_path")
        assert hasattr(repo, "delete")
        assert hasattr(repo, "list_for_project")

    def test_to_orm_document_normalizes_aware_timestamps_to_naive_utc(self):
        """Aware UTC timestamps should be normalized for naive TIMESTAMP columns."""
        from src.documents.adapters.persistence.sqlalchemy_document_repository import (
            SqlAlchemyDocumentRepository,
        )
        from src.documents.domain.models import Document, DocumentStatus, DocumentType

        aware_now = datetime.now(UTC)
        document = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="aware.pdf",
            upload_status=DocumentStatus.QUEUED,
            created_at=aware_now,
            updated_at=aware_now,
        )

        repo = SqlAlchemyDocumentRepository(session=MagicMock())
        orm_document = repo._to_orm_document(document)

        assert orm_document.created_at.tzinfo is None
        assert orm_document.updated_at.tzinfo is None

    @pytest.mark.asyncio
    async def test_update_status_persists_parsed_at(self):
        """TASK-BCK-063: Verify that update_status correctly sets parsed_at on ORM model."""
        from src.documents.adapters.persistence.models import DocumentORM
        from src.documents.adapters.persistence.sqlalchemy_document_repository import (
            SqlAlchemyDocumentRepository,
        )
        from src.documents.domain.models import DocumentStatus

        tenant_id = uuid4()
        document_id = uuid4()
        parsed_at = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)

        # Mock session
        mock_session = MagicMock()
        mock_session.execute = AsyncMock()

        # Setup mock result for select
        orm_doc = DocumentORM(
            id=document_id,
            tenant_id=tenant_id,
            upload_status=DocumentStatus.PARSING,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = orm_doc
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyDocumentRepository(session=mock_session)

        await repo.update_status(
            tenant_id,
            document_id,
            DocumentStatus.PARSED,
            parsed_at=parsed_at
        )

        assert orm_doc.upload_status == DocumentStatus.PARSED
        assert orm_doc.parsed_at is not None
        assert orm_doc.parsed_at.tzinfo is None  # Should be normalized to naive UTC
        assert orm_doc.parsed_at == datetime(2026, 5, 17, 12, 0, 0)



class TestDocumentORM:
    """Tests for DocumentORM model."""

    def test_orm_has_table_name(self):
        """Test DocumentORM has table name."""
        from src.documents.adapters.persistence.models import DocumentORM

        assert hasattr(DocumentORM, "__tablename__")
        assert DocumentORM.__tablename__ == "documents"

    def test_orm_has_id_column(self):
        """Test DocumentORM has id column."""
        from src.documents.adapters.persistence.models import DocumentORM

        assert hasattr(DocumentORM, "id")

    def test_orm_has_project_id_column(self):
        """Test DocumentORM has project_id column."""
        from src.documents.adapters.persistence.models import DocumentORM

        assert hasattr(DocumentORM, "project_id")


class TestClauseORM:
    """Tests for ClauseORM model."""

    def test_orm_has_table_name(self):
        """Test ClauseORM has table name."""
        from src.documents.adapters.persistence.models import ClauseORM

        assert hasattr(ClauseORM, "__tablename__")
        assert ClauseORM.__tablename__ == "clauses"

    def test_orm_has_id_column(self):
        """Test ClauseORM has id column."""
        from src.documents.adapters.persistence.models import ClauseORM

        assert hasattr(ClauseORM, "id")

    def test_orm_has_document_id_column(self):
        """Test ClauseORM has document_id column."""
        from src.documents.adapters.persistence.models import ClauseORM

        assert hasattr(ClauseORM, "document_id")


class TestDocumentDomainModel:
    """Tests for Document domain model."""

    def test_document_model_creation(self):
        """Test Document model can be created."""
        from src.documents.domain.models import Document, DocumentStatus

        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type="contract",
            filename="test.pdf",
            upload_status=DocumentStatus.UPLOADED,
        )

        assert doc.id is not None
        assert doc.filename == "test.pdf"

    def test_document_status_values(self):
        """Test DocumentStatus enum values."""
        from src.documents.domain.models import DocumentStatus

        assert DocumentStatus.UPLOADED.value == "uploaded"
        assert DocumentStatus.PARSING.value == "processing"
        assert DocumentStatus.PARSED.value == "parsed"
        assert DocumentStatus.ERROR.value == "error"

    def test_document_type_values(self):
        """Test DocumentType enum values."""
        from src.documents.domain.models import DocumentType

        assert DocumentType.CONTRACT.value == "contract"
        assert DocumentType.SCHEDULE.value == "schedule"
        assert DocumentType.BUDGET.value == "budget"
