"""ProjectSnapshot append-only read-model contract (ADR-015 / TASK-V3-015-04)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SnapshotTrigger(StrEnum):
    REVISION_INGESTED = "revision_ingested"
    GRAPH_COMPLETED = "graph_completed"
    HITL_CORRECTION = "hitl_correction"
    SCHEDULED = "scheduled"
    BASELINE_CHANGED = "baseline_changed"


class ProjectSnapshot(BaseModel):
    """Immutable materialized temporal snapshot supplied by application callers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_id: UUID
    project_id: UUID
    tenant_id: UUID
    captured_at: datetime
    trigger: SnapshotTrigger
    health_vector: dict[str, Any]
    coherence_subscore: float | None = None
    counts: dict[str, Any] = Field(default_factory=dict)
    totals: dict[str, Any] = Field(default_factory=dict)
    source_event_id: UUID | None = None
    created_at: datetime


__all__ = ["ProjectSnapshot", "SnapshotTrigger"]
