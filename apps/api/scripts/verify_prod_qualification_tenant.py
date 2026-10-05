#!/usr/bin/env python
"""Read-only preflight for the dedicated production qualification tenant."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ASYNCPG_URL_PREFIX = "postgresql+asyncpg://"


def _url(raw: str) -> str:
    if raw.startswith(ASYNCPG_URL_PREFIX):
        return raw
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", ASYNCPG_URL_PREFIX, 1)
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", ASYNCPG_URL_PREFIX, 1)
    raise ValueError("unsupported database URL scheme")


async def verify(database_url: str, tenant_id: UUID, clerk_org_id: str) -> tuple[bool, list[str]]:
    engine = create_async_engine(_url(database_url))
    details: list[str] = []
    try:
        async with engine.connect() as conn:
            tx = await conn.begin()
            try:
                await conn.execute(text("SET TRANSACTION READ ONLY"))
                await conn.execute(
                    text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
                    {"tenant_id": str(tenant_id)},
                )
                binding = int(
                    (
                        await conn.execute(
                            text(
                                """
                                SELECT count(*)
                                  FROM tenants
                                 WHERE id=:tenant_id
                                   AND is_active IS TRUE
                                   AND clerk_org_id=:clerk_org_id
                                   AND coalesce((settings ->> 'synthetic_acceptance')::boolean, false) IS TRUE
                                """
                            ),
                            {"tenant_id": tenant_id, "clerk_org_id": clerk_org_id},
                        )
                    ).scalar_one()
                )
                foreign = int(
                    (
                        await conn.execute(
                            text(
                                """
                                SELECT count(*)
                                  FROM projects
                                 WHERE tenant_id=:tenant_id
                                   AND name NOT LIKE 'ACCEPT-706-%'
                                   AND name NOT LIKE 'P0c PROD %'
                                   AND name NOT LIKE 'P0d PROD %'
                                """
                            ),
                            {"tenant_id": tenant_id},
                        )
                    ).scalar_one()
                )
                await tx.rollback()
            except Exception:
                await tx.rollback()
                raise
    finally:
        await engine.dispose()

    details.append(f"synthetic_tenant_binding={binding}")
    details.append(f"non_qualification_projects={foreign}")
    return binding == 1 and foreign == 0, details


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", default=os.getenv("PROD_ACCEPTANCE_EXPECTED_TENANT_ID"))
    parser.add_argument("--clerk-org-id", default=os.getenv("PROD_ACCEPTANCE_CLERK_ORGANIZATION_ID"))
    args = parser.parse_args()
    database_url = os.getenv("PROD_ACCEPTANCE_DATABASE_URL_READONLY")
    if not database_url or not args.tenant_id or not args.clerk_org_id:
        print("FAIL: protected qualification configuration missing", file=sys.stderr)
        return 2
    try:
        ok, details = asyncio.run(
            verify(database_url, UUID(args.tenant_id), args.clerk_org_id)
        )
    except Exception as exc:
        print(f"FAIL: qualification tenant preflight failed ({type(exc).__name__})", file=sys.stderr)
        return 2
    for detail in details:
        print(detail)
    print(f"PROD_QUALIFICATION_TENANT_PREFLIGHT={'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
