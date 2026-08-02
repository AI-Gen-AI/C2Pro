"""
Evidence qualification service (ADR-009 §6 — Category Aggregator pseudocode).

Phase 1 scope: deterministic evidence bundle assembly only. Real document
ingestion is wired by the orchestrator at call sites that pass per-category
document snapshots.

Refers to Suite ID: TS-UA-COH-V2-EVID-001.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.coherence.domain.v2_constants import (
    COHERENCE_CATEGORY_TO_DOC_TYPES,
    MIN_EVIDENCE_BY_CATEGORY,
)


@dataclass(frozen=True)
class EvidenceBundle:
    count: int
    evidence_coverage: float
    evidence_freshness: float
    avg_technical_reliability: float
    missing_required: list[str]
    references: list[str]


class EvidenceService:
    """Collects evidence for a single category from a project document set.

    Phase 1 deterministic implementation (ADR-009 §2.2): only documents whose
    document_type matches the category's canonical mapping (from
    COHERENCE_CATEGORY_TO_DOC_TYPES, derived from category_registry.yaml
    doc_type_priors) are counted. Coverage = min(1.0, count / threshold) using
    MIN_EVIDENCE_BY_CATEGORY, so the shadow path reports honest per-category
    evidence ratios instead of inflated cross-category counts.

    QUALITY has no canonical prior (frozenset()) — all doc types contribute.
    Unknown categories fall back to no-filter (all docs count).
    """

    def collect(
        self,
        category: str,
        project_docs: list[Any],
    ) -> EvidenceBundle:
        if not project_docs:
            return EvidenceBundle(
                count=0,
                evidence_coverage=0.0,
                evidence_freshness=0.0,
                avg_technical_reliability=0.0,
                missing_required=[],
                references=[],
            )

        relevant_types = COHERENCE_CATEGORY_TO_DOC_TYPES.get(category)
        # relevant_types is None → unknown category (no filter)
        # relevant_types is frozenset() → QUALITY (no filter, all docs contribute)
        # relevant_types is non-empty frozenset → filter by doc type
        if relevant_types:
            filtered = [
                d for d in project_docs
                if getattr(d, "document_type", None) in relevant_types
            ]
        else:
            filtered = list(project_docs)

        count = len(filtered)
        if count == 0:
            return EvidenceBundle(
                count=0,
                evidence_coverage=0.0,
                evidence_freshness=0.0,
                avg_technical_reliability=0.0,
                missing_required=[],
                references=[],
            )

        threshold = MIN_EVIDENCE_BY_CATEGORY.get(category, 1)
        evidence_coverage = min(1.0, count / threshold)
        missing_required = (
            [f"need_{threshold - count}_more_documents"] if count < threshold else []
        )
        return EvidenceBundle(
            count=count,
            evidence_coverage=evidence_coverage,
            evidence_freshness=1.0,
            avg_technical_reliability=0.9,
            missing_required=missing_required,
            references=[f"doc-{getattr(d, 'id', i)}" for i, d in enumerate(filtered)],
        )


__all__ = ["EvidenceBundle", "EvidenceService"]
