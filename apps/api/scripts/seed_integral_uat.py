"""Nonproduction ONLY: prepare the isolated database for the integral S1–S8 UAT.

What it prepares (nothing of the journey itself -- no project, document, review, alert or link is written here):

* tenant A and its Clerk-linked user: exactly the deterministic E2E tenancy the other acceptance jobs seed
  (``seed_wedge_e2e``), so the live Clerk identity A resolves to a local tenant row;
* tenant B and its Clerk-linked user: a SECOND tenant, bound to the SECOND Clerk Development identity and its own
  Organization, so the cross-tenant denial is proved between two independently authenticated humans;
* ONE declared relaxation, stated here and in the evidence: tenant A's governance setting
  ``wbs_governance.require_distinct_approver`` is set to ``false``. The tenant has a single human, so the canonical
  WBS baseline can only be approved by the same person who submitted it. The approval is then recorded by the
  application as a SELF-approval (``decided_self_approval = true``) and the verifier reports it; it is never hidden.
  A tenant with two humans keeps the default (distinct approver required).

It fails closed: it refuses to run outside ``ENVIRONMENT=test`` with local storage, without both Clerk identities, or
when A and B are not different identities in different Organizations.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import SubscriptionPlan, Tenant, User, UserRole
from src.core.database import close_db, get_raw_session, init_db
from tests.e2e_seed.seed_wedge import TENANT_ID, TEST_PASSWORD_HASH, seed_wedge_e2e

TENANT_B_ID = UUID(os.getenv("E2E_TENANT_B_ID", "00000000-0000-0000-0000-00000000a114"))
USER_B_ID = UUID("00000000-0000-0000-0000-00000000b114")


class SeedError(RuntimeError):
    """A precondition of the integral UAT could not be established."""


def require_environment(env: dict[str, str] | os._Environ[str] = os.environ) -> dict[str, str]:
    if (
        env.get("ENVIRONMENT", "").lower() != "test"
        or env.get("STORAGE_PROVIDER", "").lower() != "local"
    ):
        raise SeedError("INTEGRAL_SEED_REQUIRES_LOCAL_TEST_ONLY")
    needed = (
        "CLERK_E2E_USER_ID",
        "CLERK_E2E_ORG_ID",
        "TENANT_B_CLERK_E2E_USER_ID",
        "TENANT_B_CLERK_E2E_ORG_ID",
        "E2E_CLERK_TENANT_B_USER_EMAIL",
    )
    missing = [name for name in needed if not env.get(name)]
    if missing:
        raise SeedError(f"INTEGRAL_SEED_MISSING_CLERK_IDENTITY: {', '.join(missing)}")
    if env["CLERK_E2E_USER_ID"] == env["TENANT_B_CLERK_E2E_USER_ID"]:
        raise SeedError("INTEGRAL_SEED_A_AND_B_ARE_THE_SAME_CLERK_USER")
    if env["CLERK_E2E_ORG_ID"] == env["TENANT_B_CLERK_E2E_ORG_ID"]:
        raise SeedError("INTEGRAL_SEED_A_AND_B_SHARE_ONE_ORGANIZATION")
    if TENANT_B_ID == TENANT_ID:
        raise SeedError("INTEGRAL_SEED_A_AND_B_SHARE_ONE_TENANT")
    return {name: env[name] for name in needed}


async def _upsert_tenant_b(db: AsyncSession, ids: dict[str, str]) -> None:
    tenant = await db.get(Tenant, TENANT_B_ID)
    if tenant is None:
        db.add(
            Tenant(
                id=TENANT_B_ID,
                name="Integral UAT Tenant B",
                slug="acc01-integral-uat-tenant-b",
                subscription_plan=SubscriptionPlan.PROFESSIONAL,
                subscription_status="active",
                ai_budget_monthly=100.0,
                ai_spend_current=0.0,
                max_projects=100,
                max_users=25,
                max_storage_gb=100,
                is_active=True,
                clerk_org_id=ids["TENANT_B_CLERK_E2E_ORG_ID"],
            )
        )
    else:
        tenant.clerk_org_id = ids["TENANT_B_CLERK_E2E_ORG_ID"]
        tenant.is_active = True
    await db.flush()
    user = await db.get(User, USER_B_ID)
    if user is None:
        db.add(
            User(
                id=USER_B_ID,
                tenant_id=TENANT_B_ID,
                email=ids["E2E_CLERK_TENANT_B_USER_EMAIL"],
                hashed_password=TEST_PASSWORD_HASH,
                first_name="Tenant",
                last_name="B",
                role=UserRole.ADMIN,
                is_active=True,
                is_verified=True,
                clerk_user_id=ids["TENANT_B_CLERK_E2E_USER_ID"],
            )
        )
    else:
        user.tenant_id = TENANT_B_ID
        user.clerk_user_id = ids["TENANT_B_CLERK_E2E_USER_ID"]
        user.is_active = True


async def seed() -> dict[str, Any]:
    ids = require_environment()
    await init_db()
    try:
        async with get_raw_session() as db:
            await seed_wedge_e2e(db)
            tenant_a = await db.get(Tenant, TENANT_ID)
            if tenant_a is None:
                raise SeedError("INTEGRAL_SEED_TENANT_A_MISSING")
            settings = dict(tenant_a.settings or {})
            governance = dict(settings.get("wbs_governance") or {})
            governance["require_distinct_approver"] = False
            settings["wbs_governance"] = governance
            await db.execute(update(Tenant).where(Tenant.id == TENANT_ID).values(settings=settings))
            await _upsert_tenant_b(db, ids)
            await db.commit()
        return {
            "tenant_a": str(TENANT_ID),
            "tenant_b": str(TENANT_B_ID),
            "wbs_distinct_approver_required_tenant_a": False,
        }
    finally:
        await close_db()


if __name__ == "__main__":
    try:
        result = asyncio.run(seed())
    except SeedError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(
        "integral UAT tenancy prepared: tenants differ="
        f"{result['tenant_a'] != result['tenant_b']} "
        f"wbs_distinct_approver_required_tenant_a={result['wbs_distinct_approver_required_tenant_a']}"
    )
