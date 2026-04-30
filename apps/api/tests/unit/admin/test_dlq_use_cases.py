"""Test Suite ID: TS-BCK-042-001.

Unit coverage for DLQ admin use cases.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.admin.application.use_cases.list_dlq_entries import ListDLQEntriesUseCase
from src.admin.application.use_cases.retry_dlq_entry import (
    DLQEntryNotFoundError,
    RetryDLQEntryUseCase,
)


@dataclass(slots=True)
class _DLQEntry:
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


class _FakeDLQPort:
    def __init__(self) -> None:
        self.entry = _DLQEntry(
            id=uuid4(),
            tenant_id=uuid4(),
            task_type="document_analysis",
            document_id=None,
            payload_json={"document_id": str(uuid4())},
            error_message="analysis failed",
            error_traceback=None,
            retry_count=1,
            max_retries=3,
            status="pending",
            created_at=datetime(2026, 4, 28, tzinfo=UTC),
            updated_at=datetime(2026, 4, 28, tzinfo=UTC),
            next_retry_at=None,
        )
        self.list_status: str | None = None
        self.retry_ids: list[UUID] = []

    async def list_by_status(self, status: str) -> list[_DLQEntry]:
        self.list_status = status
        return [self.entry]

    async def get_by_id(self, dlq_id: UUID) -> _DLQEntry | None:
        return self.entry if dlq_id == self.entry.id else None

    async def retry(self, dlq_id: UUID) -> None:
        self.retry_ids.append(dlq_id)


@pytest.mark.asyncio
async def test_list_dlq_entries_returns_entries_for_requested_status() -> None:
    """TS-BCK-042-001: list use case delegates status filtering to the admin DLQ port."""
    port = _FakeDLQPort()
    use_case = ListDLQEntriesUseCase(port)

    result = await use_case.execute(status="pending")

    assert result == [port.entry]
    assert port.list_status == "pending"


@pytest.mark.asyncio
async def test_retry_dlq_entry_retries_existing_entry() -> None:
    """TS-BCK-042-001: retry use case verifies the entry exists before retrying it."""
    port = _FakeDLQPort()
    use_case = RetryDLQEntryUseCase(port)

    result = await use_case.execute(port.entry.id)

    assert result == port.entry
    assert port.retry_ids == [port.entry.id]


@pytest.mark.asyncio
async def test_retry_dlq_entry_raises_for_missing_entry() -> None:
    """TS-BCK-042-001: retry use case reports missing DLQ entries without retrying."""
    port = _FakeDLQPort()
    use_case = RetryDLQEntryUseCase(port)
    missing_id = uuid4()

    with pytest.raises(DLQEntryNotFoundError):
        await use_case.execute(missing_id)

    assert port.retry_ids == []
