"""TS-E2E-ERR-REC-001: DLQ replay branch coverage — tenant filtering edge cases."""

from __future__ import annotations

import pytest

from src.core.events.dead_letter_queue import DeadLetterQueue
from src.core.events.replay import DLQReplayService


@pytest.fixture
def dlq() -> DeadLetterQueue:
    return DeadLetterQueue()


@pytest.fixture
def replay_service(dlq: DeadLetterQueue) -> DLQReplayService:
    return DLQReplayService(dlq=dlq)


@pytest.mark.asyncio
async def test_empty_queue_after_tenant_filtering(
    replay_service: DLQReplayService, dlq: DeadLetterQueue
) -> None:
    """One message with tenant-A, filtered by tenant-B → selected=None → {"status": "empty"}."""
    dlq.push(
        topic="recovery",
        payload={"tenant_id": "tenant-A"},
        reason="test error",
    )

    result = await replay_service.replay_next(tenant_id="tenant-B")

    assert result == {"status": "empty"}


@pytest.mark.asyncio
async def test_tenant_filter_skips_mismatched(
    replay_service: DLQReplayService, dlq: DeadLetterQueue
) -> None:
    """Messages with wrong tenant → loop skips all, selected stays None."""
    dlq.push(
        topic="recovery",
        payload={"tenant_id": "tenant-A"},
        reason="test error",
    )
    dlq.push(
        topic="recovery",
        payload={"tenant_id": "tenant-A"},
        reason="another error",
    )

    result = await replay_service.replay_next(tenant_id="tenant-B")

    assert result == {"status": "empty"}
    assert len(dlq.list_messages()) == 2
