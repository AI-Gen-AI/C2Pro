"""Test Suite ID: TS-BCK-042-001.

List DLQ entries for admin review.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


class DLQEntryView(Protocol):
    """TS-BCK-042-001: Read shape required by the admin DLQ endpoints."""

    id: UUID
    tenant_id: UUID
    task_type: str
    document_id: UUID | None
    payload_json: dict[str, Any]
    error_message: str
    error_traceback: str | None
    retry_count: int
    max_retries: int
    status: str
    created_at: datetime
    updated_at: datetime
    next_retry_at: datetime | None


class DLQAdminPort(Protocol):
    """TS-BCK-042-001: Port for admin DLQ read/retry operations."""

    async def list_by_status(
        self, status: str, *, limit: int, offset: int
    ) -> list[DLQEntryView]:
        """List DLQ entries by status across the admin-visible scope (paginated)."""

    async def count_by_status(self, status: str) -> int:
        """Return the total count of DLQ entries for the given status."""

    async def get_by_id(self, dlq_id: UUID) -> DLQEntryView | None:
        """Return one DLQ entry by id."""

    async def retry(self, dlq_id: UUID) -> None:
        """Schedule a DLQ entry for retry."""


@dataclass
class DLQPageResult:
    """TS-BCK-042-001: Paginated result returned by ListDLQEntriesUseCase."""

    entries: list[DLQEntryView]
    total: int
    limit: int
    offset: int

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.entries) < self.total


class ListDLQEntriesUseCase:
    """TS-BCK-042-001: Application use case for admin DLQ listing."""

    def __init__(self, port: DLQAdminPort) -> None:
        self._port = port

    async def execute(
        self, *, status: str, limit: int, offset: int
    ) -> DLQPageResult:
        """Return a paginated page of DLQ entries matching the requested status.

        Two separate queries are issued: one for the page (with LIMIT/OFFSET)
        and one SELECT COUNT(*) for the total. This avoids loading all rows
        into memory and keeps the query plan simple. A window function would
        avoid the round-trip but adds query complexity for a low-traffic admin
        endpoint where simplicity wins.
        """
        entries = await self._port.list_by_status(status, limit=limit, offset=offset)
        total = await self._port.count_by_status(status)
        return DLQPageResult(entries=entries, total=total, limit=limit, offset=offset)
