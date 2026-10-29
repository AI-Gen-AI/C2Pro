#!/usr/bin/env python3
"""S1 Clerk Production identity preflight: READ-ONLY and FAIL-CLOSED.

Verify two *pre-existing* synthetic identities and their precise database
bindings before the browser makes an authenticated request. C2Pro can perform
Clerk user/tenant provisioning from authenticated GETs, so a Playwright test
that merely sends GETs is NOT guaranteed to be database-read-only.

The script calls only Clerk GET endpoints and performs SELECT statements in a
READ ONLY PostgreSQL transaction with a pre-existing least-privilege verifier
role. It never provisions users, changes organizations, or reads project data.
No email, ID, password, API token or database URL is printed.
"""
from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from uuid import UUID

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

CLERK_API = "https://api.clerk.com/v1"
B_TENANT = UUID("00000000-0000-0000-0000-00000000a1f1")
AUTHORIZED_A_PROJECT = UUID("e7c6031f-cd9e-4642-a5ea-35a0207ceaeb")


class PreflightBlocked(Exception):
    """Only reason codes without identifiers may be printed."""


def required(name: str) -> str:
    value = os.getenv(name, "")
    if not value:
        raise PreflightBlocked("MISSING_PROTECTED_CONFIG_" + name)
    return value


@dataclass(frozen=True)
class Identity:
    clerk_user_id: str
    clerk_org_id: str
    tenant_id: UUID


def _rows(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return [item for item in payload["data"] if isinstance(item, dict)]
    raise PreflightBlocked("CLERK_INVALID_RESPONSE_SHAPE")


def _get(client: httpx.Client, path: str, params: dict | None = None) -> object:
    try:
        response = client.get(CLERK_API + path, params=params)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        # Never emit Clerk response bodies; they may include user identifiers.
        raise PreflightBlocked("CLERK_READ_FAILED") from exc


def clerk_identity(
    client: httpx.Client,
    *,
    email: str,
    expected_tenant: UUID,
    expected_org: str | None,
    lane: str,
) -> Identity:
    users = _rows(_get(client, "/users", {"email_address": [email]}))
    if len(users) != 1 or not isinstance(users[0].get("id"), str):
        raise PreflightBlocked(lane + "_CLERK_USER_NOT_UNIQUE")

    user_id = users[0]["id"]
    memberships = _rows(
        _get(client, "/users/" + user_id + "/organization_memberships", {"limit": 100})
    )
    if len(memberships) != 1:
        raise PreflightBlocked(lane + "_CLERK_MEMBERSHIPS_NOT_ONE")
    org = memberships[0].get("organization")
    if not isinstance(org, dict) or not isinstance(org.get("id"), str):
        raise PreflightBlocked(lane + "_CLERK_ORG_MISSING")
    org_id = org["id"]
    if expected_org is not None and org_id != expected_org:
        raise PreflightBlocked(lane + "_CLERK_ORG_MISMATCH")

    org_detail = _get(client, "/organizations/" + org_id)
    if not isinstance(org_detail, dict):
        raise PreflightBlocked(lane + "_CLERK_ORG_INVALID")
    metadata = org_detail.get("public_metadata")
    if not isinstance(metadata, dict) or metadata.get("tenant_id") != str(expected_tenant):
        raise PreflightBlocked(lane + "_CLERK_TENANT_METADATA_MISMATCH")
    return Identity(user_id, org_id, expected_tenant)


def asyncpg_url(raw: str) -> str:
    if raw.startswith("postgresql+asyncpg://"):
        return raw
    if raw.startswith("postgresql://"):
        return "postgresql+asyncpg://" + raw.removeprefix("postgresql://")
    if raw.startswith("postgres://"):
        return "postgresql+asyncpg://" + raw.removeprefix("postgres://")
    raise PreflightBlocked("INVALID_DATABASE_SCHEME")


async def verify_db(a: Identity, b: Identity) -> None:
    engine = create_async_engine(
        asyncpg_url(required("PROD_ACCEPTANCE_DATABASE_URL_READONLY")),
        pool_size=1,
        max_overflow=0,
        connect_args={"timeout": 10},
    )
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await connection.execute(text("SET TRANSACTION READ ONLY"))
                await connection.execute(text("SET LOCAL statement_timeout = '15000ms'"))
                await connection.execute(text("SET LOCAL lock_timeout = '2000ms'"))

                role_result = await connection.execute(
                    text("SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = current_user")
                )
                role = role_result.one()
                if bool(role.rolbypassrls) or bool(role.rolsuper):
                    raise PreflightBlocked("READONLY_DB_ROLE_TOO_POWERFUL")

                for lane, identity in (("A", a), ("B", b)):
                    await connection.execute(
                        text("SELECT set_config('app.current_tenant', :tenant, true)"),
                        {"tenant": str(identity.tenant_id)},
                    )
                    tenant = await connection.execute(
                        text(
                            "SELECT count(*) FROM tenants "
                            "WHERE id = :tenant AND clerk_org_id = :org "
                            "AND is_active IS TRUE"
                        ),
                        {"tenant": identity.tenant_id, "org": identity.clerk_org_id},
                    )
                    if tenant.scalar_one() != 1:
                        raise PreflightBlocked(lane + "_BACKEND_TENANT_LINK_MISSING")

                    user = await connection.execute(
                        text(
                            "SELECT count(*) FROM users "
                            "WHERE tenant_id = :tenant AND clerk_user_id = :user "
                            "AND is_active IS TRUE"
                        ),
                        {"tenant": identity.tenant_id, "user": identity.clerk_user_id},
                    )
                    if user.scalar_one() != 1:
                        raise PreflightBlocked(lane + "_BACKEND_USER_LINK_MISSING")

                # Only the single pre-authorized synthetic project can be read.
                await connection.execute(
                    text("SELECT set_config('app.current_tenant', :tenant, true)"),
                    {"tenant": str(a.tenant_id)},
                )
                owned = await connection.execute(
                    text(
                        "SELECT count(*) FROM projects "
                        "WHERE id = :project AND tenant_id = :tenant "
                        "AND name LIKE 'ACCEPT-706-%'"
                    ),
                    {"project": AUTHORIZED_A_PROJECT, "tenant": a.tenant_id},
                )
                if owned.scalar_one() != 1:
                    raise PreflightBlocked("A_SYNTHETIC_PROJECT_NOT_AUTHORIZED")

                await connection.execute(
                    text("SELECT set_config('app.current_tenant', :tenant, true)"),
                    {"tenant": str(b.tenant_id)},
                )
                project_count = await connection.execute(
                    text("SELECT count(*) FROM projects WHERE tenant_id = :tenant"),
                    {"tenant": b.tenant_id},
                )
                if project_count.scalar_one() != 0:
                    raise PreflightBlocked("B_TENANT_NOT_EMPTY_SYNTHETIC")
            finally:
                await transaction.rollback()
    except PreflightBlocked:
        raise
    except Exception as exc:
        raise PreflightBlocked("DB_READONLY_PREFLIGHT_FAILED") from exc
    finally:
        await engine.dispose()


def main() -> int:
    try:
        if required("PROD_S1_CONFIRM_READONLY") != "RUN-S1-READONLY":
            raise PreflightBlocked("OPERATOR_CONFIRMATION_MISSING")
        key = required("CLERK_SECRET_KEY")
        if not key.startswith("sk_live_"):
            raise PreflightBlocked("NOT_PRODUCTION_CLERK_KEY")
        a_tenant = UUID(required("PROD_ACCEPTANCE_EXPECTED_TENANT_ID"))
        if a_tenant == B_TENANT:
            raise PreflightBlocked("TENANTS_NOT_DISTINCT")
        with httpx.Client(
            timeout=10, headers={"Authorization": "Bearer " + key}
        ) as client:
            a = clerk_identity(
                client,
                email=required("PROD_ACCEPTANCE_CLERK_EMAIL"),
                expected_tenant=a_tenant,
                expected_org=required("PROD_ACCEPTANCE_CLERK_ORGANIZATION_ID"),
                lane="A",
            )
            b = clerk_identity(
                client,
                email=required("E2E_CLERK_TENANT_B_USER_EMAIL"),
                expected_tenant=B_TENANT,
                expected_org=None,
                lane="B",
            )
        if a.clerk_org_id == b.clerk_org_id or a.clerk_user_id == b.clerk_user_id:
            raise PreflightBlocked("IDENTITIES_NOT_DISTINCT")
        asyncio.run(verify_db(a, b))
        print("S1_CLERK_DB_READONLY_PREFLIGHT=PASS (two identities, two existing tenants)")
        return 0
    except PreflightBlocked as exc:
        print("S1_CLERK_DB_READONLY_PREFLIGHT=BLOCKED:" + str(exc), file=sys.stderr)
        return 2
    except (ValueError, RuntimeError):
        print("S1_CLERK_DB_READONLY_PREFLIGHT=BLOCKED:INVALID_CONFIG", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
