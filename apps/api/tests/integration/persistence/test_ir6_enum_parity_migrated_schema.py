"""IR-6 on a MIGRATED PostgreSQL: every ORM enum label exists in the database, and every
database-only label is an explicit, justified exception.

The standard ``db`` fixture creates enum types from ORM metadata, so it can never observe this
drift. These tests run only against a database built by ``alembic upgrade head``, named by
``C2PRO_MIGRATED_TEST_DSN``.
"""

from __future__ import annotations

import importlib
import os
import pkgutil
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

DSN = os.environ.get("C2PRO_MIGRATED_TEST_DSN")
REQUIRED = os.environ.get("C2PRO_REQUIRE_MIGRATED_TEST_DSN") == "1"

if REQUIRED and not DSN:
    pytest.fail("C2PRO_REQUIRE_MIGRATED_TEST_DSN=1 but C2PRO_MIGRATED_TEST_DSN is not set", pytrace=False)

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not DSN, reason="requires C2PRO_MIGRATED_TEST_DSN (a database migrated with alembic)"),
]

# Labels that exist in the database but are deliberately NOT application vocabulary.
# PostgreSQL cannot drop enum values without recreating the type, and no code path writes these.
DB_ONLY_ALLOWLIST: dict[str, set[str]] = {
    # 20260310_0001 created clausetype with this legacy vocabulary; the application's ClauseType
    # never produces it (ClauseType.GENERAL is an alias of "other").
    "clausetype": {"general", "technical", "legal", "financial", "administrative"},
    # 20260310_0001 created document_type with these; uploads validate against DocumentType,
    # which does not offer them, and no writer produces them.
    "document_type": {"report", "correspondence"},
}


def _async_dsn() -> str:
    assert DSN is not None
    return DSN.replace("postgresql://", "postgresql+asyncpg://", 1)


def _orm_enum_labels() -> dict[str, tuple[set[str], str]]:
    import src
    from src.core.database import Base

    for module in pkgutil.walk_packages(src.__path__, "src."):
        if module.name.endswith((".models", ".orm")) or ".persistence." in module.name:
            try:
                importlib.import_module(module.name)
            except Exception:  # noqa: BLE001 - optional adapters may need extras; parity covers what imports
                continue
    labels: dict[str, tuple[set[str], str]] = {}
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, sa.Enum) and column.type.name:
                known, where = labels.get(column.type.name, (set(), f"{table.name}.{column.name}"))
                labels[column.type.name] = (known | set(column.type.enums), where)
    return labels


async def _db_enum_labels() -> dict[str, set[str]]:
    engine = create_async_engine(_async_dsn())
    try:
        async with engine.connect() as conn:
            rows = await conn.execute(
                sa.text(
                    "SELECT t.typname, e.enumlabel FROM pg_type t JOIN pg_enum e ON e.enumtypid = t.oid "
                    "JOIN pg_namespace n ON n.oid = t.typnamespace WHERE n.nspname = 'public'"
                )
            )
            result: dict[str, set[str]] = {}
            for typname, label in rows:
                result.setdefault(typname, set()).add(label)
            return result
    finally:
        await engine.dispose()


async def test_every_orm_enum_label_exists_in_the_migrated_database() -> None:
    orm = _orm_enum_labels()
    db = await _db_enum_labels()

    missing = {
        f"{name} ({where})": sorted(labels - db.get(name, set()))
        for name, (labels, where) in orm.items()
        if labels - db.get(name, set())
    }
    assert missing == {}


async def test_database_only_labels_are_explicitly_allowlisted() -> None:
    orm = _orm_enum_labels()
    db = await _db_enum_labels()

    unexpected = {
        name: sorted(db[name] - labels - DB_ONLY_ALLOWLIST.get(name, set()))
        for name, (labels, _where) in orm.items()
        if name in db and db[name] - labels - DB_ONLY_ALLOWLIST.get(name, set())
    }
    assert unexpected == {}


async def test_allowlist_does_not_hide_labels_the_application_now_uses() -> None:
    orm = _orm_enum_labels()
    overlap = {name: sorted(allowed & orm[name][0]) for name, allowed in DB_ONLY_ALLOWLIST.items() if allowed & orm[name][0]}
    assert overlap == {}


@pytest.mark.parametrize(
    "project_type",
    ["epc", "civil", "building", "maritime", "chemical", "energy", "municipal", "oil_gas", "mining", "construction"],
)
async def test_projects_created_with_any_offered_type_load_back(project_type: str) -> None:
    from src.projects.adapters.persistence.models import ProjectORM
    from src.projects.adapters.persistence.project_repository import SQLAlchemyProjectRepository

    engine = create_async_engine(_async_dsn())
    tenant_id, project_id = uuid4(), uuid4()
    try:
        async with AsyncSession(engine) as session:
            transaction = await session.begin()
            try:
                await session.execute(
                    sa.text("INSERT INTO tenants (id, name, slug, subscription_plan) VALUES (:id, 'IR6', :slug, 'free')"),
                    {"id": tenant_id, "slug": f"ir6-{tenant_id}"},
                )
                await session.execute(
                    sa.text(
                        "INSERT INTO projects (id, tenant_id, name, code, project_type, status, currency) "
                        "VALUES (:id, :tid, 'IR6 project', :code, CAST(:ptype AS projecttype), 'active', 'EUR')"
                    ),
                    {"id": project_id, "tid": tenant_id, "code": f"IR6-{str(project_id)[:8]}", "ptype": project_type},
                )
                loaded = (await session.execute(sa.select(ProjectORM).where(ProjectORM.id == project_id))).scalar_one()
                assert loaded.project_type == project_type
                domain = SQLAlchemyProjectRepository(session)._to_entity(loaded)
                assert domain.project_type.value == project_type
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
