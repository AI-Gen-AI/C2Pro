"""PQ-HITL-01: located source quotes cannot certify model interpretations."""

from uuid import uuid4

from src.analysis.domain.source_quote_verification import verify_source_quote


def test_unique_literal_quote_verified_only_against_explicit_revision() -> None:
    revision = uuid4()
    source = (
        "5.2 Defective work shall be rectified at Contractor's cost "
        "within fourteen (14) days."
    )
    outcome = verify_source_quote(
        source_revision_id=revision,
        source_text=source,
        quoted_text="Contractor's cost within fourteen (14) days",
        source_complete=True,
    )
    assert outcome.status == "VERIFIED_EXACT"
    assert outcome.revision_id == revision
    assert outcome.start_offset == source.index("Contractor's cost")
    assert outcome.end_offset is not None
    assert outcome.start_offset is not None
    assert outcome.end_offset > outcome.start_offset
    assert outcome.page is None


def test_invented_contractual_quote_never_certified_as_corruption() -> None:
    outcome = verify_source_quote(
        source_revision_id=uuid4(),
        source_text="Clause 5.2: fourteen (14) days at the Contractor's cost.",
        quoted_text="No agreed timeframe or cost allocation",
        source_complete=True,
    )
    assert outcome.status == "UNVERIFIED"
    assert outcome.start_offset is None
    assert outcome.page is None
    assert outcome.absence_proven is False


def test_missing_or_clipped_source_does_not_prove_absence() -> None:
    for source, complete in [(None, False), ("prefix text", False)]:
        outcome = verify_source_quote(
            source_revision_id=uuid4(),
            source_text=source,
            quoted_text="liquidated damages",
            source_complete=complete,
        )
        assert outcome.status in ("SOURCE_UNAVAILABLE", "UNVERIFIED")
        assert outcome.absence_proven is False


def test_duplicate_literal_quote_is_ambiguous_without_unique_locator() -> None:
    outcome = verify_source_quote(
        source_revision_id=uuid4(),
        source_text="Notice given. Notice given.",
        quoted_text="Notice given.",
        source_complete=True,
    )
    assert outcome.status == "AMBIGUOUS"
    assert outcome.start_offset is None


def test_empty_claim_and_valid_ordinary_terms_are_not_corruption() -> None:
    for quote in ("", "   "):
        outcome = verify_source_quote(
            source_revision_id=uuid4(),
            source_text="However, LD applies.",
            quoted_text=quote,
            source_complete=True,
        )
        assert outcome.status == "UNVERIFIED"

    outcome = verify_source_quote(
        source_revision_id=uuid4(),
        source_text="However, LD applies.",
        quoted_text="However, LD",
        source_complete=True,
    )
    assert outcome.status == "VERIFIED_EXACT"


def test_partial_source_coverage_is_preserved_even_for_a_located_quote() -> None:
    outcome = verify_source_quote(
        source_revision_id=uuid4(),
        source_text="Clause A",
        quoted_text="Clause A",
        source_complete=False,
    )
    assert outcome.status == "VERIFIED_EXACT"
    assert outcome.source_complete is False
