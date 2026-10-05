"""Composition root binding the analysis graph to the Documents clause read port (P0b-R1).

The analysis bounded context must not know how Documents stores clauses, so this is the one
place that opens a tenant-scoped session and builds the Documents repository. The graph node
receives Documents *domain* clauses; ``ClauseORM`` never crosses the boundary.

Mirrors the existing N10 pattern (``build_project_knowledge_graph(session)``) — an
analysis-side factory over another context's adapter — rather than inventing a new one.

Lane C / C3a: every revision persists its own clause rows, physically bound to it. A run
reads exactly the revision its #711 processing authority pinned (``revision_id``) -- never
"the latest" one. Legacy unbound rows stand in only for a document's single revision;
when the pinned revision has no clause set of its own, ``StaleClauseEvidenceError`` is
raised so N8 degrades to whole-document evidence instead of scoring another revision's
clauses.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from src.analysis.application.clause_evidence import StaleClauseEvidenceError
from src.documents.domain.clause_ordering import order_clause_evidence
from src.documents.domain.models import Clause
from src.temporal.domain.document_revision import DocumentRevision


async def load_current_revision(
    session: Any, tenant_id: UUID, document_id: UUID
) -> DocumentRevision | None:
    """The document's open (current) revision inside the caller's RLS session."""
    from src.temporal.adapters.persistence.document_revision_repository import (
        SqlAlchemyDocumentRevisionRepository,
    )

    return await SqlAlchemyDocumentRevisionRepository(session).get_current(
        document_id, tenant_id
    )


async def load_persisted_clause_evidence(
    tenant_id: UUID,
    document_id: UUID,
    revision_id: UUID | None = None,
) -> tuple[Clause, ...]:
    """Read the pinned revision's persisted clauses, RLS-scoped, in deterministic order.

    ``revision_id`` is the revision the processing authority pinned. Without one (a
    run with no pinned revision), the document's open revision is used.
    """
    from src.core.database import get_session_with_tenant
    from src.documents.adapters.persistence.sqlalchemy_document_repository import (
        SqlAlchemyDocumentRepository,
    )
    from src.documents.application.read_clause_evidence import read_clause_evidence

    async with get_session_with_tenant(tenant_id) as session:
        repository = SqlAlchemyDocumentRepository(session)
        if revision_id is None:
            current = await load_current_revision(session, tenant_id, document_id)
            revision_id = current.revision_id if current is not None else None
        if revision_id is None:
            # A pre-lineage document has exactly one (unbound) clause set.
            return await read_clause_evidence(repository, tenant_id, document_id)
        pinned = await repository.list_revision_clauses(tenant_id, document_id, revision_id)
        if pinned:
            return order_clause_evidence(pinned)
        if await repository.list_clauses_for_document(tenant_id, document_id):
            raise StaleClauseEvidenceError(
                f"document {document_id} has no clauses persisted for its pinned "
                f"revision {revision_id}"
            )
        return ()


__all__ = ["load_current_revision", "load_persisted_clause_evidence"]
