"""
Shared DTOs for cross-bounded-context communication.

These are lightweight, frozen dataclasses used to transfer data
between modules without coupling to internal domain models.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from uuid import UUID


@dataclass(frozen=True)
class WBSItemDTO:
    """
    Cross-context DTO for WBS item transfer (projects -> procurement).

    Refers to Suite ID: TS-UD-PRJ-DTO-001.
    """

    id: UUID
    project_id: UUID
    code: str
    name: str
    level: int
    start_date: date
    end_date: date
    parent_id: UUID | None = None
    specifications: dict | None = None

    def __post_init__(self) -> None:
        if not 1 <= self.level <= 4:
            raise ValueError("level must be between 1 and 4")
        if not re.match(r"^\d+(\.\d+)*$", self.code):
            raise ValueError("invalid WBS code")
        if self.end_date < self.start_date:
            raise ValueError("end_date must be after or equal to start_date")
