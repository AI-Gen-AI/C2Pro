"""
Test Suite: Document Repository Additional Tests
Component: Documents Module - Document Repository Adapter
Priority: P0

Additional tests to improve document repository coverage.
"""

import pytest
from uuid import uuid4
from unittest.mock import MagicMock, AsyncMock, patch


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

    @pytest.mark.asyncio
    async def test_get_current_tenant_id_success(self):
        """Test getting current tenant ID successfully."""
        from src.documents.adapters.persistence.sqlalchemy_document_repository import (
            SqlAlchemyDocumentRepository,
        )

        mock_session = MagicMock()
        expected_tenant_id = uuid4()
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = str(expected_tenant_id)
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = SqlAlchemyDocumentRepository(session=mock_session)
        tenant_id = await repo._get_current_tenant_id()

        assert tenant_id == expected_tenant_id

    @pytest.mark.asyncio
    async def test_get_current_tenant_id_not_set(self):
        """Test getting current tenant ID when not set."""
        from src.documents.adapters.persistence.sqlalchemy_document_repository import (
            SqlAlchemyDocumentRepository,
        )

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = SqlAlchemyDocumentRepository(session=mock_session)
        tenant_id = await repo._get_current_tenant_id()

        assert tenant_id is None

    @pytest.mark.asyncio
    async def test_get_current_tenant_id_invalid(self):
        """Test getting current tenant ID with invalid value."""
        from src.documents.adapters.persistence.sqlalchemy_document_repository import (
            SqlAlchemyDocumentRepository,
        )

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = "not-a-uuid"
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = SqlAlchemyDocumentRepository(session=mock_session)
        tenant_id = await repo._get_current_tenant_id()

        assert tenant_id is None


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
