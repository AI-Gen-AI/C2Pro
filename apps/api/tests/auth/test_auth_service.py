"""
C2Pro - Authentication Service Unit Tests

Comprehensive tests for auth service including:
- Password hashing and verification
- JWT token generation and validation
- User registration and login flows
- Token refresh functionality
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4, UUID

from src.modules.auth.service import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_tenant_slug,
    get_user_by_email,
    get_user_by_id,
    AuthService,
)
from src.modules.auth.models import User, Tenant, UserRole, SubscriptionPlan
from src.modules.auth.schemas import RegisterRequest, LoginRequest
from src.core.exceptions import AuthenticationError, ConflictError, NotFoundError
from src.config import settings


# ===========================================
# PASSWORD HASHING TESTS
# ===========================================

class TestPasswordHashing:
    """Tests for password hashing and verification."""

    def test_hash_password_returns_different_hash_each_time(self):
        """
        Hash should be unique each time due to salt.
        """
        password = "MySecurePassword123!"

        hash1 = hash_password(password)
        hash2 = hash_password(password)

        # Hashes should be different (bcrypt uses random salt)
        assert hash1 != hash2
        # But both should be valid hashes
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)

    def test_hash_password_creates_bcrypt_hash(self):
        """
        Hash should start with bcrypt identifier.
        """
        password = "TestPassword123"
        hashed = hash_password(password)

        # Bcrypt hashes start with $2b$ or $2a$ or $2y$
        assert hashed.startswith("$2")
        # Should be a reasonable length (bcrypt hashes are 60 chars)
        assert len(hashed) == 60

    def test_verify_password_with_correct_password(self):
        """
        Verification should succeed with correct password.
        """
        password = "CorrectPassword123"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_with_incorrect_password(self):
        """
        Verification should fail with incorrect password.
        """
        password = "CorrectPassword123"
        wrong_password = "WrongPassword123"
        hashed = hash_password(password)

        assert verify_password(wrong_password, hashed) is False

    def test_verify_password_case_sensitive(self):
        """
        Password verification should be case-sensitive.
        """
        password = "CaseSensitive123"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True
        assert verify_password("casesensitive123", hashed) is False
        assert verify_password("CASESENSITIVE123", hashed) is False

    def test_hash_empty_password(self):
        """
        Should be able to hash empty password (though not recommended).
        """
        hashed = hash_password("")
        assert verify_password("", hashed) is True
        assert verify_password("a", hashed) is False


# ===========================================
# JWT TOKEN TESTS
# ===========================================

class TestJWTTokens:
    """Tests for JWT token creation and validation."""

    def test_create_access_token_contains_required_claims(self):
        """
        Access token should contain all required claims.
        """
        user_id = uuid4()
        tenant_id = uuid4()
        email = "test@example.com"
        role = UserRole.ADMIN

        token = create_access_token(
            user_id=user_id,
            tenant_id=tenant_id,
            email=email,
            role=role
        )

        # Decode without verification to inspect claims
        import jwt
        payload = jwt.decode(token, options={"verify_signature": False})

        assert payload["sub"] == str(user_id)
        assert payload["tenant_id"] == str(tenant_id)
        assert payload["email"] == email
        assert payload["role"] == role.value
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload

    def test_create_access_token_with_custom_expiry(self):
        """
        Access token should respect custom expiration time.
        """
        user_id = uuid4()
        tenant_id = uuid4()
        email = "test@example.com"
        role = UserRole.USER
        custom_delta = timedelta(minutes=60)

        token = create_access_token(
            user_id=user_id,
            tenant_id=tenant_id,
            email=email,
            role=role,
            expires_delta=custom_delta
        )

        import jwt
        payload = jwt.decode(token, options={"verify_signature": False})

        # Check that expiry is approximately 60 minutes from now
        exp_time = datetime.fromtimestamp(payload["exp"])
        iat_time = datetime.fromtimestamp(payload["iat"])
        delta = exp_time - iat_time

        # Should be 60 minutes (with small tolerance for execution time)
        assert 3550 <= delta.total_seconds() <= 3610  # 60 min ± 10 sec

    def test_create_refresh_token_structure(self):
        """
        Refresh token should have correct structure and type.
        """
        user_id = uuid4()
        token = create_refresh_token(user_id=user_id)

        import jwt
        payload = jwt.decode(token, options={"verify_signature": False})

        assert payload["sub"] == str(user_id)
        assert payload["type"] == "refresh"
        assert "exp" in payload
        assert "iat" in payload
        # Refresh token should not have tenant_id, email, role
        assert "tenant_id" not in payload
        assert "email" not in payload
        assert "role" not in payload

    def test_decode_token_with_valid_token(self):
        """
        Decoding valid token should return correct payload.
        """
        user_id = uuid4()
        tenant_id = uuid4()
        email = "decode@test.com"
        role = UserRole.VIEWER

        token = create_access_token(
            user_id=user_id,
            tenant_id=tenant_id,
            email=email,
            role=role
        )

        payload = decode_token(token)

        assert payload.sub == user_id
        assert payload.tenant_id == tenant_id
        assert payload.email == email
        assert payload.role == role

    def test_decode_token_with_invalid_signature(self):
        """
        Decoding token with wrong signature should raise AuthenticationError.
        """
        user_id = uuid4()
        tenant_id = uuid4()

        # Create token with different secret
        import jwt
        token = jwt.encode(
            {"sub": str(user_id), "tenant_id": str(tenant_id)},
            "wrong-secret-key",
            algorithm="HS256"
        )

        with pytest.raises(AuthenticationError, match="Invalid token"):
            decode_token(token)

    def test_decode_token_with_expired_token(self):
        """
        Decoding expired token should raise AuthenticationError.
        """
        user_id = uuid4()
        tenant_id = uuid4()
        email = "expired@test.com"
        role = UserRole.USER

        # Create token that expired 1 hour ago
        token = create_access_token(
            user_id=user_id,
            tenant_id=tenant_id,
            email=email,
            role=role,
            expires_delta=timedelta(hours=-1)
        )

        with pytest.raises(AuthenticationError, match="Invalid token"):
            decode_token(token)

    def test_decode_token_with_malformed_token(self):
        """
        Decoding malformed token should raise AuthenticationError.
        """
        with pytest.raises(AuthenticationError):
            decode_token("not-a-valid-jwt-token")

    def test_decode_token_with_missing_claims(self):
        """
        Token missing required claims should raise AuthenticationError.
        """
        import jwt

        # Token without tenant_id claim
        token = jwt.encode(
            {"sub": str(uuid4()), "email": "test@example.com"},
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm
        )

        with pytest.raises(AuthenticationError, match="Invalid token"):
            decode_token(token)


# ===========================================
# HELPER FUNCTION TESTS
# ===========================================

class TestHelperFunctions:
    """Tests for helper utility functions."""

    def test_generate_tenant_slug_basic(self):
        """
        Should generate valid slug from company name.
        """
        slug = generate_tenant_slug("My Test Company")

        assert slug.startswith("my-test-company-")
        assert len(slug) > len("my-test-company-")
        # Should be lowercase
        assert slug == slug.lower()
        # Should not have spaces
        assert " " not in slug

    def test_generate_tenant_slug_removes_special_characters(self):
        """
        Should remove special characters from slug.
        """
        slug = generate_tenant_slug("Company! @#$% Name")

        assert "!" not in slug
        assert "@" not in slug
        assert "#" not in slug
        assert "$" not in slug
        assert "%" not in slug

    def test_generate_tenant_slug_handles_multiple_spaces(self):
        """
        Should collapse multiple spaces into single hyphen.
        """
        slug = generate_tenant_slug("Test    Multiple    Spaces")

        # Should not have multiple hyphens in a row
        assert "--" not in slug

    def test_generate_tenant_slug_uniqueness(self):
        """
        Should generate unique slugs for same name.
        """
        slug1 = generate_tenant_slug("Test Company")
        slug2 = generate_tenant_slug("Test Company")

        # Should both start with same prefix
        assert slug1.startswith("test-company-")
        assert slug2.startswith("test-company-")

        # But should be different due to random suffix
        assert slug1 != slug2

    def test_generate_tenant_slug_with_unicode(self):
        """
        Should handle unicode characters.
        """
        slug = generate_tenant_slug("Empresa Española")

        # Should remove non-ASCII characters
        assert slug.isascii() or slug.replace("-", "").isascii()

    @pytest.mark.asyncio
    async def test_get_user_by_email_existing_user(self, db, test_user):
        """
        Should return user when email exists.
        """
        user = await get_user_by_email(db, test_user.email)

        assert user is not None
        assert user.id == test_user.id
        assert user.email == test_user.email

    @pytest.mark.asyncio
    async def test_get_user_by_email_non_existing(self, db):
        """
        Should return None when email doesn't exist.
        """
        user = await get_user_by_email(db, "nonexistent@example.com")

        assert user is None

    @pytest.mark.asyncio
    async def test_get_user_by_email_case_sensitivity(self, db, test_user):
        """
        Email lookup should be case-sensitive (depends on DB collation).
        """
        # Try with different case
        user = await get_user_by_email(db, test_user.email.upper())

        # This test depends on database collation settings
        # In most Postgres setups, email searches are case-insensitive
        # But this should be tested to confirm behavior
        if user:
            assert user.email.lower() == test_user.email.lower()

    @pytest.mark.asyncio
    async def test_get_user_by_id_existing_user(self, db, test_user):
        """
        Should return user when ID exists.
        """
        user = await get_user_by_id(db, test_user.id)

        assert user is not None
        assert user.id == test_user.id
        assert user.email == test_user.email

    @pytest.mark.asyncio
    async def test_get_user_by_id_non_existing(self, db):
        """
        Should return None when ID doesn't exist.
        """
        random_id = uuid4()
        user = await get_user_by_id(db, random_id)

        assert user is None


# ===========================================
# AUTH SERVICE - REGISTRATION TESTS
# ===========================================

class TestAuthServiceRegistration:
    """Tests for user registration functionality."""

    @pytest.mark.asyncio
    async def test_register_creates_user_and_tenant(self, db):
        """
        Registration should create both user and tenant.
        """
        request = RegisterRequest(
            email="newuser@example.com",
            password="SecurePass123!",
            first_name="John",
            last_name="Doe",
            company_name="Test Company Inc"
        )

        response = await AuthService.register(db, request)

        # Verify user created
        assert response.user.email == request.email
        assert response.user.first_name == request.first_name
        assert response.user.last_name == request.last_name
        assert response.user.role == UserRole.ADMIN  # First user is admin
        assert response.user.is_active is True

        # Verify tenant created
        assert response.tenant.name == request.company_name
        assert response.tenant.slug.startswith("test-company-inc-")
        assert response.tenant.subscription_plan == SubscriptionPlan.FREE
        assert response.tenant.is_active is True

        # Verify tokens generated
        assert response.tokens.access_token is not None
        assert response.tokens.refresh_token is not None
        assert response.tokens.token_type == "bearer"

    @pytest.mark.asyncio
    async def test_register_hashes_password(self, db):
        """
        Registration should hash the password, not store plain text.
        """
        request = RegisterRequest(
            email="hashtest@example.com",
            password="PlainTextPassword123",
            first_name="Hash",
            last_name="Test",
            company_name="Hash Company"
        )

        response = await AuthService.register(db, request)

        # Get user from database
        user = await get_user_by_email(db, request.email)

        # Password should be hashed
        assert user.hashed_password != request.password
        assert user.hashed_password.startswith("$2")  # bcrypt hash

        # Should verify correctly
        assert verify_password(request.password, user.hashed_password)

    @pytest.mark.asyncio
    async def test_register_with_duplicate_email(self, db, test_user):
        """
        Registration with existing email should raise ConflictError.
        """
        request = RegisterRequest(
            email=test_user.email,  # Email already exists
            password="SomePassword123",
            first_name="Duplicate",
            last_name="User",
            company_name="Duplicate Company"
        )

        with pytest.raises(ConflictError, match="Email already registered"):
            await AuthService.register(db, request)

    @pytest.mark.asyncio
    async def test_register_sets_correct_defaults(self, db):
        """
        Registration should set correct default values.
        """
        request = RegisterRequest(
            email="defaults@example.com",
            password="Pass123!",
            first_name="Default",
            last_name="User",
            company_name="Default Co"
        )

        response = await AuthService.register(db, request)

        # User defaults
        assert response.user.role == UserRole.ADMIN
        assert response.user.is_active is True
        assert response.user.is_verified is False  # Should require email verification

        # Tenant defaults
        assert response.tenant.subscription_plan == SubscriptionPlan.FREE
        assert response.tenant.subscription_status == "active"
        assert response.tenant.ai_spend_current == 0.0

    @pytest.mark.asyncio
    async def test_register_generates_valid_tokens(self, db):
        """
        Registration should generate valid JWT tokens.
        """
        request = RegisterRequest(
            email="tokens@example.com",
            password="TokenTest123",
            first_name="Token",
            last_name="User",
            company_name="Token Company"
        )

        response = await AuthService.register(db, request)

        # Access token should be decodable
        payload = decode_token(response.tokens.access_token)
        assert payload.email == request.email
        assert payload.role == UserRole.ADMIN

        # Refresh token should be valid JWT
        import jwt
        refresh_payload = jwt.decode(
            response.tokens.refresh_token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        assert refresh_payload["type"] == "refresh"

    @pytest.mark.asyncio
    async def test_register_updates_last_login(self, db):
        """
        Registration should set last_login timestamp.
        """
        request = RegisterRequest(
            email="login@example.com",
            password="Login123",
            first_name="Login",
            last_name="Test",
            company_name="Login Co"
        )

        before = datetime.utcnow()
        response = await AuthService.register(db, request)
        after = datetime.utcnow()

        # Get user to check last_login
        user = await get_user_by_email(db, request.email)
        assert user.last_login is not None
        assert before <= user.last_login <= after


# ===========================================
# AUTH SERVICE - LOGIN TESTS
# ===========================================

class TestAuthServiceLogin:
    """Tests for user login functionality."""

    @pytest.mark.asyncio
    async def test_login_with_valid_credentials(self, db, test_user, test_tenant):
        """
        Login should succeed with correct credentials.
        """
        request = LoginRequest(
            email=test_user.email,
            password="TestPassword123!"  # Password from test_user fixture
        )

        response = await AuthService.login(db, request)

        assert response.user.id == test_user.id
        assert response.user.email == test_user.email
        assert response.tenant.id == test_tenant.id
        assert response.tokens.access_token is not None
        assert response.tokens.refresh_token is not None

    @pytest.mark.asyncio
    async def test_login_with_invalid_email(self, db):
        """
        Login should fail with non-existent email.
        """
        request = LoginRequest(
            email="nonexistent@example.com",
            password="AnyPassword123"
        )

        with pytest.raises(AuthenticationError, match="Invalid credentials"):
            await AuthService.login(db, request)

    @pytest.mark.asyncio
    async def test_login_with_wrong_password(self, db, test_user):
        """
        Login should fail with incorrect password.
        """
        request = LoginRequest(
            email=test_user.email,
            password="WrongPassword123"
        )

        with pytest.raises(AuthenticationError, match="Invalid credentials"):
            await AuthService.login(db, request)

    @pytest.mark.asyncio
    async def test_login_with_inactive_user(self, db, test_user):
        """
        Login should fail if user account is inactive.
        """
        # Deactivate user
        test_user.is_active = False
        await db.commit()

        request = LoginRequest(
            email=test_user.email,
            password="TestPassword123!"
        )

        with pytest.raises(AuthenticationError, match="Account is inactive"):
            await AuthService.login(db, request)

    @pytest.mark.asyncio
    async def test_login_with_inactive_tenant(self, db, test_user, test_tenant):
        """
        Login should fail if tenant account is inactive.
        """
        # Deactivate tenant
        test_tenant.is_active = False
        await db.commit()

        request = LoginRequest(
            email=test_user.email,
            password="TestPassword123!"
        )

        with pytest.raises(AuthenticationError, match="Organization account is inactive"):
            await AuthService.login(db, request)

    @pytest.mark.asyncio
    async def test_login_updates_last_login(self, db, test_user):
        """
        Login should update last_login timestamp.
        """
        # Record current last_login
        old_last_login = test_user.last_login

        request = LoginRequest(
            email=test_user.email,
            password="TestPassword123!"
        )

        await AuthService.login(db, request)

        # Refresh user from database
        await db.refresh(test_user)

        # last_login should be updated
        assert test_user.last_login > old_last_login

    @pytest.mark.asyncio
    async def test_login_generates_valid_tokens(self, db, test_user):
        """
        Login should generate valid JWT tokens with user info.
        """
        request = LoginRequest(
            email=test_user.email,
            password="TestPassword123!"
        )

        response = await AuthService.login(db, request)

        # Decode and verify access token
        payload = decode_token(response.tokens.access_token)
        assert payload.sub == test_user.id
        assert payload.tenant_id == test_user.tenant_id
        assert payload.email == test_user.email
        assert payload.role == test_user.role


# ===========================================
# AUTH SERVICE - OTHER METHODS
# ===========================================

class TestAuthServiceOtherMethods:
    """Tests for get_current_user and refresh_access_token."""

    @pytest.mark.asyncio
    async def test_get_current_user_valid(self, db, test_user):
        """
        Should return user for valid user_id.
        """
        user = await AuthService.get_current_user(db, test_user.id)

        assert user.id == test_user.id
        assert user.email == test_user.email

    @pytest.mark.asyncio
    async def test_get_current_user_non_existent(self, db):
        """
        Should raise NotFoundError for non-existent user.
        """
        with pytest.raises(NotFoundError, match="User not found"):
            await AuthService.get_current_user(db, uuid4())

    @pytest.mark.asyncio
    async def test_get_current_user_inactive(self, db, test_user):
        """
        Should raise AuthenticationError for inactive user.
        """
        test_user.is_active = False
        await db.commit()

        with pytest.raises(AuthenticationError, match="Account is inactive"):
            await AuthService.get_current_user(db, test_user.id)

    @pytest.mark.asyncio
    async def test_get_current_user_updates_last_activity(self, db, test_user):
        """
        Should update last_activity timestamp.
        """
        old_last_activity = test_user.last_activity

        await AuthService.get_current_user(db, test_user.id)
        await db.refresh(test_user)

        # last_activity should be updated (or set if it was None)
        if old_last_activity:
            assert test_user.last_activity >= old_last_activity
        else:
            assert test_user.last_activity is not None

    @pytest.mark.asyncio
    async def test_refresh_access_token_valid(self, db, test_user):
        """
        Should generate new access token from valid refresh token.
        """
        # Create refresh token
        refresh_token = create_refresh_token(test_user.id)

        # Refresh access token
        response = await AuthService.refresh_access_token(db, refresh_token)

        assert response.access_token is not None
        assert response.token_type == "bearer"

        # Verify new access token
        payload = decode_token(response.access_token)
        assert payload.sub == test_user.id

    @pytest.mark.asyncio
    async def test_refresh_access_token_with_access_token(self, db, test_user, test_tenant):
        """
        Should fail when using access token instead of refresh token.
        """
        # Try to use access token for refresh (wrong token type)
        access_token = create_access_token(
            user_id=test_user.id,
            tenant_id=test_tenant.id,
            email=test_user.email,
            role=test_user.role
        )

        with pytest.raises(AuthenticationError, match="Invalid token type"):
            await AuthService.refresh_access_token(db, access_token)

    @pytest.mark.asyncio
    async def test_refresh_access_token_invalid_token(self, db):
        """
        Should fail with invalid refresh token.
        """
        with pytest.raises(AuthenticationError, match="Invalid refresh token"):
            await AuthService.refresh_access_token(db, "invalid-token")

    @pytest.mark.asyncio
    async def test_refresh_access_token_expired(self, db, test_user):
        """
        Should fail with expired refresh token.
        """
        import jwt

        # Create expired refresh token
        payload = {
            "sub": str(test_user.id),
            "type": "refresh",
            "exp": datetime.utcnow() - timedelta(hours=1),
            "iat": datetime.utcnow() - timedelta(hours=2)
        }

        expired_token = jwt.encode(
            payload,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm
        )

        with pytest.raises(AuthenticationError, match="Invalid refresh token"):
            await AuthService.refresh_access_token(db, expired_token)

    @pytest.mark.asyncio
    async def test_refresh_access_token_inactive_user(self, db, test_user):
        """
        Should fail if user is inactive.
        """
        refresh_token = create_refresh_token(test_user.id)

        # Deactivate user
        test_user.is_active = False
        await db.commit()

        with pytest.raises(AuthenticationError, match="Invalid token"):
            await AuthService.refresh_access_token(db, refresh_token)
