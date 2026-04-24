"""
Token Revocation Unit Tests
TS-E2E-SEC-TNT-001

Tests for token revocation security:
- Signature verification on revocation
- Invalid token rejection
- Proper fingerprint calculation
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
import pytest_asyncio

from src.config import settings
from src.core.auth.token_revocation import (
    _memory_fallback,
    _memory_lock,
    _token_fingerprint,
    cleanup_expired_tokens,
    is_token_revoked,
    is_token_revoked_async,  # Imported for async tests
    revoke_token,
    revoke_token_async,  # Imported for async tests
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


# --- New Async Redis Tests (TASK-ARCH-009) ---
class TestTokenRevocationRedisAsync:
    """Tests for async Redis-backed token revocation."""

    @pytest_asyncio.fixture(autouse=True)
    def setup_mocker(self, mocker):
        self.mock_redis = mocker.AsyncMock()
        mocker.patch('src.core.cache.CacheService._redis', new_callable=mocker.PropertyMock, return_value=self.mock_redis)
        mocker.patch('src.core.cache.get_cache_service', return_value=mocker.Mock(_redis=self.mock_redis)) # Patch get_cache_service
        # Ensure in-memory fallback is clean for each test
        with _memory_lock:
            _memory_fallback.clear()

    @pytest.mark.asyncio
    async def test_revoke_token_async_uses_redis(self, mocker):
        payload = {
            "sub": str(uuid4()),
            "exp": datetime.now(UTC) + timedelta(hours=1),
            "iat": datetime.now(UTC),
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        fingerprint = _token_fingerprint(token)

        await revoke_token_async(token)

        self.mock_redis.set.assert_called_once_with(
            f"revoked_token:{fingerprint}", "1", ex=mocker.ANY  # Check 'ex' is passed
        )
        # Ensure we check Redis before falling back to memory
        self.mock_redis.exists.return_value = True
        assert await is_token_revoked_async(token) is True

    @pytest.mark.asyncio
    async def test_is_token_revoked_async_checks_redis(self):
        payload = {
            "sub": str(uuid4()),
            "exp": datetime.now(UTC) + timedelta(hours=1),
            "iat": datetime.now(UTC),
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        fingerprint = _token_fingerprint(token)

        self.mock_redis.exists.return_value = True

        assert await is_token_revoked_async(token) is True
        self.mock_redis.exists.assert_called_once_with(f"revoked_token:{fingerprint}")

    @pytest.mark.asyncio
    async def test_is_token_revoked_async_falls_back_to_memory_if_redis_fails(self, mocker):
        payload = {
            "sub": str(uuid4()),
            "exp": datetime.now(UTC) + timedelta(hours=1),
            "iat": datetime.now(UTC),
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        fingerprint = _token_fingerprint(token)

        # Simulate Redis failure by raising an exception on exists call
        self.mock_redis.exists.side_effect = Exception("Redis connection error")

        with _memory_lock:
            _memory_fallback[fingerprint] = datetime.now(UTC) + timedelta(hours=1)

        assert await is_token_revoked_async(token) is True
        assert self.mock_redis.exists.called # Redis was attempted

    @pytest.mark.asyncio
    async def test_revoke_token_async_falls_back_to_memory_if_redis_fails(self, mocker):
        payload = {
            "sub": str(uuid4()),
            "exp": datetime.now(UTC) + timedelta(hours=1),
            "iat": datetime.now(UTC),
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        fingerprint = _token_fingerprint(token)

        # Simulate Redis failure by raising an exception on set call
        self.mock_redis.set.side_effect = Exception("Redis connection error")

        await revoke_token_async(token)

        with _memory_lock:
            assert fingerprint in _memory_fallback
            assert _memory_fallback[fingerprint] > datetime.now(UTC) - timedelta(minutes=1) # Ensure expiry is in the future
        assert self.mock_redis.set.called # Redis was attempted
