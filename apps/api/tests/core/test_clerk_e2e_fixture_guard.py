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
import sys
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


# Keys are COMPOSED from the module's own prefix constants rather than written
# out, so these tests carry no secret-shaped literal and cannot drift from the
# rule they pin: if a prefix is ever added or renamed, they follow it.
_SUFFIX = "not-a-real-key"
_PRODUCTION_SECRETS = [p + _SUFFIX for p in fixture_script._PRODUCTION_PREFIXES if not p.startswith("pk_")]
_DEVELOPMENT_SECRETS = [p + _SUFFIX for p in fixture_script._DEVELOPMENT_SECRET_PREFIXES]
_DEVELOPMENT_SECRET = _DEVELOPMENT_SECRETS[0]


@pytest.mark.parametrize("secret_key", _PRODUCTION_SECRETS)
def test_production_secret_key_is_refused(secret_key: str) -> None:
    with pytest.raises(FixtureError, match="PRODUCTION"):
        fixture_script.require_development_instance(secret_key, None)


@pytest.mark.parametrize(
    "publishable_key", [p + _SUFFIX for p in fixture_script._PRODUCTION_PREFIXES]
)
def test_production_publishable_key_is_refused(publishable_key: str) -> None:
    with pytest.raises(FixtureError, match="PRODUCTION"):
        fixture_script.require_development_instance(_DEVELOPMENT_SECRET, publishable_key)


@pytest.mark.parametrize(
    "secret_key",
    ["sk_unknown_" + _SUFFIX, "", "abc", _DEVELOPMENT_SECRET.upper()],
    ids=["unknown_prefix", "empty", "bare", "wrong_case"],
)
def test_unprovable_environment_is_refused(secret_key: str) -> None:
    """Positive identification only -- 'not provably production' is not enough."""
    with pytest.raises(FixtureError):
        fixture_script.require_development_instance(secret_key, None)


@pytest.mark.parametrize("secret_key", _DEVELOPMENT_SECRETS)
def test_development_secret_key_is_accepted(secret_key: str) -> None:
    assert fixture_script.require_development_instance(secret_key, None) == "DEVELOPMENT/TEST"


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


# ---------------------------------------------------------------------------
# Output paths: --jwks-out and --github-env are WRITE sinks
# ---------------------------------------------------------------------------
#
# Both options name a file this script writes, so an unconstrained value lets
# whoever controls the argument redirect a write anywhere the process can
# reach. .github/workflows/ci.yml passes NEITHER option -- it runs the script
# from the repository root and relies on the defaults -- so each option has
# exactly one legitimate destination and the guard is equality against it, not
# containment in a directory the process happens to own.
#
#   --jwks-out    $RUNNER_TEMP/clerk-jwks.json  (a later ci.yml step serves that
#                                                directory over http.server and
#                                                the backend fetches
#                                                /clerk-jwks.json from it)
#   --github-env  $GITHUB_ENV                   (the file itself, not its
#                                                directory, which also holds the
#                                                other _runner_file_commands)


@pytest.fixture
def runner_temp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    return tmp_path


@pytest.fixture
def github_env_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    env_file = tmp_path / "_runner_file_commands" / "set_env_abc"
    env_file.parent.mkdir(parents=True)
    env_file.touch()
    monkeypatch.setenv("GITHUB_ENV", str(env_file))
    return env_file


def _resolve_jwks(raw: str) -> Path:
    return fixture_script.resolve_exact_path(
        raw,
        expected=fixture_script.expected_jwks_path(),
        option="--jwks-out",
        requires="RUNNER_TEMP",
    )


def _resolve_github_env(raw: str) -> Path:
    return fixture_script.resolve_exact_path(
        raw,
        expected=fixture_script.expected_github_env_path(),
        option="--github-env",
        requires="GITHUB_ENV",
    )


# --- the contracts CI actually depends on ----------------------------------


def test_jwks_contract_is_the_file_ci_serves(runner_temp: Path) -> None:
    assert fixture_script.expected_jwks_path() == runner_temp / "clerk-jwks.json"


def test_jwks_exact_path_is_accepted(runner_temp: Path) -> None:
    assert _resolve_jwks(str(runner_temp / "clerk-jwks.json")) == runner_temp / "clerk-jwks.json"


def test_github_env_contract_is_the_env_file_itself(github_env_file: Path) -> None:
    assert fixture_script.expected_github_env_path() == github_env_file


def test_github_env_exact_path_is_accepted(github_env_file: Path) -> None:
    assert _resolve_github_env(str(github_env_file)) == github_env_file


# --- a sibling in the same trusted directory is NOT authorised -------------


def test_jwks_sibling_in_runner_temp_is_refused(runner_temp: Path) -> None:
    """Being inside RUNNER_TEMP is not the contract; being THE file is."""
    with pytest.raises(FixtureError, match="not the one file"):
        _resolve_jwks(str(runner_temp / "other.json"))


def test_github_env_sibling_in_the_same_directory_is_refused(github_env_file: Path) -> None:
    with pytest.raises(FixtureError, match="not the one file"):
        _resolve_github_env(str(github_env_file.parent / "set_env_other"))


# --- traversal, arbitrary absolute paths, symlinks -------------------------


def test_jwks_traversal_is_refused(runner_temp: Path) -> None:
    with pytest.raises(FixtureError, match="not the one file"):
        _resolve_jwks(str(runner_temp / ".." / ".." / ".." / "etc" / "shadow"))


def test_github_env_traversal_is_refused(github_env_file: Path) -> None:
    with pytest.raises(FixtureError, match="not the one file"):
        _resolve_github_env(str(github_env_file.parent / ".." / ".." / "etc" / "shadow"))


@pytest.mark.parametrize(
    ("resolve", "fixture_name"),
    [(_resolve_jwks, "runner_temp"), (_resolve_github_env, "github_env_file")],
    ids=["jwks", "github_env"],
)
def test_arbitrary_absolute_path_is_refused(
    resolve: Any, fixture_name: str, request: pytest.FixtureRequest
) -> None:
    request.getfixturevalue(fixture_name)
    with pytest.raises(FixtureError, match="not the one file"):
        resolve("/etc/c2pro-should-not-exist")


def test_jwks_symlink_at_the_contract_path_is_refused(runner_temp: Path) -> None:
    """A link planted AT the destination must not redirect the write."""
    link = runner_temp / "clerk-jwks.json"
    link.symlink_to("/etc/c2pro-should-not-exist")

    with pytest.raises(FixtureError, match="symlink"):
        _resolve_jwks(str(link))


def test_github_env_symlink_at_the_contract_path_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    link = tmp_path / "set_env_abc"
    link.symlink_to("/etc/c2pro-should-not-exist")
    monkeypatch.setenv("GITHUB_ENV", str(link))

    with pytest.raises(FixtureError, match="symlink"):
        _resolve_github_env(str(link))


# --- off a runner there is no destination to guess -------------------------


def test_jwks_default_is_absent_off_a_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RUNNER_TEMP", raising=False)

    assert fixture_script.expected_jwks_path() is None


def test_jwks_override_without_runner_temp_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("RUNNER_TEMP", raising=False)

    with pytest.raises(FixtureError, match="RUNNER_TEMP"):
        _resolve_jwks(str(tmp_path / "clerk-jwks.json"))


def test_github_env_override_without_github_env_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("GITHUB_ENV", raising=False)

    with pytest.raises(FixtureError, match="GITHUB_ENV"):
        _resolve_github_env(str(tmp_path / "set_env_abc"))


# --- refusals name the option and leak nothing -----------------------------


def test_refusal_names_the_option_and_leaks_no_content(runner_temp: Path) -> None:
    secret = runner_temp / "other.json"
    secret.write_text('{"leaked": "SHOULD-NOT-APPEAR"}', encoding="utf-8")

    with pytest.raises(FixtureError) as excinfo:
        _resolve_jwks(str(secret))

    message = str(excinfo.value)
    assert "--jwks-out" in message
    assert "SHOULD-NOT-APPEAR" not in message


# --- a rejected path stops the run before any Clerk mutation ---------------


def test_rejected_output_path_never_reaches_clerk(
    monkeypatch: pytest.MonkeyPatch, runner_temp: Path
) -> None:
    """The resolution happens before the first Clerk call, not after."""
    called: list[str] = []

    def _explode(*args: Any, **kwargs: Any) -> str:
        called.append("clerk")
        raise AssertionError("Clerk must not be contacted once a path is rejected")

    monkeypatch.setattr(fixture_script, "require_development_instance", _explode)
    monkeypatch.setenv("CLERK_SECRET_KEY", _DEVELOPMENT_SECRET)
    monkeypatch.setattr(
        sys, "argv", ["provision", "--jwks-out", str(runner_temp / "other.json")]
    )

    assert fixture_script.main() == 1
    assert called == []
