"""
I9 Procurement Domain Entities
Test Suite ID: TS-I9-PROC-DOM-001
"""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ProcurementPlanItem(BaseModel):
    """Normalized procurement plan line item."""

    item_id: UUID = Field(default_factory=uuid4)
    item_name: str = Field(..., min_length=1)
    required_on_site_date: date
    optimal_order_date: date
    total_cost: Decimal = Field(..., ge=Decimal("0.00"))


class ProcurementConflict(BaseModel):
    """Conflict detected in the procurement timeline or budget posture."""

    item_id: UUID
    reason_code: str = Field(..., min_length=1)
    impact: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)

