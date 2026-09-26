"""Pure factory for the ``revision.ingested`` ProjectEvent (ADR-015).

Builds the material event that anchors a DocumentRevision to the append-only
project event log, establishing the correct lineage:

    DocumentRevision.revision_id -> ProjectEvent.source_revision_id

This module is deliberately pure: it must NOT open a DB session, commit, or
enqueue. Callers own persistence (revision + event in one transaction) and the
post-commit Celery enqueue.

Test Suite ID: TS-UT-DOC-REV-LINEAGE-001
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.temporal.domain.document_revision import DocumentRevision
from src.temporal.domain.project_event import ProjectEvent


def build_revision_ingested_event(
    *,
    document_id: UUID,
    project_id: UUID,
    tenant_id: UUID,
    revision: DocumentRevision,
    filename: str,
    actor: str | None,
) -> ProjectEvent:
    """Construct a revision.ingested ProjectEvent without any I/O side-effects."""
    now = datetime.now(UTC).replace(tzinfo=None)
    return ProjectEvent(
        event_id=uuid4(),
        project_id=project_id,
        tenant_id=tenant_id,
        event_type="revision.ingested",
        payload={
            "document_id": str(document_id),
            "revision_id": str(revision.revision_id),
            "rev_no": revision.rev_no,
            "blob_hash": revision.blob_hash,
            "filename": filename,
        },
        actor=actor,
        source_revision_id=revision.revision_id,
        occurred_at=now,
        created_at=now,
    )


__all__ = ["build_revision_ingested_event"]
