"""Test Suite ID: TS-BCK-042-001.

List DLQ entries for admin review.
"""

from __future__ import annotations

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

    async def list_by_status(self, status: str) -> list[DLQEntryView]:
        """List DLQ entries by status across the admin-visible scope."""

    async def get_by_id(self, dlq_id: UUID) -> DLQEntryView | None:
        """Return one DLQ entry by id."""

    async def retry(self, dlq_id: UUID) -> None:
        """Schedule a DLQ entry for retry."""


class ListDLQEntriesUseCase:
    """TS-BCK-042-001: Application use case for admin DLQ listing."""

    def __init__(self, port: DLQAdminPort) -> None:
        self._port = port

    async def execute(self, *, status: str) -> list[DLQEntryView]:
        """Return DLQ entries matching the requested status."""
        return await self._port.list_by_status(status)
