"""Wire single-document analysis output into the L4-1 coverage contract (P0b slice L4-2).

Given the extracted ``Clause`` evidence and intrinsic ``FindingSignal`` findings for ONE
document, produce a per-category :class:`CategoryAssessment` over the six canonical
categories: ``{state, evidence, findings, missing_data, gap}``.

Reuses existing contracts — the deterministic ``CategoryRouter`` (classification),
``FindingSignal`` (findings, already category-tagged), and the pure L4-1
``category_coverage`` domain — rather than introducing parallel models.

Qualifying-evidence contract (owned by this mapping layer, made explicit):
- A clause is *qualifying supporting evidence* for a category iff the deterministic
  ``CategoryRouter`` reports ``has_evidence`` for that category when routing the clause's
  own text with **no doc_type prior** (``doc_type=""``). That is: the clause's in-document
  Capa-1 relevance exceeds the registry ``insufficient_evidence`` threshold (ADR D4/D5).
  It is therefore NOT "a clause exists", and it deliberately excludes the doc_type prior
  (a routing *expectation* is not substantive evidence — honoring INV-1, no fabricated green).
- ``evidence_count`` for a category is the number of qualifying clauses; the category is
  ``PRESENT`` iff that count is >= 1, else ``INSUFFICIENT_EVIDENCE``.

Single-document scope: relational Coherence is OUT OF SCOPE — no ``coherence_subscore`` and
no numeric Health score are produced here.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.coherence.application.services.category_router import CategoryRouter, ChunkSignal
from src.coherence.category_registry import CanonicalCategory
from src.coherence.domain.category_weights import CoherenceCategory
from src.coherence.models import Clause, FindingSignal
from src.health.domain.category_coverage import (
    CategoryCoverageState,
    CategoryGapAlert,
    compute_category_coverage,
    gap_alerts,
)

_FROZEN_CONTRACT = ConfigDict(extra="forbid", frozen=True)

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


class CategoryAssessment(BaseModel):
    """Per-category single-document assessment: state + evidence + findings + gap.

    ``PRESENT`` carries qualifying evidence and no gap; ``INSUFFICIENT_EVIDENCE`` carries
    no evidence, factual ``missing_data`` and an actionable ``gap``. ``findings`` are
    independent of coverage state (an issue can exist regardless of coverage).
    """

    model_config = _FROZEN_CONTRACT

    category: CoherenceCategory
    state: CategoryCoverageState
    evidence_count: int = Field(default=0, ge=0)
    evidence_clause_ids: tuple[str, ...] = ()
    findings: tuple[FindingSignal, ...] = ()
    missing_data: tuple[str, ...] = ()
    gap: CategoryGapAlert | None = None

    @model_validator(mode="after")
    def _enforce_consistency(self) -> CategoryAssessment:
        if self.state is CategoryCoverageState.PRESENT:
            if self.evidence_count <= 0 or not self.evidence_clause_ids:
                raise ValueError("PRESENT assessment requires qualifying evidence")
            if self.gap is not None:
                raise ValueError("PRESENT assessment cannot carry a gap alert")
            if self.missing_data:
                raise ValueError("PRESENT assessment cannot list missing_data")
            return self
        if self.evidence_count != 0 or self.evidence_clause_ids:
            raise ValueError("INSUFFICIENT_EVIDENCE assessment must have no evidence")
        if self.gap is None:
            raise ValueError("INSUFFICIENT_EVIDENCE assessment requires a gap alert")
        if not self.missing_data:
            raise ValueError("INSUFFICIENT_EVIDENCE assessment must state missing_data")
        return self


def _router_qualifier(router: CategoryRouter) -> QualifyingCategoriesFn:
    """Deterministic, prior-free qualifier backed by the real ``CategoryRouter``."""

    def qualify(text: str) -> set[CanonicalCategory]:
        if not text.strip():
            return set()
        result = router.route([ChunkSignal(chunk_id="clause", text=text)], doc_type="", segments=[])
        return {
            category
            for category, status in result.category_status.items()
            if status == "has_evidence"
        }

    return qualify


def _group_findings(findings: Sequence[FindingSignal]) -> dict[CoherenceCategory, tuple[FindingSignal, ...]]:
    grouped: dict[CoherenceCategory, list[FindingSignal]] = {category: [] for category in CoherenceCategory}
    for finding in findings:
        # FindingSignal.category is a str Literal that also includes "CROSS" — a cross-category
        # (relational) finding with no single-document category home. Attach only single-category
        # findings to their category; skip cross-category ones (they belong to the ≥2-doc path).
        try:
            category = CoherenceCategory(finding.category)
        except ValueError:
            continue
        grouped[category].append(finding)
    return {category: tuple(items) for category, items in grouped.items()}


def assess_single_document_coverage(
    clauses: Sequence[Clause],
    findings: Sequence[FindingSignal],
    *,
    qualifier: QualifyingCategoriesFn | None = None,
) -> tuple[CategoryAssessment, ...]:
    """Assess single-document category coverage from extracted clauses + findings.

    Returns exactly one :class:`CategoryAssessment` per canonical category. No numeric
    Health score and no ``coherence_subscore`` are produced (single-document scope).
    """
    if qualifier is None:
        qualifier = _router_qualifier(CategoryRouter.from_registry())

    qualifying_ids: dict[CoherenceCategory, list[str]] = {category: [] for category in CoherenceCategory}
    for clause in clauses:
        for canonical in qualifier(clause.text):
            qualifying_ids[_CANONICAL_TO_COHERENCE[canonical]].append(clause.id)

    evidence_by_category = {category: len(ids) for category, ids in qualifying_ids.items()}
    coverage = compute_category_coverage(evidence_by_category)
    gaps_by_category = {alert.category: alert for alert in gap_alerts(coverage)}
    findings_by_category = _group_findings(findings)

    return tuple(
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
    )


__all__ = [
    "CategoryAssessment",
    "QualifyingCategoriesFn",
    "assess_single_document_coverage",
]
