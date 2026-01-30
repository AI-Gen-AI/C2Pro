"""
Domain models for the Stakeholders bounded context.
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