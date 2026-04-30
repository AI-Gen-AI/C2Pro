"""Test Suite ID: TS-BCK-042-001.

Retry a DLQ entry from the admin surface.
"""

from __future__ import annotations

from uuid import UUID

from src.admin.application.use_cases.list_dlq_entries import DLQAdminPort, DLQEntryView


class DLQEntryNotFoundError(Exception):
    """TS-BCK-042-001: Raised when an admin retry target does not exist."""


class RetryDLQEntryUseCase:
    """TS-BCK-042-001: Application use case for manual DLQ retry."""

    def __init__(self, port: DLQAdminPort) -> None:
        self._port = port

    async def execute(self, dlq_id: UUID) -> DLQEntryView:
        """Retry an existing DLQ entry and return its original entry view."""
        entry = await self._port.get_by_id(dlq_id)
        if entry is None:
            raise DLQEntryNotFoundError(str(dlq_id))

        await self._port.retry(dlq_id)
        return entry
