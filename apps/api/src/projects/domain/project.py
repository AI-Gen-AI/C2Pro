"""
C2Pro - Projects Domain Model

Domain Entity for Project aggregate.
Minimal implementation for TS-E2E-SEC-TNT-001.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class Project(BaseModel):
    """
    Project Domain Entity.

    Minimal implementation to pass E2E security tests.
    """

    id: UUID
    tenant_id: UUID
    name: str
    code: str
    project_type: str
    estimated_budget: Decimal
    currency: str = "EUR"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True
