"""Composition root binding the analysis graph to the Documents clause read port (P0b-R1).

The analysis bounded context must not know how Documents stores clauses, so this is the one
place that opens a tenant-scoped session and builds the Documents repository. The graph node
receives Documents *domain* clauses; ``ClauseORM`` never crosses the boundary.

Mirrors the existing N10 pattern (``build_project_knowledge_graph(session)``) — an
analysis-side factory over another context's adapter — rather than inventing a new one.
"""

from __future__ import annotations

from uuid import UUID

from src.documents.domain.models import Clause


async def load_persisted_clause_evidence(
    tenant_id: UUID,
    document_id: UUID,
) -> tuple[Clause, ...]:
    """Read the document's persisted clauses, RLS-scoped, in deterministic order."""
    from src.core.database import get_session_with_tenant
    from src.documents.adapters.persistence.sqlalchemy_document_repository import (
        SqlAlchemyDocumentRepository,
    )
    from src.documents.application.read_clause_evidence import read_clause_evidence

    async with get_session_with_tenant(tenant_id) as session:
        return await read_clause_evidence(
            SqlAlchemyDocumentRepository(session), tenant_id, document_id
        )


__all__ = ["load_persisted_clause_evidence"]
