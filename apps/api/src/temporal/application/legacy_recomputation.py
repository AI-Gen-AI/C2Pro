"""Governed, append-only recomputation of legacy temporal comparisons (Lane C / C3b-2).

A ``revision.changed`` event whose clause pairings were produced by an OLDER
version of a registered matcher (``p0c-structural-l1-v1``) is read-time
qualified LEGACY (``change_qualification``): its pairings are unverified and
need review. This module re-runs the CURRENT matcher over exactly the evidence
the original comparison used -- the immutable ``revision.analyzed`` clause
snapshots of its source and target revisions -- and appends the result as a
NEW ``revision.recomputed`` event.

Rules:

* The original event is never mutated or deleted; its evidence stays readable.
* Provenance links the result to what it was recomputed from
  (``recomputed_from_event_id``, ``recomputed_from_engine``) and to the exact
  evidence (source/target revision ids and blob hashes, and the snapshot event
  ids used). The engine that produced the new pairings is the current one.
* Only the snapshots that existed when the original comparison was made, and
  whose blob hash matches the original's provenance, are used. Missing or
  mismatched evidence makes the event NOT_RECOMPUTABLE: nothing is fabricated.
* Idempotent: the result's ``event_id`` is a deterministic function of
  (original event id, current engine version). Recomputing the same original
  with the same engine twice yields the same id, and the primary key admits it
  once. A future engine version produces a new, distinct recomputation.
* Which event is EFFECTIVE for a revision is decided by
  ``effective_change.select_effective_outcome`` (lineage + matcher
  qualification), never by recency alone; the LEGACY original stays visible as
  historical evidence and can never masquerade as the current matcher's output.
* L2 semantic interpretation is not re-run here (deterministic L1 only); a later
  ``revision.reinterpreted`` may enrich the recomputed pairings.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID, uuid5

from src.change_intelligence.application.structural_diff import diff_contract_revisions
from src.temporal.application.change_projection import (
    CHANGE_PROJECTION_ENGINE_VERSION,
    build_change_projection_event,
)
from src.temporal.application.change_qualification import qualify_event
from src.temporal.application.revision_change_orchestrator import snapshot_clauses_for_revision
from src.temporal.domain.engine_registry import MatcherStatus
from src.temporal.domain.project_event import ProjectEvent
from src.temporal.ports.project_event_repository import IProjectEventRepository

#: Fixed namespace for recomputation identities (never change: ids are durable).
RECOMPUTATION_NAMESPACE = UUID("3b2c0e5a-7d1f-4c62-9a8e-c3b2c3b2c3b2")
RECOMPUTED_EVENT_TYPE = "revision.recomputed"
RECOMPUTE_ACTOR = "temporal.recompute"


class RecomputeStatus(StrEnum):
    RECOMPUTED = "recomputed"
    ALREADY_RECOMPUTED = "already_recomputed"
    NOT_ELIGIBLE = "not_eligible"
    NOT_RECOMPUTABLE = "not_recomputable"


@dataclass(frozen=True)
class RecomputeOutcome:
    status: RecomputeStatus
    original_event_id: UUID
    recomputed_event_id: UUID | None = None
    reason: str | None = None


def recomputation_event_id(original_event_id: UUID, engine_version: str) -> UUID:
    return uuid5(RECOMPUTATION_NAMESPACE, f"{original_event_id}/{engine_version}")


def eligibility(event: ProjectEvent) -> str | None:
    """None when ``event`` is a legacy comparison the current matcher may recompute."""
    if event.event_type != "revision.changed":
        return "not_an_original_comparison"
    status = qualify_event(event).matcher_status
    if status is not MatcherStatus.LEGACY:
        # CURRENT needs nothing; UNSUPPORTED is an engine nobody registered, so
        # nothing proves the current matcher of a family applies to its evidence.
        return f"matcher_{status.value if status else 'unknown'}"
    return None


def _snapshot(
    revision_id: UUID, blob_hash: object, original: ProjectEvent, events: Sequence[ProjectEvent]
) -> ProjectEvent | None:
    """The revision's analysis snapshot as it stood when ``original`` was made."""
    candidates = [
        event
        for event in events
        if event.event_type == "revision.analyzed"
        and event.payload.get("revision_id") == str(revision_id)
        and event.payload.get("blob_hash") == blob_hash
        and event.payload.get("state", "ready") == "ready"
        and (event.occurred_at, str(event.event_id)) <= (original.occurred_at, str(original.event_id))
    ]
    return max(candidates, key=lambda event: (event.occurred_at, str(event.event_id))) if candidates else None


def build_recomputed_event(
    original: ProjectEvent, evidence: Sequence[ProjectEvent]
) -> ProjectEvent | str:
    """The recomputed event for ``original``, or the reason it cannot be built."""
    reason = eligibility(original)
    if reason is not None:
        return reason
    payload = original.payload
    provenance = payload.get("provenance")
    document_id = payload.get("document_id")
    if not isinstance(provenance, dict) or not isinstance(document_id, str):
        return "original_provenance_incomplete"
    try:
        source_revision_id = UUID(str(provenance["source_revision_id"]))
        target_revision_id = UUID(str(provenance["target_revision_id"]))
    except (KeyError, ValueError):
        return "original_provenance_incomplete"
    if original.source_revision_id != target_revision_id:
        return "original_provenance_inconsistent"
    source_hash = provenance.get("source_blob_hash")
    target_hash = provenance.get("target_blob_hash")
    source = _snapshot(source_revision_id, source_hash, original, evidence)
    target = _snapshot(target_revision_id, target_hash, original, evidence)
    if source is None or target is None:
        return "evidence_snapshot_missing"
    old_clauses = snapshot_clauses_for_revision(source_revision_id, [source])
    new_clauses = snapshot_clauses_for_revision(target_revision_id, [target])
    if old_clauses is None or new_clauses is None:
        return "evidence_snapshot_incomplete"

    changeset = diff_contract_revisions(
        project_id=original.project_id,
        tenant_id=original.tenant_id,
        from_revision_id=source_revision_id,
        to_revision_id=target_revision_id,
        old_clauses=old_clauses,
        new_clauses=new_clauses,
    )
    event = build_change_projection_event(
        changeset=changeset,
        document_id=UUID(document_id),
        source_blob_hash=str(source_hash),
        target_blob_hash=str(target_hash),
        event_type=RECOMPUTED_EVENT_TYPE,
        actor=RECOMPUTE_ACTOR,
        diff_engine_version=CHANGE_PROJECTION_ENGINE_VERSION,
        provenance_extra={
            "recomputed_from_event_id": str(original.event_id),
            "recomputed_from_engine": str(provenance.get("diff_engine_version")),
            "recomputation_reason": "legacy_matcher",
            "source_snapshot_event_id": str(source.event_id),
            "target_snapshot_event_id": str(target.event_id),
        },
    )
    return event.model_copy(
        update={
            "event_id": recomputation_event_id(
                original.event_id, CHANGE_PROJECTION_ENGINE_VERSION
            )
        }
    )


async def recompute_legacy_change_event(
    repository: IProjectEventRepository, original: ProjectEvent
) -> RecomputeOutcome:
    """Append the current matcher's recomputation of ``original`` at most once."""
    reason = eligibility(original)
    if reason is not None:
        return RecomputeOutcome(RecomputeStatus.NOT_ELIGIBLE, original.event_id, reason=reason)
    event_id = recomputation_event_id(original.event_id, CHANGE_PROJECTION_ENGINE_VERSION)
    if await repository.get(event_id, original.tenant_id) is not None:
        return RecomputeOutcome(RecomputeStatus.ALREADY_RECOMPUTED, original.event_id, event_id)

    provenance = original.payload.get("provenance")
    revision_ids = {
        str(provenance.get(key))
        for key in ("source_revision_id", "target_revision_id")
        if isinstance(provenance, dict) and provenance.get(key)
    }
    evidence: list[ProjectEvent] = []
    for raw in sorted(revision_ids):
        try:
            revision_id = UUID(raw)
        except ValueError:
            continue
        evidence.extend(
            await repository.list_for_revision(tenant_id=original.tenant_id, revision_id=revision_id)
        )
    built = build_recomputed_event(original, evidence)
    if isinstance(built, str):
        return RecomputeOutcome(RecomputeStatus.NOT_RECOMPUTABLE, original.event_id, reason=built)
    if not await repository.append_if_absent(built):
        return RecomputeOutcome(RecomputeStatus.ALREADY_RECOMPUTED, original.event_id, event_id)
    return RecomputeOutcome(RecomputeStatus.RECOMPUTED, original.event_id, event_id)


async def recompute_legacy_changes_for_project(
    repository: IProjectEventRepository, *, tenant_id: UUID, project_id: UUID
) -> list[RecomputeOutcome]:
    """Recompute every eligible legacy comparison of one project (idempotent)."""
    events = await repository.list_for_project(project_id, tenant_id)
    outcomes: list[RecomputeOutcome] = []
    for event in events:
        if eligibility(event) is None:
            outcomes.append(await recompute_legacy_change_event(repository, event))
    return outcomes


__all__ = [
    "RECOMPUTATION_NAMESPACE",
    "RECOMPUTED_EVENT_TYPE",
    "RecomputeOutcome",
    "RecomputeStatus",
    "build_recomputed_event",
    "eligibility",
    "recompute_legacy_change_event",
    "recompute_legacy_changes_for_project",
    "recomputation_event_id",
]
