"""Shared builders for CategoryAggregator-based coherence tests.

Single source for the EvidenceBundle / no-conflict fixtures so the per-category
aggregator suites don't duplicate them (keeps SonarCloud new-code duplication ≤ 3%).
"""
from __future__ import annotations

from src.coherence.services.v2.conflict_service import ConflictReport
from src.coherence.services.v2.evidence_service import EvidenceBundle


def bundle(
    count: int = 3,
    coverage: float = 0.9,
    tri: float = 0.85,
    freshness: float = 0.95,
) -> EvidenceBundle:
    """A sufficiently-covered evidence bundle for an assessable category."""
    return EvidenceBundle(
        count=count,
        evidence_coverage=coverage,
        evidence_freshness=freshness,
        avg_technical_reliability=tri,
        missing_required=[],
        references=[f"doc-{i}" for i in range(count)],
    )


def no_conflict() -> ConflictReport:
    """A clean conflict report (no hard conflict)."""
    return ConflictReport(
        severity="none", hard_conflict=False, conflict_set=[], evidence_certainty=1.0
    )


__all__ = ["bundle", "no_conflict"]
