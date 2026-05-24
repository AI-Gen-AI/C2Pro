"""
Document Repository Interface (Port).
Defines the contract for interacting with document persistence.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from src.core.tenants.types import TenantId
from src.documents.domain.models import (
    Clause,
    Document,
    DocumentAlertSignal,
    DocumentHistorySnapshot,
    DocumentStatus,
)


class IDocumentRepository(ABC):
    @abstractmethod
    async def add(self, tenant_id: TenantId, document: Document) -> None:
        """Adds a new document to the repository."""
        pass

    @abstractmethod
    async def get_by_id(self, tenant_id: TenantId, document_id: UUID) -> Document | None:
        """Retrieves a document by its ID."""
        pass

    @abstractmethod
    async def get_by_id_internal(self, document_id: UUID) -> Document | None:
        """Retrieves a document by its ID without tenant filtering. Internal use only."""
        pass

    @abstractmethod
    async def get_document_with_clauses(self, tenant_id: TenantId, document_id: UUID) -> Document | None:
        """Retrieves a document by its ID, including its associated clauses."""
        pass

    @abstractmethod
    async def get_history_snapshot(self, tenant_id: TenantId, document_id: UUID) -> DocumentHistorySnapshot | None:
        """Retrieves the normalized persistence projection needed to build a document history timeline."""
        pass

    @abstractmethod
    async def list_alert_signals_for_document(self, tenant_id: TenantId, document_id: UUID) -> list[DocumentAlertSignal]:
        """Lists alert projections linked to a document for downstream explanation/read models."""
        pass

    @abstractmethod
    async def update_status(
        self,
        tenant_id: TenantId,
        document_id: UUID,
        status: DocumentStatus,
        parsing_error: str | None = None,
        parsed_at: datetime | None = None,
    ) -> None:
        """Updates the status and optional parsing metadata of a document."""
        pass

    @abstractmethod
    async def update_metadata(self, tenant_id: TenantId, document_id: UUID, document_metadata: dict) -> None:
        """Updates the metadata of a document."""
        pass

    @abstractmethod
    async def update_storage_path(self, tenant_id: TenantId, document_id: UUID, storage_url: str) -> None:
        """Updates the storage URL of a document."""
        pass

    @abstractmethod
    async def update_version(
        self,
        tenant_id: TenantId,
        document_id: UUID,
        version: int,
        file_hash: str,
        filename: str,
        status: DocumentStatus,
    ) -> Document:
        """
        Updates document version and related fields for re-upload.
        Part of TASK-BCK-023.

        Args:
            document_id: Document to update
            version: New version number
            file_hash: New file hash
            filename: New filename
            status: New status (usually UPLOADED for re-processing)

        Returns:
            Updated document
        """
        pass

    @abstractmethod
    async def delete(self, tenant_id: TenantId, document_id: UUID) -> None:
        """Deletes a document from the repository."""
        pass

    @abstractmethod
    async def list_for_project(
        self, tenant_id: TenantId, project_id: UUID, skip: int, limit: int
    ) -> tuple[list[Document], int]:
        """Lists documents for a specific project with pagination."""
        pass

    @abstractmethod
    async def get_project_tenant_id(self, project_id: UUID) -> UUID | None:
        """Retrieves the tenant ID associated with a project."""
        pass

    @abstractmethod
    async def add_clause(self, tenant_id: TenantId, clause: Clause) -> None:
        """Adds a new clause to a document."""
        pass

    @abstractmethod
    async def clause_exists(self, tenant_id: TenantId, clause_id: UUID) -> bool:
        """Checks whether a clause exists by ID."""
        pass

    @abstractmethod
    async def get_clause_text_map(self, tenant_id: TenantId, clause_ids: list[UUID]) -> dict[UUID, str]:
        """Returns a map of clause_id to full_text for the given IDs."""
        pass

    @abstractmethod
    async def get_clauses_by_ids(self, tenant_id: TenantId, clause_ids: list[UUID]) -> list[Clause]:
        """Returns clauses for the given IDs."""
        pass

    @abstractmethod
    async def get_clause_by_document_and_code(
        self, tenant_id: TenantId, document_id: UUID, clause_code: str
    ) -> Clause | None:
        """Returns a clause by document_id and clause_code."""
        pass

    @abstractmethod
    async def list_clauses_for_document(self, tenant_id: TenantId, document_id: UUID) -> list[Clause]:
        """Lists all clauses for a document."""
        pass

    @abstractmethod
    async def commit(self) -> None:
        """Commits pending changes to the repository."""
        pass

    @abstractmethod
    async def refresh(self, entity: object) -> None:
        """Refreshes the state of an entity from the repository."""
        pass
