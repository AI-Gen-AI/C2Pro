"""Focused branch coverage for the C2.5 admin-operations database boundary."""

from __future__ import annotations

import importlib
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.core.database as database
from src.config import settings

_CATALOG_FIELDS = (
    "rolcanlogin",
    "rolsuper",
    "rolbypassrls",
    "rolcreaterole",
    "rolcreatedb",
    "is_member",
    "is_table_owner",
    "has_extra_inherited",
    "is_db_owner",
    "is_schema_owner",
    "has_db_create",
    "has_schema_create",
    "session_user_eq_current_user",
    "has_direct_rel_grants",
    "has_direct_col_grants",
    "has_direct_schema_grants",
    "has_direct_db_grants",
    "has_direct_proc_grants",
    "has_direct_default_acls",
)


def _catalog_row(**overrides: bool) -> tuple[bool, ...]:
    values = {
        "rolcanlogin": True,
        "rolsuper": False,
        "rolbypassrls": False,
        "rolcreaterole": False,
        "rolcreatedb": False,
        "is_member": True,
        "is_table_owner": False,
        "has_extra_inherited": False,
        "is_db_owner": False,
        "is_schema_owner": False,
        "has_db_create": False,
        "has_schema_create": False,
        "session_user_eq_current_user": True,
        "has_direct_rel_grants": False,
        "has_direct_col_grants": False,
        "has_direct_schema_grants": False,
        "has_direct_db_grants": False,
        "has_direct_proc_grants": False,
        "has_direct_default_acls": False,
    }
    values.update(overrides)
    return tuple(values[name] for name in _CATALOG_FIELDS)


def _session_factory_for(
    row: tuple[bool, ...],
):
    session = MagicMock()
    session.bind = MagicMock()
    session.bind.dialect.name = "postgresql"

    result = MagicMock()
    result.fetchone.return_value = row

    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    @asynccontextmanager
    async def session_context():
        yield session

    def factory():
        return session_context()

    return factory, session


@pytest.fixture(autouse=True)
def reset_admin_ops_globals(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(database, "_admin_ops_engine", None)
    monkeypatch.setattr(database, "_admin_ops_session_factory", None)


@pytest.mark.asyncio
async def test_init_admin_ops_db_normalizes_dsn_and_assigns_engine_and_factory() -> None:
    engine = MagicMock()
    factory = MagicMock()

    with (
        patch.object(
            settings,
            "admin_ops_database_url",
            "postgresql://restricted:fake@db.example/c2pro",
        ),
        patch.object(
            database,
            "create_async_engine",
            return_value=engine,
        ) as create_engine,
        patch.object(
            database,
            "async_sessionmaker",
            return_value=factory,
        ) as make_session_factory,
    ):
        await database.init_admin_ops_db()

    create_engine.assert_called_once()
    assert (
        create_engine.call_args.args[0]
        == "postgresql+asyncpg://restricted:fake@db.example/c2pro"
    )
    make_session_factory.assert_called_once()
    assert database._admin_ops_engine is engine
    assert database._admin_ops_session_factory is factory


@pytest.mark.asyncio
async def test_close_admin_ops_db_disposes_engine_and_clears_globals() -> None:
    engine = MagicMock()
    engine.dispose = AsyncMock()

    database._admin_ops_engine = engine
    database._admin_ops_session_factory = MagicMock()

    await database.close_admin_ops_db()

    engine.dispose.assert_awaited_once()
    assert database._admin_ops_engine is None
    assert database._admin_ops_session_factory is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"rolcanlogin": False}, "lacks LOGIN"),
        ({"rolbypassrls": True}, "BypassRLS"),
        ({"rolcreaterole": True}, "CreateRole"),
        (
            {"has_extra_inherited": True},
            "unexpected inherited role memberships",
        ),
        (
            {"has_direct_rel_grants": True},
            "unexpected direct relation",
        ),
        (
            {"has_direct_col_grants": True},
            "unexpected direct column",
        ),
        (
            {"has_direct_schema_grants": True},
            "unexpected direct schema",
        ),
        (
            {"has_direct_db_grants": True},
            "unexpected direct database",
        ),
        (
            {"has_direct_proc_grants": True},
            "unexpected direct function",
        ),
        (
            {"has_direct_default_acls": True},
            "unexpected direct default ACLs",
        ),
    ],
    ids=[
        "no-login",
        "bypass-rls",
        "create-role",
        "extra-inherited-role",
        "direct-relation-grant",
        "direct-column-grant",
        "direct-schema-grant",
        "direct-database-grant",
        "direct-procedure-grant",
        "direct-default-acl",
    ],
)
async def test_admin_ops_session_rejects_remaining_elevated_principal_paths(
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, bool],
    message: str,
) -> None:
    factory, session = _session_factory_for(_catalog_row(**overrides))
    monkeypatch.setattr(database, "_admin_ops_session_factory", factory)

    with pytest.raises(RuntimeError, match=message):
        async with database.get_admin_ops_session():
            pytest.fail("invalid admin principal reached protected body")

    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_ops_session_rolls_back_when_protected_body_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory, session = _session_factory_for(_catalog_row())
    monkeypatch.setattr(database, "_admin_ops_session_factory", factory)

    with pytest.raises(ValueError, match="synthetic body failure"):
        async with database.get_admin_ops_session():
            raise ValueError("synthetic body failure")

    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_adapter_admin_session_yields_real_admin_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router_module = importlib.import_module("src.admin.adapters.http.router")
    session = MagicMock()

    @asynccontextmanager
    async def fake_get_admin_ops_session():
        yield session

    monkeypatch.setattr(
        router_module,
        "get_admin_ops_session",
        fake_get_admin_ops_session,
    )

    adapter = router_module.DLQAdminOpsAdapter()

    async with adapter._admin_session() as yielded:
        assert yielded is session


def test_get_dlq_admin_port_returns_admin_ops_adapter() -> None:
    router_module = importlib.import_module("src.admin.adapters.http.router")

    port = router_module.get_dlq_admin_port()

    assert isinstance(port, router_module.DLQAdminOpsAdapter)
