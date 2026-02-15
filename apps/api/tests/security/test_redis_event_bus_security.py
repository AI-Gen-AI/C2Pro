"""
Security tests for Redis Event Bus adapter.

Suite ID: TS-INT-EVT-BUS-001
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.core.events.redis_event_bus import RedisEventBusAdapter


@pytest.mark.unit
@pytest.mark.asyncio
class TestRedisEventBusSecurity:
    """
    Security and reliability checks for event transport.

    Suite ID: TS-INT-EVT-BUS-001
    """

    async def test_tenant_boundary_enforced_at_transport_channel_level(self) -> None:
        """Suite ID: TS-INT-EVT-BUS-001"""
        redis = AsyncMock()
        bus = RedisEventBusAdapter(redis_client=redis, env="test")
        tenant_a = str(uuid4())
        tenant_b = str(uuid4())
        received_a: list[dict[str, Any]] = []
        received_b: list[dict[str, Any]] = []

        async def handler_a(payload: dict[str, Any]) -> None:
            received_a.append(payload)

        async def handler_b(payload: dict[str, Any]) -> None:
            received_b.append(payload)

        bus.subscribe("alerts.created", handler_a, tenant_scope=tenant_a)
        bus.subscribe("alerts.created", handler_b, tenant_scope=tenant_b)

        await bus.publish(
            topic="alerts.created",
            payload={"alert_id": "a-1"},
            tenant_id=tenant_a,
            correlation_id=str(uuid4()),
        )

        assert received_a == [{"alert_id": "a-1"}]
        assert received_b == []
        channel = redis.publish.call_args.args[0]
        assert channel == f"c2pro.test.{tenant_a}.alerts.created"

    async def test_failure_logs_safe_metadata_only_without_sensitive_payload(self, monkeypatch) -> None:
        """Suite ID: TS-INT-EVT-BUS-001"""
        redis = AsyncMock()
        redis.publish.side_effect = ConnectionError("redis down")
        bus = RedisEventBusAdapter(redis_client=redis, env="prod")
        tenant_id = str(uuid4())
        correlation_id = str(uuid4())
        payload = {"password": "secret-123", "token": "jwt-secret", "note": "safe"}

        captured: dict[str, Any] = {}

        def _capture(event: str, **kwargs: Any) -> None:
            captured["event"] = event
            captured["kwargs"] = kwargs

        monkeypatch.setattr("src.core.events.redis_event_bus.logger.error", _capture)

        with pytest.raises(ConnectionError):
            await bus.publish(
                topic="documents.uploaded",
                payload=payload,
                tenant_id=tenant_id,
                correlation_id=correlation_id,
            )

        assert captured["event"] == "event_bus_publish_failed"
        assert captured["kwargs"]["tenant_id"] == tenant_id
        assert captured["kwargs"]["correlation_id"] == correlation_id
        assert "payload" not in captured["kwargs"]
        assert "secret-123" not in str(captured["kwargs"])
        assert "jwt-secret" not in str(captured["kwargs"])

    async def test_duplicate_replay_dropped_by_correlation_id(self) -> None:
        """Suite ID: TS-INT-EVT-BUS-001"""
        redis = AsyncMock()
        bus = RedisEventBusAdapter(redis_client=redis, env="test")
        tenant_id = str(uuid4())
        correlation_id = str(uuid4())
        received: list[dict[str, Any]] = []

        async def handler(payload: dict[str, Any]) -> None:
            received.append(payload)

        bus.subscribe("coherence.completed", handler, tenant_scope=tenant_id)

        await bus.publish(
            topic="coherence.completed",
            payload={"job_id": "job-1"},
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )
        await bus.publish(
            topic="coherence.completed",
            payload={"job_id": "job-1"},
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )

        assert redis.publish.await_count == 1
        assert received == [{"job_id": "job-1"}]
