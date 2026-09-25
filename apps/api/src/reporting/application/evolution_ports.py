"""TS-P0D-REPORT-006 - Boundary for the Evolution Report's document change history.

The Evolution Report's document deltas come from computed revision change sets.
Reporting consumes them through this port as the existing ``ChangeSet`` contract
(ADR-016) and never computes diffs itself, so it does not pre-decide any field
the change-set producer has not defined. Until a readable change-set store
exists, the default adapter reports the source as unavailable, so an Evolution
Report can never present "no changes" for a window whose changes cannot be read.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.change_intelligence.domain.contracts import ChangeSet


class DocumentChangeHistory(Protocol):
    async def list_revision_changes(
        self,
        project_id: UUID,
        tenant_id: UUID,
        *,
        from_event_id: UUID,
        to_event_id: UUID,
    ) -> list[ChangeSet]:
        """Change sets for revisions ingested inside a window of the project event log.

        The window is bounded by two real ``revision.ingested`` project events, never by
        calendar dates: it excludes ``from_event_id`` and includes ``to_event_id``, with
        events ordered by ``occurred_at`` and then ``event_id``.
        Raises ``SourceUnavailableError`` when change history cannot be read.
        """
        ...


__all__ = ["DocumentChangeHistory"]
