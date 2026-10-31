#!/usr/bin/env python
"""READ-ONLY preflight of the two Clerk DEVELOPMENT identities of the integral S1-S8 UAT.

It answers, before any browser or paid AI call, the question "can this run start?" for both humans:

* identity A (``E2E_CLERK_USER_EMAIL``, default the E2E user) and identity B (``E2E_CLERK_TENANT_B_USER_EMAIL``)
  each resolve to EXACTLY ONE Clerk user of the Development instance;
* each is a member of an Organization whose ``publicMetadata.tenant_id`` is set (the tenant the application resolves);
* the two Organizations and the two tenant ids DIFFER, and the two users differ.

It never creates, changes or deletes anything and refuses to talk to a Production instance (the same positive
Development identification the fixture provisioner uses). It prints booleans and pseudonyms only -- never an email,
a Clerk id or a key -- and exits:

* 0  both identities are ready;
* 3  the only thing missing is B's Organization membership (B's user exists): run the provisioner for B, then re-run;
* 1  anything else (a missing user, an ambiguous email, a shared Organization or tenant, a Production key).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

READY, NEEDS_B_ORGANIZATION, FAILED = 0, 3, 1

# Identity B of THIS runner (#1112) is a Clerk DEVELOPMENT user. It is not the Production B of the read-only
# validation lane (#1144): that identity lives in another Clerk instance and never counts here.
DEV_B_EMAIL_ENV = "INTEGRAL_CLERK_DEV_B_EMAIL"
LEGACY_B_EMAIL_ENV = "E2E_CLERK_TENANT_B_USER_EMAIL"


def resolve_b_email(environ: dict[str, str] | os._Environ[str]) -> str:
    """The dedicated Development-B variable wins; the legacy tenant-B name is only a fallback."""
    return (environ.get(DEV_B_EMAIL_ENV) or environ.get(LEGACY_B_EMAIL_ENV) or "").strip()


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def _load_provisioner() -> Any:
    path = Path(__file__).resolve().parent / "provision_clerk_e2e_fixture.py"
    spec = importlib.util.spec_from_file_location("provision_clerk_e2e_fixture", path)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules["provision_clerk_e2e_fixture"] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _pseudonym(value: str | None) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:12] if value else ""


@dataclass
class IdentityReport:
    label: str
    users_found: int = 0
    user_id: str = ""
    membership_count: int = 0
    organization_id: str = ""
    tenant_id: str = ""
    problems: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return not self.problems

    def public(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "users_found": self.users_found,
            "membership_count": self.membership_count,
            "has_tenant_metadata": bool(self.tenant_id),
            "user": _pseudonym(self.user_id),
            "organization": _pseudonym(self.organization_id),
            "problems": self.problems,
        }


def evaluate_identity(
    label: str, users: list[dict[str, Any]], memberships: list[dict[str, Any]]
) -> IdentityReport:
    """Pure: judge one identity from what Clerk answered about it."""
    report = IdentityReport(label=label, users_found=len(users), membership_count=len(memberships))
    if len(users) != 1:
        report.problems.append(
            f"the email resolves to {len(users)} Clerk user(s) in the Development instance, expected "
            "exactly one (a Production identity of the read-only lane #1144 does not count)"
        )
        return report
    report.user_id = str(users[0].get("id") or "")
    if len(memberships) == 0:
        report.problems.append(
            "the user belongs to no Organization (no tenant context can be resolved)"
        )
        return report
    if len(memberships) > 1:
        report.problems.append(
            f"the user belongs to {len(memberships)} Organizations; exactly one is required"
        )
        return report
    organization = memberships[0].get("organization") or {}
    report.organization_id = str(organization.get("id") or "")
    report.tenant_id = str((organization.get("public_metadata") or {}).get("tenant_id") or "")
    if not report.organization_id:
        report.problems.append("the membership names no Organization")
    if not report.tenant_id:
        report.problems.append("the Organization carries no publicMetadata.tenant_id")
    elif not _is_uuid(report.tenant_id):
        report.problems.append("the Organization's publicMetadata.tenant_id is not a valid UUID")
    return report


def evaluate_pair(a: IdentityReport, b: IdentityReport) -> tuple[int, list[str]]:
    """Pure: the exit code and the reasons, from the two identity reports."""
    reasons: list[str] = [f"A: {p}" for p in a.problems]
    if a.problems:
        reasons.extend(f"B: {p}" for p in b.problems)
        return FAILED, reasons
    only_org_missing = b.users_found == 1 and b.membership_count == 0
    if only_org_missing:
        return NEEDS_B_ORGANIZATION, [
            "B: the user exists and belongs to no Organization yet (provision it)"
        ]
    reasons.extend(f"B: {p}" for p in b.problems)
    if b.problems:
        return FAILED, reasons
    if a.user_id == b.user_id:
        reasons.append("A and B are the same Clerk user")
    if a.organization_id == b.organization_id:
        reasons.append("A and B share one Organization")
    if a.tenant_id == b.tenant_id:
        reasons.append("A and B share one tenant id")
    return (FAILED if reasons else READY), reasons


def main() -> int:
    provisioner = _load_provisioner()
    secret_key = os.getenv("CLERK_SECRET_KEY", "")
    publishable = os.getenv("CLERK_PUBLISHABLE_KEY") or os.getenv(
        "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY"
    )
    email_a = os.getenv("E2E_CLERK_USER_EMAIL", provisioner.DEFAULT_E2E_EMAIL)
    email_b = resolve_b_email(os.environ)
    if not secret_key:
        print("FAIL: CLERK_SECRET_KEY is required.", file=sys.stderr)
        return FAILED
    if not email_b:
        print(
            f"FAIL: {DEV_B_EMAIL_ENV} (or legacy {LEGACY_B_EMAIL_ENV}) is not configured: Development "
            "identity B does not exist for this run. Nothing is created and nothing is faked.",
            file=sys.stderr,
        )
        return FAILED
    if email_a.strip().lower() == email_b.lower():
        print("FAIL: identities A and B resolve to the same email.", file=sys.stderr)
        return FAILED
    try:
        environment = provisioner.require_development_instance(secret_key, publishable)
    except provisioner.FixtureError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return FAILED
    reports: list[IdentityReport] = []
    with httpx.Client(timeout=30.0, headers={"Authorization": f"Bearer {secret_key}"}) as client:
        admin = provisioner.ClerkAdmin(client)
        for label, email in (("A", email_a), ("B", email_b)):
            try:
                users = admin.users_by_email(email)
                memberships = admin.user_memberships(str(users[0]["id"])) if len(users) == 1 else []
            except provisioner.FixtureError as exc:
                print(
                    f"FAIL: Clerk read for identity {label} failed: {str(exc)[:200]}",
                    file=sys.stderr,
                )
                return FAILED
            reports.append(evaluate_identity(label, users, memberships))
    code, reasons = evaluate_pair(reports[0], reports[1])
    print(
        json.dumps(
            {
                "clerk_environment": environment,
                "a": reports[0].public(),
                "b": reports[1].public(),
                "exit": code,
                "reasons": reasons,
            },
            indent=2,
        )
    )
    return code


if __name__ == "__main__":
    sys.exit(main())
