"""PQ-HITL-06/#942 + #713: finding the cited clause is not proof the claim is true.

A clause-code hit used to return ``similarity_score=100`` whatever the claim said,
and a fuzzy match accepted a claim with the wrong deadline (``30 days`` against
``fourteen (14) days`` scores ~92 >= 85). The locator must report, separately:
which revision-bound clause it found, whether the quoted text appears verbatim,
and deterministic term conflicts (durations, named parties). It never reports a
claim as supported and never invents a page or bounding box.

Offline synthetic unit tests with a fake repository; not proof of PDF rendering,
real RLS or end-user navigation.
"""

from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.documents.application.services.source_locator import SourceLocator
from src.documents.domain.models import Clause, ClauseType

SOURCE_A = (
    "5.2 The Contractor shall bear the cost of remedial works within fourteen (14) "
    "days after receipt of written notice from the Engineer."
)
SOURCE_B = (
    "5.2 The Contractor shall bear the cost of remedial works within 30 days after "
    "receipt of written notice from the Engineer."
)


def _clause(*, tenant_id: UUID, document_id: UUID, revision_id: UUID, text: str) -> Clause:
    return Clause(
        id=uuid4(),
        project_id=uuid4(),
        tenant_id=tenant_id,
        document_id=document_id,
        revision_id=revision_id,
        clause_code="5.2",
        clause_type=ClauseType.QUALITY,
        title="Remedial works",
        full_text=text,
    )


def _code_repository(*clauses: Clause) -> AsyncMock:
    by_revision = {c.revision_id: c for c in clauses}
    repository = AsyncMock()

    async def by_code(**kwargs: object) -> Clause | None:
        return by_revision.get(kwargs["revision_id"])

    repository.get_clause_by_document_and_code.side_effect = by_code
    repository.list_revision_clauses.return_value = []
    repository.list_current_clauses.return_value = []
    return repository


@pytest.fixture
def ids() -> tuple[UUID, UUID, UUID, UUID]:
    return uuid4(), uuid4(), uuid4(), uuid4()


def _assert_no_invented_geometry(location) -> None:  # noqa: ANN001
    assert location.page_number is None
    assert location.bbox is None


async def test_bare_reference_finds_revision_bound_clause_without_claiming_support(ids) -> None:
    tenant_id, document_id, revision_a, _ = ids
    clause = _clause(
        tenant_id=tenant_id, document_id=document_id, revision_id=revision_a, text=SOURCE_A
    )
    locator = SourceLocator(_code_repository(clause))

    location = await locator.locate_evidence(
        "Clause 5.2", document_id, tenant_id, revision_id=revision_a
    )

    assert location is not None
    assert location.clause_id == clause.id
    assert location.clause_code == "5.2"
    assert location.revision_id == revision_a
    assert location.match_method == "clause_code"
    assert location.quote_status == "NO_QUOTE"
    assert location.term_conflicts == []
    assert location.claim_support == "UNVERIFIED"
    _assert_no_invented_geometry(location)


async def test_verbatim_quote_is_verified_but_claim_stays_unverified(ids) -> None:
    tenant_id, document_id, revision_a, _ = ids
    clause = _clause(
        tenant_id=tenant_id, document_id=document_id, revision_id=revision_a, text=SOURCE_A
    )
    locator = SourceLocator(_code_repository(clause))

    location = await locator.locate_evidence(
        'Clause 5.2: "the contractor shall bear the cost of remedial works within  '
        'fourteen (14) days"',
        document_id,
        tenant_id,
        revision_id=revision_a,
    )

    assert location is not None
    assert location.quote_status == "VERBATIM"
    assert location.term_conflicts == []
    assert location.claim_support == "UNVERIFIED"
    _assert_no_invented_geometry(location)


async def test_wrong_deadline_citing_correct_clause_is_flagged(ids) -> None:
    tenant_id, document_id, revision_a, _ = ids
    clause = _clause(
        tenant_id=tenant_id, document_id=document_id, revision_id=revision_a, text=SOURCE_A
    )
    locator = SourceLocator(_code_repository(clause))

    location = await locator.locate_evidence(
        "Clause 5.2 requires the Contractor to bear the cost within 30 days",
        document_id,
        tenant_id,
        revision_id=revision_a,
    )

    assert location is not None
    assert location.clause_id == clause.id
    assert location.quote_status == "NOT_VERBATIM"
    assert "duration_not_in_source:30 day" in location.term_conflicts
    assert location.claim_support == "CONFLICT_DETECTED"


async def test_wrong_party_citing_correct_clause_is_flagged(ids) -> None:
    tenant_id, document_id, revision_a, _ = ids
    clause = _clause(
        tenant_id=tenant_id, document_id=document_id, revision_id=revision_a, text=SOURCE_A
    )
    locator = SourceLocator(_code_repository(clause))

    location = await locator.locate_evidence(
        "Under Clause 5.2 the Employer bears the cost of remedial works",
        document_id,
        tenant_id,
        revision_id=revision_a,
    )

    assert location is not None
    assert "party_not_in_source:employer" in location.term_conflicts
    assert location.claim_support == "CONFLICT_DETECTED"


async def test_same_claim_is_judged_against_the_selected_revision_only(ids) -> None:
    tenant_id, document_id, revision_a, revision_b = ids
    a = _clause(tenant_id=tenant_id, document_id=document_id, revision_id=revision_a, text=SOURCE_A)
    b = _clause(tenant_id=tenant_id, document_id=document_id, revision_id=revision_b, text=SOURCE_B)
    locator = SourceLocator(_code_repository(a, b))
    claim = "Clause 5.2: the Contractor bears the cost within 30 days"

    on_a = await locator.locate_evidence(claim, document_id, tenant_id, revision_id=revision_a)
    on_b = await locator.locate_evidence(claim, document_id, tenant_id, revision_id=revision_b)

    assert on_a is not None and on_b is not None
    assert (on_a.revision_id, on_a.clause_id) == (revision_a, a.id)
    assert (on_b.revision_id, on_b.clause_id) == (revision_b, b.id)
    assert on_a.claim_support == "CONFLICT_DETECTED"
    assert on_b.term_conflicts == []
    assert on_b.claim_support == "UNVERIFIED"


async def test_fuzzy_match_of_contradictory_claim_is_not_reported_as_verbatim(ids) -> None:
    tenant_id, document_id, revision_a, _ = ids
    clause = _clause(
        tenant_id=tenant_id, document_id=document_id, revision_id=revision_a, text=SOURCE_A
    )
    repository = _code_repository()
    repository.list_revision_clauses.return_value = [clause]
    locator = SourceLocator(repository)

    location = await locator.locate_evidence(
        "The Contractor shall bear the cost of remedial works within 30 days",
        document_id,
        tenant_id,
        revision_id=revision_a,
    )

    assert location is not None
    assert location.match_method == "text_similarity"
    assert location.clause_id == clause.id
    assert location.revision_id == revision_a
    assert location.quote_status == "NOT_VERBATIM"
    assert "duration_not_in_source:30 day" in location.term_conflicts
    assert location.claim_support == "CONFLICT_DETECTED"
    _assert_no_invented_geometry(location)


async def test_section_sign_reference_uses_the_clause_code_path(ids) -> None:
    tenant_id, document_id, revision_a, _ = ids
    clause = _clause(
        tenant_id=tenant_id, document_id=document_id, revision_id=revision_a, text=SOURCE_A
    )
    repository = _code_repository(clause)
    locator = SourceLocator(repository)

    location = await locator.locate_evidence("§5.2", document_id, tenant_id, revision_id=revision_a)

    assert location is not None
    assert location.match_method == "clause_code"
    kwargs = repository.get_clause_by_document_and_code.await_args.kwargs
    assert kwargs == {
        "tenant_id": tenant_id,
        "document_id": document_id,
        "clause_code": "5.2",
        "revision_id": revision_a,
    }


@pytest.mark.parametrize(
    ("claim", "source"),
    [
        ("Clause 5.2: costs are borne within 14 days", SOURCE_A),
        ("Clause 5.2: costs are borne within fourteen days", SOURCE_B.replace("30", "14")),
    ],
)
async def test_number_words_and_digits_are_the_same_duration(ids, claim: str, source: str) -> None:
    tenant_id, document_id, revision_a, _ = ids
    clause = _clause(
        tenant_id=tenant_id, document_id=document_id, revision_id=revision_a, text=source
    )
    locator = SourceLocator(_code_repository(clause))

    location = await locator.locate_evidence(claim, document_id, tenant_id, revision_id=revision_a)

    assert location is not None
    assert location.term_conflicts == []


async def test_spanish_claim_with_wrong_deadline_is_flagged(ids) -> None:
    tenant_id, document_id, revision_a, _ = ids
    clause = _clause(
        tenant_id=tenant_id,
        document_id=document_id,
        revision_id=revision_a,
        text="5.2 El Contratista asumirá el coste en un plazo de catorce (14) días.",
    )
    locator = SourceLocator(_code_repository(clause))

    location = await locator.locate_evidence(
        "Cláusula 5.2: el Contratista asume el coste en un plazo de 30 días",
        document_id,
        tenant_id,
        revision_id=revision_a,
    )

    assert location is not None
    assert "duration_not_in_source:30 day" in location.term_conflicts
    assert location.claim_support == "CONFLICT_DETECTED"
