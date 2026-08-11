"""SnapshotProjectionUseCase: fetch snapshots from repo, run ProjectionEngine (ADR-021)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.briefing.application.projection_engine import ProjectionEngine
from src.briefing.domain.projection import MorningBriefingProjection


@dataclass(frozen=True)
class BriefingRequest:
    project_id: UUID
    tenant_id: UUID
    since: datetime


class SnapshotProjectionUseCase:
    def __init__(self, snapshot_repository: object) -> None:
        self._repo = snapshot_repository

    async def execute(self, request: BriefingRequest) -> MorningBriefingProjection:
        snapshots = await self._repo.list_since(  # type: ignore[attr-defined]
            request.project_id, request.tenant_id, request.since
        )
        return ProjectionEngine.project(snapshots)


__all__ = ["BriefingRequest", "SnapshotProjectionUseCase"]
