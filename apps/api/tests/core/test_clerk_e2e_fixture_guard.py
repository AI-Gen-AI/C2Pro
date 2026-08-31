"""Fail-closed guarantees of the Clerk E2E fixture provisioner.

TS-UT-P0B-FIXTURE-001.

This script is the only thing in the repository authorised to mutate a Clerk
instance. Everything here therefore pins the REFUSALS rather than the happy
path: an unprovable environment, an ambiguous identity, an ambiguous
Organization, or an Organization that already belongs to another tenant must
all stop before any write.

Note on slugs: this Clerk instance rejects them outright
(``organization_slugs_disabled``), so the fixture identifies its Organization by
the deterministic tenant id in publicMetadata -- which is what the frontend
actually reads -- and never sends a slug.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "provision_clerk_e2e_fixture.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("provision_clerk_e2e_fixture", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixture_script = _load()
FixtureError = fixture_script.FixtureError


# ---------------------------------------------------------------------------
# Environment safety: the gate in front of an external mutation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "secret_key",
    ["sk_live_abc", "live_abc"],
    ids=["sk_live", "legacy_live"],
)
def test_production_secret_key_is_refused(secret_key: str) -> None:
    with pytest.raises(FixtureError, match="PRODUCTION"):
        fixture_script.require_development_instance(secret_key, None)


def test_production_publishable_key_is_refused() -> None:
    with pytest.raises(FixtureError, match="PRODUCTION"):
        fixture_script.require_development_instance("sk_test_abc", "pk_live_abc")


@pytest.mark.parametrize(
    "secret_key",
    ["sk_unknown_abc", "", "abc", "SK_TEST_abc"],
    ids=["unknown_prefix", "empty", "bare", "wrong_case"],
)
def test_unprovable_environment_is_refused(secret_key: str) -> None:
    """Positive identification only -- 'not provably production' is not enough."""
    with pytest.raises(FixtureError):
        fixture_script.require_development_instance(secret_key, None)


@pytest.mark.parametrize("secret_key", ["sk_test_abc", "test_abc"])
def test_development_secret_key_is_accepted(secret_key: str) -> None:
    assert fixture_script.require_development_instance(secret_key, "pk_test_abc") == (
        "DEVELOPMENT/TEST"
    )


# ---------------------------------------------------------------------------
# Reconciliation refusals
# ---------------------------------------------------------------------------


class _FakeAdmin:
    """Records writes so a test can prove none happened."""

    def __init__(
        self,
        *,
        users: list[dict[str, Any]] | None = None,
        organizations: list[dict[str, Any]] | None = None,
    ) -> None:
        self._users = users or []
        self._organizations = organizations or []
        self.writes: list[str] = []

    def users_by_email(self, email: str) -> list[dict[str, Any]]:
        return self._users

    def merge_organization_metadata(self, org_id: str, tenant_id: str) -> dict[str, Any]:
        self.writes.append(f"metadata:{org_id}")
        return {}

    def organization_memberships(self, org_id: str) -> list[dict[str, Any]]:
        return []

    def create_organization_membership(
        self, org_id: str, user_id: str, role: str
    ) -> dict[str, Any]:
        self.writes.append(f"membership:{org_id}:{user_id}")
        return {}


@pytest.mark.parametrize("users", [[], [{"id": "user_a"}, {"id": "user_b"}]], ids=["none", "two"])
def test_ambiguous_identity_is_refused(users: list[dict[str, Any]]) -> None:
    admin = _FakeAdmin(users=users)
    with pytest.raises(FixtureError, match="exactly one Clerk user"):
        fixture_script.resolve_user(admin, "testuser@c2pro.com")
    assert admin.writes == []


def test_single_identity_resolves() -> None:
    admin = _FakeAdmin(users=[{"id": "user_only"}])
    assert fixture_script.resolve_user(admin, "testuser@c2pro.com") == "user_only"


_TENANT = fixture_script.DEFAULT_TENANT_ID
_NAME = fixture_script.DEFAULT_ORG_NAME


def _select(organizations: list[dict[str, Any]]) -> dict[str, Any] | None:
    return fixture_script.select_organization(organizations, name=_NAME, tenant_id=_TENANT)


def test_organization_is_identified_by_tenant_metadata() -> None:
    """Tenant metadata wins: it is what the frontend actually reads."""
    chosen = _select(
        [
            {"id": "org_named", "name": _NAME},
            {"id": "org_tenant", "name": "Something Else",
             "public_metadata": {"tenant_id": _TENANT}},
        ]
    )
    assert chosen is not None
    assert chosen["id"] == "org_tenant"


def test_duplicate_tenant_claims_are_refused() -> None:
    with pytest.raises(FixtureError, match="claim the E2E tenant_id"):
        _select(
            [
                {"id": "org_1", "public_metadata": {"tenant_id": _TENANT}},
                {"id": "org_2", "public_metadata": {"tenant_id": _TENANT}},
            ]
        )


def test_duplicate_names_are_refused() -> None:
    with pytest.raises(FixtureError, match="share the dedicated E2E name"):
        _select([{"id": "org_1", "name": _NAME}, {"id": "org_2", "name": _NAME}])


def test_first_run_adopts_the_exact_name_before_metadata_exists() -> None:
    chosen = _select([{"id": "org_named", "name": _NAME}])
    assert chosen is not None
    assert chosen["id"] == "org_named"


def test_unrelated_organizations_are_not_adopted() -> None:
    assert _select([{"id": "org_other", "name": "Someone Else's Org"}]) is None
    assert _select([]) is None


def test_organization_pointing_at_another_tenant_is_refused() -> None:
    admin = _FakeAdmin()
    org = {"id": "org_1", "public_metadata": {"tenant_id": "11111111-1111-1111-1111-111111111111"}}
    with pytest.raises(FixtureError, match="DIFFERENT tenant_id"):
        fixture_script.ensure_tenant_metadata(admin, org, fixture_script.DEFAULT_TENANT_ID)
    assert admin.writes == [], "a conflicting Organization must never be repointed"


def test_correct_tenant_metadata_is_a_noop() -> None:
    admin = _FakeAdmin()
    org = {"id": "org_1", "public_metadata": {"tenant_id": fixture_script.DEFAULT_TENANT_ID}}
    assert fixture_script.ensure_tenant_metadata(admin, org, fixture_script.DEFAULT_TENANT_ID) is (
        False
    )
    assert admin.writes == []


def test_missing_tenant_metadata_is_written() -> None:
    admin = _FakeAdmin()
    org = {"id": "org_1", "public_metadata": {}}
    assert fixture_script.ensure_tenant_metadata(admin, org, fixture_script.DEFAULT_TENANT_ID) is (
        True
    )
    assert admin.writes == ["metadata:org_1"]


def test_membership_is_created_only_when_absent() -> None:
    admin = _FakeAdmin()
    assert fixture_script.ensure_membership(admin, "org_1", "user_1", "org:admin") is True
    assert admin.writes == ["membership:org_1:user_1"]


def test_existing_membership_is_a_noop() -> None:
    class _MemberAdmin(_FakeAdmin):
        def organization_memberships(self, org_id: str) -> list[dict[str, Any]]:
            return [{"public_user_data": {"user_id": "user_1"}}]

    admin = _MemberAdmin()
    assert fixture_script.ensure_membership(admin, "org_1", "user_1", "org:admin") is False
    assert admin.writes == []


# ---------------------------------------------------------------------------
# Tenant identity must stay the repository's deterministic one
# ---------------------------------------------------------------------------


def test_default_tenant_matches_the_existing_e2e_seed() -> None:
    """The fixture must not invent a second tenant contract."""
    from tests.e2e_seed.seed_wedge import TENANT_ID

    assert str(TENANT_ID) == fixture_script.DEFAULT_TENANT_ID


def test_unwrap_handles_both_clerk_list_shapes() -> None:
    assert fixture_script._unwrap({"data": [{"id": "a"}]}) == [{"id": "a"}]
    assert fixture_script._unwrap([{"id": "b"}]) == [{"id": "b"}]
    assert fixture_script._unwrap({"total_count": 0}) == []
