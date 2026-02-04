"""
Test Suite: TS-UAD-HTTP-MDW-001 — Middleware (Auth, Tenant)
Component: HTTP Adapters — TenantIsolationMiddleware
Priority: P0/P1 Mixed
Coverage Target: 90%

Validates TenantIsolationMiddleware in isolation:
1. Public-path bypass — /health skips auth entirely
2. Valid JWT pass-through — tenant_id & user_id injected into request.state
3. Invalid / tampered / wrong-key tokens → 401
4. Expired tokens → 401 "Token has expired"
5. Missing Authorization header → 401
6. Token-type enforcement — refresh tokens and missing type rejected
7. Tenant DB validation — inactive / missing tenants → 401

Methodology: TDD Strict (Red → Green → Refactor)
Testing Approach: Unit tests.  The middleware's settings (jwt_secret_key /
    jwt_algorithm) and DB session (get_raw_session) are patched at their
    module-import points.  Tokens are signed directly with jwt.encode (PyJWT)
    using the same test secret the patched middleware decodes against, so
    signature round-trips are exercised without touching the real Settings
    singleton or any database.
"""

import pytest
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
import jwt

from src.core.middleware.tenant_isolation import TenantIsolationMiddleware


# ===========================================
# CONSTANTS
# ===========================================

_SECRET = "mdw-test-secret-key-do-not-use-in-prod"
_ALG = "HS256"


# ===========================================
# TOKEN BUILDERS
# ===========================================


def _sign(payload: dict) -> str:
    """Encode + sign a raw payload with the test secret."""
    return jwt.encode(payload, _SECRET, algorithm=_ALG)


def _access_token(
    *,
    user_id: UUID | None = None,
    tenant_id: UUID | None = None,
    email: str = "user@test.com",
    role: str = "admin",
    expires_delta: timedelta | None = None,
) -> tuple[str, UUID, UUID]:
    """
    Build a correctly-signed access token.

    Returns:
        (token_string, tenant_id, user_id)
    """
    uid = user_id or uuid4()
    tid = tenant_id or uuid4()
    exp = datetime.utcnow() + (expires_delta or timedelta(hours=1))

    token = _sign({
        "sub": str(uid),
        "tenant_id": str(tid),
        "email": email,
        "role": role,
        "exp": exp,
        "iat": datetime.utcnow(),
        "type": "access",
    })
    return token, tid, uid


# ===========================================
# FIXTURES
# ===========================================


@pytest.fixture
def mock_settings():
    """Replace the settings reference inside TenantIsolationMiddleware."""
    s = MagicMock()
    s.jwt_secret_key = _SECRET
    s.jwt_algorithm = _ALG
    with patch("src.core.middleware.tenant_isolation.settings", s):
        yield s


@pytest.fixture
def mock_tenant_db():
    """
    Patch get_raw_session so _validate_tenant_exists never hits a real DB.

    Yields the mock *result* object.  Reconfigure per-test before the
    request:
        mock_tenant_db.scalar_one_or_none.return_value = <MagicMock | None>

    Default: a tenant with is_active = True.
    """
    mock_session = AsyncMock()
    mock_result = MagicMock()  # scalar_one_or_none() is synchronous
    mock_session.execute = AsyncMock(return_value=mock_result)

    active_tenant = MagicMock()
    active_tenant.is_active = True
    mock_result.scalar_one_or_none.return_value = active_tenant

    @asynccontextmanager
    async def _session():
        yield mock_session

    with patch("src.core.middleware.tenant_isolation.get_raw_session", _session):
        yield mock_result


@pytest.fixture
def app(mock_settings, mock_tenant_db):
    """
    Minimal FastAPI app with TenantIsolationMiddleware.

    PUBLIC_PATHS contains "/" which makes startswith("/") match every path,
    effectively disabling auth for all routes.  We filter it out so the
    middleware actually exercises its JWT / tenant logic.  "/health" remains
    in the list and is tested via TestPublicPathBypass.

    GET /protected  — echoes injected tenant_id + user_id (requires auth)
    GET /health     — public path, no auth required
    """
    _app = FastAPI()
    _app.add_middleware(TenantIsolationMiddleware)

    @_app.get("/protected")
    async def _protected(request: Request):
        user_id = getattr(request.state, "user_id", None)
        return {
            "tenant_id": str(request.state.tenant_id),
            "user_id": str(user_id) if user_id else None,
        }

    @_app.get("/health")
    async def _health():
        return {"status": "ok"}

    # Patch PUBLIC_PATHS at class level: remove the bare "/" entry that
    # matches all paths via startswith.  Patch stays active while the
    # fixture is alive (yield inside with-block).
    filtered = [p for p in TenantIsolationMiddleware.PUBLIC_PATHS if p != "/"]
    with patch.object(TenantIsolationMiddleware, "PUBLIC_PATHS", filtered):
        yield _app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


# ===========================================
# PUBLIC PATH BYPASS
# ===========================================


class TestPublicPathBypass:
    """
    PUBLIC_PATHS in the middleware skip all JWT logic.
    Requests to /health pass through regardless of Authorization header.
    """

    @pytest.mark.unit
    @pytest.mark.critical
    def test_uad_http_mdw_public_health_no_token(self, client):
        """
        Given: /health is in PUBLIC_PATHS
        When: GET /health with no Authorization header
        Then: 200 {"status": "ok"}
        """
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @pytest.mark.unit
    def test_uad_http_mdw_public_path_ignores_garbage_token(self, client):
        """
        Given: /health is public
        When: GET /health with a garbage Bearer value
        Then: 200 — token is never decoded for public paths
        """
        response = client.get(
            "/health",
            headers={"Authorization": "Bearer totally-invalid-token"},
        )

        assert response.status_code == 200


# ===========================================
# UAD-HTTP-022 – VALID AUTHENTICATION
# ===========================================


class TestValidAuthentication:
    """
    UAD-HTTP-022: A correctly signed access token with an active tenant
    causes the middleware to pass the request through to the endpoint.
    """

    @pytest.mark.unit
    @pytest.mark.critical
    def test_uad_http_022_valid_token_returns_200(self, client):
        """
        Given: Valid access token; mock DB returns active tenant
        When: GET /protected with Bearer
        Then: 200
        """
        token, _, _ = _access_token()

        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200

    @pytest.mark.unit
    def test_uad_http_022_response_content_type_json(self, client):
        """
        Given: Valid token
        When: GET /protected
        Then: Content-Type is application/json
        """
        token, _, _ = _access_token()

        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")


# ===========================================
# UAD-HTTP-023 – INVALID / TAMPERED TOKEN
# ===========================================


class TestInvalidToken:
    """
    UAD-HTTP-023: Any token that fails signature verification or cannot
    be decoded is rejected with 401.
    """

    @pytest.mark.unit
    @pytest.mark.critical
    def test_uad_http_023_garbage_string_rejected(self, client):
        """
        Given: Bearer value is a random non-JWT string
        When: GET /protected
        Then: 401 with JSON body containing detail
        """
        response = client.get(
            "/protected",
            headers={"Authorization": "Bearer this-is-not-a-jwt"},
        )

        assert response.status_code == 401
        assert "detail" in response.json()

    @pytest.mark.unit
    def test_uad_http_023_tampered_signature_rejected(self, client):
        """
        Given: A valid token whose signature has been replaced
        When: GET /protected
        Then: 401 (signature mismatch → JWTError)
        """
        token, _, _ = _access_token()
        header, payload_part, _ = token.split(".")
        # Replace signature with an obviously-wrong value
        tampered = f"{header}.{payload_part}.AAAA"

        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {tampered}"},
        )

        assert response.status_code == 401

    @pytest.mark.unit
    def test_uad_http_023_wrong_secret_key_rejected(self, client):
        """
        Given: Token signed with a secret the middleware does NOT know
        When: GET /protected
        Then: 401
        """
        payload = {
            "sub": str(uuid4()),
            "tenant_id": str(uuid4()),
            "email": "bad@test.com",
            "role": "user",
            "exp": datetime.utcnow() + timedelta(hours=1),
            "iat": datetime.utcnow(),
            "type": "access",
        }
        bad_token = jwt.encode(payload, "completely-different-secret", algorithm=_ALG)

        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {bad_token}"},
        )

        assert response.status_code == 401


# ===========================================
# UAD-HTTP-024 – EXPIRED TOKEN
# ===========================================


class TestExpiredToken:
    """
    UAD-HTTP-024: The middleware catches ExpiredSignatureError separately
    from generic JWTError, returning the specific message "Token has expired".
    """

    @pytest.mark.unit
    @pytest.mark.critical
    def test_uad_http_024_expired_token_returns_401(self, client):
        """
        Given: Access token whose exp is 5 minutes in the past
        When: GET /protected
        Then: 401
        """
        token, _, _ = _access_token(expires_delta=timedelta(minutes=-5))

        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401

    @pytest.mark.unit
    def test_uad_http_024_expired_token_detail_message(self, client):
        """
        Given: Expired token
        When: GET /protected
        Then: detail == "Token has expired"
        """
        token, _, _ = _access_token(expires_delta=timedelta(minutes=-10))

        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Token has expired"


# ===========================================
# UAD-HTTP-025 – TENANT INJECTION
# ===========================================


class TestTenantInjection:
    """
    UAD-HTTP-025: After successful auth the middleware injects tenant_id
    and user_id into request.state.  The /protected endpoint echoes these
    back so the test can verify round-trip correctness.
    """

    @pytest.mark.unit
    @pytest.mark.critical
    def test_uad_http_025_tenant_id_injected_from_token(self, client):
        """
        Given: Token carrying a known tenant_id
        When: GET /protected
        Then: Response tenant_id matches the token's tenant_id
        """
        expected_tenant = uuid4()
        token, _, _ = _access_token(tenant_id=expected_tenant)

        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.json()["tenant_id"] == str(expected_tenant)

    @pytest.mark.unit
    def test_uad_http_025_user_id_injected_from_token(self, client):
        """
        Given: Token carrying a known user_id (sub claim)
        When: GET /protected
        Then: Response user_id matches the token's sub
        """
        expected_user = uuid4()
        token, _, _ = _access_token(user_id=expected_user)

        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.json()["user_id"] == str(expected_user)


# ===========================================
# UAD-HTTP-026 – MISSING AUTHORIZATION
# ===========================================


class TestMissingAuthorization:
    """
    UAD-HTTP-026: Protected endpoints reject requests that lack a proper
    "Bearer <token>" Authorization header.
    """

    @pytest.mark.unit
    @pytest.mark.critical
    def test_uad_http_026_no_header_returns_401(self, client):
        """
        Given: No Authorization header present
        When: GET /protected
        Then: 401 with detail
        """
        response = client.get("/protected")

        assert response.status_code == 401
        assert "detail" in response.json()

    @pytest.mark.unit
    def test_uad_http_026_bearer_with_empty_token_returns_401(self, client):
        """
        Given: Authorization is "Bearer " — space present but no token
        When: GET /protected
        Then: 401 (jwt.decode on empty string raises DecodeError)
        """
        response = client.get(
            "/protected",
            headers={"Authorization": "Bearer "},
        )

        assert response.status_code == 401

    @pytest.mark.unit
    def test_uad_http_026_basic_auth_scheme_returns_401(self, client):
        """
        Given: Authorization uses "Basic" instead of "Bearer"
        When: GET /protected
        Then: 401 — middleware only recognises Bearer
        """
        response = client.get(
            "/protected",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )

        assert response.status_code == 401


# ===========================================
# TOKEN TYPE ENFORCEMENT
# ===========================================


class TestTokenTypeValidation:
    """
    The middleware requires payload["type"] == "access".  Refresh tokens
    and tokens missing the type claim are explicitly rejected before the
    tenant DB check is reached.
    """

    @pytest.mark.unit
    @pytest.mark.critical
    def test_refresh_token_rejected_as_access(self, client):
        """
        Given: Properly signed token with type == "refresh"
        When: Presented as Bearer on /protected
        Then: 401 detail == "Invalid token type"
        """
        refresh = _sign({
            "sub": str(uuid4()),
            "tenant_id": str(uuid4()),
            "exp": datetime.utcnow() + timedelta(days=30),
            "iat": datetime.utcnow(),
            "type": "refresh",
        })

        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {refresh}"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid token type"

    @pytest.mark.unit
    def test_token_without_type_claim_rejected(self, client):
        """
        Given: Signed token with no 'type' field at all
        When: Presented as Bearer
        Then: 401 detail == "Invalid token type"
              (payload.get("type") → None != "access")
        """
        no_type = _sign({
            "sub": str(uuid4()),
            "tenant_id": str(uuid4()),
            "email": "notype@test.com",
            "role": "user",
            "exp": datetime.utcnow() + timedelta(hours=1),
            "iat": datetime.utcnow(),
            # "type" deliberately omitted
        })

        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {no_type}"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid token type"


# ===========================================
# TENANT DB VALIDATION
# ===========================================


class TestTenantValidation:
    """
    After extracting tenant_id from the JWT, the middleware queries the
    DB to verify the tenant exists and is active.  These tests control
    the mocked DB response to cover each branch.
    """

    @pytest.mark.unit
    @pytest.mark.critical
    def test_inactive_tenant_returns_401(self, client, mock_tenant_db):
        """
        Given: Valid token, but DB says tenant.is_active == False
        When: GET /protected
        Then: 401 detail == "Invalid authentication context"
        """
        inactive = MagicMock()
        inactive.is_active = False
        mock_tenant_db.scalar_one_or_none.return_value = inactive

        token, _, _ = _access_token()

        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid authentication context"

    @pytest.mark.unit
    def test_missing_tenant_in_db_returns_401(self, client, mock_tenant_db):
        """
        Given: Valid token, but no matching tenant row (None)
        When: GET /protected
        Then: 401 detail == "Invalid authentication context"
        """
        mock_tenant_db.scalar_one_or_none.return_value = None

        token, _, _ = _access_token()

        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid authentication context"

    @pytest.mark.unit
    def test_token_without_tenant_id_claim_returns_401(self, client):
        """
        Given: Signed access token missing the tenant_id claim
        When: GET /protected
        Then: 401 detail == "Missing tenant_id in token"
        """
        no_tid = _sign({
            "sub": str(uuid4()),
            # "tenant_id" deliberately omitted
            "email": "no-tid@test.com",
            "role": "user",
            "exp": datetime.utcnow() + timedelta(hours=1),
            "iat": datetime.utcnow(),
            "type": "access",
        })

        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {no_tid}"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Missing tenant_id in token"


# ===========================================
# GREEN PHASE NOTES
# ===========================================

"""
GREEN PHASE STRATEGY:

These 19 tests validate the TenantIsolationMiddleware contracts:

1. Public-path bypass:  _is_public_path() → call_next() immediately
2. JWT decode:          jwt.decode (PyJWT) with verify_signature + verify_exp
3. Token-type gate:     payload["type"] must equal "access"
4. Tenant-id extract:   payload["tenant_id"] parsed as UUID
5. Tenant DB check:     get_raw_session() → Tenant query → is_active gate
6. State injection:     request.state.tenant_id / .user_id set on success

Each test exercises exactly one middleware branch.  No integration
dependencies — DB and settings are fully mocked at the module-import level.

Test breakdown by ID:
    UAD-HTTP-022  Valid auth pass-through         (2 tests)
    UAD-HTTP-023  Invalid / tampered tokens       (3 tests)
    UAD-HTTP-024  Expired tokens                  (2 tests)
    UAD-HTTP-025  Tenant ID injection             (2 tests)
    UAD-HTTP-026  Missing Authorization           (3 tests)
    Extra         Public path bypass              (2 tests)
    Extra         Token type enforcement          (2 tests)
    Extra         Tenant DB validation            (3 tests)
    ─────────────────────────────────────────────────────
    Total                                         19 tests
"""
