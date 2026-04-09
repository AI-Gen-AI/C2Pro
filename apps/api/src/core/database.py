"""
C2Pro - Database Configuration

SQLAlchemy async setup con Supabase PostgreSQL.
Incluye Row Level Security (RLS) para multi-tenancy.
"""

import re
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import UUID

import structlog
from fastapi import Request  # Import Request
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

logger = structlog.get_logger()

# Slow query threshold in seconds (100ms)
SLOW_QUERY_THRESHOLD_MS = 100

# UUID validation pattern (safe for SQL string interpolation)
_UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)


def _validate_uuid_for_sql(value: UUID | str) -> str:
    """
    Validate and convert UUID to safe SQL string.

    PostgreSQL SET commands don't support parameterized queries.
    This function ensures the UUID is valid before using in SQL.
    """
    str_value = str(value)

    if not _UUID_PATTERN.match(str_value):
        raise ValueError(f"Invalid UUID format: {str_value}")

    return str_value


@event.listens_for(Engine, "before_cursor_execute")
def _receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # noqa: ARG001
    """SQLAlchemy event handler - all args required by event listener interface."""
    conn.info.setdefault("query_start_time", []).append(time.perf_counter())


@event.listens_for(Engine, "after_cursor_execute")
def _receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # noqa: ARG001
    """SQLAlchemy event handler - all args required by event listener interface."""
    start_times = conn.info.get("query_start_time", [])
    if start_times:
        start_time = start_times.pop()
        duration_ms = (time.perf_counter() - start_time) * 1000

        if duration_ms > SLOW_QUERY_THRESHOLD_MS:
            # Truncate long statements for logging
            stmt_preview = statement[:200] + "..." if len(statement) > 200 else statement
            logger.warning(
                "slow_query_detected",
                duration_ms=round(duration_ms, 2),
                threshold_ms=SLOW_QUERY_THRESHOLD_MS,
                statement_preview=stmt_preview,
            )


class Base(DeclarativeBase):
    """Base class para todos los modelos SQLAlchemy."""

    pass


# Engine global
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


@event.listens_for(Engine, "connect")
def _initialize_tenant_guc(dbapi_connection, connection_record) -> None:  # noqa: ARG001
    """
    SQLAlchemy event handler - connection_record required by event listener interface.
    Ensure PostgreSQL custom GUC exists on every new DB connection.

    This keeps `SHOW app.current_tenant` available across sessions and enables
    deterministic RLS context checks in tests and runtime diagnostics.
    """
    try:
        from src.config import settings

        # sqlite doesn't support custom GUC; skip silently.
        if settings.database_url.startswith("sqlite"):
            return

        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("SET SESSION app.current_tenant = ''")
        finally:
            cursor.close()
    except Exception:
        # Never block connection creation due to GUC bootstrap.
        return


async def init_db() -> None:
    """
    Inicializa conexión a la base de datos.
    Llamar en startup de la aplicación.
    """
    global _engine, _session_factory

    from src.analysis.adapters.persistence import models as analysis_models  # noqa: F401
    from src.config import settings

    # Import all models to register them with SQLAlchemy
    # This is necessary for relationship resolution
    from src.core.auth import models as auth_models  # noqa: F401
    from src.documents.adapters.persistence import models as document_models  # noqa: F401
    from src.procurement.adapters.persistence import models as procurement_models  # noqa: F401
    from src.projects.adapters.persistence import models as project_models  # noqa: F401
    from src.stakeholders.adapters.persistence import models as stakeholder_models  # noqa: F401

    logger.debug("models_imported")

    # Convertir URL a async
    database_url = settings.database_url
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    if database_url.startswith("sqlite"):
        _engine = create_async_engine(
            database_url,
            echo=settings.db_echo,
        )
    else:
        _engine = create_async_engine(
            database_url,
            echo=settings.db_echo,
            pool_pre_ping=settings.db_pool_pre_ping,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_recycle=settings.db_pool_recycle,
            connect_args={"statement_cache_size": 0},
        )
        logger.info(
            "connection_pool_configured",
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_recycle=settings.db_pool_recycle,
        )

    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    logger.info("database_engine_created", url=database_url[:50] + "...")


async def close_db() -> None:
    """
    Cierra conexión a la base de datos.
    Llamar en shutdown de la aplicación.
    """
    global _engine

    if _engine:
        await _engine.dispose()
        _engine = None
        logger.info("database_engine_closed")


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency para obtener sesión de base de datos.

    Si la request tiene un tenant_id en su estado (establecido por el middleware),
    configura la sesión con Row Level Security (RLS) para ese tenant.
    """
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    from src.config import settings

    async with _session_factory() as session:
        try:
            # Check if tenant_id is available from the request state (set by middleware)
            if (
                hasattr(request.state, "tenant_id")
                and request.state.tenant_id
                and not settings.database_url.startswith("sqlite")
            ):
                tenant_id = request.state.tenant_id
                # SET commands don't support parameterized queries in PostgreSQL
                # Use validated UUID to prevent SQL injection
                safe_tenant = _validate_uuid_for_sql(tenant_id)
                await session.execute(text(f"SET LOCAL app.current_tenant = '{safe_tenant}'"))
                logger.debug("RLS_tenant_set", tenant_id=str(tenant_id))

            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            # Always reset the tenant context to prevent leakage
            if (
                hasattr(request.state, "tenant_id")
                and request.state.tenant_id
                and not settings.database_url.startswith("sqlite")
            ):
                await session.execute(text("RESET app.current_tenant"))
                logger.debug("RLS_tenant_reset", tenant_id=str(request.state.tenant_id))


# The get_session_with_tenant context manager can now be simplified or potentially removed
# if get_session is the primary way to get a session in FastAPI routes.
# However, keeping it for explicit tenant setting in background tasks or specific service methods
# where request context is not available might be useful.
# For this task, we will keep it as is, but rely on the improved get_session.


@asynccontextmanager
async def get_session_with_tenant(tenant_id: UUID) -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session with tenant context set via RLS.

    Useful for background tasks or service methods where request context is not available.
    Sets the tenant_id in the session for RLS policies.

    Args:
        tenant_id: UUID of the tenant to set in session context

    Yields:
        AsyncSession with tenant context set
    """
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    async with _session_factory() as session:
        try:
            # Set tenant_id for RLS
            # SET commands don't support parameterized queries in PostgreSQL
            # Use validated UUID to prevent SQL injection
            safe_tenant = _validate_uuid_for_sql(tenant_id)
            await session.execute(text(f"SET LOCAL app.current_tenant = '{safe_tenant}'"))
            logger.debug("RLS_tenant_set", tenant_id=str(tenant_id))

            yield session

            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            # Reset tenant context
            await session.execute(text("RESET app.current_tenant"))
            logger.debug("RLS_tenant_reset", tenant_id=str(tenant_id))


@asynccontextmanager
async def get_raw_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session without tenant context.

    Useful for middleware validation or operations that need to query
    across all tenants (like checking if a tenant exists).

    Yields:
        AsyncSession without RLS tenant context
    """
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    async with _session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
