"""
I10 Stakeholders Domain Entities
Test Suite ID: TS-I10-STKH-DOM-001
"""

from enum import Enum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class RACIRole(str, Enum):
    RESPONSIBLE = "Responsible"
    ACCOUNTABLE = "Accountable"
    CONSULTED = "Consulted"
    INFORMED = "Informed"


class Stakeholder(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., min_length=1)
    canonical_id: UUID
    aliases: set[str] = Field(default_factory=set)
    confidence: float = Field(..., ge=0.0, le=1.0)
    ambiguity_flag: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class PartyResolutionResult(BaseModel):
    original_name: str
    resolved_stakeholder_id: UUID | None = None
    canonical_id: UUID
    ambiguity_flag: bool = False
    action: Literal["new", "merged", "new_with_canonical"]
    warning_message: str | None = None


class RACIResponsibility(BaseModel):
    stakeholder_id: UUID
    role: RACIRole
    confidence: float = Field(..., ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RACIActivity(BaseModel):
    activity_id: UUID = Field(default_factory=uuid4)
    description: str = Field(..., min_length=1)
    responsibilities: list[RACIResponsibility] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

