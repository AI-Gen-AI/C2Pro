"""ProjectEvent append-only log contract (ADR-015 / TASK-V3-015-03)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.evidence.domain.runtime_trust import EvidenceRef
from src.temporal.domain.event_type import validate_event_type


class ProjectEvent(BaseModel):
    """Immutable temporal event emitted by project-state producers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: UUID
    project_id: UUID
    tenant_id: UUID
    event_type: str
    payload: dict[str, Any]
    actor: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    source_revision_id: UUID | None = None
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    occurred_at: datetime
    created_at: datetime

    @field_validator("event_type")
    @classmethod
    def _validate_event_type(cls, value: str) -> str:
        return validate_event_type(value)


__all__ = ["ProjectEvent"]
