"""
Structural protocols for entities consumed by the knowledge graph.

These protocols declare only the fields the analysis context needs,
decoupling it from the concrete domain models in documents,
procurement, and stakeholders bounded contexts.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from src.shared_kernel.enums import RACIRole


@runtime_checkable
class ClauseView(Protocol):
    id: UUID
    title: str | None
    clause_code: str


@runtime_checkable
class WBSTaskView(Protocol):
    id: UUID
    code: str
    name: str
    parent_code: str | None
    source_clause_id: UUID | None


@runtime_checkable
class StakeholderView(Protocol):
    id: UUID
    name: str | None
    role: str | None
    organization: str | None
    quadrant: object | None  # Any enum-like with .value


@runtime_checkable
class RaciAssignmentView(Protocol):
    raci_role: RACIRole
    stakeholder_id: UUID
    wbs_item_id: UUID
