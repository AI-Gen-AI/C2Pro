"""
In-memory dead letter queue for failed events/jobs.

Refers to Suite ID: TS-INT-EVT-DLQ-001.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass(frozen=True)
class DLQMessage:
    """Dead letter queue message payload."""

    message_id: UUID
    topic: str
    payload: dict[str, Any]
    reason: str
    created_at: datetime
    retryable: bool = True
    attempts: int = 1
    task_id: str | None = None


class DeadLetterQueue:
    """Simple in-memory DLQ adapter."""

    def __init__(self, max_size: int = 10_000) -> None:
        self._max_size = max_size
        self._messages: list[DLQMessage] = []

    def push(
        self,
        topic: str,
        payload: dict[str, Any],
        reason: str,
        retryable: bool = True,
        attempts: int = 1,
        task_id: str | None = None,
    ) -> DLQMessage:
        if len(self._messages) >= self._max_size:
            self._messages.pop(0)
        message = DLQMessage(
            message_id=uuid4(),
            topic=topic,
            payload=payload,
            reason=reason,
            created_at=datetime.now(UTC),
            retryable=retryable,
            attempts=attempts,
            task_id=task_id,
        )
        self._messages.append(message)
        return message

    async def enqueue(
        self,
        *,
        task_id: str,
        payload: dict[str, Any],
        error: str,
        retryable: bool = True,
        attempts: int = 1,
    ) -> DLQMessage:
        """
        Async compatibility API used by E2E resilience suites.

        Maps enqueue contract to the existing synchronous push primitive.
        """
        return self.push(
            topic="recovery",
            payload=payload,
            reason=error,
            retryable=retryable,
            attempts=attempts,
            task_id=task_id,
        )

    def list(self) -> list[DLQMessage]:
        return list(self._messages)

    def list_by_topic(self, topic: str) -> list[DLQMessage]:
        return [message for message in self._messages if message.topic == topic]

    def pop_oldest(self) -> DLQMessage | None:
        if not self._messages:
            return None
        return self._messages.pop(0)

    def purge(self) -> None:
        self._messages.clear()

    async def size(self) -> int:
        """Async queue size helper for resilience flows."""
        return len(self._messages)
