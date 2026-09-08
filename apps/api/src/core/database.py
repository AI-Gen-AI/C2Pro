"""
C2Pro - Database Configuration

SQLAlchemy async setup con Supabase PostgreSQL.
Incluye Row Level Security (RLS) para multi-tenancy.
"""

import re
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from typing import TYPE_CHECKING, Any, TypeAlias
from uuid import UUID

import structlog
from fastapi import Request  # Import Request

if TYPE_CHECKING:
    RequestType: TypeAlias = Request[Any]
else:
    RequestType = Request

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
_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


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
def _receive_before_cursor_execute(
    conn: Any,
    cursor: Any,
    statement: Any,
    parameters: Any,
    context: Any,
    executemany: Any,  # noqa: ARG001
) -> None:
    """SQLAlchemy event handler - all args required by event listener interface."""
    conn.info.setdefault("query_start_time", []).append(time.perf_counter())


@event.listens_for(Engine, "after_cursor_execute")
def _receive_after_cursor_execute(
    conn: Any,
    cursor: Any,
    statement: Any,
    parameters: Any,
    context: Any,
    executemany: Any,  # noqa: ARG001
) -> None:
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
def _initialize_tenant_guc(dbapi_connection: Any, connection_record: Any) -> None:  # noqa: ARG001
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


async def get_session(request: RequestType) -> AsyncGenerator[AsyncSession, None]:
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
                # SET LOCAL ensures the variable is only set for the current transaction
                # and automatically discarded on COMMIT or ROLLBACK.
                # We use validated UUID to prevent SQL injection.
                safe_tenant = _validate_uuid_for_sql(tenant_id)
                await session.execute(text(f"SET LOCAL app.current_tenant = '{safe_tenant}'"))
                logger.debug("RLS_tenant_set", tenant_id=str(tenant_id))

            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            # Explicit cleanup for extra safety in connection pooling scenarios.
            if (
                hasattr(request.state, "tenant_id")
                and request.state.tenant_id
                and not settings.database_url.startswith("sqlite")
            ):
                # Connection might already be closed/invalid.
                with suppress(Exception):
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


# =============================================================================
# C2.5 — Cross-Tenant Admin Operations Session
# =============================================================================

_admin_ops_engine: AsyncEngine | None = None
_admin_ops_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_admin_ops_db() -> None:
    """
    Initialize the admin operations database engine.

    Uses ADMIN_OPS_DATABASE_URL from settings. No fallback to DATABASE_URL.
    Must be called before any admin operations endpoints are accessed.
    Missing/malformed ADMIN_OPS_DATABASE_URL does not kill ordinary API startup.
    """
    global _admin_ops_engine, _admin_ops_session_factory

    from src.config import settings

    dsn = settings.admin_ops_database_url
    if not dsn:
        logger.warning(
            "admin_ops_db_unconfigured_at_startup",
            message="ADMIN_OPS_DATABASE_URL is not set. Cross-tenant admin/DLQ endpoints will be unavailable (503).",
        )
        return

    if dsn.startswith("postgresql://") and not dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql://", "postgresql+asyncpg://", 1)

    try:
        # Construct engine/factory locally first to prevent partial assignment
        local_engine = create_async_engine(
            dsn,
            echo=settings.db_echo,
            pool_pre_ping=settings.db_pool_pre_ping,
            pool_size=2,  # Small pool for admin operations
            max_overflow=0,
            pool_timeout=settings.db_pool_timeout,
            pool_recycle=settings.db_pool_recycle,
            connect_args={"statement_cache_size": 0},
        )

        local_session_factory = async_sessionmaker(
            bind=local_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

        # Assign globals only on successful construction
        _admin_ops_engine = local_engine
        _admin_ops_session_factory = local_session_factory
        logger.info("admin_ops_database_engine_created")

    except Exception as exc:
        _admin_ops_engine = None
        _admin_ops_session_factory = None
        # Log only the exception class name to prevent credential leakage
        logger.error(
            "admin_ops_db_init_failed",
            exception_type=type(exc).__name__,
            message="Dedicated admin operations database failed to initialize. Ordinary API startup will proceed, but cross-tenant admin operations will be unavailable (503).",
        )


async def close_admin_ops_db() -> None:
    """Close the admin operations database engine, clearing both engine and session factory."""
    global _admin_ops_engine, _admin_ops_session_factory

    try:
        if _admin_ops_engine:
            await _admin_ops_engine.dispose()
    finally:
        _admin_ops_engine = None
        _admin_ops_session_factory = None
        logger.info("admin_ops_database_engine_closed")


@asynccontextmanager
async def get_admin_ops_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session for cross-tenant admin operations.

    Uses the dedicated ADMIN_OPS_DATABASE_URL credential (C2.5).
    PostgreSQL ROLE membership is the ONLY database authorization boundary.
    No GUC (app.admin_ops) is set.

    Before yielding, validates the actual database principal to ensure:
    - LOGIN capability
    - NOT superuser
    - NOT BYPASSRLS
    - NOT CREATEROLE
    - Correct membership in c2pro_admin_ops
    - NOT owner of 'dlq_failed_tasks'
    - No unexpected inherited elevated role membership

    Yields:
        AsyncSession connected as the verified restricted admin login role.

    Raises:
        RuntimeError: If admin DB is uninitialized or validation fails.
    """
    if _admin_ops_session_factory is None:
        raise RuntimeError("ADMIN_OPS_DATABASE_URL is uninitialized or not configured.")

    async with _admin_ops_session_factory() as session:
        # Validate PostgreSQL principal and privileges dynamically via catalog
        if session.bind and session.bind.dialect.name == "postgresql":
            result = await session.execute(
                text(
                    """
                    SELECT
                        rolcanlogin,
                        rolsuper,
                        rolbypassrls,
                        rolcreaterole,
                        rolcreatedb,
                        pg_has_role(current_user, 'c2pro_admin_ops', 'member') AS is_member,
                        EXISTS (
                            SELECT 1 FROM pg_class c
                            JOIN pg_roles r ON c.relowner = r.oid
                            WHERE c.relname = 'dlq_failed_tasks' AND r.rolname = current_user
                        ) AS is_table_owner,
                        EXISTS (
                            SELECT 1 FROM pg_auth_members m
                            JOIN pg_roles r ON m.roleid = r.oid
                            WHERE m.member = current_user::regrole
                            AND r.rolname NOT IN ('c2pro_admin_ops', 'public')
                        ) AS has_extra_inherited,
                        EXISTS (
                            SELECT 1 FROM pg_database d
                            JOIN pg_roles r ON d.datdba = r.oid
                            WHERE d.datname = current_database() AND r.rolname = current_user
                        ) AS is_db_owner,
                        EXISTS (
                            SELECT 1 FROM pg_namespace n
                            JOIN pg_roles r ON n.nspowner = r.oid
                            WHERE n.nspname = 'public' AND r.rolname = current_user
                        ) AS is_schema_owner,
                        has_database_privilege(current_user, current_database(), 'CREATE') AS has_db_create,
                        has_schema_privilege(current_user, 'public', 'CREATE') AS has_schema_create,
                        (SELECT session_user = current_user) AS session_user_eq_current_user,
                        -- Indicators for direct grants to current_user
                        (
                            SELECT EXISTS (
                                SELECT 1 FROM pg_class c
                                JOIN pg_namespace n ON c.relnamespace = n.oid
                                CROSS JOIN unnest(COALESCE(c.relacl, acldefault(
                                    CASE c.relkind WHEN 'S' THEN 's'::"char" ELSE 'r'::"char" END,
                                    c.relowner
                                ))) acl
                                WHERE n.nspname = 'public'
                                  AND acl::text LIKE current_user || '=%'
                            )
                        ) AS has_direct_rel_grants,
                        (
                            SELECT EXISTS (
                                SELECT 1 FROM pg_attribute a
                                JOIN pg_class c ON a.attrelid = c.oid
                                JOIN pg_namespace n ON c.relnamespace = n.oid
                                CROSS JOIN unnest(COALESCE(a.attacl, acldefault('c', c.relowner))) acl
                                WHERE n.nspname = 'public'
                                  AND acl::text LIKE current_user || '=%'
                            )
                        ) AS has_direct_col_grants,
                        (
                            SELECT EXISTS (
                                SELECT 1 FROM pg_namespace n
                                CROSS JOIN unnest(COALESCE(n.nspacl, acldefault('n', n.nspowner))) acl
                                WHERE acl::text LIKE current_user || '=%'
                                  AND NOT (n.nspname = 'public' AND acl::text = current_user || '=U/' || pg_get_userbyid(n.nspowner))
                            )
                        ) AS has_direct_schema_grants,
                        (
                            SELECT EXISTS (
                                SELECT 1 FROM pg_database d
                                CROSS JOIN unnest(COALESCE(d.datacl, acldefault('d', d.datdba))) acl
                                WHERE d.datname = current_database()
                                  AND acl::text LIKE current_user || '=%'
                                  AND NOT (acl::text = current_user || '=c/' || pg_get_userbyid(d.datdba))
                            )
                        ) AS has_direct_db_grants,
                        (
                            SELECT EXISTS (
                                SELECT 1 FROM pg_proc p
                                JOIN pg_namespace n ON p.pronamespace = n.oid
                                CROSS JOIN unnest(COALESCE(p.proacl, acldefault('f', p.proowner))) acl
                                WHERE n.nspname = 'public'
                                  AND acl::text LIKE current_user || '=%'
                            )
                        ) AS has_direct_proc_grants,
                        (
                            SELECT EXISTS (
                                SELECT 1 FROM pg_default_acl a
                                CROSS JOIN unnest(a.defaclacl) acl
                                WHERE acl::text LIKE current_user || '=%'
                            )
                        ) AS has_direct_default_acls
                    FROM pg_roles
                    WHERE rolname = current_user
                    """
                )
            )
            row = result.fetchone()
            if row:
                (
                    rolcanlogin,
                    rolsuper,
                    rolbypassrls,
                    rolcreaterole,
                    rolcreatedb,
                    is_member,
                    is_table_owner,
                    has_extra_inherited,
                    is_db_owner,
                    is_schema_owner,
                    has_db_create,
                    has_schema_create,
                    session_user_eq_current_user,
                    has_direct_rel_grants,
                    has_direct_col_grants,
                    has_direct_schema_grants,
                    has_direct_db_grants,
                    has_direct_proc_grants,
                    has_direct_default_acls,
                ) = row
                if not rolcanlogin:
                    raise RuntimeError("Database principal lacks LOGIN privilege.")
                if rolsuper:
                    raise RuntimeError(
                        "Superuser login is strictly forbidden for admin operations."
                    )
                if rolbypassrls:
                    raise RuntimeError(
                        "BypassRLS login is strictly forbidden for admin operations."
                    )
                if rolcreaterole:
                    raise RuntimeError(
                        "CreateRole login is strictly forbidden for admin operations."
                    )
                if rolcreatedb:
                    raise RuntimeError("CreateDB login is strictly forbidden for admin operations.")
                if not is_member:
                    raise RuntimeError("Database principal is not a member of c2pro_admin_ops.")
                if is_table_owner:
                    raise RuntimeError("Database principal owns dlq_failed_tasks (bypassing RLS).")
                if has_extra_inherited:
                    raise RuntimeError(
                        "Database principal possesses unexpected inherited role memberships."
                    )
                if is_db_owner:
                    raise RuntimeError("Database principal owns the current database.")
                if is_schema_owner:
                    raise RuntimeError("Database principal owns the public schema.")
                if has_db_create:
                    raise RuntimeError(
                        "Database principal possesses CREATE privilege on the database."
                    )
                if has_schema_create:
                    raise RuntimeError(
                        "Database principal possesses CREATE privilege on the public schema."
                    )
                if not session_user_eq_current_user:
                    raise RuntimeError("session_user and current_user must match exactly.")
                if has_direct_rel_grants:
                    raise RuntimeError(
                        "Database principal possesses unexpected direct relation/table/sequence privileges."
                    )
                if has_direct_col_grants:
                    raise RuntimeError(
                        "Database principal possesses unexpected direct column privileges."
                    )
                if has_direct_schema_grants:
                    raise RuntimeError(
                        "Database principal possesses unexpected direct schema privileges."
                    )
                if has_direct_db_grants:
                    raise RuntimeError(
                        "Database principal possesses unexpected direct database privileges."
                    )
                if has_direct_proc_grants:
                    raise RuntimeError(
                        "Database principal possesses unexpected direct function/procedure privileges."
                    )
                if has_direct_default_acls:
                    raise RuntimeError(
                        "Database principal possesses unexpected direct default ACLs."
                    )

        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
