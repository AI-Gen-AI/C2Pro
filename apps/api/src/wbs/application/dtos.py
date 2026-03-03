"""
WBS Application DTOs.

Refers to Suite ID: TS-CT-WBS-API-001
"""

from dataclasses import dataclass
from datetime import date
from uuid import UUID


@dataclass(frozen=True)
class WBSItemDTO:
    """DTO for WBS item responses."""

    id: UUID
    code: str
    name: str
    level: int
    description: str | None = None
    parent_id: UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    budget: dict | None = None
    completion: int = 0
    children: list[dict] = None

    def __post_init__(self):
        if self.children is None:
            object.__setattr__(self, "children", [])


@dataclass(frozen=True)
class CreateWBSItemRequest:
    """Request DTO for creating a WBS item."""

    name: str
    description: str | None = None
    parent_id: UUID | None = None
    code: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    budget_amount: float | None = None
    budget_currency: str = "EUR"
    completion: int = 0


@dataclass(frozen=True)
class UpdateWBSItemRequest:
    """Request DTO for updating a WBS item."""

    name: str | None = None
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    budget_amount: float | None = None
    budget_currency: str | None = None
    completion: int | None = None


@dataclass(frozen=True)
class MoveWBSItemRequest:
    """Request DTO for moving a WBS item."""

    new_parent_id: UUID | None


@dataclass(frozen=True)
class WBSResponse:
    """Response DTO for WBS endpoints."""

    items: list[WBSItemDTO]
    coverage: dict
    alerts: list[dict]


@dataclass(frozen=True)
class WBSCoverage:
    """Coverage information for WBS."""

    total_items: int
    items_with_budget: int
    items_with_dates: int
    items_with_alerts: int
    completion_average: float
