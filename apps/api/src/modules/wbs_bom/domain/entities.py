"""
I8 WBS/BOM Domain Entities
Test Suite ID: TS-I8-WBS-BOM-DOM-001
"""

from uuid import UUID

from pydantic import BaseModel, Field


class WBSItem(BaseModel):
    """Represents a work-breakdown-structure node with clause traceability."""

    wbs_id: UUID
    code: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    level: int = Field(..., ge=1)
    clause_id: UUID | None = None
    parent_wbs_id: UUID | None = None


class BOMItem(BaseModel):
    """Represents a bill-of-materials line linked to a WBS item and clause."""

    bom_id: UUID
    wbs_id: UUID
    description: str = Field(..., min_length=1)
    quantity: float = Field(..., gt=0.0)
    unit_cost: float = Field(..., ge=0.0)
    clause_id: UUID | None = None

