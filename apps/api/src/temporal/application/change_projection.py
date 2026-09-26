"""TS-UT-P0C-TEMPORAL-001 - canonical P0c revision-change ProjectEvent projection.

The event payload is the durable, immutable change read model.  It deliberately
stores the existing ADR-016 ``ChangeSet`` unchanged alongside P0c-only product
metadata; no second ChangeSet persistence model is introduced.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from src.change_intelligence.domain.contracts import ChangeSet
from src.temporal.domain.document_revision import DocumentRevision
from src.temporal.domain.project_event import ProjectEvent

CHANGE_PROJECTION_ENGINE_VERSION = "p0c-structural-l1-v1"


class ChangeCause(StrEnum):
    """Why C2Pro presents a non-empty computed change."""

    BUSINESS_STATE_CHANGED = "BUSINESS_STATE_CHANGED"
    NEWLY_DISCOVERED = "NEWLY_DISCOVERED"


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _state_for(changeset: ChangeSet) -> str:
    if any(change.needs_review for change in changeset.changes):
        return "needs_review"
    return "ready"


def _confidence_for(changeset: ChangeSet) -> float | None:
    values = [
        change.confidence if change.confidence is not None else change.match_confidence
        for change in changeset.changes
    ]
    return min(values) if values else None


def _cause_for(changeset: ChangeSet, source_blob_hash: str, target_blob_hash: str) -> ChangeCause | None:
    if not changeset.changes:
        return None
    if source_blob_hash == target_blob_hash:
        return ChangeCause.NEWLY_DISCOVERED
    return ChangeCause.BUSINESS_STATE_CHANGED


def build_change_projection_event(
    *,
    changeset: ChangeSet,
    document_id: UUID,
    source_blob_hash: str,
    target_blob_hash: str,
    source_ingestion_event_id: UUID | None = None,
    target_ingestion_event_id: UUID | None = None,
    semantic_model_version: str | None = None,
    semantic_provider: str | None = None,
    semantic_model: str | None = None,
    change_cause: ChangeCause | None = None,
    event_type: str = "revision.changed",
    provenance_extra: dict[str, str] | None = None,
    actor: str | None = None,
) -> ProjectEvent:
    """Build the immutable temporal projection after L1/L2 computation.

    Equal content hashes can still produce a useful interpretation upgrade, but
    are never labelled as a change in the underlying business state.
    """

    now = _utcnow()
    cause = change_cause if change_cause is not None else _cause_for(
        changeset, source_blob_hash, target_blob_hash
    )
    evidence_refs = [
        ref for change in changeset.changes for ref in change.evidence_refs
    ]
    return ProjectEvent(
        event_id=uuid4(),
        project_id=changeset.project_id,
        tenant_id=changeset.tenant_id,
        event_type=event_type,
        payload={
            "schema_version": 1,
            "state": _state_for(changeset),
            "document_id": str(document_id),
            "change_cause": cause.value if cause is not None else None,
            "changeset": changeset.model_dump(mode="json"),
            "source_ingestion_event_id": (
                str(source_ingestion_event_id) if source_ingestion_event_id else None
            ),
            "target_ingestion_event_id": (
                str(target_ingestion_event_id) if target_ingestion_event_id else None
            ),
            "provenance": {
                "diff_engine_version": CHANGE_PROJECTION_ENGINE_VERSION,
                "source_revision_id": str(changeset.from_revision_id),
                "target_revision_id": str(changeset.to_revision_id),
                "semantic_model_version": semantic_model_version,
                "semantic_provider": semantic_provider,
                "semantic_model": semantic_model,
                "source_blob_hash": source_blob_hash,
                "target_blob_hash": target_blob_hash,
                **(provenance_extra or {}),
            },
            "l3_impact": None,
        },
        actor=actor,
        confidence=_confidence_for(changeset),
        source_revision_id=changeset.to_revision_id,
        evidence_refs=evidence_refs,
        occurred_at=now,
        created_at=now,
    )


def build_revision_processing_failed_event(
    *,
    revision: DocumentRevision,
    failure_code: str,
    actor: str | None = None,
) -> ProjectEvent:
    """Record a queryable, retry-safe failure without exposing exception text.

    This projection is append-only. A subsequent successful analysis adds its
    own snapshot/change event rather than rewriting the historical failure.
    """
    now = _utcnow()
    return ProjectEvent(
        event_id=uuid4(),
        project_id=revision.project_id,
        tenant_id=revision.tenant_id,
        event_type="revision.analysis_failed",
        payload={
            "schema_version": 1,
            "state": "error",
            "reason": "Revision analysis failed; retry will be attempted.",
            "failure_code": failure_code,
            "document_id": str(revision.document_id),
            "change_cause": None,
            "provenance": {
                "diff_engine_version": CHANGE_PROJECTION_ENGINE_VERSION,
                "source_revision_id": str(revision.revision_id),
                "target_revision_id": str(revision.revision_id),
                "semantic_model_version": None,
            },
            "l3_impact": None,
        },
        actor=actor,
        source_revision_id=revision.revision_id,
        evidence_refs=[],
        occurred_at=now,
        created_at=now,
    )


__all__ = [
    "CHANGE_PROJECTION_ENGINE_VERSION",
    "ChangeCause",
    "build_change_projection_event",
    "build_revision_processing_failed_event",
]
