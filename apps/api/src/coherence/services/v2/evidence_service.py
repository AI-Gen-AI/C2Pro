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

from src.coherence.domain.v2_constants import MIN_EVIDENCE_BY_CATEGORY


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

    Phase 1 deterministic implementation (ADR-009 §2.2): coverage is computed
    as min(1.0, count / threshold) using MIN_EVIDENCE_BY_CATEGORY, so the
    shadow path reports an honest evidence ratio instead of a fixed 1.0
    placeholder. The production adapter (Phase 3) will replace this with a
    real document store query.
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
        count = len(project_docs)
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
            references=[f"doc-{i}" for i, _ in enumerate(project_docs)],
        )


__all__ = ["EvidenceBundle", "EvidenceService"]
