"""Anchor resolver tests (ADR-016 / TASK-V3-016-03).

TS-UT-CI-ANCH-001
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


def test_exact_clause_code_match_has_full_confidence() -> None:
    from src.change_intelligence.application.anchor_resolver import resolve_clause_anchors

    old = _clause("5.2", "Penalty cap is 10 percent.")
    new = _clause("5.2", "Penalty cap is 15 percent.")

    result = resolve_clause_anchors([old], [new])

    assert len(result.matched) == 1
    match = result.matched[0]
    assert match.old is old
    assert match.new is new
    assert match.anchor == "5.2"
    assert match.match_confidence == 1.0
    assert match.needs_review is False
    assert result.unmatched_old == []
    assert result.unmatched_new == []


def test_renumbered_clause_is_fuzzy_paired_not_added_and_removed() -> None:
    from src.change_intelligence.application.anchor_resolver import resolve_clause_anchors

    old = _clause("5.2", "Penalty cap is limited to 10 percent of contract value.")
    new = _clause("6.1", "Penalty cap is limited to 10 percent of contract value.")

    result = resolve_clause_anchors([old], [new])

    assert len(result.matched) == 1
    assert result.matched[0].anchor == "5.2"
    assert result.matched[0].match_confidence >= 0.8
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


def test_duplicate_old_clause_code_is_not_silently_dropped_after_exact_match() -> None:
    from src.change_intelligence.application.anchor_resolver import resolve_clause_anchors

    old_a = _clause("5.2", "A")
    old_b = _clause("5.2", "B")
    new_c = _clause("5.2", "C")

    result = resolve_clause_anchors([old_a, old_b], [new_c])

    assert len(result.matched) == 1
    assert result.matched[0].old is old_a
    assert result.matched[0].new is new_c
    assert result.unmatched_old == [old_b]
    assert result.unmatched_new == []


def test_duplicate_empty_clause_code_is_not_silently_dropped_after_exact_match() -> None:
    from src.change_intelligence.application.anchor_resolver import resolve_clause_anchors

    old_a = _clause("", "A")
    old_b = _clause("", "B")
    new_c = _clause("", "C")

    result = resolve_clause_anchors([old_a, old_b], [new_c])

    assert len(result.matched) == 1
    assert result.matched[0].old is old_a
    assert result.matched[0].new is new_c
    assert result.unmatched_old == [old_b]
    assert result.unmatched_new == []
