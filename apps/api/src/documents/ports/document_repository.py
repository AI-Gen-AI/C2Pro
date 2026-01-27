"""
Document Repository Interface (Port).
Defines the contract for interacting with document persistence.
"""
from abc import ABC, abstractmethod
from typing import List, Tuple
from uuid import UUID

from src.documents.domain.models import Document, DocumentStatus, DocumentType, Clause

class IDocumentRepository(ABC):
    @abstractmethod
    async def add(self, document: Document) -> None:
        """Adds a new document to the repository."""
        pass

    @abstractmethod
    async def get_by_id(self, document_id: UUID) -> Document | None:
        """Retrieves a document by its ID."""
        pass

    @abstractmethod
    async def get_document_with_clauses(self, document_id: UUID) -> Document | None:
        """Retrieves a document by its ID, including its associated clauses."""
        pass

    @abstractmethod
    async def update_status(self, document_id: UUID, status: DocumentStatus, parsing_error: str | None = None) -> None:
        """Updates the status and optional parsing error of a document."""
        pass

    @abstractmethod
    async def update_storage_path(self, document_id: UUID, storage_url: str) -> None:
        """Updates the storage URL of a document."""
        pass

    @abstractmethod
    async def delete(self, document_id: UUID) -> None:
        """Deletes a document from the repository."""
        pass

    @abstractmethod
    async def list_for_project(
        self, project_id: UUID, skip: int, limit: int
    ) -> Tuple[List[Document], int]:
        """Lists documents for a specific project with pagination."""
        pass

    @abstractmethod
    async def get_project_tenant_id(self, project_id: UUID) -> UUID | None:
        """Retrieves the tenant ID associated with a project."""
        pass

    @abstractmethod
    async def add_clause(self, clause: Clause) -> None:
        """Adds a new clause to a document."""
        pass
    
    @abstractmethod
    async def commit(self) -> None:
        """Commits pending changes to the repository."""
        pass

    @abstractmethod
    async def refresh(self, entity: object) -> None:
        """Refreshes the state of an entity from the repository."""
        pass
