"""Single-document category-coverage domain (ADR-024 / ADR-018, P0b slice L4-1).

Pure domain: given per-category supporting-evidence counts extracted from ONE
document, compute honest coverage across the six canonical categories and the
actionable gap alerts for the categories that lack evidence.

Invariants:
- INV-1 (honest-null): a category is ``PRESENT`` only when backed by real evidence;
  a category without evidence is ``INSUFFICIENT_EVIDENCE`` — never a fabricated
  zero/green. There is no numeric score in this slice, so "null" is a distinct
  state, not a ``0``.
- Single-document scope: relational Coherence is OUT OF SCOPE here (no
  ``coherence_subscore`` is produced for one document).

Reuses the canonical ``CoherenceCategory`` (SCOPE/BUDGET/TIME/TECHNICAL/LEGAL/
QUALITY) and ``HealthNullReason.INSUFFICIENT_EVIDENCE`` rather than introducing
duplicate category/null-reason models.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.coherence.domain.category_weights import CoherenceCategory
from src.health.domain.health_vector import HealthNullReason

_FROZEN_CONTRACT = ConfigDict(extra="forbid", frozen=True)

# Actionable gap guidance per category: names the category and what to upload to
# cover it. Each message ends with "to assess <CATEGORY>." so the category is explicit.
_CATEGORY_GAP_ACTION: dict[CoherenceCategory, str] = {
    CoherenceCategory.SCOPE: "Upload the contract scope / statement of work to assess SCOPE.",
    CoherenceCategory.BUDGET: "Upload the budget or bill of quantities (BoQ) to assess BUDGET.",
    CoherenceCategory.TIME: "Upload the project schedule (cronograma) to assess TIME.",
    CoherenceCategory.TECHNICAL: "Upload the technical specifications (pliego técnico) to assess TECHNICAL.",
    CoherenceCategory.LEGAL: "Upload the legal terms and conditions to assess LEGAL.",
    CoherenceCategory.QUALITY: "Upload the quality plan / acceptance criteria to assess QUALITY.",
}

# Evidence extracted from one document: number of supporting units per category.
# A missing key or a non-positive count means "no evidence" for that category.
EvidenceByCategory = Mapping[CoherenceCategory, int]


class CategoryCoverageState(StrEnum):
    """Whether a category is evidence-backed or lacks sufficient evidence."""

    PRESENT = "present"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class CategoryCoverage(BaseModel):
    """Honest coverage for one category.

    ``PRESENT`` requires supporting evidence and carries no ``null_reason``.
    ``INSUFFICIENT_EVIDENCE`` carries zero evidence, ``HealthNullReason.
    INSUFFICIENT_EVIDENCE`` and a non-empty ``missing_data`` stating what is
    missing. This enforces INV-1 (no fabricated green).
    """

    model_config = _FROZEN_CONTRACT

    category: CoherenceCategory
    state: CategoryCoverageState
    evidence_count: int = Field(default=0, ge=0)
    missing_data: tuple[str, ...] = ()
    null_reason: HealthNullReason | None = None

    @model_validator(mode="after")
    def _enforce_honest_null(self) -> CategoryCoverage:
        if self.state is CategoryCoverageState.PRESENT:
            if self.evidence_count <= 0:
                raise ValueError("PRESENT coverage requires supporting evidence (evidence_count > 0)")
            if self.null_reason is not None:
                raise ValueError("PRESENT coverage cannot carry a null_reason")
            if self.missing_data:
                raise ValueError("PRESENT coverage cannot list missing_data")
            return self
        # INSUFFICIENT_EVIDENCE
        if self.evidence_count != 0:
            raise ValueError("INSUFFICIENT_EVIDENCE coverage must have zero evidence")
        if self.null_reason is not HealthNullReason.INSUFFICIENT_EVIDENCE:
            raise ValueError("INSUFFICIENT_EVIDENCE coverage requires null_reason=INSUFFICIENT_EVIDENCE")
        if not self.missing_data:
            raise ValueError("INSUFFICIENT_EVIDENCE coverage must state what is missing")
        return self


class CategoryGapAlert(BaseModel):
    """An actionable gap alert for a category that lacks sufficient evidence."""

    model_config = _FROZEN_CONTRACT

    category: CoherenceCategory
    action: str = Field(min_length=1)


def compute_category_coverage(evidence_by_category: EvidenceByCategory) -> tuple[CategoryCoverage, ...]:
    """Compute honest coverage for all six canonical categories from one document.

    A category is ``PRESENT`` only when backed by >= 1 evidence unit; otherwise it
    is ``INSUFFICIENT_EVIDENCE`` (never a fabricated zero/green). Always returns
    exactly one entry per :class:`CoherenceCategory`.
    """
    coverage: list[CategoryCoverage] = []
    for category in CoherenceCategory:
        count = int(evidence_by_category.get(category, 0))
        if count > 0:
            coverage.append(
                CategoryCoverage(
                    category=category,
                    state=CategoryCoverageState.PRESENT,
                    evidence_count=count,
                )
            )
        else:
            coverage.append(
                CategoryCoverage(
                    category=category,
                    state=CategoryCoverageState.INSUFFICIENT_EVIDENCE,
                    evidence_count=0,
                    missing_data=(_CATEGORY_GAP_ACTION[category],),
                    null_reason=HealthNullReason.INSUFFICIENT_EVIDENCE,
                )
            )
    return tuple(coverage)


def gap_alerts(coverage: tuple[CategoryCoverage, ...]) -> tuple[CategoryGapAlert, ...]:
    """Return one actionable gap alert per ``INSUFFICIENT_EVIDENCE`` category."""
    return tuple(
        CategoryGapAlert(category=item.category, action=_CATEGORY_GAP_ACTION[item.category])
        for item in coverage
        if item.state is CategoryCoverageState.INSUFFICIENT_EVIDENCE
    )


__all__ = [
    "CategoryCoverage",
    "CategoryCoverageState",
    "CategoryGapAlert",
    "EvidenceByCategory",
    "compute_category_coverage",
    "gap_alerts",
]
