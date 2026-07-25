"""TS-E2E-ERR-REC-001: Unit tests for DLQReplayService dead-letter replay flows."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.core.events.dead_letter_queue import DeadLetterQueue, DLQMessage
from src.core.events.replay import DLQReplayService


def _make_msg(
    *,
    message_id: str | None = None,
    payload: dict | None = None,
    retryable: bool = True,
    attempts: int = 1,
    reason: str = "test-error",
    task_id: str | None = "task-1",
    topic: str = "recovery",
) -> DLQMessage:
    return DLQMessage(
        message_id=uuid4() if message_id is None else uuid4(),
        topic=topic,
        payload=payload or {},
        reason=reason,
        created_at=datetime.now(UTC),
        retryable=retryable,
        attempts=attempts,
        task_id=task_id,
    )


@pytest.mark.asyncio
async def test_empty_queue_returns_empty_status() -> None:
    dlq = DeadLetterQueue()
    dlq._messages = []  # noqa: SLF001
    service = DLQReplayService(dlq=dlq)

    result = await service.replay_next()

    assert result == {"status": "empty"}


@pytest.mark.asyncio
async def test_non_retryable_returns_quarantined() -> None:
    dlq = DeadLetterQueue()
    dlq._messages = [_make_msg(retryable=False, attempts=1)]  # noqa: SLF001
    service = DLQReplayService(dlq=dlq)

    result = await service.replay_next()

    assert result == {"status": "quarantined", "reason": "non_retryable"}


@pytest.mark.asyncio
async def test_max_attempts_returns_permanent_failure() -> None:
    dlq = DeadLetterQueue()
    dlq._messages = [_make_msg(retryable=True, attempts=5)]  # noqa: SLF001
    service = DLQReplayService(dlq=dlq, max_attempts=5)

    result = await service.replay_next()

    assert result == {"status": "permanent_failure", "code": "MAX_ATTEMPTS_EXCEEDED"}


@pytest.mark.asyncio
async def test_duplicate_correlation_drops() -> None:
    dlq = DeadLetterQueue()
    dlq.enqueue = AsyncMock(return_value=None)
    dlq.size = AsyncMock(return_value=1)
    corr_id = "corr-abc"
    msg_a = _make_msg(payload={"tenant_id": "t1", "correlation_id": corr_id})
    msg_b = _make_msg(payload={"tenant_id": "t1", "correlation_id": corr_id})
    dlq._messages = [msg_a]  # noqa: SLF001
    service = DLQReplayService(dlq=dlq)

    result_first = await service.replay_next()
    assert result_first["status"] == "replayed"

    dlq._messages = [msg_b]  # noqa: SLF001
    result_second = await service.replay_next()
    assert result_second == {"status": "dropped_duplicate"}


@pytest.mark.asyncio
async def test_force_fail_requeues() -> None:
    dlq = DeadLetterQueue()
    dlq.enqueue = AsyncMock(return_value=None)
    dlq.size = AsyncMock(return_value=0)
    msg = _make_msg(retryable=True, attempts=0, task_id="task-fail", payload={"tenant_id": "t1"})
    dlq._messages = [msg]  # noqa: SLF001
    service = DLQReplayService(dlq=dlq)

    result = await service.replay_next(force_fail=True)

    assert result["status"] == "requeued"
    assert result["attempts"] == 1
    dlq.enqueue.assert_awaited_once()


@pytest.mark.asyncio
async def test_successful_replay() -> None:
    dlq = DeadLetterQueue()
    dlq.enqueue = AsyncMock(return_value=None)
    dlq.size = AsyncMock(return_value=0)
    msg = _make_msg(retryable=True, attempts=0, task_id="task-ok", payload={"tenant_id": "t1"})
    dlq._messages = [msg]  # noqa: SLF001
    service = DLQReplayService(dlq=dlq)

    result = await service.replay_next()

    assert result["status"] == "replayed"
    assert result["remaining"] == 0
    assert result["tenant_id"] == "t1"
    assert "audit_event" in result
    assert result["audit_event"]["type"] == "dlq_replay"


@pytest.mark.asyncio
async def test_tenant_filtering() -> None:
    dlq = DeadLetterQueue()
    dlq.enqueue = AsyncMock(return_value=None)
    dlq.size = AsyncMock(return_value=0)
    msg_tenant_b = _make_msg(payload={"tenant_id": "tenant-B"})
    dlq._messages = [msg_tenant_b]  # noqa: SLF001
    service = DLQReplayService(dlq=dlq)

    result = await service.replay_next(tenant_id="tenant-A")

    assert result == {"status": "empty"}
