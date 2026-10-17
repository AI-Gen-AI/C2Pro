"""Revision-bound, source-verified structured budget-row evidence.

This contract deliberately does not consume the legacy procurement BOM or WBS
``budget_spent`` fields.  An adapter must supply a locator it observed while
parsing one immutable :class:`DocumentRevision`; mapping a row to WBS requires
the adapter to have resolved the current approved WBS baseline first.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from src.temporal.domain.document_revision import DocumentRevision


class BudgetRowEvidenceError(ValueError):
    """Base error for an attempt to create non-authoritative budget evidence."""


class InvalidBudgetRowEvidenceError(BudgetRowEvidenceError):
    """The claimed row is not bound to the verified source revision."""


class DuplicateBudgetRowEvidenceError(BudgetRowEvidenceError):
    """The immutable revision/locator identity has already been recorded."""


class UnapprovedWBSMappingError(BudgetRowEvidenceError):
    """A budget row tried to link to a WBS node without an approved baseline."""


class BudgetAssessmentState(StrEnum):
    """Readiness only; this is intentionally not a green coherence outcome."""

    NOT_ASSESSED = "NOT_ASSESSED"
    READY_FOR_COMPARISON = "READY_FOR_COMPARISON"


@dataclass(frozen=True)
class ApprovedWBSScope:
    """Approved WBS authority resolved by the application/persistence boundary."""

    tenant_id: UUID
    project_id: UUID
    baseline_id: UUID
    node_ids: frozenset[UUID]


@dataclass(frozen=True)
class BudgetRowEvidence:
    """One source row, immutable and attributable to an exact document revision."""

    tenant_id: UUID
    project_id: UUID
    document_id: UUID
    revision_id: UUID
    source_locator: str
    description: str
    quantity: Decimal
    unit: str
    unit_price: Decimal
    amount: Decimal
    currency: str
    tax_basis: str
    wbs_baseline_id: UUID | None
    wbs_node_id: UUID | None

    @property
    def identity(self) -> tuple[UUID, str]:
        """The replay-resistant identity within immutable source evidence."""
        return (self.revision_id, self.source_locator)


@dataclass(frozen=True)
class BudgetComparabilityAssessment:
    """Whether rows can proceed to a future contractual comparison input.

    ``READY_FOR_COMPARISON`` does not assess budget performance and must not be
    rendered as a coherence pass.  A separate approved comparison baseline is
    still required before any score or alert is produced.
    """

    state: BudgetAssessmentState
    reason: str | None
    amount: Decimal | None = None


def bind_verified_budget_row(
    *,
    document_revision: DocumentRevision,
    actor_tenant_id: UUID,
    source_revision_id: UUID,
    source_locator: str,
    verified_locators: Collection[str],
    description: str,
    quantity: Decimal,
    unit: str,
    unit_price: Decimal,
    amount: Decimal,
    currency: str,
    tax_basis: str,
    approved_wbs_scope: ApprovedWBSScope | None,
    wbs_node_id: UUID | None,
    existing_row_identities: Collection[tuple[UUID, str]],
) -> BudgetRowEvidence:
    """Build evidence only after source and WBS authority were independently read.

    The caller's tenant is checked against the revision rather than trusted as
    metadata.  ``verified_locators`` must be derived from the parsed immutable
    document revision; arbitrary client-supplied locators are rejected.
    """
    if actor_tenant_id != document_revision.tenant_id:
        raise InvalidBudgetRowEvidenceError("tenant does not own document revision")
    if source_revision_id != document_revision.revision_id:
        raise InvalidBudgetRowEvidenceError("source revision does not match document revision")
    if not source_locator or source_locator not in verified_locators:
        raise InvalidBudgetRowEvidenceError("source locator was not verified in document revision")
    if (document_revision.revision_id, source_locator) in existing_row_identities:
        raise DuplicateBudgetRowEvidenceError("budget row evidence already exists for revision locator")
    _require_nonempty("description", description)
    _require_nonempty("unit", unit)
    _require_nonempty("currency", currency)
    _require_nonempty("tax_basis", tax_basis)
    _require_nonnegative("quantity", quantity)
    _require_nonnegative("unit_price", unit_price)
    _require_nonnegative("amount", amount)

    baseline_id: UUID | None = None
    if wbs_node_id is not None:
        if approved_wbs_scope is None:
            raise UnapprovedWBSMappingError("WBS mapping requires an approved baseline")
        if (
            approved_wbs_scope.tenant_id != document_revision.tenant_id
            or approved_wbs_scope.project_id != document_revision.project_id
            or wbs_node_id not in approved_wbs_scope.node_ids
        ):
            raise UnapprovedWBSMappingError("WBS node is not in this revision's approved scope")
        baseline_id = approved_wbs_scope.baseline_id

    return BudgetRowEvidence(
        tenant_id=document_revision.tenant_id,
        project_id=document_revision.project_id,
        document_id=document_revision.document_id,
        revision_id=document_revision.revision_id,
        source_locator=source_locator,
        description=description,
        quantity=quantity,
        unit=unit,
        unit_price=unit_price,
        amount=amount,
        currency=currency,
        tax_basis=tax_basis,
        wbs_baseline_id=baseline_id,
        wbs_node_id=wbs_node_id,
    )


def assess_budget_comparability(
    rows: Collection[BudgetRowEvidence],
) -> BudgetComparabilityAssessment:
    """Expose only honest readiness; never invent a zero or passing budget score."""
    if not rows:
        return BudgetComparabilityAssessment(
            state=BudgetAssessmentState.NOT_ASSESSED,
            reason="no_verified_budget_rows",
        )

    lineages = {
        (row.tenant_id, row.project_id, row.document_id, row.revision_id) for row in rows
    }
    if len(lineages) != 1:
        return BudgetComparabilityAssessment(
            state=BudgetAssessmentState.NOT_ASSESSED,
            reason="mixed_budget_evidence_lineage",
        )

    semantics = {(row.currency, row.unit, row.tax_basis) for row in rows}
    if len(semantics) != 1:
        return BudgetComparabilityAssessment(
            state=BudgetAssessmentState.NOT_ASSESSED,
            reason="incompatible_budget_row_semantics",
        )

    return BudgetComparabilityAssessment(
        state=BudgetAssessmentState.READY_FOR_COMPARISON,
        reason=None,
    )


def _require_nonempty(name: str, value: str) -> None:
    if not value.strip():
        raise InvalidBudgetRowEvidenceError(f"{name} must not be empty")


def _require_nonnegative(name: str, value: Decimal) -> None:
    if not value.is_finite() or value < 0:
        raise InvalidBudgetRowEvidenceError(f"{name} must be a finite non-negative decimal")


__all__ = [
    "ApprovedWBSScope",
    "BudgetAssessmentState",
    "BudgetComparabilityAssessment",
    "BudgetRowEvidence",
    "BudgetRowEvidenceError",
    "DuplicateBudgetRowEvidenceError",
    "InvalidBudgetRowEvidenceError",
    "UnapprovedWBSMappingError",
    "assess_budget_comparability",
    "bind_verified_budget_row",
]
