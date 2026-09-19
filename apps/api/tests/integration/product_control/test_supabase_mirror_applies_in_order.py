"""The Supabase migration mirror applies cleanly, in filename order, on a real PostgreSQL.

Regression guard for the ADR-025 release-candidate defect: Alembic's
``20260814_0002_add_wbs_source_document_id.py`` added
``procurement_wbs_items.source_document_id`` to the authoritative history, but its
Supabase mirror (``supabase/migrations/``) was never committed -- so a fresh Supabase
preview database, which is built ONLY from that mirror directory (never from Alembic),
reached ``20260914000500_adr025_canonical_wbs_data_and_references.sql`` without the
column and failed with ``column w.source_document_id does not exist`` (SQLSTATE 42703).

Alembic's own migration graph was never broken (apps/api/tests/unit/product_control/
test_adr025_wbs_migrations.py and the alembic-scratch-DB
test_adr025_wbs_legacy_data_migration.py both already pass) -- this is specifically an
Alembic/Supabase mirror drift class of defect, invisible to any Alembic-only test.

This test reproduces the exact predecessor schema the Supabase mirror set builds on (a
minimal Supabase-platform stub -- ``auth.users``/``auth.uid()``/``auth.jwt()`` -- plus
every ``supabase/migrations/*.sql`` file in filename order) and fails loudly, with the
real Postgres error, the moment any migration in the mirror set references a column,
table or function nothing before it created.

Requires ``C2PRO_MIGRATION_SCRATCH_DSN`` (a disposable database whose name ends with
``_test``), the same fixture this repository's other scratch-database migration tests
use. With ``C2PRO_REQUIRE_MIGRATED_TEST_DSN=1`` (CI) a missing DSN is a failure.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import pytest

asyncpg = pytest.importorskip("asyncpg")

SCRATCH_DSN = os.environ.get("C2PRO_MIGRATION_SCRATCH_DSN")
REQUIRED = os.environ.get("C2PRO_REQUIRE_MIGRATED_TEST_DSN") == "1"

if REQUIRED and not SCRATCH_DSN:
    pytest.fail("C2PRO_REQUIRE_MIGRATED_TEST_DSN=1 but C2PRO_MIGRATION_SCRATCH_DSN is not set", pytrace=False)

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not SCRATCH_DSN, reason="requires C2PRO_MIGRATION_SCRATCH_DSN (a disposable *_test database)"),
]

API_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = API_ROOT.parents[1]
SUPABASE_MIGRATIONS = REPO_ROOT / "supabase" / "migrations"

# Minimal stand-in for the Supabase-platform schema every mirror migration assumes
# already exists (a real Supabase project provisions this itself; a plain scratch
# PostgreSQL does not). Kept deliberately small: just enough surface -- auth.users,
# auth.uid(), auth.jwt(), and the three platform roles -- for RLS policies and the
# auth.users FK to resolve, without asserting anything about Supabase's own internals.
_PLATFORM_STUB = """
CREATE SCHEMA IF NOT EXISTS auth;
CREATE TABLE IF NOT EXISTS auth.users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email text,
    raw_user_meta_data jsonb DEFAULT '{}'::jsonb,
    created_at timestamptz DEFAULT now()
);
CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid AS $$
  SELECT NULLIF(current_setting('request.jwt.claim.sub', true), '')::uuid
$$ LANGUAGE sql STABLE;
CREATE OR REPLACE FUNCTION auth.jwt() RETURNS jsonb AS $$
  SELECT NULLIF(current_setting('request.jwt.claims', true), '')::jsonb
$$ LANGUAGE sql STABLE;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        CREATE ROLE authenticated;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        CREATE ROLE anon;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        CREATE ROLE service_role;
    END IF;
END
$$;
"""


def _database_name(dsn: str) -> str:
    return urlparse(dsn).path.lstrip("/")


def _maintenance_dsn(dsn: str) -> str:
    return urlunparse(urlparse(dsn)._replace(path="/postgres"))


async def _recreate_scratch_database() -> None:
    assert SCRATCH_DSN is not None
    name = _database_name(SCRATCH_DSN)
    assert name.endswith("_test"), f"refusing to recreate {name!r}: scratch database names must end with _test"
    admin = await asyncpg.connect(_maintenance_dsn(SCRATCH_DSN))
    try:
        await admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await admin.execute(f'CREATE DATABASE "{name}"')
    finally:
        await admin.close()


async def test_every_supabase_mirror_migration_applies_in_filename_order() -> None:
    assert SUPABASE_MIGRATIONS.is_dir(), f"missing {SUPABASE_MIGRATIONS}"
    migrations = sorted(SUPABASE_MIGRATIONS.glob("*.sql"))
    assert migrations, "expected at least one Supabase migration file"

    await _recreate_scratch_database()
    conn = await asyncpg.connect(SCRATCH_DSN)
    try:
        await conn.execute(_PLATFORM_STUB)
        applied: list[str] = []
        for migration in migrations:
            try:
                await conn.execute(migration.read_text(encoding="utf-8"))
            except Exception as error:  # noqa: BLE001 -- surface the real DB error with provenance
                pytest.fail(
                    f"{migration.name} failed to apply after {len(applied)} prior migration(s) "
                    f"({applied[-1] if applied else 'none'} applied last): {error}",
                    pytrace=False,
                )
            applied.append(migration.name)
    finally:
        await conn.close()
