"""
C2Pro - Event Publisher

Publishes domain events to Redis Pub/Sub channels.

Provides async, non-blocking event emission with JSON serialisation
and automatic UUID coercion.  The publisher is intentionally thin:
serialise → delegate.  Retry, dead-letter routing, and backoff are
the responsibility of the event-bus layer above this class
(see TS-INT-EVT-DLQ-001).

Version: 1.0.0
Date: 2026-02-04
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID


class _PayloadEncoder(json.JSONEncoder):
    """JSON encoder that coerces uuid.UUID instances to their string form."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, UUID):
            return str(obj)
        return super().default(obj)


class EventPublisher:
    """
    Publishes events to a Redis Pub/Sub channel.

    Args:
        redis_client: An async Redis client instance
                      (e.g. ``redis.asyncio.Redis``).
    """

    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client

    async def publish(self, event_name: str, payload: dict[str, Any]) -> None:
        """
        Serialise *payload* to JSON and publish to the *event_name* channel.

        Args:
            event_name: Redis channel name (e.g. ``"document.uploaded"``).
            payload:    Event data.  ``uuid.UUID`` values are coerced to
                        strings automatically; all other values must be
                        natively JSON-serialisable.

        Raises:
            TypeError:       *payload* contains a value that cannot be
                             serialised to JSON.
            ConnectionError: Propagated from the underlying Redis client
                             on transport failure.
        """
        message = json.dumps(payload, cls=_PayloadEncoder)
        await self._redis.publish(event_name, message)
