"""S5-02: create / list / revoke explicit per-project review grants (READ_REVIEW, REVIEW_FINDING, APPROVE_CANDIDATE).

DRY-RUN BY DEFAULT: without ``--apply`` it validates the request and PRINTS what it would do; nothing is written.

``--apply`` is allowed ONLY against an isolated, local test PostgreSQL (``ENVIRONMENT=test`` AND a loopback database
host AND ``--confirm-isolated-test-database``). Real grants on a real tenant need a separate, per-environment approval
and a different channel: this script refuses them. It never creates a Clerk identity, never reads the Clerk membership
and never derives a grant from a role: the grantor is an explicit ADMIN of the tenant (the database re-checks it, writes
the grant and its audit event atomically, and refuses ordinary self-grants).

    python -m scripts.grant_project_review_permissions grant --tenant T --project P --user U \
        --capability REVIEW_FINDING --granted-by ADMIN --reason "why"            # dry-run
    ... --apply --confirm-isolated-test-database                                  # isolated test DB only
    python -m scripts.grant_project_review_permissions revoke --tenant T --grant G --revoked-by ADMIN --reason "why"
    python -m scripts.grant_project_review_permissions list --tenant T [--project P]
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Sequence
from urllib.parse import urlparse
from uuid import UUID

from src.modules.hitl.application.project_review_authorization import ProjectCapability

_LOOPBACK = {"localhost", "127.0.0.1", "::1"}


class GrantScriptError(RuntimeError):
    """The request is refused before any database is touched."""


def database_host(env: dict[str, str] | os._Environ[str] = os.environ) -> str:
    url = env.get("DATABASE_URL", "")
    return (urlparse(url.replace("+asyncpg", "")).hostname or "").lower()


def require_isolated_test_database(
    *, confirmed: bool, env: dict[str, str] | os._Environ[str] = os.environ
) -> None:
    """The ONLY condition under which ``--apply`` may write. Pure, so it is unit-tested."""
    if not confirmed:
        raise GrantScriptError("APPLY_REQUIRES_--confirm-isolated-test-database")
    if env.get("ENVIRONMENT", "").lower() != "test":
        raise GrantScriptError("APPLY_REQUIRES_ENVIRONMENT_TEST")
    if database_host(env) not in _LOOPBACK:
        raise GrantScriptError(
            "APPLY_REFUSES_NON_LOOPBACK_DATABASE: real grants need a separate per-environment approval"
        )


def _uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"not a UUID: {value}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--tenant", type=_uuid, required=True)
        p.add_argument(
            "--apply",
            action="store_true",
            help="write (isolated test database only); default is a dry-run",
        )
        p.add_argument("--confirm-isolated-test-database", action="store_true")

    grant = sub.add_parser("grant")
    common(grant)
    grant.add_argument("--project", type=_uuid, required=True)
    grant.add_argument("--user", type=_uuid, required=True)
    grant.add_argument("--capability", choices=[c.value for c in ProjectCapability], required=True)
    grant.add_argument("--granted-by", type=_uuid, required=True)
    grant.add_argument("--reason", required=True)
    grant.add_argument(
        "--self-grant-exception-reason",
        help="only for a tenant with an enabled single_person_exception: an audited, limited, non-independent self-grant",
    )

    revoke = sub.add_parser("revoke")
    common(revoke)
    revoke.add_argument("--grant", type=_uuid, required=True)
    revoke.add_argument("--revoked-by", type=_uuid, required=True)
    revoke.add_argument("--reason", required=True)

    listing = sub.add_parser("list")
    listing.add_argument("--tenant", type=_uuid, required=True)
    listing.add_argument("--project", type=_uuid)
    return parser


def describe(args: argparse.Namespace) -> str:
    if args.command == "grant":
        extra = (
            " [SELF-GRANT EXCEPTION, non-independent]" if args.self_grant_exception_reason else ""
        )
        return (
            f"GRANT {args.capability} on project {args.project} to user {args.user} "
            f"(tenant {args.tenant}, by {args.granted_by}){extra}: {args.reason}"
        )
    if args.command == "revoke":
        return (
            f"REVOKE grant {args.grant} (tenant {args.tenant}, by {args.revoked_by}): {args.reason}"
        )
    return f"LIST active grants of tenant {args.tenant}" + (
        f" project {args.project}" if args.project else ""
    )


async def _run(args: argparse.Namespace) -> int:
    from src.core.database import close_db, get_raw_session, init_db
    from src.modules.hitl.adapters.persistence.project_review_grants import (
        ProjectGrantRefused,
        ProjectReviewGrantRepository,
    )

    await init_db()
    try:
        async with get_raw_session() as session:
            repository = ProjectReviewGrantRepository(session)
            if args.command == "list":
                for grant in await repository.list_active(
                    tenant_id=args.tenant, project_id=args.project
                ):
                    print(
                        f"{grant.grant_id} {grant.capability.value} project={grant.project_id} user={grant.user_id}"
                    )
                return 0
            try:
                if args.command == "grant":
                    grant_id = await repository.grant(
                        tenant_id=args.tenant,
                        project_id=args.project,
                        user_id=args.user,
                        capability=ProjectCapability(args.capability),
                        granted_by=args.granted_by,
                        reason=args.reason,
                        exception_reason=args.self_grant_exception_reason,
                    )
                    print(f"GRANTED {grant_id}")
                else:
                    await repository.revoke(
                        tenant_id=args.tenant,
                        grant_id=args.grant,
                        revoked_by=args.revoked_by,
                        reason=args.reason,
                    )
                    print(f"REVOKED {args.grant}")
            except ProjectGrantRefused as exc:
                await session.rollback()
                print(f"REFUSED by the database: {exc}", file=sys.stderr)
                return 2
            await session.commit()
        return 0
    finally:
        await close_db()


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(describe(args))
    if args.command == "list":
        return asyncio.run(_run(args))
    if not args.apply:
        print("DRY-RUN: nothing was written (pass --apply on an isolated test database to write).")
        return 0
    try:
        require_isolated_test_database(confirmed=args.confirm_isolated_test_database)
    except GrantScriptError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 3
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
