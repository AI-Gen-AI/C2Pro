"""
Redis-backed Event Bus adapter.

Refers to Suite ID: TS-INT-EVT-BUS-001.
"""

from __future__ import annotations

import copy
import inspect
import json
import os
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID, uuid4

import structlog

from src.core.events.event_bus import EventBus


logger = structlog.get_logger()

Handler = Callable[[dict[str, Any]], Any | Awaitable[Any]]


class _PayloadEncoder(json.JSONEncoder):
    """JSON encoder that coerces UUID values to strings."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, UUID):
            return str(obj)
        return super().default(obj)


class RedisEventBusAdapter:
    """
    Redis-backed Event Bus adapter with tenant-scoped channel routing.

    Refers to Suite ID: TS-INT-EVT-BUS-001.
    """

    def __init__(self, redis_client: Any, env: str) -> None:
        self._redis = redis_client
        self._env = env
        self._subscribers: dict[str, list[tuple[str, Handler]]] = defaultdict(list)
        self._token_index: dict[str, str] = {}
        self._published_correlations: dict[str, set[str]] = defaultdict(set)
        self.last_errors: list[Exception] = []

    def _channel_for(self, topic: str, tenant_id: str | UUID) -> str:
        return f"c2pro.{self._env}.{tenant_id}.{topic}"

    def subscribe(self, topic: str, handler: Handler, tenant_scope: str | UUID) -> str:
        token = str(uuid4())
        channel = self._channel_for(topic, tenant_scope)
        self._subscribers[channel].append((token, handler))
        self._token_index[token] = channel
        return token

    def unsubscribe(self, token: str) -> bool:
        channel = self._token_index.pop(token, None)
        if channel is None:
            return False
        subscribers = self._subscribers.get(channel, [])
        for index, (item_token, _handler) in enumerate(subscribers):
            if item_token == token:
                del subscribers[index]
                return True
        return False

    async def publish(
        self,
        topic: str,
        payload: dict[str, Any],
        tenant_id: str | UUID,
        correlation_id: str | UUID | None = None,
    ) -> None:
        """
        Publish an event to Redis and dispatch to local subscribers.

        Refers to Suite ID: TS-INT-EVT-BUS-001.
        """
        correlation = correlation_id or str(uuid4())
        correlation_str = str(correlation)
        channel = self._channel_for(topic, tenant_id)

        if correlation_str in self._published_correlations[channel]:
            logger.warning(
                "event_bus_duplicate_correlation_dropped",
                channel=channel,
                topic=topic,
                tenant_id=str(tenant_id),
                correlation_id=correlation_str,
            )
            return

        # RED/GREEN contract: malformed payloads must fail before transport.
        message = json.dumps(
            {
                "correlation_id": correlation_str,
                "tenant_id": str(tenant_id),
                "topic": topic,
                "payload": payload,
            },
            cls=_PayloadEncoder,
        )

        try:
            await self._redis.publish(channel, message)
        except Exception as exc:
            logger.error(
                "event_bus_publish_failed",
                channel=channel,
                topic=topic,
                tenant_id=str(tenant_id),
                correlation_id=correlation_str,
                error=str(exc),
            )
            raise

        self._published_correlations[channel].add(correlation_str)
        logger.info(
            "event_bus_publish_succeeded",
            channel=channel,
            topic=topic,
            tenant_id=str(tenant_id),
            correlation_id=correlation_str,
        )

        subscribers = list(self._subscribers.get(channel, []))
        for _token, handler in subscribers:
            try:
                handler_payload = copy.deepcopy(payload)
                result = handler(handler_payload)
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:  # pragma: no cover - isolated handler failures
                self.last_errors.append(exc)

    async def close(self) -> None:
        close_fn = getattr(self._redis, "close", None)
        if close_fn is None:
            return
        result = close_fn()
        if inspect.isawaitable(result):
            await result


def build_event_bus(*, redis_url: str | None, environment: str) -> RedisEventBusAdapter | EventBus:
    """
    Build event bus from runtime policy.

    Refers to Suite ID: TS-INT-EVT-BUS-001.
    """
    mode = os.environ.get("EVENT_BUS_MODE", "").strip().lower()
    if mode == "inmemory":
        logger.warning("event_bus_inmemory_mode_enabled", environment=environment)
        return EventBus()

    if not redis_url:
        logger.warning("event_bus_redis_url_missing_fallback_inmemory", environment=environment)
        return EventBus()

    try:
        import redis.asyncio as redis
    except Exception:
        logger.warning("event_bus_redis_library_missing_fallback_inmemory", environment=environment)
        return EventBus()

    redis_client = redis.from_url(redis_url, decode_responses=True)
    return RedisEventBusAdapter(redis_client=redis_client, env=environment)
