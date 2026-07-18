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
    @property
    def id(self) -> UUID: ...

    @property
    def title(self) -> str | None: ...

    @property
    def clause_code(self) -> str: ...


@runtime_checkable
class WBSTaskView(Protocol):
    @property
    def id(self) -> UUID: ...

    @property
    def code(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def parent_code(self) -> str | None: ...

    @property
    def source_clause_id(self) -> UUID | None: ...


@runtime_checkable
class StakeholderView(Protocol):
    @property
    def id(self) -> UUID: ...

    @property
    def name(self) -> str | None: ...

    @property
    def role(self) -> str | None: ...

    @property
    def organization(self) -> str | None: ...

    @property
    def quadrant(self) -> object | None: ...  # Any enum-like with .value


@runtime_checkable
class RaciAssignmentView(Protocol):
    @property
    def raci_role(self) -> RACIRole: ...

    @property
    def stakeholder_id(self) -> UUID: ...

    @property
    def wbs_item_id(self) -> UUID: ...
