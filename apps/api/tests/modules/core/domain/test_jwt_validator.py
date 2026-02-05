"""
JWT validation domain tests.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import HTTPException

from src.core.auth.jwt_validator import JwtValidator


class _PublicKeyProvider:
    def __init__(self, key: str) -> None:
        self._key = key

    def get_public_key(self) -> str:
        return self._key


class TestJwtValidator:
    """Refers to Suite ID: TS-UC-SEC-JWT-001"""

    def test_001_valid_access_token_decodes(self) -> None:
        secret = "test-secret-key"
        validator = JwtValidator(public_key_provider=_PublicKeyProvider(secret))
        token = self._build_token(secret=secret)

        payload = validator.decode(token)

        assert payload.sub == UUID("11111111-1111-1111-1111-111111111111")
        assert payload.tenant_id == UUID("22222222-2222-2222-2222-222222222222")
        assert payload.token_type == "access"

    def test_002_expired_token_raises_401(self) -> None:
        secret = "test-secret-key"
        validator = JwtValidator(public_key_provider=_PublicKeyProvider(secret))
        token = self._build_token(secret=secret, expires_delta=timedelta(seconds=-5))

        with pytest.raises(HTTPException, match="Token has expired"):
            validator.decode(token)

    def test_003_invalid_signature_raises_401(self) -> None:
        validator = JwtValidator(public_key_provider=_PublicKeyProvider("real-secret"))
        token = self._build_token(secret="other-secret")

        with pytest.raises(HTTPException, match="Invalid authentication credentials"):
            validator.decode(token)

    def test_004_malformed_token_raises_401(self) -> None:
        validator = JwtValidator(public_key_provider=_PublicKeyProvider("real-secret"))

        with pytest.raises(HTTPException, match="Invalid authentication credentials"):
            validator.decode("not.a.valid.jwt")

    def test_005_missing_tenant_id_raises_401(self) -> None:
        secret = "test-secret-key"
        validator = JwtValidator(public_key_provider=_PublicKeyProvider(secret))
        token = self._build_token(secret=secret, include_tenant=False)

        with pytest.raises(HTTPException, match="Missing tenant_id in token"):
            validator.decode(token)

    def test_006_missing_sub_raises_401(self) -> None:
        secret = "test-secret-key"
        validator = JwtValidator(public_key_provider=_PublicKeyProvider(secret))
        token = self._build_token(secret=secret, include_sub=False)

        with pytest.raises(HTTPException, match="Missing sub in token"):
            validator.decode(token)

    def test_007_invalid_uuid_claim_raises_401(self) -> None:
        secret = "test-secret-key"
        validator = JwtValidator(public_key_provider=_PublicKeyProvider(secret))
        token = self._build_token(secret=secret, sub="not-a-uuid")

        with pytest.raises(HTTPException, match="Invalid authentication credentials"):
            validator.decode(token)

    def test_008_wrong_token_type_for_access_raises_401(self) -> None:
        secret = "test-secret-key"
        validator = JwtValidator(public_key_provider=_PublicKeyProvider(secret))
        token = self._build_token(secret=secret, token_type="refresh")

        with pytest.raises(HTTPException, match="Invalid token type"):
            validator.decode(token, expected_token_type="access")

    def test_009_refresh_token_allowed_when_expected_type_refresh(self) -> None:
        secret = "test-secret-key"
        validator = JwtValidator(public_key_provider=_PublicKeyProvider(secret))
        token = self._build_token(secret=secret, token_type="refresh")

        payload = validator.decode(token, expected_token_type="refresh")

        assert payload.token_type == "refresh"

    def test_010_missing_bearer_header_raises_401(self) -> None:
        validator = JwtValidator(public_key_provider=_PublicKeyProvider("test-secret-key"))

        with pytest.raises(HTTPException, match="Invalid authentication credentials"):
            validator.decode_authorization_header("Token abc")

    def test_011_decode_authorization_header_valid(self) -> None:
        secret = "test-secret-key"
        validator = JwtValidator(public_key_provider=_PublicKeyProvider(secret))
        token = self._build_token(secret=secret)

        payload = validator.decode_authorization_header(f"Bearer {token}")

        assert payload.tenant_id == UUID("22222222-2222-2222-2222-222222222222")

    def test_012_empty_token_raises_401(self) -> None:
        validator = JwtValidator(public_key_provider=_PublicKeyProvider("test-secret-key"))
        with pytest.raises(HTTPException, match="Invalid authentication credentials"):
            validator.decode("")

    @staticmethod
    def _build_token(
        secret: str,
        expires_delta: timedelta = timedelta(minutes=10),
        token_type: str = "access",
        include_tenant: bool = True,
        include_sub: bool = True,
        sub: str | None = None,
    ) -> str:
        now = datetime.now(timezone.utc)
        payload: dict[str, object] = {
            "exp": now + expires_delta,
            "iat": now,
            "type": token_type,
        }
        if include_sub:
            payload["sub"] = sub or str(uuid4()) if sub else "11111111-1111-1111-1111-111111111111"
        if include_tenant:
            payload["tenant_id"] = "22222222-2222-2222-2222-222222222222"
        return jwt.encode(payload, secret, algorithm="HS256")
