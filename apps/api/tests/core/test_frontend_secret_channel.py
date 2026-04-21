"""TS-SEC-SECRET-CHANNEL-001.

Contract tests for secure Clerk secret channel endpoint.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.config import settings
from src.core.frontend_support.router import router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def test_secret_channel_rejects_invalid_token() -> None:
    client = _client()
    original_token = settings.secret_channel_token
    original_backend = settings.secret_channel_backend
    original_ref = settings.secret_channel_bundle_ref
    try:
        settings.secret_channel_token = "token-123"
        settings.secret_channel_backend = "env_json"
        settings.secret_channel_bundle_ref = '{"NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY":"pk_test_new"}'

        response = client.get("/api/v1/security/secret-channel/clerk", headers={"X-Secret-Channel-Token": "wrong"})

        assert response.status_code == 401
    finally:
        settings.secret_channel_token = original_token
        settings.secret_channel_backend = original_backend
        settings.secret_channel_bundle_ref = original_ref


def test_secret_channel_returns_redacted_bundle() -> None:
    client = _client()
    original_token = settings.secret_channel_token
    original_backend = settings.secret_channel_backend
    original_ref = settings.secret_channel_bundle_ref
    try:
        settings.secret_channel_token = "token-123"
        settings.secret_channel_backend = "env_json"
        settings.secret_channel_bundle_ref = (
            '{'
            '"NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY":"pk_test_new",'
            '"CLERK_SECRET_KEY":"sk_test_new",'
            '"CLERK_ISSUER":"https://issuer",'
            '"CLERK_JWKS_URL":"https://issuer/.well-known/jwks.json"'
            '}'
        )

        response = client.get(
            "/api/v1/security/secret-channel/clerk",
            headers={"X-Secret-Channel-Token": "token-123"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["values"]["NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY"] == "pk_test_new"
        assert payload["values"]["CLERK_ISSUER"] == "https://issuer"
        assert "CLERK_SECRET_KEY" not in payload["values"]
    finally:
        settings.secret_channel_token = original_token
        settings.secret_channel_backend = original_backend
        settings.secret_channel_bundle_ref = original_ref
