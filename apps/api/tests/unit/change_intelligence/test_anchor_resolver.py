"""Anchor resolver tests (ADR-016 / TASK-V3-016-03).

TS-UT-CI-ANCH-001

``clause_code`` is not identity evidence (PR-C1): a source number counts only
when it is read from the clause's own text.
"""

from __future__ import annotations

from uuid import uuid4

from src.documents.domain.models import Clause, ClauseType


def _clause(code: str, text: str) -> Clause:
    return Clause(
        id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        document_id=uuid4(),
        clause_code=code,
        clause_type=ClauseType.OTHER,
        title=None,
        full_text=text,
    )


def test_source_identifier_in_clause_text_match_has_full_confidence() -> None:
    from src.change_intelligence.application.anchor_resolver import resolve_clause_anchors

    old = _clause("AUTO-001", "5.2 Penalty cap is 10 percent.")
    new = _clause("AUTO-007", "5.2 Penalty cap is 15 percent.")

    result = resolve_clause_anchors([old], [new])

    assert len(result.matched) == 1
    match = result.matched[0]
    assert match.old is old
    assert match.new is new
    assert match.anchor == "5.2"
    assert match.basis == "source_identifier"
    assert match.match_confidence == 1.0
    assert match.needs_review is False
    assert result.unmatched_old == []
    assert result.unmatched_new == []


def test_identical_text_under_different_codes_is_paired_not_added_and_removed() -> None:
    from src.change_intelligence.application.anchor_resolver import resolve_clause_anchors

    old = _clause("5.2", "Penalty cap is limited to 10 percent of contract value.")
    new = _clause("6.1", "Penalty cap is limited to 10 percent of contract value.")

    result = resolve_clause_anchors([old], [new])

    assert len(result.matched) == 1
    assert result.matched[0].basis == "exact_content"
    assert result.matched[0].match_confidence == 1.0
    assert result.matched[0].needs_review is False
    assert result.unmatched_old == []
    assert result.unmatched_new == []


def test_genuinely_different_clauses_below_threshold_are_left_unmatched() -> None:
    from src.change_intelligence.application.anchor_resolver import resolve_clause_anchors

    old = _clause("5.2", "Penalty cap is limited to 10 percent.")
    new = _clause("8.4", "The contractor must submit monthly safety logs.")

    result = resolve_clause_anchors([old], [new], fuzzy_threshold=0.9)

    assert result.matched == []
    assert result.unmatched_old == [old]
    assert result.unmatched_new == [new]


def test_low_confidence_fuzzy_pair_is_flagged_for_review() -> None:
    from src.change_intelligence.application.anchor_resolver import resolve_clause_anchors

    old = _clause("5.2", "Penalty cap is limited to 10 percent of contract value.")
    new = _clause("6.1", "Penalty cap is capped at 15 percent of contract value.")

    result = resolve_clause_anchors([old], [new], fuzzy_threshold=0.8)

    assert len(result.matched) == 1
    assert result.matched[0].match_confidence < 0.9
    assert result.matched[0].needs_review is True


def test_shared_clause_code_does_not_pair_different_clauses() -> None:
    from src.change_intelligence.application.anchor_resolver import resolve_clause_anchors

    old_a = _clause("5.2", "A")
    old_b = _clause("5.2", "B")
    new_c = _clause("5.2", "C")

    result = resolve_clause_anchors([old_a, old_b], [new_c])

    assert result.matched == []
    assert result.unmatched_old == [old_a, old_b]
    assert result.unmatched_new == [new_c]


def test_shared_empty_clause_code_does_not_pair_different_clauses() -> None:
    from src.change_intelligence.application.anchor_resolver import resolve_clause_anchors

    old_a = _clause("", "A")
    old_b = _clause("", "B")
    new_c = _clause("", "C")

    result = resolve_clause_anchors([old_a, old_b], [new_c])

    assert result.matched == []
    assert result.unmatched_old == [old_a, old_b]
    assert result.unmatched_new == [new_c]


def test_ambiguous_similarity_is_left_unpaired_and_marked() -> None:
    from src.change_intelligence.application.anchor_resolver import resolve_clause_anchors

    old_a = _clause("AUTO-001", "The Contractor shall submit the monthly progress report.")
    old_b = _clause("AUTO-002", "The Contractor shall submit the monthly safety report.")
    new_c = _clause("AUTO-001", "The Contractor shall submit the monthly quality report.")

    result = resolve_clause_anchors([old_a, old_b], [new_c])

    assert result.matched == []
    assert result.ambiguous_old == [old_a, old_b]
    assert result.ambiguous_new == [new_c]


def test_source_label_is_read_from_clause_text() -> None:
    from src.change_intelligence.application.anchor_resolver import split_source_label

    assert split_source_label("Cláusula 4.2.- Plazo de ejecución") == ("clausula 4.2", "Plazo de ejecución")
    assert split_source_label("ARTICLE 17 Termination") == ("article 17", "Termination")
    assert split_source_label("Annex III.2 Technical scope") == ("annex iii.2", "Technical scope")
    assert split_source_label("PRIMERA.- Objeto del contrato") == ("primera", "Objeto del contrato")
    assert split_source_label("3.1.4 Payment terms") == ("3.1.4", "Payment terms")
    assert split_source_label("2. Price. The price is fixed.") == ("2", "Price. The price is fixed.")
    # A clause that merely starts with a quantity has no source number.
    assert split_source_label("30 days after notice the Employer may act.") == (
        None,
        "30 days after notice the Employer may act.",
    )
