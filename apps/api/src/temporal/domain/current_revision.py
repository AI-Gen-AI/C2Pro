"""Which revision of a document is CURRENT truth (Lane C / C3a).

The only authority is the #714 trust machine: the document's active TRUSTED
artifact, bound to exactly one revision of that document. Never the latest
upload, the latest analysis or the highest ``rev_no``.

* ``TRUSTED`` -- an active TRUSTED artifact is bound to a revision of this
  document in this tenant; that revision is current.
* ``SINGLE_REVISION`` -- no bound TRUSTED artifact, but the document has at most
  one revision (or none: a pre-lineage upload) and it was not explicitly
  rejected. There is nothing to mix or to choose between, so its single clause
  set is current. This is also how a legacy, unbound TRUSTED artifact is honoured.
* ``UNRESOLVED`` -- anything else (several revisions and no bound TRUSTED one, a
  trusted binding to a revision outside the lineage, an only revision whose
  analysis was rejected). Readers fail closed: no current clauses.

The decision itself is SQL (``current_revision_sql``) so every reader -- the
repository, coherence, the budget builder, RAG retrieval -- applies the same rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class CurrentRevisionStatus(StrEnum):
    TRUSTED = "trusted"
    SINGLE_REVISION = "single_revision"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class CurrentRevision:
    document_id: UUID
    status: CurrentRevisionStatus
    # The current revision; None when unresolved or when the document has no lineage.
    revision_id: UUID | None
    # True when the document has at most one revision: legacy unbound rows can only
    # belong to it, so they may stand in for its clause set.
    single_revision: bool

    @property
    def resolved(self) -> bool:
        return self.status is not CurrentRevisionStatus.UNRESOLVED


__all__ = ["CurrentRevision", "CurrentRevisionStatus"]
