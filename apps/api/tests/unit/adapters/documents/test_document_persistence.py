"""
Test Suite: TS-UAD-DOC-004 - Document Persistence Tests
Component: Documents Module - Persistence Adapters
Priority: P1

Tests the SqlAlchemy document and clause repositories.
"""

import pytest
from uuid import uuid4
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime


class TestSqlAlchemyDocumentRepository:
    """Tests for SqlAlchemyDocumentRepository."""

    def test_repository_init(self):
        """Test repository initialization."""
        from src.documents.adapters.persistence.sqlalchemy_document_repository import (
            SqlAlchemyDocumentRepository,
        )

        mock_session = MagicMock()
        repo = SqlAlchemyDocumentRepository(session=mock_session)

        assert repo is not None
        assert repo.session is mock_session

    def test_repository_has_core_methods(self):
        """Test repository has core methods."""
        from src.documents.adapters.persistence.sqlalchemy_document_repository import (
            SqlAlchemyDocumentRepository,
        )

        mock_session = MagicMock()
        repo = SqlAlchemyDocumentRepository(session=mock_session)

        # Check core methods exist
        assert hasattr(repo, "session")
        assert hasattr(repo, "_get_current_tenant_id")
        assert hasattr(repo, "_to_domain_document")

    @pytest.mark.asyncio
    async def test_repository_get_current_tenant_id(self):
        """Test getting current tenant ID."""
        from src.documents.adapters.persistence.sqlalchemy_document_repository import (
            SqlAlchemyDocumentRepository,
        )

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = str(uuid4())
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = SqlAlchemyDocumentRepository(session=mock_session)
        tenant_id = await repo._get_current_tenant_id()

        assert tenant_id is not None

    @pytest.mark.asyncio
    async def test_repository_get_current_tenant_id_none(self):
        """Test getting current tenant ID when none set."""
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


class TestDocumentORM:
    """Tests for DocumentORM model."""

    def test_orm_model_exists(self):
        """Test DocumentORM model can be imported."""
        from src.documents.adapters.persistence.models import DocumentORM

        assert DocumentORM is not None

    def test_orm_has_tablename(self):
        """Test DocumentORM has table name."""
        from src.documents.adapters.persistence.models import DocumentORM

        assert hasattr(DocumentORM, "__tablename__")


class TestClauseORM:
    """Tests for ClauseORM model."""

    def test_orm_model_exists(self):
        """Test ClauseORM model can be imported."""
        from src.documents.adapters.persistence.models import ClauseORM

        assert ClauseORM is not None

    def test_orm_has_tablename(self):
        """Test ClauseORM has table name."""
        from src.documents.adapters.persistence.models import ClauseORM

        assert hasattr(ClauseORM, "__tablename__")


class TestDocumentDomainModel:
    """Tests for Document domain model."""

    def test_document_model_import(self):
        """Test Document model can be imported."""
        from src.documents.domain.models import Document

        assert Document is not None

    def test_document_status_enum(self):
        """Test DocumentStatus enum exists."""
        from src.documents.domain.models import DocumentStatus

        assert DocumentStatus.UPLOADED is not None
        assert DocumentStatus.PARSING is not None
        assert DocumentStatus.PARSED is not None
        assert DocumentStatus.ERROR is not None

    def test_document_type_enum(self):
        """Test DocumentType enum exists."""
        from src.documents.domain.models import DocumentType

        assert DocumentType.CONTRACT is not None
        assert DocumentType.SCHEDULE is not None
        assert DocumentType.BUDGET is not None


class TestClauseDomainModel:
    """Tests for Clause domain model."""

    def test_clause_model_import(self):
        """Test Clause model can be imported."""
        from src.documents.domain.models import Clause

        assert Clause is not None
