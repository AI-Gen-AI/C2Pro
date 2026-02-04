"""
C2Pro — Event Bus module.

Async event publication over Redis Pub/Sub.
"""

from src.core.events.event_publisher import EventPublisher

__all__ = ["EventPublisher"]
