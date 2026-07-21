"""
TASK-QA-206: DB bootstrap pytest plugin — auto-imported by conftest.py.

Centralises all PostgreSQL schema-bootstrap helpers and DB fixtures so that
conftest.py stays ≤ 700 LOC. Loaded via:

    pytest_plugins = ("tests._bootstrap", ...)

The `scripts/bootstrap_test_infra.py` script handles external infra
(Docker, Alembic migrations). This module handles the in-process SQLAlchemy
schema creation that runs inside each pytest session.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from importlib import import_module

import pytest
import pytest_asyncio
from sqlalchemy import Column, event, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from src.config import settings
from src.core.database import Base
from tests.support.postgres_bootstrap import (
    reset_public_schema,
    run_postgres_test_bootstrap,
)

# ---------------------------------------------------------------------------
# Pytest configuration (markers + Prometheus reset)
# ---------------------------------------------------------------------------


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers for this project."""
    from prometheus_client import REGISTRY, ProcessCollector

    collectors = list(REGISTRY._collector_to_names.keys())
    for collector in collectors:
        if not isinstance(collector, ProcessCollector):
            REGISTRY.unregister(collector)

    config.addinivalue_line("markers", "security: marca tests de seguridad críticos")
    config.addinivalue_line("markers", "tdd: mark tests that enforce TDD workflow")
    config.addinivalue_line("markers", "gate_verification: CTO security gates verification tests")
    config.addinivalue_line("markers", "gate1_rls: Gate 1 - Row Level Security verification")
    config.addinivalue_line("markers", "gate2_identity: Gate 2 - Identity & Authentication verification")
    config.addinivalue_line("markers", "gate3_mcp: Gate 3 - MCP Security verification")
    config.addinivalue_line("markers", "gate4_traceability: Gate 4 - Traceability & Audit Logging verification")
    config.addinivalue_line("markers", "contract: Contract tests (API/frontend alignment)")


# ---------------------------------------------------------------------------
# Event loop
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="function")
def event_loop():
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# SQLAlchemy enum helpers
# ---------------------------------------------------------------------------


def _iter_metadata_enum_types():
    seen: set[str] = set()
    for table in Base.metadata.tables.values():
        for column in table.columns:
            column_type = column.type
            enum_name = getattr(column_type, "name", None)
            has_enum_values = getattr(column_type, "enums", None) is not None
            if not enum_name or not has_enum_values or enum_name in seen:
                continue
            seen.add(str(enum_name))
            yield column_type


def _collect_metadata_enum_type_names() -> list[str]:
    return sorted(str(t.name) for t in _iter_metadata_enum_types())


async def _reset_metadata_enum_types(conn) -> None:
    for enum_name in _collect_metadata_enum_type_names():
        safe_name = enum_name.replace('"', '""')
        await conn.execute(text(f'DROP TYPE IF EXISTS public."{safe_name}" CASCADE'))


async def _create_metadata_enum_types(conn) -> None:
    def _create(sync_conn) -> None:
        for enum_type in _iter_metadata_enum_types():
            # Only postgresql.ENUM carries `create_type`; the generic
            # sqlalchemy.Enum does not.  Enums declared create_type=False
            # (e.g. coherence_score_version) are skipped by create_all, so
            # pre-create them here by toggling the flag temporarily.  Every
            # other enum keeps the original plain .create() behaviour.
            create_type = getattr(enum_type, "create_type", None)
            if create_type is False:
                enum_type.create_type = True
                try:
                    enum_type.create(sync_conn, checkfirst=True)
                finally:
                    enum_type.create_type = False
            else:
                enum_type.create(sync_conn, checkfirst=True)

    await conn.run_sync(_create)


def _set_metadata_enum_create_type(enabled: bool) -> None:
    for enum_type in _iter_metadata_enum_types():
        enum_type.create_type = enabled


# ---------------------------------------------------------------------------
# Schema inspection helpers
# ---------------------------------------------------------------------------


_ORM_MODEL_MODULES = (
    "src.analysis.adapters.persistence.models",
    "src.coherence.adapters.persistence.models",
    "src.core.ai.models",
    "src.core.auth.models",
    "src.core.security.adapters.persistence.models",
    "src.documents.adapters.persistence.models",
    "src.procurement.adapters.persistence.models",
    "src.project_state.adapters.persistence.models",
    "src.projects.adapters.persistence.models",
    "src.stakeholders.adapters.persistence.models",
    "src.temporal.adapters.persistence.models",
)


def _register_test_orm_models() -> None:
    """Register every ORM table before creating the isolated test schema."""
    for module_name in _ORM_MODEL_MODULES:
        import_module(module_name)


async def _table_exists(conn, table_name: str) -> bool:
    result = await conn.execute(
        text("SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename=:t"),
        {"t": table_name},
    )
    return result.first() is not None


async def _column_exists(conn, table_name: str, column_name: str) -> bool:
    result = await conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=:t AND column_name=:c"
        ),
        {"t": table_name, "c": column_name},
    )
    return result.first() is not None


async def _ensure_rls_and_audit_compatibility(conn) -> None:
    """Enable RLS policies + patch audit_logs for test compatibility."""
    rls_tables = (
        "tenants", "users", "projects", "documents", "clauses", "analyses",
        "alerts", "extractions", "stakeholders", "wbs_items", "bom_items",
        "stakeholder_wbs_raci", "ai_usage_logs", "audit_logs",
    )
    for table_name in rls_tables:
        if not await _table_exists(conn, table_name):
            continue
        await conn.execute(text(f'ALTER TABLE public."{table_name}" ENABLE ROW LEVEL SECURITY'))
        await conn.execute(text(f'ALTER TABLE public."{table_name}" FORCE ROW LEVEL SECURITY'))
        policy_name = f"{table_name}_allow_all"
        existing = await conn.execute(
            text(
                "SELECT 1 FROM pg_policies "
                "WHERE schemaname='public' AND tablename=:t AND policyname=:p"
            ),
            {"t": table_name, "p": policy_name},
        )
        if existing.first() is None:
            await conn.execute(
                text(
                    f'CREATE POLICY "{policy_name}" ON public."{table_name}" '
                    "USING (true) WITH CHECK (true)"
                )
            )

    if await _table_exists(conn, "audit_logs"):
        for col, ddl in [
            ("user_id", "ADD COLUMN user_id UUID"),
            ("changes", "ADD COLUMN changes JSONB DEFAULT '{}'::jsonb"),
            ("created_at", "ADD COLUMN created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()"),
        ]:
            if not await _column_exists(conn, "audit_logs", col):
                await conn.execute(
                    text(f"ALTER TABLE public.audit_logs {ddl}")
                )


def _ensure_test_fk_stub_tables() -> None:
    """Register minimal stub tables required by cross-module FKs in test metadata."""
    if "wbs_items" not in Base.metadata.tables:
        from sqlalchemy import Table

        Table(
            "wbs_items",
            Base.metadata,
            Column("id", PGUUID(as_uuid=True), primary_key=True),
            extend_existing=True,
        )


# ---------------------------------------------------------------------------
# Auth-schema helpers (Supabase compatibility)
# ---------------------------------------------------------------------------


def _auth_schema_available(session: Session) -> bool:
    cached = session.info.get("auth_schema_available")
    if cached is not None:
        return cached
    try:
        result = session.execute(
            text("SELECT 1 FROM pg_namespace WHERE nspname = 'auth'")
        ).first()
        available = bool(result)
    except Exception:
        available = False
    session.info["auth_schema_available"] = available
    return available


def _auth_user_trigger_enabled(session: Session) -> bool:
    cached = session.info.get("auth_user_trigger_enabled")
    if cached is not None:
        return cached
    try:
        result = session.execute(
            text(
                "SELECT 1 FROM pg_trigger t "
                "JOIN pg_class c ON c.oid = t.tgrelid "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'auth' AND c.relname = 'users' "
                "AND t.tgname = 'on_auth_user_created' AND t.tgenabled <> 'D'"
            )
        ).first()
        enabled = bool(result)
    except Exception:
        enabled = False
    session.info["auth_user_trigger_enabled"] = enabled
    return enabled


@event.listens_for(Session, "before_flush")
def _ensure_auth_users(session: Session, _flush_context, _instances) -> None:
    import json

    from src.core.auth.models import User

    if session.bind is None or session.bind.dialect.name != "postgresql":
        return
    if not _auth_schema_available(session):
        return
    new_users = [obj for obj in session.new if isinstance(obj, User)]
    if not new_users:
        return
    for user in new_users:
        role_value = user.role.value if hasattr(user.role, "value") else str(user.role or "user")
        meta = json.dumps({"tenant_id": str(user.tenant_id), "role": role_value})
        trigger_enabled = _auth_user_trigger_enabled(session)
        if trigger_enabled:
            try:
                session.execute(text("SET LOCAL session_replication_role = replica"))
            except Exception:
                trigger_enabled = False
        session.execute(
            text(
                "INSERT INTO auth.users (id, email, raw_user_meta_data, created_at, updated_at) "
                "VALUES (:id, :email, CAST(:meta AS jsonb), NOW(), NOW()) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {"id": user.id, "email": user.email, "meta": meta},
        )
        if trigger_enabled:
            session.execute(text("SET LOCAL session_replication_role = origin"))


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create a test database engine with full schema bootstrap."""
    from sqlalchemy.exc import OperationalError

    database_url = settings.database_url
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    root_database_url = database_url.rsplit("/", 1)[0] + "/postgres"
    try:
        root_engine = create_async_engine(
            root_database_url,
            echo=False,
            pool_pre_ping=True,
            isolation_level="AUTOCOMMIT",
            connect_args={"statement_cache_size": 0},
        )
        async with root_engine.connect() as conn:
            result = await conn.execute(text("SELECT 1 FROM pg_database WHERE datname = 'c2pro_test'"))
            if not result.scalar_one_or_none():
                await conn.execute(text("CREATE DATABASE c2pro_test"))
        await root_engine.dispose()
    except Exception as exc:
        print(f"[WARNING] Could not ensure c2pro_test database exists: {exc}")

    try:
        engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            connect_args={"statement_cache_size": 0},
        )

        _register_test_orm_models()
        _ensure_test_fk_stub_tables()

        async def _cleanup_bootstrap(conn) -> None:
            await reset_public_schema(conn)

        async def _prepare_bootstrap(conn) -> None:
            await _reset_metadata_enum_types(conn)
            await _create_metadata_enum_types(conn)
            _set_metadata_enum_create_type(False)
            try:
                await conn.run_sync(Base.metadata.create_all)
            finally:
                _set_metadata_enum_create_type(True)
            await _ensure_rls_and_audit_compatibility(conn)

        await run_postgres_test_bootstrap(
            engine,
            cleanup_step=_cleanup_bootstrap,
            prepare_step=_prepare_bootstrap,
            warning_sink=lambda exc: print(f"[WARNING] Bootstrap drop_all skipped: {exc}"),
        )

        # Recreate engine after schema reset to avoid stale pooled connections.
        await engine.dispose()
        engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            connect_args={"statement_cache_size": 0},
        )
        async with engine.begin() as conn:
            _set_metadata_enum_create_type(False)
            try:
                await conn.run_sync(Base.metadata.create_all)
            finally:
                _set_metadata_enum_create_type(True)

        yield engine

        async with engine.begin() as conn:
            try:
                await conn.run_sync(Base.metadata.drop_all)
            except Exception as exc:
                print(f"[WARNING] Teardown drop_all skipped: {exc}")

        await engine.dispose()

    except (OperationalError, OSError) as exc:
        pytest.fail(
            f"PostgreSQL test database unavailable at {settings.database_url}. "
            "Start the test container with `docker-compose -f docker-compose.test.yml up -d`. "
            f"Original error: {exc}"
        )


@pytest_asyncio.fixture(scope="function")
async def test_session_factory(test_engine):
    """Session factory aligned with the test engine."""
    factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    from src.core import database as core_database

    previous = core_database._session_factory
    core_database._session_factory = factory
    try:
        yield factory
    finally:
        core_database._session_factory = previous


@pytest_asyncio.fixture
async def db(test_session_factory) -> AsyncGenerator[AsyncSession, None]:
    """Per-test DB session with automatic rollback."""
    async with test_session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()


@pytest_asyncio.fixture
async def db_session(db) -> AsyncGenerator[AsyncSession, None]:
    """Alias for db (backward compat)."""
    yield db


@pytest_asyncio.fixture
async def async_session(db) -> AsyncGenerator[AsyncSession, None]:
    """Backward-compatible alias used by legacy repository unit suites."""
    yield db


@pytest_asyncio.fixture
async def db_engine(test_engine):
    """Alias for engine (DB probe tests)."""
    return test_engine
