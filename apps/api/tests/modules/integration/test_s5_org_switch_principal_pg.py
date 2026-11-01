"""S5-01 precondition: the identity a project permission can safely bind to, given Clerk organization switching.

``get_current_user`` -> ``_provision_clerk_user`` keeps ONE ``users`` row per Clerk user (looked up by
``clerk_user_id``) and, when the token's organization changes, REASSIGNS that same row's ``tenant_id``. These tests run
the production function on PostgreSQL through A -> B -> A and pin what that means for a permission table:

* ``users.id`` is stable per Clerk user across tenants; it is NOT per membership;
* the row's ``role`` is carried over unchanged (an ADMIN of A is an ADMIN row in B) -- a pre-existing property that a
  permission must never be derived from;
* the composite key I first proposed -- ``(tenant_id, user_id) -> users (tenant_id, id)`` -- makes that reassignment
  FAIL for any user who holds a grant (an authentication outage), so it must not be used;
* the safe principal is ``(tenant_id, users.id)`` with the tenant proved by ``users.tenant_id`` AT CHECK TIME: a
  grant of A cannot be used in B (and is dormant, not transferred, while the user is in B).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import dependencies as auth
from src.core.auth.bootstrap_lookup import BootstrapTenantRecord, BootstrapUserRecord
from src.core.auth.models import Tenant, User, UserRole

pytestmark = pytest.mark.asyncio

CLERK_USER = "user_org_switch_principal"


async def _world(db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    suffix = uuid4().hex[:8]
    tenants = {
        name: Tenant(id=uuid4(), name=f"Org {name}", slug=f"org-{name}-{suffix}", clerk_org_id=f"org_{name}_{suffix}", is_active=True)
        for name in ("A", "B")
    }
    db.add_all(tenants.values())
    await db.flush()
    user = User(
        id=uuid4(), tenant_id=tenants["A"].id, email=f"switch-{suffix}@example.invalid", clerk_user_id=CLERK_USER + suffix,
        role=UserRole.ADMIN, is_active=True, is_verified=True,
    )
    db.add(user)
    await db.commit()

    async def tenant_lookup(session: AsyncSession, clerk_org_id: str) -> BootstrapTenantRecord | None:
        row = (await session.execute(select(Tenant).where(Tenant.clerk_org_id == clerk_org_id))).scalar_one_or_none()
        return None if row is None else BootstrapTenantRecord(row.id, row.is_active, row.clerk_org_id, row.name)

    async def user_lookup(session: AsyncSession, clerk_user_id: str) -> BootstrapUserRecord | None:
        row = (await session.execute(select(User).where(User.clerk_user_id == clerk_user_id))).scalar_one_or_none()
        return None if row is None else BootstrapUserRecord(row.id, row.tenant_id, row.email, row.is_active)

    monkeypatch.setattr(auth, "lookup_tenant_by_clerk_org_id", tenant_lookup)
    monkeypatch.setattr(auth, "lookup_user_by_clerk_user_id", user_lookup)
    return {"tenants": tenants, "user": user, "clerk_user_id": user.clerk_user_id}


async def _enter(db: AsyncSession, w: dict[str, Any], org: str) -> User:
    """The production sign-in step for a token whose organization claim is ``org``."""
    return await auth._provision_clerk_user(
        db, w["clerk_user_id"], w["tenants"][org].clerk_org_id, w["user"].email, "Switch", "User"
    )


async def test_the_same_row_moves_between_tenants_keeping_its_id_and_its_role(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    w = await _world(db, monkeypatch)
    a, b = w["tenants"]["A"].id, w["tenants"]["B"].id
    uid = w["user"].id

    in_a = await _enter(db, w, "A")
    assert (in_a.id, in_a.tenant_id) == (uid, a)
    in_b = await _enter(db, w, "B")
    assert (in_b.id, in_b.tenant_id) == (uid, b), "the SAME row is reassigned to B"
    assert in_b.role == UserRole.ADMIN, "FINDING (pre-existing): the role of A is carried into B unchanged"
    back = await _enter(db, w, "A")
    assert (back.id, back.tenant_id) == (uid, a), "and back again"
    assert (await db.execute(text("SELECT count(*) FROM users WHERE clerk_user_id = :c"), {"c": w["clerk_user_id"]})).scalar_one() == 1


async def test_a_composite_tenant_user_key_would_make_the_organization_switch_fail_for_a_granted_user(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Why the FK ``(tenant_id, user_id) -> users (tenant_id, id)`` of the first proposal is rejected."""
    w = await _world(db, monkeypatch)
    a, uid = w["tenants"]["A"].id, w["user"].id
    table = f"scratch_grants_{uuid4().hex[:8]}"
    constraint = f"uq_users_tenant_id_{uuid4().hex[:8]}"
    await db.execute(text(f"ALTER TABLE users ADD CONSTRAINT {constraint} UNIQUE (tenant_id, id)"))
    await db.execute(
        text(
            f"CREATE TABLE {table} (tenant_id uuid NOT NULL, user_id uuid NOT NULL, "
            f"FOREIGN KEY (tenant_id, user_id) REFERENCES users (tenant_id, id))"
        )
    )
    await db.execute(text(f"INSERT INTO {table} VALUES (:t, :u)"), {"t": a, "u": uid})
    await db.commit()
    try:
        with pytest.raises(IntegrityError):  # the sign-in itself fails: the user cannot enter organization B any more
            await _enter(db, w, "B")
        await db.rollback()
    finally:
        await db.execute(text(f"DROP TABLE IF EXISTS {table}"))
        await db.execute(text(f"ALTER TABLE users DROP CONSTRAINT IF EXISTS {constraint}"))
        await db.commit()


async def test_a_key_on_the_stable_user_id_alone_does_not_block_the_switch_and_membership_is_proved_at_check_time(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The chosen design: FK to ``users (id)``; tenant proved by ``users.tenant_id`` when the permission is checked."""
    w = await _world(db, monkeypatch)
    a, b, uid = w["tenants"]["A"].id, w["tenants"]["B"].id, w["user"].id
    table = f"scratch_grants_{uuid4().hex[:8]}"
    await db.execute(
        text(f"CREATE TABLE {table} (tenant_id uuid NOT NULL, user_id uuid NOT NULL REFERENCES users (id), active boolean NOT NULL DEFAULT true)")
    )
    await db.execute(text(f"INSERT INTO {table} (tenant_id, user_id) VALUES (:t, :u)"), {"t": a, "u": uid})
    await db.commit()

    check = text(
        f"SELECT count(*) FROM {table} g JOIN users u ON u.id = g.user_id AND u.tenant_id = g.tenant_id "
        f"WHERE g.tenant_id = :t AND g.user_id = :u AND g.active AND u.is_active"
    )

    async def usable(tenant: UUID) -> int:
        return (await db.execute(check, {"t": tenant, "u": uid})).scalar_one()

    try:
        assert await usable(a) == 1, "in A the grant of A is usable"
        await _enter(db, w, "B")  # the switch succeeds: nothing blocks it
        assert await usable(a) == 0, "while the user is in B the grant of A is DORMANT, not usable"
        assert await usable(b) == 0, "and it is never a grant of B"
        await _enter(db, w, "A")
        assert await usable(a) == 1, "back in A it applies again (it was never transferred or lost)"
        assert await usable(b) == 0
    finally:
        await db.execute(text(f"DROP TABLE IF EXISTS {table}"))
        await db.commit()
