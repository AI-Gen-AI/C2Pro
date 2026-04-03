"""TS-E2E-SEC-TNT-001

Shared helpers for PostgreSQL-backed test schema bootstrap.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

BootstrapStep = Callable[[AsyncConnection], Awaitable[None]]
WarningSink = Callable[[Exception], None]


async def _run_bootstrap_phase(
    engine: AsyncEngine,
    step: BootstrapStep,
) -> None:
    async with engine.connect() as conn:
        transaction = await conn.begin()
        try:
            await conn.execute(text("SET LOCAL search_path TO public"))
            await conn.execute(text("SELECT 1"))
            await step(conn)
        except Exception:
            await transaction.rollback()
            raise
        else:
            await transaction.commit()


async def _run_optional_bootstrap_phase(
    engine: AsyncEngine,
    step: BootstrapStep,
) -> Exception | None:
    try:
        await _run_bootstrap_phase(engine, step)
    except Exception as exc:  # pragma: no cover - exercised via orchestrator test
        return exc
    return None


async def run_postgres_test_bootstrap(
    engine: AsyncEngine,
    *,
    cleanup_step: BootstrapStep,
    prepare_step: BootstrapStep,
    warning_sink: WarningSink,
) -> None:
    cleanup_error = await _run_optional_bootstrap_phase(engine, cleanup_step)
    if cleanup_error is not None:
        warning_sink(cleanup_error)
    await _run_bootstrap_phase(engine, prepare_step)


async def reset_public_schema(conn: AsyncConnection) -> None:
    await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
    await conn.execute(text("CREATE SCHEMA public"))
    await conn.execute(text("SET search_path TO public"))
