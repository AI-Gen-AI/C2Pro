"""
JWT Validation & Tenant Middleware Tests

Refers to Suite ID: TS-UC-SEC-JWT-001.
Refers to Suite ID: TS-UAD-HTTP-MDW-001.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import jwt as pyjwt
import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from src.core.auth.jwt_validator import JwtValidator
from src.core.auth.models import UserRole
from src.core.auth.service import create_access_token
from src.core.middleware import TenantIsolationMiddleware


class TestJwtValidation:
    """Refers to Suite ID: TS-UC-SEC-JWT-001."""

    @pytest.mark.asyncio
    async def test_expired_token_raises_401(self):
        """Expired token must raise 401."""
        public_key_provider = Mock()
        public_key_provider.get_public_key.return_value = "test-secret-key"
        validator = JwtValidator(public_key_provider=public_key_provider)

        expired_payload = {
            "sub": str(uuid4()),
            "tenant_id": str(uuid4()),
            "exp": datetime.now(UTC) - timedelta(seconds=1),
            "type": "access",
        }
        token = pyjwt.encode(expired_payload, "test-secret-key", algorithm="HS256")

        with pytest.raises(HTTPException) as exc_info:
            await validator.decode(token)

        assert exc_info.value.status_code == 401
        public_key_provider.get_public_key.assert_called_once()


class TestTenantMiddlewareHeaderExtraction:
    """Refers to Suite ID: TS-UAD-HTTP-MDW-001."""

    @pytest.fixture(autouse=True)
    def _bypass_tenant_db(self, monkeypatch):
        """Avoid hitting DB during middleware unit tests."""
        monkeypatch.setattr(
            TenantIsolationMiddleware,
            "_validate_tenant_exists",
            AsyncMock(return_value=True),
        )

    def test_jwt_tenant_id_is_injected_into_request_context(self):
        """JWT tenant_id populates request.state.tenant_id."""
        app = FastAPI()
        app.add_middleware(TenantIsolationMiddleware)

        @app.get("/protected")
        async def protected(request: Request):
            tenant_id = getattr(request.state, "tenant_id", None)
            return {"tenant_id": str(tenant_id) if tenant_id else None}

        client = TestClient(app)
        tenant_id = uuid4()
        user_id = uuid4()
        token = create_access_token(
            user_id=user_id,
            tenant_id=tenant_id,
            email="test@example.com",
            role=UserRole.ADMIN,
        )

        response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        assert response.json()["tenant_id"] == str(tenant_id)
