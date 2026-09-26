"""Portfolio R/A/G rollup domain models (ADR-021, TASK-V3-021-03)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class RagStatus(StrEnum):
    GREEN = "green"
    AMBER = "amber"
    RED = "red"


@dataclass(frozen=True)
class ProjectRollupEntry:
    project_id: UUID
    rag_status: RagStatus
    overall_health: float
    open_action_items: int
    snapshot_count: int
    latest_snapshot_at: datetime


@dataclass(frozen=True)
class PortfolioRollup:
    tenant_id: UUID
    generated_at: datetime
    entries: tuple[ProjectRollupEntry, ...]

    @property
    def counts_by_rag(self) -> dict[RagStatus, int]:
        result: dict[RagStatus, int] = {}
        for entry in self.entries:
            result[entry.rag_status] = result.get(entry.rag_status, 0) + 1
        return result


__all__ = ["PortfolioRollup", "ProjectRollupEntry", "RagStatus"]
