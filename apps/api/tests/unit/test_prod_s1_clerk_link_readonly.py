"""Offline tests for S1 Clerk↔PostgreSQL read-only preflight (no live credentials)."""
from __future__ import annotations

from pathlib import Path
from uuid import UUID

import httpx
import pytest

from scripts import verify_prod_s1_clerk_link_readonly as s1


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("postgres://db.invalid/test", "postgresql+asyncpg://db.invalid/test"),
        ("postgresql://db.invalid/test", "postgresql+asyncpg://db.invalid/test"),
        ("postgresql+asyncpg://db.invalid/test", "postgresql+asyncpg://db.invalid/test"),
    ],
)
def test_only_postgres_database_schemes(raw: str, expected: str) -> None:
    assert s1.asyncpg_url(raw) == expected
    with pytest.raises(s1.PreflightBlocked, match="INVALID_DATABASE_SCHEME"):
        s1.asyncpg_url("sqlite:///demo.db")


def clerk_fake_api(
    *,
    tenant: str,
    org_count: int = 1,
    org_id: str = "org_b",
) -> httpx.Client:
    def respond(request: httpx.Request) -> httpx.Response:
        p = request.url.path
        if p == "/v1/users":
            return httpx.Response(200, json={"data": [{"id": "user_b"}]})
        if p == "/v1/users/user_b/organization_memberships":
            return httpx.Response(
                200,
                json={"data": [{"organization": {"id": org_id}} for _ in range(org_count)]},
            )
        if p == "/v1/organizations/" + org_id:
            return httpx.Response(200, json={"public_metadata": {"tenant_id": tenant}})
        return httpx.Response(404, json={"error": "unexpected path"})

    return httpx.Client(transport=httpx.MockTransport(respond))


def test_b_clerk_membership_and_tenant_verified_from_api() -> None:
    with clerk_fake_api(tenant=str(s1.B_TENANT)) as client:
        identity = s1.clerk_identity(
            client,
            email="synthetic-b@example.invalid",
            expected_tenant=s1.B_TENANT,
            expected_org=None,
            lane="B",
        )
    assert identity.clerk_user_id == "user_b"
    assert identity.clerk_org_id == "org_b"
    assert identity.tenant_id == s1.B_TENANT


def test_multiple_memberships_fail_closed_before_db() -> None:
    with clerk_fake_api(tenant=str(s1.B_TENANT), org_count=2) as client:
        with pytest.raises(s1.PreflightBlocked, match="B_CLERK_MEMBERSHIPS_NOT_ONE"):
            s1.clerk_identity(
                client,
                email="synthetic-b@example.invalid",
                expected_tenant=s1.B_TENANT,
                expected_org=None,
                lane="B",
            )


def test_wrong_clerk_tenant_metadata_fails_closed() -> None:
    with clerk_fake_api(tenant=str(UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"))) as client:
        with pytest.raises(s1.PreflightBlocked, match="B_CLERK_TENANT_METADATA_MISMATCH"):
            s1.clerk_identity(
                client,
                email="synthetic-b@example.invalid",
                expected_tenant=s1.B_TENANT,
                expected_org=None,
                lane="B",
            )


def test_a_exact_expected_organization_rejected_if_wrong() -> None:
    with clerk_fake_api(tenant=str(s1.B_TENANT)) as client:
        with pytest.raises(s1.PreflightBlocked, match="A_CLERK_ORG_MISMATCH"):
            s1.clerk_identity(
                client,
                email="synthetic-a@example.invalid",
                expected_tenant=s1.B_TENANT,
                expected_org="org_expected",
                lane="A",
            )


def test_no_live_authorization_no_network(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv("PROD_S1_CONFIRM_READONLY", raising=False)
    monkeypatch.delenv("CLERK_SECRET_KEY", raising=False)
    assert s1.main() == 2
    captured = capsys.readouterr()
    assert "OPERATOR_CONFIRMATION_MISSING" not in captured.out
    assert "MISSING_PROTECTED_CONFIG" in captured.err


def test_source_has_no_write_queries_or_clerk_mutations() -> None:
    source = Path(s1.__file__).read_text()
    assert "SET TRANSACTION READ ONLY" in source
    assert "await transaction.rollback()" in source
    assert "SELECT count(*) FROM users" in source
    assert "SELECT count(*) FROM tenants" in source
    assert "synthetic_acceptance" in source
    assert "A_TENANT_HAS_UNAUTHORIZED_PROJECTS" in source
    assert "name NOT LIKE 'ACCEPT-706-%'" in source
    assert "B_TENANT_NOT_EMPTY_SYNTHETIC" in source
    assert "client.get(" in source
    assert "client.post(" not in source
    assert "client.patch(" not in source
    assert "client.delete(" not in source


def test_production_credentials_are_step_scoped_and_browser_opt_in() -> None:
    """Never leak live Clerk/DB secrets into dependency install job environment."""
    workflow = (
        Path(__file__).resolve().parents[4]
        / ".github"
        / "workflows"
        / "prod-s1-clerk-identity-readonly.yml"
    ).read_text()
    assert "default: preflight_only" in workflow
    assert "if: inputs.mode == 'browser_readonly'" in workflow

    protected_job = workflow.split("  s1-identity-readonly:", 1)[1]
    job_header = protected_job.split("    steps:", 1)[0]
    assert "CLERK_SECRET_KEY:" not in job_header
    assert "PROD_ACCEPTANCE_DATABASE_URL_READONLY:" not in job_header

    setup = protected_job.split("      - name: Setup frontend toolchain for separately approved browser run", 1)[1]
    assert "if: inputs.mode == 'browser_readonly'" in setup.split("      - name:", 1)[0]
    browser = protected_job.split("      - name: Check real Clerk identities and B-to-A denial", 1)[1]
    assert "PROD_ACCEPTANCE_DATABASE_URL_READONLY:" not in browser.split("      - name:", 1)[0]
    assert "CLERK_SECRET_KEY:" in browser.split("      - name:", 1)[0]
