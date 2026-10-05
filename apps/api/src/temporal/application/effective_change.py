"""Which stored outcome of a revision is its EFFECTIVE (current) result? (Lane C / C3b-2)

A revision can accumulate several immutable outcome events:

* ``revision.changed`` / ``revision.analysis_failed`` -- an ANALYSIS of the
  revision (a fresh comparison, or its failure); a re-analysis appends another;
* ``revision.recomputed`` -- the current matcher re-run over an earlier
  comparison's immutable snapshots (``provenance.recomputed_from_event_id``);
* ``revision.reinterpreted`` -- a later L2 reading of an earlier comparison's
  pairings (``provenance.reinterpretation_of_event_id``).

Derived events never replace history: every event stays readable. What a
reader is given as *effective* is decided by lineage and trust qualification,
never by "latest timestamp" alone:

1. The newest ANALYSIS (root) wins -- re-analysing a revision supersedes its
   earlier analyses, and a failed newest analysis fails closed.
2. Within that root's derivation family, the best-qualified event wins: a
   comparison by the CURRENT registered matcher beats a LEGACY one, which beats
   an UNSUPPORTED one. So an older matcher's output can never shadow a
   recomputation by the current matcher, whatever their timestamps.
3. Ties prefer the deeper derivation (a derived event refines its parent),
   then the newer event, then the event id (total, deterministic order).

Every other event is HISTORICAL and names the event that supersedes it.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from src.temporal.application.change_qualification import qualify_event
from src.temporal.domain.engine_registry import MatcherStatus
from src.temporal.domain.project_event import ProjectEvent

ANALYSIS_EVENT_TYPES = frozenset({"revision.changed", "revision.analysis_failed"})
DERIVED_EVENT_TYPES = frozenset({"revision.recomputed", "revision.reinterpreted"})
OUTCOME_EVENT_TYPES = ANALYSIS_EVENT_TYPES | DERIVED_EVENT_TYPES

# provenance key naming the event a derived event was produced from.
_DERIVATION_KEYS = {
    "revision.recomputed": "recomputed_from_event_id",
    "revision.reinterpreted": "reinterpretation_of_event_id",
}
_STATUS_RANK = {
    MatcherStatus.CURRENT: 2,
    MatcherStatus.LEGACY: 1,
    MatcherStatus.UNSUPPORTED: 0,
}
_MAX_DEPTH = 64


class Derivation(StrEnum):
    ORIGINAL = "original"
    RECOMPUTED = "recomputed"
    REINTERPRETED = "reinterpreted"


@dataclass(frozen=True)
class EffectiveOutcome:
    """The effective outcome of ONE revision and the lineage of the others."""

    effective: ProjectEvent | None
    superseded_by: dict[UUID, UUID] = field(default_factory=dict)

    def is_effective(self, event: ProjectEvent) -> bool:
        return self.effective is not None and event.event_id == self.effective.event_id


def derivation_of(event: ProjectEvent) -> Derivation:
    if event.event_type == "revision.recomputed":
        return Derivation.RECOMPUTED
    if event.event_type == "revision.reinterpreted":
        return Derivation.REINTERPRETED
    return Derivation.ORIGINAL


def derived_from(event: ProjectEvent) -> UUID | None:
    key = _DERIVATION_KEYS.get(event.event_type)
    provenance = event.payload.get("provenance") if isinstance(event.payload, dict) else None
    raw = provenance.get(key) if key and isinstance(provenance, dict) else None
    try:
        return UUID(str(raw)) if raw else None
    except ValueError:
        return None


def _order(event: ProjectEvent) -> tuple[object, ...]:
    return (event.occurred_at, str(event.event_id))


def select_effective_outcome(events: Iterable[ProjectEvent]) -> EffectiveOutcome:
    """Pick the effective outcome among one revision's events (pure, deterministic)."""
    outcomes = [event for event in events if event.event_type in OUTCOME_EVENT_TYPES]
    if not outcomes:
        return EffectiveOutcome(effective=None)
    by_id = {event.event_id: event for event in outcomes}

    def chain(event: ProjectEvent) -> list[ProjectEvent]:
        """event, its parent, ... up to the root present in this set (cycle safe)."""
        path = [event]
        seen = {event.event_id}
        current = event
        for _ in range(_MAX_DEPTH):
            parent_id = derived_from(current)
            parent = by_id.get(parent_id) if parent_id else None
            if parent is None or parent.event_id in seen:
                break
            path.append(parent)
            seen.add(parent.event_id)
            current = parent
        return path

    roots = [event for event in outcomes if event.event_type in ANALYSIS_EVENT_TYPES]
    if not roots:
        # Derived events whose analysis is not in this set: their own chains' tops.
        roots = list({chain(event)[-1].event_id: chain(event)[-1] for event in outcomes}.values())
    root = max(roots, key=_order)

    if root.event_type == "revision.analysis_failed":
        effective = root
    else:
        family = [event for event in outcomes if chain(event)[-1].event_id == root.event_id]

        def rank(event: ProjectEvent) -> tuple[object, ...]:
            status = qualify_event(event).matcher_status
            return (
                _STATUS_RANK.get(status, -1) if status is not None else -1,
                len(chain(event)),
                *_order(event),
            )

        effective = max(family, key=rank)

    superseded = {
        event.event_id: effective.event_id
        for event in outcomes
        if event.event_id != effective.event_id
    }
    return EffectiveOutcome(effective=effective, superseded_by=superseded)


def effective_by_revision(events: Sequence[ProjectEvent]) -> dict[UUID, EffectiveOutcome]:
    """Group outcome events by the revision they describe and select per revision."""
    grouped: dict[UUID, list[ProjectEvent]] = {}
    for event in events:
        if event.event_type in OUTCOME_EVENT_TYPES and event.source_revision_id is not None:
            grouped.setdefault(event.source_revision_id, []).append(event)
    return {revision_id: select_effective_outcome(group) for revision_id, group in grouped.items()}


__all__ = [
    "ANALYSIS_EVENT_TYPES",
    "DERIVED_EVENT_TYPES",
    "OUTCOME_EVENT_TYPES",
    "Derivation",
    "EffectiveOutcome",
    "derivation_of",
    "derived_from",
    "effective_by_revision",
    "select_effective_outcome",
]
