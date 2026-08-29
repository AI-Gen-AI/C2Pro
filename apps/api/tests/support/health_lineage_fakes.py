"""Shared in-memory doubles for the single-document assessment lineage (ADR-024 / P0b).

``SnapshotWriter`` resolves an assessment through three collaborators — snapshot repo,
project-event repo, analysis repo — so every suite that exercises that lineage needs the
same four fakes plus a ``graph.completed`` event and a wired writer. They live here once
rather than being re-declared per test module: a second copy drifts, and two subtly
different "fake analysis repo"s make a failure ambiguous about which behaviour is real.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from src.temporal.domain.project_event import ProjectEvent
from src.temporal.domain.project_snapshot import ProjectSnapshot


class FakeSnapshotRepo:
    """Append-only snapshot store with ``latest``/``list_since`` over one project."""

    def __init__(self, existing: list[ProjectSnapshot] | None = None) -> None:
        self.snapshots: list[ProjectSnapshot] = list(existing or [])
        self.appended: list[ProjectSnapshot] = []

    async def append_snapshot(self, snapshot: ProjectSnapshot) -> ProjectSnapshot:
        self.snapshots.append(snapshot)
        self.appended.append(snapshot)
        return snapshot

    async def latest(self, project_id: UUID, tenant_id: UUID) -> ProjectSnapshot | None:
        relevant = [s for s in self.snapshots if s.project_id == project_id]
        return max(relevant, key=lambda s: s.captured_at) if relevant else None

    async def list_since(
        self, project_id: UUID, tenant_id: UUID, since: datetime
    ) -> list[ProjectSnapshot]:
        return [
            s for s in self.snapshots if s.project_id == project_id and s.captured_at >= since
        ]


class FakeProjectStateRepo:
    """No project state — the assessment lineage is what is under test, not the state."""

    async def get(self, project_id: UUID, tenant_id: UUID) -> None:
        return None


class FakeEventRepo:
    """Tenant-scoped project-event lookup."""

    def __init__(self, events: list[ProjectEvent] | None = None) -> None:
        self.events = list(events or [])

    async def get(self, event_id: UUID, tenant_id: UUID) -> ProjectEvent | None:
        for event in self.events:
            if event.event_id == event_id and event.tenant_id == tenant_id:
                return event
        return None


class FakeAnalysisRepo:
    """``result_json`` by analysis id, recording which ids were actually requested."""

    def __init__(self, by_id: dict[UUID, dict[str, Any] | None] | None = None) -> None:
        self.by_id = dict(by_id or {})
        self.requested: list[UUID] = []

    async def get_result_json(self, analysis_id: UUID, tenant_id: UUID) -> dict[str, Any] | None:
        self.requested.append(analysis_id)
        return self.by_id.get(analysis_id)


def graph_completed_event(
    project_id: UUID, tenant_id: UUID, analysis_id: UUID
) -> ProjectEvent:
    """A ``graph.completed`` event carrying analysis_id LINEAGE ONLY (no findings)."""
    now = datetime.now(UTC).replace(tzinfo=None)
    return ProjectEvent(
        event_id=uuid4(),
        project_id=project_id,
        tenant_id=tenant_id,
        event_type="graph.completed",
        payload={"analysis_id": str(analysis_id), "document_id": "doc-1"},
        actor="analysis_graph",
        occurred_at=now,
        created_at=now,
    )


def make_writer(snapshot_repo, event_repo=None, analysis_repo=None, clock=None):
    """A real ``SnapshotWriter`` wired to the fakes above."""
    from src.temporal.application.snapshot_writer import SnapshotWriter

    return SnapshotWriter(
        project_state_repository=FakeProjectStateRepo(),
        snapshot_repository=snapshot_repo,
        event_repository=event_repo,
        analysis_repository=analysis_repo,
        clock=clock,
    )


__all__ = [
    "FakeAnalysisRepo",
    "FakeEventRepo",
    "FakeProjectStateRepo",
    "FakeSnapshotRepo",
    "graph_completed_event",
    "make_writer",
]
