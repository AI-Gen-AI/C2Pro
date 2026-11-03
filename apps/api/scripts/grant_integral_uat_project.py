"""Nonproduction ONLY (S5, owner decision D1): the explicit grants step of the integral UAT, AFTER its project exists.

The seed cannot grant anything because the journey creates its project later. This step runs once the project (and the
Clerk Development identities A/B, which are NEVER created here) exist, on the ISOLATED test database of the run:

1. fail closed unless ``ENVIRONMENT=test`` and the database is a loopback one (the same gate as the grant script);
2. the project must belong to tenant A, and the grantee must be an ACTIVE ADMIN/USER row of tenant A that already exists
   (its Clerk identity is untouched); a missing project or user is a refusal, never an implicit creation;
3. the three capabilities (READ_REVIEW, REVIEW_FINDING, APPROVE_CANDIDATE) are granted through the GOVERNED function
   ``project_review_grant_create`` (actor, reason, audit event written atomically with the grant);
   * with ``--grantor`` an independent ADMIN of the tenant grants (the normal path, no exception);
   * without it the tenant has ONE human, so the only way is the documented, limited, audited single-person exception:
     tenant A only, written with reason / granted_by / granted_at, and every resulting grant is a
     SELF_GRANTED_NOT_INDEPENDENT one (``self_grant_exception = true``). No grantor is invented;
4. ``enforce`` is switched ON for tenant A (the project under test) and for tenant B (the isolation target) BEFORE any
   HITL operation the run intends to qualify.

It never touches a tenant other than the two seeded synthetic ones, Production, Clerk or any secret. It prints one JSON
report on its last line.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.hitl.adapters.persistence.project_review_grants import (
    ProjectGrantRefused,
    ProjectReviewGrantRepository,
)
from src.modules.hitl.application.project_review_authorization import ProjectCapability

SETTINGS_KEY = "hitl_project_authorization"
EXCEPTION_REASON = (
    "Synthetic integral-UAT tenant A has exactly one human: the explicit project grants can only be created by that "
    "same person. Nonproduction, limited to this tenant, recorded as SELF_GRANTED_NOT_INDEPENDENT."
)
EXCEPTION_GRANTED_BY = "grant_integral_uat_project (nonproduction, synthetic tenant A only)"
ALL_CAPABILITIES: tuple[ProjectCapability, ...] = (
    ProjectCapability.READ_REVIEW,
    ProjectCapability.REVIEW_FINDING,
    ProjectCapability.APPROVE_CANDIDATE,
)


class GrantStepRefused(RuntimeError):
    """A precondition is missing: nothing was written (fail closed)."""


def require_isolated_environment(env: dict[str, str] | os._Environ[str] = os.environ) -> None:
    from scripts.grant_project_review_permissions import (
        GrantScriptError,
        require_isolated_test_database,
    )

    try:
        require_isolated_test_database(confirmed=True, env=env)
    except GrantScriptError as exc:
        raise GrantStepRefused(f"GRANT_STEP_REQUIRES_ISOLATED_TEST_DATABASE: {exc}") from exc


async def _scalar(session: AsyncSession, sql: str, **params: Any) -> Any:
    return (await session.execute(text(sql), {k: str(v) for k, v in params.items()})).scalar_one_or_none()


async def _set_mode(session: AsyncSession, tenant_id: UUID, extra: dict[str, Any] | None = None) -> None:
    """Switch ``settings.hitl_project_authorization`` to enforce (non-transitional), keeping other settings intact."""
    marker: dict[str, Any] = {"mode": "enforce"}
    marker.update(extra or {})
    await session.execute(
        text(
            "UPDATE public.tenants SET settings = jsonb_set(coalesce(settings, '{}'::jsonb), "
            "'{hitl_project_authorization}', coalesce(settings #> '{hitl_project_authorization}', '{}'::jsonb) "
            "|| cast(:marker as jsonb), true) WHERE id = cast(:t as uuid)"
        ),
        {"t": str(tenant_id), "marker": json.dumps(marker)},
    )
    # `transitional` / `reason` belong to the off marker only
    await session.execute(
        text(
            "UPDATE public.tenants SET settings = settings #- '{hitl_project_authorization,transitional}' "
            "#- '{hitl_project_authorization,reason}' WHERE id = cast(:t as uuid)"
        ),
        {"t": str(tenant_id)},
    )


async def establish_project_authority(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    project_id: UUID,
    grantee_user_id: UUID,
    grantor_user_id: UUID | None = None,
    enforce_also: Sequence[UUID] = (),
    now: datetime | None = None,
) -> dict[str, Any]:
    """Grant the three capabilities on ``project_id`` to ``grantee_user_id`` and switch the tenants to enforce.

    Does not commit: the caller owns the transaction. Raises ``GrantStepRefused`` with nothing written on any missing
    precondition (project not of this tenant, grantee/grantor missing or inactive, wrong role, DB refusal).
    """
    project_tenant = await _scalar(
        session, "SELECT tenant_id FROM public.projects WHERE id = cast(:p as uuid)", p=project_id
    )
    if project_tenant is None or UUID(str(project_tenant)) != tenant_id:
        raise GrantStepRefused("GRANT_STEP_PROJECT_NOT_FOUND_IN_TENANT")

    async def member(user_id: UUID, *, admin: bool) -> None:
        row = (
            await session.execute(
                text("SELECT role::text, is_active FROM public.users WHERE id = cast(:u as uuid) AND tenant_id = cast(:t as uuid)"),
                {"u": str(user_id), "t": str(tenant_id)},
            )
        ).first()
        if row is None or not row[1]:
            raise GrantStepRefused(f"GRANT_STEP_USER_NOT_AN_ACTIVE_MEMBER: {user_id}")
        if admin and str(row[0]).lower() != "admin":
            raise GrantStepRefused(f"GRANT_STEP_GRANTOR_IS_NOT_AN_ADMIN: {user_id}")
        if not admin and str(row[0]).lower() not in {"admin", "user"}:
            raise GrantStepRefused(f"GRANT_STEP_GRANTEE_IS_NOT_A_HUMAN_MEMBER: {user_id}")

    await member(grantee_user_id, admin=False)
    self_grant = grantor_user_id is None or grantor_user_id == grantee_user_id
    actor = grantee_user_id if grantor_user_id is None else grantor_user_id
    await member(actor, admin=True)

    stamp = (now or datetime.now(UTC)).isoformat()
    if self_grant:
        await session.execute(
            text(
                "UPDATE public.tenants SET settings = jsonb_set(coalesce(settings, '{}'::jsonb), "
                "'{hitl_project_authorization,single_person_exception}', cast(:v as jsonb), true) WHERE id = cast(:t as uuid)"
            ),
            {
                "t": str(tenant_id),
                "v": json.dumps({"enabled": True, "reason": EXCEPTION_REASON, "granted_by": EXCEPTION_GRANTED_BY, "granted_at": stamp}),
            },
        )

    repository = ProjectReviewGrantRepository(session)
    already = {
        grant.capability: grant.grant_id
        for grant in await repository.list_active(tenant_id=tenant_id, project_id=project_id)
        if grant.user_id == grantee_user_id
    }
    granted: dict[str, str] = {}
    try:
        for capability in ALL_CAPABILITIES:
            if capability in already:
                granted[capability.value] = str(already[capability])
                continue
            grant_id = await repository.grant(
                tenant_id=tenant_id,
                project_id=project_id,
                user_id=grantee_user_id,
                capability=capability,
                granted_by=actor,
                reason=f"integral UAT: explicit {capability.value} on the synthetic project",
                exception_reason=EXCEPTION_REASON if self_grant else None,
            )
            granted[capability.value] = str(grant_id)
    except ProjectGrantRefused as exc:
        raise GrantStepRefused(f"GRANT_STEP_DATABASE_REFUSED_THE_GRANT: {exc}") from exc

    for tenant in (tenant_id, *enforce_also):
        await _set_mode(session, tenant)

    return {
        "tenant_id": str(tenant_id),
        "project_id": str(project_id),
        "grantee_user_id": str(grantee_user_id),
        "grantor_user_id": str(actor),
        "grants": granted,
        "grant_kind": "SELF_GRANTED_NOT_INDEPENDENT" if self_grant else "INDEPENDENT_ADMIN_GRANT",
        "enforced_tenants": [str(t) for t in (tenant_id, *enforce_also)],
    }


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    from scripts.seed_integral_uat import TENANT_B_ID
    from src.core.database import close_db, get_raw_session, init_db
    from tests.e2e_seed.seed_wedge import TENANT_ID, USER_ID

    tenant_id = args.tenant or TENANT_ID
    if tenant_id != TENANT_ID:
        raise GrantStepRefused("GRANT_STEP_ONLY_THE_SYNTHETIC_TENANT_A")
    await init_db()
    try:
        async with get_raw_session() as session:
            report = await establish_project_authority(
                session,
                tenant_id=tenant_id,
                project_id=args.project,
                grantee_user_id=args.grantee or USER_ID,
                grantor_user_id=args.grantor,
                enforce_also=(TENANT_B_ID,),
            )
            await session.commit()
        return report
    finally:
        await close_db()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("project", type=UUID, help="the project created by the journey (must belong to tenant A)")
    parser.add_argument("--tenant", type=UUID, default=None, help="defaults to the synthetic tenant A")
    parser.add_argument("--grantee", type=UUID, default=None, help="defaults to the seeded user A")
    parser.add_argument("--grantor", type=UUID, default=None, help="an independent ADMIN of the tenant; omit for the exception")
    args = parser.parse_args(argv)
    try:
        require_isolated_environment()
        report = asyncio.run(_run(args))
    except GrantStepRefused as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
