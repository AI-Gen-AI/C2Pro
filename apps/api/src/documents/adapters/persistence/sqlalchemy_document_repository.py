"""
SQLAlchemy implementation of the IDocumentRepository port.
Handles persistence for Document and Clause entities.
"""
from datetime import datetime
from typing import List, Tuple
from uuid import UUID

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload # For eager loading relationships

from src.documents.domain.models import Document, DocumentStatus, Clause
from src.documents.ports.document_repository import IDocumentRepository
from src.documents.adapters.persistence.models import DocumentORM, ClauseORM

class SqlAlchemyDocumentRepository(IDocumentRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- Mapper functions ---
    def _to_domain_document(self, orm_document: DocumentORM) -> Document:
        if orm_document is None:
            return None
        # Convert list of ClauseORM to list of Clause domain entities
        clauses = [self._to_domain_clause(orm_clause) for orm_clause in orm_document.clauses] if orm_document.clauses else []
        
        domain_document = Document(
            id=orm_document.id,
            project_id=orm_document.project_id,
            document_type=orm_document.document_type,
            filename=orm_document.filename,
            file_format=orm_document.file_format,
            storage_url=orm_document.storage_url,
            storage_encrypted=orm_document.storage_encrypted,
            file_size_bytes=orm_document.file_size_bytes,
            upload_status=orm_document.upload_status,
            parsed_at=orm_document.parsed_at,
            parsing_error=orm_document.parsing_error,
            retention_until=orm_document.retention_until,
            created_by=orm_document.created_by,
            created_at=orm_document.created_at,
            updated_at=orm_document.updated_at,
            document_metadata=orm_document.document_metadata or {},
            clauses=clauses # Assign the list of domain clauses
        )
        return domain_document

    def _to_domain_clause(self, orm_clause: ClauseORM) -> Clause:
        if orm_clause is None:
            return None
        domain_clause = Clause(
            id=orm_clause.id,
            project_id=orm_clause.project_id,
            document_id=orm_clause.document_id,
            clause_code=orm_clause.clause_code,
            clause_type=orm_clause.clause_type,
            title=orm_clause.title,
            full_text=orm_clause.full_text,
            text_start_offset=orm_clause.text_start_offset,
            text_end_offset=orm_clause.text_end_offset,
            extracted_entities=orm_clause.extracted_entities or {},
            extraction_confidence=orm_clause.extraction_confidence,
            extraction_model=orm_clause.extraction_model,
            manually_verified=orm_clause.manually_verified,
            verified_at=orm_clause.verified_at
        )
        return domain_clause

    def _to_orm_document(self, domain_document: Document) -> DocumentORM:
        now = datetime.utcnow()
        orm_document = DocumentORM(
            id=domain_document.id,
            project_id=domain_document.project_id,
            document_type=domain_document.document_type,
            filename=domain_document.filename,
            file_format=domain_document.file_format,
            storage_url=domain_document.storage_url,
            storage_encrypted=domain_document.storage_encrypted,
            file_size_bytes=domain_document.file_size_bytes,
            upload_status=domain_document.upload_status,
            parsed_at=domain_document.parsed_at,
            parsing_error=domain_document.parsing_error,
            retention_until=domain_document.retention_until,
            created_by=domain_document.created_by,
            created_at=domain_document.created_at or now,
            updated_at=domain_document.updated_at or now,
            document_metadata=domain_document.document_metadata,
            # Note: clauses are handled separately if it's an aggregate root
        )
        return orm_document
    
    def _to_orm_clause(self, domain_clause: Clause) -> ClauseORM:
        orm_clause = ClauseORM(
            id=domain_clause.id,
            project_id=domain_clause.project_id,
            document_id=domain_clause.document_id,
            clause_code=domain_clause.clause_code,
            clause_type=domain_clause.clause_type,
            title=domain_clause.title,
            full_text=domain_clause.full_text,
            text_start_offset=domain_clause.text_start_offset,
            text_end_offset=domain_clause.text_end_offset,
            extracted_entities=domain_clause.extracted_entities,
            extraction_confidence=domain_clause.extraction_confidence,
            extraction_model=domain_clause.extraction_model,
            manually_verified=domain_clause.manually_verified,
            verified_at=domain_clause.verified_at
        )
        return orm_clause

    # --- Repository Methods ---
    async def add(self, document: Document) -> None:
        orm_document = self._to_orm_document(document)
        self.session.add(orm_document)

    async def get_by_id(self, document_id: UUID) -> Document | None:
        stmt = select(DocumentORM).where(DocumentORM.id == document_id)
        result = await self.session.execute(stmt)
        orm_document = result.scalar_one_or_none()
        return self._to_domain_document(orm_document)

    async def get_document_with_clauses(self, document_id: UUID) -> Document | None:
        stmt = select(DocumentORM).options(selectinload(DocumentORM.clauses)).where(DocumentORM.id == document_id)
        result = await self.session.execute(stmt)
        orm_document = result.scalar_one_or_none()
        return self._to_domain_document(orm_document)

    async def update_status(self, document_id: UUID, status: DocumentStatus, parsing_error: str | None = None) -> None:
        orm_document = await self.session.get(DocumentORM, document_id)
        if orm_document:
            orm_document.upload_status = status
            orm_document.parsing_error = parsing_error

    async def update_storage_path(self, document_id: UUID, storage_url: str) -> None:
        orm_document = await self.session.get(DocumentORM, document_id)
        if orm_document:
            orm_document.storage_url = storage_url

    async def delete(self, document_id: UUID) -> None:
        orm_document = await self.session.get(DocumentORM, document_id)
        if orm_document:
            await self.session.delete(orm_document)

    async def list_for_project(
        self, project_id: UUID, skip: int, limit: int
    ) -> Tuple[List[Document], int]:
        stmt = select(DocumentORM).where(DocumentORM.project_id == project_id).offset(skip).limit(limit)
        count_stmt = select(func.count()).where(DocumentORM.project_id == project_id)

        results = await self.session.execute(stmt)
        documents_orm = results.scalars().all()

        total_count_result = await self.session.execute(count_stmt)
        total_count = total_count_result.scalar_one()

        return [self._to_domain_document(doc_orm) for doc_orm in documents_orm], total_count

    async def get_project_tenant_id(self, project_id: UUID) -> UUID | None:
        result = await self.session.execute(
            text("SELECT tenant_id FROM projects WHERE id = :project_id"),
            {"project_id": str(project_id)},
        )
        return result.scalar_one_or_none()
    
    async def add_clause(self, clause: Clause) -> None:
        orm_clause = self._to_orm_clause(clause)
        self.session.add(orm_clause)

    async def commit(self) -> None:
        await self.session.commit()

    async def refresh(self, entity: Document | Clause) -> None:
        if isinstance(entity, Document):
            orm_entity = await self.session.get(DocumentORM, entity.id)
        elif isinstance(entity, Clause):
            orm_entity = await self.session.get(ClauseORM, entity.id)
        else:
            raise TypeError(f"Cannot refresh unknown entity type: {type(entity)}")
        if orm_entity:
            await self.session.refresh(orm_entity)
            # Update the domain entity with refreshed ORM data
            if isinstance(entity, Document):
                entity.filename = orm_entity.filename
                entity.file_format = orm_entity.file_format
                entity.storage_url = orm_entity.storage_url
                entity.storage_encrypted = orm_entity.storage_encrypted
                entity.file_size_bytes = orm_entity.file_size_bytes
                entity.upload_status = orm_entity.upload_status
                entity.parsed_at = orm_entity.parsed_at
                entity.parsing_error = orm_entity.parsing_error
                entity.retention_until = orm_entity.retention_until
                entity.created_by = orm_entity.created_by
                entity.created_at = orm_entity.created_at
                entity.updated_at = orm_entity.updated_at
                entity.document_metadata = orm_entity.document_metadata or {}
            elif isinstance(entity, Clause):
                entity.clause_code = orm_entity.clause_code
                entity.clause_type = orm_entity.clause_type
                entity.title = orm_entity.title
                entity.full_text = orm_entity.full_text
                entity.text_start_offset = orm_entity.text_start_offset
                entity.text_end_offset = orm_entity.text_end_offset
                entity.extracted_entities = orm_entity.extracted_entities or {}
                entity.extraction_confidence = orm_entity.extraction_confidence
                entity.extraction_model = orm_entity.extraction_model
                entity.manually_verified = orm_entity.manually_verified
                entity.verified_at = orm_entity.verified_at
