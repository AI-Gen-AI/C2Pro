"""
Tests for the SqlAlchemyDocumentRepository.

Suite IDs: [TEST-DB-DOC-01], [TEST-DB-DOC-02]
"""
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.documents.domain.models import Document, DocumentStatus, DocumentType


@pytest.mark.asyncio
@pytest.mark.integration
class TestDocumentRepository:
    """
    Integration tests for the Document Repository.
    """

    async def test_add_and_get_document_successfully(
        self, db_session: AsyncSession, setup_project_with_tenant
    ):
        """
        [TEST-DB-DOC-01]: Verifies that a document can be added and retrieved.

        Given: A valid project and tenant exist.
        When: A new Document entity is created and added via the repository.
        Then: The repository should be able to retrieve the same document by its ID.
        And: The retrieved document's attributes should match the original ones.
        """
        # Arrange
        project, tenant_id = setup_project_with_tenant
        repo = SqlAlchemyDocumentRepository(session=db_session, tenant_id=tenant_id)

        new_document = Document(
            id=uuid.uuid4(),
            project_id=project.id,
            tenant_id=tenant_id,
            filename="contract.pdf",
            storage_path=f"tenant-placeholder/{project.id}/{uuid.uuid4()}.pdf",
            document_type=DocumentType.CONTRACT,
            status=DocumentStatus.UPLOADED,
            file_size_bytes=1024,
        )

        # Act
        await repo.add(new_document)
        await db_session.commit()

        retrieved_document = await repo.get_by_id(new_document.id)

        # Assert
        assert retrieved_document is not None
        assert retrieved_document.id == new_document.id
        assert retrieved_document.project_id == project.id
        assert retrieved_document.tenant_id == tenant_id
        assert retrieved_document.filename == "contract.pdf"
        assert retrieved_document.status == DocumentStatus.UPLOADED

    async def test_get_by_id_fails_for_different_tenant(
        self, db_session: AsyncSession, setup_two_tenants_with_project
    ):
        """
        [TEST-DB-DOC-02]: Verifies tenant isolation.

        Given: Two tenants exist, and a document belongs to tenant_A.
        When: A repository configured for tenant_B attempts to fetch the document.
        Then: The repository must return None, as if the document does not exist.
        """
        # Arrange
        tenant_a_id, tenant_b_id, project_a = setup_two_tenants_with_project

        # Create a document for Tenant A
        repo_a = SqlAlchemyDocumentRepository(session=db_session, tenant_id=tenant_a_id)
        document_a = Document(
            id=uuid.uuid4(),
            project_id=project_a.id,
            tenant_id=tenant_a_id,
            filename="secret_contract.pdf",
            storage_path="path/to/secret.pdf",
            document_type=DocumentType.CONTRACT,
            status=DocumentStatus.UPLOADED,
            file_size_bytes=2048,
        )
        await repo_a.add(document_a)
        await db_session.commit()

        # Act
        # Repository for Tenant B tries to access Tenant A's document
        repo_b = SqlAlchemyDocumentRepository(session=db_session, tenant_id=tenant_b_id)
        retrieved_document = await repo_b.get_by_id(document_a.id)

        # Assert
        assert (
            retrieved_document is None
        ), "Security Breach: Repository returned a document from another tenant!"