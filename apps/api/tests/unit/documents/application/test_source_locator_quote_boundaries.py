"""PQ-HITL-06/#942: verbatim quotes and term conflicts must not pass on fragments.

Review round after #1035. A quote was certified VERBATIM when it only matched
inside a longer word ("4 days" inside "14 days", "contractor" inside
"Subcontractor"), and duration parsing read only the tail of a number
("1,000" / "2,000" both as "000"; "1.5" as "5") or ignored hours, so a
contradictory claim produced no conflict. Identical durations written as
"14 (catorce) días" or in decomposed Unicode were reported as conflicts.

Paraphrased units (two weeks vs 14 days) stay flagged for review by design.
Offline synthetic unit tests with a fake repository.
"""

from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.documents.application.services.source_locator import SourceLocator
from src.documents.domain.models import Clause, ClauseType


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


def _locator(clause: Clause) -> SourceLocator:
    repository = AsyncMock()

    async def by_code(**kwargs: object) -> Clause | None:
        return clause if kwargs["revision_id"] == clause.revision_id else None

    repository.get_clause_by_document_and_code.side_effect = by_code
    repository.list_revision_clauses.return_value = []
    repository.list_current_clauses.return_value = []
    return SourceLocator(repository)


async def _locate(query: str, source: str):  # noqa: ANN202
    tenant_id, document_id, revision_id = uuid4(), uuid4(), uuid4()
    clause = _clause(
        tenant_id=tenant_id, document_id=document_id, revision_id=revision_id, text=source
    )
    location = await _locator(clause).locate_evidence(
        query, document_id, tenant_id, revision_id=revision_id
    )
    assert location is not None
    return location


@pytest.mark.parametrize(
    ("quote", "source"),
    [
        ('"ability to terminate the contract"', "There is no inability to terminate the contract."),
        ('"payment is due within"', "Prepayment is due within ten days."),
        ('"4 days after receipt"', "Notice within 14 days after receipt."),
        ('"contractor shall bear"', "The Subcontractor shall bear the cost."),
        ('"(a) The Contractor shall pay"', "5.2(a) The Contractor shall payout."),
    ],
)
async def test_quote_inside_a_longer_word_is_not_verbatim(quote: str, source: str) -> None:
    location = await _locate(f"Clause 5.2: {quote}", source)

    assert location.quote_status == "NOT_VERBATIM"


@pytest.mark.parametrize(
    ("quote", "source"),
    [
        ('"contractor shall bear"', "The Contractor shall bear the cost."),
        ('"the Contractor\'s cost"', "at the Contractor's cost."),
        ('"14 days"', "Notice within 14 days."),
        ('"(a) The Contractor shall pay"', "5.2(a) The Contractor shall pay the cost."),
        ('"Contractor shall pay (b)"', "The Contractor shall pay (b)2 instalments."),
    ],
)
async def test_whole_word_quote_remains_verbatim(quote: str, source: str) -> None:
    location = await _locate(f"Clause 5.2: {quote}", source)

    assert location.quote_status == "VERBATIM"


@pytest.mark.parametrize(
    ("claim", "source"),
    [
        ("plazo de 14 días", "en un plazo de 14 (catorce) días"),
        ("within 14 days", "within 14 (fourteen) days"),
        ("en 30 días", "en 30 días"),
        ("en 30 días", "en 30 días"),
        ("within 1,000 days", "within 1,000 days"),
        ("within 24 hours", "within twenty-four (24) hours"),
    ],
)
async def test_identical_durations_are_not_conflicts(claim: str, source: str) -> None:
    location = await _locate(f"Clause 5.2: {claim}", source)

    assert location.term_conflicts == []
    assert location.claim_support == "UNVERIFIED"


@pytest.mark.parametrize(
    ("claim", "source"),
    [
        ("within 1,000 days", "within 2,000 days"),
        ("en 1.000 días", "en 2.000 días"),
        ("within 1.5 months", "within 5 months"),
        ("within 48 hours", "within 24 hours"),
        ("en 48 horas", "en 24 horas"),
    ],
)
async def test_different_durations_are_conflicts(claim: str, source: str) -> None:
    location = await _locate(f"Clause 5.2: {claim}", source)

    assert any(c.startswith("duration_not_in_source:") for c in location.term_conflicts)
    assert location.claim_support == "CONFLICT_DETECTED"


@pytest.mark.parametrize(
    ("claim", "party"),
    [
        ("los empleadores asumen el coste", "employer"),
        ("los ingenieros aprueban", "engineer"),
        ("los clientes pagan", "client"),
    ],
)
async def test_spanish_plural_party_is_detected(claim: str, party: str) -> None:
    location = await _locate(f"Clause 5.2: {claim}", "El Contratista asumirá el coste.")

    assert f"party_not_in_source:{party}" in location.term_conflicts


@pytest.mark.parametrize(
    "reference",
    ["Subclause 5.2", "Subcláusula 5.2", "Sub-Clause 5.2", "Subcláusula 5.2", "Cláusula 5.2"],
)
async def test_subclause_reference_uses_the_clause_code_path(reference: str) -> None:
    location = await _locate(reference, "5.2 The Contractor shall bear the cost.")

    assert location.match_method == "clause_code"
