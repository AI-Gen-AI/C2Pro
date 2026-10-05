"""Port for ProjectEvent append-only repository (ADR-015 / TASK-V3-015-03).

LOCKED INVARIANT: implementations MUST NOT call session commit().
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from src.temporal.application.timeline import TimelineKey
from src.temporal.domain.project_event import ProjectEvent


class IProjectEventRepository(ABC):
    @abstractmethod
    async def append(self, event: ProjectEvent) -> ProjectEvent:
        ...

    @abstractmethod
    async def get(self, event_id: UUID, tenant_id: UUID) -> ProjectEvent | None:
        """Exact tenant-scoped lookup of one event (snapshot lineage resolution)."""
        ...

    @abstractmethod
    async def list_for_project(
        self,
        project_id: UUID,
        tenant_id: UUID,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[ProjectEvent]:
        ...

    @abstractmethod
    async def page_for_project(
        self,
        project_id: UUID,
        tenant_id: UUID,
        *,
        after: TimelineKey | None,
        limit: int,
    ) -> list[ProjectEvent]:
        """Return at most ``limit + 1`` events in canonical database order."""
        ...

    @abstractmethod
    async def get_change_for_revision(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        document_id: UUID,
        revision_id: UUID,
    ) -> ProjectEvent | None:
        """Fail-closed relational lookup for one revision change projection."""
        ...

    @abstractmethod
    async def list_for_revision(self, *, tenant_id: UUID, revision_id: UUID) -> list[ProjectEvent]:
        """Every event a revision itself produced, in canonical order (temporal-review seam)."""
        ...

    async def append_if_absent(self, event: ProjectEvent) -> bool:
        """Append ``event`` unless an event with its id exists; True when appended.

        Idempotency for deterministic event ids (Lane C / C3b-2 recomputation).
        Implementations should make the check-and-insert race-safe.
        """
        if await self.get(event.event_id, event.tenant_id) is not None:
            return False
        await self.append(event)
        return True

    async def list_outcomes_for_revisions(
        self, *, tenant_id: UUID, revision_ids: list[UUID]
    ) -> list[ProjectEvent]:
        """Every outcome event (analysis / recomputation / reinterpretation) of these revisions."""
        from src.temporal.application.effective_change import OUTCOME_EVENT_TYPES

        events: list[ProjectEvent] = []
        for revision_id in dict.fromkeys(revision_ids):
            events.extend(
                event
                for event in await self.list_for_revision(tenant_id=tenant_id, revision_id=revision_id)
                if event.event_type in OUTCOME_EVENT_TYPES
            )
        return events

    async def list_revision_outcomes(
        self, *, tenant_id: UUID, project_id: UUID, document_id: UUID, revision_id: UUID
    ) -> list[ProjectEvent]:
        """Every outcome event of one revision of one document, in canonical order."""
        return [
            event
            for event in await self.list_outcomes_for_revisions(tenant_id=tenant_id, revision_ids=[revision_id])
            if event.project_id == project_id and event.payload.get("document_id") == str(document_id)
        ]


__all__ = ["IProjectEventRepository"]
