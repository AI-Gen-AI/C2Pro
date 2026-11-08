"""Wire single-document analysis output into the L4-1 coverage contract (P0b slice L4-2).

Given the extracted ``Clause`` evidence and intrinsic ``FindingSignal`` findings for ONE
document, produce a per-category :class:`CategoryAssessment` over the six canonical
categories: ``{state, evidence, findings, missing_data, gap}``, plus the preserved
cross-dimensional (``CROSS``) findings.

The result contracts (:class:`CategoryAssessment`, :class:`SingleDocumentCoverage`) became
persisted Health state in L4-3, so they live in ``health.domain.single_document_coverage``
and are re-exported here — one canonical model, no parallel duplicate. This module owns the
*mapping service* that produces them.

Reuses existing contracts — the deterministic ``CategoryRouter`` (classification),
``FindingSignal`` (findings, already category-tagged), and the pure L4-1
``category_coverage`` domain — rather than introducing parallel models.

Qualifying-evidence contract (owned by this mapping layer, made explicit):
- A clause is *qualifying supporting evidence* when its text, with **no doc_type
  prior**, passes the canonical ``CategoryRouter`` threshold. Additionally, ONLY
  for verified CLAUSE granularity from persisted source rows, a conjunction of
  structural signal and two distinct lexicon terms in the SAME paragraph may
  qualify; never infer that a document-level synthetic blob is an actual clause. The latter corrects
  a Capa-1 blind spot caused by reserving 60% router weight for unavailable
  embeddings. A category name or a document-type expectation alone is not
  evidence. No source-free evidence, relational score or synthetic green is produced.
- ``evidence_count`` for a category is the number of *distinct* qualifying clauses; the
  category is ``PRESENT`` iff that count is >= 1, else ``INSUFFICIENT_EVIDENCE``.

CROSS findings are preserved, never discarded, and never attributed to a canonical
category — see :mod:`src.health.domain.single_document_coverage` for the producer audit
and the full rationale.

Single-document scope: relational Coherence is OUT OF SCOPE — no ``coherence_subscore`` and
no numeric Health score are produced here.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from uuid import UUID

from src.coherence.application.services.category_router import CategoryRouter, ChunkSignal
from src.coherence.category_registry import CanonicalCategory
from src.coherence.domain.category_weights import CoherenceCategory
from src.coherence.models import Clause, FindingSignal
from src.health.domain.category_coverage import (
    compute_category_coverage,
    gap_alerts,
)
from src.health.domain.single_document_coverage import (
    CROSS_CATEGORY as _CROSS_CATEGORY,
)
from src.health.domain.single_document_coverage import (
    CategoryAssessment,
    EvidenceGranularity,
    SingleDocumentCoverage,
)

# CanonicalCategory (router) uses SCHEDULE; the canonical product category is TIME.
# Reuse the established SCHEDULE->TIME alias; the other five map by identical name.
_CANONICAL_TO_COHERENCE: dict[CanonicalCategory, CoherenceCategory] = {
    CanonicalCategory.SCOPE: CoherenceCategory.SCOPE,
    CanonicalCategory.BUDGET: CoherenceCategory.BUDGET,
    CanonicalCategory.SCHEDULE: CoherenceCategory.TIME,
    CanonicalCategory.TECHNICAL: CoherenceCategory.TECHNICAL,
    CanonicalCategory.LEGAL: CoherenceCategory.LEGAL,
    CanonicalCategory.QUALITY: CoherenceCategory.QUALITY,
}

# A qualifier decides, deterministically, which categories a clause's text supports.
QualifyingCategoriesFn = Callable[[str], set[CanonicalCategory]]


def _router_qualifier(
    router: CategoryRouter, *, allow_clause_anchors: bool = False
) -> QualifyingCategoriesFn:
    """Deterministic, prior-free qualifier backed by the real ``CategoryRouter``."""

    def qualify(text: str) -> set[CanonicalCategory]:
        if not text.strip():
            return set()
        result = router.route([ChunkSignal(chunk_id="clause", text=text)], doc_type="", segments=[])
        threshold_qualified = {
            category
            for category, status in result.category_status.items()
            if status == "has_evidence"
        }
        # Stronger source anchors are safe only for verified persisted clauses.
        # A whole-document synthetic Clause may combine unrelated paragraphs.
        if not allow_clause_anchors:
            return threshold_qualified
        # Applied to the ENTIRE v2 Health decision, not just its fallback:
        # even the legacy threshold can classify an unrelated numeric heading
        # as positive. Contractual source context is mandatory in CLAUSE mode.
        if not router.clause_has_contractual_party(text):
            return set()
        return threshold_qualified | router.clause_source_evidence_categories(text)

    return qualify


def _partition_findings(
    findings: Sequence[FindingSignal],
) -> tuple[dict[CoherenceCategory, tuple[FindingSignal, ...]], tuple[FindingSignal, ...]]:
    """Split findings into per-canonical-category buckets and the preserved CROSS bucket.

    An unrecognised label raises rather than silently losing a finding.
    """
    grouped: dict[CoherenceCategory, list[FindingSignal]] = {
        category: [] for category in CoherenceCategory
    }
    cross: list[FindingSignal] = []
    for finding in findings:
        if finding.category == _CROSS_CATEGORY:
            cross.append(finding)
            continue
        grouped[CoherenceCategory(finding.category)].append(finding)
    return {category: tuple(items) for category, items in grouped.items()}, tuple(cross)


def assess_single_document_coverage(
    clauses: Sequence[Clause],
    findings: Sequence[FindingSignal],
    *,
    qualifier: QualifyingCategoriesFn | None = None,
    document_id: UUID | None = None,
    granularity: EvidenceGranularity = EvidenceGranularity.DOCUMENT,
) -> SingleDocumentCoverage:
    """Assess single-document category coverage from extracted clauses + findings.

    Returns exactly one :class:`CategoryAssessment` per canonical category, plus the
    preserved ``CROSS`` findings. No numeric Health score and no ``coherence_subscore``
    are produced (single-document scope).
    """
    if qualifier is None:
        qualifier = _router_qualifier(
            CategoryRouter.from_registry(),
            allow_clause_anchors=granularity is EvidenceGranularity.CLAUSE,
        )

    qualifying_ids: dict[CoherenceCategory, list[str]] = {
        category: [] for category in CoherenceCategory
    }
    seen_ids: dict[CoherenceCategory, set[str]] = {
        category: set() for category in CoherenceCategory
    }
    for clause in clauses:
        for canonical in qualifier(clause.text):
            category = _CANONICAL_TO_COHERENCE[canonical]
            # One clause supports a category at most once — counting it twice would
            # inflate evidence_count and overstate coverage strength (INV-1).
            if clause.id in seen_ids[category]:
                continue
            seen_ids[category].add(clause.id)
            qualifying_ids[category].append(clause.id)

    evidence_by_category = {category: len(ids) for category, ids in qualifying_ids.items()}
    coverage = compute_category_coverage(evidence_by_category)
    gaps_by_category = {alert.category: alert for alert in gap_alerts(coverage)}
    findings_by_category, cross_findings = _partition_findings(findings)

    return SingleDocumentCoverage(
        document_id=document_id,
        assessments=tuple(
            CategoryAssessment(
                category=item.category,
                state=item.state,
                evidence_count=item.evidence_count,
                evidence_clause_ids=tuple(qualifying_ids[item.category]),
                findings=findings_by_category[item.category],
                missing_data=item.missing_data,
                gap=gaps_by_category.get(item.category),
            )
            for item in coverage
        ),
        cross_findings=cross_findings,
    )


__all__ = [
    "CategoryAssessment",
    "QualifyingCategoriesFn",
    "SingleDocumentCoverage",
    "assess_single_document_coverage",
]
