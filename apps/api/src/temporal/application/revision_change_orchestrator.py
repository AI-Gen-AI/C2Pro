"""TS-UT-P0C-TEMPORAL-004 - build P0c projections from immutable revision snapshots."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

from src.change_intelligence.application.semantic_diff import (
    enrich_modified_changes_with_provenance,
)
from src.change_intelligence.application.structural_diff import diff_contract_revisions
from src.documents.domain.models import Clause, ClauseType
from src.temporal.application.change_projection import build_change_projection_event
from src.temporal.domain.document_revision import DocumentRevision
from src.temporal.domain.project_event import ProjectEvent


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _snapshot_clause(clause: Clause) -> dict[str, Any]:
    return {
        "id": str(clause.id), "project_id": str(clause.project_id), "tenant_id": str(clause.tenant_id),
        "document_id": str(clause.document_id), "clause_code": clause.clause_code,
        "clause_type": clause.clause_type.value if clause.clause_type else None, "title": clause.title,
        "full_text": clause.full_text, "text_start_offset": clause.text_start_offset,
        "text_end_offset": clause.text_end_offset, "extracted_entities": clause.extracted_entities,
        "extraction_confidence": clause.extraction_confidence, "extraction_model": clause.extraction_model,
        "manually_verified": clause.manually_verified,
        "verified_at": clause.verified_at.isoformat() if clause.verified_at else None,
    }


def _restore_clause(snapshot: dict[str, Any]) -> Clause:
    return Clause(
        id=UUID(str(snapshot["id"])), project_id=UUID(str(snapshot["project_id"])),
        tenant_id=UUID(str(snapshot["tenant_id"])), document_id=UUID(str(snapshot["document_id"])),
        clause_code=str(snapshot["clause_code"]),
        clause_type=ClauseType(str(snapshot["clause_type"])) if snapshot.get("clause_type") else None,
        title=snapshot.get("title") if isinstance(snapshot.get("title"), str) else None,
        full_text=snapshot.get("full_text") if isinstance(snapshot.get("full_text"), str) else None,
        text_start_offset=snapshot.get("text_start_offset") if isinstance(snapshot.get("text_start_offset"), int) else None,
        text_end_offset=snapshot.get("text_end_offset") if isinstance(snapshot.get("text_end_offset"), int) else None,
        extracted_entities=cast(dict[str, Any], snapshot["extracted_entities"]) if isinstance(snapshot.get("extracted_entities"), dict) else {},
        extraction_confidence=float(snapshot["extraction_confidence"]) if isinstance(snapshot.get("extraction_confidence"), int | float) else None,
        extraction_model=snapshot.get("extraction_model") if isinstance(snapshot.get("extraction_model"), str) else None,
        manually_verified=bool(snapshot.get("manually_verified", False)),
    )


def _analysis_snapshot_event(
    revision: DocumentRevision,
    clauses: list[Clause],
    *,
    state: str = "ready",
    reason: str | None = None,
) -> ProjectEvent:
    now = _utcnow()
    return ProjectEvent(
        event_id=uuid4(), project_id=revision.project_id, tenant_id=revision.tenant_id,
        event_type="revision.analyzed", source_revision_id=revision.revision_id,
        payload={"schema_version": 1, "state": state, "reason": reason, "document_id": str(revision.document_id),
                 "revision_id": str(revision.revision_id), "blob_hash": revision.blob_hash,
                 "clauses": [_snapshot_clause(clause) for clause in clauses]},
        occurred_at=now, created_at=now,
    )


def _parent_snapshot(parent_revision_id: UUID, events: list[ProjectEvent]) -> ProjectEvent | None:
    for event in reversed(events):
        if event.event_type == "revision.analyzed" and event.payload.get("revision_id") == str(parent_revision_id):
            return event
    return None


async def build_revision_analysis_events(
    *, revision: DocumentRevision, clauses: list[Clause], existing_events: list[ProjectEvent]
) -> list[ProjectEvent]:
    """Emit a revision snapshot and, when possible, the real L1 temporal change.

    The parent comparison reads only the previous immutable event payload.  This
    keeps before evidence true even after current document clauses are replaced.
    """

    if any(
        event.event_type == "revision.analyzed"
        and event.payload.get("revision_id") == str(revision.revision_id)
        for event in existing_events
    ):
        return []
    snapshot = _analysis_snapshot_event(revision, clauses)
    if revision.parent_revision_id is None:
        return [snapshot]
    parent = _parent_snapshot(revision.parent_revision_id, existing_events)
    if parent is None:
        return [_analysis_snapshot_event(
            revision, clauses, state="needs_review",
            reason="The prior revision has not produced an immutable analysis snapshot yet.",
        )]
    raw_clauses = parent.payload.get("clauses")
    if not isinstance(raw_clauses, list) or not all(isinstance(value, dict) for value in raw_clauses):
        return [_analysis_snapshot_event(
            revision, clauses, state="needs_review",
            reason="The prior revision snapshot is incomplete and cannot support a reliable comparison.",
        )]
    previous_clauses = [_restore_clause(value) for value in raw_clauses]
    changeset = diff_contract_revisions(
        project_id=revision.project_id, tenant_id=revision.tenant_id,
        from_revision_id=revision.parent_revision_id, to_revision_id=revision.revision_id,
        old_clauses=previous_clauses, new_clauses=clauses,
    )
    # ADR-016 L2 remains tenant-gated and fail-closed.  The projection keeps
    # L1 when the gate is off or an individual semantic call fails.
    enriched_changeset, semantic_provenance = await enrich_modified_changes_with_provenance(
        changeset, revision.tenant_id
    )
    change = build_change_projection_event(
        changeset=enriched_changeset, document_id=revision.document_id,
        source_blob_hash=str(parent.payload.get("blob_hash") or ""), target_blob_hash=revision.blob_hash,
        semantic_provider=semantic_provenance["provider"] if semantic_provenance else None,
        semantic_model=semantic_provenance["model"] if semantic_provenance else None,
        semantic_model_version=semantic_provenance["version"] if semantic_provenance else None,
    )
    return [snapshot, change]


__all__ = ["build_revision_analysis_events"]
