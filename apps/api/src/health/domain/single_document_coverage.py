"""Single-document coverage contracts (P0b slice L4-2/L4-3, ADR-024 / ADR-018).

These are **Health domain** contracts: they became persisted Health state in L4-3
(``HealthVector.single_document_coverage``), so they live in the domain layer rather
than the application layer. ``health.application.single_document_coverage`` — which
owns the *mapping service* that produces them — re-exports these same classes, so
there is exactly one canonical model and no parallel duplicate.

Invariants (unchanged from L4-2):
- ``evidence_clause_ids`` never repeats a clause id;
- ``evidence_count == len(set(evidence_clause_ids))`` — the count can never overstate
  the evidence (INV-1, no fabricated green);
- a ``gap``, when present, belongs to the same category as its assessment;
- a :class:`SingleDocumentCoverage` holds exactly one assessment per canonical category;
- ``cross_findings`` holds ONLY ``CROSS`` findings, preserved verbatim and never
  attributed to a canonical category.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.coherence.domain.category_weights import CoherenceCategory
from src.coherence.models import FindingSignal
from src.health.domain.category_coverage import CategoryCoverageState, CategoryGapAlert

_FROZEN_CONTRACT = ConfigDict(extra="forbid", frozen=True)

# The cross-dimensional label carried by FindingSignal.category alongside the six canonical
# categories. Preserved separately; never mapped onto a canonical category.
CROSS_CATEGORY = "CROSS"


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
        # --- Invariants that hold in EVERY state -------------------------------
        if len(set(self.evidence_clause_ids)) != len(self.evidence_clause_ids):
            raise ValueError("evidence_clause_ids must not repeat a clause id")
        if self.evidence_count != len(self.evidence_clause_ids):
            raise ValueError("evidence_count must equal the number of distinct evidence_clause_ids")
        if self.gap is not None and self.gap.category is not self.category:
            raise ValueError("gap alert category must match the assessment category")

        # --- State-specific invariants -----------------------------------------
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


class SingleDocumentCoverage(BaseModel):
    """Single-document coverage: the six category assessments + preserved CROSS findings.

    ``cross_findings`` holds the ``FindingSignal`` entries tagged ``CROSS``. They are
    cross-dimensional and CAN be produced from one document (``CROSS-BUDGET-SCOPE`` pairs
    a BUDGET clause with a SCOPE clause; ``CROSS-SCHEDULE-DELIVERY`` pairs a TIME clause
    with a TECHNICAL clause), so they are preserved verbatim rather than discarded, and are
    NOT attributed to any canonical category — a CROSS finding spans two dimensions and
    carries a composite ``clause_id``, so single-category attribution would fabricate
    evidence (INV-1).
    """

    model_config = _FROZEN_CONTRACT

    assessments: tuple[CategoryAssessment, ...]
    cross_findings: tuple[FindingSignal, ...] = ()

    @model_validator(mode="after")
    def _enforce_shape(self) -> SingleDocumentCoverage:
        categories = [assessment.category for assessment in self.assessments]
        if len(categories) != len(set(categories)) or set(categories) != set(CoherenceCategory):
            raise ValueError("assessments must hold exactly one entry per canonical category")
        if any(finding.category != CROSS_CATEGORY for finding in self.cross_findings):
            raise ValueError("cross_findings must hold only CROSS-category findings")
        return self


__all__ = ["CROSS_CATEGORY", "CategoryAssessment", "SingleDocumentCoverage"]
