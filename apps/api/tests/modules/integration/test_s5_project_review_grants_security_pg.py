"""S5-01 on real PostgreSQL: the grants table is an authority, so it is tested as one -- not only by tenant RLS.

Proven here, with the REAL migration SQL: effective INSERT/UPDATE/DELETE privileges; that an ordinary role (no
BYPASSRLS, no privileges) can neither create a grant nor call the writers; that even the owner cannot write outside the
governed functions; forced RLS partitions by tenant; revocation is auditable and history immutable; the grant and its
audit event are one atomic write; concurrent grants/revocations and the FOR SHARE gate S5-05 will use; and that none of
it breaks (or leaks across) the Clerk organization switch.
"""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.hitl.adapters.persistence.project_review_grants import (
    ProjectGrantRefused,
    ProjectReviewGrantRepository,
)
from src.modules.hitl.application.project_review_authorization import (
    ProjectAuthorizationDenied,
    ProjectCapability,
    ProjectReviewAuthorizer,
)
from tests.modules.integration.grants_world import GrantsWorld, build_world, in_tenant, migration

pytestmark = pytest.mark.asyncio

READ, REVIEW, APPROVE = ProjectCapability.READ_REVIEW, ProjectCapability.REVIEW_FINDING, ProjectCapability.APPROVE_CANDIDATE


async def _grant(db: AsyncSession, w: GrantsWorld, *, user: UUID, project: UUID, cap: ProjectCapability, by: UUID | None = None, tenant: UUID | None = None, exception: str | None = None) -> UUID:
    return await ProjectReviewGrantRepository(db).grant(
        tenant_id=tenant or w.tenant_a, project_id=project, user_id=user, capability=cap,
        granted_by=by or w.admin_a, reason="synthetic test grant", exception_reason=exception,
    )


async def _count(db: AsyncSession, sql: str, **params: object) -> int:
    return int((await db.execute(text(sql), params)).scalar_one())


# ── the migration itself ─────────────────────────────────────────────────────────────────────────────────────────
async def test_the_schema_is_additive_forced_rls_with_no_delete_policy_and_a_clean_downgrade(db: AsyncSession) -> None:
    w = await build_world(db)
    flags = (await db.execute(text("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = 'project_review_grants'"))).one()
    assert tuple(flags) == (True, True)
    policies = {r[0]: r[1] for r in (await db.execute(text("SELECT policyname, cmd FROM pg_policies WHERE tablename = 'project_review_grants'"))).all()}
    assert sorted(policies.values()) == ["INSERT", "SELECT", "UPDATE"], "no DELETE policy exists"
    # the two keys that would block the Clerk organization switch do NOT exist
    keys = (await db.execute(text("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = 'public.project_review_grants'::regclass AND contype = 'f'"))).scalars().all()
    assert not [k for k in keys if "tenant_id, user_id" in k or "users(tenant_id" in k.replace(" ", "")], keys
    # existing tenants of the world were created BEFORE nothing marks them: the migration's own marker statement is exercised below
    assert w.tenant_a

    for statement in migration().DOWNGRADE_STATEMENTS:
        await (await db.connection()).exec_driver_sql(statement)
    await db.commit()
    assert not (await db.execute(text("SELECT to_regclass('public.project_review_grants') IS NOT NULL"))).scalar_one()


async def test_the_migration_marks_existing_tenants_transitional_and_leaves_marked_ones_alone(db: AsyncSession) -> None:
    stmt = migration().UPGRADE_STATEMENTS[-1]
    await build_world(db, mode=None)
    # the test bootstrap pre-marks fixture tenants: strip it so these look like pre-migration production tenants
    await db.execute(text("UPDATE tenants SET settings = coalesce(settings, '{}'::jsonb) - 'hitl_project_authorization'"))
    await db.commit()
    unmarked = await _count(db, "SELECT count(*) FROM tenants WHERE NOT (coalesce(settings,'{}'::jsonb) ? 'hitl_project_authorization')")
    assert unmarked >= 2
    await (await db.connection()).exec_driver_sql(stmt)
    await db.commit()
    assert await _count(db, "SELECT count(*) FROM tenants WHERE NOT (coalesce(settings,'{}'::jsonb) ? 'hitl_project_authorization')") == 0
    row = (await db.execute(text("SELECT settings #>> '{hitl_project_authorization,mode}', settings #>> '{hitl_project_authorization,transitional}' FROM tenants LIMIT 1"))).one()
    assert tuple(row) == ("off", "true")
    # a tenant already set to enforce is not touched
    await db.execute(text("UPDATE tenants SET settings = jsonb_set(settings, '{hitl_project_authorization,mode}', '\"enforce\"') WHERE id = (SELECT id FROM tenants LIMIT 1)"))
    await (await db.connection()).exec_driver_sql(stmt)
    await db.commit()
    assert await _count(db, "SELECT count(*) FROM tenants WHERE settings #>> '{hitl_project_authorization,mode}' = 'enforce'") == 1


# ── privileges ───────────────────────────────────────────────────────────────────────────────────────────────────
async def test_not_even_the_owner_can_write_outside_the_governed_functions_and_nothing_can_delete(db: AsyncSession) -> None:
    w = await build_world(db)
    await in_tenant(db, w.tenant_a)
    with pytest.raises(DBAPIError, match="governed functions"):
        await db.execute(
            text(
                "INSERT INTO project_review_grants (grant_id, tenant_id, project_id, user_id, permission, granted_by, grant_reason) "
                "VALUES (gen_random_uuid(), :t, :p, :u, 'READ_REVIEW', :a, 'direct insert')"
            ),
            {"t": w.tenant_a, "p": w.p1, "u": w.reviewer_a, "a": w.admin_a},
        )
    await db.rollback()
    await in_tenant(db, w.tenant_a)
    gid = await _grant(db, w, user=w.reviewer_a, project=w.p1, cap=READ)
    await db.commit()
    await in_tenant(db, w.tenant_a)
    for statement, message in (
        ("DELETE FROM project_review_grants WHERE grant_id = :g", "append-only"),
        ("UPDATE project_review_grants SET grant_reason = 'edited' WHERE grant_id = :g", "governed functions"),
    ):
        with pytest.raises(DBAPIError, match=message):
            await db.execute(text(statement), {"g": gid})
        await db.rollback()
        await in_tenant(db, w.tenant_a)
    assert await _count(db, "SELECT count(*) FROM project_review_grants WHERE grant_id = :g AND grant_reason = 'synthetic test grant'", g=gid) == 1


async def test_an_ordinary_role_without_bypassrls_can_neither_write_read_nor_call_the_writers(db: AsyncSession) -> None:
    w = await build_world(db)
    role = f"prg_ordinary_{uuid4().hex[:10]}"
    await db.execute(text(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS"))
    await db.execute(text(f"GRANT USAGE ON SCHEMA public TO {role}"))  # so the TABLE privileges are what is under test
    await db.commit()
    try:
        attrs = (await db.execute(text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = :r"), {"r": role})).one()
        assert tuple(attrs) == (False, False), "the role under test really has no BYPASSRLS"
        for statement, params in (
            ("INSERT INTO project_review_grants (grant_id, tenant_id, project_id, user_id, permission, granted_by, grant_reason) VALUES (gen_random_uuid(), :t, :p, :u, 'READ_REVIEW', :a, 'x')", {"t": w.tenant_a, "p": w.p1, "u": w.reviewer_a, "a": w.admin_a}),
            ("UPDATE project_review_grants SET grant_reason = 'x'", {}),
            ("DELETE FROM project_review_grants", {}),
            ("SELECT count(*) FROM project_review_grants", {}),
            ("SELECT public.project_review_grant_create(:t, :p, :u, 'READ_REVIEW', :a, 'x', NULL)", {"t": w.tenant_a, "p": w.p1, "u": w.reviewer_a, "a": w.admin_a}),
            ("SELECT public.project_review_grant_revoke(:t, gen_random_uuid(), :a, 'x')", {"t": w.tenant_a, "a": w.admin_a}),
        ):
            await db.execute(text(f"SET LOCAL ROLE {role}"))
            await in_tenant(db, w.tenant_a)
            with pytest.raises(DBAPIError, match="permission denied"):
                await db.execute(text(statement), params)
            await db.rollback()
    finally:
        await db.rollback()
        await db.execute(text("RESET ROLE"))
        await db.execute(text(f"DROP OWNED BY {role}"))
        await db.execute(text(f"DROP ROLE IF EXISTS {role}"))
        await db.commit()


async def test_forced_rls_partitions_rows_by_tenant_for_a_role_that_is_allowed_to_read(db: AsyncSession) -> None:
    w = await build_world(db)
    await in_tenant(db, w.tenant_a)
    await _grant(db, w, user=w.reviewer_a, project=w.p1, cap=READ)
    await db.commit()
    await in_tenant(db, w.tenant_b)
    await _grant(db, w, user=w.user_b, project=w.p_b, cap=READ, by=w.admin_b, tenant=w.tenant_b)
    await db.commit()
    role = f"prg_reader_{uuid4().hex[:10]}"
    await db.execute(text(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS"))
    await db.execute(text(f"GRANT USAGE ON SCHEMA public TO {role}"))
    await db.execute(text(f"GRANT SELECT ON project_review_grants TO {role}"))
    await db.commit()
    try:
        await db.execute(text(f"SET LOCAL ROLE {role}"))
        seen = {}
        for label, tenant in (("a", w.tenant_a), ("b", w.tenant_b), ("none", None)):
            await in_tenant(db, tenant)
            seen[label] = await _count(db, "SELECT count(*) FROM project_review_grants")
        assert seen == {"a": 1, "b": 1, "none": 0}, "each tenant sees only its own grants; no context sees nothing"
        await in_tenant(db, w.tenant_a)
        with pytest.raises(DBAPIError, match="permission denied"):  # reading is not writing
            await db.execute(text("DELETE FROM project_review_grants"))
        await db.rollback()
    finally:
        await db.rollback()
        await db.execute(text("RESET ROLE"))
        await db.execute(text(f"DROP OWNED BY {role}"))
        await db.execute(text(f"DROP ROLE IF EXISTS {role}"))
        await db.commit()


# ── who may grant, and what is refused ───────────────────────────────────────────────────────────────────────────
async def test_only_an_active_admin_grants_to_an_active_member_of_the_same_tenant_and_no_ordinary_self_grant(db: AsyncSession) -> None:
    w = await build_world(db)
    await in_tenant(db, w.tenant_a)
    ok = await _grant(db, w, user=w.reviewer_a, project=w.p1, cap=REVIEW)
    assert ok
    assert await _count(db, "SELECT count(*) FROM project_events WHERE event_type = 'hitl.project_grant_created' AND payload->>'grant_id' = :g", g=str(ok)) == 1

    for _label, kwargs, message in (
        ("a USER cannot administer grants", {"user": w.approver_a, "project": w.p1, "cap": APPROVE, "by": w.reviewer_a}, "only an active ADMIN"),
        ("an ADMIN cannot self-grant APPROVE_CANDIDATE", {"user": w.admin_a, "project": w.p1, "cap": APPROVE}, "self-granted"),
        ("an ADMIN cannot self-grant any capability", {"user": w.admin_a, "project": w.p1, "cap": READ}, "self-granted"),
        ("the grantee must belong to the tenant", {"user": w.user_b, "project": w.p1, "cap": READ}, "active member"),
        ("the project must belong to the tenant", {"user": w.reviewer_a, "project": w.p_b, "cap": READ}, "violates foreign key|foreign key"),
        ("an exception flag outside a self-grant", {"user": w.reviewer_a, "project": w.p2, "cap": READ, "exception": "because"}, "marks only a self-grant"),
    ):
        with pytest.raises((ProjectGrantRefused, DBAPIError, IntegrityError), match=message):
            await _grant(db, w, **kwargs)  # type: ignore[arg-type]
        await in_tenant(db, w.tenant_a)
    # the writer is bound to the session's tenant context: naming tenant A while the context says B is refused
    await db.execute(text("SELECT set_config('app.current_tenant', :t, false)"), {"t": str(w.tenant_b)})
    with pytest.raises(DBAPIError, match="own tenant context"):
        await db.execute(
            text("SELECT public.project_review_grant_create(:t, :p, :u, 'READ_REVIEW', :a, 'x', NULL)"),
            {"t": w.tenant_a, "p": w.p1, "u": w.approver_a, "a": w.admin_a},
        )
    await db.rollback()


async def test_the_single_person_exception_is_governed_audited_and_not_implicit(db: AsyncSession) -> None:
    w = await build_world(db)
    await in_tenant(db, w.tenant_a)
    with pytest.raises(ProjectGrantRefused, match="self-granted"):
        await _grant(db, w, user=w.admin_a, project=w.p1, cap=APPROVE, exception="no second person exists")  # flag without the tenant setting
    await db.execute(
        text("UPDATE tenants SET settings = jsonb_set(settings, '{hitl_project_authorization,single_person_exception}', cast(:v as jsonb), true) WHERE id = :t"),
        {"t": w.tenant_a, "v": '{"enabled": true, "reason": "synthetic single-human tenant", "granted_by": "operator:test", "granted_at": "2026-11-01T10:00:00+00:00"}'},
    )
    await db.commit()
    await in_tenant(db, w.tenant_a)
    with pytest.raises(ProjectGrantRefused, match="self-granted"):  # the setting alone is not enough: the grant must say so
        await ProjectReviewGrantRepository(db).grant(tenant_id=w.tenant_a, project_id=w.p1, user_id=w.admin_a, capability=APPROVE, granted_by=w.admin_a, reason="x")
    gid = await _grant(db, w, user=w.admin_a, project=w.p1, cap=APPROVE, exception="no second person exists")
    payload = (await db.execute(text("SELECT payload FROM project_events WHERE payload->>'grant_id' = :g"), {"g": str(gid)})).scalar_one()
    assert payload["self_grant_exception"] is True and payload["exception_reason"] == "no second person exists"
    # the exception is per-grant and per-project: it grants nothing on another project, and nothing else implicitly
    auth = ProjectReviewAuthorizer(db)
    assert (await auth.require(tenant_id=w.tenant_a, user_id=w.admin_a, project_id=w.p1, capability=APPROVE)).grant_id == gid
    with pytest.raises(ProjectAuthorizationDenied) as other_project:
        await auth.require(tenant_id=w.tenant_a, user_id=w.admin_a, project_id=w.p2, capability=APPROVE)
    assert other_project.value.visible is False
    with pytest.raises(ProjectAuthorizationDenied) as other_capability:
        await auth.require(tenant_id=w.tenant_a, user_id=w.admin_a, project_id=w.p1, capability=REVIEW)
    assert other_capability.value.visible is True, "the ADMIN holds one capability only; it can see the project but not review"


# ── revocation, history, atomicity ───────────────────────────────────────────────────────────────────────────────
async def test_revocation_is_auditable_once_only_admin_only_and_history_is_kept(db: AsyncSession) -> None:
    w = await build_world(db)
    await in_tenant(db, w.tenant_a)
    repo = ProjectReviewGrantRepository(db)
    gid = await _grant(db, w, user=w.approver_a, project=w.p1, cap=APPROVE)
    with pytest.raises(ProjectGrantRefused, match="only an active ADMIN"):
        await repo.revoke(tenant_id=w.tenant_a, grant_id=gid, revoked_by=w.reviewer_a, reason="not an admin")
    await repo.revoke(tenant_id=w.tenant_a, grant_id=gid, revoked_by=w.admin_a, reason="left the project")
    with pytest.raises(ProjectGrantRefused, match="already revoked"):
        await repo.revoke(tenant_id=w.tenant_a, grant_id=gid, revoked_by=w.admin_a, reason="again")
    row = (await db.execute(text("SELECT revoked_by, revoke_reason, revoked_at >= granted_at FROM project_review_grants WHERE grant_id = :g"), {"g": gid})).one()
    assert (row[0], row[1], row[2]) == (w.admin_a, "left the project", True)
    event = (await db.execute(text("SELECT payload FROM project_events WHERE event_type = 'hitl.project_grant_revoked' AND payload->>'grant_id' = :g"), {"g": str(gid)})).scalar_one()
    assert event["revoked_by"] == str(w.admin_a) and event["reason"] == "left the project"
    # another tenant's context cannot revoke it (it does not even see it)
    await in_tenant(db, w.tenant_b)
    with pytest.raises(ProjectGrantRefused, match="does not exist or is already revoked"):
        await repo.revoke(tenant_id=w.tenant_b, grant_id=gid, revoked_by=w.admin_b, reason="cross-tenant")
    # history is preserved: the same capability can be granted again, as a NEW row
    await in_tenant(db, w.tenant_a)
    again = await _grant(db, w, user=w.approver_a, project=w.p1, cap=APPROVE)
    assert again != gid and await _count(db, "SELECT count(*) FROM project_review_grants WHERE user_id = :u AND permission = 'APPROVE_CANDIDATE'", u=w.approver_a) == 2
    with pytest.raises(ProjectGrantRefused, match="duplicate key|unique"):  # at most one ACTIVE grant
        await _grant(db, w, user=w.approver_a, project=w.p1, cap=APPROVE)


async def test_the_grant_and_its_audit_event_are_one_atomic_write(db: AsyncSession) -> None:
    w = await build_world(db)
    await in_tenant(db, w.tenant_a)
    await db.execute(text("CREATE FUNCTION prg_test_refuse_event() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'audit sink down'; END $$"))
    await db.execute(text("CREATE TRIGGER prg_test_refuse BEFORE INSERT ON project_events FOR EACH ROW WHEN (NEW.event_type = 'hitl.project_grant_created') EXECUTE FUNCTION prg_test_refuse_event()"))
    await db.commit()
    try:
        await in_tenant(db, w.tenant_a)
        with pytest.raises(ProjectGrantRefused, match="audit sink down"):
            await _grant(db, w, user=w.reviewer_a, project=w.p1, cap=READ)
        assert await _count(db, "SELECT count(*) FROM project_review_grants") == 0, "no audit event, no grant"
    finally:
        await db.rollback()
        await db.execute(text("DROP TRIGGER IF EXISTS prg_test_refuse ON project_events"))
        await db.execute(text("DROP FUNCTION IF EXISTS prg_test_refuse_event()"))
        await db.commit()


# ── concurrency and the transactional gate S5-05 will use ────────────────────────────────────────────────────────
async def test_concurrent_identical_grants_create_exactly_one_active_grant(db: AsyncSession, test_session_factory) -> None:  # type: ignore[no-untyped-def]
    w = await build_world(db)

    async def attempt() -> str:
        async with test_session_factory() as session:
            await in_tenant(session, w.tenant_a)
            try:
                await ProjectReviewGrantRepository(session).grant(
                    tenant_id=w.tenant_a, project_id=w.p1, user_id=w.reviewer_a, capability=REVIEW, granted_by=w.admin_a, reason="race"
                )
                await session.commit()
                return "granted"
            except ProjectGrantRefused as exc:
                await session.rollback()
                return f"refused: {exc}"

    results = await asyncio.gather(*(attempt() for _ in range(4)))
    assert results.count("granted") == 1, results
    assert await _count(db, "SELECT count(*) FROM project_review_grants WHERE revoked_at IS NULL") == 1


async def test_a_revocation_waits_for_the_transaction_that_holds_the_grant_for_share_and_is_then_seen(db: AsyncSession, test_session_factory) -> None:  # type: ignore[no-untyped-def]
    """The gate S5-05 needs: revalidate FOR SHARE inside the committing transaction; a concurrent revocation cannot slip through."""
    w = await build_world(db)
    await in_tenant(db, w.tenant_a)
    gid = await _grant(db, w, user=w.approver_a, project=w.p1, cap=APPROVE)
    await db.commit()

    async with test_session_factory() as committing, test_session_factory() as revoker:
        await in_tenant(committing, w.tenant_a)
        proof = await ProjectReviewAuthorizer(committing).require(tenant_id=w.tenant_a, user_id=w.approver_a, project_id=w.p1, capability=APPROVE, lock=True)
        assert proof.grant_id == gid

        await in_tenant(revoker, w.tenant_a)
        await revoker.execute(text("SET LOCAL lock_timeout = '300ms'"))
        with pytest.raises(ProjectGrantRefused, match="lock timeout|canceling statement"):
            await ProjectReviewGrantRepository(revoker).revoke(tenant_id=w.tenant_a, grant_id=gid, revoked_by=w.admin_a, reason="concurrent")
        await revoker.rollback()

        await committing.commit()  # the committing transaction finishes with the grant still active
        await in_tenant(revoker, w.tenant_a)
        await ProjectReviewGrantRepository(revoker).revoke(tenant_id=w.tenant_a, grant_id=gid, revoked_by=w.admin_a, reason="after the commit")
        await revoker.commit()

    async with test_session_factory() as later:
        await in_tenant(later, w.tenant_a)
        with pytest.raises(ProjectAuthorizationDenied):
            await ProjectReviewAuthorizer(later).revalidate(proof)  # the stale proof no longer holds
        with pytest.raises(ProjectAuthorizationDenied):
            await ProjectReviewAuthorizer(later).require(tenant_id=w.tenant_a, user_id=w.approver_a, project_id=w.p1, capability=APPROVE)


# ── compatibility with the Clerk organization switch ─────────────────────────────────────────────────────────────
async def test_grants_follow_the_user_through_an_organization_switch_without_ever_becoming_grants_of_the_other_tenant(db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    from sqlalchemy import select

    from src.core.auth import dependencies as auth_dependencies
    from src.core.auth.bootstrap_lookup import BootstrapTenantRecord, BootstrapUserRecord
    from src.core.auth.models import Tenant, User

    w = await build_world(db)
    clerk_id = (await db.execute(select(User.clerk_user_id).where(User.id == w.approver_a))).scalar_one()
    org = {w.tenant_a: None, w.tenant_b: None}
    for tid in org:
        org[tid] = (await db.execute(select(Tenant.clerk_org_id).where(Tenant.id == tid))).scalar_one()

    async def tenant_lookup(session: AsyncSession, clerk_org_id: str) -> BootstrapTenantRecord | None:
        row = (await session.execute(select(Tenant).where(Tenant.clerk_org_id == clerk_org_id))).scalar_one_or_none()
        return None if row is None else BootstrapTenantRecord(row.id, row.is_active, row.clerk_org_id, row.name)

    async def user_lookup(session: AsyncSession, clerk_user_id: str) -> BootstrapUserRecord | None:
        row = (await session.execute(select(User).where(User.clerk_user_id == clerk_user_id))).scalar_one_or_none()
        return None if row is None else BootstrapUserRecord(row.id, row.tenant_id, row.email, row.is_active)

    monkeypatch.setattr(auth_dependencies, "lookup_tenant_by_clerk_org_id", tenant_lookup)
    monkeypatch.setattr(auth_dependencies, "lookup_user_by_clerk_user_id", user_lookup)

    await in_tenant(db, w.tenant_a)
    gid = await _grant(db, w, user=w.approver_a, project=w.p1, cap=APPROVE)
    await db.commit()

    async def can(tenant: UUID, project: UUID) -> bool:
        await in_tenant(db, tenant)
        try:
            await ProjectReviewAuthorizer(db).require(tenant_id=tenant, user_id=w.approver_a, project_id=project, capability=APPROVE)
            return True
        except ProjectAuthorizationDenied:
            return False

    async def enter(tenant: UUID) -> None:
        await auth_dependencies._provision_clerk_user(db, clerk_id, org[tenant], "approver@example.invalid", "Ap", "Prover")

    assert await can(w.tenant_a, w.p1) is True
    await enter(w.tenant_b)  # with the grant row present: the switch is NOT blocked by any key
    assert await can(w.tenant_a, w.p1) is False, "while the user is in B the grant of A is dormant"
    assert await can(w.tenant_b, w.p_b) is False and await can(w.tenant_b, w.p1) is False, "and it is never a grant of B"
    await enter(w.tenant_a)
    assert await can(w.tenant_a, w.p1) is True, "back in A it applies again; it was neither lost nor transferred"
    assert await can(w.tenant_a, w.p2) is False
    assert await _count(db, "SELECT count(*) FROM project_review_grants WHERE grant_id = :g AND tenant_id = :t", g=gid, t=w.tenant_a) == 1
