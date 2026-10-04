"""Port: which revisions of a document the #714 trust machine has TRUSTED.

Read-only evidence for the lineage-aware temporal-review seam. The authority is
the #714 ``document_artifacts`` trust state; this port only reports it, keyed
by the exact revision each artifact is bound to. Artifacts with no revision
binding are never attributed to a revision -- only flagged.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class RevisionTrustEvidence:
    # revision_id -> the #714 trust states of the artifacts bound to it.
    states_by_revision: Mapping[UUID, frozenset[str]]
    # A TRUSTED artifact of this document exists with no revision binding (legacy).
    unbound_trusted: bool


class IRevisionTrustReader(Protocol):
    async def read(self, *, tenant_id: UUID, document_id: UUID) -> RevisionTrustEvidence: ...


__all__ = ["IRevisionTrustReader", "RevisionTrustEvidence"]
