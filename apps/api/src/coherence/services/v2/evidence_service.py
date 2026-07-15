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

    Phase 1 implementation is intentionally minimal: it is a Protocol-shaped
    base class for stub services in tests and for the deterministic adapter
    used during shadow-mode. The production adapter (Phase 3) will plug in
    the real document store query.
    """

    def collect(  # noqa: D401 — Protocol-style stub
        self,
        category: str,  # noqa: ARG002 - required by the EvidenceService interface
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
        return EvidenceBundle(
            count=len(project_docs),
            evidence_coverage=1.0,
            evidence_freshness=1.0,
            avg_technical_reliability=0.9,
            missing_required=[],
            references=[f"doc-{i}" for i, _ in enumerate(project_docs)],
        )


__all__ = ["EvidenceBundle", "EvidenceService"]
