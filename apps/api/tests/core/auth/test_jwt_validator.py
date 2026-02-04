"""
JWT Validation & Tenant Middleware Tests (TDD - RED Phase)

Refers to Suite ID: TS-UC-SEC-JWT-001.
Refers to Suite ID: TS-UAD-HTTP-MDW-001.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request, HTTPException
from fastapi.testclient import TestClient
import jwt

from src.core.middleware import TenantIsolationMiddleware
from src.core.auth.jwt_validator import JwtValidator


class TestJwtValidation:
    """Refers to Suite ID: TS-UC-SEC-JWT-001."""

    def test_expired_token_raises_401(self, mocker):
        """
        RED: Expired token must raise 401.
        """
        public_key_provider = mocker.Mock()
        public_key_provider.get_public_key.return_value = "test-secret-key"
        validator = JwtValidator(public_key_provider=public_key_provider)

        expired_payload = {
            "sub": str(uuid4()),
            "tenant_id": str(uuid4()),
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
            "type": "access",
        }
        token = jwt.encode(expired_payload, "test-secret-key", algorithm="HS256")

        with pytest.raises(HTTPException) as exc_info:
            validator.decode(token)

        assert exc_info.value.status_code == 401
        public_key_provider.get_public_key.assert_called_once()


class TestTenantMiddlewareHeaderExtraction:
    """Refers to Suite ID: TS-UAD-HTTP-MDW-001."""

    def test_x_tenant_id_header_is_injected_into_request_context(self):
        """
        RED: X-Tenant-ID header should populate request.state.tenant_id.
        """
        app = FastAPI()
        app.add_middleware(TenantIsolationMiddleware)

        @app.get("/protected")
        async def protected(request: Request):
            tenant_id = getattr(request.state, "tenant_id", None)
            return {"tenant_id": str(tenant_id) if tenant_id else None}

        client = TestClient(app)
        tenant_id = uuid4()

        response = client.get("/protected", headers={"X-Tenant-ID": str(tenant_id)})

        assert response.status_code == 200
        assert response.json()["tenant_id"] == str(tenant_id)
