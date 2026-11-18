"""#1274: HTTP platform route denies non-owner identities without connecting to UAT.

The Clerk verifier is mocked; no signed token or secret from any environment
is used. This is an HTTP boundary test, not an IdP integration proof.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.admin.adapters.http.platform_budget_router import router
from src.config import settings
from src.core.auth import platform_operator
from src.core.middleware import tenant_isolation


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "platform_operator_org_id", "org_private_fixture")
    monkeypatch.setattr(settings, "platform_operator_user_ids", ["user_fixture_owner"])
    monkeypatch.setattr(settings, "platform_budget_read_database_url", None)
    monkeypatch.setattr(
        platform_operator,
        "operator_org_is_contaminated",
        AsyncMock(return_value=False),
    )
    verified = AsyncMock(return_value={
        "sub": "user_fixture_owner", "org_id": "org_private_fixture",
        "email": "test@example.invalid", "email_verified": True,
    })
    monkeypatch.setattr(tenant_isolation, "verify_clerk_token", verified)

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.add_middleware(tenant_isolation.TenantIsolationMiddleware)

    # A fake HS512 header exercises route classification and the mocked Clerk
    # gate; an actual verifier would reject the fake signature.
    token = jwt.encode({"sub": "untrusted"}, "fixture-only-key", algorithm="HS512")
    with TestClient(app) as http:
        yield http, verified, {"Authorization": f"Bearer {token}"}


def test_anonymous_denied_without_database_access(client) -> None:
    http, verified, _ = client
    response = http.get("/api/v1/platform/budgets")
    assert response.status_code == 401
    assert verified.await_count == 0


def test_owner_without_dedicated_budget_capability_gets_503(client) -> None:
    http, verified, auth = client
    response = http.get("/api/v1/platform/budgets", headers=auth)
    assert response.status_code == 503
    assert response.json()["detail"] == "Budget read capability unavailable"
    assert verified.await_count == 1


@pytest.mark.parametrize("claims", [
    # Customer org admin/forged token flag is not authority for platform reads.
    {"sub": "user_customer_admin", "org_id": "org_customer",
     "email_verified": True, "org_role": "admin", "platform_operator": True},
    # Operator-org membership alone is insufficient without owner allowlist.
    {"sub": "user_other_org_member", "org_id": "org_private_fixture",
     "email_verified": True, "org_role": "admin"},
    # Fake owner ID bound to another Clerk org is still denied.
    {"sub": "user_fixture_owner", "org_id": "org_customer",
     "email_verified": True},
    # Email must not substitute for verified user ID.
    {"sub": "user_wrong", "org_id": "org_private_fixture",
     "email": "test@example.invalid", "email_verified": True},
    # Verified email required even for pinned user.
    {"sub": "user_fixture_owner", "org_id": "org_private_fixture",
     "email_verified": False},
])
def test_unauthorized_claims_denied_403(client, claims) -> None:
    http, verified, auth = client
    verified.return_value = claims
    response = http.get("/api/v1/platform/budgets", headers=auth)
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized"


def test_revoked_or_unverifiable_session_denied_401(client) -> None:
    http, verified, auth = client
    verified.side_effect = ValueError("synthetic verifier refusal")
    response = http.get("/api/v1/platform/budgets", headers=auth)
    assert response.status_code == 401


def test_missing_owner_allowlist_is_denied(client, monkeypatch: pytest.MonkeyPatch) -> None:
    http, _, auth = client
    monkeypatch.setattr(settings, "platform_operator_user_ids", [])
    response = http.get("/api/v1/platform/budgets", headers=auth)
    assert response.status_code == 403


def test_no_mutating_route_is_mounted(client) -> None:
    http, _, auth = client
    for method in ("POST", "PATCH", "PUT", "DELETE"):
        response = http.request(method, "/api/v1/platform/budgets", headers=auth)
        assert response.status_code in {401, 403, 404, 405}
        assert response.status_code != 200
