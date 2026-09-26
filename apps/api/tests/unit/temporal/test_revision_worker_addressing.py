"""TS-UT-P0C-TEMPORAL-005 - ingestion binds work to an immutable revision."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from src.documents.application.document_source import (
    resolve_source_revision as resolve_processing_revision,
)
from src.documents.application.document_source import verify_revision_file_hash
from src.temporal.domain.document_revision import DocumentRevision


def _revision(*, revision_id: UUID, document_id: UUID, tenant_id: UUID, project_id: UUID, number: int) -> DocumentRevision:
    now = datetime.now(UTC).replace(tzinfo=None)
    return DocumentRevision(
        revision_id=revision_id, document_id=document_id, tenant_id=tenant_id,
        project_id=project_id, rev_no=number, parent_revision_id=None,
        blob_hash=f"hash-{number}", blob_key=f"revisions/hash-{number}.pdf",
        valid_from=now, created_at=now,
    )


class _RevisionRepo:
    def __init__(self, current: DocumentRevision, by_id: dict[UUID, DocumentRevision]) -> None:
        self.current = current
        self.by_id = by_id

    async def get_current(self, document_id: UUID, tenant_id: UUID) -> DocumentRevision | None:
        assert document_id == self.current.document_id
        assert tenant_id == self.current.tenant_id
        return self.current

    async def get_by_id(self, revision_id: UUID, tenant_id: UUID) -> DocumentRevision | None:
        revision = self.by_id.get(revision_id)
        return revision if revision and revision.tenant_id == tenant_id else None


@pytest.mark.asyncio
async def test_worker_uses_explicit_revision_even_after_later_revision_becomes_current() -> None:
    """TS-UT-P0C-TEMPORAL-005: queued A never reads B's mutable storage pointer."""
    document_id, tenant_id, project_id = uuid4(), uuid4(), uuid4()
    revision_a = _revision(revision_id=uuid4(), document_id=document_id, tenant_id=tenant_id, project_id=project_id, number=1)
    revision_b = _revision(revision_id=uuid4(), document_id=document_id, tenant_id=tenant_id, project_id=project_id, number=2)
    repo = _RevisionRepo(revision_b, {revision_a.revision_id: revision_a, revision_b.revision_id: revision_b})

    selected = await resolve_processing_revision(
        revision_repository=repo, document_id=document_id, tenant_id=tenant_id,  # type: ignore[arg-type]
        revision_id=revision_a.revision_id,
    )

    assert selected == revision_a
    assert selected.blob_key == "revisions/hash-1.pdf"


@pytest.mark.asyncio
async def test_worker_rejects_explicit_revision_from_another_document() -> None:
    """TS-UT-P0C-TEMPORAL-005: identifiers cannot be used to cross document history."""
    document_id, tenant_id, project_id = uuid4(), uuid4(), uuid4()
    current = _revision(revision_id=uuid4(), document_id=document_id, tenant_id=tenant_id, project_id=project_id, number=2)
    foreign = _revision(revision_id=uuid4(), document_id=uuid4(), tenant_id=tenant_id, project_id=project_id, number=1)

    with pytest.raises(ValueError, match="revision not found"):
        await resolve_processing_revision(
            revision_repository=_RevisionRepo(current, {foreign.revision_id: foreign}),  # type: ignore[arg-type]
            document_id=document_id, tenant_id=tenant_id, revision_id=foreign.revision_id,
        )


def test_worker_rejects_bytes_that_do_not_match_the_pinned_revision(tmp_path) -> None:
    """TS-UT-P0C-TEMPORAL-005: a key collision/corruption cannot fabricate evidence."""
    file_path = tmp_path / "revision.pdf"
    file_path.write_bytes(b"bytes from a later revision")

    with pytest.raises(ValueError, match="immutable revision blob hash mismatch"):
        verify_revision_file_hash(file_path, "not-the-file-hash")
