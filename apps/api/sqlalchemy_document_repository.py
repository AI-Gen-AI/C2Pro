"""
SQLAlchemy implementation of the Document Repository.

Suite IDs: [TEST-DB-DOC-01], [TEST-DB-DOC-02]
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.documents.adapters.persistence.sqlalchemy_orm import DocumentORM
from src.documents.domain.models import Document


class SqlAlchemyDocumentRepository:
    """
    Repository for Document entities using SQLAlchemy.
    It enforces tenant isolation on all queries.
    """

    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id

    async def add(self, document: Document) -> None:
        """
        Adds a new Document to the database.
        """
        orm_document = DocumentORM(**document.model_dump())
        self.session.add(orm_document)

    async def get_by_id(self, document_id: UUID) -> Document | None:
        """
        Retrieves a Document by its ID, ensuring it belongs to the current tenant.
        """
        stmt = select(DocumentORM).where(
            DocumentORM.id == document_id,
            DocumentORM.tenant_id == self.tenant_id,  # Tenant isolation
        )
        result = await self.session.execute(stmt)
        orm_document = result.scalar_one_or_none()

        if orm_document:
            return self._to_domain(orm_document)
        return None

    def _to_domain(self, orm_document: DocumentORM) -> Document:
        """Converts an ORM object to a domain model."""
        return Document.model_validate(orm_document, from_attributes=True)