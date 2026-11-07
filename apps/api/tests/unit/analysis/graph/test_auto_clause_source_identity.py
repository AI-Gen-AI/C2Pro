"""Regression: original EPC clause number must survive parser AUTO-* identity."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.analysis.adapters.graph.review_source_references import grounded_review_source_references


def _persisted_clause(*, tenant, project, document, revision, auto_code, original_text):
    return SimpleNamespace(
        id=uuid4(),
        tenant_id=tenant,
        project_id=project,
        document_id=document,
        revision_id=revision,
        clause_code=auto_code,
        full_text=original_text,
    )


def test_epc_8_2_original_prefix_uniquely_resolves_auto_007_clause_id():
    tenant, project, document, revision = [uuid4() for _ in range(4)]
    clause = _persisted_clause(
        tenant=tenant, project=project, document=document, revision=revision,
        auto_code="AUTO-007",
        original_text=(
            "8.2 The contractual completion deadline is 2027-06-30. "
            "Contractor shall achieve completion of all works by 2027-06-30."
        ),
    )
    refs = grounded_review_source_references(
        tenant_id=tenant, project_id=project, document_id=document,
        revision_id=revision, clause_codes={"8.2"}, persisted_clauses=[clause],
    )
    # Original source prefix and exact tenant/revision suffice to locate ClauseORM
    # UUID. They do NOT independently validate an AI-generated risk narrative.
    assert refs == [{
        "document_id": str(document),
        "revision_id": str(revision),
        "clause_id": str(clause.id),
        "clause_code": "8.2",
    }]


def test_epc_8_3_original_prefix_uniquely_resolves_auto_clause_id():
    tenant, project, document, revision = [uuid4() for _ in range(4)]
    clause = _persisted_clause(
        tenant=tenant, project=project, document=document, revision=revision,
        auto_code="AUTO-009", original_text="8.3 Contractor may request an extension.",
    )
    refs = grounded_review_source_references(
        tenant_id=tenant, project_id=project, document_id=document,
        revision_id=revision, clause_codes={"8.3"}, persisted_clauses=[clause],
    )
    assert refs[0]["clause_id"] == str(clause.id)
    assert refs[0]["clause_code"] == "8.3"


def test_number_prefix_8_21_does_not_match_8_2():
    tenant, project, document, revision = [uuid4() for _ in range(4)]
    clause = _persisted_clause(
        tenant=tenant, project=project, document=document, revision=revision,
        auto_code="AUTO-007", original_text="8.21 Similar but different clause",
    )
    refs = grounded_review_source_references(
        tenant_id=tenant, project_id=project, document_id=document,
        revision_id=revision, clause_codes={"8.2"}, persisted_clauses=[clause],
    )
    assert refs == []


@pytest.mark.parametrize("malformed_prefix", ["8.2(a)", "8.2A", "8.21abc"])
def test_malformed_numbered_prefix_never_backtracks_to_parent_clause_code(malformed_prefix):
    tenant, project, document, revision = [uuid4() for _ in range(4)]
    clause = _persisted_clause(
        tenant=tenant, project=project, document=document, revision=revision,
        auto_code="AUTO-007", original_text=f"{malformed_prefix} Not a clause heading",
    )
    assert grounded_review_source_references(
        tenant_id=tenant, project_id=project, document_id=document,
        revision_id=revision, clause_codes={"8"}, persisted_clauses=[clause],
    ) == []


@pytest.mark.parametrize("separator", [" ", ": "])
def test_valid_numbered_heading_with_space_or_colon_resolves(separator):
    tenant, project, document, revision = [uuid4() for _ in range(4)]
    clause = _persisted_clause(
        tenant=tenant, project=project, document=document, revision=revision,
        auto_code="AUTO-007", original_text=f"8.2{separator}The contractual completion deadline",
    )
    refs = grounded_review_source_references(
        tenant_id=tenant, project_id=project, document_id=document,
        revision_id=revision, clause_codes={"8.2"}, persisted_clauses=[clause],
    )
    assert refs[0]["clause_id"] == str(clause.id)


def test_mismatched_explicit_code_conflicts_with_matching_auto_heading():
    tenant, project, document, revision = [uuid4() for _ in range(4)]
    mismatched_explicit_clause = _persisted_clause(
        tenant=tenant, project=project, document=document, revision=revision,
        auto_code="8.3", original_text="8.2 Original contractual clause",
    )
    auto_clause = _persisted_clause(
        tenant=tenant, project=project, document=document, revision=revision,
        auto_code="AUTO-007", original_text="8.2 Duplicate parser clause",
    )
    assert grounded_review_source_references(
        tenant_id=tenant, project_id=project, document_id=document,
        revision_id=revision, clause_codes={"8.2"},
        persisted_clauses=[mismatched_explicit_clause, auto_clause],
    ) == []


def test_explicit_code_without_matching_source_heading_is_not_verified():
    tenant, project, document, revision = [uuid4() for _ in range(4)]
    clause = _persisted_clause(
        tenant=tenant, project=project, document=document, revision=revision,
        auto_code="8.2", original_text="Time for Completion. Contractor shall proceed.",
    )
    # A stored numeric code alone cannot substitute for missing source identity.
    assert grounded_review_source_references(
        tenant_id=tenant, project_id=project, document_id=document,
        revision_id=revision, clause_codes={"8.2"}, persisted_clauses=[clause],
    ) == []


def test_whitespace_around_section_symbol_preserves_numeric_heading_identity():
    tenant, project, document, revision = [uuid4() for _ in range(4)]
    clause = _persisted_clause(
        tenant=tenant, project=project, document=document, revision=revision,
        auto_code="AUTO-007", original_text="  §  8.2 The contractual completion deadline",
    )
    refs = grounded_review_source_references(
        tenant_id=tenant, project_id=project, document_id=document,
        revision_id=revision, clause_codes={"8.2"}, persisted_clauses=[clause],
    )
    assert refs[0]["clause_id"] == str(clause.id)


def test_two_auto_clauses_with_same_original_number_remain_ambiguous():
    tenant, project, document, revision = [uuid4() for _ in range(4)]
    clauses = [
        _persisted_clause(
            tenant=tenant, project=project, document=document, revision=revision,
            auto_code=code, original_text="8.2 Repeated conflicting clause",
        )
        for code in ["AUTO-007", "AUTO-008"]
    ]
    refs = grounded_review_source_references(
        tenant_id=tenant, project_id=project, document_id=document,
        revision_id=revision, clause_codes={"8.2"}, persisted_clauses=clauses,
    )
    assert refs == []


def test_explicit_and_auto_clauses_with_same_original_number_remain_ambiguous():
    tenant, project, document, revision = [uuid4() for _ in range(4)]
    explicit_clause = _persisted_clause(
        tenant=tenant, project=project, document=document, revision=revision,
        auto_code="8.2", original_text="8.2 Actual contractual clause",
    )
    auto_clause = _persisted_clause(
        tenant=tenant, project=project, document=document, revision=revision,
        auto_code="AUTO-007", original_text="8.2 Duplicate parser clause",
    )
    assert grounded_review_source_references(
        tenant_id=tenant, project_id=project, document_id=document,
        revision_id=revision, clause_codes={"8.2"},
        persisted_clauses=[explicit_clause, auto_clause],
    ) == []


def test_number_only_inside_persisted_paragraph_is_not_a_clause_heading():
    tenant, project, document, revision = [uuid4() for _ in range(4)]
    clause = _persisted_clause(
        tenant=tenant, project=project, document=document, revision=revision,
        auto_code="AUTO-007",
        original_text="The deadline in section 8.2 is commercially significant.",
    )
    assert grounded_review_source_references(
        tenant_id=tenant, project_id=project, document_id=document,
        revision_id=revision, clause_codes={"8.2"}, persisted_clauses=[clause],
    ) == []


def test_explicit_code_with_conflicting_persisted_heading_is_not_genuine():
    tenant, project, document, revision = [uuid4() for _ in range(4)]
    clause = _persisted_clause(
        tenant=tenant, project=project, document=document, revision=revision,
        auto_code="8.2", original_text="8.3 Different original clause heading",
    )
    assert grounded_review_source_references(
        tenant_id=tenant, project_id=project, document_id=document,
        revision_id=revision, clause_codes={"8.2"}, persisted_clauses=[clause],
    ) == []


def test_auto_clause_without_original_text_is_not_a_locator():
    tenant, project, document, revision = [uuid4() for _ in range(4)]
    clause = _persisted_clause(
        tenant=tenant, project=project, document=document, revision=revision,
        auto_code="AUTO-007", original_text=None,
    )
    assert grounded_review_source_references(
        tenant_id=tenant, project_id=project, document_id=document,
        revision_id=revision, clause_codes={"8.2"}, persisted_clauses=[clause],
    ) == []


def test_auto_clause_from_other_revision_or_tenant_never_binds():
    tenant, project, document, revision = [uuid4() for _ in range(4)]
    clause = _persisted_clause(
        tenant=uuid4(), project=project, document=document, revision=revision,
        auto_code="AUTO-007", original_text="8.2 Original wording",
    )
    refs = grounded_review_source_references(
        tenant_id=tenant, project_id=project, document_id=document,
        revision_id=revision, clause_codes={"8.2"}, persisted_clauses=[clause],
    )
    assert refs == []

    stale_revision_clause = _persisted_clause(
        tenant=tenant, project=project, document=document, revision=uuid4(),
        auto_code="AUTO-008", original_text="8.2 Original wording",
    )
    assert grounded_review_source_references(
        tenant_id=tenant, project_id=project, document_id=document,
        revision_id=revision, clause_codes={"8.2"}, persisted_clauses=[stale_revision_clause],
    ) == []
