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
sys.path.insert(0, str(Path(__file__).resolve().parent))

os.environ["ENVIRONMENT"] = "test"
os.environ["TEST_DATABASE_URL"] = "postgresql://postgres:postgres@127.0.0.1:5433/c2pro_test"
if "JWT_SECRET_KEY" not in os.environ:
    os.environ["JWT_SECRET_KEY"] = "test_secret_for_gate_only"

import psycopg
from psycopg import sql
from psycopg_pool import AsyncConnectionPool
from security_gate_common import resolve_admin_dsn as _resolve_admin_dsn_impl  # noqa: E402

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


async def _provision_roles(
    pool: AsyncConnectionPool,
    app_role: str,
    admin_login_role: str,
    created_synthetic_roles: list[str],
) -> None:
    """Dynamically provision synthetic restricted roles in the disposable test database."""
    print(
        f"Provisioning synthetic restricted roles ({app_role}, {admin_login_role}) in the disposable database..."
    )
    async with pool.connection() as conn:
        # 1. Provision synthetic app role (NOSUPERUSER, LOGIN, non-owner)
        res = await conn.execute(
            sql.SQL("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = {role})").format(
                role=sql.Literal(app_role)
            )
        )
        if (await res.fetchone())[0]:
            raise RuntimeError(
                f"SAFETY VIOLATION: Synthetic role '{app_role}' unexpectedly already exists. Failing closed."
            )

        await conn.execute(
            sql.SQL(
                "CREATE ROLE {role_id} WITH LOGIN PASSWORD 'app_pass_gate' "
                "NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS"
            ).format(role_id=sql.Identifier(app_role))
        )
        created_synthetic_roles.append(app_role)

        # 2. Provision synthetic admin login role (LOGIN, NOSUPERUSER)
        res = await conn.execute(
            sql.SQL("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = {role})").format(
                role=sql.Literal(admin_login_role)
            )
        )
        if (await res.fetchone())[0]:
            raise RuntimeError(
                f"SAFETY VIOLATION: Synthetic role '{admin_login_role}' unexpectedly already exists. Failing closed."
            )

        await conn.execute(
            sql.SQL(
                "CREATE ROLE {role_id} WITH LOGIN PASSWORD 'admin_pass_gate' "
                "NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS"
            ).format(role_id=sql.Identifier(admin_login_role))
        )
        created_synthetic_roles.append(admin_login_role)

        # 3. Grant capability membership only after required roles exist
        await conn.execute(
            sql.SQL("GRANT c2pro_admin_ops TO {role_id}").format(
                role_id=sql.Identifier(admin_login_role)
            )
        )

        # Grant CONNECT and basic public usage to allow roles to log in
        res = await conn.execute("SELECT current_database()")
        db_name = (await res.fetchone())[0]
        await conn.execute(
            sql.SQL(
                "GRANT CONNECT ON DATABASE {db_name_id} TO {app_role_id}, {admin_login_role_id}"
            ).format(
                db_name_id=sql.Identifier(db_name),
                app_role_id=sql.Identifier(app_role),
                admin_login_role_id=sql.Identifier(admin_login_role),
            )
        )
        await conn.execute(
            sql.SQL("GRANT USAGE ON SCHEMA public TO {app_role_id}, {admin_login_role_id}").format(
                app_role_id=sql.Identifier(app_role),
                admin_login_role_id=sql.Identifier(admin_login_role),
            )
        )

        # Grant DML permissions on dlq_failed_tasks so RLS can be evaluated
        await conn.execute(
            sql.SQL(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON dlq_failed_tasks TO {app_role_id}"
            ).format(app_role_id=sql.Identifier(app_role))
        )


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
        actual = dict(
            zip(["rolsuper", "rolbypassrls", "rolcreaterole", "rolcanlogin"], row, strict=False)
        )
        for k, v in expected.items():
            if actual[k] != v:
                print(f"FAIL: {role}.{k} = {actual[k]}, expected {v}")
                return False
        print(f"OK: {role} catalog properties match expected")
        return True


def _assert_loopback(dsn: str) -> None:
    """Refuse obvious non-loopback/prod DSNs for security safety."""
    if "://" in dsn:
        parsed = urlparse(dsn)
        host = parsed.hostname
    else:
        # Key-value DSN
        import re

        m = re.search(r"\bhost=(\S+)", dsn)
        host = m.group(1) if m else "127.0.0.1"

    if not host:
        host = "127.0.0.1"

    # Normalize host
    host = host.lower().strip()
    if host not in ("127.0.0.1", "localhost", "::1", "postgres-test"):
        raise ValueError(
            f"SAFETY VIOLATION: Target host {host!r} is not loopback. "
            f"The gate only permits local/loopback test databases to prevent accidental production mutation."
        )


async def _test_admin_ops_unprivileged(pool: AsyncConnectionPool) -> bool:
    """Verify c2pro_admin_ops is completely unprivileged as expected by contract."""
    print("\n=== Testing c2pro_admin_ops catalog/privilege properties ===")
    async with pool.connection() as conn:
        # 1. rolcreatedb false
        res = await conn.execute(
            "SELECT rolcreatedb FROM pg_roles WHERE rolname = 'c2pro_admin_ops'"
        )
        row = await res.fetchone()
        if not row or row[0] is not False:
            print("FAIL: c2pro_admin_ops.rolcreatedb is not False")
            return False

        # 2. no memberships (member of no other role besides public/itself)
        res = await conn.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_auth_members m
                JOIN pg_roles r ON m.roleid = r.oid
                WHERE m.member = 'c2pro_admin_ops'::regrole
                AND r.rolname != 'public'
            )
            """
        )
        row = await res.fetchone()
        if row[0]:
            print("FAIL: c2pro_admin_ops inherits unexpected memberships")
            return False

        # 3. no DB/schema ownership
        res = await conn.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_database d
                JOIN pg_roles r ON d.datdba = r.oid
                WHERE d.datname = current_database() AND r.rolname = 'c2pro_admin_ops'
            ) OR EXISTS (
                SELECT 1 FROM pg_namespace n
                JOIN pg_roles r ON n.nspowner = r.oid
                WHERE n.nspname = 'public' AND r.rolname = 'c2pro_admin_ops'
            )
            """
        )
        row = await res.fetchone()
        if row[0]:
            print("FAIL: c2pro_admin_ops owns database or public schema")
            return False

        # 4. no CREATE on database or public schema
        res = await conn.execute(
            """
            SELECT has_schema_privilege('c2pro_admin_ops', 'public', 'CREATE') OR
                   has_database_privilege('c2pro_admin_ops', current_database(), 'CREATE')
            """
        )
        row = await res.fetchone()
        if row[0]:
            print("FAIL: c2pro_admin_ops has CREATE privilege on database or public schema")
            return False

        print("OK: c2pro_admin_ops catalog/privilege properties are fully unprivileged as expected")
        return True


async def _test_admin_login_exact_unprivileged(pool: AsyncConnectionPool) -> bool:
    """Verify admin login is exact member of c2pro_admin_ops and has no elevated permissions."""
    print("\n=== Testing admin login properties ===")
    async with pool.connection() as conn:
        # 1. session_user == current_user
        res = await conn.execute("SELECT session_user = current_user")
        row = await res.fetchone()
        if not row or not row[0]:
            print("FAIL: session_user != current_user")
            return False

        # 2. exact membership only in c2pro_admin_ops
        res = await conn.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_auth_members m
                JOIN pg_roles r ON m.roleid = r.oid
                WHERE m.member = current_user::regrole
                AND r.rolname NOT IN ('c2pro_admin_ops', 'public')
            )
            """
        )
        row = await res.fetchone()
        if row[0]:
            print("FAIL: admin login possesses unexpected role memberships")
            return False

        # 3. no elevated flags
        res = await conn.execute(
            """
            SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb
            FROM pg_roles WHERE rolname = current_user
            """
        )
        row = await res.fetchone()
        if not row or any(row):
            print(f"FAIL: admin login has elevated flags: {row}")
            return False

        # 4. no DB/schema/table ownership
        res = await conn.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_database d
                JOIN pg_roles r ON d.datdba = r.oid
                WHERE d.datname = current_database() AND r.rolname = current_user
            ) OR EXISTS (
                SELECT 1 FROM pg_namespace n
                JOIN pg_roles r ON n.nspowner = r.oid
                WHERE n.nspname = 'public' AND r.rolname = current_user
            ) OR EXISTS (
                SELECT 1 FROM pg_class c
                JOIN pg_roles r ON c.relowner = r.oid
                WHERE c.relname = 'dlq_failed_tasks' AND r.rolname = current_user
            )
            """
        )
        row = await res.fetchone()
        if row[0]:
            print("FAIL: admin login owns database, schema or dlq_failed_tasks")
            return False

        # 5. no CREATE on database or public schema
        res = await conn.execute(
            """
            SELECT has_schema_privilege(current_user, 'public', 'CREATE') OR
                   has_database_privilege(current_user, current_database(), 'CREATE')
            """
        )
        row = await res.fetchone()
        if row[0]:
            print("FAIL: admin login has CREATE privilege on database or public schema")
            return False

        print("OK: admin login properties match exact unprivileged contract")
        return True


async def _test_admin_truncate_denied(pool: AsyncConnectionPool) -> bool:
    """Verify TRUNCATE is denied for c2pro_admin_login."""
    print("\n=== Testing admin login TRUNCATE DENIED ===")
    async with pool.connection() as conn:
        try:
            await conn.execute("TRUNCATE TABLE dlq_failed_tasks")
            print("FAIL: TRUNCATE succeeded (should be denied)")
            return False
        except psycopg.errors.InsufficientPrivilege:
            print("OK: TRUNCATE denied as expected")
            return True
        except Exception as e:
            print(f"FAIL: unexpected error: {e}")
            return False


async def _test_catalog_no_unexpected_dml(pool: AsyncConnectionPool) -> bool:
    """Verify no unexpected DML grants exist on other public business tables."""
    print("\n=== Verifying no unexpected DML on unrelated public business tables ===")
    async with pool.connection() as conn:
        res = await conn.execute(
            """
            SELECT DISTINCT c.relname
            FROM (
                SELECT relname, relnamespace
                FROM pg_class
                WHERE relkind = 'r'
            ) c
            CROSS JOIN LATERAL (
                VALUES ('SELECT'), ('INSERT'), ('UPDATE'), ('DELETE'), ('TRUNCATE')
            ) p(privilege_type)
            JOIN pg_namespace n ON c.relnamespace = n.oid
            WHERE n.nspname = 'public'
              AND c.relname != 'dlq_failed_tasks'
              AND has_table_privilege('c2pro_admin_ops', n.nspname || '.' || c.relname, p.privilege_type)
            """
        )
        unexpected = [row[0] for row in await res.fetchall()]
        if unexpected:
            print(
                f"FAIL: c2pro_admin_ops possesses privileges on unrelated public tables: {unexpected}"
            )
            return False
        print("OK: c2pro_admin_ops possesses absolutely no DML grants on unrelated public tables")
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
            print(
                f"FAIL: c2pro_app Tenant A cross-tenant retry updated {cur.rowcount} rows (should be 0)"
            )
            return False
        print("OK: c2pro_app Tenant A cross-tenant retry updated 0 rows (denied by RLS)")

    return True


async def _test_c2pro_app_cross_tenant_denied(app_pool: AsyncConnectionPool) -> bool:
    """Test c2pro_app cannot perform cross-tenant operations without GUC."""
    print("\n=== Testing c2pro_app cross-tenant denied ===")

    async with app_pool.connection() as conn, conn.transaction():
        # No GUC set - should see nothing (fail-closed)
        result = await conn.execute("SELECT COUNT(*) FROM dlq_failed_tasks")
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
        result = await conn.execute("SELECT tenant_id FROM dlq_failed_tasks ORDER BY tenant_id")
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
        result = await conn.execute("SELECT COUNT(*) FROM dlq_failed_tasks")
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
        if row[0] != 1 or row[1] != "retrying":
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
        if "dlq_admin_select" not in policies:
            print("FAIL: dlq_admin_select policy missing")
            return False
        cmd, roles = policies["dlq_admin_select"]
        if cmd != "r":  # r indicates select capability
            print(f"FAIL: dlq_admin_select cmd = {cmd}, expected 'r'")
            return False
        if "c2pro_admin_ops" not in roles:
            print(f"FAIL: dlq_admin_select roles = {roles}, expected c2pro_admin_ops")
            return False
        print("OK: dlq_admin_select policy TO c2pro_admin_ops FOR SELECT")

        # Check UPDATE policy
        if "dlq_admin_retry" not in policies:
            print("FAIL: dlq_admin_retry policy missing")
            return False
        cmd, roles = policies["dlq_admin_retry"]
        if cmd != "w":  # w indicates update capability
            print(f"FAIL: dlq_admin_retry cmd = {cmd}, expected 'w'")
            return False
        if "c2pro_admin_ops" not in roles:
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
        if "dlq_admin_insert" in all_policies:
            print("FAIL: dlq_admin_insert policy exists (should not)")
            return False
        if "dlq_admin_delete" in all_policies:
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
                if "UPDATE" not in privs:
                    print(f"FAIL: column {col} missing UPDATE grant")
                    return False
                print(f"OK: column {col} has UPDATE grant")
            elif col == "tenant_id":
                if "UPDATE" in privs:
                    print("FAIL: column tenant_id has UPDATE grant (should be excluded)")
                    return False
                print("OK: column tenant_id excluded from UPDATE grant")
            else:
                if "UPDATE" in privs:
                    print(f"FAIL: column {col} has unexpected UPDATE grant")
                    return False

    return True


def _run_alembic_migrations(target_dsn: str) -> None:
    import subprocess
    import sys

    print("\nRunning Alembic migrations on the disposable database...")
    env = os.environ.copy()
    env["DATABASE_URL"] = target_dsn
    env["TEST_DATABASE_URL"] = target_dsn
    env["ENVIRONMENT"] = "test"
    if "JWT_SECRET_KEY" not in env:
        env["JWT_SECRET_KEY"] = "test_secret_for_gate_only"
    api_dir = Path(__file__).resolve().parents[1]
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(api_dir),
        env=env,
        check=True,
    )


def _run_alembic_downgrade(target_dsn: str) -> None:
    import subprocess
    import sys

    print("\nRunning Alembic downgrade on the disposable database...")
    env = os.environ.copy()
    env["DATABASE_URL"] = target_dsn
    env["TEST_DATABASE_URL"] = target_dsn
    env["ENVIRONMENT"] = "test"
    if "JWT_SECRET_KEY" not in env:
        env["JWT_SECRET_KEY"] = "test_secret_for_gate_only"
    api_dir = Path(__file__).resolve().parents[1]
    subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "-1"],
        cwd=str(api_dir),
        env=env,
        check=True,
    )


async def _test_direct_login_escalation_proof(
    admin_pool: AsyncConnectionPool, target_dsn: str, admin_login_role: str
) -> bool:
    print("\n=== Testing direct-login escalation proof (Blocker 2 / Blocker 5) ===")
    from src.config import settings
    from src.core.database import close_admin_ops_db, get_admin_ops_session, init_admin_ops_db

    admin_login_dsn = _derive_dsn(target_dsn, admin_login_role, "admin_pass_gate")
    settings.admin_ops_database_url = admin_login_dsn

    await init_admin_ops_db()
    try:
        async with get_admin_ops_session():
            pass
        print("OK: Initial runtime validation passes (only CONNECT + public USAGE granted)")
    except Exception as exc:
        print(f"FAIL: Initial runtime validation failed: {exc}")
        await close_admin_ops_db()
        return False
    await close_admin_ops_db()

    print(f"Injecting forbidden direct grant (UPDATE (tenant_id)) to {admin_login_role}...")
    async with admin_pool.connection() as conn:
        await conn.execute(
            sql.SQL("GRANT UPDATE (tenant_id) ON dlq_failed_tasks TO {role_id}").format(
                role_id=sql.Identifier(admin_login_role)
            )
        )

    await init_admin_ops_db()
    rejected_successfully = False
    try:
        async with get_admin_ops_session():
            pass
    except RuntimeError as exc:
        if "unexpected direct" in str(exc) or "possesses unexpected direct" in str(exc):
            print(f"OK: Runtime validation successfully rejected direct-login escalation: {exc}")
            rejected_successfully = True
        else:
            print(f"FAIL: Runtime validation rejected for unexpected reason: {exc}")
    except Exception as exc:
        print(f"FAIL: Runtime validation raised unexpected error: {exc}")
    await close_admin_ops_db()

    print(f"Revoking injected forbidden direct grant from {admin_login_role}...")
    async with admin_pool.connection() as conn:
        await conn.execute(
            sql.SQL("REVOKE UPDATE (tenant_id) ON dlq_failed_tasks FROM {role_id}").format(
                role_id=sql.Identifier(admin_login_role)
            )
        )

    await init_admin_ops_db()
    passed_cleanly = False
    try:
        async with get_admin_ops_session():
            passed_cleanly = True
        print("OK: Runtime validation passes cleanly after revoking the direct grant")
    except Exception as exc:
        print(f"FAIL: Runtime validation failed after revocation: {exc}")
    await close_admin_ops_db()

    return rejected_successfully and passed_cleanly


def _snapshot_and_provision_base_db(
    admin_base_dsn: str,
    DB_NAME: str,
    app_role: str,
    admin_login_role: str,
) -> tuple[bool, bool, bool, tuple | None, list[str], bool, bool]:
    canonical_app_existed = False
    canonical_admin_login_existed = False
    admin_role_preexisted = False
    preexisting_ops_flags = None
    preexisting_ops_members = []
    created_by_gate = False
    database_created_by_gate = False

    print("\n=== Checking and Recording Pre-existing Role Snapshot (Section 5 / hygiene) ===")
    with psycopg.connect(admin_base_dsn, autocommit=True) as conn:
        # Check canonical c2pro_app
        res = conn.execute("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'c2pro_app')")
        canonical_app_existed = res.fetchone()[0]
        if canonical_app_existed:
            print("OK: Found pre-existing canonical role 'c2pro_app'")
        else:
            print("INFO: Canonical role 'c2pro_app' does not exist in cluster")

        # Check canonical c2pro_admin_login
        res = conn.execute("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'c2pro_admin_login')")
        canonical_admin_login_existed = res.fetchone()[0]
        if canonical_admin_login_existed:
            print("OK: Found pre-existing canonical role 'c2pro_admin_login'")
        else:
            print("INFO: Canonical role 'c2pro_admin_login' does not exist in cluster")

        # Check c2pro_admin_ops
        res = conn.execute("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'c2pro_admin_ops')")
        admin_role_preexisted = res.fetchone()[0]

        if admin_role_preexisted:
            print("INFO: Capability role 'c2pro_admin_ops' already exists. Validating locked properties...")
            res_props = conn.execute(
                """
                SELECT rolsuper, rolbypassrls, rolcreaterole, rolcanlogin, rolcreatedb
                FROM pg_roles WHERE rolname = 'c2pro_admin_ops'
                """
            )
            props = res_props.fetchone()
            if props:
                rolsuper, rolbypassrls, rolcreaterole, rolcanlogin, rolcreatedb = props
                preexisting_ops_flags = (rolsuper, rolbypassrls, rolcreaterole, rolcanlogin, rolcreatedb)
                if rolsuper or rolbypassrls or rolcreaterole or rolcanlogin or rolcreatedb:
                    raise RuntimeError(
                        f"SAFETY VIOLATION: Pre-existing c2pro_admin_ops role has invalid properties: "
                        f"rolsuper={rolsuper}, rolbypassrls={rolbypassrls}, rolcreaterole={rolcreaterole}, "
                        f"rolcanlogin={rolcanlogin}, rolcreatedb={rolcreatedb}. Expected all to be False."
                    )
                print("OK: Pre-existing 'c2pro_admin_ops' properties are valid (locked flags match contract).")

            # Fetch memberships of pre-existing c2pro_admin_ops to preserve them
            res_m = conn.execute(
                """
                SELECT r.rolname FROM pg_auth_members m
                JOIN pg_roles r ON m.roleid = r.oid
                WHERE m.member = 'c2pro_admin_ops'::regrole
                """
            )
            preexisting_ops_members = [r[0] for r in res_m.fetchall()]
            created_by_gate = False
        else:
            print("INFO: Capability role 'c2pro_admin_ops' does not exist. Creating it with exact locked flags...")
            conn.execute(
                "CREATE ROLE c2pro_admin_ops NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS"
            )
            created_by_gate = True

        # Section 6: Check synthetic role collisions to fail closed early rather than repurposing
        res = conn.execute(sql.SQL("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = {role})").format(role=sql.Literal(app_role)))
        if res.fetchone()[0]:
            raise RuntimeError(f"SAFETY VIOLATION: Synthetic role '{app_role}' unexpectedly already exists. Failing closed.")
        res = conn.execute(sql.SQL("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = {role})").format(role=sql.Literal(admin_login_role)))
        if res.fetchone()[0]:
            raise RuntimeError(f"SAFETY VIOLATION: Synthetic role '{admin_login_role}' unexpectedly already exists. Failing closed.")

        # Ensure clean slate: drop database if exists
        print(f"\nCleaning up database {DB_NAME} if exists...")
        conn.execute(f"DROP DATABASE IF EXISTS {DB_NAME}")
        conn.execute(f"CREATE DATABASE {DB_NAME}")
        database_created_by_gate = True

    return (
        canonical_app_existed,
        canonical_admin_login_existed,
        admin_role_preexisted,
        preexisting_ops_flags,
        preexisting_ops_members,
        created_by_gate,
        database_created_by_gate,
    )


async def _run_gate_assertions(
    admin_pool: AsyncConnectionPool,
    app_pool: AsyncConnectionPool,
    admin_login_pool: AsyncConnectionPool,
) -> bool:
    passed = True
    # 1. Role catalog properties
    print("\n=== Role Catalog Verification ===")
    passed &= await _check_role_properties(
        admin_pool,
        "c2pro_admin_ops",
        rolsuper=False,
        rolbypassrls=False,
        rolcreaterole=False,
        rolcanlogin=False,
    )

    # 2. Table ownership
    passed &= await _check_table_owner(admin_pool, "dlq_failed_tasks", "c2pro_admin_ops")

    # 3. Extended unprivileged check on c2pro_admin_ops
    passed &= await _test_admin_ops_unprivileged(admin_pool)

    # 4. Extended unprivileged check on admin login role
    passed &= await _test_admin_login_exact_unprivileged(admin_login_pool)

    # 5. Seed DLQ rows
    await _seed_dlq_rows(admin_pool)

    # 6. app role tenant isolation
    passed &= await _test_c2pro_app_tenant_isolation(app_pool)

    # 7. app role cross-tenant denied
    passed &= await _test_c2pro_app_cross_tenant_denied(app_pool)

    # 8. Admin login cross-tenant SELECT
    passed &= await _test_admin_login_select_cross_tenant(admin_login_pool)

    # 9. Admin login COUNT cross-tenant
    passed &= await _test_admin_login_count_cross_tenant(admin_login_pool)

    # 10. Admin login retry UPDATE
    passed &= await _test_admin_login_retry_update(admin_login_pool)

    # 11. Admin tenant_id UPDATE denied
    passed &= await _test_admin_tenant_id_update_denied(admin_login_pool)

    # 12. Admin INSERT denied
    passed &= await _test_admin_insert_denied(admin_login_pool)

    # 13. Admin DELETE denied
    passed &= await _test_admin_delete_denied(admin_login_pool)

    # 14. Unrelated table access denied
    passed &= await _test_admin_unrelated_table_denied(admin_login_pool)

    # 15. Admin policy catalog
    passed &= await _test_admin_policy_catalog(admin_login_pool)

    # 16. Column-level UPDATE grant
    passed &= await _test_grant_catalog(admin_login_pool)

    # 17. Admin TRUNCATE denied
    passed &= await _test_admin_truncate_denied(admin_login_pool)

    # 18. No unexpected DML on unrelated public business tables
    passed &= await _test_catalog_no_unexpected_dml(admin_pool)

    return passed


def _execute_teardown_and_hygiene(
    admin_base_dsn: str,
    DB_NAME: str,
    app_role: str,
    admin_login_role: str,
    database_created_by_gate: bool,
    created_synthetic_roles: list[str],
    created_by_gate: bool,
    admin_role_preexisted: bool,
    canonical_app_existed: bool,
    canonical_admin_login_existed: bool,
    preexisting_ops_flags: tuple | None,
    preexisting_ops_members: list[str],
    cleanup_errors: list[str],
) -> bool:
    hygiene_passed = True
    print("\n=== Executing Outer Fail-Safe Cleanup Lifecycle ===")

    # 2. Connect to postgres as superuser to perform teardown
    try:
        with psycopg.connect(admin_base_dsn, autocommit=True) as conn:
            # Disconnect active connections to DB if we created it
            if database_created_by_gate:
                print(f"Terminating active backend connections to {DB_NAME}...")
                try:
                    conn.execute(
                        f"""
                        SELECT pg_terminate_backend(pid) FROM pg_stat_activity
                        WHERE datname = '{DB_NAME}' AND pid <> pg_backend_pid()
                        """
                    )
                except Exception as e:
                    cleanup_errors.append(f"Failed to terminate active connections to {DB_NAME}: {e}")

                print(f"Dropping target database: {DB_NAME}...")
                try:
                    conn.execute(f"DROP DATABASE IF EXISTS {DB_NAME}")
                    print(f"OK: Disposable database {DB_NAME} dropped successfully")
                except Exception as e:
                    cleanup_errors.append(f"Failed to drop disposable database {DB_NAME}: {e}")

            # Drop synthetic login roles actually created by this invocation
            for role_name in reversed(created_synthetic_roles):
                try:
                    conn.execute(sql.SQL("DROP ROLE IF EXISTS {role}").format(role=sql.Identifier(role_name)))
                    print(f"OK: Synthetic login role '{role_name}' dropped cleanly")
                except Exception as e:
                    cleanup_errors.append(f"Failed to drop synthetic role {role_name}: {e}")

            # If c2pro_admin_ops was created by the gate, drop it
            if created_by_gate:
                print("INFO: Dropping gate-created capability role 'c2pro_admin_ops'...")
                try:
                    conn.execute("DROP ROLE IF EXISTS c2pro_admin_ops")
                    print("OK: Gate-created 'c2pro_admin_ops' dropped cleanly")
                except Exception as e:
                    cleanup_errors.append(f"Failed to drop gate-created role c2pro_admin_ops: {e}")
            else:
                print("INFO: Preserving pre-existing c2pro_admin_ops capability role.")

            print("\n=== Verifying Cluster Hygiene State (Section 5 / R10) ===")
            # Prove c2pro_app exists/is untouched if it originally pre-existed
            try:
                res = conn.execute("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'c2pro_app')")
                still_exists = res.fetchone()[0]
                if still_exists != canonical_app_existed:
                    hygiene_passed = False
                    cleanup_errors.append("HYGIENE FAILURE: Canonical role 'c2pro_app' state was altered/mutated")
                else:
                    print("OK: Canonical role 'c2pro_app' state remained untouched by gate")
            except Exception as e:
                cleanup_errors.append(f"Failed to verify c2pro_app state: {e}")

            # Prove c2pro_admin_login exists/is untouched if it originally pre-existed
            try:
                res = conn.execute("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'c2pro_admin_login')")
                still_exists = res.fetchone()[0]
                if still_exists != canonical_admin_login_existed:
                    hygiene_passed = False
                    cleanup_errors.append("HYGIENE FAILURE: Canonical role 'c2pro_admin_login' state was altered/mutated")
                else:
                    print("OK: Canonical role 'c2pro_admin_login' state remained untouched by gate")
            except Exception as e:
                cleanup_errors.append(f"Failed to verify c2pro_admin_login state: {e}")

            # Prove c2pro_admin_ops state conforms to pre-existing or created
            try:
                res = conn.execute("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'c2pro_admin_ops')")
                ops_exists = res.fetchone()[0]
                if admin_role_preexisted:
                    if not ops_exists:
                        hygiene_passed = False
                        cleanup_errors.append("HYGIENE FAILURE: Pre-existing capability role 'c2pro_admin_ops' was deleted")
                    else:
                        # Verify flags and memberships unchanged
                        res_props = conn.execute(
                            """
                            SELECT rolsuper, rolbypassrls, rolcreaterole, rolcanlogin, rolcreatedb
                            FROM pg_roles WHERE rolname = 'c2pro_admin_ops'
                            """
                        )
                        props = res_props.fetchone()
                        if props != preexisting_ops_flags:
                            hygiene_passed = False
                            cleanup_errors.append(f"HYGIENE FAILURE: Pre-existing 'c2pro_admin_ops' flags mutated from {preexisting_ops_flags} to {props}")
                        else:
                            print("OK: Pre-existing capability role 'c2pro_admin_ops' flags remained unchanged")

                        res_m = conn.execute(
                            """
                            SELECT r.rolname FROM pg_auth_members m
                            JOIN pg_roles r ON m.roleid = r.oid
                            WHERE m.member = 'c2pro_admin_ops'::regrole
                            """
                        )
                        members = [r[0] for r in res_m.fetchall()]
                        if sorted(members) != sorted(preexisting_ops_members):
                            hygiene_passed = False
                            cleanup_errors.append(f"HYGIENE FAILURE: Pre-existing 'c2pro_admin_ops' memberships mutated from {preexisting_ops_members} to {members}")
                        else:
                            print("OK: Pre-existing capability role 'c2pro_admin_ops' memberships remained unchanged")
                else:
                    if ops_exists:
                        hygiene_passed = False
                        cleanup_errors.append("HYGIENE FAILURE: Gate-created capability role 'c2pro_admin_ops' was leaked")
                    else:
                        print("OK: Gate-created capability role 'c2pro_admin_ops' was cleanly deleted")
            except Exception as e:
                cleanup_errors.append(f"Failed to verify c2pro_admin_ops state: {e}")

            # Prove synthetic login roles deleted
            try:
                res_admin = conn.execute(sql.SQL("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = {role})").format(role=sql.Literal(admin_login_role)))
                res_app = conn.execute(sql.SQL("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = {role})").format(role=sql.Literal(app_role)))
                if res_admin.fetchone()[0] or res_app.fetchone()[0]:
                    hygiene_passed = False
                    cleanup_errors.append("HYGIENE FAILURE: Synthetic temporary login roles leaked in cluster")
                else:
                    print("OK: Synthetic temporary login roles cleanly and completely deleted from cluster")
            except Exception as e:
                cleanup_errors.append(f"Failed to verify synthetic role deletion: {e}")

            # Prove database deleted
            try:
                res = conn.execute(f"SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname = '{DB_NAME}')")
                if res.fetchone()[0]:
                    hygiene_passed = False
                    cleanup_errors.append("HYGIENE FAILURE: Disposable database leaked in cluster")
                else:
                    print("OK: Disposable database cleanly and completely deleted from cluster")
            except Exception as e:
                cleanup_errors.append(f"Failed to verify database deletion: {e}")

    except Exception as e:
        cleanup_errors.append(f"Fail-safe cleanup database connection level exception: {e}")

    return hygiene_passed


async def main() -> int:
    """Run the C2.5 disposable DB gate with an outer fail-safe lifecycle."""
    import sys

    if sys.platform == "win32":
        import asyncio

        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # 1. Resolve P0_SEC_ADMIN_DSN through the canonical loopback-only resolver
    try:
        admin_dsn = _resolve_admin_dsn_impl("P0_SEC_ADMIN_DSN")
    except Exception as exc:
        print(f"ERROR resolving P0_SEC_ADMIN_DSN: {exc}")
        return 1

    DB_NAME = "c25_admin_ops_gate"

    # Dynamic synthetic restricted roles for isolation
    app_role = f"c25_gate_app_{os.getpid()}"
    admin_login_role = f"c25_gate_admin_{os.getpid()}"

    # Deriving the target disposable database DSN
    target_dsn = admin_dsn.rsplit("/", 1)[0] + "/" + DB_NAME
    admin_base_dsn = admin_dsn.rsplit("/", 1)[0] + "/postgres"

    # Resource initialization for outer try/finally fail-safe lifecycle
    admin_pool = None
    app_pool = None
    admin_login_pool = None
    created_synthetic_roles: list[str] = []
    cleanup_errors: list[str] = []
    all_passed = True

    # Snapshots and setups
    try:
        (
            canonical_app_existed,
            canonical_admin_login_existed,
            admin_role_preexisted,
            preexisting_ops_flags,
            preexisting_ops_members,
            created_by_gate,
            database_created_by_gate,
        ) = _snapshot_and_provision_base_db(admin_base_dsn, DB_NAME, app_role, admin_login_role)

        print(f"Successfully created disposable database: {DB_NAME}")

        # Run the initial migration chain
        _run_alembic_migrations(target_dsn)

        # Connect to the target disposable database as superuser
        print(f"Connecting to {DB_NAME} as superuser...")
        admin_pool = await _connect(target_dsn)

        # 1. Dynamically provision the restricted synthetic roles and grant CONNECT/USAGE
        await _provision_roles(admin_pool, app_role, admin_login_role, created_synthetic_roles)

        # 2. Derive connection DSNs for synthetic roles internally
        app_dsn = _derive_dsn(target_dsn, app_role, "app_pass_gate")
        admin_login_dsn = _derive_dsn(target_dsn, admin_login_role, "admin_pass_gate")

        # 3. Create restricted connection pools
        print(f"Connecting as {app_role} and {admin_login_role}...")
        app_pool = await _connect(app_dsn)
        admin_login_pool = await _connect(admin_login_dsn)

        # Execute initial gate checks
        all_passed &= await _run_gate_assertions(admin_pool, app_pool, admin_login_pool)

        # Run direct-login escalation proof (Blocker 2 / Blocker 5)
        all_passed &= await _test_direct_login_escalation_proof(admin_pool, target_dsn, admin_login_role)

        # Upgrade -> Gate -> Downgrade -> Upgrade -> Gate verification lifecycle
        print("\n=== Executing Downgrade -> Upgrade Idempotency Lifecycle ===")
        # Close pools before downgrade
        await app_pool.close()
        await admin_login_pool.close()

        _run_alembic_downgrade(target_dsn)
        _run_alembic_migrations(target_dsn)

        # Reconnect pools
        app_pool = await _connect(app_dsn)
        admin_login_pool = await _connect(admin_login_dsn)

        print("\nRe-running all assertions after downgrade/upgrade...")
        all_passed &= await _run_gate_assertions(admin_pool, app_pool, admin_login_pool)

    except Exception as exc:
        print(f"\n❌ GATE LIFECYCLE EXECUTION FAILURE: {exc}")
        all_passed = False

    finally:
        # 1. Gracefully close connection pools if they exist
        if app_pool:
            try:
                await app_pool.close()
            except Exception as e:
                cleanup_errors.append(f"Failed to close app_pool: {e}")
        if admin_login_pool:
            try:
                await admin_login_pool.close()
            except Exception as e:
                cleanup_errors.append(f"Failed to close admin_login_pool: {e}")
        if admin_pool:
            try:
                await admin_pool.close()
            except Exception as e:
                cleanup_errors.append(f"Failed to close admin_pool: {e}")

        hygiene_passed = _execute_teardown_and_hygiene(
            admin_base_dsn,
            DB_NAME,
            app_role,
            admin_login_role,
            database_created_by_gate,
            created_synthetic_roles,
            created_by_gate,
            admin_role_preexisted,
            canonical_app_existed,
            canonical_admin_login_existed,
            preexisting_ops_flags,
            preexisting_ops_members,
            cleanup_errors,
        )

        if cleanup_errors or not hygiene_passed:
            all_passed = False
            print("\n❌ HYGIENE OR CLEANUP FAILURES DETECTED:")
            for err in cleanup_errors:
                print(f"  - {err}")
        else:
            print("\nOK: Cluster-state hygiene verified successfully. No privileges on 'c2pro_test' were changed.")

    if all_passed:
        print(
            "\n✅ ALL C2.5 GATE CHECKS PASSED (disposable DB + escalation proof + downgrade/upgrade)"
        )
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
