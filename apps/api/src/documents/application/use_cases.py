"""
Application Use Cases for the Documents bounded context.

This module contains the high-level application logic (use cases)
that orchestrate the domain models and repositories to fulfill
business requirements.
"""

from dataclasses import dataclass
from uuid import uuid4
from datetime import datetime

from src.documents.application.dtos import CreateDocumentDTO
from src.documents.domain.models import Document, DocumentStatus
from src.documents.ports.document_repository import IDocumentRepository


@dataclass
class CreateDocumentUseCase:
    """
    Use case for creating a new document.
    It orchestrates the creation and persistence of a Document entity.
    """
    repository: IDocumentRepository

    def execute(self, dto: CreateDocumentDTO) -> Document:
        """
        Executes the use case.

        1. Creates a new Document entity from the DTO.
        2. Persists the new document using the repository.
        3. Returns the created document entity.
        """
        # For now, we are creating a basic Document entity.
        # A DocumentFactory might be introduced later for more complex creation logic.
        new_document = Document(
            id=uuid4(),
            project_id=dto.project_id,
            document_type=dto.document_type,
            filename=dto.filename,
            upload_status=DocumentStatus.UPLOADED, # Default status on creation
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            file_format=dto.file_format,
            storage_url=dto.storage_url,
            file_size_bytes=dto.file_size_bytes,
            created_by=dto.created_by,
            document_metadata=dto.document_metadata or {},
        )

        self.repository.save(new_document)

        return new_document
