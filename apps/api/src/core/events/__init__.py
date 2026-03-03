"""
C2Pro — Event Bus module.

Async event publication over Redis Pub/Sub.

Uses lazy imports (PEP 562) to avoid pulling in redis.asyncio
at ``import src.core.events`` time.
"""

from __future__ import annotations

import importlib
from typing import Any

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "EventPublisher":       ("src.core.events.event_publisher", "EventPublisher"),
    "EventBus":             ("src.core.events.event_bus", "EventBus"),
    "RedisEventBusAdapter": ("src.core.events.redis_event_bus", "RedisEventBusAdapter"),
    "build_event_bus":      ("src.core.events.redis_event_bus", "build_event_bus"),
    "DeadLetterQueue":      ("src.core.events.dead_letter_queue", "DeadLetterQueue"),
    "DLQMessage":           ("src.core.events.dead_letter_queue", "DLQMessage"),
    "DLQReplayService":     ("src.core.events.replay", "DLQReplayService"),
}

__all__ = list(_LAZY_IMPORTS.keys())


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        module_path, attr = _LAZY_IMPORTS[name]
        mod = importlib.import_module(module_path)
        value = getattr(mod, attr)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'src.core.events' has no attribute {name!r}")
