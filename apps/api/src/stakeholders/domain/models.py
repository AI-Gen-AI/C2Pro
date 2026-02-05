"""
Domain models for the Stakeholders bounded context.

Refers to Suite ID: TS-UD-STK-ENT-001.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID


class PowerLevel(str, Enum):
    """Level of power of the stakeholder."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class InterestLevel(str, Enum):
    """Level of interest of the stakeholder."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class StakeholderQuadrant(str, Enum):
    """Power/interest quadrant (Mendelow Matrix)."""
    KEY_PLAYER = "key_player"  # high/high
    KEEP_SATISFIED = "keep_satisfied"  # high/low
    KEEP_INFORMED = "keep_informed"  # low/high
    MONITOR = "monitor"  # low/low


class RACIRole(str, Enum):
    """RACI roles."""
    RESPONSIBLE = "R"
    ACCOUNTABLE = "A"
    CONSULTED = "C"
    INFORMED = "I"


@dataclass
class Stakeholder:
    """
    Represents a Stakeholder as a pure domain entity.
    """
    id: UUID
    project_id: UUID
    power_level: PowerLevel
    interest_level: InterestLevel
    approval_status: str # Assuming approval_status is string for now, enum to be defined later if needed
    created_at: datetime
    updated_at: datetime
    name: str | None = None
    role: str | None = None
    organization: str | None = None
    department: str | None = None
    quadrant: StakeholderQuadrant | None = None
    email: str | None = None
    phone: str | None = None
    source_clause_id: UUID | None = None
    extracted_from_document_id: UUID | None = None
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    review_comment: str | None = None
    stakeholder_metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.project_id is None:
            raise ValueError("project_id is required")
        if self.name is None or not self.name.strip():
            raise ValueError("name is required")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be before created_at")

        clause_adjusted = self.source_clause_id is not None and self.power_level == PowerLevel.LOW
        if clause_adjusted:
            self.power_level = PowerLevel.MEDIUM

        if self.quadrant is None:
            if clause_adjusted:
                self.quadrant = StakeholderQuadrant.KEEP_SATISFIED
            else:
                self.quadrant = _derive_quadrant(self.power_level, self.interest_level)


    def is_key_player(self) -> bool:
        return self.quadrant == StakeholderQuadrant.KEY_PLAYER

    def has_clause_reference(self) -> bool:
        return self.source_clause_id is not None


@dataclass
class RaciAssignment:
    """
    Represents a RACI assignment as a pure domain entity.
    """
    id: UUID
    project_id: UUID
    stakeholder_id: UUID
    wbs_item_id: UUID
    raci_role: RACIRole
    created_at: datetime
    evidence_text: str | None = None
    generated_automatically: bool = True
    manually_verified: bool = False
    verified_by: UUID | None = None
    verified_at: datetime | None = None

    def is_verified(self) -> bool:
        return self.manually_verified and self.verified_at is not None


def _derive_quadrant(power_level: PowerLevel, interest_level: InterestLevel) -> StakeholderQuadrant:
    if power_level == PowerLevel.HIGH and interest_level == InterestLevel.HIGH:
        return StakeholderQuadrant.KEY_PLAYER
    if power_level == PowerLevel.HIGH and interest_level != InterestLevel.HIGH:
        return StakeholderQuadrant.KEEP_SATISFIED
    if power_level != PowerLevel.HIGH and interest_level == InterestLevel.HIGH:
        return StakeholderQuadrant.KEEP_INFORMED
    return StakeholderQuadrant.MONITOR
