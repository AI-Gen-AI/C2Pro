"""Composition root binding the analysis graph to the Documents clause read port (P0b-R1).

The analysis bounded context must not know how Documents stores clauses, so this is the one
place that opens a tenant-scoped session and builds the Documents repository. The graph node
receives Documents *domain* clauses; ``ClauseORM`` never crosses the boundary.

Mirrors the existing N10 pattern (``build_project_knowledge_graph(session)``) — an
analysis-side factory over another context's adapter — rather than inventing a new one.

Persisted clause rows are written once per document, so after a re-upload they may still
be the previous revision's clauses. They are returned only when they are bound to the
document's current revision; otherwise ``StaleClauseEvidenceError`` is raised.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from src.analysis.application.clause_evidence import StaleClauseEvidenceError
from src.documents.domain.clause_revision_binding import clauses_bound_to_revision
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
) -> tuple[Clause, ...]:
    """Read the current revision's persisted clauses, RLS-scoped, in deterministic order."""
    from src.core.database import get_session_with_tenant
    from src.documents.adapters.persistence.sqlalchemy_document_repository import (
        SqlAlchemyDocumentRepository,
    )
    from src.documents.application.read_clause_evidence import read_clause_evidence

    async with get_session_with_tenant(tenant_id) as session:
        clauses = await read_clause_evidence(
            SqlAlchemyDocumentRepository(session), tenant_id, document_id
        )
        if not clauses:
            return clauses
        current = await load_current_revision(session, tenant_id, document_id)
        if current is not None and not clauses_bound_to_revision(
            clauses,
            revision_id=current.revision_id,
            parent_revision_id=current.parent_revision_id,
        ):
            raise StaleClauseEvidenceError(
                f"persisted clauses of document {document_id} are not bound to its "
                f"current revision {current.revision_id}"
            )
        return clauses


__all__ = ["load_current_revision", "load_persisted_clause_evidence"]
