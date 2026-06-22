"""FROZEN — DocumentRevision lineage contract (ADR-015 / TASK-V3-015-01).

Content-addressed, append-only revision chain. Each revision is immutable
except for closing the open interval (valid_to). The revision is the
evidence anchor for later temporal events (INV-1).

FROZEN CONTRACT — do not add/rename/remove fields without re-freezing.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentRevision(BaseModel):
    """Content-addressed document revision in the append-only lineage chain."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    revision_id: UUID
    document_id: UUID
    project_id: UUID
    tenant_id: UUID
    rev_no: int
    parent_revision_id: UUID | None = None
    blob_hash: str
    blob_key: str
    valid_from: datetime
    valid_to: datetime | None = None
    created_at: datetime


__all__ = ["DocumentRevision"]
