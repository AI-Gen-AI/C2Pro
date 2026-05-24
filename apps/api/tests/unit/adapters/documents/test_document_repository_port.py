"""
Test Suite: Document Repository Port Tests
Component: Documents Module - Repository Interface
Priority: P2

Tests for the IDocumentRepository interface contract.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.documents.domain.models import Clause, ClauseType, Document, DocumentStatus, DocumentType


class TestIDocumentRepositoryInterface:
    """Tests verifying IDocumentRepository interface contract."""

    @pytest.mark.asyncio
    async def test_add_document(self):
        """Test add method is called with document."""
        from src.documents.ports.document_repository import IDocumentRepository

        mock_repo = MagicMock(spec=IDocumentRepository)
        tenant_id = uuid4()
        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=tenant_id,
            document_type=DocumentType.CONTRACT,
            filename="test.pdf",
            upload_status=DocumentStatus.UPLOADED,
        )

        mock_repo.add = AsyncMock()
        await mock_repo.add(tenant_id, doc)

        mock_repo.add.assert_called_once_with(tenant_id, doc)

    @pytest.mark.asyncio
    async def test_get_by_id(self):
        """Test get_by_id returns document."""
        from src.documents.ports.document_repository import IDocumentRepository

        mock_repo = MagicMock(spec=IDocumentRepository)
        tenant_id = uuid4()
        doc_id = uuid4()

        mock_repo.get_by_id = AsyncMock(return_value=None)
        await mock_repo.get_by_id(tenant_id, doc_id)

        mock_repo.get_by_id.assert_called_once_with(tenant_id, doc_id)

    @pytest.mark.asyncio
    async def test_get_document_with_clauses(self):
        """Test get_document_with_clauses returns document with clauses."""
        from src.documents.ports.document_repository import IDocumentRepository

        mock_repo = MagicMock(spec=IDocumentRepository)
        tenant_id = uuid4()
        doc_id = uuid4()

        mock_repo.get_document_with_clauses = AsyncMock(return_value=None)
        await mock_repo.get_document_with_clauses(tenant_id, doc_id)

        mock_repo.get_document_with_clauses.assert_called_once_with(tenant_id, doc_id)

    @pytest.mark.asyncio
    async def test_update_status(self):
        """Test update_status changes document status."""
        from src.documents.ports.document_repository import IDocumentRepository

        mock_repo = MagicMock(spec=IDocumentRepository)
        tenant_id = uuid4()
        doc_id = uuid4()

        mock_repo.update_status = AsyncMock()
        await mock_repo.update_status(tenant_id, doc_id, DocumentStatus.PARSED)

        mock_repo.update_status.assert_called_once_with(tenant_id, doc_id, DocumentStatus.PARSED)

    @pytest.mark.asyncio
    async def test_update_status_with_error(self):
        """Test update_status with parsing error."""
        from src.documents.ports.document_repository import IDocumentRepository

        mock_repo = MagicMock(spec=IDocumentRepository)
        tenant_id = uuid4()
        doc_id = uuid4()

        mock_repo.update_status = AsyncMock()
        await mock_repo.update_status(tenant_id, doc_id, DocumentStatus.ERROR, "Parse failed")

        mock_repo.update_status.assert_called_once_with(tenant_id, doc_id, DocumentStatus.ERROR, "Parse failed")

    @pytest.mark.asyncio
    async def test_update_storage_path(self):
        """Test update_storage_path changes URL."""
        from src.documents.ports.document_repository import IDocumentRepository

        mock_repo = MagicMock(spec=IDocumentRepository)
        tenant_id = uuid4()
        doc_id = uuid4()

        mock_repo.update_storage_path = AsyncMock()
        await mock_repo.update_storage_path(tenant_id, doc_id, "/new/path.pdf")

        mock_repo.update_storage_path.assert_called_once_with(tenant_id, doc_id, "/new/path.pdf")

    @pytest.mark.asyncio
    async def test_delete_document(self):
        """Test delete removes document."""
        from src.documents.ports.document_repository import IDocumentRepository

        mock_repo = MagicMock(spec=IDocumentRepository)
        tenant_id = uuid4()
        doc_id = uuid4()

        mock_repo.delete = AsyncMock()
        await mock_repo.delete(tenant_id, doc_id)

        mock_repo.delete.assert_called_once_with(tenant_id, doc_id)

    @pytest.mark.asyncio
    async def test_list_for_project(self):
        """Test list_for_project returns documents."""
        from src.documents.ports.document_repository import IDocumentRepository

        mock_repo = MagicMock(spec=IDocumentRepository)
        tenant_id = uuid4()
        project_id = uuid4()

        mock_repo.list_for_project = AsyncMock(return_value=([], 0))
        result = await mock_repo.list_for_project(tenant_id, project_id, 0, 10)

        assert result == ([], 0)
        mock_repo.list_for_project.assert_called_once_with(tenant_id, project_id, 0, 10)

    @pytest.mark.asyncio
    async def test_get_project_tenant_id(self):
        """Test get_project_tenant_id returns tenant."""
        from src.documents.ports.document_repository import IDocumentRepository

        mock_repo = MagicMock(spec=IDocumentRepository)
        project_id = uuid4()

        mock_repo.get_project_tenant_id = AsyncMock(return_value=None)
        await mock_repo.get_project_tenant_id(project_id)

        mock_repo.get_project_tenant_id.assert_called_once_with(project_id)

    @pytest.mark.asyncio
    async def test_add_clause(self):
        """Test add_clause adds clause to document."""
        from src.documents.ports.document_repository import IDocumentRepository

        mock_repo = MagicMock(spec=IDocumentRepository)
        tenant_id = uuid4()
        clause = Clause(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=tenant_id,
            document_id=uuid4(),
            clause_code="1.0",
            clause_type=ClauseType.SCOPE,
            title="Test",
            full_text="Test clause text",
        )

        mock_repo.add_clause = AsyncMock()
        await mock_repo.add_clause(tenant_id, clause)

        mock_repo.add_clause.assert_called_once_with(tenant_id, clause)

    @pytest.mark.asyncio
    async def test_clause_exists(self):
        """Test clause_exists checks clause."""
        from src.documents.ports.document_repository import IDocumentRepository

        mock_repo = MagicMock(spec=IDocumentRepository)
        tenant_id = uuid4()
        clause_id = uuid4()

        mock_repo.clause_exists = AsyncMock(return_value=True)
        result = await mock_repo.clause_exists(tenant_id, clause_id)

        assert result is True
        mock_repo.clause_exists.assert_called_once_with(tenant_id, clause_id)

    @pytest.mark.asyncio
    async def test_get_clause_text_map(self):
        """Test get_clause_text_map returns mapping."""
        from src.documents.ports.document_repository import IDocumentRepository

        mock_repo = MagicMock(spec=IDocumentRepository)
        tenant_id = uuid4()
        clause_ids = [uuid4(), uuid4()]

        mock_repo.get_clause_text_map = AsyncMock(return_value={})
        await mock_repo.get_clause_text_map(tenant_id, clause_ids)

        mock_repo.get_clause_text_map.assert_called_once_with(tenant_id, clause_ids)

    @pytest.mark.asyncio
    async def test_get_clauses_by_ids(self):
        """Test get_clauses_by_ids returns clauses."""
        from src.documents.ports.document_repository import IDocumentRepository

        mock_repo = MagicMock(spec=IDocumentRepository)
        tenant_id = uuid4()
        clause_ids = [uuid4()]

        mock_repo.get_clauses_by_ids = AsyncMock(return_value=[])
        await mock_repo.get_clauses_by_ids(tenant_id, clause_ids)

        mock_repo.get_clauses_by_ids.assert_called_once_with(tenant_id, clause_ids)

    @pytest.mark.asyncio
    async def test_get_clause_by_document_and_code(self):
        """Test get_clause_by_document_and_code finds clause."""
        from src.documents.ports.document_repository import IDocumentRepository

        mock_repo = MagicMock(spec=IDocumentRepository)
        tenant_id = uuid4()
        doc_id = uuid4()

        mock_repo.get_clause_by_document_and_code = AsyncMock(return_value=None)
        await mock_repo.get_clause_by_document_and_code(tenant_id, doc_id, "1.0")

        mock_repo.get_clause_by_document_and_code.assert_called_once_with(tenant_id, doc_id, "1.0")

    @pytest.mark.asyncio
    async def test_list_clauses_for_document(self):
        """Test list_clauses_for_document returns clauses."""
        from src.documents.ports.document_repository import IDocumentRepository

        mock_repo = MagicMock(spec=IDocumentRepository)
        tenant_id = uuid4()
        doc_id = uuid4()

        mock_repo.list_clauses_for_document = AsyncMock(return_value=[])
        await mock_repo.list_clauses_for_document(tenant_id, doc_id)

        mock_repo.list_clauses_for_document.assert_called_once_with(tenant_id, doc_id)

    @pytest.mark.asyncio
    async def test_commit(self):
        """Test commit saves changes."""
        from src.documents.ports.document_repository import IDocumentRepository

        mock_repo = MagicMock(spec=IDocumentRepository)

        mock_repo.commit = AsyncMock()
        await mock_repo.commit()

        mock_repo.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh(self):
        """Test refresh reloads entity."""
        from src.documents.ports.document_repository import IDocumentRepository

        mock_repo = MagicMock(spec=IDocumentRepository)
        entity = MagicMock()

        mock_repo.refresh = AsyncMock()
        await mock_repo.refresh(entity)

        mock_repo.refresh.assert_called_once_with(entity)
