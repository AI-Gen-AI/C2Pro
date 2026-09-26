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
from src.health.domain.null_reason import HealthNullReason

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

# Factual "not detected" statement per category — the ``missing_data`` facet of ADR-024's
# {state, findings, missing_data}. Deliberately DISTINCT from the actionable gap alert
# (``_CATEGORY_GAP_ACTION``): ``missing_data`` states what is absent; the gap says what to do.
_CATEGORY_MISSING_DATA: dict[CoherenceCategory, str] = {
    CoherenceCategory.SCOPE: "contract scope / statement of work not detected",
    CoherenceCategory.BUDGET: "budget / bill of quantities (BoQ) not detected",
    CoherenceCategory.TIME: "project schedule / cronograma not detected",
    CoherenceCategory.TECHNICAL: "technical specifications / pliego técnico not detected",
    CoherenceCategory.LEGAL: "legal terms and conditions not detected",
    CoherenceCategory.QUALITY: "quality plan / acceptance criteria not detected",
}

# Evidence extracted from one document: number of supporting units per category.
# Contract: keys MUST be CoherenceCategory and values MUST be non-bool ints >= 0.
# Malformed input is a programming/domain error and is REJECTED — never silently
# coerced into an honest-null user state (INSUFFICIENT_EVIDENCE is a valid product
# state; an invalid key/type/negative count is not).
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


def _validate_evidence_input(evidence_by_category: EvidenceByCategory) -> None:
    """Reject malformed input up front.

    Invalid input is a programming/domain error — it must NOT be coerced into an
    honest-null user state. ``int > 0`` => PRESENT, ``int 0`` => INSUFFICIENT_EVIDENCE;
    a negative count, a bool/non-int value, or a non-``CoherenceCategory`` key are all
    rejected.
    """
    for key, value in evidence_by_category.items():
        if not isinstance(key, CoherenceCategory):
            raise TypeError(f"evidence key must be a CoherenceCategory, got {key!r}")
        # bool is a subclass of int — reject it explicitly (True/False is not a count).
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"evidence count for {key.value} must be a non-bool int, got {value!r}")
        if value < 0:
            raise ValueError(f"evidence count for {key.value} must be >= 0, got {value}")


def compute_category_coverage(evidence_by_category: EvidenceByCategory) -> tuple[CategoryCoverage, ...]:
    """Compute honest coverage for all six canonical categories from one document.

    A category is ``PRESENT`` only when backed by >= 1 evidence unit; a count of ``0``
    (or an absent key) is ``INSUFFICIENT_EVIDENCE`` (never a fabricated zero/green).
    Malformed input is rejected via :func:`_validate_evidence_input` rather than coerced.
    Always returns exactly one entry per :class:`CoherenceCategory`.
    """
    _validate_evidence_input(evidence_by_category)
    coverage: list[CategoryCoverage] = []
    for category in CoherenceCategory:
        count = evidence_by_category.get(category, 0)
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
                    missing_data=(_CATEGORY_MISSING_DATA[category],),
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
