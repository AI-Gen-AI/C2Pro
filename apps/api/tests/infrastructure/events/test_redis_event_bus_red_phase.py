"""
RED phase tests for Redis-backed Event Bus.

Suite ID: TS-INT-EVT-BUS-001
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest


Handler = Callable[[dict[str, Any]], Awaitable[None] | None]


def _build_bus(*, env: str = "test", redis_client: AsyncMock | None = None) -> Any:
    """
    Suite ID: TS-INT-EVT-BUS-001

    Import the target adapter lazily so RED can be confirmed as ImportError
    before implementation exists.
    """
    from src.core.events.redis_event_bus import RedisEventBusAdapter

    client = redis_client or AsyncMock()
    return RedisEventBusAdapter(redis_client=client, env=env), client


@pytest.mark.unit
@pytest.mark.asyncio
class TestRedisEventBusRedPhase:
    """
    RED phase contract for Redis Event Bus.

    Suite ID: TS-INT-EVT-BUS-001
    """

    async def test_publish_subscribe_through_redis_channel(self) -> None:
        """Suite ID: TS-INT-EVT-BUS-001"""
        bus, redis = _build_bus()
        received: list[dict[str, Any]] = []
        tenant_id = str(uuid4())

        async def handler(payload: dict[str, Any]) -> None:
            received.append(payload)

        _token = bus.subscribe("documents.uploaded", handler, tenant_scope=tenant_id)
        await bus.publish(
            topic="documents.uploaded",
            payload={"document_id": "doc-1"},
            tenant_id=tenant_id,
            correlation_id=str(uuid4()),
        )

        redis.publish.assert_awaited_once()
        assert received == [{"document_id": "doc-1"}]

    async def test_tenant_channel_isolation(self) -> None:
        """Suite ID: TS-INT-EVT-BUS-001"""
        bus, redis = _build_bus(env="prod")
        tenant_a = str(uuid4())
        tenant_b = str(uuid4())
        received_a: list[dict[str, Any]] = []

        async def handler_a(payload: dict[str, Any]) -> None:
            received_a.append(payload)

        _token = bus.subscribe("alerts.created", handler_a, tenant_scope=tenant_a)

        await bus.publish(
            topic="alerts.created",
            payload={"alert_id": "a-1"},
            tenant_id=tenant_b,
            correlation_id=str(uuid4()),
        )

        assert received_a == []
        channel = redis.publish.call_args.args[0]
        assert channel.startswith(f"c2pro.prod.{tenant_b}.alerts.created")

    async def test_reconnect_and_recover_after_connection_error(self) -> None:
        """Suite ID: TS-INT-EVT-BUS-001"""
        bus, redis = _build_bus()
        tenant_id = str(uuid4())
        redis.publish.side_effect = [ConnectionError("down"), None]

        with pytest.raises(ConnectionError):
            await bus.publish(
                topic="coherence.completed",
                payload={"job_id": "j-1"},
                tenant_id=tenant_id,
                correlation_id=str(uuid4()),
            )

        await bus.publish(
            topic="coherence.completed",
            payload={"job_id": "j-1"},
            tenant_id=tenant_id,
            correlation_id=str(uuid4()),
        )
        assert redis.publish.await_count == 2

    async def test_serialization_rejects_malformed_payload(self) -> None:
        """Suite ID: TS-INT-EVT-BUS-001"""
        bus, redis = _build_bus()
        tenant_id = str(uuid4())

        with pytest.raises(TypeError):
            await bus.publish(
                topic="documents.uploaded",
                payload={"bad": {1, 2, 3}},
                tenant_id=tenant_id,
                correlation_id=str(uuid4()),
            )

        redis.publish.assert_not_awaited()

    async def test_redis_outage_fails_when_mode_is_redis(self) -> None:
        """Suite ID: TS-INT-EVT-BUS-001"""
        bus, redis = _build_bus(env="prod")
        tenant_id = str(uuid4())
        redis.publish.side_effect = ConnectionError("redis unavailable")

        with pytest.raises(ConnectionError):
            await bus.publish(
                topic="documents.uploaded",
                payload={"document_id": "doc-7"},
                tenant_id=tenant_id,
                correlation_id=str(uuid4()),
            )
