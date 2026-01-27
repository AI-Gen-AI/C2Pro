"""
Pydantic schemas for the WBS (Work Breakdown Structure) module.
"""

from __future__ import annotations
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field

# Assuming WBSItemType is defined elsewhere and can be imported
# For now, let's create a placeholder if it's not easily accessible
from src.procurement.adapters.persistence.models import WBSItemType


class WBSNodeBase(BaseModel):
    """Base schema for a WBS node."""
    name: str = Field(..., description="Name of the WBS item.")
    wbs_code: str = Field(..., description="Unique code for the WBS item (e.g., '1.2.1').")
    description: Optional[str] = Field(None, description="Detailed description of the WBS item.")
    item_type: Optional[WBSItemType] = Field(None, description="Type of the WBS item.")
    
    class Config:
        orm_mode = True


class WBSNodeCreate(WBSNodeBase):
    """Schema for creating a new WBS node."""
    project_id: UUID
    parent_id: Optional[UUID] = None


class WBSNode(WBSNodeBase):
    """Recursive schema for a WBS node, including its children."""
    id: UUID
    children: List[WBSNode] = []


# This is crucial for Pydantic to handle the recursive self-referencing `List[WBSNode]`
WBSNode.update_forward_refs()

class WBSNodeUpdate(BaseModel):
    """Schema for updating a WBS node."""
    name: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[UUID] = None
