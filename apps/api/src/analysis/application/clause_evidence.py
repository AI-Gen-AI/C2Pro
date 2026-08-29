"""Resolve the clause evidence N8 scores and assesses (P0b-R1).

Before R1 the analysis graph fabricated a single ``coherence.models.Clause`` holding the
entire document text. Every category therefore rested on the same synthetic id, cross-clause
pairing was structurally impossible (one clause cannot pair), and no finding could be traced
to an addressable part of the contract.

Ingestion already solves the segmentation problem: ``core.tasks.ingestion_tasks`` splits a
contract on real clause boundaries and persists the result in ``documents.clauses``,
idempotently and exactly once per document. R1 introduces **no new parser** — it reads those
rows back through the Documents read port and adapts them into the canonical coherence
contract.

Identity: the canonical evidence id is ``str(persisted_clause.id)``, the persisted UUID
primary key. ``clause_code`` (``AUTO-001``) is a per-document display label — it is not
unique across documents and is not identity; it travels as metadata. Because ingestion
writes these ids once, at ingestion, replaying an analysis yields the same evidence ids.

Granularity is explicit, never inferred by a reader:

- ``CLAUSE``   — a contract with persisted clauses; ids are real ``documents.clauses`` UUIDs.
- ``DOCUMENT`` — the legacy whole-document clause; the id is a synthetic document-level
  marker. This covers non-contract documents (which have no persisted segmentation) and a
  contract whose clauses could not be read. In neither case may the synthetic id be
  presented as if it were persisted clause evidence.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from src.coherence.models import Clause as CoherenceClause
from src.documents.domain.models import Clause as PersistedClause
from src.health.domain.analysis_assessment import EvidenceGranularity

# Only contracts are segmented and persisted by ingestion today; every other document type
# keeps the pre-R1 whole-document path unchanged.
CONTRACT_DOC_TYPE = "contract"

# Degradation reasons, recorded on the resolved evidence so the reason a contract fell back
# to document granularity is observable rather than guessed.
REASON_NO_PERSISTED_CLAUSES = "contract_has_no_persisted_clauses"
REASON_CLAUSE_READ_FAILED = "persisted_clause_read_failed"
REASON_MISSING_IDENTITY = "missing_tenant_or_document_id"
REASON_NON_CONTRACT = "document_type_is_not_segmented"


@dataclass(frozen=True)
class ClauseEvidence:
    """The clauses N8 will score, plus what those clause ids actually are."""

    clauses: tuple[CoherenceClause, ...]
    granularity: EvidenceGranularity
    degradation_reason: str | None = None


def to_coherence_clauses(
    persisted: Sequence[PersistedClause],
    *,
    doc_type: str,
) -> tuple[CoherenceClause, ...]:
    """Adapt persisted Documents clauses into the canonical coherence contract.

    Every input clause produces exactly one output clause — no cap, no filter, no silent
    truncation. Absent source spans stay ``None``; they are never reinterpreted as ``0``,
    which would claim a position the row does not have.
    """
    return tuple(
        CoherenceClause(
            id=str(clause.id),
            text=clause.full_text or "",
            data={
                # Lineage — what this evidence is and where it came from.
                "document_type": doc_type,
                "evidence_granularity": EvidenceGranularity.CLAUSE.value,
                "source_document_id": str(clause.document_id),
                # Metadata carried from the persisted row (never identity).
                "clause_code": clause.clause_code,
                "clause_type": clause.clause_type.value if clause.clause_type else None,
                "title": clause.title,
                "extracted_entities": dict(clause.extracted_entities or {}),
                # Source spans are NULL for deterministically-ingested contracts today;
                # they are propagated as-is so a future span backfill needs no remapping.
                "text_start_offset": clause.text_start_offset,
                "text_end_offset": clause.text_end_offset,
            },
        )
        for clause in persisted
    )


def granular_evidence(
    persisted: Sequence[PersistedClause],
    *,
    doc_type: str,
) -> ClauseEvidence:
    """Clause-granular evidence backed by persisted ``documents.clauses`` rows."""
    return ClauseEvidence(
        clauses=to_coherence_clauses(persisted, doc_type=doc_type),
        granularity=EvidenceGranularity.CLAUSE,
    )


def whole_document_clause_id(doc_type: str, document_id: str) -> str:
    """The synthetic, document-level evidence id — stable, never random, never a clause id."""
    return f"{doc_type}-{document_id}"


def whole_document_evidence(
    *,
    doc_type: str,
    document_id: str,
    text: str,
    risks: Sequence[Any],
    wbs: Sequence[Any],
    bom_items: Sequence[Any],
    degradation_reason: str | None = None,
) -> ClauseEvidence:
    """The pre-R1 whole-document clause, retained for non-contract documents and fallbacks."""
    return ClauseEvidence(
        clauses=(
            CoherenceClause(
                id=whole_document_clause_id(doc_type, document_id),
                text=text,
                data={
                    "document_type": doc_type,
                    "evidence_granularity": EvidenceGranularity.DOCUMENT.value,
                    "risks": list(risks),
                    "wbs": list(wbs),
                    "bom_items": list(bom_items),
                },
            ),
        ),
        granularity=EvidenceGranularity.DOCUMENT,
        degradation_reason=degradation_reason,
    )


__all__ = [
    "CONTRACT_DOC_TYPE",
    "REASON_CLAUSE_READ_FAILED",
    "REASON_MISSING_IDENTITY",
    "REASON_NON_CONTRACT",
    "REASON_NO_PERSISTED_CLAUSES",
    "ClauseEvidence",
    "EvidenceGranularity",
    "granular_evidence",
    "to_coherence_clauses",
    "whole_document_clause_id",
    "whole_document_evidence",
]
