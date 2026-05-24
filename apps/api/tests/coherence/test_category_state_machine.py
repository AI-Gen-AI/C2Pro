"""
Tests for the deterministic Category State Machine (ADR-009 §7-§8).

Refers to Suite ID: TS-UD-COH-V2-SM-001.
"""
from __future__ import annotations

import pytest

from src.coherence.application.dtos.coherence_v2_dtos import CategoryStatus
from src.coherence.domain.category_state_machine import (
    CategoryStateMachine,
    InvalidTransitionError,
)


@pytest.mark.unit
def test_pending_to_insufficient_on_low_evidence() -> None:
    nxt = CategoryStateMachine.transition(
        CategoryStatus.PENDING_DOCUMENTS, "evidence_below_threshold"
    )
    assert nxt is CategoryStatus.INSUFFICIENT_EVIDENCE


@pytest.mark.unit
def test_insufficient_to_scored_on_threshold_met() -> None:
    nxt = CategoryStateMachine.transition(
        CategoryStatus.INSUFFICIENT_EVIDENCE, "evidence_meets_threshold"
    )
    assert nxt is CategoryStatus.SCORED


@pytest.mark.unit
def test_scored_to_conflicting_on_conflict() -> None:
    nxt = CategoryStateMachine.transition(
        CategoryStatus.SCORED, "conflict_detected"
    )
    assert nxt is CategoryStatus.CONFLICTING_EVIDENCE


@pytest.mark.unit
def test_scored_to_insufficient_only_on_docs_deleted() -> None:
    nxt = CategoryStateMachine.transition(
        CategoryStatus.SCORED, "docs_deleted"
    )
    assert nxt is CategoryStatus.INSUFFICIENT_EVIDENCE


@pytest.mark.unit
def test_processing_error_is_terminal_except_reset() -> None:
    with pytest.raises(InvalidTransitionError):
        CategoryStateMachine.transition(
            CategoryStatus.PROCESSING_ERROR, "evidence_meets_threshold"
        )
    assert (
        CategoryStateMachine.transition(CategoryStatus.PROCESSING_ERROR, "reset")
        is CategoryStatus.PENDING_DOCUMENTS
    )


@pytest.mark.unit
def test_not_applicable_short_circuits_events() -> None:
    # Only reset/marked_na should be valid; all others raise.
    for event in [
        "evidence_meets_threshold",
        "evidence_below_threshold",
        "conflict_detected",
        "docs_uploaded",
        "engine_error",
    ]:
        with pytest.raises(InvalidTransitionError):
            CategoryStateMachine.transition(CategoryStatus.NOT_APPLICABLE, event)


@pytest.mark.unit
def test_any_state_transitions_to_processing_error_on_engine_error() -> None:
    for state in (
        CategoryStatus.PENDING_DOCUMENTS,
        CategoryStatus.INSUFFICIENT_EVIDENCE,
        CategoryStatus.SCORED,
        CategoryStatus.CONFLICTING_EVIDENCE,
    ):
        assert (
            CategoryStateMachine.transition(state, "engine_error")
            is CategoryStatus.PROCESSING_ERROR
        )


@pytest.mark.unit
def test_disallowed_transition_raises_invalid_transition_error() -> None:
    with pytest.raises(InvalidTransitionError):
        CategoryStateMachine.transition(
            CategoryStatus.PENDING_DOCUMENTS, "conflict_detected"
        )


@pytest.mark.unit
def test_assert_valid_raises_on_unreachable_pair() -> None:
    with pytest.raises(InvalidTransitionError):
        CategoryStateMachine.assert_valid(
            CategoryStatus.PENDING_DOCUMENTS, CategoryStatus.CONFLICTING_EVIDENCE
        )


@pytest.mark.unit
def test_marked_na_event_transitions_to_not_applicable_from_any_non_terminal() -> None:
    for state in (
        CategoryStatus.PENDING_DOCUMENTS,
        CategoryStatus.INSUFFICIENT_EVIDENCE,
        CategoryStatus.SCORED,
        CategoryStatus.CONFLICTING_EVIDENCE,
    ):
        assert (
            CategoryStateMachine.transition(state, "marked_na")
            is CategoryStatus.NOT_APPLICABLE
        )
