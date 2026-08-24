"""TASK-P0a-004: migration evidence for alerts.severity enum conformance.

Exercises Alembic revision ``20260824_0001`` against an ephemeral PostgreSQL
database (same pattern as ``test_alerts_schema_matches_orm.py``). Demonstrates:

* drifted ``character varying`` -> upgrade -> ``alertseverity`` (values preserved);
* dependent ``security_invoker`` view ``v_project_alerts`` survives with its
  definition, ``security_invoker`` option and grants intact;
* ``ix_alerts_severity`` survives the type change;
* severity filtering/ranking SQL (native enum *and* the #558 AS-TEXT form) works
  after conformance;
* an invalid/unconvertible value causes a guarded failure with **no partial
  mutation** (column stays ``varchar``, view stays present);
* idempotent no-op when already ``alertseverity`` and a real, reversible
  downgrade back to ``varchar(20)`` (upgrade -> downgrade -> upgrade round-trip).

Requires a reachable PostgreSQL superuser (``TEST_DATABASE_URL`` /
``settings.database_url``); runs in the ``integration`` lane on CI.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
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
        self._root_url = base_url.rsplit("/", 1)[0] + "/postgres"
        self.database_name = f"c2pro_sev_conf_{uuid4().hex[:12]}"
        self.async_url = self._root_url.rsplit("/", 1)[0] + f"/{self.database_name}"
        self.sync_url = _to_sync_url(self.async_url)
        self._monkeypatch = monkeypatch

    def __enter__(self) -> _EphemeralDb:
        asyncio.run(_create_database(self._root_url, self.database_name))
        # Alembic reads settings.database_url (sync) for the target database.
        self._monkeypatch.setattr(settings, "database_url", self.sync_url)
        return self

    def __exit__(self, *_exc: object) -> None:
        asyncio.run(_drop_database(self._root_url, self.database_name))

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


async def _view_grants(url: str) -> set[tuple[str, str]]:
    rows = await _rows(
        url,
        """
        SELECT grantee, privilege_type FROM information_schema.role_table_grants
        WHERE table_schema = 'public' AND table_name = 'v_project_alerts'
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
async def _drift_severity_to_varchar(url: str) -> None:
    """Reproduce production drift: varchar column + a security_invoker view + grant."""
    engine = create_async_engine(_to_async_url(url), isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            await conn.execute(text("DROP VIEW IF EXISTS public.v_project_alerts"))
            await conn.execute(
                text(
                    "ALTER TABLE public.alerts "
                    "ALTER COLUMN severity TYPE varchar(20) USING severity::text"
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE VIEW public.v_project_alerts AS
                    SELECT a.id, a.project_id, a.severity, a.title, a.status, a.created_at
                    FROM public.alerts a
                    """
                )
            )
            await conn.execute(
                text("ALTER VIEW public.v_project_alerts SET (security_invoker = true)")
            )
            # Sentinel non-default grant to prove the migration preserves privileges.
            await conn.execute(text("GRANT SELECT ON public.v_project_alerts TO PUBLIC"))
    finally:
        await engine.dispose()


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
    engine = create_async_engine(_to_async_url(url), isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            await conn.execute(text("UPDATE public.alerts SET severity = :v"), {"v": value})
    finally:
        await engine.dispose()


# --------------------------------------------------------------------------- #
# Tests                                                                        #
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_upgrade_conforms_drifted_varchar_to_enum(monkeypatch: pytest.MonkeyPatch) -> None:
    """varchar(20) drift -> upgrade -> alertseverity, preserving data + view + index."""
    with _EphemeralDb(monkeypatch) as db:
        db.upgrade(DOWN_REVISION)
        # Seed while the column is the canonical enum, then reproduce the varchar drift.
        asyncio.run(
            _seed_alerts(
                db.async_url,
                [AlertSeverity.CRITICAL, AlertSeverity.HIGH, AlertSeverity.LOW],
            )
        )
        asyncio.run(_drift_severity_to_varchar(db.async_url))
        assert asyncio.run(_severity_udt(db.async_url)) == "varchar"

        viewdef_before = asyncio.run(_viewdef(db.async_url))
        grants_before = asyncio.run(_view_grants(db.async_url))
        assert ("PUBLIC", "SELECT") in grants_before

        db.upgrade(REVISION)

        # Column conformed, NOT NULL preserved, index survived.
        assert asyncio.run(_severity_udt(db.async_url)) == "alertseverity"
        assert asyncio.run(_severity_not_null(db.async_url)) is True
        assert asyncio.run(_index_exists(db.async_url, "ix_alerts_severity")) is True

        # Values preserved through the conversion.
        labels = asyncio.run(_rows(db.async_url, "SELECT severity::text FROM public.alerts"))
        assert {row[0] for row in labels} == {"critical", "high", "low"}

        # View preserved: exists, same definition, security_invoker, and grants.
        assert asyncio.run(_view_exists(db.async_url)) is True
        assert asyncio.run(_view_is_security_invoker(db.async_url)) is True
        assert asyncio.run(_viewdef(db.async_url)) == viewdef_before
        assert grants_before <= asyncio.run(_view_grants(db.async_url))

        # Native-enum comparison (the whole point of conformance) now works.
        native = asyncio.run(
            _rows(
                db.async_url,
                "SELECT id FROM public.alerts WHERE severity = 'critical'::public.alertseverity",
            )
        )
        assert len(native) == 1

        # #558 AS-TEXT filtering + ranking still works against the conformed column.
        ordered = asyncio.run(
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


@pytest.mark.integration
def test_upgrade_rejects_invalid_value_without_partial_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unconvertible severity aborts the migration; column + view stay untouched."""
    with _EphemeralDb(monkeypatch) as db:
        db.upgrade(DOWN_REVISION)
        asyncio.run(_seed_alerts(db.async_url, [AlertSeverity.LOW]))
        asyncio.run(_drift_severity_to_varchar(db.async_url))
        asyncio.run(_raw_set_severity(db.async_url, "bogus"))

        with pytest.raises(Exception):  # noqa: B017 - DBAPI wraps the guarded RAISE
            db.upgrade(REVISION)

        # No partial mutation: still varchar, offending value intact, view still present.
        assert asyncio.run(_severity_udt(db.async_url)) == "varchar"
        remaining = asyncio.run(_rows(db.async_url, "SELECT severity::text FROM public.alerts"))
        assert {row[0] for row in remaining} == {"bogus"}
        assert asyncio.run(_view_exists(db.async_url)) is True


@pytest.mark.integration
def test_downgrade_and_upgrade_roundtrip_is_reversible(monkeypatch: pytest.MonkeyPatch) -> None:
    """No-op on already-enum, real downgrade to varchar(20), then re-upgrade to enum."""
    with _EphemeralDb(monkeypatch) as db:
        # Fresh upgrade lands on the enum already -> migration takes the idempotent no-op path.
        db.upgrade(REVISION)
        assert asyncio.run(_severity_udt(db.async_url)) == "alertseverity"
        assert asyncio.run(_view_exists(db.async_url)) is True

        # Real downgrade back to varchar(20), preserving the (canonical) view contract.
        db.downgrade(DOWN_REVISION)
        assert asyncio.run(_severity_udt(db.async_url)) == "varchar"
        assert asyncio.run(_severity_not_null(db.async_url)) is True
        assert asyncio.run(_view_exists(db.async_url)) is True
        assert asyncio.run(_view_is_security_invoker(db.async_url)) is True

        # Re-upgrade converts the varchar back to the enum through Alembic.
        db.upgrade(REVISION)
        assert asyncio.run(_severity_udt(db.async_url)) == "alertseverity"
        assert asyncio.run(_severity_not_null(db.async_url)) is True
        assert asyncio.run(_view_exists(db.async_url)) is True
        assert asyncio.run(_view_is_security_invoker(db.async_url)) is True
