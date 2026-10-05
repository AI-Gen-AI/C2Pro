"""Impact read contracts for temporal changes (PR-C2).

Resolution state is separate from impacted entities: an ``ImpactItem`` exists
only for a defensible target entity, and an UNKNOWN assessment carries no
items and no confidence -- nothing is fabricated to fill the shape.

``EpistemicBasis`` keeps fact, derivation and projection apart in every read
model: an observed change, a derived impact and a projected consequence are
never presented as the same kind of truth.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.temporal.domain.entity_ref import TemporalEntityRef


class EpistemicBasis(StrEnum):
    OBSERVED = "observed"  # source/revision facts
    DERIVED = "derived"  # inferred from persisted relationships
    PROJECTED = "projected"  # hypothetical consequence of an uncommitted state
    TRUSTED = "trusted"  # canonical accepted project state


class ImpactStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    CANDIDATE = "CANDIDATE"
    UNKNOWN = "UNKNOWN"


_FROZEN = ConfigDict(extra="forbid", frozen=True)


class ImpactTarget(BaseModel):
    """A persisted project entity that depends on the changed source entity."""

    model_config = _FROZEN

    entity_type: str
    entity_id: UUID
    label: str | None = None
    # The target's own persisted lifecycle status, reported, never changed.
    status: str | None = None
    # Read-time only: the target's basis was affected by a newer revision.
    # None when staleness is not assessed for this entity type.
    potentially_stale: bool | None = None


class ImpactRelationship(BaseModel):
    model_config = _FROZEN

    kind: Literal["direct", "indirect"]
    via: str  # the persisted link that supports it, e.g. "alerts.source_clause_id"
    link_confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class ImpactItem(BaseModel):
    model_config = _FROZEN

    target: ImpactTarget
    relationship: ImpactRelationship
    status: Literal[ImpactStatus.CONFIRMED, ImpactStatus.CANDIDATE]
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class ImpactAssessment(BaseModel):
    model_config = _FROZEN

    status: ImpactStatus
    items: list[ImpactItem] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    reason: str | None = None
    basis: EpistemicBasis = EpistemicBasis.DERIVED

    @model_validator(mode="after")
    def _unknown_carries_nothing(self) -> ImpactAssessment:
        if self.status is ImpactStatus.UNKNOWN and (self.items or self.confidence is not None):
            raise ValueError("an UNKNOWN impact assessment carries no items and no confidence")
        if self.status is not ImpactStatus.UNKNOWN and not self.items:
            raise ValueError(
                "a CONFIRMED or CANDIDATE assessment needs at least one impacted entity"
            )
        return self


class ChangeImpact(BaseModel):
    """The impact of one change within a stored change event."""

    model_config = _FROZEN

    change_index: int = Field(ge=0)
    change_type: str
    source: TemporalEntityRef
    assessment: ImpactAssessment


__all__ = [
    "ChangeImpact",
    "EpistemicBasis",
    "ImpactAssessment",
    "ImpactItem",
    "ImpactRelationship",
    "ImpactStatus",
    "ImpactTarget",
]
