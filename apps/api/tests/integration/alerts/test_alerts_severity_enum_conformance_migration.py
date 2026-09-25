"""TASK-P0a-004: migration evidence for alerts.severity enum conformance.

Exercises Alembic revision ``20260824_0001`` against an ephemeral PostgreSQL
database (same pattern as ``test_alerts_schema_matches_orm.py``). Demonstrates:

* drifted ``character varying(20)`` -> upgrade -> ``alertseverity`` (values preserved);
* dependent ``security_invoker`` view ``v_project_alerts`` survives with its
  definition, ``security_invoker`` option and **exact** non-owner grants + owner —
  including stripping a privilege injected via schema default privileges;
* ``ix_alerts_severity`` survives the type change;
* severity filtering/ranking SQL (native enum *and* the #558 AS-TEXT form) works;
* an invalid/unconvertible value -> guarded failure with no partial mutation;
* an unexpected ``varchar`` shape (wrong length / nullable / has default) -> abort
  with no partial mutation;
* a non-canonical ``alertseverity`` label set -> abort before mutation;
* idempotent no-op when already ``alertseverity`` and a real, reversible downgrade
  back to ``varchar(20)`` (upgrade -> downgrade -> upgrade round-trip).

Requires a reachable PostgreSQL superuser (``TEST_DATABASE_URL`` /
``settings.database_url``); runs in the ``integration`` lane on CI.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Sequence
from typing import TypeVar
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from alembic import command
from src.analysis.adapters.persistence.models import Alert
from src.analysis.domain.enums import AlertSeverity
from src.config import settings

DOWN_REVISION = "20260814_0002"
REVISION = "20260824_0001"

_T = TypeVar("_T")


def _run(coro: Awaitable[_T]) -> _T:
    return asyncio.run(coro)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# URL + database lifecycle helpers (mirrors test_alerts_schema_matches_orm.py) #
# --------------------------------------------------------------------------- #
def _to_async_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _to_sync_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


async def _create_database(root_url: str, database_name: str) -> None:
    engine = create_async_engine(root_url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(text(f'CREATE DATABASE "{database_name}"'))
    await engine.dispose()


async def _drop_database(root_url: str, database_name: str) -> None:
    engine = create_async_engine(root_url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(
            text(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = :database_name AND pid <> pg_backend_pid()
                """
            ),
            {"database_name": database_name},
        )
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
    await engine.dispose()


class _EphemeralDb:
    """Create/migrate/drop a throwaway database and drive Alembic against it."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        base_url = _to_async_url(settings.database_url)
        self.root_url = base_url.rsplit("/", 1)[0] + "/postgres"
        self.database_name = f"c2pro_sev_conf_{uuid4().hex[:12]}"
        self.async_url = self.root_url.rsplit("/", 1)[0] + f"/{self.database_name}"
        self.sync_url = _to_sync_url(self.async_url)
        self._monkeypatch = monkeypatch

    def __enter__(self) -> _EphemeralDb:
        _run(_create_database(self.root_url, self.database_name))
        # Alembic reads settings.database_url (sync) for the target database.
        self._monkeypatch.setattr(settings, "database_url", self.sync_url)
        return self

    def __exit__(self, *_exc: object) -> None:
        _run(_drop_database(self.root_url, self.database_name))

    def upgrade(self, revision: str) -> None:
        command.upgrade(Config("alembic.ini"), revision)

    def downgrade(self, revision: str) -> None:
        command.downgrade(Config("alembic.ini"), revision)


# --------------------------------------------------------------------------- #
# Introspection helpers                                                        #
# --------------------------------------------------------------------------- #
async def _scalar(url: str, sql: str, **params: object) -> object:
    engine = create_async_engine(_to_async_url(url))
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(sql), params)
            return result.scalar()
    finally:
        await engine.dispose()


async def _rows(url: str, sql: str, **params: object) -> list[tuple]:
    engine = create_async_engine(_to_async_url(url))
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(sql), params)
            return [tuple(row) for row in result.all()]
    finally:
        await engine.dispose()


async def _exec(url: str, statements: Sequence[str]) -> None:
    engine = create_async_engine(_to_async_url(url), isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            for statement in statements:
                await conn.execute(text(statement))
    finally:
        await engine.dispose()


async def _severity_udt(url: str) -> str | None:
    value = await _scalar(
        url,
        """
        SELECT udt_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'alerts' AND column_name = 'severity'
        """,
    )
    return None if value is None else str(value)


async def _severity_not_null(url: str) -> bool:
    value = await _scalar(
        url,
        """
        SELECT is_nullable FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'alerts' AND column_name = 'severity'
        """,
    )
    return value == "NO"


async def _severity_shape(url: str) -> tuple:
    rows = await _rows(
        url,
        """
        SELECT udt_name, character_maximum_length, is_nullable, (column_default IS NOT NULL)
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'alerts' AND column_name = 'severity'
        """,
    )
    return rows[0]


async def _view_exists(url: str) -> bool:
    return bool(
        await _scalar(
            url,
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relname = 'v_project_alerts' AND c.relkind = 'v'
            )
            """,
        )
    )


async def _view_is_security_invoker(url: str) -> bool:
    return bool(
        await _scalar(
            url,
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_class c, unnest(c.reloptions) o
                WHERE c.oid = 'public.v_project_alerts'::regclass
                  AND o ILIKE 'security_invoker=%'
                  AND split_part(o, '=', 2) IN ('true', 'on', '1')
            )
            """,
        )
    )


async def _view_owner(url: str) -> str:
    return str(
        await _scalar(
            url,
            "SELECT pg_get_userbyid(relowner) FROM pg_class WHERE oid = 'public.v_project_alerts'::regclass",
        )
    )


async def _nonowner_grants(url: str) -> set[tuple[str, str]]:
    rows = await _rows(
        url,
        """
        SELECT grantee, privilege_type FROM information_schema.role_table_grants
        WHERE table_schema = 'public' AND table_name = 'v_project_alerts'
          AND grantee <> (
              SELECT pg_get_userbyid(relowner) FROM pg_class
              WHERE oid = 'public.v_project_alerts'::regclass
          )
        """,
    )
    return {(str(g), str(p)) for g, p in rows}


async def _viewdef(url: str) -> str:
    return str(
        await _scalar(url, "SELECT pg_get_viewdef('public.v_project_alerts'::regclass, true)")
    )


async def _index_exists(url: str, name: str) -> bool:
    return bool(
        await _scalar(
            url,
            "SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname=:n)",
            n=name,
        )
    )


# --------------------------------------------------------------------------- #
# Drift + seed helpers                                                         #
# --------------------------------------------------------------------------- #
_DRIFT_VIEW = (
    "CREATE VIEW public.v_project_alerts AS "
    "SELECT a.id, a.project_id, a.severity, a.title, a.status, a.created_at FROM public.alerts a"
)


async def _drift_severity_to_varchar(url: str) -> None:
    """Reproduce production drift: varchar(20) NOT NULL, no default + a grant."""
    await _exec(
        url,
        [
            "DROP VIEW IF EXISTS public.v_project_alerts",
            "ALTER TABLE public.alerts ALTER COLUMN severity TYPE varchar(20) USING severity::text",
            _DRIFT_VIEW,
            "ALTER VIEW public.v_project_alerts SET (security_invoker = true)",
            # Sentinel non-default grant to prove the migration preserves privileges.
            "GRANT SELECT ON public.v_project_alerts TO PUBLIC",
        ],
    )


async def _reshape_severity(
    url: str, type_sql: str, not_null: bool, default_sql: str | None
) -> None:
    """Put alerts.severity into an arbitrary (possibly unapproved) varchar shape."""
    statements = [
        "DROP VIEW IF EXISTS public.v_project_alerts",
        "ALTER TABLE public.alerts ALTER COLUMN severity DROP DEFAULT",
        f"ALTER TABLE public.alerts ALTER COLUMN severity TYPE {type_sql} USING severity::text",
        "ALTER TABLE public.alerts ALTER COLUMN severity "
        + ("SET NOT NULL" if not_null else "DROP NOT NULL"),
    ]
    if default_sql is not None:
        statements.append(
            f"ALTER TABLE public.alerts ALTER COLUMN severity SET DEFAULT {default_sql}"
        )
    statements += [_DRIFT_VIEW, "ALTER VIEW public.v_project_alerts SET (security_invoker = true)"]
    await _exec(url, statements)


async def _setup_default_priv_probe(url: str, role: str) -> None:
    """Grant future public views SELECT to `role` via schema default privileges."""
    await _exec(
        url,
        [
            f"CREATE ROLE {role} NOLOGIN",
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO {role}",
        ],
    )


async def _drop_role(root_url: str, role: str) -> None:
    await _exec(root_url, [f"DROP ROLE IF EXISTS {role}"])


async def _tamper_enum_add_label(url: str, label: str) -> None:
    await _exec(url, [f"ALTER TYPE public.alertseverity ADD VALUE IF NOT EXISTS '{label}'"])


async def _seed_alerts(url: str, severities: Sequence[AlertSeverity]) -> None:
    engine = create_async_engine(_to_async_url(url))
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            for sev in severities:
                session.add(
                    Alert(
                        project_id=uuid4(),
                        severity=sev,
                        title=f"seed-{sev.value}",
                        message="seed message",
                        description="seed description",
                    )
                )
            await session.commit()
    finally:
        await engine.dispose()


async def _raw_set_severity(url: str, value: str) -> None:
    await _exec(url, [f"UPDATE public.alerts SET severity = '{value}'"])


# --------------------------------------------------------------------------- #
# Tests                                                                        #
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_upgrade_conforms_drifted_varchar_to_enum(monkeypatch: pytest.MonkeyPatch) -> None:
    """varchar(20) drift -> enum, preserving data, index and EXACT view privileges."""
    probe = f"c2pro_probe_{uuid4().hex[:8]}"
    root_url = _to_async_url(settings.database_url).rsplit("/", 1)[0] + "/postgres"
    try:
        with _EphemeralDb(monkeypatch) as db:
            db.upgrade(DOWN_REVISION)
            _run(
                _seed_alerts(
                    db.async_url,
                    [AlertSeverity.CRITICAL, AlertSeverity.HIGH, AlertSeverity.LOW],
                )
            )
            _run(_drift_severity_to_varchar(db.async_url))
            assert _run(_severity_udt(db.async_url)) == "varchar"

            owner_before = _run(_view_owner(db.async_url))
            nonowner_before = _run(_nonowner_grants(db.async_url))
            assert ("PUBLIC", "SELECT") in nonowner_before
            viewdef_before = _run(_viewdef(db.async_url))

            # Inject a schema default privilege: the migration's CREATE VIEW would
            # auto-grant SELECT to `probe`. Exact ACL restore must strip that extra.
            _run(_setup_default_priv_probe(db.async_url, probe))

            db.upgrade(REVISION)

            # Column conformed, NOT NULL preserved, index survived, values intact.
            assert _run(_severity_udt(db.async_url)) == "alertseverity"
            assert _run(_severity_not_null(db.async_url)) is True
            assert _run(_index_exists(db.async_url, "ix_alerts_severity")) is True
            labels = _run(_rows(db.async_url, "SELECT severity::text FROM public.alerts"))
            assert {row[0] for row in labels} == {"critical", "high", "low"}

            # EXACT view privilege parity: same non-owner grants, no injected extra,
            # same owner, same definition, still security_invoker.
            nonowner_after = _run(_nonowner_grants(db.async_url))
            assert nonowner_after == nonowner_before
            assert all(grantee != probe for grantee, _ in nonowner_after)
            assert _run(_view_owner(db.async_url)) == owner_before
            assert _run(_viewdef(db.async_url)) == viewdef_before
            assert _run(_view_is_security_invoker(db.async_url)) is True

            # Native-enum comparison (the point of conformance) now works.
            native = _run(
                _rows(
                    db.async_url,
                    "SELECT id FROM public.alerts WHERE severity = 'critical'::public.alertseverity",
                )
            )
            assert len(native) == 1

            # #558 AS-TEXT filtering + ranking still works against the conformed column.
            ordered = _run(
                _rows(
                    db.async_url,
                    """
                    SELECT severity::text FROM public.alerts
                    ORDER BY CASE severity::text
                        WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                        WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 4 END
                    """,
                )
            )
            assert [row[0] for row in ordered] == ["critical", "high", "low"]
    finally:
        with contextlib.suppress(Exception):
            _run(_drop_role(root_url, probe))


@pytest.mark.integration
def test_upgrade_rejects_invalid_value_without_partial_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unconvertible severity aborts the migration; column + view stay untouched."""
    with _EphemeralDb(monkeypatch) as db:
        db.upgrade(DOWN_REVISION)
        _run(_seed_alerts(db.async_url, [AlertSeverity.LOW]))
        _run(_drift_severity_to_varchar(db.async_url))
        _run(_raw_set_severity(db.async_url, "bogus"))

        with pytest.raises(Exception):  # noqa: B017 - DBAPI wraps the guarded RAISE
            db.upgrade(REVISION)

        assert _run(_severity_udt(db.async_url)) == "varchar"
        remaining = _run(_rows(db.async_url, "SELECT severity::text FROM public.alerts"))
        assert {row[0] for row in remaining} == {"bogus"}
        assert _run(_view_exists(db.async_url)) is True


@pytest.mark.integration
def test_upgrade_aborts_on_unexpected_varchar_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    """VARCHAR that is not exactly varchar(20) NOT NULL no-default aborts, no mutation."""
    with _EphemeralDb(monkeypatch) as db:
        db.upgrade(DOWN_REVISION)
        _run(_seed_alerts(db.async_url, [AlertSeverity.LOW]))

        for type_sql, not_null, default_sql in (
            ("varchar(30)", True, None),  # wrong length
            ("varchar(20)", False, None),  # nullable
            ("varchar(20)", True, "'low'::varchar"),  # has a default
        ):
            _run(_reshape_severity(db.async_url, type_sql, not_null, default_sql))
            shape_before = _run(_severity_shape(db.async_url))

            with pytest.raises(Exception):  # noqa: B017 - DBAPI wraps the guarded RAISE
                db.upgrade(REVISION)

            assert _run(_severity_udt(db.async_url)) == "varchar"
            assert _run(_severity_shape(db.async_url)) == shape_before  # no partial mutation
            assert _run(_view_exists(db.async_url)) is True


@pytest.mark.integration
def test_upgrade_aborts_on_noncanonical_enum_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    """A tampered public.alertseverity label set aborts before any mutation."""
    with _EphemeralDb(monkeypatch) as db:
        db.upgrade(DOWN_REVISION)
        _run(_seed_alerts(db.async_url, [AlertSeverity.LOW]))
        _run(_drift_severity_to_varchar(db.async_url))  # valid varchar(20) shape
        _run(_tamper_enum_add_label(db.async_url, "info"))

        with pytest.raises(Exception):  # noqa: B017 - DBAPI wraps the guarded RAISE
            db.upgrade(REVISION)

        # Label guard fires before the cast -> column untouched, view intact.
        assert _run(_severity_udt(db.async_url)) == "varchar"
        assert _run(_view_exists(db.async_url)) is True


@pytest.mark.integration
def test_downgrade_and_upgrade_roundtrip_is_reversible(monkeypatch: pytest.MonkeyPatch) -> None:
    """No-op on already-enum, real downgrade to varchar(20), then re-upgrade to enum."""
    with _EphemeralDb(monkeypatch) as db:
        # Fresh upgrade lands on the enum already -> migration takes the no-op path.
        db.upgrade(REVISION)
        assert _run(_severity_udt(db.async_url)) == "alertseverity"
        assert _run(_view_exists(db.async_url)) is True
        owner0 = _run(_view_owner(db.async_url))
        nonowner0 = _run(_nonowner_grants(db.async_url))

        # Real downgrade back to varchar(20), preserving the (canonical) view contract.
        db.downgrade(DOWN_REVISION)
        assert _run(_severity_udt(db.async_url)) == "varchar"
        assert _run(_severity_not_null(db.async_url)) is True
        assert _run(_view_exists(db.async_url)) is True
        assert _run(_view_is_security_invoker(db.async_url)) is True
        assert _run(_view_owner(db.async_url)) == owner0
        assert _run(_nonowner_grants(db.async_url)) == nonowner0

        # Re-upgrade converts the varchar back to the enum through Alembic.
        db.upgrade(REVISION)
        assert _run(_severity_udt(db.async_url)) == "alertseverity"
        assert _run(_severity_not_null(db.async_url)) is True
        assert _run(_view_exists(db.async_url)) is True
        assert _run(_view_is_security_invoker(db.async_url)) is True
        assert _run(_view_owner(db.async_url)) == owner0
        assert _run(_nonowner_grants(db.async_url)) == nonowner0
