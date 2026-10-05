"""Persist a revision's clause set, bound to exactly that revision (Lane C / C3a).

Every revision of a contract keeps its own clause rows; nothing is overwritten,
copied or deleted when a new revision arrives. The caller passes the revision
pinned by the #711 processing authority -- never "the latest" one.

Idempotent: if rows are already bound to the revision (a retry, a redelivery, a
reprocess of the same immutable revision) they are returned unchanged and nothing
is inserted. Otherwise the rows are inserted with stable identities:

* when the revision already has an immutable analysis snapshot (written before
  C3a, when rows were not yet per revision), its clause ids are reused, so the
  snapshot's entity ids ARE the persisted ids;
* otherwise the id is derived from (revision, position, clause code), so two
  attempts of the same revision can never create a second set.

The caller builds the revision snapshot from the returned clauses.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from uuid import UUID, uuid5

from src.core.tenants.types import TenantId
from src.documents.domain.clause_ordering import order_clause_evidence
from src.documents.domain.models import Clause
from src.documents.ports.document_repository import IDocumentRepository

# Fixed namespace for revision-bound clause identities (never change: ids are durable).
CLAUSE_IDENTITY_NAMESPACE = UUID("6f1d3c52-8a0e-4c39-9b8c-1c3a0c0d0c3a")


class ClauseIdentityConflictError(ValueError):
    """A clause identity this revision must use already belongs to another row."""


@dataclass(frozen=True)
class RevisionClausePersistence:
    clauses: tuple[Clause, ...]
    inserted: int


def revision_clause_id(revision_id: UUID, position: int, clause_code: str) -> UUID:
    return uuid5(CLAUSE_IDENTITY_NAMESPACE, f"{revision_id}/{position}/{clause_code}")


async def persist_revision_clauses(
    repository: IDocumentRepository,
    *,
    tenant_id: TenantId,
    document_id: UUID,
    revision_id: UUID | None,
    extracted: Sequence[Clause],
    snapshot: Sequence[Clause] | None = None,
) -> RevisionClausePersistence:
    for clause in (*extracted, *(snapshot or ())):
        if clause.document_id != document_id:
            raise ClauseIdentityConflictError(
                f"clause {clause.id} belongs to document {clause.document_id}, not {document_id}"
            )

    if revision_id is None:
        # A pre-lineage document has exactly one (unbound) clause set: never a second.
        existing = await repository.list_clauses_for_document(tenant_id, document_id)
        if existing:
            return RevisionClausePersistence(order_clause_evidence(existing), 0)
        for clause in extracted:
            await repository.add_clause(tenant_id, clause)
        return RevisionClausePersistence(tuple(extracted), len(extracted))

    existing = await repository.list_clauses_bound_to_revision(tenant_id, document_id, revision_id)
    if existing:
        return RevisionClausePersistence(order_clause_evidence(existing), 0)

    if snapshot:
        rows = [
            replace(clause, tenant_id=tenant_id, document_id=document_id, revision_id=revision_id)
            for clause in snapshot
        ]
        taken = await repository.get_clauses_by_ids(tenant_id, [row.id for row in rows])
        if taken:
            # Rows with the snapshot's identities exist but are not bound to this
            # revision: binding or duplicating them would be a guess. Fail closed.
            raise ClauseIdentityConflictError(
                f"revision {revision_id} snapshot identities already persisted unbound"
            )
    else:
        rows = [
            replace(
                clause,
                id=revision_clause_id(revision_id, position, clause.clause_code),
                tenant_id=tenant_id,
                document_id=document_id,
                revision_id=revision_id,
            )
            for position, clause in enumerate(extracted)
        ]
    for row in rows:
        await repository.add_clause(tenant_id, row)
    return RevisionClausePersistence(tuple(rows), len(rows))


__all__ = [
    "CLAUSE_IDENTITY_NAMESPACE",
    "ClauseIdentityConflictError",
    "RevisionClausePersistence",
    "persist_revision_clauses",
    "revision_clause_id",
]
