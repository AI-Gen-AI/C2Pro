"""
Refers to Suite ID: TS-E2E-ERR-REC-001

E2E RED tests for error recovery contracts (DLQ + replay + isolation).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.core.events.dead_letter_queue import DeadLetterQueue


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_001_dlq_enqueue_contract_supports_task_id_and_attempt_metadata() -> None:
    """TS-E2E-ERR-REC-001: enqueue API must accept task_id and persist attempt metadata."""
    dlq = DeadLetterQueue()
    task_id = str(uuid4())
    payload = {"tenant_id": str(uuid4()), "document_id": str(uuid4())}

    # Expected contract for recovery suite (RED): async enqueue with task_id payload.
    message = await dlq.enqueue(task_id=task_id, payload=payload, error="timeout")  # type: ignore[attr-defined]

    assert message.task_id == task_id
    assert message.attempts == 1


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_002_replay_service_replays_oldest_message_successfully() -> None:
    """TS-E2E-ERR-REC-001: replay service must replay oldest retryable DLQ message."""
    from src.core.events.replay import DLQReplayService  # type: ignore[import-not-found]

    dlq = DeadLetterQueue()
    await dlq.enqueue(  # type: ignore[attr-defined]
        task_id=str(uuid4()),
        payload={"tenant_id": str(uuid4()), "document_id": str(uuid4())},
        error="upstream_failure",
    )

    replay = DLQReplayService(dlq=dlq)
    result = await replay.replay_next()

    assert result["status"] == "replayed"
    assert result["remaining"] == 0


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_003_non_retryable_message_is_quarantined_not_replayed() -> None:
    """TS-E2E-ERR-REC-001: non-retryable messages must go to quarantine."""
    from src.core.events.replay import DLQReplayService  # type: ignore[import-not-found]

    dlq = DeadLetterQueue()
    await dlq.enqueue(  # type: ignore[attr-defined]
        task_id=str(uuid4()),
        payload={"tenant_id": str(uuid4()), "document_id": str(uuid4())},
        error="validation_error",
        retryable=False,
    )

    replay = DLQReplayService(dlq=dlq)
    result = await replay.replay_next()

    assert result["status"] == "quarantined"
    assert result["reason"] == "non_retryable"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_004_replay_enforces_max_attempts_and_marks_permanent_failure() -> None:
    """TS-E2E-ERR-REC-001: messages over max attempts must be marked permanent_failure."""
    from src.core.events.replay import DLQReplayService  # type: ignore[import-not-found]

    dlq = DeadLetterQueue()
    await dlq.enqueue(  # type: ignore[attr-defined]
        task_id=str(uuid4()),
        payload={"tenant_id": str(uuid4()), "document_id": str(uuid4())},
        error="timeout",
        attempts=5,
    )

    replay = DLQReplayService(dlq=dlq, max_attempts=5)
    result = await replay.replay_next()

    assert result["status"] == "permanent_failure"
    assert result["code"] == "MAX_ATTEMPTS_EXCEEDED"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_005_replay_filters_by_tenant_context() -> None:
    """TS-E2E-ERR-REC-001: replay must process only messages for requested tenant."""
    from src.core.events.replay import DLQReplayService  # type: ignore[import-not-found]

    tenant_a = str(uuid4())
    tenant_b = str(uuid4())
    dlq = DeadLetterQueue()
    await dlq.enqueue(task_id=str(uuid4()), payload={"tenant_id": tenant_a}, error="err-a")  # type: ignore[attr-defined]
    await dlq.enqueue(task_id=str(uuid4()), payload={"tenant_id": tenant_b}, error="err-b")  # type: ignore[attr-defined]

    replay = DLQReplayService(dlq=dlq)
    result = await replay.replay_next(tenant_id=tenant_a)

    assert result["tenant_id"] == tenant_a
    assert result["remaining_for_tenant"] == 0


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_006_duplicate_correlation_id_is_dropped_on_replay() -> None:
    """TS-E2E-ERR-REC-001: duplicate correlation IDs must be dropped during recovery replay."""
    from src.core.events.replay import DLQReplayService  # type: ignore[import-not-found]

    correlation_id = "corr-001"
    tenant_id = str(uuid4())
    dlq = DeadLetterQueue()
    await dlq.enqueue(  # type: ignore[attr-defined]
        task_id=str(uuid4()),
        payload={"tenant_id": tenant_id, "correlation_id": correlation_id},
        error="first",
    )
    await dlq.enqueue(  # type: ignore[attr-defined]
        task_id=str(uuid4()),
        payload={"tenant_id": tenant_id, "correlation_id": correlation_id},
        error="duplicate",
    )

    replay = DLQReplayService(dlq=dlq)
    first = await replay.replay_next(tenant_id=tenant_id)
    second = await replay.replay_next(tenant_id=tenant_id)

    assert first["status"] == "replayed"
    assert second["status"] == "dropped_duplicate"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_007_replay_failure_requeues_with_incremented_attempts() -> None:
    """TS-E2E-ERR-REC-001: failed replay should requeue message with attempts+1."""
    from src.core.events.replay import DLQReplayService  # type: ignore[import-not-found]

    dlq = DeadLetterQueue()
    task_id = str(uuid4())
    await dlq.enqueue(task_id=task_id, payload={"tenant_id": str(uuid4())}, error="initial")  # type: ignore[attr-defined]

    replay = DLQReplayService(dlq=dlq)
    result = await replay.replay_next(force_fail=True)

    assert result["status"] == "requeued"
    assert result["attempts"] == 2


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_008_replay_emits_structured_audit_event() -> None:
    """TS-E2E-ERR-REC-001: successful replay must emit structured audit event."""
    from src.core.events.replay import DLQReplayService  # type: ignore[import-not-found]

    dlq = DeadLetterQueue()
    task_id = str(uuid4())
    tenant_id = str(uuid4())
    await dlq.enqueue(task_id=task_id, payload={"tenant_id": tenant_id}, error="recoverable")  # type: ignore[attr-defined]

    replay = DLQReplayService(dlq=dlq)
    result = await replay.replay_next()

    assert result["audit_event"]["type"] == "dlq_replay"
    assert result["audit_event"]["task_id"] == task_id
    assert result["audit_event"]["tenant_id"] == tenant_id

