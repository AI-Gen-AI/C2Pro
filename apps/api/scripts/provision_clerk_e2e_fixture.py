#!/usr/bin/env python
"""Idempotently provision the dedicated Clerk E2E Organization fixture.

TS-E2E-P0B-FIXTURE-001.

WHY THIS EXISTS
---------------
The P0b acceptance gate proved that the configured E2E Clerk identity has
``membershipCount = 0``. That is not a product defect, it is an incomplete test
fixture: C2Pro derives frontend tenant identity from
``organization.publicMetadata.tenant_id`` (``lib/clerk-tenant.ts``), and
``AuthSync`` auto-activates an Organization only when the user has exactly one
membership. A Clerk-signed-in user with no Organization therefore cannot
represent the normal tenant-authenticated journey, and no amount of product-auth
change should be used to paper over that.

So this script makes the fixture satisfy the real product contract, rather than
weakening the contract to fit the fixture.

SAFETY
------
Every ambiguity FAILS CLOSED. In particular the script refuses to run at all
unless the Clerk credentials are positively identified as a
development/test instance, using the same rule ``@clerk/shared`` applies
(``live_`` / ``sk_live_`` / ``pk_live_`` prefixes mean production). An
unrecognised prefix stops the run — "not provably production" is not good
enough to authorise a mutation.

It also stops rather than guessing when:
  * the E2E email resolves to zero or several Clerk users;
  * several Organizations match the dedicated E2E slug;
  * a matching Organization already carries a DIFFERENT tenant_id;
  * the E2E identity would end up in more than one Organization (which would
    silently disable AuthSync's auto-activation).

No secret is ever printed. The Organization id is written to ``$GITHUB_ENV``
because the database seed needs it, but is never echoed to stdout.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

import httpx

CLERK_API_BASE = "https://api.clerk.com/v1"

# Repository truth: the deterministic E2E tenant already used by
# apps/api/tests/e2e_seed/seed_wedge.py and apps/api/tests/conftest.py.
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-00000000a113"
DEFAULT_E2E_EMAIL = "testuser@c2pro.com"
DEFAULT_ORG_SLUG = "c2pro-e2e"
DEFAULT_ORG_NAME = "C2Pro E2E"

# @clerk/shared/keys: a key is production when it carries one of these prefixes.
_PRODUCTION_PREFIXES = ("live_", "sk_live_", "pk_live_")
# Positive development identification. Anything else fails closed.
_DEVELOPMENT_SECRET_PREFIXES = ("sk_test_", "test_")


class FixtureError(RuntimeError):
    """A fixture guarantee could not be established safely."""


# ---------------------------------------------------------------------------
# Environment safety
# ---------------------------------------------------------------------------


def require_development_instance(secret_key: str, publishable_key: str | None) -> str:
    """Return the proven environment label, or raise.

    Positive identification only: an unrecognised prefix is treated as unsafe,
    because this function is the sole gate in front of an external mutation.
    """
    if any(secret_key.startswith(prefix) for prefix in _PRODUCTION_PREFIXES):
        raise FixtureError(
            "CLERK_SECRET_KEY is a PRODUCTION key. Refusing to mutate a production "
            "Clerk instance under any circumstances."
        )
    if publishable_key and any(publishable_key.startswith(p) for p in _PRODUCTION_PREFIXES):
        raise FixtureError(
            "The Clerk publishable key is a PRODUCTION key. Refusing to mutate."
        )
    if not any(secret_key.startswith(prefix) for prefix in _DEVELOPMENT_SECRET_PREFIXES):
        raise FixtureError(
            "CLERK_SECRET_KEY could not be positively identified as a development/test "
            "key. Refusing to mutate an instance whose environment is not proven."
        )
    return "DEVELOPMENT/TEST"


# ---------------------------------------------------------------------------
# Clerk Backend API (paths mirror @clerk/backend 3.11.4 OrganizationApi/UserApi)
# ---------------------------------------------------------------------------


def _unwrap(payload: Any) -> list[dict[str, Any]]:
    """Clerk list endpoints return either a bare list or {data, total_count}."""
    if isinstance(payload, dict):
        data = payload.get("data", [])
        return list(data) if isinstance(data, list) else []
    return list(payload) if isinstance(payload, list) else []


class ClerkAdmin:
    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def _call(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self._client.request(method, f"{CLERK_API_BASE}{path}", **kwargs)
        if response.status_code >= 400:
            # Clerk error bodies carry no secret material, only rule messages.
            raise FixtureError(
                f"Clerk API {method} {path} failed with {response.status_code}: {response.text}"
            )
        return response.json()

    def get_organization(self, org_id: str) -> dict[str, Any]:
        return dict(self._call("GET", f"/organizations/{org_id}"))

    def users_by_email(self, email: str) -> list[dict[str, Any]]:
        return _unwrap(self._call("GET", "/users", params={"email_address": [email]}))

    def organizations_by_query(self, query: str) -> list[dict[str, Any]]:
        return _unwrap(self._call("GET", "/organizations", params={"query": query, "limit": 100}))

    def create_organization(
        self, *, name: str, slug: str, created_by: str, tenant_id: str
    ) -> dict[str, Any]:
        return dict(
            self._call(
                "POST",
                "/organizations",
                json={
                    "name": name,
                    "slug": slug,
                    "created_by": created_by,
                    "public_metadata": {"tenant_id": tenant_id},
                },
            )
        )

    def merge_organization_metadata(self, org_id: str, tenant_id: str) -> dict[str, Any]:
        return dict(
            self._call(
                "PATCH",
                f"/organizations/{org_id}/metadata",
                json={"public_metadata": {"tenant_id": tenant_id}},
            )
        )

    def organization_memberships(self, org_id: str) -> list[dict[str, Any]]:
        return _unwrap(self._call("GET", f"/organizations/{org_id}/memberships", params={"limit": 100}))

    def create_organization_membership(self, org_id: str, user_id: str, role: str) -> dict[str, Any]:
        return dict(
            self._call(
                "POST",
                f"/organizations/{org_id}/memberships",
                json={"user_id": user_id, "role": role},
            )
        )

    def user_memberships(self, user_id: str) -> list[dict[str, Any]]:
        return _unwrap(
            self._call("GET", f"/users/{user_id}/organization_memberships", params={"limit": 100})
        )


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------


def resolve_user(admin: ClerkAdmin, email: str) -> str:
    users = admin.users_by_email(email)
    if len(users) != 1:
        raise FixtureError(
            f"The configured E2E email must resolve to exactly one Clerk user; found {len(users)}. "
            "Refusing to guess which identity the harness means."
        )
    user_id = users[0].get("id")
    if not isinstance(user_id, str) or not user_id:
        raise FixtureError("Clerk returned a user without an id.")
    return user_id


def resolve_organization(
    admin: ClerkAdmin, slug: str
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Return the single Organization matching the dedicated slug, if any."""
    candidates = admin.organizations_by_query(slug)
    exact = [org for org in candidates if org.get("slug") == slug]
    if len(exact) > 1:
        raise FixtureError(
            f"{len(exact)} Organizations share the dedicated E2E slug '{slug}'. "
            "Refusing to pick one; resolve the ambiguity in Clerk first."
        )
    return (exact[0] if exact else None), candidates


def ensure_tenant_metadata(admin: ClerkAdmin, org: dict[str, Any], tenant_id: str) -> bool:
    """Return True when metadata had to be written. Conflicts fail closed."""
    metadata = org.get("public_metadata") or {}
    existing = metadata.get("tenant_id")
    if existing == tenant_id:
        return False
    if isinstance(existing, str) and existing:
        raise FixtureError(
            "The dedicated E2E Organization already points at a DIFFERENT tenant_id. "
            "Refusing to repoint an Organization that belongs to another tenant."
        )
    org_id = str(org["id"])
    admin.merge_organization_metadata(org_id, tenant_id)
    return True


def ensure_membership(admin: ClerkAdmin, org_id: str, user_id: str, role: str) -> bool:
    """Return True when the membership had to be created."""
    members = admin.organization_memberships(org_id)
    for membership in members:
        if (membership.get("public_user_data") or {}).get("user_id") == user_id:
            return False
    admin.create_organization_membership(org_id, user_id, role)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", default=os.getenv("E2E_CLERK_USER_EMAIL", DEFAULT_E2E_EMAIL))
    parser.add_argument("--slug", default=os.getenv("E2E_CLERK_ORG_SLUG", DEFAULT_ORG_SLUG))
    parser.add_argument("--name", default=DEFAULT_ORG_NAME)
    parser.add_argument("--tenant-id", default=os.getenv("E2E_TENANT_ID", DEFAULT_TENANT_ID))
    parser.add_argument("--role", default="org:admin")
    parser.add_argument(
        "--github-env",
        default=os.getenv("GITHUB_ENV"),
        help="File to append CLERK_E2E_* exports to (GitHub Actions env file).",
    )
    args = parser.parse_args()

    secret_key = os.getenv("CLERK_SECRET_KEY", "")
    if not secret_key:
        print("FAIL: CLERK_SECRET_KEY is required to reconcile the E2E fixture.", file=sys.stderr)
        return 2

    publishable_key = os.getenv("CLERK_PUBLISHABLE_KEY") or os.getenv(
        "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY"
    )

    try:
        environment = require_development_instance(secret_key, publishable_key)
        print(f"clerk_environment = {environment}")

        with httpx.Client(
            timeout=30.0, headers={"Authorization": f"Bearer {secret_key}"}
        ) as client:
            admin = ClerkAdmin(client)

            user_id = resolve_user(admin, args.email)
            print("e2e_user_resolved = true")

            org, candidates = resolve_organization(admin, args.slug)
            if org is None:
                org = admin.create_organization(
                    name=args.name,
                    slug=args.slug,
                    created_by=user_id,
                    tenant_id=args.tenant_id,
                )
                print("organization = CREATED")
                print(f"organization_candidates_seen = {len(candidates)}")
            else:
                print("organization = EXISTED")

            org_id = str(org["id"])
            metadata_written = ensure_tenant_metadata(admin, org, args.tenant_id)
            print(f"organization_tenant_metadata = {'WRITTEN' if metadata_written else 'ALREADY_CORRECT'}")

            membership_created = ensure_membership(admin, org_id, user_id, args.role)
            print(f"membership = {'CREATED' if membership_created else 'EXISTED'}")

            memberships = admin.user_memberships(user_id)
            print(f"e2e_user_membership_count = {len(memberships)}")
            if len(memberships) != 1:
                raise FixtureError(
                    f"The E2E identity holds {len(memberships)} Organization memberships. "
                    "AuthSync auto-activates an Organization only at exactly one membership, "
                    "so any other count leaves the tenant context unresolved."
                )

            member_org_id = str((memberships[0].get("organization") or {}).get("id", ""))
            if member_org_id != org_id:
                raise FixtureError(
                    "The E2E identity's only membership is NOT the dedicated E2E Organization."
                )

            # Re-read so the reported metadata is the server's state, not ours.
            confirmed = admin.get_organization(org_id)
            confirmed_tenant = (confirmed.get("public_metadata") or {}).get("tenant_id")
            print(f"organization_tenant_id_matches = {confirmed_tenant == args.tenant_id}")
            if confirmed_tenant != args.tenant_id:
                raise FixtureError("Organization publicMetadata.tenant_id did not persist.")

            # The Organization id is an identifier, not a secret, but it is only
            # exported for the database seed -- never echoed to the build log.
            if args.github_env:
                with Path(args.github_env).open("a", encoding="utf-8") as handle:
                    handle.write(f"CLERK_E2E_ORG_ID={org_id}\n")
                    handle.write(f"E2E_CLERK_ORGANIZATION_ID={org_id}\n")
                    handle.write(f"CLERK_E2E_USER_ID={user_id}\n")
                    handle.write(f"E2E_EXPECTED_TENANT_ID={args.tenant_id}\n")
                print("exports_written = true")

    except FixtureError as exc:
        print(f"FAIL (fixture not provisioned, nothing left half-applied): {exc}", file=sys.stderr)
        return 1

    print("\nPASS: the dedicated Clerk E2E Organization fixture is aligned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
