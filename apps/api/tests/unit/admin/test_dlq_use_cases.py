"""Test Suite ID: TS-BCK-042-001.

Unit coverage for DLQ admin use cases.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.admin.application.use_cases.list_dlq_entries import (
    DLQPageResult,
    ListDLQEntriesUseCase,
)
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
    def __init__(self, entries: list[_DLQEntry] | None = None) -> None:
        self._entries = entries or [
            _DLQEntry(
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
        ]
        self.entry = self._entries[0]
        self.list_calls: list[dict[str, Any]] = []
        self.retry_ids: list[UUID] = []

    async def list_by_status(
        self, status: str, *, limit: int, offset: int
    ) -> list[_DLQEntry]:
        self.list_calls.append({"status": status, "limit": limit, "offset": offset})
        matching = [e for e in self._entries if e.status == status]
        return matching[offset : offset + limit]

    async def count_by_status(self, status: str) -> int:
        return sum(1 for e in self._entries if e.status == status)

    async def get_by_id(self, dlq_id: UUID) -> _DLQEntry | None:
        return next((e for e in self._entries if e.id == dlq_id), None)

    async def retry(self, dlq_id: UUID) -> None:
        self.retry_ids.append(dlq_id)


# ---------------------------------------------------------------------------
# List use case
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_dlq_entries_returns_entries_for_requested_status() -> None:
    """TS-BCK-042-001: list use case delegates status filtering to the admin DLQ port."""
    port = _FakeDLQPort()
    use_case = ListDLQEntriesUseCase(port)

    result = await use_case.execute(status="pending", limit=50, offset=0)

    assert isinstance(result, DLQPageResult)
    assert result.entries == [port.entry]
    assert port.list_calls[0]["status"] == "pending"


@pytest.mark.asyncio
async def test_list_returns_pagination_metadata() -> None:
    """TS-BCK-042-001: execute returns total, limit, offset, and has_more."""
    port = _FakeDLQPort()
    use_case = ListDLQEntriesUseCase(port)

    result = await use_case.execute(status="pending", limit=10, offset=0)

    assert result.total == 1
    assert result.limit == 10
    assert result.offset == 0
    assert result.has_more is False


@pytest.mark.asyncio
async def test_list_has_more_is_true_when_page_does_not_exhaust_total() -> None:
    """TS-BCK-042-001: has_more=True when offset+page_size < total."""
    entries = [
        _DLQEntry(
            id=uuid4(),
            tenant_id=uuid4(),
            task_type="doc",
            document_id=None,
            payload_json={},
            error_message="err",
            error_traceback=None,
            retry_count=0,
            max_retries=3,
            status="pending",
            created_at=datetime(2026, 4, 28, tzinfo=UTC),
            updated_at=datetime(2026, 4, 28, tzinfo=UTC),
            next_retry_at=None,
        )
        for _ in range(5)
    ]
    port = _FakeDLQPort(entries=entries)
    use_case = ListDLQEntriesUseCase(port)

    result = await use_case.execute(status="pending", limit=2, offset=0)

    assert len(result.entries) == 2
    assert result.total == 5
    assert result.has_more is True


@pytest.mark.asyncio
async def test_list_limit_1_returns_single_entry() -> None:
    """TS-BCK-042-001: limit=1 boundary — only one entry returned."""
    entries = [
        _DLQEntry(
            id=uuid4(),
            tenant_id=uuid4(),
            task_type="doc",
            document_id=None,
            payload_json={},
            error_message="err",
            error_traceback=None,
            retry_count=0,
            max_retries=3,
            status="pending",
            created_at=datetime(2026, 4, 28, tzinfo=UTC),
            updated_at=datetime(2026, 4, 28, tzinfo=UTC),
            next_retry_at=None,
        )
        for _ in range(3)
    ]
    port = _FakeDLQPort(entries=entries)
    use_case = ListDLQEntriesUseCase(port)

    result = await use_case.execute(status="pending", limit=1, offset=0)

    assert len(result.entries) == 1
    assert result.total == 3
    assert result.has_more is True


@pytest.mark.asyncio
async def test_list_limit_500_boundary() -> None:
    """TS-BCK-042-001: limit=500 boundary — returns all when total < 500."""
    entries = [
        _DLQEntry(
            id=uuid4(),
            tenant_id=uuid4(),
            task_type="doc",
            document_id=None,
            payload_json={},
            error_message="err",
            error_traceback=None,
            retry_count=0,
            max_retries=3,
            status="pending",
            created_at=datetime(2026, 4, 28, tzinfo=UTC),
            updated_at=datetime(2026, 4, 28, tzinfo=UTC),
            next_retry_at=None,
        )
        for _ in range(10)
    ]
    port = _FakeDLQPort(entries=entries)
    use_case = ListDLQEntriesUseCase(port)

    result = await use_case.execute(status="pending", limit=500, offset=0)

    assert len(result.entries) == 10
    assert result.total == 10
    assert result.has_more is False


@pytest.mark.asyncio
async def test_list_offset_past_total_returns_empty() -> None:
    """TS-BCK-042-001: offset past total returns empty entries but correct total."""
    port = _FakeDLQPort()
    use_case = ListDLQEntriesUseCase(port)

    result = await use_case.execute(status="pending", limit=50, offset=999)

    assert result.entries == []
    assert result.total == 1
    assert result.has_more is False


@pytest.mark.asyncio
async def test_list_default_values_applied() -> None:
    """TS-BCK-042-001: callers must pass limit/offset explicitly (no defaults in use case)."""
    port = _FakeDLQPort()
    use_case = ListDLQEntriesUseCase(port)

    await use_case.execute(status="pending", limit=50, offset=0)

    call = port.list_calls[0]
    assert call["limit"] == 50
    assert call["offset"] == 0


# ---------------------------------------------------------------------------
# Retry use case
# ---------------------------------------------------------------------------


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
