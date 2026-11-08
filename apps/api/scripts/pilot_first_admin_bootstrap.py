"""OPERATOR-ONLY, one-time first-admin bootstrap for the Railway PILOT tenant that has zero active admins.

There is no HTTP grant endpoint and no elevation path: this script is the single, audited, owner-approved exception.
It is NEVER imported by application runtime and has two modes:

* default DRY-RUN: only READs (read-only transaction, always rolled back); prints counts and fingerprints, no email, no
  secret, no Clerk payload; reports ``apply_ready``;
* ``--apply``: one transaction that locks tenant / project / user, re-verifies everything, promotes ONLY the selected
  existing user ``user -> admin``, appends a ``hitl.first_admin_bootstrap`` project event and (only with the separate
  ``--non-independent-self-review-with-reason``) records the audited single-person exception, creates the three grants
  through the EXISTING ``ProjectReviewGrantRepository.grant`` and sets ``enforce``. Any failed pre/post check rolls back.

Fail closed: wrong Railway project/environment, wrong target project, non-operator DB role, tenant that already has an
active admin, user/Clerk mismatch, or Clerk unverifiable => nothing is written. No SQL privilege, RLS, migration or user
creation/move is performed; the grants stay revocable. Secrets are read from the environment only and never printed.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.hitl.adapters.persistence.project_review_grants import (
    ProjectGrantRefused,
    ProjectReviewGrantRepository,
)
from src.modules.hitl.application.project_review_authorization import (
    AuthorizationMode,
    ProjectReviewAuthorizer,
)
from src.modules.hitl.application.project_review_authorization import ProjectCapability as Cap

PILOT_RAILWAY_PROJECT_ID = "44d57536-aca6-4ea0-bc0c-58ce1a5f8eba"
PILOT_RAILWAY_ENVIRONMENT_ID = "60aa9a4c-c231-4bd9-bc87-f76883ea7e0e"
PILOT_PROJECT_ID = UUID("5992eb43-90ef-4d2a-983a-97695e13abfc")
EVENT_TYPE = "hitl.first_admin_bootstrap"
RUNTIME_ROLES = frozenset(
    {"anon", "authenticated", "authenticator", "service_role", "supabase_auth_admin"}
)
CAPABILITIES = (Cap.READ_REVIEW, Cap.REVIEW_FINDING, Cap.APPROVE_CANDIDATE)
CLERK_API = "https://api.clerk.com/v1"
MARKER_PREFIX = "OWNER-APPROVED:"
Fetch = Callable[[str, str], dict[str, Any]]


class BootstrapRefused(RuntimeError):
    """A gate or check failed: nothing was written (fail closed)."""


@dataclass(frozen=True)
class Request:
    tenant_id: UUID
    user_id: UUID
    clerk_user_id: str
    owner_marker: str
    operator_role: str
    apply: bool = False
    self_review_reason: str | None = None


def fp(value: object) -> str:
    return "fp_" + hashlib.sha256(str(value).encode()).hexdigest()[:12]


def check_gates(req: Request, env: dict[str, str] | os._Environ[str]) -> None:
    """Pure CLI-level gates for ``--apply`` (a dry-run needs none: it only reads)."""
    if env.get("RAILWAY_PROJECT_ID") != PILOT_RAILWAY_PROJECT_ID:
        raise BootstrapRefused("GATE_RAILWAY_PROJECT_IS_NOT_THE_PILOT")
    if env.get("RAILWAY_ENVIRONMENT_ID") != PILOT_RAILWAY_ENVIRONMENT_ID:
        raise BootstrapRefused("GATE_RAILWAY_ENVIRONMENT_IS_NOT_THE_PILOT")
    marker = req.owner_marker.strip()
    if not marker.startswith(MARKER_PREFIX) or len(marker) < len(MARKER_PREFIX) + 8:
        raise BootstrapRefused("GATE_OWNER_AUTHORIZATION_MARKER_MISSING_OR_MALFORMED")
    if req.self_review_reason is not None and len(req.self_review_reason.strip()) < 20:
        raise BootstrapRefused("GATE_SELF_REVIEW_REASON_TOO_SHORT")
    if not req.clerk_user_id.startswith("user_"):
        raise BootstrapRefused("GATE_CLERK_USER_ID_MALFORMED")


def _http_get(path: str, secret: str) -> dict[str, Any]:
    request = urllib.request.Request(  # noqa: S310 - fixed https Clerk host
        CLERK_API + path,
        headers={"Authorization": f"Bearer {secret}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
        return json.loads(response.read())


def verify_clerk(
    req: Request, db_email: str, clerk_org_id: str | None, fetch: Fetch | None
) -> dict[str, Any]:
    """Read-only Clerk proof. Returns booleans only: no payload, no email, no secret leaves this function."""
    secret = os.environ.get("CLERK_SECRET_KEY", "")
    if fetch is None and not secret:
        raise BootstrapRefused("CLERK_UNVERIFIABLE_NO_BACKEND_SECRET")
    get = fetch or (lambda path, _s: _http_get(path, secret))
    try:
        user = get(f"/users/{req.clerk_user_id}", secret)
        memberships = (
            get(f"/users/{req.clerk_user_id}/organization_memberships?limit=100", secret)
            if clerk_org_id
            else {}
        )
    except Exception as exc:  # network, HTTP, JSON: the type is not echoed (it may carry the URL)
        raise BootstrapRefused("CLERK_UNVERIFIABLE_API_UNAVAILABLE") from exc
    if user.get("id") != req.clerk_user_id or user.get("banned") or user.get("locked"):
        raise BootstrapRefused("CLERK_USER_NOT_FOUND_OR_NOT_ACTIVE")
    primary = next(
        (
            e
            for e in user.get("email_addresses", [])
            if e.get("id") == user.get("primary_email_address_id")
        ),
        None,
    )
    if primary is None or (primary.get("verification") or {}).get("status") != "verified":
        raise BootstrapRefused("CLERK_PRIMARY_EMAIL_NOT_VERIFIED")
    if str(primary.get("email_address", "")).strip().lower() != db_email.strip().lower():
        raise BootstrapRefused("CLERK_PRIMARY_EMAIL_DOES_NOT_MATCH_DB_USER")
    if clerk_org_id and not any(
        (m.get("organization") or {}).get("id") == clerk_org_id for m in memberships.get("data", [])
    ):
        raise BootstrapRefused("CLERK_USER_NOT_A_MEMBER_OF_THE_TENANT_ORG")
    return {
        "clerk_active": True,
        "email_verified": True,
        "email_matches_db": True,
        "org_member": bool(clerk_org_id) or None,
    }


async def _preflight(session: AsyncSession, req: Request, *, lock: bool) -> dict[str, Any]:
    """Read (and with ``lock`` row-lock, tenant -> project -> user) everything the decision depends on."""
    suffix = " FOR UPDATE" if lock else ""
    role = (
        await session.execute(
            text("SELECT current_user, rolsuper FROM pg_roles WHERE rolname = current_user")
        )
    ).one()
    if role[0] in RUNTIME_ROLES or role[0] != req.operator_role:
        raise BootstrapRefused("DB_ROLE_IS_NOT_THE_DECLARED_OPERATOR_ROLE")
    t = {"t": str(req.tenant_id), "p": str(PILOT_PROJECT_ID), "u": str(req.user_id)}
    tenant = (
        await session.execute(
            text(
                "SELECT clerk_org_id, is_active FROM public.tenants WHERE id = cast(:t as uuid)"
                + suffix
            ),
            t,
        )
    ).first()
    if tenant is None or not tenant[1]:
        raise BootstrapRefused("TENANT_NOT_FOUND_OR_INACTIVE")
    if (
        await session.execute(
            text("SELECT tenant_id FROM public.projects WHERE id = cast(:p as uuid)" + suffix), t
        )
    ).scalar_one_or_none() != req.tenant_id:
        raise BootstrapRefused("TARGET_PROJECT_NOT_FOUND_IN_TENANT")
    user = (
        await session.execute(
            text(
                "SELECT role::text, is_active, clerk_user_id, email FROM public.users WHERE id = cast(:u as uuid) AND tenant_id = cast(:t as uuid)"
                + suffix
            ),
            t,
        )
    ).first()
    if user is None or not user[1]:
        raise BootstrapRefused("USER_NOT_AN_ACTIVE_MEMBER_OF_THE_TENANT")
    if user[2] != req.clerk_user_id:
        raise BootstrapRefused("DB_CLERK_USER_ID_DOES_NOT_MATCH_PROVIDER_SUBJECT")
    if str(user[0]).lower() != "user":
        raise BootstrapRefused("USER_ROLE_IS_NOT_USER_ONLY_USER_TO_ADMIN_IS_ALLOWED")
    admins = (
        await session.execute(
            text(
                "SELECT count(*) FROM public.users WHERE tenant_id = cast(:t as uuid) AND is_active AND role::text = 'admin'"
            ),
            t,
        )
    ).scalar_one()
    if admins != 0:
        raise BootstrapRefused("TENANT_ALREADY_HAS_AN_ACTIVE_ADMIN_ONE_TIME_ONLY")
    counts = (
        await session.execute(
            text(
                "SELECT (SELECT count(*) FROM public.users WHERE tenant_id = cast(:t as uuid) AND is_active),"
                " (SELECT count(*) FROM public.project_review_grants WHERE tenant_id = cast(:t as uuid) AND revoked_at IS NULL)"
            ),
            t,
        )
    ).one()
    return {
        "active_admins": admins,
        "active_users": counts[0],
        "active_grants": counts[1],
        "operator_role_superuser": bool(role[1]),
        "clerk_org_id": tenant[0],
        "db_email": user[3],
    }


def _report(
    req: Request, facts: dict[str, Any], clerk: dict[str, Any] | None, **extra: Any
) -> dict[str, Any]:
    return {
        "mode": "APPLY" if req.apply else "DRY_RUN",
        "tenant_fp": fp(req.tenant_id),
        "user_fp": fp(req.user_id),
        "clerk_user_fp": fp(req.clerk_user_id),
        "operator_fp": fp(req.operator_role),
        "project_fp": fp(PILOT_PROJECT_ID),
        "active_admins": facts["active_admins"],
        "active_users": facts["active_users"],
        "active_grants": facts["active_grants"],
        "clerk": clerk or "UNVERIFIED",
        "self_review": req.self_review_reason is not None,
        **extra,
    }


async def execute(
    session: AsyncSession,
    req: Request,
    *,
    env: dict[str, str] | os._Environ[str] = os.environ,
    clerk_fetch: Fetch | None = None,
) -> dict[str, Any]:
    """Dry-run: read-only + rolled back by the caller. Apply: the caller commits ONLY if this returns."""
    if req.apply:
        check_gates(req, env)
    await session.execute(text("SET TRANSACTION " + ("READ WRITE" if req.apply else "READ ONLY")))
    facts = await _preflight(session, req, lock=req.apply)
    try:
        clerk: dict[str, Any] | None = verify_clerk(
            req, facts["db_email"], facts["clerk_org_id"], clerk_fetch
        )
    except BootstrapRefused:
        if req.apply:
            raise
        clerk = None  # dry-run reports it; it can never be apply_ready without the proof
    if not req.apply:
        return _report(req, facts, clerk, apply_ready=clerk is not None)

    t, u, p = req.tenant_id, req.user_id, PILOT_PROJECT_ID
    await session.execute(text("SELECT set_config('app.current_tenant', :t, true)"), {"t": str(t)})
    promoted = (
        await session.execute(
            text(
                "UPDATE public.users SET role = 'admin' WHERE id = cast(:u as uuid) AND tenant_id = cast(:t as uuid) "
                "AND is_active AND role::text = 'user' AND clerk_user_id = :c"
            ),
            {"u": str(u), "t": str(t), "c": req.clerk_user_id},
        )
    ).rowcount
    if promoted != 1:
        raise BootstrapRefused("PROMOTION_AFFECTED_UNEXPECTED_ROW_COUNT")
    payload = {
        "operator_fp": fp(req.operator_role),
        "user_fp": fp(u),
        "clerk_user_fp": fp(req.clerk_user_id),
        "owner_marker_fp": fp(req.owner_marker.strip()),
        "previous_role": "user",
        "new_role": "admin",
        "self_review": req.self_review_reason is not None,
        "railway_project_id": PILOT_RAILWAY_PROJECT_ID,
        "railway_environment_id": PILOT_RAILWAY_ENVIRONMENT_ID,
    }
    await session.execute(
        text(
            "INSERT INTO public.project_events (event_id, project_id, tenant_id, event_type, payload, actor, evidence_refs, occurred_at, created_at) "
            "VALUES (cast(:e as uuid), cast(:p as uuid), cast(:t as uuid), :type, cast(:pl as jsonb), :a, "
            "'[]'::jsonb, now() AT TIME ZONE 'utc', now() AT TIME ZONE 'utc')"
        ),
        {
            "e": str(uuid4()),
            "p": str(p),
            "t": str(t),
            "type": EVENT_TYPE,
            "pl": json.dumps(payload),
            "a": f"operator:{fp(req.operator_role)}",
        },
    )

    grants: dict[str, str] = {}
    if req.self_review_reason is not None:
        reason = req.self_review_reason.strip()
        exception = {
            "enabled": True,
            "reason": reason,
            "granted_by": f"first-admin-bootstrap:{fp(req.operator_role)}",
            "granted_at": datetime.now(UTC).isoformat(),
        }
        await session.execute(
            text(
                "UPDATE public.tenants SET settings = jsonb_set(coalesce(settings, '{}'::jsonb), "
                "'{hitl_project_authorization,single_person_exception}', cast(:v as jsonb), true) WHERE id = cast(:t as uuid)"
            ),
            {"t": str(t), "v": json.dumps(exception)},
        )
        repository = ProjectReviewGrantRepository(session)
        try:
            for capability in CAPABILITIES:
                grants[capability.value] = str(
                    await repository.grant(
                        tenant_id=t,
                        project_id=p,
                        user_id=u,
                        capability=capability,
                        granted_by=u,
                        reason=f"first-admin bootstrap: {capability.value}",
                        exception_reason=reason,
                    )
                )
        except ProjectGrantRefused as exc:
            raise BootstrapRefused(f"DATABASE_REFUSED_THE_GRANT: {exc}") from exc
        await session.execute(
            text(
                "UPDATE public.tenants SET settings = jsonb_set(coalesce(settings, '{}'::jsonb), "
                "'{hitl_project_authorization,mode}', '\"enforce\"', true) WHERE id = cast(:t as uuid)"
            ),
            {"t": str(t)},
        )

    after = await _preflight_post(session, req, grants)
    return _report(req, facts, clerk, applied=True, grants=sorted(grants), post=after)


async def _preflight_post(
    session: AsyncSession, req: Request, grants: dict[str, str]
) -> dict[str, Any]:
    t = {"t": str(req.tenant_id), "u": str(req.user_id)}
    admins = (
        await session.execute(
            text(
                "SELECT array_agg(id) FROM public.users WHERE tenant_id = cast(:t as uuid) AND is_active AND role::text = 'admin'"
            ),
            t,
        )
    ).scalar_one()
    event = (
        await session.execute(
            text(
                "SELECT count(*) FROM public.project_events WHERE tenant_id = cast(:t as uuid) AND event_type = :e"
            ),
            {**t, "e": EVENT_TYPE},
        )
    ).scalar_one()
    if admins != [req.user_id] or event < 1:
        raise BootstrapRefused("POSTCHECK_FAILED_ADMIN_SET_OR_AUDIT_EVENT")
    post: dict[str, Any] = {"admins": 1, "audit_event": True}
    if grants:
        caps = await ProjectReviewAuthorizer(session).capabilities(
            tenant_id=req.tenant_id, user_id=req.user_id, project_id=PILOT_PROJECT_ID
        )
        if caps.mode is not AuthorizationMode.ENFORCE or not (
            caps.read_review and caps.review_finding and caps.approve_candidate
        ):
            raise BootstrapRefused("POSTCHECK_FAILED_CAPABILITIES_OR_ENFORCE")
        post.update(mode="enforce", capabilities=3)
    return post


async def _main(args: argparse.Namespace) -> dict[str, Any]:
    from sqlalchemy.ext.asyncio import create_async_engine

    url = os.environ.get(
        "PILOT_OPERATOR_DATABASE_URL"
    )  # deliberately NOT DATABASE_URL (the runtime's)
    if not url:
        raise BootstrapRefused("PILOT_OPERATOR_DATABASE_URL_NOT_SET")
    req = Request(
        args.tenant_id,
        args.user_id,
        args.clerk_user_id,
        args.owner_authorization_marker,
        args.operator_role,
        args.apply,
        args.non_independent_self_review_with_reason,
    )
    engine = create_async_engine(url)
    try:
        async with AsyncSession(engine) as session:
            try:
                report = await execute(session, req)
            except BaseException:
                await session.rollback()
                raise
            await (session.commit() if req.apply else session.rollback())
            return report
    finally:
        await engine.dispose()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--tenant-id", type=UUID, required=True)
    parser.add_argument("--user-id", type=UUID, required=True)
    parser.add_argument("--clerk-user-id", required=True)
    parser.add_argument(
        "--owner-authorization-marker",
        required=True,
        help=f"{MARKER_PREFIX}<token> from the owner approval",
    )
    parser.add_argument(
        "--operator-role", required=True, help="must equal current_user of the operator connection"
    )
    parser.add_argument(
        "--apply", action="store_true", help="WRITE; default is a read-only dry-run"
    )
    parser.add_argument("--non-independent-self-review-with-reason", metavar="REASON", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        report = asyncio.run(_main(build_parser().parse_args(argv)))
    except BootstrapRefused as exc:
        print(json.dumps({"refused": str(exc), "written": False}))
        return 2
    print(json.dumps(report, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
