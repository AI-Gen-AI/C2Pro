"""
JWT validation helper for security use cases.

Refers to Suite ID: TS-UC-SEC-JWT-001.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

import jwt
from fastapi import HTTPException


class PublicKeyProvider(Protocol):
    """Refers to Suite ID: TS-UC-SEC-JWT-001."""

    def get_public_key(self) -> str: ...


@dataclass(frozen=True)
class JWTClaims:
    """Refers to Suite ID: TS-UC-SEC-JWT-001."""

    sub: UUID
    tenant_id: UUID
    token_type: str
    exp: datetime
    iat: datetime | None = None


class JwtValidator:
    """Refers to Suite ID: TS-UC-SEC-JWT-001."""

    def __init__(
        self,
        public_key_provider: PublicKeyProvider,
        algorithm: str = "HS256",
    ) -> None:
        self._public_key_provider = public_key_provider
        self._algorithm = algorithm

    def decode(self, token: str, expected_token_type: str = "access") -> JWTClaims:
        if not token:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        key = self._public_key_provider.get_public_key()
        try:
            payload = jwt.decode(token, key, algorithms=[self._algorithm])
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.PyJWTError:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        sub_value = payload.get("sub")
        if not sub_value:
            raise HTTPException(status_code=401, detail="Missing sub in token")
        tenant_value = payload.get("tenant_id")
        if not tenant_value:
            raise HTTPException(status_code=401, detail="Missing tenant_id in token")

        token_type = str(payload.get("type") or "")
        if expected_token_type and token_type != expected_token_type:
            raise HTTPException(status_code=401, detail="Invalid token type")

        try:
            sub_uuid = UUID(str(sub_value))
            tenant_uuid = UUID(str(tenant_value))
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        exp_raw = payload.get("exp")
        exp_dt = datetime.fromtimestamp(exp_raw) if isinstance(exp_raw, (int, float)) else exp_raw
        iat_raw = payload.get("iat")
        iat_dt = datetime.fromtimestamp(iat_raw) if isinstance(iat_raw, (int, float)) else iat_raw
        return JWTClaims(
            sub=sub_uuid,
            tenant_id=tenant_uuid,
            token_type=token_type,
            exp=exp_dt,
            iat=iat_dt,
        )

    def decode_authorization_header(
        self,
        authorization_header: str,
        expected_token_type: str = "access",
    ) -> JWTClaims:
        if not authorization_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        token = authorization_header[7:].strip()
        return self.decode(token=token, expected_token_type=expected_token_type)
