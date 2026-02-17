"""
Dead-letter replay service.

Refers to Suite ID: TS-E2E-ERR-REC-001.
"""

from __future__ import annotations

from typing import Any

from src.core.events.dead_letter_queue import DeadLetterQueue


class DLQReplayService:
    """Minimal replay coordinator for DLQ recovery flows."""

    def __init__(self, *, dlq: DeadLetterQueue, max_attempts: int = 5) -> None:
        self._dlq = dlq
        self._max_attempts = max_attempts
        self._seen_correlation_ids_by_tenant: dict[str, set[str]] = {}

    async def replay_next(
        self,
        *,
        tenant_id: str | None = None,
        force_fail: bool = False,
    ) -> dict[str, Any]:
        """
        Replay one message honoring retryability, tenant filtering, and idempotency.
        """
        messages = self._dlq.list()
        selected = None
        for message in messages:
            message_tenant = str(message.payload.get("tenant_id", ""))
            if tenant_id is not None and message_tenant != tenant_id:
                continue
            selected = message
            break

        if selected is None:
            return {"status": "empty"}

        # Remove the selected message from queue.
        remaining = [msg for msg in messages if msg.message_id != selected.message_id]
        self._dlq._messages = remaining  # noqa: SLF001 - local in-memory adapter contract

        if not selected.retryable:
            return {"status": "quarantined", "reason": "non_retryable"}

        if selected.attempts >= self._max_attempts:
            return {"status": "permanent_failure", "code": "MAX_ATTEMPTS_EXCEEDED"}

        message_tenant = str(selected.payload.get("tenant_id", ""))
        correlation_id = selected.payload.get("correlation_id")
        if correlation_id:
            seen = self._seen_correlation_ids_by_tenant.setdefault(message_tenant, set())
            if str(correlation_id) in seen:
                return {"status": "dropped_duplicate"}
            seen.add(str(correlation_id))

        if force_fail:
            await self._dlq.enqueue(
                task_id=selected.task_id or "unknown-task",
                payload=selected.payload,
                error=selected.reason,
                retryable=selected.retryable,
                attempts=selected.attempts + 1,
            )
            return {"status": "requeued", "attempts": selected.attempts + 1}

        remaining_all = await self._dlq.size()
        remaining_for_tenant = len(
            [msg for msg in self._dlq.list() if str(msg.payload.get("tenant_id", "")) == message_tenant]
        )
        return {
            "status": "replayed",
            "remaining": remaining_all,
            "tenant_id": message_tenant,
            "remaining_for_tenant": remaining_for_tenant,
            "audit_event": {
                "type": "dlq_replay",
                "task_id": selected.task_id,
                "tenant_id": message_tenant,
            },
        }

