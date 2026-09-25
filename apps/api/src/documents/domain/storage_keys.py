"""P0b immutable document storage contract (ADR-015 revision lineage).

Every revision's bytes live at one immutable object key, scoped to its tenant, project and
document and addressed by the SHA-256 of its content::

    tenants/{tenant_id}/projects/{project_id}/documents/{document_id}/revisions/{sha256}{ext}

Initial upload and re-upload use the same key; a later revision never overwrites, moves or
deletes an earlier one. ``Document.storage_url`` is only a pointer to the current revision
object and is never read as history.

Documents uploaded before revisions existed keep their bytes at the legacy ``{id}{ext}``
object. Those objects are read (and deleted with their document) but never written again.
"""

from __future__ import annotations

import os
import re
from uuid import UUID

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


def document_object_prefix(tenant_id: UUID, project_id: UUID, document_id: UUID) -> str:
    """Prefix owning every revision object of one document (always ends with ``/``)."""
    return f"tenants/{UUID(str(tenant_id))}/projects/{UUID(str(project_id))}/documents/{UUID(str(document_id))}/"


def revision_object_key(
    *,
    tenant_id: UUID,
    project_id: UUID,
    document_id: UUID,
    blob_hash: str,
    filename: str | None,
) -> str:
    """Immutable object key of one revision's bytes."""
    if not _SHA256_HEX.fullmatch(blob_hash or ""):
        raise ValueError("revision blob_hash must be a lowercase SHA-256 hex digest")
    extension = os.path.splitext(filename or "")[1].lower()
    return f"{document_object_prefix(tenant_id, project_id, document_id)}revisions/{blob_hash}{extension}"


def legacy_document_object_key(document_id: UUID, filename: str | None) -> str:
    """Object key of a document stored before revision lineage (read/delete only)."""
    extension = os.path.splitext(filename or "")[1].lower()
    return f"{UUID(str(document_id))}{extension}"


def is_document_object_prefix(prefix: str) -> bool:
    """True only for the exact prefix of a single document (never wider)."""
    parts = prefix.split("/")
    if len(parts) != 7 or parts[0] != "tenants" or parts[2] != "projects" or parts[4] != "documents" or parts[6] != "":
        return False
    try:
        return all(str(UUID(parts[index])) == parts[index] for index in (1, 3, 5))
    except ValueError:
        return False


__all__ = [
    "document_object_prefix",
    "is_document_object_prefix",
    "legacy_document_object_key",
    "revision_object_key",
]
