"""
TS-SEC-PS-RLS-001  –  project_state RLS enforcement under non-superuser role.

TASK-V3-014-08

Existing ``test_project_state_rls.py`` marks cross-tenant isolation as *xfail*
because the ``db`` fixture connects as the *postgres* superuser, which always
bypasses RLS.  This module connects as the ``nonsuperuser`` role created by
``infrastructure/database/test-init/01-setup.sql`` via raw **asyncpg**, seeds
two tenants' rows through a superuser admin connection, and asserts that the
non-superuser role **cannot** SELECT / UPDATE / DELETE the other tenant's
``project_states`` or ``project_state_entities`` rows.

If isolation does **not** hold, the test fails loudly — this would be a real
multi-tenant data-exposure vulnerability.

Bootstrap: ``scripts/bootstrap_test_infra.py`` (full Alembic pipeline)
"""

from __future__ import annotations

import os
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio

# ── Connection strings ─────────────────────────────────────────
ADMIN_URL = os.getenv(
    "C2PRO_RLS_ADMIN_URL",
    "postgresql://postgres:postgres@localhost:5433/c2pro_test",
)
USER_URL = os.getenv(
    "C2PRO_RLS_USER_URL",
    "postgresql://nonsuperuser:test@localhost:5433/c2pro_test",
)

# ── Stable UUIDs for seeded data ───────────────────────────────
TENANT_A = uuid4()
TENANT_B = uuid4()
PROJECT_A = uuid4()
PROJECT_B = uuid4()
ENTITY_A = uuid4()
ENTITY_B = uuid4()

# ── COALESCE pattern used by migration 20260613_0002 ───────────
_COALESCE = (
    "tenant_id = COALESCE("
    "NULLIF(current_setting('app.current_tenant', true), '')::uuid, "
    "tenant_id)"
)

# ── Policies to create / drop ──────────────────────────────────
_PS_POLICIES = [
    ("project_states_select", "SELECT", _COALESCE),
    ("project_states_insert", "INSERT", _COALESCE),
    ("project_states_update", "UPDATE", _COALESCE),
    ("project_states_delete", "DELETE", _COALESCE),
]
_PSE_POLICIES = [
    ("pse_select", "SELECT", _COALESCE),
    ("pse_insert", "INSERT", _COALESCE),
    ("pse_update", "UPDATE", _COALESCE),
    ("pse_delete", "DELETE", _COALESCE),
]


# ── Fixtures ───────────────────────────────────────────────────

@pytest_asyncio.fixture
async def admin_conn():
    """Superuser connection for seeding / cleanup."""
    try:
        conn = await asyncpg.connect(ADMIN_URL, statement_cache_size=0)
    except Exception as exc:
        pytest.skip(f"Test database unavailable: {exc}")
    try:
        yield conn
    finally:
        await conn.close()


@pytest_asyncio.fixture
async def seeded_db(test_engine, admin_conn: asyncpg.Connection):
    """Seed two tenants with project_state rows, return their IDs.

    Creates COALESCE RLS policies on project_states / project_state_entities,
    seeds data as superuser (bypasses RLS), then cleans up everything.

    Cleanup deletes seeded rows *and* the created policies so the test is
    repeatable.
    """
    slug_a = f"rls-a-{TENANT_A.hex[:8]}"
    slug_b = f"rls-b-{TENANT_B.hex[:8]}"

    # ── Pre-cleanup (idempotent on re-runs) ───────────────────
    await admin_conn.execute(
        "DELETE FROM project_state_entities WHERE tenant_id IN ($1, $2)",
        TENANT_A, TENANT_B,
    )
    await admin_conn.execute(
        "DELETE FROM project_states WHERE tenant_id IN ($1, $2)",
        TENANT_A, TENANT_B,
    )
    await admin_conn.execute(
        "DELETE FROM projects WHERE id IN ($1, $2)",
        PROJECT_A, PROJECT_B,
    )
    await admin_conn.execute(
        "DELETE FROM tenants WHERE id IN ($1, $2) OR slug IN ($3, $4)",
        TENANT_A, TENANT_B, slug_a, slug_b,
    )

    # ── Drop stale policies if any ────────────────────────────
    for name, _, _ in _PS_POLICIES + _PSE_POLICIES:
        for tbl in ("project_states", "project_state_entities"):
            await admin_conn.execute(
                f"DROP POLICY IF EXISTS {name} ON {tbl}"
            )

    # ── Re-grant schema access (bootstrap drops/recreates public) ─
    #    reset_public_schema() drops `public` CASCADE, destroying 01-setup.sql grants.
    await admin_conn.execute(
        "GRANT ALL ON SCHEMA public TO nonsuperuser"
    )
    await admin_conn.execute(
        "GRANT ALL ON ALL TABLES IN SCHEMA public TO nonsuperuser"
    )
    await admin_conn.execute(
        "GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO nonsuperuser"
    )
    await admin_conn.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO nonsuperuser"
    )
    await admin_conn.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO nonsuperuser"
    )

    # ── Enable RLS ────────────────────────────────────────────
    await admin_conn.execute(
        "ALTER TABLE project_states ENABLE ROW LEVEL SECURITY"
    )
    await admin_conn.execute(
        "ALTER TABLE project_state_entities ENABLE ROW LEVEL SECURITY"
    )

    # ── Create COALESCE policies ──────────────────────────────
    for name, cmd, using in _PS_POLICIES:
        await admin_conn.execute(
            f"CREATE POLICY {name} ON project_states "
            f"FOR {cmd} {'USING' if cmd != 'INSERT' else 'WITH CHECK'} ({using})"
        )
    for name, cmd, using in _PSE_POLICIES:
        await admin_conn.execute(
            f"CREATE POLICY {name} ON project_state_entities "
            f"FOR {cmd} {'USING' if cmd != 'INSERT' else 'WITH CHECK'} ({using})"
        )

    # ── Seed tenants ──────────────────────────────────────────
    await admin_conn.execute(
        """
        INSERT INTO tenants (
            id, name, slug, subscription_plan, subscription_status,
            ai_budget_monthly, ai_spend_current, max_projects, max_users,
            max_storage_gb, settings, is_active, created_at, updated_at
        ) VALUES
            ($1, $3, $5, 'free', 'active',
             50, 0, 5, 3, 10, '{}'::jsonb, true, now(), now()),
            ($2, $4, $6, 'free', 'active',
             50, 0, 5, 3, 10, '{}'::jsonb, true, now(), now())
        """,
        TENANT_A, TENANT_B,
        f"Tenant A ({slug_a})", f"Tenant B ({slug_b})",
        slug_a, slug_b,
    )

    # ── Seed projects ─────────────────────────────────────────
    await admin_conn.execute(
        """
        INSERT INTO projects (
            id, tenant_id, name, project_type, status, currency,
            metadata, created_at, updated_at
        ) VALUES
            ($1, $2, 'Proj A', 'construction', 'active', 'EUR',
             '{}'::jsonb, now(), now()),
            ($3, $4, 'Proj B', 'construction', 'active', 'EUR',
             '{}'::jsonb, now(), now())
        """,
        PROJECT_A, TENANT_A, PROJECT_B, TENANT_B,
    )

    # ── Seed project_states ───────────────────────────────────
    await admin_conn.execute(
        """
        INSERT INTO project_states (
            project_id, tenant_id, lifecycle_status,
            document_revision_ids, procurement_refs,
            created_at, updated_at
        ) VALUES
            ($1, $2, 'active', '[]'::jsonb, '[]'::jsonb, now(), now()),
            ($3, $4, 'active', '[]'::jsonb, '[]'::jsonb, now(), now())
        ON CONFLICT (project_id) DO UPDATE SET lifecycle_status = EXCLUDED.lifecycle_status
        """,
        PROJECT_A, TENANT_A, PROJECT_B, TENANT_B,
    )

    # ── Seed project_state_entities ───────────────────────────
    await admin_conn.execute(
        """
        INSERT INTO project_state_entities (
            entity_id, project_id, tenant_id, entity_type,
            lifecycle_status, payload, created_at, updated_at
        ) VALUES
            ($1, $2, $3, 'risk', 'active', '{"title":"A"}'::jsonb, now(), now()),
            ($4, $5, $6, 'risk', 'active', '{"title":"B"}'::jsonb, now(), now())
        ON CONFLICT (entity_id) DO UPDATE SET payload = EXCLUDED.payload
        """,
        ENTITY_A, PROJECT_A, TENANT_A, ENTITY_B, PROJECT_B, TENANT_B,
    )

    yield {"tenant_a": TENANT_A, "tenant_b": TENANT_B}

    # ── Cleanup (superuser bypasses RLS) ──────────────────────
    await admin_conn.execute(
        "DELETE FROM project_state_entities WHERE entity_id IN ($1, $2)",
        ENTITY_A, ENTITY_B,
    )
    await admin_conn.execute(
        "DELETE FROM project_states WHERE project_id IN ($1, $2)",
        PROJECT_A, PROJECT_B,
    )
    await admin_conn.execute(
        "DELETE FROM projects WHERE id IN ($1, $2)",
        PROJECT_A, PROJECT_B,
    )
    await admin_conn.execute(
        "DELETE FROM tenants WHERE id IN ($1, $2)",
        TENANT_A, TENANT_B,
    )
    for name, _, _ in _PS_POLICIES + _PSE_POLICIES:
        for tbl in ("project_states", "project_state_entities"):
            await admin_conn.execute(
                f"DROP POLICY IF EXISTS {name} ON {tbl}"
            )


@pytest_asyncio.fixture
async def user_conn(seeded_db):
    """Non-superuser connection — RLS enforced."""
    try:
        conn = await asyncpg.connect(USER_URL, statement_cache_size=0)
    except Exception as exc:
        pytest.skip(f"Non-superuser role unavailable: {exc}")
    try:
        yield conn
    finally:
        await conn.close()


# ── Tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.security
async def test_project_states_select_isolation(
    user_conn: asyncpg.Connection, seeded_db
):
    """Non-superuser scoped to tenant A must NOT see tenant B's project_states rows."""
    await user_conn.execute(
        f"SET SESSION app.current_tenant = '{seeded_db['tenant_a']}'"
    )

    rows = await user_conn.fetch(
        "SELECT project_id, tenant_id FROM project_states ORDER BY project_id"
    )

    assert len(rows) == 1, f"Expected 1 row for tenant A, got {len(rows)}"
    assert rows[0]["tenant_id"] == seeded_db["tenant_a"]
    assert rows[0]["project_id"] == PROJECT_A


@pytest.mark.asyncio
@pytest.mark.security
async def test_project_state_entities_select_isolation(
    user_conn: asyncpg.Connection, seeded_db
):
    """Non-superuser scoped to tenant A must NOT see tenant B's project_state_entities rows."""
    await user_conn.execute(
        f"SET SESSION app.current_tenant = '{seeded_db['tenant_a']}'"
    )

    rows = await user_conn.fetch(
        "SELECT entity_id, tenant_id FROM project_state_entities ORDER BY entity_id"
    )

    assert len(rows) == 1, f"Expected 1 entity for tenant A, got {len(rows)}"
    assert rows[0]["tenant_id"] == seeded_db["tenant_a"]
    assert rows[0]["entity_id"] == ENTITY_A


@pytest.mark.asyncio
@pytest.mark.security
async def test_project_states_admin_mode_when_no_tenant_context(
    user_conn: asyncpg.Connection, seeded_db
):
    """COALESCE pattern: empty app.current_tenant means admin mode — all rows visible.

    The COALESCE RLS policy: tenant_id = COALESCE(NULLIF(current_setting(...), '')::uuid, tenant_id)
    When the GUC is empty, NULLIF returns NULL, COALESCE falls back to tenant_id,
    so tenant_id = tenant_id is always TRUE → admin/superuser access.
    """
    await user_conn.execute("SET SESSION app.current_tenant = ''")

    count_ps = await user_conn.fetchval("SELECT COUNT(*) FROM project_states")
    count_pse = await user_conn.fetchval(
        "SELECT COUNT(*) FROM project_state_entities"
    )

    assert count_ps == 2, (
        f"COALESCE admin mode: expected 2 rows (all tenants), got {count_ps}"
    )
    assert count_pse == 2, (
        f"COALESCE admin mode: expected 2 rows (all tenants), got {count_pse}"
    )


@pytest.mark.asyncio
@pytest.mark.security
async def test_project_states_update_blocked_cross_tenant(
    user_conn: asyncpg.Connection, seeded_db
):
    """Non-superuser scoped to tenant A must NOT update tenant B's project_states."""
    await user_conn.execute(
        f"SET SESSION app.current_tenant = '{seeded_db['tenant_a']}'"
    )

    result = await user_conn.execute(
        "UPDATE project_states SET lifecycle_status = 'HACKED' "
        "WHERE project_id = $1",
        PROJECT_B,
    )

    assert result == "UPDATE 0", (
        f"Cross-tenant UPDATE succeeded — RLS not enforced! Got: {result}"
    )


@pytest.mark.asyncio
@pytest.mark.security
async def test_project_states_delete_blocked_cross_tenant(
    user_conn: asyncpg.Connection, seeded_db
):
    """Non-superuser scoped to tenant A must NOT delete tenant B's project_states."""
    await user_conn.execute(
        f"SET SESSION app.current_tenant = '{seeded_db['tenant_a']}'"
    )

    result = await user_conn.execute(
        "DELETE FROM project_states WHERE project_id = $1",
        PROJECT_B,
    )

    assert result == "DELETE 0", (
        f"Cross-tenant DELETE succeeded — RLS not enforced! Got: {result}"
    )


@pytest.mark.asyncio
@pytest.mark.security
async def test_project_state_entities_update_blocked_cross_tenant(
    user_conn: asyncpg.Connection, seeded_db
):
    """Non-superuser scoped to tenant A must NOT update tenant B's project_state_entities."""
    await user_conn.execute(
        f"SET SESSION app.current_tenant = '{seeded_db['tenant_a']}'"
    )

    result = await user_conn.execute(
        "UPDATE project_state_entities SET entity_type = 'HACKED' "
        "WHERE entity_id = $1",
        ENTITY_B,
    )

    assert result == "UPDATE 0", (
        f"Cross-tenant UPDATE on entities succeeded — RLS not enforced! Got: {result}"
    )


@pytest.mark.asyncio
@pytest.mark.security
async def test_project_state_entities_delete_blocked_cross_tenant(
    user_conn: asyncpg.Connection, seeded_db
):
    """Non-superuser scoped to tenant A must NOT delete tenant B's project_state_entities."""
    await user_conn.execute(
        f"SET SESSION app.current_tenant = '{seeded_db['tenant_a']}'"
    )

    result = await user_conn.execute(
        "DELETE FROM project_state_entities WHERE entity_id = $1",
        ENTITY_B,
    )

    assert result == "DELETE 0", (
        f"Cross-tenant DELETE on entities succeeded — RLS not enforced! Got: {result}"
    )


@pytest.mark.asyncio
@pytest.mark.security
async def test_project_states_insert_with_wrong_tenant_rejected(
    user_conn: asyncpg.Connection, seeded_db
):
    """Non-superuser scoped to tenant A must NOT insert a row with tenant B's ID."""
    await user_conn.execute(
        f"SET SESSION app.current_tenant = '{seeded_db['tenant_a']}'"
    )

    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await user_conn.execute(
            "INSERT INTO project_states "
            "(project_id, tenant_id, lifecycle_status, document_revision_ids, "
            " procurement_refs, created_at, updated_at) "
            "VALUES ($1, $2, 'active', '[]'::jsonb, '[]'::jsonb, now(), now())",
            uuid4(), seeded_db["tenant_b"],
        )


@pytest.mark.asyncio
@pytest.mark.security
async def test_project_state_entities_insert_with_wrong_tenant_rejected(
    user_conn: asyncpg.Connection, seeded_db
):
    """Non-superuser scoped to tenant A must NOT insert a project_state_entity with tenant B's ID."""
    await user_conn.execute(
        f"SET SESSION app.current_tenant = '{seeded_db['tenant_a']}'"
    )

    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await user_conn.execute(
            "INSERT INTO project_state_entities "
            "(entity_id, project_id, tenant_id, entity_type, lifecycle_status, "
            " payload, created_at, updated_at) "
            "VALUES ($1, $2, $3, 'risk', 'active', '{}'::jsonb, now(), now())",
            uuid4(), PROJECT_A, seeded_db["tenant_b"],
        )


@pytest.mark.asyncio
@pytest.mark.security
async def test_rls_policies_exist_on_project_state_tables(
    admin_conn: asyncpg.Connection, seeded_db
):
    """Verify that COALESCE RLS policies exist on both project_state tables."""
    policies = await admin_conn.fetch(
        """
        SELECT tablename, policyname, qual, with_check
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename IN ('project_states', 'project_state_entities')
        ORDER BY tablename, policyname
        """
    )

    policy_map: dict[str, dict[str, str]] = {}
    for row in policies:
        qual = row["qual"] or ""
        wchk = row["with_check"] or ""
        policy_map.setdefault(row["tablename"], {})[row["policyname"]] = qual + wchk

    for tbl, expected in [("project_states", _PS_POLICIES), ("project_state_entities", _PSE_POLICIES)]:
        for name, cmd, _ in expected:
            assert name in policy_map.get(tbl, {}), (
                f"Missing policy '{name}' on '{tbl}'"
            )
            body = policy_map[tbl][name]
            assert "COALESCE" in body, (
                f"Policy '{name}' on '{tbl}' does not use COALESCE pattern: {body}"
            )
            assert "app.current_tenant" in body, (
                f"Policy '{name}' on '{tbl}' does not reference app.current_tenant GUC"
            )


@pytest.mark.asyncio
@pytest.mark.security
async def test_rls_is_enabled_on_project_state_tables(
    admin_conn: asyncpg.Connection, seeded_db
):
    """Verify RLS is actually ENABLED (not just policies exist)."""
    result = await admin_conn.fetch(
        """
        SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relname IN ('project_states', 'project_state_entities')
        ORDER BY c.relname
        """
    )

    for row in result:
        assert row["relrowsecurity"], (
            f"RLS not enabled on '{row['relname']}' (relrowsecurity=false)"
        )
