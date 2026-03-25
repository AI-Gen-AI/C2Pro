"""
Token revocation helpers.

Refers to Suite ID: TS-E2E-SEC-TNT-001.
"""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from threading import Lock

import jwt

_revoked_token_expirations: dict[str, datetime] = {}
_revocation_lock = Lock()


def _token_fingerprint(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def _cleanup_expired_tokens(now: datetime) -> None:
    expired = [
        fingerprint
        for fingerprint, expires_at in _revoked_token_expirations.items()
        if expires_at <= now
    ]
    for fingerprint in expired:
        _revoked_token_expirations.pop(fingerprint, None)


def revoke_token(token: str) -> None:
    payload = jwt.decode(token, options={"verify_signature": False, "verify_exp": False})
    expires_at = datetime.fromtimestamp(payload["exp"], tz=UTC)
    fingerprint = _token_fingerprint(token)
    now = datetime.now(UTC)

    with _revocation_lock:
        _cleanup_expired_tokens(now)
        _revoked_token_expirations[fingerprint] = expires_at


def is_token_revoked(token: str) -> bool:
    fingerprint = _token_fingerprint(token)
    now = datetime.now(UTC)

    with _revocation_lock:
        _cleanup_expired_tokens(now)
        expires_at = _revoked_token_expirations.get(fingerprint)
        return expires_at is not None and expires_at > now
