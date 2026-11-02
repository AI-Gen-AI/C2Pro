"""The owner's Clerk Development user: prepared, never created without the express phrase, never at the expense of the E2E identity.

A fake Clerk records every call; nothing touches the network.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[3] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import provision_owner_dev_user as p  # noqa: E402
from provision_clerk_e2e_fixture import FixtureError  # noqa: E402

TENANT = "00000000-0000-0000-0000-00000000a113"
ORG = {"id": "org_e2e", "name": "C2Pro E2E", "public_metadata": {"tenant_id": TENANT}}
E2E_EMAIL = "testuser@c2pro.com"
OWNER = "owner+clerk_test@example.com"


class FakeClerk(p.OwnerAdmin):
    def __init__(self, *, users: dict[str, list[dict]] | None = None, memberships: dict[str, list[dict]] | None = None, orgs: list[dict] | None = None):
        self.calls: list[tuple] = []
        self._users = users or {}
        self._memberships = memberships or {}
        self._orgs = [ORG] if orgs is None else orgs

    def list_organizations(self, limit: int = 100) -> tuple[list[dict[str, Any]], int | None]:
        self.calls.append(("list_organizations",))
        return self._orgs, len(self._orgs)

    def users_by_email(self, email: str) -> list[dict[str, Any]]:
        self.calls.append(("users_by_email", email))
        return self._users.get(email, [])

    def user_memberships(self, user_id: str) -> list[dict[str, Any]]:
        self.calls.append(("user_memberships", user_id))
        return self._memberships.get(user_id, [])

    def create_user(self, *, email: str, first_name: str) -> dict[str, Any]:
        self.calls.append(("WRITE create_user", email))
        return {"id": "user_owner"}

    def create_organization_membership(self, org_id: str, user_id: str, role: str) -> dict[str, Any]:
        self.calls.append(("WRITE membership", org_id, user_id, role))
        return {}

    @property
    def writes(self) -> list[tuple]:
        return [c for c in self.calls if str(c[0]).startswith("WRITE")]


def plan(admin: FakeClerk, email: str = OWNER) -> p.Plan:
    return p.build_plan(admin, email=email, e2e_email=E2E_EMAIL, org_name="C2Pro E2E", tenant_id=TENANT, environment="DEVELOPMENT/TEST")


def test_the_plan_is_read_only_and_says_what_an_authorized_run_would_do() -> None:
    admin = FakeClerk()
    result = plan(admin)
    assert result.refusal is None and result.organization_found and not result.user_exists
    assert result.actions == ["create the Clerk Development user", "add it to the E2E Organization as org:member"]
    assert admin.writes == [], "building the plan never writes"


def test_the_automated_e2e_identity_can_never_be_the_owners_user() -> None:
    admin = FakeClerk(users={E2E_EMAIL: [{"id": "user_e2e"}]})
    for email in (E2E_EMAIL, E2E_EMAIL.upper(), f"  {E2E_EMAIL} "):
        assert plan(admin, email).refusal.startswith("OWNER_EMAIL_IS_THE_AUTOMATED_E2E_IDENTITY")
    assert admin.calls == [], "refused before any Clerk call"


def test_it_refuses_when_the_e2e_organization_is_missing_and_never_creates_one() -> None:
    admin = FakeClerk(orgs=[])
    assert plan(admin).refusal.startswith("E2E_ORGANIZATION_NOT_FOUND") and admin.writes == []


def test_an_existing_user_is_only_added_and_only_when_it_belongs_to_no_other_organization() -> None:
    other = {"organization": {"id": "org_other"}}
    mine = {"organization": {"id": "org_e2e"}}
    user = {OWNER: [{"id": "user_owner"}]}
    assert plan(FakeClerk(users=user, memberships={"user_owner": []})).actions == ["add the existing user to the E2E Organization as org:member"]
    assert plan(FakeClerk(users=user, memberships={"user_owner": [mine]})).actions == []
    refused = plan(FakeClerk(users=user, memberships={"user_owner": [other]}))
    assert refused.refusal.startswith("USER_BELONGS_TO_ANOTHER_ORGANIZATION") and refused.other_memberships == 1


def test_several_users_for_one_email_stop_the_run() -> None:
    with pytest.raises(FixtureError):
        plan(FakeClerk(users={OWNER: [{"id": "a"}, {"id": "b"}]}))


def test_apply_performs_exactly_the_two_writes_and_nothing_else() -> None:
    admin = FakeClerk()
    result = p.apply_plan(admin, plan(admin), email=OWNER, org_name="C2Pro E2E", tenant_id=TENANT)
    assert result == {"user_created": True, "membership_added": True, "role": "org:member"}
    assert admin.writes == [("WRITE create_user", OWNER), ("WRITE membership", "org_e2e", "user_owner", "org:member")]


def test_apply_refuses_a_refused_plan() -> None:
    admin = FakeClerk(orgs=[])
    with pytest.raises(FixtureError):
        p.apply_plan(admin, plan(admin), email=OWNER, org_name="C2Pro E2E", tenant_id=TENANT)
    assert admin.writes == []


def test_the_cli_never_applies_without_the_express_phrase_and_refuses_a_production_key(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_x")
    assert p.main(["--email", OWNER, "--apply"]) == 2
    assert p.main(["--email", OWNER, "--apply", "--authorization", "yes please"]) == 2
    assert "nothing was done" in capsys.readouterr().err
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_live_x")
    assert p.main(["--email", OWNER]) == 1
    assert "PRODUCTION" in capsys.readouterr().err


def test_the_email_only_ever_appears_as_a_fingerprint() -> None:
    result = plan(FakeClerk())
    assert OWNER not in repr(result) and len(result.email_fingerprint) == 10
