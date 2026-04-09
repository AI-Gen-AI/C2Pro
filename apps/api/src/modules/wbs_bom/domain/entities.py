"""
WBS/BOM generation domain entities.

Refers to Test Suite IDs: TS-I8-WBS-BOM-DOM-001, TS-I8-WBS-BOM-APP-001.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class WBSItem:
    """Traceable WBS item generated from extracted clauses."""

    wbs_id: UUID
    code: str
    name: str
    level: int
    clause_id: UUID | None
    parent_wbs_id: UUID | None = None


@dataclass(frozen=True)
class BOMItem:
    """Traceable BOM item generated from extracted clauses."""

    bom_id: UUID
    wbs_id: UUID
    description: str
    quantity: float
    unit_cost: float
    clause_id: UUID | None
