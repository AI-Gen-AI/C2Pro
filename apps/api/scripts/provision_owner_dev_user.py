"""Prepare (DRY-RUN by default) the Clerk DEVELOPMENT user the owner signs in with to work in C2Pro in a browser.

NOTHING is created unless BOTH ``--apply`` and ``--authorization OWNER-AUTHORIZED-CLERK-DEV-USER`` are given. Without them this
script only READS Clerk and prints the plan, so it is safe to run today and shows exactly what the authorization would do.

Guarantees (each is a refusal, not a warning):
* the Clerk credentials must be positively identified as a DEVELOPMENT/TEST instance (the same gate as the E2E fixture);
* the automated E2E identity is never touched: the owner's email may not be the E2E email, and no existing user is modified;
* the only write is (a) creating ONE user with the given email and (b) adding it as a plain member (``org:member``) of the dedicated
  E2E Organization -- which must already exist and keep its tenant. No other organization, user or setting is changed;
* an already existing user is only ADDED to that Organization, and only if it belongs to no other one (a second membership would
  disable the front end's automatic Organization activation);
* ambiguity (several users for the email, several organizations for the tenant) stops the run.

A Clerk Development email of the form ``name+clerk_test@domain`` needs no inbox: the instance accepts the fixed code 424242. A real
address works too (Clerk mails the code). Nothing secret is printed; the email appears only as a short fingerprint.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from typing import Any

import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from provision_clerk_e2e_fixture import (  # noqa: E402
    CLERK_API_BASE,
    DEFAULT_E2E_EMAIL,
    DEFAULT_ORG_NAME,
    DEFAULT_TENANT_ID,
    ClerkAdmin,
    FixtureError,
    require_development_instance,
    select_organization,
)

AUTHORIZATION_PHRASE = "OWNER-AUTHORIZED-CLERK-DEV-USER"
OWNER_ROLE = "org:member"


class OwnerAdmin(ClerkAdmin):
    """The one extra write this script needs; everything else is inherited (and mostly read-only)."""

    def create_user(self, *, email: str, first_name: str) -> dict[str, Any]:
        return dict(
            self._call(
                "POST",
                "/users",
                json={"email_address": [email], "first_name": first_name, "skip_password_requirement": True},
            )
        )


@dataclass
class Plan:
    environment: str
    email_fingerprint: str
    organization_found: bool
    organization_id_fingerprint: str
    user_exists: bool
    already_member: bool
    other_memberships: int
    actions: list[str] = field(default_factory=list)
    refusal: str | None = None

    @property
    def writes(self) -> bool:
        return bool(self.actions)


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()[:10]


def build_plan(
    admin: ClerkAdmin, *, email: str, e2e_email: str, org_name: str, tenant_id: str, environment: str
) -> Plan:
    """READ-ONLY. Decides what an authorized run would do, or why it must not."""
    email = email.strip()
    plan = Plan(environment, fingerprint(email), False, "", False, False, 0)
    if "@" not in email:
        plan.refusal = "OWNER_EMAIL_INVALID"
        return plan
    if email.lower() == e2e_email.strip().lower():
        plan.refusal = "OWNER_EMAIL_IS_THE_AUTOMATED_E2E_IDENTITY: it is never reused, replaced or altered"
        return plan

    organizations, total = admin.list_organizations()
    if total is not None and total > len(organizations):
        raise FixtureError(f"The instance reports {total} Organizations but only {len(organizations)} were listed (truncated view).")
    org = select_organization(organizations, name=org_name, tenant_id=tenant_id)
    if org is None:
        plan.refusal = "E2E_ORGANIZATION_NOT_FOUND: run the E2E fixture first; this script never creates an Organization"
        return plan
    plan.organization_found = True
    org_id = str(org["id"])
    plan.organization_id_fingerprint = fingerprint(org_id)

    users = admin.users_by_email(email)
    if len(users) > 1:
        raise FixtureError(f"The email resolves to {len(users)} Clerk users; refusing to guess.")
    if not users:
        plan.actions += ["create the Clerk Development user", f"add it to the E2E Organization as {OWNER_ROLE}"]
        return plan

    plan.user_exists = True
    user_id = str(users[0]["id"])
    memberships = admin.user_memberships(user_id)
    in_target = [m for m in memberships if (m.get("organization") or {}).get("id") == org_id]
    others = [m for m in memberships if (m.get("organization") or {}).get("id") != org_id]
    plan.already_member, plan.other_memberships = bool(in_target), len(others)
    if others:
        plan.refusal = "USER_BELONGS_TO_ANOTHER_ORGANIZATION: a second membership would disable automatic Organization activation"
        return plan
    if not in_target:
        plan.actions.append(f"add the existing user to the E2E Organization as {OWNER_ROLE}")
    return plan


def apply_plan(admin: OwnerAdmin, plan: Plan, *, email: str, org_name: str, tenant_id: str) -> dict[str, Any]:
    if plan.refusal:
        raise FixtureError(plan.refusal)
    organizations, _ = admin.list_organizations()
    org = select_organization(organizations, name=org_name, tenant_id=tenant_id)
    assert org is not None  # build_plan established it
    org_id = str(org["id"])
    users = admin.users_by_email(email)
    created = False
    if not users:
        user = admin.create_user(email=email, first_name="Owner")
        created = True
    else:
        user = users[0]
    user_id = str(user["id"])
    added = False
    if not any((m.get("organization") or {}).get("id") == org_id for m in admin.user_memberships(user_id)):
        admin.create_organization_membership(org_id, user_id, OWNER_ROLE)
        added = True
    return {"user_created": created, "membership_added": added, "role": OWNER_ROLE}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", default=os.getenv("OWNER_DEV_EMAIL", ""))
    parser.add_argument("--apply", action="store_true", help="perform the writes (also needs --authorization)")
    parser.add_argument("--authorization", default="", help=f"must equal {AUTHORIZATION_PHRASE} for --apply")
    args = parser.parse_args(argv)

    secret = os.getenv("CLERK_SECRET_KEY", "")
    publishable = os.getenv("CLERK_PUBLISHABLE_KEY") or os.getenv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY")
    if not secret or not args.email:
        print("FAIL: CLERK_SECRET_KEY and --email (or OWNER_DEV_EMAIL) are required.", file=sys.stderr)
        return 2
    apply = bool(args.apply and args.authorization == AUTHORIZATION_PHRASE)
    if args.apply and not apply:
        print(f"FAIL: --apply needs --authorization {AUTHORIZATION_PHRASE}; nothing was done.", file=sys.stderr)
        return 2
    try:
        environment = require_development_instance(secret, publishable)
        with httpx.Client(timeout=30.0, headers={"Authorization": f"Bearer {secret}"}) as client:
            admin = OwnerAdmin(client)
            plan = build_plan(
                admin,
                email=args.email,
                e2e_email=os.getenv("E2E_CLERK_USER_EMAIL", DEFAULT_E2E_EMAIL),
                org_name=os.getenv("E2E_CLERK_ORG_NAME", DEFAULT_ORG_NAME),
                tenant_id=os.getenv("E2E_TENANT_ID", DEFAULT_TENANT_ID),
                environment=environment,
            )
            report: dict[str, Any] = {"mode": "APPLY" if apply else "DRY_RUN", "plan": asdict(plan), "clerk_api": CLERK_API_BASE}
            if apply:
                report["result"] = apply_plan(
                    admin,
                    plan,
                    email=args.email,
                    org_name=os.getenv("E2E_CLERK_ORG_NAME", DEFAULT_ORG_NAME),
                    tenant_id=os.getenv("E2E_TENANT_ID", DEFAULT_TENANT_ID),
                )
    except FixtureError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if plan.refusal else 0


if __name__ == "__main__":
    sys.exit(main())
