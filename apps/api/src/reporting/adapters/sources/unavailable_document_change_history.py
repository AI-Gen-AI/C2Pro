"""TS-P0D-REPORT-006 - Default document change history: unavailable until change sets are stored.

No computed revision change sets are persisted or readable in this codebase yet, so
this adapter always reports the source as unavailable. It never returns an empty
list, which would falsely read as "nothing changed".
"""

from __future__ import annotations

from uuid import UUID

from src.change_intelligence.domain.contracts import ChangeSet
from src.reporting.application.ports import SourceUnavailableError

DOCUMENT_CHANGE_HISTORY_UNAVAILABLE_REASON = (
    "Document change history is not available yet: computed revision changes are not stored in this environment."
)


class UnavailableDocumentChangeHistory:
    async def list_revision_changes(self, project_id: UUID, tenant_id: UUID, *, from_event_id: UUID, to_event_id: UUID) -> list[ChangeSet]:  # noqa: ARG002 - DocumentChangeHistory signature; there is nothing to read yet
        raise SourceUnavailableError(DOCUMENT_CHANGE_HISTORY_UNAVAILABLE_REASON)
