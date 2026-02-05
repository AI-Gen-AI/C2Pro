"""
In-memory event bus with publish/subscribe support.

Refers to Suite ID: TS-INT-EVT-BUS-001.
"""

from __future__ import annotations

import copy
import inspect
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4


Handler = Callable[[dict[str, Any]], Any | Awaitable[Any]]


class EventBus:
    """In-memory async publish/subscribe event bus."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[tuple[str, Handler]]] = defaultdict(list)
        self.last_errors: list[Exception] = []

    def subscribe(self, topic: str, handler: Handler) -> str:
        token = str(uuid4())
        self._subscribers[topic].append((token, handler))
        return token

    def unsubscribe(self, topic: str, token: str) -> bool:
        subscribers = self._subscribers.get(topic, [])
        for index, (item_token, _handler) in enumerate(subscribers):
            if item_token == token:
                del subscribers[index]
                return True
        return False

    def subscriber_count(self, topic: str) -> int:
        return len(self._subscribers.get(topic, []))

    def clear_topic(self, topic: str) -> None:
        self._subscribers[topic] = []

    async def publish(self, topic: str, payload: dict[str, Any]) -> None:
        subscribers = list(self._subscribers.get(topic, []))
        for _token, handler in subscribers:
            try:
                handler_payload = copy.deepcopy(payload)
                result = handler(handler_payload)
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:  # pragma: no cover - intentionally isolated
                self.last_errors.append(exc)
