"""PC-3: revision-bound structured budget-row evidence contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from src.analysis.domain.budget_row_evidence import (
    ApprovedWBSScope,
    BudgetAssessmentState,
    DuplicateBudgetRowEvidenceError,
    InvalidBudgetRowEvidenceError,
    UnapprovedWBSMappingError,
    assess_budget_comparability,
    bind_verified_budget_row,
)
from src.coherence.domain.budget_line_availability import (
    structured_budget_assessment_from_rows,
)
from src.temporal.domain.document_revision import DocumentRevision

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
PROJECT_ID = UUID("22222222-2222-2222-2222-222222222222")
DOCUMENT_ID = UUID("33333333-3333-3333-3333-333333333333")
REVISION_ID = UUID("44444444-4444-4444-4444-444444444444")
BASELINE_ID = UUID("55555555-5555-5555-5555-555555555555")
WBS_NODE_ID = UUID("66666666-6666-6666-6666-666666666666")
NOW = datetime(2026, 10, 17, tzinfo=UTC)
LOCATOR = "sheet=Budget;row=12"


def _revision(*, tenant_id: UUID = TENANT_ID) -> DocumentRevision:
    return DocumentRevision(
        revision_id=REVISION_ID,
        document_id=DOCUMENT_ID,
        project_id=PROJECT_ID,
        tenant_id=tenant_id,
        rev_no=3,
        blob_hash="a" * 64,
        blob_key="revisions/budget-v3.xlsx",
        valid_from=NOW,
        created_at=NOW,
    )


def _approved_scope() -> ApprovedWBSScope:
    return ApprovedWBSScope(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        baseline_id=BASELINE_ID,
        node_ids=frozenset({WBS_NODE_ID}),
    )


def _bind(**overrides: object):
    values: dict[str, object] = {
        "document_revision": _revision(),
        "actor_tenant_id": TENANT_ID,
        "source_revision_id": REVISION_ID,
        "source_locator": LOCATOR,
        "verified_locators": frozenset({LOCATOR}),
        "description": "Concrete foundation",
        "quantity": Decimal("12"),
        "unit": "m3",
        "unit_price": Decimal("100.00"),
        "amount": Decimal("1200.00"),
        "currency": "EUR",
        "tax_basis": "NET",
        "approved_wbs_scope": _approved_scope(),
        "wbs_node_id": WBS_NODE_ID,
        "existing_row_identities": frozenset(),
    }
    values.update(overrides)
    return bind_verified_budget_row(**values)  # type: ignore[arg-type]


def test_binds_verified_row_to_exact_revision_and_approved_wbs_baseline() -> None:
    """Dropping revision or baseline binding would permit evidence substitution."""
    row = _bind()

    assert row.tenant_id == TENANT_ID
    assert row.project_id == PROJECT_ID
    assert row.document_id == DOCUMENT_ID
    assert row.revision_id == REVISION_ID
    assert row.source_locator == LOCATOR
    assert row.wbs_baseline_id == BASELINE_ID
    assert row.wbs_node_id == WBS_NODE_ID
    assert row.amount == Decimal("1200.00")


def test_rejects_row_claiming_a_different_document_revision() -> None:
    """A row from another revision cannot become evidence for this revision."""
    with pytest.raises(InvalidBudgetRowEvidenceError, match="revision"):
        _bind(source_revision_id=uuid4())


def test_rejects_foreign_tenant_even_when_locator_and_revision_match() -> None:
    """Tenant substitution must fail before a row is constructed."""
    with pytest.raises(InvalidBudgetRowEvidenceError, match="tenant"):
        _bind(actor_tenant_id=uuid4())


def test_rejects_duplicate_revision_locator_identity() -> None:
    """Replaying the same source row cannot create duplicate evidence."""
    with pytest.raises(DuplicateBudgetRowEvidenceError):
        _bind(existing_row_identities=frozenset({(REVISION_ID, LOCATOR)}))


def test_rejects_unverified_source_locator() -> None:
    """A locator must be observed in the parsed revision, not merely supplied."""
    with pytest.raises(InvalidBudgetRowEvidenceError, match="locator"):
        _bind(verified_locators=frozenset({"sheet=Budget;row=13"}))


def test_rejects_wbs_mapping_without_an_approved_baseline() -> None:
    """A WBS node ID alone is never approval authority."""
    with pytest.raises(UnapprovedWBSMappingError):
        _bind(approved_wbs_scope=None)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("currency", "USD"),
        ("unit", "kg"),
        ("tax_basis", "GROSS"),
    ],
)
def test_incompatible_rows_are_not_assessed_as_zero_or_green(
    field: str, replacement: str
) -> None:
    """Incomparable money semantics leave BUDGET honestly not assessed."""
    first = _bind()
    second = _bind(
        source_locator="sheet=Budget;row=14",
        verified_locators=frozenset({LOCATOR, "sheet=Budget;row=14"}),
        **{field: replacement},
    )

    assessment = assess_budget_comparability((first, second))

    assert assessment.state is BudgetAssessmentState.NOT_ASSESSED
    assert assessment.amount is None
    assert assessment.reason == "incompatible_budget_row_semantics"

    coherence_assessment, coherence_reasons = structured_budget_assessment_from_rows(
        (first, second)
    )
    assert coherence_assessment == {"BUDGET": False}
    assert coherence_reasons == {"BUDGET": "incompatible_budget_row_semantics"}


def test_verified_rows_without_a_contractual_comparison_stay_not_assessed() -> None:
    """A source-backed row alone cannot turn the coherence budget category green."""
    assessment, reasons = structured_budget_assessment_from_rows((_bind(),))

    assert assessment == {"BUDGET": False}
    assert reasons == {"BUDGET": "approved_budget_comparison_missing"}


def test_rows_from_different_revisions_are_not_comparable() -> None:
    """A later upload cannot be mixed with its superseded revision in Coherence."""
    later_revision_id = uuid4()
    later_locator = "sheet=Budget;row=12"
    later_revision = _revision().model_copy(update={"revision_id": later_revision_id})
    first = _bind()
    second = _bind(
        document_revision=later_revision,
        source_revision_id=later_revision_id,
        source_locator=later_locator,
        verified_locators=frozenset({later_locator}),
    )

    assessment = assess_budget_comparability((first, second))

    assert assessment.state is BudgetAssessmentState.NOT_ASSESSED
    assert assessment.reason == "mixed_budget_evidence_lineage"
