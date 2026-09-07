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

    Raises on failure (including if role already exists with wrong properties).
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
                SELECT rolsuper, rolbypassrls, rolcreaterole, rolcanlogin
                FROM pg_roles WHERE rolname = 'c2pro_admin_ops'
                """
            )
            row = result.fetchone()

            if row:
                rolsuper, rolbypassrls, rolcreaterole, rolcanlogin = row
                if (rolsuper or rolbypassrls or rolcreaterole or rolcanlogin):
                    raise RuntimeError(
                        "c2pro_admin_ops exists but has incorrect properties: "
                        f"rolsuper={rolsuper}, rolbypassrls={rolbypassrls}, "
                        f"rolcreaterole={rolcreaterole}, rolcanlogin={rolcanlogin}. "
                        "Drop and re-run, or fix manually."
                    )
                print("c2pro_admin_ops already exists with correct properties.")
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
    raise SystemExit(asyncio.run(main()))
