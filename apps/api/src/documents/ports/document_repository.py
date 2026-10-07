"""
Document Repository Interface (Port).
Defines the contract for interacting with document persistence.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from src.core.json_types import JsonDict
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
    async def get_document_with_clauses(
        self, tenant_id: TenantId, document_id: UUID, revision_id: UUID | None = None
    ) -> Document | None:
        """The document with ONE clause set: its current revision's (trusted-current
        rule) or, when ``revision_id`` is given, that historical revision's."""
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
    async def update_metadata(
        self, tenant_id: TenantId, document_id: UUID, document_metadata: JsonDict
    ) -> None:
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
        self,
        tenant_id: TenantId,
        document_id: UUID,
        clause_code: str,
        revision_id: UUID | None = None,
    ) -> Clause | None:
        """The clause with ``clause_code`` in the current (or the given) revision."""
        pass

    @abstractmethod
    async def list_clauses_for_document(self, tenant_id: TenantId, document_id: UUID) -> list[Clause]:
        """Every clause row of the document across ALL revisions (not current truth)."""
        pass

    # Lane C / C3a revision-scoped reads. Not abstract so existing test doubles keep
    # constructing; an adapter that does not implement them fails closed.
    async def list_current_clauses(self, tenant_id: TenantId, document_id: UUID) -> list[Clause]:
        """The current revision's clauses; empty when the current revision is unresolved."""
        raise NotImplementedError

    async def list_revision_clauses(
        self, tenant_id: TenantId, document_id: UUID, revision_id: UUID
    ) -> list[Clause]:
        """An explicitly requested revision's clauses (historical read)."""
        raise NotImplementedError

    async def list_clauses_bound_to_revision(
        self, tenant_id: TenantId, document_id: UUID, revision_id: UUID
    ) -> list[Clause]:
        """Only the rows physically bound to ``revision_id``."""
        raise NotImplementedError

    async def begin_processing_generation(
        self,
        tenant_id: TenantId,
        document_id: UUID,
        revision_id: UUID | None = None,
        *,
        expected_revision_id: UUID | None = None,
        expected_generation: int | None = None,
        expected_stage: str | None = None,
        expected_phase: str | None = None,
        expected_outcome: str | None = None,
    ) -> int | None:
        """#711: start a new processing generation in the current transaction.

        A new canonical revision or an explicit reprocess supersedes every
        earlier processing attempt. Adapters without a processing-authority
        store keep the default (no generation).
        """
        _ = (
            tenant_id,
            document_id,
            revision_id,
            expected_revision_id,
            expected_generation,
            expected_stage,
            expected_phase,
            expected_outcome,
        )
        return None

    @abstractmethod
    async def commit(self) -> None:
        """Commits pending changes to the repository."""
        pass

    @abstractmethod
    async def refresh(self, entity: Document | Clause) -> None:
        """Refreshes the state of an entity from the repository."""
        pass
