"""Read-time qualification of stored temporal events (PR-C2).

Stored change events are immutable evidence. What a user (or the trust seam)
is given is qualified when read: only a change event produced by the CURRENT
version of a registered engine family, with match provenance on every change,
passes through unchanged. Anything else is presented as ``needs_review`` with
unknown confidence and no change cause:

* LEGACY      -- a known older version of a registered family (``legacy_matcher``);
* UNSUPPORTED -- an engine nobody registered (unverified, never called legacy);
* CURRENT engine but a change without ``match_basis`` -- provenance incomplete.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.temporal.domain.engine_registry import (
    REGISTERED_ENGINE_FAMILIES,
    MatcherStatus,
    classify_engine_version,
)
from src.temporal.domain.project_event import ProjectEvent

CHANGE_EVENT_TYPES = frozenset({"revision.changed", "revision.reinterpreted", "revision.recomputed"})


@dataclass(frozen=True)
class ChangeQualification:
    matcher_status: MatcherStatus | None  # None: not a change event
    legacy_matcher: bool
    identity_verified: bool
    effective_state: str
    effective_confidence: float | None
    effective_change_cause: str | None
    reason: str | None


def _stored_state(event: ProjectEvent) -> str:
    state = event.payload.get("state")
    if isinstance(state, str) and state:
        return state
    return "processing" if event.event_type == "revision.ingested" else "ready"


def _changes(event: ProjectEvent) -> list[Any]:
    changeset = event.payload.get("changeset")
    changes = changeset.get("changes") if isinstance(changeset, dict) else None
    return changes if isinstance(changes, list) else []


def _has_match_provenance(event: ProjectEvent) -> bool:
    return all(
        isinstance(change, dict) and isinstance(change.get("match_basis"), str)
        for change in _changes(event)
    )


def _cause(event: ProjectEvent) -> str | None:
    cause = event.payload.get("change_cause")
    return cause if isinstance(cause, str) else None


def qualify_event(event: ProjectEvent) -> ChangeQualification:
    if event.event_type not in CHANGE_EVENT_TYPES:
        return ChangeQualification(
            matcher_status=None,
            legacy_matcher=False,
            identity_verified=False,
            effective_state=_stored_state(event),
            effective_confidence=event.confidence,
            effective_change_cause=_cause(event),
            reason=None,
        )

    provenance = event.payload.get("provenance")
    engine = provenance.get("diff_engine_version") if isinstance(provenance, dict) else None
    classification = classify_engine_version(engine)
    status = classification.status

    if status is MatcherStatus.CURRENT and _has_match_provenance(event):
        # A stored "ready" never hides a change that itself needs review.
        review_required = any(change.get("needs_review") is True for change in _changes(event))
        return ChangeQualification(
            matcher_status=status,
            legacy_matcher=False,
            identity_verified=True,
            effective_state="needs_review" if review_required else _stored_state(event),
            effective_confidence=event.confidence,
            effective_change_cause=_cause(event),
            reason=None,
        )

    if status is MatcherStatus.LEGACY:
        current = REGISTERED_ENGINE_FAMILIES[str(classification.family)]
        reason = (
            f"Compared by an older matcher ({classification.engine}); the current version is "
            f"{classification.family}-v{current}. Its clause pairings are unverified and need review."
        )
    elif status is MatcherStatus.UNSUPPORTED:
        reason = (
            f"Compared by an unregistered engine ({classification.engine or 'not recorded'}); "
            "its pairings cannot be verified and need review."
        )
    else:
        reason = (
            "Match provenance is missing for at least one change; its pairing cannot be verified."
        )

    return ChangeQualification(
        matcher_status=status,
        legacy_matcher=status is MatcherStatus.LEGACY,
        identity_verified=False,
        effective_state="needs_review",
        effective_confidence=None,
        effective_change_cause=None,
        reason=reason,
    )


__all__ = ["CHANGE_EVENT_TYPES", "ChangeQualification", "qualify_event"]
