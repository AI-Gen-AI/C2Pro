"""Build the persisted single-document assessment artifact at analysis completion (L4-3).

This is the ONE place the analysis pipeline invokes the L4-2 mapping service. It runs at
N8 (``coherence_scorer``), the earliest production point where the canonical
``coherence.models.Clause[]`` and ``FindingSignal[]`` coexist, and its output is persisted
verbatim in ``analyses.result_json``. Downstream consumers (SnapshotWriter → HealthVector)
read the persisted artifact — they never re-run the ``CategoryRouter``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from src.coherence.models import Clause, FindingSignal
from src.health.application.single_document_coverage import assess_single_document_coverage
from src.health.domain.analysis_assessment import encode_single_document_assessment
from src.health.domain.single_document_coverage import EvidenceGranularity


def build_document_assessment_artifact(
    clauses: Sequence[Clause],
    finding_signals: Sequence[FindingSignal],
    granularity: EvidenceGranularity = EvidenceGranularity.DOCUMENT,
    degradation_reason: str | None = None,
) -> dict[str, Any]:
    """Run L4-2 exactly once and return the additive ``result_json`` fragment.

    ``granularity`` records what the resulting ``evidence_clause_ids`` are — persisted
    ``documents.clauses`` UUIDs (P0b-R1) or a single synthetic document-level id. It
    defaults to the honest, weaker claim. ``degradation_reason`` records why a document
    that could have been clause-granular was not, so the reason survives into
    ``result_json`` instead of living only in a log line.
    """
    coverage = assess_single_document_coverage(clauses, finding_signals)
    return encode_single_document_assessment(
        coverage, finding_signals, granularity, degradation_reason
    )


__all__ = ["build_document_assessment_artifact"]
