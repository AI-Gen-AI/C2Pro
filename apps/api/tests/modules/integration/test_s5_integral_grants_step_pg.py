"""Owner decision D1: the explicit grants step AFTER the project exists, on an isolated PostgreSQL, under enforce.

What is proven (the Clerk identities are never created: only existing ``users`` rows are used):

* before the step the tenants are in the transitional ``off`` and a stranger still passes (the historical rehearsal);
  after it they are ``enforce`` and the stranger is denied -- ``enforce`` is DEMONSTRATED, not assumed;
* the three capabilities exist only for the grantee, only on the project the step names: a second project of the SAME
  tenant is a stranger's project, another tenant's member holds nothing, and a revocation is effective on the next check;
* the grants were created by the governed function, with actor, reason and audit event; the single-human tenant uses
  the documented, limited exception and is labelled SELF_GRANTED_NOT_INDEPENDENT; an independent ADMIN needs none;
* every missing precondition is a refusal with NOTHING written (project of another tenant, missing/inactive/viewer
  grantee, non-ADMIN grantor), and the script refuses a non-isolated database.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.grant_integral_uat_project import (
    ALL_CAPABILITIES,
    GrantStepRefused,
    establish_project_authority,
    require_isolated_environment,
)
from src.modules.hitl.adapters.persistence.project_review_grants import ProjectReviewGrantRepository
from src.modules.hitl.application.project_review_authorization import (
    ProjectAuthorizationDenied,
    ProjectCapability,
    ProjectReviewAuthorizer,
)
from tests.modules.integration.grants_world import GrantsWorld, build_world, in_tenant

pytestmark = pytest.mark.asyncio


async def _can(db: AsyncSession, w: GrantsWorld, *, tenant, user, project, cap) -> bool:
    await in_tenant(db, tenant)
    try:
        await ProjectReviewAuthorizer(db).require(tenant_id=tenant, user_id=user, project_id=project, capability=cap)
    except ProjectAuthorizationDenied:
        return False
    return True


async def _mode(db: AsyncSession, tenant) -> str | None:
    return (await db.execute(text("SELECT settings #>> '{hitl_project_authorization,mode}' FROM tenants WHERE id = :t"), {"t": tenant})).scalar_one()


async def _legacy_world(db: AsyncSession) -> GrantsWorld:
    """The state the seed leaves: both tenants in the explicit transitional ``off`` and no grant anywhere."""
    return await build_world(db, mode="off")


async def test_enforce_is_demonstrated_before_and_after_the_step(db: AsyncSession) -> None:
    w = await _legacy_world(db)
    stranger = w.outsider_a
    assert await _can(db, w, tenant=w.tenant_a, user=stranger, project=w.p1, cap=ProjectCapability.APPROVE_CANDIDATE), "off: legacy rule"

    report = await establish_project_authority(
        db, tenant_id=w.tenant_a, project_id=w.p1, grantee_user_id=w.reviewer_a, grantor_user_id=w.admin_a, enforce_also=(w.tenant_b,)
    )
    await db.commit()

    assert report["grant_kind"] == "INDEPENDENT_ADMIN_GRANT" and set(report["grants"]) == {c.value for c in ALL_CAPABILITIES}
    assert (await _mode(db, w.tenant_a), await _mode(db, w.tenant_b)) == ("enforce", "enforce")
    marker = (await db.execute(text("SELECT settings #> '{hitl_project_authorization}' FROM tenants WHERE id = :t"), {"t": w.tenant_a})).scalar_one()
    assert "transitional" not in marker and "reason" not in marker, "enforce is not a transitional state"
    for cap in ALL_CAPABILITIES:
        assert await _can(db, w, tenant=w.tenant_a, user=w.reviewer_a, project=w.p1, cap=cap), cap
        assert not await _can(db, w, tenant=w.tenant_a, user=stranger, project=w.p1, cap=cap), f"enforce denies a stranger: {cap}"
    assert not await _can(db, w, tenant=w.tenant_a, user=w.admin_a, project=w.p1, cap=ProjectCapability.APPROVE_CANDIDATE), (
        "being the tenant ADMIN (and the grantor) is not authority to approve"
    )


async def test_the_authority_is_per_project_per_tenant_and_revocable(db: AsyncSession) -> None:
    w = await _legacy_world(db)
    report = await establish_project_authority(
        db, tenant_id=w.tenant_a, project_id=w.p1, grantee_user_id=w.reviewer_a, grantor_user_id=w.admin_a, enforce_also=(w.tenant_b,)
    )
    await db.commit()

    # a second project of the SAME tenant is a stranger's project for the grantee
    for cap in ALL_CAPABILITIES:
        assert not await _can(db, w, tenant=w.tenant_a, user=w.reviewer_a, project=w.p2, cap=cap), f"P2 denied: {cap}"
    # tenant B: its own member holds nothing on A's project, and the grantee's grants are not usable in B's context
    for cap in ALL_CAPABILITIES:
        assert not await _can(db, w, tenant=w.tenant_b, user=w.user_b, project=w.p1, cap=cap), f"B member on A's project: {cap}"
        assert not await _can(db, w, tenant=w.tenant_b, user=w.reviewer_a, project=w.p1, cap=cap), f"A's grantee in B's context: {cap}"
    assert not await _can(db, w, tenant=w.tenant_b, user=w.user_b, project=w.p_b, cap=ProjectCapability.READ_REVIEW), "B is enforce too: nothing is granted"

    # revocation of ONE capability is effective on the next check and leaves the others
    await in_tenant(db, w.tenant_a)
    await ProjectReviewGrantRepository(db).revoke(
        tenant_id=w.tenant_a, grant_id=UUID(report["grants"]["APPROVE_CANDIDATE"]), revoked_by=w.admin_a, reason="test revocation",
    )
    await db.commit()
    assert not await _can(db, w, tenant=w.tenant_a, user=w.reviewer_a, project=w.p1, cap=ProjectCapability.APPROVE_CANDIDATE)
    assert await _can(db, w, tenant=w.tenant_a, user=w.reviewer_a, project=w.p1, cap=ProjectCapability.READ_REVIEW)


async def test_grants_are_governed_with_actor_reason_and_audit_events_and_the_step_is_idempotent(db: AsyncSession) -> None:
    w = await _legacy_world(db)
    kwargs = {"tenant_id": w.tenant_a, "project_id": w.p1, "grantee_user_id": w.reviewer_a, "grantor_user_id": w.admin_a}
    first = await establish_project_authority(db, **kwargs)
    second = await establish_project_authority(db, **kwargs)
    await db.commit()
    assert first["grants"] == second["grants"], "a second run creates nothing new"
    rows = (await db.execute(text(
        "SELECT permission, granted_by, grant_reason, self_grant_exception FROM project_review_grants WHERE tenant_id = :t AND revoked_at IS NULL"
    ), {"t": w.tenant_a})).all()
    assert sorted(r[0] for r in rows) == sorted(c.value for c in ALL_CAPABILITIES)
    assert all(r[1] == w.admin_a and r[2].startswith("integral UAT") and r[3] is False for r in rows)
    events = (await db.execute(text(
        "SELECT count(*) FROM project_events WHERE tenant_id = :t AND project_id = :p AND event_type = 'hitl.project_grant_created'"
    ), {"t": w.tenant_a, "p": w.p1})).scalar_one()
    assert events == 3, "one audit event per capability, written with the grant"


async def test_the_single_human_tenant_uses_the_documented_limited_exception_and_is_labelled(db: AsyncSession) -> None:
    w = await _legacy_world(db)
    # tenant A has ONE human here: the ADMIN grants to themselves
    report = await establish_project_authority(db, tenant_id=w.tenant_a, project_id=w.p1, grantee_user_id=w.admin_a)
    await db.commit()
    assert report["grant_kind"] == "SELF_GRANTED_NOT_INDEPENDENT" and report["grantor_user_id"] == str(w.admin_a)
    exception = (await db.execute(text("SELECT settings #> '{hitl_project_authorization,single_person_exception}' FROM tenants WHERE id = :t"), {"t": w.tenant_a})).scalar_one()
    assert exception["enabled"] is True and all(str(exception[k]).strip() for k in ("reason", "granted_by", "granted_at"))
    labelled = (await db.execute(text("SELECT bool_and(self_grant_exception) FROM project_review_grants WHERE tenant_id = :t"), {"t": w.tenant_a})).scalar_one()
    assert labelled is True
    # the exception is LIMITED: tenant B got none and an ordinary self-grant in B is still refused by the database
    assert (await db.execute(text("SELECT settings #> '{hitl_project_authorization,single_person_exception}' FROM tenants WHERE id = :t"), {"t": w.tenant_b})).scalar_one() is None
    await in_tenant(db, w.tenant_b)
    with pytest.raises(Exception, match="self-granted without the audited single-person exception"):
        await ProjectReviewGrantRepository(db).grant(
            tenant_id=w.tenant_b, project_id=w.p_b, user_id=w.admin_b, capability=ProjectCapability.APPROVE_CANDIDATE,
            granted_by=w.admin_b, reason="ordinary self-grant",
        )
    await db.rollback()


@pytest.mark.parametrize(
    "case",
    ["project_of_another_tenant", "missing_project", "missing_grantee", "inactive_grantee", "grantor_not_admin", "grantor_other_tenant"],
)
async def test_every_missing_precondition_refuses_and_writes_nothing(db: AsyncSession, case: str) -> None:
    w = await _legacy_world(db)
    project, grantee, grantor = w.p1, w.reviewer_a, w.admin_a
    if case == "project_of_another_tenant":
        project = w.p_b
    elif case == "missing_project":
        project = uuid4()
    elif case == "missing_grantee":
        grantee = uuid4()
    elif case == "inactive_grantee":
        await db.execute(text("UPDATE users SET is_active = false WHERE id = :u"), {"u": w.reviewer_a})
        await db.commit()
    elif case == "grantor_not_admin":
        grantor = w.approver_a
    elif case == "grantor_other_tenant":
        grantor = w.admin_b
    with pytest.raises(GrantStepRefused):
        await establish_project_authority(
            db, tenant_id=w.tenant_a, project_id=project, grantee_user_id=grantee, grantor_user_id=grantor, enforce_also=(w.tenant_b,)
        )
    await db.rollback()
    assert (await db.execute(text("SELECT count(*) FROM project_review_grants"))).scalar_one() == 0
    assert (await _mode(db, w.tenant_a), await _mode(db, w.tenant_b)) == ("off", "off"), "fail closed: no mode was changed"


async def test_a_viewer_or_api_principal_cannot_be_granted(db: AsyncSession) -> None:
    w = await _legacy_world(db)
    await db.execute(text("UPDATE users SET role = 'viewer' WHERE id = :u"), {"u": w.reviewer_a})
    await db.commit()
    with pytest.raises(GrantStepRefused, match="NOT_A_HUMAN_MEMBER"):
        await establish_project_authority(db, tenant_id=w.tenant_a, project_id=w.p1, grantee_user_id=w.reviewer_a, grantor_user_id=w.admin_a)
    await db.rollback()


async def test_the_step_refuses_a_non_isolated_database_or_environment() -> None:
    ok = {"ENVIRONMENT": "test", "DATABASE_URL": "postgresql+asyncpg://u:p@localhost:5433/c2pro_test"}
    require_isolated_environment(ok)
    for env in (
        {**ok, "ENVIRONMENT": "production"},
        {**ok, "DATABASE_URL": "postgresql+asyncpg://u:p@db.example.supabase.co:5432/postgres"},
        {"ENVIRONMENT": "test"},
    ):
        with pytest.raises(GrantStepRefused, match="REQUIRES_ISOLATED_TEST_DATABASE"):
            require_isolated_environment(env)
