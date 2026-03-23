"""
Real RLS enforcement tests.
TS-E2E-SEC-TNT-001
"""

from __future__ import annotations

import os
from uuid import UUID

import asyncpg
import pytest
import pytest_asyncio


ADMIN_URL = os.getenv(
    "C2PRO_RLS_ADMIN_URL",
    "postgresql://supabase_admin:postgres@localhost:54322/c2pro_migration_check",
)
USER_URL = os.getenv(
    "C2PRO_RLS_USER_URL",
    "postgresql://nonsuperuser:test@localhost:54322/c2pro_migration_check",
)
ROLE_NAME = os.getenv("C2PRO_RLS_ROLE_NAME", "nonsuperuser")
ROLE_PASSWORD = os.getenv("C2PRO_RLS_ROLE_PASSWORD", "test")

TENANT_A_ID = UUID("11111111-1111-1111-1111-111111111111")
TENANT_B_ID = UUID("22222222-2222-2222-2222-222222222222")
PROJECT_A_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
PROJECT_B_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@pytest_asyncio.fixture
async def admin_conn():
    try:
        conn = await asyncpg.connect(ADMIN_URL, statement_cache_size=0)
    except Exception as exc:
        pytest.skip(f"Admin RLS database unavailable: {exc}")
    try:
        yield conn
    finally:
        await conn.close()


@pytest_asyncio.fixture
async def seeded_rls_db(admin_conn: asyncpg.Connection):
    db_name = ADMIN_URL.rsplit("/", 1)[-1]

    await admin_conn.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE_NAME}') THEN
                CREATE USER {ROLE_NAME} WITH PASSWORD '{ROLE_PASSWORD}';
            END IF;
        END $$;
        """
    )
    await admin_conn.execute(f"GRANT CONNECT ON DATABASE {db_name} TO {ROLE_NAME}")
    await admin_conn.execute(f"GRANT USAGE ON SCHEMA public TO {ROLE_NAME}")
    await admin_conn.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {ROLE_NAME}")
    await admin_conn.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {ROLE_NAME}")

    await admin_conn.execute(
        """
        INSERT INTO tenants (
            id, name, slug, subscription_plan, subscription_status,
            ai_budget_monthly, ai_spend_current, max_projects, max_users, max_storage_gb,
            settings, is_active
        )
        VALUES
            ($1, 'Tenant A', 'tenant-a', 'free', 'active', 50, 0, 5, 3, 10, '{}'::jsonb, true),
            ($2, 'Tenant B', 'tenant-b', 'free', 'active', 50, 0, 5, 3, 10, '{}'::jsonb, true)
        ON CONFLICT (id) DO UPDATE
        SET name = EXCLUDED.name,
            slug = EXCLUDED.slug,
            is_active = EXCLUDED.is_active
        """,
        TENANT_A_ID,
        TENANT_B_ID,
    )

    await admin_conn.execute(
        """
        INSERT INTO projects (
            id, tenant_id, name, project_type, status, currency, metadata
        )
        VALUES
            ($1, $2, 'Project A', 'construction', 'active', 'EUR', '{}'::jsonb),
            ($3, $4, 'Project B', 'construction', 'active', 'EUR', '{}'::jsonb)
        ON CONFLICT (id) DO UPDATE
        SET tenant_id = EXCLUDED.tenant_id,
            name = EXCLUDED.name,
            status = EXCLUDED.status
        """,
        PROJECT_A_ID,
        TENANT_A_ID,
        PROJECT_B_ID,
        TENANT_B_ID,
    )

    return {"tenant_a": TENANT_A_ID, "tenant_b": TENANT_B_ID}


@pytest_asyncio.fixture
async def rls_user_conn(seeded_rls_db):
    try:
        conn = await asyncpg.connect(USER_URL, statement_cache_size=0)
    except Exception as exc:
        pytest.skip(f"RLS user connection unavailable: {exc}")
    try:
        yield conn
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_real_rls_blocks_rows_without_tenant_context(rls_user_conn: asyncpg.Connection):
    """Non-superuser should see zero project rows when tenant context is missing."""
    await rls_user_conn.execute("SET SESSION app.current_tenant = ''")

    count = await rls_user_conn.fetchval("SELECT COUNT(*) FROM projects")

    assert count == 0


@pytest.mark.asyncio
async def test_real_rls_allows_only_current_tenant_rows(
    rls_user_conn: asyncpg.Connection, seeded_rls_db
):
    """Non-superuser should only see rows for the tenant present in the GUC."""
    await rls_user_conn.execute(f"SET SESSION app.current_tenant = '{seeded_rls_db['tenant_a']}'")

    visible_rows = await rls_user_conn.fetch(
        "SELECT id, tenant_id FROM projects ORDER BY id"
    )

    assert len(visible_rows) == 1
    assert visible_rows[0]["tenant_id"] == seeded_rls_db["tenant_a"]
    assert visible_rows[0]["id"] == PROJECT_A_ID


@pytest.mark.asyncio
async def test_real_rls_blocks_rows_with_unknown_tenant_context(rls_user_conn: asyncpg.Connection):
    """Non-superuser should see zero rows when tenant GUC is set to an unknown tenant."""
    unknown_tenant = UUID("33333333-3333-3333-3333-333333333333")
    await rls_user_conn.execute(f"SET SESSION app.current_tenant = '{unknown_tenant}'")

    count = await rls_user_conn.fetchval("SELECT COUNT(*) FROM projects")

    assert count == 0
