#!/usr/bin/env python3
"""C2.5 — Cross-Tenant Admin / DLQ Boundary Gate (Disposable DB).

Self-verifying gate proving:
- c2pro_admin_ops capability role properties
- Admin login (MEMBER OF c2pro_admin_ops) cross-tenant DLQ access
- Admin login retry UPDATE allowed on exact columns
- Admin login tenant_id UPDATE denied
- Admin login INSERT/DELETE denied
- Admin login unrelated table access denied
- c2pro_app tenant isolation preserved
- c2pro_app cross-tenant denied

Analogous to C2 checkpoint gate and P0-SEC gates.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg
from psycopg_pool import AsyncConnectionPool

# Test constants
TENANT_A = "aaaaaaaa-aaaa-aaaa-aaaa-000000000001"
TENANT_B = "bbbbbbbb-bbbb-bbbb-bbbb-000000000002"
DLQ_A = "11111111-1111-1111-1111-111111111111"
DLQ_B = "22222222-2222-2222-2222-222222222222"


def _derive_dsn(admin_dsn: str, username: str, password: str | None = None) -> str:
    """Derive restricted DSN by replacing credentials in the admin superuser DSN."""
    clean_dsn = admin_dsn.replace("postgresql+asyncpg://", "postgresql://")
    if "://" in clean_dsn:
        parsed = urlparse(clean_dsn)
        netloc = parsed.netloc
        host_part = netloc.split("@")[-1] if "@" in netloc else netloc

        new_netloc = f"{username}:{password}@{host_part}" if password else f"{username}@{host_part}"

        parsed = parsed._replace(netloc=new_netloc)
        return urlunparse(parsed)
    else:
        # Key-value DSN format
        import re
        clean = re.sub(r"\buser=\S+", "", clean_dsn)
        clean = re.sub(r"\bpassword=\S+", "", clean)
        new_dsn = f"{clean.strip()} user={username}"
        if password:
            new_dsn += f" password={password}"
        return new_dsn


async def _connect(dsn: str) -> AsyncConnectionPool:
    conn_string = dsn.replace("postgresql+asyncpg://", "postgresql://")
    pool = AsyncConnectionPool(
        conninfo=conn_string,
        min_size=0,
        max_size=2,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": None},
    )
    await pool.open(wait=True, timeout=30)
    return pool


async def _provision_roles(pool: AsyncConnectionPool) -> None:
    """Dynamically provision restricted roles in the disposable test database."""
    print("Provisioning restricted roles in the disposable database...")
    async with pool.connection() as conn:
        # Provision c2pro_app (NOSUPERUSER, LOGIN, non-owner)
        await conn.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'c2pro_app') THEN
                    CREATE ROLE c2pro_app WITH LOGIN PASSWORD 'app_pass_gate'
                    NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
                ELSE
                    ALTER ROLE c2pro_app WITH LOGIN PASSWORD 'app_pass_gate'
                    NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
                END IF;
            END $$;
            """
        )

        # Provision c2pro_admin_ops (NOLOGIN, NOSUPERUSER, non-owner)
        await conn.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'c2pro_admin_ops') THEN
                    CREATE ROLE c2pro_admin_ops NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
                ELSE
                    ALTER ROLE c2pro_admin_ops NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
                END IF;
            END $$;
            """
        )

        # Provision c2pro_admin_login (LOGIN, NOSUPERUSER, member of c2pro_admin_ops)
        await conn.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'c2pro_admin_login') THEN
                    CREATE ROLE c2pro_admin_login WITH LOGIN PASSWORD 'admin_pass_gate'
                    NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
                ELSE
                    ALTER ROLE c2pro_admin_login WITH LOGIN PASSWORD 'admin_pass_gate'
                    NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
                END IF;
                GRANT c2pro_admin_ops TO c2pro_admin_login;
            END $$;
            """
        )

        # Grant CONNECT and basic public usage to allow roles to log in
        res = await conn.execute("SELECT current_database()")
        db_name = (await res.fetchone())[0]
        await conn.execute(f"GRANT CONNECT ON DATABASE {db_name} TO c2pro_app")
        await conn.execute(f"GRANT CONNECT ON DATABASE {db_name} TO c2pro_admin_login")
        await conn.execute("GRANT USAGE ON SCHEMA public TO c2pro_app")
        await conn.execute("GRANT USAGE ON SCHEMA public TO c2pro_admin_login")

        # Grant DML permissions on dlq_failed_tasks so RLS can be evaluated
        await conn.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON dlq_failed_tasks TO c2pro_app")


async def _check_role_properties(pool: AsyncConnectionPool, role: str, **expected) -> bool:
    """Verify role catalog properties."""
    async with pool.connection() as conn:
        result = await conn.execute(
            """
            SELECT rolsuper, rolbypassrls, rolcreaterole, rolcanlogin
            FROM pg_roles WHERE rolname = %s
            """,
            (role,),
        )
        row = await result.fetchone()
        if not row:
            print(f"FAIL: role {role} does not exist")
            return False
        actual = dict(zip(["rolsuper", "rolbypassrls", "rolcreaterole", "rolcanlogin"], row, strict=False))
        for k, v in expected.items():
            if actual[k] != v:
                print(f"FAIL: {role}.{k} = {actual[k]}, expected {v}")
                return False
        print(f"OK: {role} catalog properties match expected")
        return True


async def _check_table_owner(pool: AsyncConnectionPool, table: str, expected_owner: str) -> bool:
    """Verify table is not owned by the restricted role."""
    async with pool.connection() as conn:
        result = await conn.execute(
            """
            SELECT relowner::regrole FROM pg_class WHERE relname = %s
            """,
            (table,),
        )
        row = await result.fetchone()
        if not row:
            print(f"FAIL: table {table} does not exist")
            return False
        owner = row[0]
        if owner == expected_owner:
            print(f"FAIL: table {table} is owned by {expected_owner} (should not be)")
            return False
        print(f"OK: table {table} not owned by {expected_owner} (owner: {owner})")
        return True


async def _seed_dlq_rows(pool: AsyncConnectionPool) -> None:
    """Seed DLQ rows for Tenant A and Tenant B as superuser."""
    async with pool.connection() as conn:
        # Clear existing rows to make it completely idempotent
        await conn.execute("DELETE FROM dlq_failed_tasks")
        await conn.execute(
            f"""
            INSERT INTO dlq_failed_tasks (id, tenant_id, task_type, payload_json, error_message, retry_count, max_retries, status, created_at, updated_at)
            VALUES
                ('{DLQ_A}'::uuid, '{TENANT_A}'::uuid, 'document_analysis', '{{"doc": "a"}}', 'error a', 0, 3, 'pending', NOW(), NOW()),
                ('{DLQ_B}'::uuid, '{TENANT_B}'::uuid, 'document_analysis', '{{"doc": "b"}}', 'error b', 0, 3, 'pending', NOW(), NOW())
            """
        )


async def _test_c2pro_app_tenant_isolation(app_pool: AsyncConnectionPool) -> bool:
    """Test c2pro_app sees own tenant only, cross-tenant denied."""
    print("\n=== Testing c2pro_app tenant isolation ===")

    # Test Tenant A sees own row (uses single explicit transaction block)
    async with app_pool.connection() as conn, conn.transaction():
        await conn.execute(f"SET LOCAL app.current_tenant = '{TENANT_A}'")
        result = await conn.execute(
            "SELECT tenant_id FROM dlq_failed_tasks WHERE id = %s",
            (DLQ_A,),
        )
        row = await result.fetchone()
        if not row or str(row[0]) != TENANT_A:
            print("FAIL: c2pro_app Tenant A cannot see own DLQ row")
            return False
        print("OK: c2pro_app Tenant A sees own DLQ row")

    # Test Tenant A cannot see Tenant B row (uses single explicit transaction block)
    async with app_pool.connection() as conn, conn.transaction():
        await conn.execute(f"SET LOCAL app.current_tenant = '{TENANT_A}'")
        result = await conn.execute(
            "SELECT tenant_id FROM dlq_failed_tasks WHERE id = %s",
            (DLQ_B,),
        )
        row = await result.fetchone()
        if row:
            print("FAIL: c2pro_app Tenant A can see Tenant B row")
            return False
        print("OK: c2pro_app Tenant A cannot see Tenant B row")

    # Test Tenant A cannot retry Tenant B row (uses single explicit transaction block)
    async with app_pool.connection() as conn, conn.transaction():
        await conn.execute(f"SET LOCAL app.current_tenant = '{TENANT_A}'")
        cur = await conn.execute(
            """
            UPDATE dlq_failed_tasks
            SET retry_count = retry_count + 1,
                status = 'retrying',
                updated_at = NOW()
            WHERE id = %s
            """,
            (DLQ_B,),
        )
        if cur.rowcount != 0:
            print(f"FAIL: c2pro_app Tenant A cross-tenant retry updated {cur.rowcount} rows (should be 0)")
            return False
        print("OK: c2pro_app Tenant A cross-tenant retry updated 0 rows (denied by RLS)")

    return True


async def _test_c2pro_app_cross_tenant_denied(app_pool: AsyncConnectionPool) -> bool:
    """Test c2pro_app cannot perform cross-tenant operations without GUC."""
    print("\n=== Testing c2pro_app cross-tenant denied ===")

    async with app_pool.connection() as conn, conn.transaction():
        # No GUC set - should see nothing (fail-closed)
        result = await conn.execute(
            "SELECT COUNT(*) FROM dlq_failed_tasks"
        )
        count = (await result.fetchone())[0]
        if count != 0:
            print(f"FAIL: c2pro_app without GUC sees {count} rows (should be 0)")
            return False
        print("OK: c2pro_app without GUC sees 0 rows (fail-closed)")

    return True


async def _test_admin_login_select_cross_tenant(admin_pool: AsyncConnectionPool) -> bool:
    """Test admin login can SELECT cross-tenant."""
    print("\n=== Testing admin login SELECT cross-tenant ===")

    async with admin_pool.connection() as conn:
        result = await conn.execute(
            "SELECT tenant_id FROM dlq_failed_tasks ORDER BY tenant_id"
        )
        rows = await result.fetchall()
        tenant_ids = {str(row[0]) for row in rows}
        if tenant_ids != {TENANT_A, TENANT_B}:
            print(f"FAIL: admin sees {tenant_ids}, expected {{TENANT_A, TENANT_B}}")
            return False
        print("OK: admin login sees both Tenant A and Tenant B DLQ rows")
    return True


async def _test_admin_login_count_cross_tenant(admin_pool: AsyncConnectionPool) -> bool:
    """Test admin login can COUNT across tenants."""
    print("\n=== Testing admin login COUNT cross-tenant ===")

    async with admin_pool.connection() as conn:
        result = await conn.execute(
            "SELECT COUNT(*) FROM dlq_failed_tasks"
        )
        count = (await result.fetchone())[0]
        if count != 2:
            print(f"FAIL: admin count = {count}, expected 2")
            return False
        print("OK: admin login COUNT = 2 across tenants")
    return True


async def _test_admin_login_retry_update(admin_pool: AsyncConnectionPool) -> bool:
    """Test admin login can UPDATE retry columns."""
    print("\n=== Testing admin login retry UPDATE ===")

    async with admin_pool.connection() as conn:
        # Retry DLQ_A (should update retry_count, status, updated_at, next_retry_at)
        await conn.execute(
            """
            UPDATE dlq_failed_tasks
            SET retry_count = retry_count + 1,
                status = 'retrying',
                updated_at = NOW(),
                next_retry_at = NOW() + INTERVAL '2 minutes'
            WHERE id = %s
            """,
            (DLQ_A,),
        )
        result = await conn.execute(
            "SELECT retry_count, status FROM dlq_failed_tasks WHERE id = %s",
            (DLQ_A,),
        )
        row = await result.fetchone()
        if row[0] != 1 or row[1] != 'retrying':
            print(f"FAIL: retry update failed, got retry_count={row[0]}, status={row[1]}")
            return False
        print("OK: admin login retry UPDATE succeeded on allowed columns")
    return True


async def _test_admin_tenant_id_update_denied(admin_pool: AsyncConnectionPool) -> bool:
    """Test admin login UPDATE tenant_id is denied."""
    print("\n=== Testing admin login UPDATE tenant_id DENIED ===")

    async with admin_pool.connection() as conn:
        try:
            await conn.execute(
                "UPDATE dlq_failed_tasks SET tenant_id = %s WHERE id = %s",
                (TENANT_B, DLQ_A),
            )
            print("FAIL: UPDATE tenant_id succeeded (should be denied by column grant)")
            return False
        except psycopg.errors.InsufficientPrivilege:
            print("OK: UPDATE tenant_id denied by column-level grant")
            return True
        except Exception as e:
            print(f"FAIL: unexpected error: {e}")
            return False


async def _test_admin_insert_denied(admin_pool: AsyncConnectionPool) -> bool:
    """Test admin login INSERT is denied."""
    print("\n=== Testing admin login INSERT DENIED ===")

    async with admin_pool.connection() as conn:
        try:
            await conn.execute(
                """
                INSERT INTO dlq_failed_tasks (id, tenant_id, task_type, payload_json, error_message, retry_count, max_retries, status, created_at, updated_at)
                VALUES (gen_random_uuid(), %s, 'test', '{}', 'test', 0, 3, 'pending', NOW(), NOW())
                """,
                (TENANT_A,),
            )
            print("FAIL: INSERT succeeded (should be denied)")
            return False
        except psycopg.errors.InsufficientPrivilege:
            print("OK: INSERT denied by missing grant")
            return True
        except Exception as e:
            print(f"FAIL: unexpected error: {e}")
            return False


async def _test_admin_delete_denied(admin_pool: AsyncConnectionPool) -> bool:
    """Test admin login DELETE is denied."""
    print("\n=== Testing admin login DELETE DENIED ===")

    async with admin_pool.connection() as conn:
        try:
            await conn.execute(
                "DELETE FROM dlq_failed_tasks WHERE id = %s",
                (DLQ_A,),
            )
            print("FAIL: DELETE succeeded (should be denied)")
            return False
        except psycopg.errors.InsufficientPrivilege:
            print("OK: DELETE denied by missing grant")
            return True
        except Exception as e:
            print(f"FAIL: unexpected error: {e}")
            return False


async def _test_admin_unrelated_table_denied(admin_pool: AsyncConnectionPool) -> bool:
    """Test admin login cannot access unrelated business tables."""
    print("\n=== Testing admin login unrelated table access DENIED ===")

    tables = ["projects", "documents"]
    for table in tables:
        async with admin_pool.connection() as conn:
            try:
                await conn.execute(f"SELECT 1 FROM {table} LIMIT 1")
                print(f"FAIL: admin can SELECT from {table} (should be denied)")
                return False
            except psycopg.errors.InsufficientPrivilege:
                print(f"OK: admin cannot SELECT from {table} (denied)")
            except psycopg.errors.UndefinedTable:
                print(f"SKIP: table {table} does not exist")
            except Exception as e:
                print(f"FAIL: unexpected error on {table}: {e}")
                return False
    return True


async def _test_admin_policy_catalog(admin_pool: AsyncConnectionPool) -> bool:
    """Verify effective catalog has correct admin policies."""
    print("\n=== Verifying admin policy catalog ===")

    async with admin_pool.connection() as conn:
        result = await conn.execute(
            """
            SELECT polname, polcmd, polroles::regrole[]
            FROM pg_policy
            WHERE polrelid = 'dlq_failed_tasks'::regclass
            AND polname IN ('dlq_admin_select', 'dlq_admin_retry')
            ORDER BY polname
            """
        )
        policies = {row[0]: (row[1], row[2]) for row in await result.fetchall()}

        # Check SELECT policy
        if 'dlq_admin_select' not in policies:
            print("FAIL: dlq_admin_select policy missing")
            return False
        cmd, roles = policies['dlq_admin_select']
        if cmd != 'r':  # 'r' = SELECT
            print(f"FAIL: dlq_admin_select cmd = {cmd}, expected 'r'")
            return False
        if 'c2pro_admin_ops' not in roles:
            print(f"FAIL: dlq_admin_select roles = {roles}, expected c2pro_admin_ops")
            return False
        print("OK: dlq_admin_select policy TO c2pro_admin_ops FOR SELECT")

        # Check UPDATE policy
        if 'dlq_admin_retry' not in policies:
            print("FAIL: dlq_admin_retry policy missing")
            return False
        cmd, roles = policies['dlq_admin_retry']
        if cmd != 'w':  # 'w' = UPDATE (write in PG catalog)
            print(f"FAIL: dlq_admin_retry cmd = {cmd}, expected 'w'")
            return False
        if 'c2pro_admin_ops' not in roles:
            print(f"FAIL: dlq_admin_retry roles = {roles}, expected c2pro_admin_ops")
            return False
        print("OK: dlq_admin_retry policy TO c2pro_admin_ops FOR UPDATE")

    # Check no INSERT/DELETE policies
    async with admin_pool.connection() as conn:
        result = await conn.execute(
            """
            SELECT polname, polcmd
            FROM pg_policy
            WHERE polrelid = 'dlq_failed_tasks'::regclass
            AND polname LIKE 'dlq_admin_%'
            """
        )
        all_policies = {row[0]: row[1] for row in await result.fetchall()}
        if 'dlq_admin_insert' in all_policies:
            print("FAIL: dlq_admin_insert policy exists (should not)")
            return False
        if 'dlq_admin_delete' in all_policies:
            print("FAIL: dlq_admin_delete policy exists (should not)")
            return False
        print("OK: no admin INSERT/DELETE policies")

    return True


async def _test_grant_catalog(admin_pool: AsyncConnectionPool) -> bool:
    """Verify column-level UPDATE grant excludes tenant_id."""
    print("\n=== Verifying column-level UPDATE grant ===")

    async with admin_pool.connection() as conn:
        result = await conn.execute(
            """
            SELECT attname
            FROM pg_attribute
            WHERE attrelid = 'dlq_failed_tasks'::regclass
            AND attnum > 0
            AND NOT attisdropped
            ORDER BY attnum
            """
        )
        columns = [row[0] for row in await result.fetchall()]

        # Check column privileges
        for col in columns:
            result = await conn.execute(
                """
                SELECT privilege_type
                FROM information_schema.column_privileges
                WHERE table_name = 'dlq_failed_tasks'
                AND column_name = %s
                AND grantee = 'c2pro_admin_ops'
                """,
                (col,),
            )
            privs = {row[0] for row in await result.fetchall()}

            if col in ["retry_count", "status", "updated_at", "next_retry_at"]:
                if 'UPDATE' not in privs:
                    print(f"FAIL: column {col} missing UPDATE grant")
                    return False
                print(f"OK: column {col} has UPDATE grant")
            elif col == "tenant_id":
                if 'UPDATE' in privs:
                    print("FAIL: column tenant_id has UPDATE grant (should be excluded)")
                    return False
                print("OK: column tenant_id excluded from UPDATE grant")
            else:
                if 'UPDATE' in privs:
                    print(f"FAIL: column {col} has unexpected UPDATE grant")
                    return False

    return True


async def main() -> int:
    """Run the C2.5 disposable DB gate."""
    import sys
    if sys.platform == "win32":
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Read the disposable trusted admin superuser DSN from the environment
    admin_dsn = (
        os.environ.get("P0_SEC_ADMIN_DSN")
        or os.environ.get("ADMIN_OPS_ADMIN_DSN")
        or os.environ.get("DATABASE_URL")
    )
    if not admin_dsn:
        print("ERROR: Set P0_SEC_ADMIN_DSN, ADMIN_OPS_ADMIN_DSN or DATABASE_URL to a superuser DSN")
        return 1

    # Connect to the superuser pool
    print("Connecting to the database as superuser/owner...")
    admin_pool = await _connect(admin_dsn)

    # 1. Dynamically provision the restricted roles and grant CONNECT/USAGE
    await _provision_roles(admin_pool)

    # 2. Derive connection DSNs for c2pro_app and c2pro_admin_login internally
    app_dsn = _derive_dsn(admin_dsn, "c2pro_app", "app_pass_gate")
    admin_login_dsn = _derive_dsn(admin_dsn, "c2pro_admin_login", "admin_pass_gate")

    # 3. Create restricted connection pools
    print("Connecting as c2pro_app and c2pro_admin_login...")
    app_pool = await _connect(app_dsn)
    admin_login_pool = await _connect(admin_login_dsn)

    all_passed = True

    try:
        # 1. Role catalog properties
        print("\n=== Role Catalog Verification ===")
        all_passed &= await _check_role_properties(
            admin_pool, "c2pro_admin_ops",
            rolsuper=False, rolbypassrls=False, rolcreaterole=False, rolcanlogin=False
        )

        # 2. Table ownership
        all_passed &= await _check_table_owner(admin_pool, "dlq_failed_tasks", "c2pro_admin_ops")

        # 3. Seed DLQ rows
        await _seed_dlq_rows(admin_pool)

        # 4. c2pro_app tenant isolation
        all_passed &= await _test_c2pro_app_tenant_isolation(app_pool)

        # 5. c2pro_app cross-tenant denied
        all_passed &= await _test_c2pro_app_cross_tenant_denied(app_pool)

        # 6. Admin login cross-tenant SELECT
        all_passed &= await _test_admin_login_select_cross_tenant(admin_login_pool)

        # 7. Admin login COUNT cross-tenant
        all_passed &= await _test_admin_login_count_cross_tenant(admin_login_pool)

        # 8. Admin login retry UPDATE
        all_passed &= await _test_admin_login_retry_update(admin_login_pool)

        # 9. Admin tenant_id UPDATE denied
        all_passed &= await _test_admin_tenant_id_update_denied(admin_login_pool)

        # 10. Admin INSERT denied
        all_passed &= await _test_admin_insert_denied(admin_login_pool)

        # 11. Admin DELETE denied
        all_passed &= await _test_admin_delete_denied(admin_login_pool)

        # 12. Unrelated table access denied
        all_passed &= await _test_admin_unrelated_table_denied(admin_login_pool)

        # 13. Admin policy catalog
        all_passed &= await _test_admin_policy_catalog(admin_login_pool)

        # 14. Column-level UPDATE grant
        all_passed &= await _test_grant_catalog(admin_login_pool)

    finally:
        await admin_pool.close()
        await app_pool.close()
        await admin_login_pool.close()

    if all_passed:
        print("\n✅ ALL C2.5 GATE CHECKS PASSED")
        return 0
    else:
        print("\n❌ SOME C2.5 GATE CHECKS FAILED")
        return 1


if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    raise SystemExit(asyncio.run(main()))
