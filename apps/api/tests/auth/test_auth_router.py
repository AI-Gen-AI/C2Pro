"""
C2Pro - Auth Router Integration Tests

Integration tests for authentication API endpoints.
Tests the complete request-response cycle including middleware,
routing, service layer, and database operations.
"""

import pytest
import pytest_asyncio
from fastapi import status
from fastapi.testclient import TestClient
from uuid import uuid4

from src.main import app
from src.core.database import get_session
from src.modules.auth.models import User, Tenant, UserRole, SubscriptionPlan
from src.modules.auth.service import hash_password


# ===========================================
# CONSTANTS
# ===========================================

API_PREFIX = "/api/v1"


# ===========================================
# TEST CLIENT SETUP
# ===========================================

@pytest.fixture
def simple_client():
    """Create FastAPI test client for tests that don't need database."""
    return TestClient(app, raise_server_exceptions=False)


@pytest_asyncio.fixture
async def client(db):
    """Create FastAPI test client with database dependency override."""
    async def override_get_session():
        """Override database session for testing."""
        yield db

    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(generate_token, test_user, test_tenant):
    """Generate authorization headers with valid JWT token."""
    token = generate_token(
        user_id=test_user.id,
        tenant_id=test_tenant.id,
        email=test_user.email,
        role=test_user.role.value
    )
    return {"Authorization": f"Bearer {token}"}


# ===========================================
# PUBLIC ENDPOINTS TESTS
# ===========================================

class TestRegisterEndpoint:
    """Tests for POST /auth/register endpoint."""

    @pytest.mark.asyncio
    async def test_register_success(self, client):
        """Should successfully register new user and create tenant."""
        # Arrange
        request_data = {
            "company_name": "New Company LLC",
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "first_name": "John",
            "last_name": "Doe",
            "accept_terms": True
        }

        # Act
        response = client.post(f"{API_PREFIX}/auth/register", json=request_data)

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        # Verify response structure
        assert "user" in data
        assert "tenant" in data
        assert "tokens" in data
        assert "message" in data

        # Verify user data
        assert data["user"]["email"] == request_data["email"]
        assert data["user"]["first_name"] == request_data["first_name"]
        assert data["user"]["last_name"] == request_data["last_name"]
        assert data["user"]["role"] == UserRole.ADMIN.value

        # Verify tenant data
        assert data["tenant"]["name"] == request_data["company_name"]
        assert data["tenant"]["subscription_plan"] == SubscriptionPlan.FREE.value

        # Verify tokens
        assert data["tokens"]["access_token"] is not None
        assert data["tokens"]["refresh_token"] is not None
        assert data["tokens"]["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client, test_user):
        """Should return 409 when email already exists."""
        # Arrange
        request_data = {
            "company_name": "Another Company",
            "email": test_user.email,  # Existing email
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "first_name": "Jane",
            "last_name": "Smith",
            "accept_terms": True
        }

        # Act
        response = client.post(f"{API_PREFIX}/auth/register", json=request_data)

        # Assert
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already exists" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_register_weak_password(self, client):
        """Should return 422 when password doesn't meet requirements."""
        # Arrange - password too short
        request_data = {
            "company_name": "Test Company",
            "email": "test@example.com",
            "password": "short",
            "password_confirm": "short",
            "accept_terms": True
        }

        # Act
        response = client.post(f"{API_PREFIX}/auth/register", json=request_data)

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_register_password_mismatch(self, client):
        """Should return 422 when passwords don't match."""
        # Arrange
        request_data = {
            "company_name": "Test Company",
            "email": "test@example.com",
            "password": "SecurePass123!",
            "password_confirm": "DifferentPass123!",
            "accept_terms": True
        }

        # Act
        response = client.post(f"{API_PREFIX}/auth/register", json=request_data)

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "do not match" in str(response.json()).lower()

    @pytest.mark.asyncio
    async def test_register_terms_not_accepted(self, client):
        """Should return 422 when terms not accepted."""
        # Arrange
        request_data = {
            "company_name": "Test Company",
            "email": "test@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "accept_terms": False
        }

        # Act
        response = client.post(f"{API_PREFIX}/auth/register", json=request_data)

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestLoginEndpoint:
    """Tests for POST /auth/login endpoint."""

    @pytest.mark.asyncio
    async def test_login_success(self, client, test_user):
        """Should successfully login with valid credentials."""
        # Arrange
        request_data = {
            "email": test_user.email,
            "password": "TestPassword123!"  # From test_user fixture
        }

        # Act
        response = client.post(f"{API_PREFIX}/auth/login", json=request_data)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify response structure
        assert "user" in data
        assert "tenant" in data
        assert "tokens" in data

        # Verify user data
        assert data["user"]["email"] == test_user.email
        assert data["user"]["id"] == str(test_user.id)

        # Verify tokens
        assert data["tokens"]["access_token"] is not None
        assert data["tokens"]["refresh_token"] is not None

    @pytest.mark.asyncio
    async def test_login_invalid_password(self, client, test_user):
        """Should return 401 with wrong password."""
        # Arrange
        request_data = {
            "email": test_user.email,
            "password": "WrongPassword123!"
        }

        # Act
        response = client.post(f"{API_PREFIX}/auth/login", json=request_data)

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "invalid" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client):
        """Should return 401 for non-existent user."""
        # Arrange
        request_data = {
            "email": "nonexistent@example.com",
            "password": "SomePassword123!"
        }

        # Act
        response = client.post(f"{API_PREFIX}/auth/login", json=request_data)

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_login_inactive_user(self, client, db, test_tenant):
        """Should return 401 for inactive user."""
        # Arrange - create inactive user
        inactive_user = User(
            id=uuid4(),
            tenant_id=test_tenant.id,
            email="inactive@example.com",
            hashed_password=hash_password("TestPassword123!"),
            first_name="Inactive",
            last_name="User",
            role=UserRole.ADMIN,
            is_active=False,  # Inactive
            is_verified=True,
        )
        db.add(inactive_user)
        await db.commit()

        request_data = {
            "email": inactive_user.email,
            "password": "TestPassword123!"
        }

        # Act
        response = client.post(f"{API_PREFIX}/auth/login", json=request_data)

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "inactive" in response.json()["detail"].lower()


class TestRefreshTokenEndpoint:
    """Tests for POST /auth/refresh endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, client, test_user, test_tenant, generate_token):
        """Should successfully refresh access token with valid refresh token."""
        # Arrange - generate a refresh token
        refresh_token = generate_token(
            user_id=test_user.id,
            tenant_id=test_tenant.id,
            email=test_user.email,
            role=test_user.role.value,
            token_type="refresh",
            expires_delta_seconds=30 * 24 * 60 * 60  # 30 days
        )

        request_data = {
            "refresh_token": refresh_token
        }

        # Act
        response = client.post(f"{API_PREFIX}/auth/refresh", json=request_data)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"
        assert data["access_token"] != refresh_token  # Should be a new token

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self, client):
        """Should return 401 with invalid refresh token."""
        # Arrange
        request_data = {
            "refresh_token": "invalid.jwt.token"
        }

        # Act
        response = client.post(f"{API_PREFIX}/auth/refresh", json=request_data)

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_refresh_token_expired(self, client, test_user, test_tenant, generate_token):
        """Should return 401 with expired refresh token."""
        # Arrange - generate expired token
        expired_token = generate_token(
            user_id=test_user.id,
            tenant_id=test_tenant.id,
            email=test_user.email,
            role=test_user.role.value,
            token_type="refresh",
            expires_delta_seconds=-3600  # Expired 1 hour ago
        )

        request_data = {
            "refresh_token": expired_token
        }

        # Act
        response = client.post(f"{API_PREFIX}/auth/refresh", json=request_data)

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ===========================================
# PROTECTED ENDPOINTS TESTS
# ===========================================

class TestGetMeEndpoint:
    """Tests for GET /auth/me endpoint."""

    @pytest.mark.asyncio
    async def test_get_me_success(self, client, test_user, auth_headers):
        """Should return current user info with valid token."""
        # Act
        response = client.get(f"{API_PREFIX}/auth/me", headers=auth_headers)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify response structure
        assert "user" in data
        assert "tenant" in data

        # Verify user data
        assert data["user"]["id"] == str(test_user.id)
        assert data["user"]["email"] == test_user.email
        assert data["user"]["first_name"] == test_user.first_name
        assert data["user"]["last_name"] == test_user.last_name

    @pytest.mark.asyncio
    async def test_get_me_missing_token(self, client):
        """Should return 401 when no token provided."""
        # Act
        response = client.get(f"{API_PREFIX}/auth/me")

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_get_me_invalid_token(self, client):
        """Should return 401 with invalid token."""
        # Arrange
        headers = {"Authorization": "Bearer invalid.jwt.token"}

        # Act
        response = client.get(f"{API_PREFIX}/auth/me", headers=headers)

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestUpdateMeEndpoint:
    """Tests for PUT /auth/me endpoint."""

    @pytest.mark.asyncio
    async def test_update_me_success(self, client, test_user, auth_headers):
        """Should successfully update user profile."""
        # Arrange
        update_data = {
            "first_name": "Updated",
            "last_name": "Name",
            "phone": "+34 600 123 456"
        }

        # Act
        response = client.put(f"{API_PREFIX}/auth/me", json=update_data, headers=auth_headers)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["first_name"] == update_data["first_name"]
        assert data["last_name"] == update_data["last_name"]
        assert data["phone"] == update_data["phone"]

    @pytest.mark.asyncio
    async def test_update_me_partial(self, client, test_user, auth_headers):
        """Should update only provided fields."""
        # Arrange - only update first name
        update_data = {
            "first_name": "OnlyFirstName"
        }

        # Act
        response = client.put(f"{API_PREFIX}/auth/me", json=update_data, headers=auth_headers)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["first_name"] == update_data["first_name"]
        # Last name should remain unchanged
        assert data["last_name"] == test_user.last_name

    @pytest.mark.asyncio
    async def test_update_me_missing_token(self, client):
        """Should return 401 when no token provided."""
        # Arrange
        update_data = {"first_name": "Updated"}

        # Act
        response = client.put(f"{API_PREFIX}/auth/me", json=update_data)

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestLogoutEndpoint:
    """Tests for POST /auth/logout endpoint."""

    @pytest.mark.asyncio
    async def test_logout_success(self, client, auth_headers):
        """Should successfully logout with valid token."""
        # Act
        response = client.post(f"{API_PREFIX}/auth/logout", headers=auth_headers)

        # Assert
        assert response.status_code == status.HTTP_204_NO_CONTENT

    @pytest.mark.asyncio
    async def test_logout_missing_token(self, client):
        """Should return 401 when no token provided."""
        # Act
        response = client.post(f"{API_PREFIX}/auth/logout")

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestChangePasswordEndpoint:
    """Tests for POST /auth/change-password endpoint."""

    @pytest.mark.asyncio
    async def test_change_password_success(self, client, test_user, auth_headers):
        """Should successfully change password with correct current password."""
        # Arrange
        request_data = {
            "current_password": "TestPassword123!",  # From test_user fixture
            "new_password": "NewSecurePass123!",
            "new_password_confirm": "NewSecurePass123!"
        }

        # Act
        response = client.post(f"{API_PREFIX}/auth/change-password", json=request_data, headers=auth_headers)

        # Assert
        assert response.status_code == status.HTTP_204_NO_CONTENT

    @pytest.mark.asyncio
    async def test_change_password_wrong_current(self, client, auth_headers):
        """Should return 401 with incorrect current password."""
        # Arrange
        request_data = {
            "current_password": "WrongPassword123!",
            "new_password": "NewSecurePass123!",
            "new_password_confirm": "NewSecurePass123!"
        }

        # Act
        response = client.post(f"{API_PREFIX}/auth/change-password", json=request_data, headers=auth_headers)

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "incorrect" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_change_password_weak_new_password(self, client, auth_headers):
        """Should return 422 when new password doesn't meet requirements."""
        # Arrange
        request_data = {
            "current_password": "TestPassword123!",
            "new_password": "weak",  # Too short, no uppercase, no digit
            "new_password_confirm": "weak"
        }

        # Act
        response = client.post(f"{API_PREFIX}/auth/change-password", json=request_data, headers=auth_headers)

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_change_password_oauth_user(self, client, db, test_tenant, generate_token):
        """Should return 400 for OAuth users (no hashed_password)."""
        # Arrange - create OAuth user without hashed_password
        oauth_user = User(
            id=uuid4(),
            tenant_id=test_tenant.id,
            email="oauth@example.com",
            hashed_password=None,  # OAuth user
            first_name="OAuth",
            last_name="User",
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=True,
        )
        db.add(oauth_user)
        await db.commit()

        # Generate token for OAuth user
        token = generate_token(
            user_id=oauth_user.id,
            tenant_id=test_tenant.id,
            email=oauth_user.email,
            role=oauth_user.role.value
        )
        headers = {"Authorization": f"Bearer {token}"}

        request_data = {
            "current_password": "anything",
            "new_password": "NewSecurePass123!",
            "new_password_confirm": "NewSecurePass123!"
        }

        # Act
        response = client.post(f"{API_PREFIX}/auth/change-password", json=request_data, headers=headers)

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "oauth" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_change_password_missing_token(self, client):
        """Should return 401 when no token provided."""
        # Arrange
        request_data = {
            "current_password": "TestPassword123!",
            "new_password": "NewSecurePass123!",
            "new_password_confirm": "NewSecurePass123!"
        }

        # Act
        response = client.post(f"{API_PREFIX}/auth/change-password", json=request_data)

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ===========================================
# HEALTH CHECK TEST
# ===========================================

class TestHealthEndpoint:
    """Tests for GET /auth/health endpoint."""

    def test_health_check(self, simple_client):
        """Should always return ok status."""
        # Act
        response = simple_client.get(f"{API_PREFIX}/auth/health")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "ok"
        assert data["service"] == "auth"
