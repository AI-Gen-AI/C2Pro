"""Evidence-preserving L2 reinterpretation producer for P0c temporal events."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from src.change_intelligence.application.semantic_diff import enrich_modified_changes
from src.change_intelligence.domain.contracts import ChangeSet
from src.temporal.application.change_projection import ChangeCause, build_change_projection_event
from src.temporal.domain.project_event import ProjectEvent
from src.temporal.ports.project_event_repository import IProjectEventRepository


def _interpretation_fingerprint(changeset: ChangeSet) -> tuple[tuple[object, ...], ...]:
    """Only semantic conclusions count; structural evidence must remain unchanged."""
    return tuple(
        (
            change.anchor,
            change.semantic_summary,
            change.severity,
            change.confidence,
            change.needs_review,
        )
        for change in changeset.changes
    )


async def reinterpret_change_event(
    *,
    original_event: ProjectEvent,
    llm: Any,
    semantic_provider: str,
    semantic_model: str,
    semantic_model_version: str,
) -> ProjectEvent | None:
    """Run later L2 interpretation over immutable prior evidence.

    The producer emits nothing when the interpretation is materially unchanged.
    When it is richer, it emits a new append-only event classified
    ``NEWLY_DISCOVERED`` even if the original revision comparison involved two
    different uploads: the new event describes what C2Pro learned later, not a
    second mutation of business reality.
    """
    if original_event.event_type not in {"revision.changed", "revision.reinterpreted"}:
        return None
    payload = original_event.payload
    raw_changeset = payload.get("changeset")
    provenance = payload.get("provenance")
    document_id = payload.get("document_id")
    if not isinstance(raw_changeset, dict) or not isinstance(provenance, dict) or not isinstance(document_id, str):
        return None
    # ``model_dump(mode='json')`` includes Pydantic computed fields; they are
    # read-only projection convenience, not ChangeSet input.
    changeset = ChangeSet.model_validate(
        {key: value for key, value in raw_changeset.items() if key != "summary_counts"}
    )
    enriched = await enrich_modified_changes(changeset, changeset.tenant_id, llm=llm)
    if _interpretation_fingerprint(enriched) == _interpretation_fingerprint(changeset):
        return None
    source_hash = provenance.get("source_blob_hash")
    target_hash = provenance.get("target_blob_hash")
    if not isinstance(source_hash, str) or not isinstance(target_hash, str):
        return None
    return build_change_projection_event(
        changeset=enriched,
        document_id=UUID(document_id),
        source_blob_hash=source_hash,
        target_blob_hash=target_hash,
        semantic_provider=semantic_provider,
        semantic_model=semantic_model,
        semantic_model_version=semantic_model_version,
        change_cause=ChangeCause.NEWLY_DISCOVERED,
        event_type="revision.reinterpreted",
        provenance_extra={"reinterpretation_of_event_id": str(original_event.event_id)},
    )


async def produce_reinterpretation_event(
    *,
    repository: IProjectEventRepository,
    original_event: ProjectEvent,
    llm: Any,
    semantic_provider: str,
    semantic_model: str,
    semantic_model_version: str,
) -> ProjectEvent | None:
    """Persist a later L2 interpretation as a separate temporal event."""
    event = await reinterpret_change_event(
        original_event=original_event,
        llm=llm,
        semantic_provider=semantic_provider,
        semantic_model=semantic_model,
        semantic_model_version=semantic_model_version,
    )
    if event is not None:
        await repository.append(event)
    return event


__all__ = ["produce_reinterpretation_event", "reinterpret_change_event"]
