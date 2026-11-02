"""Support for the owner's browser session (an EPHEMERAL Development/Test stack on a CI runner, never Production).

``seed``  -- resolve the owner's Clerk Development user READ-ONLY, require it to be a member of the dedicated E2E Organization, and
             upsert the matching local user row (tenant = the synthetic E2E tenant, role ADMIN) in the isolated database.
``grants`` -- the review rules stay in ``enforce``; so the owner can decide findings in the projects they create, a loop gives that
             one user the three review capabilities on each new project of the tenant (through the governed grant function, declared
             SELF_GRANTED_NOT_INDEPENDENT). Same step as the automated runs use (grant_integral_uat_project); runs until its deadline.

Both refuse unless ENVIRONMENT=test and the database is a loopback one. No secret is printed; the email is only fingerprinted.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import sys
import time
from typing import Any
from uuid import UUID, uuid5

from sqlalchemy import text

NAMESPACE = UUID("6f0b6f0e-2f3a-4c1e-9d55-0c2f1a0e0a0a")
SYNTHETIC_TENANT = UUID("00000000-0000-0000-0000-00000000a113")


def owner_user_id(clerk_user_id: str) -> UUID:
    """A stable local id for the owner's row: the same Clerk user always maps to the same row."""
    return uuid5(NAMESPACE, clerk_user_id)


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()[:10]


def resolve_owner(email: str) -> str:
    """READ-ONLY: the Clerk user id of the owner, who must be a member of the dedicated E2E Organization."""
    import httpx

    from scripts.provision_clerk_e2e_fixture import (
        DEFAULT_ORG_NAME,
        DEFAULT_TENANT_ID,
        ClerkAdmin,
        FixtureError,
        require_development_instance,
        select_organization,
    )

    secret = os.environ["CLERK_SECRET_KEY"]
    require_development_instance(secret, os.getenv("CLERK_PUBLISHABLE_KEY") or os.getenv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY"))
    with httpx.Client(timeout=30.0, headers={"Authorization": f"Bearer {secret}"}) as client:
        admin = ClerkAdmin(client)
        users = admin.users_by_email(email)
        if len(users) != 1:
            raise FixtureError(f"OWNER_CLERK_USER_NOT_FOUND_OR_AMBIGUOUS: {len(users)} user(s) for fingerprint {fingerprint(email)}")
        user_id = str(users[0]["id"])
        organizations, _ = admin.list_organizations()
        org = select_organization(organizations, name=os.getenv("E2E_CLERK_ORG_NAME", DEFAULT_ORG_NAME), tenant_id=os.getenv("E2E_TENANT_ID", DEFAULT_TENANT_ID))
        if org is None or not any((m.get("organization") or {}).get("id") == org["id"] for m in admin.user_memberships(user_id)):
            raise FixtureError("OWNER_NOT_A_MEMBER_OF_THE_E2E_ORGANIZATION: run provision_owner_dev_user.py (authorized) first")
        return user_id


async def seed(email: str, clerk_user_id: str) -> dict[str, Any]:
    from scripts.grant_integral_uat_project import require_isolated_environment
    from src.core.auth.models import User, UserRole
    from src.core.database import close_db, get_raw_session, init_db
    from tests.e2e_seed.seed_wedge import TEST_PASSWORD_HASH

    require_isolated_environment()
    await init_db()
    try:
        async with get_raw_session() as db:
            row_id = owner_user_id(clerk_user_id)
            existing = await db.get(User, row_id)
            if existing is None:
                db.add(
                    User(
                        id=row_id, tenant_id=SYNTHETIC_TENANT, email=email, hashed_password=TEST_PASSWORD_HASH, first_name="Owner",
                        last_name="Session", role=UserRole.ADMIN, is_active=True, is_verified=True, clerk_user_id=clerk_user_id,
                    )
                )
            else:
                existing.tenant_id, existing.is_active, existing.clerk_user_id = SYNTHETIC_TENANT, True, clerk_user_id
            await db.commit()
        return {"local_user_id": str(row_id), "email_fingerprint": fingerprint(email), "created": existing is None}
    finally:
        await close_db()


async def grants_loop(local_user_id: UUID, deadline: float, every: float = 8.0) -> int:
    from scripts.grant_integral_uat_project import (
        GrantStepRefused,
        establish_project_authority,
        require_isolated_environment,
    )
    from src.core.database import close_db, get_raw_session, init_db

    require_isolated_environment()
    await init_db()
    granted = 0
    try:
        while time.time() < deadline:
            async with get_raw_session() as db:
                rows = (
                    await db.execute(
                        text(
                            "SELECT p.id FROM public.projects p WHERE p.tenant_id = cast(:t as uuid) AND NOT EXISTS ("
                            "SELECT 1 FROM public.project_review_grants g WHERE g.project_id = p.id AND g.user_id = cast(:u as uuid) "
                            "AND g.permission = 'APPROVE_CANDIDATE' AND g.revoked_at IS NULL)"
                        ),
                        {"t": str(SYNTHETIC_TENANT), "u": str(local_user_id)},
                    )
                ).all()
                for (project_id,) in rows:
                    try:
                        await establish_project_authority(db, tenant_id=SYNTHETIC_TENANT, project_id=project_id, grantee_user_id=local_user_id)
                        await db.commit()
                        granted += 1
                        print(f"granted review capabilities on a new project (total {granted})", flush=True)
                    except GrantStepRefused as exc:
                        await db.rollback()
                        print(f"grant skipped: {exc}", flush=True)
            await asyncio.sleep(every)
    finally:
        await close_db()
    return granted


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else ""
    email = os.environ.get("OWNER_SESSION_EMAIL", "")
    if command == "seed":
        clerk_id = resolve_owner(email)
        print(asyncio.run(seed(email, clerk_id)))
        return 0
    if command == "grants":
        clerk_id = resolve_owner(email)
        minutes = min(int(os.environ.get("OWNER_SESSION_MINUTES", "60")), 120)
        asyncio.run(grants_loop(owner_user_id(clerk_id), time.time() + minutes * 60 + 120))
        return 0
    print("usage: python -m scripts.owner_session_support seed|grants", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
