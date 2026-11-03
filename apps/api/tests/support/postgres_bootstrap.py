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
    strict_cleanup: bool = False,
) -> None:
    if strict_cleanup:
        await _run_bootstrap_phase(engine, cleanup_step)
    else:
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


async def reset_test_schemas(conn: AsyncConnection) -> None:
    """Reset both fixture-owned schemas, including SQL-only dependants.

    Call only after validating the test target. Dropping public alone leaves
    recovery rows and removes their FK/trigger through CASCADE.
    """
    await conn.execute(text("DROP SCHEMA IF EXISTS system_recovery CASCADE"))
    await reset_public_schema(conn)


async def provision_recovery_schema(conn: AsyncConnection) -> None:
    """Restore SQL-only recovery obligations on the metadata test fixture.

    SQLAlchemy create_all cannot recreate the Alembic-owned tables. Import the
    checked-out migration DDL rather than duplicating it in test scaffolding.
    This deliberately does NOT stamp Alembic or claim a fully migrated DB.
    A genuinely migrated schema requires the separate alembic_schema route.
    """
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    versions = Path(__file__).resolve().parents[2] / "alembic" / "versions"

    def load_migration(filename: str, name: str):
        spec = importlib.util.spec_from_file_location(name, versions / filename)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"recovery_migration_unavailable:{filename}")
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        return migration

    discovery = load_migration(
        "20260927_0711_recovery_discovery.py", "fixture_recovery_discovery"
    )
    trust = load_migration(
        "20260927_0714_document_artifact_trust_state.py", "fixture_trust_projection"
    )
    materialization = load_migration(
        "20261004_0002_trusted_artifact_materialization.py",
        "fixture_trusted_materialization",
    )

    def apply(sync_conn):
        operations = Operations(MigrationContext.configure(sync_conn))
        discovery.op = operations
        discovery.upgrade()

        # Only the SQL-only obligation table, not the 0714 historical
        # reclassification or application data migrations.
        trust.op = operations
        trust._create_projection_index()

        # The repository always writes materialization_state. Keep the fixture
        # aligned to the exact migration-owned projection columns and index,
        # without replaying its business-table alterations on ORM create_all.
        for statement in (
            materialization.ADD_MATERIALIZATION_COLUMNS_SQL,
            materialization.ADD_MATERIALIZATION_STATE_CHECK_SQL,
            materialization.ADD_PENDING_MATERIALIZATION_INDEX_SQL,
        ):
            operations.execute(statement)

    await conn.run_sync(apply)
