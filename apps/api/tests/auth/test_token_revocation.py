"""
Token Revocation Unit Tests
TS-E2E-SEC-TNT-001

Tests for token revocation security:
- Signature verification on revocation
- Invalid token rejection
- Proper fingerprint calculation
"""

import pytest
import jwt
from datetime import datetime, timedelta, UTC
from uuid import uuid4

from src.config import settings
from src.core.auth.token_revocation import (
    _memory_fallback,
    _memory_lock,
    revoke_token,
    is_token_revoked,
    _token_fingerprint,
    cleanup_expired_tokens,
)


class TestTokenRevocationSignatureVerification:
    """Tests that token revocation verifies JWT signatures."""

    def test_revoke_token_accepts_valid_signature(self):
        """
        Valid tokens with correct signature should be accepted for revocation.
        """
        payload = {
            "sub": str(uuid4()),
            "tenant_id": str(uuid4()),
            "exp": datetime.now(UTC) + timedelta(hours=1),
            "iat": datetime.now(UTC),
        }
        valid_token = jwt.encode(
            payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )

        revoke_token(valid_token)

        assert is_token_revoked(valid_token) is True

    def test_revoke_token_rejects_invalid_signature(self):
        """
        Tokens with invalid/corrupted signatures must be rejected.
        This prevents DoS attacks where attacker fills revocation list with fake tokens.
        """
        payload = {
            "sub": str(uuid4()),
            "tenant_id": str(uuid4()),
            "exp": datetime.now(UTC) + timedelta(hours=1),
            "iat": datetime.now(UTC),
        }
        invalid_token = jwt.encode(
            payload, "wrong-secret-key", algorithm=settings.jwt_algorithm
        )

        with pytest.raises(jwt.PyJWTError):
            revoke_token(invalid_token)

    def test_revoke_token_rejects_tampered_token(self):
        """
        Tampered tokens (modified after signing) must be rejected.
        """
        payload = {
            "sub": str(uuid4()),
            "tenant_id": str(uuid4()),
            "exp": datetime.now(UTC) + timedelta(hours=1),
            "iat": datetime.now(UTC),
        }
        valid_token = jwt.encode(
            payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )
        tampered_token = valid_token[:-10] + "tampered!!!"

        with pytest.raises(jwt.PyJWTError):
            revoke_token(tampered_token)

    def test_revoke_token_rejects_completely_fake_token(self):
        """
        Completely fabricated tokens must be rejected.
        """
        fake_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.fake"

        with pytest.raises(jwt.PyJWTError):
            revoke_token(fake_token)


class TestTokenFingerprint:
    """Tests for token fingerprint calculation."""

    def test_fingerprint_is_deterministic(self):
        """Same token should always produce same fingerprint."""
        token = "test-token-string"
        fp1 = _token_fingerprint(token)
        fp2 = _token_fingerprint(token)
        assert fp1 == fp2

    def test_fingerprint_is_different_for_different_tokens(self):
        """Different tokens should produce different fingerprints."""
        fp1 = _token_fingerprint("token-a")
        fp2 = _token_fingerprint("token-b")
        assert fp1 != fp2


class TestCleanupExpiredTokens:
    """Tests for expired token cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_removes_expired_tokens(self):
        """Expired tokens should be removed during cleanup."""

        now = datetime.now(UTC)
        with _memory_lock:
            _memory_fallback["expired_fp"] = now - timedelta(hours=1)
            _memory_fallback["valid_fp"] = now + timedelta(hours=1)

        cleaned_count = await cleanup_expired_tokens()

        assert cleaned_count == 1

        with _memory_lock:
            assert "expired_fp" not in _memory_fallback
            assert "valid_fp" in _memory_fallback
