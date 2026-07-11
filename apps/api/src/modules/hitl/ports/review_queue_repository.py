"""
I11 HITL review queue repository port.
Test Suite ID: TS-I11-HITL-PORT-001
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.modules.hitl.domain.entities import ReviewItem, ReviewStatus


class IReviewQueueRepository(Protocol):
    async def add_review_item(self, item: ReviewItem) -> UUID: ...

    async def get_review_item(self, item_id: UUID) -> ReviewItem | None: ...

    async def update_review_item(self, item: ReviewItem) -> None: ...

    async def get_overdue_items(self) -> list[ReviewItem]: ...

    async def list_by_status(
        self,
        status: ReviewStatus | None = None,
        *,
        skip: int = 0,
        limit: int = 50,
        project_id: UUID | None = None,
    ) -> list[ReviewItem]: ...

    async def count_by_status(
        self,
        status: ReviewStatus | None = None,
        *,
        project_id: UUID | None = None,
    ) -> int: ...
