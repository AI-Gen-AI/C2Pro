"""
Deterministic Category State Machine for ECOA v2 (ADR-009 §7, §8).

Refers to Suite ID: TS-UD-COH-V2-SM-001.
"""
from __future__ import annotations

from typing import Final

from src.coherence.application.dtos.coherence_v2_dtos import CategoryStatus


class InvalidTransitionError(RuntimeError):
    """Raised when the requested (state, event) pair is not allowed by ADR-009 §8."""


_ALLOWED_TRANSITIONS: Final[dict[tuple[CategoryStatus, str], CategoryStatus]] = {
    # From pending_documents
    (CategoryStatus.PENDING_DOCUMENTS, "docs_uploaded"): CategoryStatus.PENDING_DOCUMENTS,
    (CategoryStatus.PENDING_DOCUMENTS, "evidence_below_threshold"): CategoryStatus.INSUFFICIENT_EVIDENCE,
    (CategoryStatus.PENDING_DOCUMENTS, "evidence_meets_threshold"): CategoryStatus.SCORED,
    (CategoryStatus.PENDING_DOCUMENTS, "marked_na"): CategoryStatus.NOT_APPLICABLE,
    (CategoryStatus.PENDING_DOCUMENTS, "engine_error"): CategoryStatus.PROCESSING_ERROR,
    (CategoryStatus.PENDING_DOCUMENTS, "reset"): CategoryStatus.PENDING_DOCUMENTS,

    # From insufficient_evidence
    (CategoryStatus.INSUFFICIENT_EVIDENCE, "evidence_meets_threshold"): CategoryStatus.SCORED,
    (CategoryStatus.INSUFFICIENT_EVIDENCE, "evidence_below_threshold"): CategoryStatus.INSUFFICIENT_EVIDENCE,
    (CategoryStatus.INSUFFICIENT_EVIDENCE, "docs_uploaded"): CategoryStatus.INSUFFICIENT_EVIDENCE,
    (CategoryStatus.INSUFFICIENT_EVIDENCE, "marked_na"): CategoryStatus.NOT_APPLICABLE,
    (CategoryStatus.INSUFFICIENT_EVIDENCE, "engine_error"): CategoryStatus.PROCESSING_ERROR,
    (CategoryStatus.INSUFFICIENT_EVIDENCE, "reset"): CategoryStatus.PENDING_DOCUMENTS,

    # From scored
    (CategoryStatus.SCORED, "conflict_detected"): CategoryStatus.CONFLICTING_EVIDENCE,
    (CategoryStatus.SCORED, "docs_deleted"): CategoryStatus.INSUFFICIENT_EVIDENCE,
    (CategoryStatus.SCORED, "evidence_meets_threshold"): CategoryStatus.SCORED,
    (CategoryStatus.SCORED, "marked_na"): CategoryStatus.NOT_APPLICABLE,
    (CategoryStatus.SCORED, "engine_error"): CategoryStatus.PROCESSING_ERROR,
    (CategoryStatus.SCORED, "reset"): CategoryStatus.PENDING_DOCUMENTS,

    # From conflicting_evidence
    (CategoryStatus.CONFLICTING_EVIDENCE, "conflict_resolved"): CategoryStatus.SCORED,
    (CategoryStatus.CONFLICTING_EVIDENCE, "docs_deleted"): CategoryStatus.INSUFFICIENT_EVIDENCE,
    (CategoryStatus.CONFLICTING_EVIDENCE, "marked_na"): CategoryStatus.NOT_APPLICABLE,
    (CategoryStatus.CONFLICTING_EVIDENCE, "engine_error"): CategoryStatus.PROCESSING_ERROR,
    (CategoryStatus.CONFLICTING_EVIDENCE, "reset"): CategoryStatus.PENDING_DOCUMENTS,

    # From not_applicable
    (CategoryStatus.NOT_APPLICABLE, "reset"): CategoryStatus.PENDING_DOCUMENTS,
    (CategoryStatus.NOT_APPLICABLE, "marked_na"): CategoryStatus.NOT_APPLICABLE,

    # From processing_error (terminal except reset)
    (CategoryStatus.PROCESSING_ERROR, "reset"): CategoryStatus.PENDING_DOCUMENTS,
}


class CategoryStateMachine:
    """Pure functional state machine — class only for grouping."""

    @classmethod
    def transition(
        cls, current: CategoryStatus, event: str
    ) -> CategoryStatus:
        try:
            return _ALLOWED_TRANSITIONS[(current, event)]
        except KeyError as exc:
            raise InvalidTransitionError(
                f"Transition from {current.value!r} via event {event!r} is not allowed."
            ) from exc

    @classmethod
    def assert_valid(
        cls, frm: CategoryStatus, to: CategoryStatus
    ) -> None:
        if not any(
            target is to and source is frm
            for (source, _event), target in _ALLOWED_TRANSITIONS.items()
        ):
            raise InvalidTransitionError(
                f"No event transitions {frm.value!r} → {to.value!r}."
            )


__all__ = ["CategoryStateMachine", "InvalidTransitionError"]
