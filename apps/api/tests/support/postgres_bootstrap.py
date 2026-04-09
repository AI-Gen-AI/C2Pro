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

    await _run_bootstrap_phase(engine, ensure_pgvector_extension)
    await _run_bootstrap_phase(engine, prepare_step)


async def ensure_pgvector_extension(conn: AsyncConnection) -> None:
    """Enable pgvector before metadata DDL creates vector-backed tables."""
    schema_query = text(
        """
        SELECT n.nspname
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'vector'
        ORDER BY CASE WHEN n.nspname = 'public' THEN 0 ELSE 1 END
        LIMIT 1
        """
    )
    result = await conn.execute(schema_query)
    vector_schema = (
        result.scalar_one_or_none()
        if result is not None and hasattr(result, "scalar_one_or_none")
        else None
    )
    if vector_schema == "public":
        return

    extension_result = await conn.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_extension
                WHERE extname = 'vector'
            )
            """
        )
    )
    extension_exists = (
        extension_result.scalar_one()
        if extension_result is not None and hasattr(extension_result, "scalar_one")
        else False
    )

    if extension_exists:
        await conn.execute(text("ALTER EXTENSION vector SET SCHEMA public"))
    else:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public"))

    verification = await conn.execute(schema_query)
    verified_schema = (
        verification.scalar_one_or_none()
        if verification is not None and hasattr(verification, "scalar_one_or_none")
        else None
    )
    if verified_schema != "public":
        raise RuntimeError("pgvector bootstrap failed: vector type is not available in public schema")


async def reset_public_schema(conn: AsyncConnection) -> None:
    await conn.execute(text("DROP EXTENSION IF EXISTS vector CASCADE"))
    await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
    await conn.execute(text("CREATE SCHEMA public"))
    await conn.execute(text("SET search_path TO public"))
