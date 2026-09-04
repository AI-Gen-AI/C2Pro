#!/usr/bin/env python
"""Read back and prove the Clerk <-> local tenant linkage.

TS-E2E-P0B-TENANT-LINK-001.

Seeding a value and asserting it are different things, and this is a tenant
boundary: if ``tenants.clerk_org_id`` or ``users.clerk_user_id`` did not land
exactly as intended, the backend would resolve a Clerk JWT to the wrong tenant
(or auto-provision a new one) and the acceptance journey would still pass while
proving nothing about isolation.

So this re-reads both rows from PostgreSQL after the seed and proves four
equalities. It never mutates, and it reports boolean equality only -- raw Clerk
identifiers are compared in process and never printed.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Repository truth: apps/api/tests/e2e_seed/seed_wedge.py
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-00000000a113"
DEFAULT_USER_ID = "00000000-0000-0000-0000-00000000b113"


def _normalize_database_url(raw: str) -> str:
    if raw.startswith("postgresql+asyncpg://"):
        return raw
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+asyncpg://", 1)
    return raw


def evaluate_tenant_link(
    tenant: dict[str, Any] | None,
    user: dict[str, Any] | None,
    *,
    expected_tenant_id: str,
    expected_org_id: str,
    expected_user_clerk_id: str,
) -> list[tuple[str, bool, str]]:
    """Return (check_name, passed, safe_detail) for the four linkage equalities.

    ``safe_detail`` never contains a Clerk identifier -- only presence and the
    outcome of an in-process comparison.
    """
    checks: list[tuple[str, bool, str]] = []

    if tenant is None:
        return [("tenant row exists", False, "tenant row not found")]
    if user is None:
        checks.append(("tenant row exists", True, "found"))
        checks.append(("user row exists", False, "user row not found"))
        return checks

    checks.append(("tenant row exists", True, "found"))
    checks.append(("user row exists", True, "found"))

    tenant_id = str(tenant.get("id", ""))
    checks.append(
        (
            "tenant.id is the deterministic E2E tenant",
            tenant_id == expected_tenant_id,
            f"matches={tenant_id == expected_tenant_id}",
        )
    )

    clerk_org_id = tenant.get("clerk_org_id")
    checks.append(
        (
            "tenant.clerk_org_id is the dedicated E2E Organization",
            bool(clerk_org_id) and clerk_org_id == expected_org_id,
            f"present={bool(clerk_org_id)} matches={clerk_org_id == expected_org_id}",
        )
    )

    clerk_user_id = user.get("clerk_user_id")
    checks.append(
        (
            "user.clerk_user_id is the configured E2E identity",
            bool(clerk_user_id) and clerk_user_id == expected_user_clerk_id,
            f"present={bool(clerk_user_id)} matches={clerk_user_id == expected_user_clerk_id}",
        )
    )

    user_tenant_id = str(user.get("tenant_id", ""))
    checks.append(
        (
            "user.tenant_id is the deterministic E2E tenant",
            user_tenant_id == expected_tenant_id,
            f"matches={user_tenant_id == expected_tenant_id}",
        )
    )
    return checks


async def _read_rows(
    database_url: str, tenant_id: UUID, user_id: UUID
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    engine = create_async_engine(_normalize_database_url(database_url))
    try:
        async with engine.connect() as conn:
            tenant_row = (
                await conn.execute(
                    text("SELECT id, clerk_org_id FROM tenants WHERE id = CAST(:tid AS uuid)"),
                    {"tid": str(tenant_id)},
                )
            ).mappings().first()
            user_row = (
                await conn.execute(
                    text(
                        "SELECT id, tenant_id, clerk_user_id FROM users "
                        "WHERE id = CAST(:uid AS uuid)"
                    ),
                    {"uid": str(user_id)},
                )
            ).mappings().first()
    finally:
        await engine.dispose()
    return (dict(tenant_row) if tenant_row else None, dict(user_row) if user_row else None)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", default=os.getenv("E2E_EXPECTED_TENANT_ID", DEFAULT_TENANT_ID))
    parser.add_argument("--user-id", default=DEFAULT_USER_ID)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    args = parser.parse_args()

    if not args.database_url:
        print("FAIL: DATABASE_URL is required to verify the tenant link.", file=sys.stderr)
        return 2

    expected_org_id = os.getenv("CLERK_E2E_ORG_ID", "")
    expected_user_clerk_id = os.getenv("CLERK_E2E_USER_ID", "")
    if not expected_org_id or not expected_user_clerk_id:
        print(
            "FAIL: CLERK_E2E_ORG_ID and CLERK_E2E_USER_ID must be exported by the fixture "
            "step before the tenant link can be proven.",
            file=sys.stderr,
        )
        return 2

    tenant, user = asyncio.run(
        _read_rows(args.database_url, UUID(args.tenant_id), UUID(args.user_id))
    )
    checks = evaluate_tenant_link(
        tenant,
        user,
        expected_tenant_id=args.tenant_id,
        expected_org_id=expected_org_id,
        expected_user_clerk_id=expected_user_clerk_id,
    )

    print("E2E tenant linkage read-back (boolean evidence only)")
    for name, passed, detail in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name} ({detail})")

    failed = [name for name, passed, _ in checks if not passed]
    if failed:
        print(f"\nFAIL: {len(failed)} tenant linkage guarantee(s) not met: {', '.join(failed)}")
        return 1
    print("\nPASS: Clerk and the local database describe the same tenant.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
