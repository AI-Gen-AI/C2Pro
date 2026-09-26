"""Resolve and fetch the immutable bytes a document operation must read (P0b).

The worker, the synchronous parse path and downloads all read a revision object by its
exact ``DocumentRevision.blob_key`` and verify its SHA-256 before use. A task that pins a
revision keeps reading that revision even after a newer one becomes current. Only a
document with no revision lineage at all falls back to its legacy ``{id}{ext}`` object.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import UUID

from src.documents.domain.models import Document
from src.documents.domain.storage_keys import legacy_document_object_key
from src.documents.ports.storage_service import IStorageService
from src.temporal.domain.document_revision import DocumentRevision
from src.temporal.ports.document_revision_repository import IDocumentRevisionRepository

REVISION_NOT_FOUND = "revision not found or access denied"
REVISION_HASH_MISMATCH = "immutable revision blob hash mismatch"


class RevisionSourceError(ValueError):
    """The requested revision cannot be read safely; never fall back to another object."""


async def resolve_source_revision(
    *,
    revision_repository: IDocumentRevisionRepository,
    document_id: UUID,
    tenant_id: UUID,
    revision_id: UUID | None,
) -> DocumentRevision | None:
    """Return the pinned revision, else the current one, inside the tenant and document.

    ``None`` means the document has no revision lineage (legacy upload).
    """
    if revision_id is not None:
        revision = await revision_repository.get_by_id(revision_id, tenant_id)
        if revision is None or revision.document_id != document_id or revision.tenant_id != tenant_id:
            raise RevisionSourceError(REVISION_NOT_FOUND)
        return revision
    return await revision_repository.get_current(document_id, tenant_id)


def verify_revision_file_hash(file_path: Path, expected_hash: str) -> None:
    """Fail closed if fetched bytes are not the revision they claim to be."""
    digest = hashlib.sha256()
    with file_path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected_hash:
        raise RevisionSourceError(REVISION_HASH_MISMATCH)


async def fetch_source_file(
    *,
    storage: IStorageService,
    document: Document,
    revision: DocumentRevision | None,
) -> Path:
    """Download the immutable object for ``revision`` (or the legacy object if none)."""
    if revision is None:
        return await storage.download_file(legacy_document_object_key(document.id, document.filename))
    file_path = await storage.download_object(revision.blob_key)
    verify_revision_file_hash(file_path, revision.blob_hash)
    return file_path


__all__ = [
    "REVISION_HASH_MISMATCH",
    "REVISION_NOT_FOUND",
    "RevisionSourceError",
    "fetch_source_file",
    "resolve_source_revision",
    "verify_revision_file_hash",
]
