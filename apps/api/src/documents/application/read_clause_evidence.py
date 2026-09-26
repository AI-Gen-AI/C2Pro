"""Read a document's persisted clause evidence in deterministic order (P0b-R1).

The single Documents-owned entry point other bounded contexts use to obtain clause
evidence. It adds exactly one thing over the raw port call: the canonical ordering, so
callers cannot accidentally depend on PostgreSQL's unspecified row order.

Tenant scoping is the port's (and ultimately RLS's) responsibility — ``tenant_id`` is
passed through unchanged and never defaulted.
"""

from __future__ import annotations

from uuid import UUID

from src.documents.domain.clause_ordering import order_clause_evidence
from src.documents.domain.models import Clause
from src.documents.ports.clause_evidence_reader import ClauseEvidenceReader


async def read_clause_evidence(
    reader: ClauseEvidenceReader,
    tenant_id: UUID,
    document_id: UUID,
) -> tuple[Clause, ...]:
    """Return every persisted clause for the document, in canonical order."""
    clauses = await reader.list_clauses_for_document(tenant_id, document_id)
    return order_clause_evidence(clauses)


__all__ = ["read_clause_evidence"]
