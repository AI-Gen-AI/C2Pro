"""TS-HOTFIX-ALERTS-SCHEMA-DRIFT-001.

Regression tests for migrated alerts schema parity with the Alert ORM.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.analysis.adapters.persistence.models import Alert
from src.config import settings


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


async def _alert_columns(database_url: str) -> set[str]:
    engine = create_async_engine(_to_async_url(database_url))
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'alerts'
                """
            )
        )
        columns = {str(row[0]) for row in result}
    await engine.dispose()
    return columns


@pytest.mark.integration
def test_migrated_alerts_table_has_every_alert_orm_column(monkeypatch: pytest.MonkeyPatch) -> None:
    """Migrated DB, not create_all, must match Alert ORM columns."""
    base_url = _to_async_url(settings.database_url)
    root_url = base_url.rsplit("/", 1)[0] + "/postgres"
    database_name = f"c2pro_alert_schema_{uuid4().hex[:12]}"
    migrated_url = root_url.rsplit("/", 1)[0] + f"/{database_name}"
    sync_migrated_url = _to_sync_url(migrated_url)

    orm_columns = {column.name for column in Alert.__table__.columns}
    assert "message" in orm_columns

    asyncio.run(_create_database(root_url, database_name))
    try:
        monkeypatch.setattr(settings, "database_url", sync_migrated_url)
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")

        db_columns = asyncio.run(_alert_columns(migrated_url))
        missing = sorted(orm_columns - db_columns)
        assert missing == []
    finally:
        asyncio.run(_drop_database(root_url, database_name))
