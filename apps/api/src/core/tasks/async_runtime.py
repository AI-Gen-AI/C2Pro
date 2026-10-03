"""Lifecycle boundary for Celery tasks that own a fresh asyncio event loop.

Celery tasks in this package are synchronous wrappers around asyncio.run.
Any SQLAlchemy AsyncEngine created inside that loop must be disposed before
the loop closes; otherwise asyncpg/Supavisor connections can outlive their
owning loop and exhaust the upstream transaction pool.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import TypeVar

import structlog

from src.core.database import close_db

logger = structlog.get_logger(__name__)

T = TypeVar("T")


async def _run_with_db_cleanup(awaitable: Awaitable[T]) -> T:
    """Await one task body and dispose its loop-bound DB resources."""
    primary_error: BaseException | None = None
    try:
        return await awaitable
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        try:
            await close_db()
        except Exception:
            logger.exception("celery_async_db_cleanup_failed")
            if primary_error is None:
                raise


def run_async_db_task(awaitable: Awaitable[T]) -> T:
    """Run one Celery async body and close its DB engine on the same loop."""
    return asyncio.run(_run_with_db_cleanup(awaitable))
