from typing import List, Optional, Tuple
from uuid import UUID
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from apps.api.src.core.database import get_session_with_tenant
from apps.api.src.documents.domain.models import Document, DocumentStatus, DocumentType
from apps.api.src.documents.adapters.persistence.models import DocumentORM
from apps.api.src.documents.ports.document_repository import DocumentRepository
from apps.api.src.documents.ports.project_repository import ProjectRepositoryPort
from apps.api.src.documents.application.dtos import DocumentListItem

logger = structlog.get_logger()

class DocumentRepositoryImpl(DocumentRepository):
    def __init__(self, db_session: AsyncSession, project_repository: ProjectRepositoryPort):
        self.db_session = db_session
        self.project_repository = project_repository

    async def _to_domain_model(self, orm_model: DocumentORM) -> Document:
        return Document(
            id=orm_model.id,
            project_id=orm_model.project_id,
            document_type=orm_model.document_type,
            filename=orm_model.filename,
            upload_status=orm_model.upload_status,
            parsed_at=orm_model.parsed_at,
            parsing_error=orm_model.parsing_error,
            # Clauses are not loaded by default for simplicity,
            # but could be added if needed for specific use cases
            clauses=[]
        )

    async def _to_orm_model(self, domain_model: Document) -> DocumentORM:
        return DocumentORM(
            id=domain_model.id,
            project_id=domain_model.project_id,
            document_type=domain_model.document_type,
            filename=domain_model.filename,
            upload_status=domain_model.upload_status,
            parsed_at=domain_model.parsed_at,
            parsing_error=domain_model.parsing_error,
            # storage_url and other fields would be set directly or from metadata
            # This conversion might need more context for full ORM model creation
        )

    async def get_by_id(self, document_id: UUID, tenant_id: UUID) -> Optional[Document]:
        async with get_session_with_tenant(tenant_id) as session:
            result = await session.execute(
                select(DocumentORM).where(DocumentORM.id == document_id)
            )
            orm_document = result.scalar_one_or_none()
            if orm_document:
                return await self._to_domain_model(orm_document)
            return None

    async def add(self, document: Document, db_session: AsyncSession) -> Document:
        orm_document = await self._to_orm_model(document)
        db_session.add(orm_document)
        await db_session.flush() # To get ID if not set
        return await self._to_domain_model(orm_document)

    async def update(self, document: Document, db_session: AsyncSession) -> Document:
        # For update, we fetch the existing ORM object, then update its fields
        orm_document = await db_session.get(DocumentORM, document.id)
        if not orm_document:
            raise ValueError(f"Document with ID {document.id} not found for update.")

        orm_document.document_type = document.document_type
        orm_document.filename = document.filename
        orm_document.upload_status = document.upload_status
        orm_document.parsed_at = document.parsed_at
        orm_document.parsing_error = document.parsing_error
        # Update other fields as necessary, e.g., storage_url
        await db_session.flush()
        return await self._to_domain_model(orm_document)

    async def delete(self, document: Document, db_session: AsyncSession):
        orm_document = await db_session.get(DocumentORM, document.id)
        if orm_document:
            await db_session.delete(orm_document)
            await db_session.flush()

    async def list_by_project_id(
        self, project_id: UUID, tenant_id: UUID, skip: int = 0, limit: int = 20
    ) -> Tuple[List[DocumentListItem], int]:
        async with get_session_with_tenant(tenant_id) as session:
            # 1. Build the base query for documents
            stmt = (
                select(
                    DocumentORM.id,
                    DocumentORM.filename,
                    DocumentORM.upload_status,
                    DocumentORM.parsing_error,
                    DocumentORM.created_at,
                    DocumentORM.file_size_bytes,
                )
                .where(DocumentORM.project_id == project_id)
                .order_by(DocumentORM.created_at.desc())
            )

            # 2. Get total count for pagination metadata
            count_stmt = select(func.count()).where(DocumentORM.project_id == project_id)
            total_count_result = await session.execute(count_stmt)
            total_count = total_count_result.scalar_one()

            # 3. Apply pagination
            stmt = stmt.offset(skip).limit(limit)

            # 4. Execute query and fetch results
            documents_result = await session.execute(stmt)
            document_rows = documents_result.all()

            # 5. Map results to DocumentListItem
            items: List[DocumentListItem] = [
                DocumentListItem(
                    id=row.id,
                    filename=row.filename,
                    status=self._normalize_document_status_for_polling(row.upload_status),
                    error_message=row.parsing_error if row.upload_status == DocumentStatus.ERROR else None,
                    uploaded_at=row.created_at,
                    file_size_bytes=row.file_size_bytes or 0,
                )
                for row in document_rows
            ]
            return items, total_count
    
    async def get_tenant_id_from_project(self, project_id: UUID) -> Optional[UUID]:
        return await self.project_repository.get_tenant_id_by_project_id(project_id)

    def _normalize_document_status_for_polling(self, document_status: DocumentStatus) -> DocumentStatus:
        """
        Helper to map internal DocumentStatus to external DocumentPollingStatus.
        Since DocumentStatus already covers the needed states for polling, we can use it directly.
        """
        if document_status == DocumentStatus.UPLOADED:
            return DocumentStatus.QUEUED # This seems to be a conceptual mapping from old service
        return document_status
