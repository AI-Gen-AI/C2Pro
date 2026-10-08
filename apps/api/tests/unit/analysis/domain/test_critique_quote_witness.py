"""PQ-HITL-01: quoted source snippets must be independently addressable."""

from src.analysis.domain.critique_quote_witness import QuoteWitnessStatus, verify_source_quote

SOURCE = (
    "Clause 5.2: Defective work shall be rectified at the Contractor's "
    "cost within fourteen (14) days of written notice."
)


def test_exact_quote_is_located_without_asserting_claim_is_true() -> None:
    result = verify_source_quote(
        source_text=SOURCE,
        quote="Contractor's cost within fourteen (14) days",
    )
    assert result.status is QuoteWitnessStatus.LOCATED
    assert result.char_start is not None
    assert SOURCE[result.char_start:result.char_end] == result.located_text
    assert result.claim_verified is False


def test_absent_quote_has_no_fabricated_location() -> None:
    result = verify_source_quote(source_text=SOURCE, quote="within thirty (30) days")
    assert result.status is QuoteWitnessStatus.UNRESOLVED
    assert result.char_start is None
    assert result.char_end is None
    assert result.located_text is None


def test_whitespace_variation_remains_locatable_without_changing_content() -> None:
    source = "The Contractor shall\n  rectify defects within fourteen (14) days."
    result = verify_source_quote(source_text=source, quote="Contractor shall rectify defects")
    assert result.status is QuoteWitnessStatus.LOCATED
    assert result.located_text == "Contractor shall\n  rectify defects"


def test_partial_excerpt_cannot_establish_absence_of_other_provisions() -> None:
    result = verify_source_quote(
        source_text="Clause 1.1 covers scope.",
        quote="Clause 6.3 termination",
        source_complete=False,
    )
    assert result.status is QuoteWitnessStatus.SOURCE_PARTIAL_UNRESOLVED
    assert result.claim_verified is False


def test_unavailable_source_or_blank_quote_fails_closed() -> None:
    assert verify_source_quote(None, "Clause 5.2").status is QuoteWitnessStatus.SOURCE_UNAVAILABLE
    assert verify_source_quote(SOURCE, "   ").status is QuoteWitnessStatus.UNRESOLVED


def test_ordinary_abbreviations_and_disclosure_words_are_not_auto_flagged() -> None:
    source = "However, the Contractor shall pay LD under clause 9. Conversely, cap applies."
    for word in ("However", "LD", "Conversely"):
        result = verify_source_quote(source, word)
        assert result.status is QuoteWitnessStatus.LOCATED
        assert result.claim_verified is False


def test_quote_outside_bounded_excerpt_does_not_get_fabricated_witness() -> None:
    content = "x" * 17000 + "Clause 5.2 Contractor's cost."
    result = verify_source_quote(
        content[:16000],
        "Clause 5.2 Contractor's cost",
        source_complete=False,
    )
    assert result.status is QuoteWitnessStatus.SOURCE_PARTIAL_UNRESOLVED
