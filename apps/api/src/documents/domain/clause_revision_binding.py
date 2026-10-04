"""Which immutable document revision a persisted clause was extracted from.

Ingestion records the pinned revision on every clause it extracts
(``extracted_entities.evidence_location.revision_id``). Persisted clause rows are
written once per document, so after a re-upload they can still describe an
earlier revision. A reader that analyses the current revision must not consume
them as that revision's clauses.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any
from uuid import UUID

from src.documents.domain.models import Clause


def clause_revision_id(clause: Clause) -> UUID | None:
    """The revision the clause was extracted from, or ``None`` when unrecorded."""
    return revision_id_from_extracted_entities(clause.extracted_entities)


def revision_id_from_extracted_entities(extracted_entities: Mapping[str, Any] | None) -> UUID | None:
    """Same binding, read from a raw ``clauses.extracted_entities`` value."""
    location = (extracted_entities or {}).get("evidence_location")
    raw = location.get("revision_id") if isinstance(location, dict) else None
    if not raw:
        return None
    try:
        return UUID(str(raw))
    except ValueError:
        # A malformed binding proves nothing about the clause's revision.
        return None


def clauses_bound_to_revision(
    clauses: Iterable[Clause],
    *,
    revision_id: UUID,
    parent_revision_id: UUID | None,
) -> bool:
    """True only when every clause provably belongs to ``revision_id``.

    An unrecorded binding is accepted only for a revision with no parent: with a
    single revision in the lineage there is nothing the clause could be stale against.
    """
    for clause in clauses:
        bound = clause_revision_id(clause)
        if bound == revision_id:
            continue
        if bound is None and parent_revision_id is None:
            continue
        return False
    return True


__all__ = ["clause_revision_id", "clauses_bound_to_revision", "revision_id_from_extracted_entities"]
