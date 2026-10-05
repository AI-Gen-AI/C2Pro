"""Generic reference to a revision-bound project entity (ADR-014 / PR-C2).

Mirrors the provenance fields of ADR-014 ``ProjectEntity`` (source revision +
evidence) for read models. A clause is one ``entity_type``; schedule
activities, milestones, budget items or specification sections use the same
shape, so no temporal contract assumes every source is a clause.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.change_intelligence.domain.contracts import ObjectType
from src.evidence.domain.runtime_trust import EvidenceRef


class TemporalEntityRef(BaseModel):
    """One entity as it existed in one artifact revision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    # DocumentType value of the source artifact (contract, schedule, budget...).
    artifact_type: str | None
    document_id: UUID
    revision_id: UUID
    entity_type: ObjectType
    # Persisted id of the entity in that revision; None when it was never persisted.
    entity_id: str | None
    evidence: list[EvidenceRef] = Field(default_factory=list)


__all__ = ["TemporalEntityRef"]
