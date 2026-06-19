"""TS-UD-HEALTH-018-004 - Health-scoped coherence subscore adapter.

Coherence Score remains a standalone C2Pro product signal. Within Project
Health, ADR-018 demotes coherence to one optional Contract dimension subscore.
"""

from __future__ import annotations

from src.analysis.adapters.graph.project_coherence_result import ProjectCoherenceResult


def coherence_subscore_from_result(result: ProjectCoherenceResult | None) -> float | None:
    """Extract ProjectGraph coherence overall score for Contract health scoring."""

    if result is None or result.overall_score is None:
        return None
    if result.overall_score <= 1.0:
        return result.overall_score * 100.0
    return result.overall_score


__all__ = ["coherence_subscore_from_result"]
