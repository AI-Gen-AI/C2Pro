"""
C2Pro - Database Configuration

SQLAlchemy async setup con Supabase PostgreSQL.
Incluye Row Level Security (RLS) para multi-tenancy.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import UUID

import structlog
from fastapi import Request  # Import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from src.config import settings

logger = structlog.get_logger()


class Base(DeclarativeBase):
    """Base class para todos los modelos SQLAlchemy."""

    pass


# Engine global
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_db() -> None:
    """
    Inicializa conexión a la base de datos.
    Llamar en startup de la aplicación.
    """
    global _engine, _session_factory

    # Import all models to register them with SQLAlchemy
    # This is necessary for relationship resolution
    from src.modules.auth import models as auth_models  # noqa: F401
    from src.analysis.adapters.persistence import models as analysis_models  # noqa: F401
    from src.documents.adapters.persistence import models as document_models  # noqa: F401
    from src.stakeholders.adapters.persistence import models as stakeholder_models  # noqa: F401
    from src.procurement.adapters.persistence import models as procurement_models  # noqa: F401
    from src.projects.adapters.persistence import models as project_models  # noqa: F401

    logger.debug("models_imported")

    # Convertir URL a async
    database_url = settings.database_url
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    if database_url.startswith("sqlite"):
        _engine = create_async_engine(
            database_url,
            echo=settings.debug,
        )
    else:
        _engine = create_async_engine(
            database_url,
            echo=settings.debug,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
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
                # Format the UUID directly into the SQL string (safe since UUID type is validated)
                await session.execute(text(f"SET LOCAL app.current_tenant = '{str(tenant_id)}'"))
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
            # Format the UUID directly into the SQL string (safe since UUID type is validated)
            await session.execute(text(f"SET LOCAL app.current_tenant = '{str(tenant_id)}'"))
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
