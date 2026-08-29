"""Narrow read port exposing persisted clause evidence to other bounded contexts (P0b-R1).

The analysis pipeline needs the clauses ingestion already persisted for a document, and
nothing else. Consuming the full :class:`~src.documents.ports.document_repository.IDocumentRepository`
would hand it write methods it must never use; consuming ``ClauseORM`` would drag the
Documents persistence schema into the analysis bounded context.

This protocol is that minimal published contract: one tenant-scoped read returning
Documents *domain* clauses. :class:`SqlAlchemyDocumentRepository` already satisfies it
structurally, so no adapter change is required.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable
from uuid import UUID

from src.documents.domain.models import Clause


@runtime_checkable
class ClauseEvidenceReader(Protocol):
    """Tenant-scoped read access to a document's persisted clauses."""

    async def list_clauses_for_document(
        self, tenant_id: UUID, document_id: UUID
    ) -> Sequence[Clause]:
        """Return the clauses persisted for ``document_id`` within ``tenant_id``."""
        ...


__all__ = ["ClauseEvidenceReader"]
