"""Port for the DocumentRevision repository (ADR-015 / TASK-V3-015-01).

LOCKED INVARIANT: implementations MUST NOT call session commit().
Enforced by tests/unit/temporal/test_no_commit_in_revision_repository.py.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from src.temporal.domain.document_revision import DocumentRevision


class IDocumentRevisionRepository(ABC):
    @abstractmethod
    async def get_current(
        self, document_id: UUID, tenant_id: UUID
    ) -> DocumentRevision | None: ...

    @abstractmethod
    async def list_lineage(
        self, document_id: UUID, tenant_id: UUID
    ) -> list[DocumentRevision]: ...

    @abstractmethod
    async def append_revision(
        self, rev: DocumentRevision
    ) -> DocumentRevision: ...

    @abstractmethod
    async def close_current(
        self, document_id: UUID, tenant_id: UUID, valid_to: datetime
    ) -> None: ...


__all__ = ["IDocumentRevisionRepository"]
