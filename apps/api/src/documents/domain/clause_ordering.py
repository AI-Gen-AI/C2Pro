"""Deterministic ordering for persisted clause evidence (P0b-R1).

``documents.clauses`` rows are read back as *evidence* by the analysis pipeline, so their
order must be a stable total order: re-running an analysis over the same document has to
produce the same evidence sequence, and therefore the same persisted assessment.

``list_clauses_for_document`` issues no ``ORDER BY``, so PostgreSQL is free to return rows
in any order. This module — not the SQL adapter — owns the ordering *rule*, which keeps it
pure and directly testable.

The rule, in precedence order:

1. **Source order** when the row carries it: ``text_start_offset``. This is the document's
   own reading order and is always preferred when present.
2. **``clause_code``** otherwise. Ingestion writes zero-padded ``AUTO-001`` codes, so
   lexicographic order is document order for the deterministic contract splitter.
3. **The persisted UUID** as the final tie-break, so two clauses sharing a code can never
   swap places between runs.

Clauses that carry a source offset sort ahead of clauses that do not. Mixing the two is a
degenerate case (ingestion populates offsets for all rows of a document or none of them);
what matters is that the combined order is total and reproducible, never that an absent
offset is silently treated as ``0``.
"""

from __future__ import annotations

from collections.abc import Iterable

from src.documents.domain.models import Clause


def _sort_key(clause: Clause) -> tuple[int, int, str, str]:
    offset = clause.text_start_offset
    # `offset is None` first in the tuple keeps offset-bearing clauses ahead WITHOUT
    # coercing a missing offset into a real position (INV-1: absent is not zero).
    return (
        1 if offset is None else 0,
        offset if offset is not None else 0,
        clause.clause_code or "",
        str(clause.id),
    )


def order_clause_evidence(clauses: Iterable[Clause]) -> tuple[Clause, ...]:
    """Return the clauses in a stable, replay-safe total order."""
    return tuple(sorted(clauses, key=_sort_key))


__all__ = ["order_clause_evidence"]
