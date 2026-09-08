#!/usr/bin/env python3
"""Owner bootstrap for the c2pro_admin_ops capability role (C2.5).

Analogous to C2 checkpoint_bootstrap.py: provisions the capability role
before the admin policy migration runs.

ROLE: c2pro_admin_ops
  NOLOGIN
  NOSUPERUSER
  NOCREATEDB
  NOCREATEROLE
  NOBYPASSRLS
  non-owner

Usage:
    ADMIN_OPS_OWNER_DATABASE_URL=postgresql://c2pro_owner:...@host/db \\
        python apps/api/scripts/admin_ops_bootstrap.py

Credential: reads ADMIN_OPS_OWNER_DATABASE_URL, falling back to
DATABASE_URL (logged, not silent) -- until C3 provisions a literal
c2pro_owner secret per environment, the existing full-privilege application
credential plays that role, which is safe: it is strictly MORE privileged
than what this script needs, not less.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _resolve_owner_dsn() -> tuple[str, bool]:
    """Return (dsn, is_fallback). Never silently picks a DSN without saying which."""
    owner_dsn = os.environ.get("ADMIN_OPS_OWNER_DATABASE_URL")
    if owner_dsn:
        return owner_dsn, False
    fallback = os.environ.get("DATABASE_URL")
    if not fallback:
        raise SystemExit(
            "admin_ops_bootstrap: neither ADMIN_OPS_OWNER_DATABASE_URL nor "
            "DATABASE_URL is set. Provide an owner-privileged DSN."
        )
    return fallback, True


async def bootstrap_admin_ops_role(dsn: str) -> None:
    """Create c2pro_admin_ops capability role with exact properties.

    Raises on failure (including if role already exists with wrong properties, unexpected memberships,
    unexpected ownership, or unexpected direct DML privileges).
    """
    from psycopg_pool import AsyncConnectionPool

    conn_string = dsn.replace("postgresql+asyncpg://", "postgresql://")
    pool = AsyncConnectionPool(
        conninfo=conn_string,
        min_size=0,
        max_size=2,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": None},
    )
    try:
        await pool.open(wait=True, timeout=30)

        async with pool.connection() as conn:
            # Check if role exists and verify properties
            result = await conn.execute(
                """
                SELECT rolsuper, rolbypassrls, rolcreaterole, rolcanlogin, rolcreatedb
                FROM pg_roles WHERE rolname = 'c2pro_admin_ops'
                """
            )
            row = await result.fetchone()

            if row:
                rolsuper, rolbypassrls, rolcreaterole, rolcanlogin, rolcreatedb = row
                if (rolsuper or rolbypassrls or rolcreaterole or rolcanlogin or rolcreatedb):
                    raise RuntimeError(
                        "c2pro_admin_ops exists but has incorrect properties: "
                        f"rolsuper={rolsuper}, rolbypassrls={rolbypassrls}, "
                        f"rolcreaterole={rolcreaterole}, rolcanlogin={rolcanlogin}, "
                        f"rolcreatedb={rolcreatedb}. Drop and re-run, or fix manually."
                    )

                # Validate no memberships
                result_mem = await conn.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM pg_auth_members m
                        JOIN pg_roles r ON m.roleid = r.oid
                        WHERE m.member = 'c2pro_admin_ops'::regrole
                        AND r.rolname != 'public'
                    )
                    """
                )
                row_mem = await result_mem.fetchone()
                if row_mem[0]:
                    raise RuntimeError("c2pro_admin_ops possesses unexpected role memberships.")

                # Validate not owner of current database or public schema
                result_own = await conn.execute(
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
                row_own = await result_own.fetchone()
                if row_own[0]:
                    raise RuntimeError("c2pro_admin_ops owns the current database or the public schema.")

                # Validate not owner of tables/sequences/functions/types in current DB
                result_obj_own = await conn.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM pg_class c
                        JOIN pg_roles r ON c.relowner = r.oid
                        JOIN pg_namespace n ON c.relnamespace = n.oid
                        WHERE n.nspname = 'public' AND r.rolname = 'c2pro_admin_ops'
                    ) OR EXISTS (
                        SELECT 1 FROM pg_proc p
                        JOIN pg_roles r ON p.proowner = r.oid
                        JOIN pg_namespace n ON p.pronamespace = n.oid
                        WHERE n.nspname = 'public' AND r.rolname = 'c2pro_admin_ops'
                    ) OR EXISTS (
                        SELECT 1 FROM pg_type t
                        JOIN pg_roles r ON t.typowner = r.oid
                        JOIN pg_namespace n ON t.typnamespace = n.oid
                        WHERE n.nspname = 'public' AND r.rolname = 'c2pro_admin_ops'
                    )
                    """
                )
                row_obj_own = await result_obj_own.fetchone()
                if row_obj_own[0]:
                    raise RuntimeError("c2pro_admin_ops owns objects (tables, functions, types, etc.) in the database.")

                # Validate no unexpected direct DML privileges on other public business tables
                result_dml = await conn.execute(
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
                unexpected_tables = [r[0] for r in await result_dml.fetchall()]
                if unexpected_tables:
                    raise RuntimeError(
                        "c2pro_admin_ops possesses unexpected privileges on public business tables: "
                        f"{', '.join(unexpected_tables)}"
                    )

                # Check if dlq_failed_tasks exists before verifying privileges on it
                result_exists = await conn.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM pg_class c
                        JOIN pg_namespace n ON c.relnamespace = n.oid
                        WHERE n.nspname = 'public' AND c.relname = 'dlq_failed_tasks'
                    )
                    """
                )
                row_exists = await result_exists.fetchone()
                if row_exists[0]:
                    # Validate on dlq_failed_tasks (INSERT, DELETE, TRUNCATE, unexpected columns)
                    result_dlq_tbl = await conn.execute(
                        """
                        SELECT p.privilege_type
                        FROM (
                            VALUES ('INSERT'), ('DELETE'), ('TRUNCATE')
                        ) p(privilege_type)
                        WHERE has_table_privilege('c2pro_admin_ops', 'dlq_failed_tasks', p.privilege_type)
                        """
                    )
                    unexpected_dlq_privs = [r[0] for r in await result_dlq_tbl.fetchall()]
                    if unexpected_dlq_privs:
                        raise RuntimeError(
                            f"c2pro_admin_ops possesses unexpected direct table-level privileges on dlq_failed_tasks: {unexpected_dlq_privs}"
                        )

                    result_dlq_cols = await conn.execute(
                        """
                        SELECT a.attname
                        FROM pg_attribute a
                        JOIN pg_class c ON a.attrelid = c.oid
                        JOIN pg_namespace n ON c.relnamespace = n.oid
                        WHERE n.nspname = 'public'
                          AND c.relname = 'dlq_failed_tasks'
                          AND a.attnum > 0
                          AND NOT a.attisdropped
                          AND a.attname NOT IN ('retry_count', 'status', 'updated_at', 'next_retry_at')
                          AND has_column_privilege('c2pro_admin_ops', 'dlq_failed_tasks', a.attname, 'UPDATE')
                        """
                    )
                    unexpected_dlq_cols = [r[0] for r in await result_dlq_cols.fetchall()]
                    if unexpected_dlq_cols:
                        raise RuntimeError(
                            f"c2pro_admin_ops possesses unexpected UPDATE privileges on dlq_failed_tasks columns: {unexpected_dlq_cols}"
                        )
                else:
                    print("dlq_failed_tasks table does not exist yet; skipping relation-level privilege checks.")

                print("c2pro_admin_ops already exists and is fully verified compliant.")
                return

            # Create role with exact properties
            await conn.execute(
                """
                CREATE ROLE c2pro_admin_ops
                NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
                """
            )
            print("c2pro_admin_ops capability role created successfully.")

    finally:
        await pool.close()


async def main() -> int:
    dsn, is_fallback = _resolve_owner_dsn()
    if is_fallback:
        print(
            "admin_ops_bootstrap: ADMIN_OPS_OWNER_DATABASE_URL not set, "
            "using DATABASE_URL (TRANSITIONAL -- see module docstring)."
        )
    else:
        print("admin_ops_bootstrap: using ADMIN_OPS_OWNER_DATABASE_URL.")

    await bootstrap_admin_ops_role(dsn)
    print("admin_ops_bootstrap: c2pro_admin_ops capability role is provisioned.")
    return 0


if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    raise SystemExit(asyncio.run(main()))
