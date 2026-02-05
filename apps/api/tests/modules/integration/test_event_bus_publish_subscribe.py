"""
Event bus publish/subscribe integration tests.
"""

from __future__ import annotations

import asyncio

import pytest

from src.core.events.event_bus import EventBus


@pytest.mark.asyncio
class TestEventBusPublishSubscribe:
    """Refers to Suite ID: TS-INT-EVT-BUS-001"""

    async def test_001_publish_delivers_to_single_subscriber(self) -> None:
        bus = EventBus()
        received: list[dict[str, str]] = []

        async def handler(payload: dict[str, str]) -> None:
            received.append(payload)

        bus.subscribe("document.uploaded", handler)
        await bus.publish("document.uploaded", {"id": "d1"})
        assert received == [{"id": "d1"}]

    async def test_002_publish_delivers_to_multiple_subscribers(self) -> None:
        bus = EventBus()
        a: list[str] = []
        b: list[str] = []

        bus.subscribe("document.uploaded", lambda payload: a.append(payload["id"]))
        bus.subscribe("document.uploaded", lambda payload: b.append(payload["id"]))
        await bus.publish("document.uploaded", {"id": "d1"})
        assert a == ["d1"]
        assert b == ["d1"]

    async def test_003_publish_routes_by_topic(self) -> None:
        bus = EventBus()
        docs: list[str] = []
        alerts: list[str] = []

        bus.subscribe("document.uploaded", lambda payload: docs.append(payload["id"]))
        bus.subscribe("alert.created", lambda payload: alerts.append(payload["id"]))
        await bus.publish("document.uploaded", {"id": "d1"})
        assert docs == ["d1"]
        assert alerts == []

    async def test_004_unsubscribe_stops_delivery(self) -> None:
        bus = EventBus()
        received: list[str] = []

        token = bus.subscribe("document.uploaded", lambda payload: received.append(payload["id"]))
        assert bus.unsubscribe("document.uploaded", token) is True
        await bus.publish("document.uploaded", {"id": "d1"})
        assert received == []

    async def test_005_unsubscribe_unknown_returns_false(self) -> None:
        bus = EventBus()
        assert bus.unsubscribe("document.uploaded", "missing") is False

    async def test_006_publish_with_no_subscribers_is_noop(self) -> None:
        bus = EventBus()
        await bus.publish("document.uploaded", {"id": "d1"})
        assert bus.subscriber_count("document.uploaded") == 0

    async def test_007_async_handler_is_awaited(self) -> None:
        bus = EventBus()
        order: list[str] = []

        async def handler(_payload: dict[str, str]) -> None:
            await asyncio.sleep(0)
            order.append("done")

        bus.subscribe("document.uploaded", handler)
        await bus.publish("document.uploaded", {"id": "d1"})
        assert order == ["done"]

    async def test_008_sync_handler_is_supported(self) -> None:
        bus = EventBus()
        received: list[str] = []
        bus.subscribe("document.uploaded", lambda payload: received.append(payload["id"]))
        await bus.publish("document.uploaded", {"id": "d1"})
        assert received == ["d1"]

    async def test_009_handlers_called_in_subscription_order(self) -> None:
        bus = EventBus()
        called: list[str] = []
        bus.subscribe("document.uploaded", lambda _payload: called.append("first"))
        bus.subscribe("document.uploaded", lambda _payload: called.append("second"))
        await bus.publish("document.uploaded", {"id": "d1"})
        assert called == ["first", "second"]

    async def test_010_handler_error_does_not_stop_other_handlers(self) -> None:
        bus = EventBus()
        called: list[str] = []

        def broken(_payload: dict[str, str]) -> None:
            raise RuntimeError("boom")

        bus.subscribe("document.uploaded", broken)
        bus.subscribe("document.uploaded", lambda _payload: called.append("ok"))
        await bus.publish("document.uploaded", {"id": "d1"})
        assert called == ["ok"]
        assert len(bus.last_errors) == 1

    async def test_011_payload_is_copied_per_handler(self) -> None:
        bus = EventBus()
        snapshots: list[dict[str, str]] = []

        def mutator(payload: dict[str, str]) -> None:
            payload["id"] = "mutated"

        def observer(payload: dict[str, str]) -> None:
            snapshots.append(payload)

        bus.subscribe("document.uploaded", mutator)
        bus.subscribe("document.uploaded", observer)
        await bus.publish("document.uploaded", {"id": "d1"})
        assert snapshots == [{"id": "d1"}]

    async def test_012_concurrent_publishes_to_different_topics(self) -> None:
        bus = EventBus()
        docs: list[str] = []
        alerts: list[str] = []
        bus.subscribe("document.uploaded", lambda payload: docs.append(payload["id"]))
        bus.subscribe("alert.created", lambda payload: alerts.append(payload["id"]))
        await asyncio.gather(
            bus.publish("document.uploaded", {"id": "d1"}),
            bus.publish("alert.created", {"id": "a1"}),
        )
        assert docs == ["d1"]
        assert alerts == ["a1"]

    async def test_013_subscriber_count_reflects_state(self) -> None:
        bus = EventBus()
        token = bus.subscribe("document.uploaded", lambda _payload: None)
        assert bus.subscriber_count("document.uploaded") == 1
        bus.unsubscribe("document.uploaded", token)
        assert bus.subscriber_count("document.uploaded") == 0

    async def test_014_clear_topic_subscribers(self) -> None:
        bus = EventBus()
        bus.subscribe("document.uploaded", lambda _payload: None)
        bus.subscribe("document.uploaded", lambda _payload: None)
        bus.clear_topic("document.uploaded")
        assert bus.subscriber_count("document.uploaded") == 0
