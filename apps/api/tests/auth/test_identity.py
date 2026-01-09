from uuid import uuid4

import pytest
from httpx import AsyncClient

from src.modules.auth.models import Tenant, User  # For direct database interaction
from src.modules.auth.service import (
    hash_password,  # For setting up test users with hashed passwords
)


@pytest.mark.asyncio
@pytest.mark.auth
async def test_register_new_user_and_tenant_success(client: AsyncClient):
    """
    Test successful user registration and tenant creation.
    """
    # === Arrange ===
    register_data = {
        "email": f"new_user_{uuid4()}@example.com",
        "password": "SecurePassword123!",
        "company_name": f"New Company {uuid4()}",
        "accept_terms": True,
    }

    # === Act ===
    response = await client.post("/api/v1/auth/register", json=register_data)

    # === Assert ===
    assert response.status_code == 201
    response_data = response.json()
    assert "user" in response_data
    assert "tenant" in response_data
    assert "access_token" in response_data
    assert "refresh_token" in response_data
    assert response_data["user"]["email"] == register_data["email"]
    assert response_data["tenant"]["name"] == register_data["company_name"]


@pytest.mark.asyncio
@pytest.mark.auth
async def test_register_user_with_existing_email(client: AsyncClient):
    """
    Test registration with an email that already exists should fail.
    """
    # === Arrange ===
    email = f"existing_{uuid4()}@example.com"
    register_data_1 = {
        "email": email,
        "password": "SecurePassword123!",
        "company_name": f"Company A {uuid4()}",
        "accept_terms": True,
    }
    register_data_2 = {  # Same email, different company
        "email": email,
        "password": "AnotherSecurePassword123!",
        "company_name": f"Company B {uuid4()}",
        "accept_terms": True,
    }

    # Register first user successfully
    await client.post("/api/v1/auth/register", json=register_data_1)

    # === Act ===
    response = await client.post("/api/v1/auth/register", json=register_data_2)

    # === Assert ===
    assert response.status_code == 409
    assert "Email already exists" in response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.auth
@pytest.mark.parametrize(
    "password",
    [
        "short",  # Too short
        "nopassword",  # No special char, no digit, no uppercase
        "NOUPPERCASE1!",
        "no_digit!",
    ],
)
async def test_register_user_invalid_password(client: AsyncClient, password: str):
    """
    Test registration with an invalid (weak) password should fail.
    """
    # === Arrange ===
    register_data = {
        "email": f"weak_pass_{uuid4()}@example.com",
        "password": password,
        "company_name": f"Weak Pass Company {uuid4()}",
        "accept_terms": True,
    }

    # === Act ===
    response = await client.post("/api/v1/auth/register", json=register_data)

    # === Assert ===
    assert response.status_code == 422
    assert "password" in response.json()["detail"][0]["loc"]


@pytest.mark.asyncio
@pytest.mark.auth
async def test_login_success(client: AsyncClient, db_session):
    """
    Test successful user login with correct credentials.
    """
    # === Arrange ===
    # Manually create a user in the database
    email = f"login_user_{uuid4()}@example.com"
    password = "CorrectPassword123!"
    tenant_id = uuid4()

    tenant = Tenant(id=tenant_id, name=f"Login Company {uuid4()}")
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)

    user = User(
        id=uuid4(), email=email, tenant_id=tenant_id, hashed_password=hash_password(password)
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    login_data = {"email": email, "password": password}

    # === Act ===
    response = await client.post("/api/v1/auth/login", json=login_data)

    # === Assert ===
    assert response.status_code == 200
    response_data = response.json()
    assert "user" in response_data
    assert "tenant" in response_data
    assert "access_token" in response_data
    assert "refresh_token" in response_data
    assert response_data["user"]["email"] == email


@pytest.mark.asyncio
@pytest.mark.auth
async def test_login_invalid_credentials(client: AsyncClient, db_session):
    """
    Test login with incorrect password should fail.
    """
    # === Arrange ===
    email = f"invalid_cred_{uuid4()}@example.com"
    password = "CorrectPassword123!"
    tenant_id = uuid4()

    tenant = Tenant(id=tenant_id, name=f"Invalid Cred Company {uuid4()}")
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)

    user = User(
        id=uuid4(), email=email, tenant_id=tenant_id, hashed_password=hash_password(password)
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    login_data = {"email": email, "password": "WrongPassword!"}

    # === Act ===
    response = await client.post("/api/v1/auth/login", json=login_data)

    # === Assert ===
    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.auth
async def test_login_non_existent_user(client: AsyncClient):
    """
    Test login with a non-existent user should fail.
    """
    # === Arrange ===
    login_data = {"email": f"non_existent_{uuid4()}@example.com", "password": "AnyPassword123!"}

    # === Act ===
    response = await client.post("/api/v1/auth/login", json=login_data)

    # === Assert ===
    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.auth
async def test_get_me_success(client: AsyncClient, get_auth_headers, create_test_user_and_tenant):
    """
    Test authenticated user can retrieve their own profile successfully.
    """
    # === Arrange ===
    user, tenant = await create_test_user_and_tenant("Me Company", "me@example.com")
    headers = get_auth_headers(user_id=user.id, tenant_id=tenant.id)

    # === Act ===
    response = await client.get("/api/v1/auth/me", headers=headers)

    # === Assert ===
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["user"]["email"] == user.email
    assert response_data["tenant"]["id"] == str(tenant.id)


@pytest.mark.asyncio
@pytest.mark.auth
async def test_update_me_success(
    client: AsyncClient, get_auth_headers, create_test_user_and_tenant
):
    """
    Test authenticated user can update their own profile successfully.
    """
    # === Arrange ===
    user, tenant = await create_test_user_and_tenant("Update Me Company", "update_me@example.com")
    headers = get_auth_headers(user_id=user.id, tenant_id=tenant.id)
    update_data = {"first_name": "Updated", "last_name": "User", "phone": "123-456-7890"}

    # === Act ===
    response = await client.put("/api/v1/auth/me", json=update_data, headers=headers)

    # === Assert ===
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["first_name"] == update_data["first_name"]
    assert response_data["last_name"] == update_data["last_name"]
    assert response_data["phone"] == update_data["phone"]


@pytest.mark.asyncio
@pytest.mark.auth
async def test_update_me_unauthenticated(client: AsyncClient):
    """
    Test unauthenticated user cannot update any profile.
    """
    # === Arrange ===
    update_data = {"first_name": "Unauthorized"}

    # === Act ===
    response = await client.put("/api/v1/auth/me", json=update_data)

    # === Assert ===
    assert response.status_code == 401
    assert "Not authenticated" in response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.auth
async def test_change_password_success(
    client: AsyncClient, db_session, create_test_user_and_tenant, get_auth_headers
):
    """
    Test authenticated user can change their password successfully with correct old password.
    """
    # === Arrange ===
    email = f"password_change_{uuid4()}@example.com"
    old_password = "OldSecurePassword123!"
    new_password = "NewSecurePassword456!"

    user, tenant = await create_test_user_and_tenant("Pass Change Company", email)

    # Update user with hashed old password directly in DB for login
    user.hashed_password = hash_password(old_password)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    headers = get_auth_headers(user_id=user.id, tenant_id=tenant.id, email=email)

    change_data = {"current_password": old_password, "new_password": new_password}

    # === Act ===
    response = await client.post("/api/v1/auth/change-password", json=change_data, headers=headers)

    # === Assert ===
    assert response.status_code == 204  # No content on success

    # Try to log in with new password to verify
    login_response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": new_password}
    )
    assert login_response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.auth
async def test_change_password_invalid_old_password(
    client: AsyncClient, db_session, create_test_user_and_tenant, get_auth_headers
):
    """
    Test changing password with incorrect old password should fail.
    """
    # === Arrange ===
    email = f"invalid_old_pass_{uuid4()}@example.com"
    old_password = "OldSecurePassword123!"
    new_password = "NewSecurePassword456!"

    user, tenant = await create_test_user_and_tenant("Invalid Old Pass Company", email)

    user.hashed_password = hash_password(old_password)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    headers = get_auth_headers(user_id=user.id, tenant_id=tenant.id, email=email)

    change_data = {"current_password": "WrongOldPassword!", "new_password": new_password}

    # === Act ===
    response = await client.post("/api/v1/auth/change-password", json=change_data, headers=headers)

    # === Assert ===
    assert response.status_code == 401
    assert "Current password is incorrect" in response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.auth
async def test_change_password_unauthenticated(client: AsyncClient):
    """
    Test unauthenticated user cannot change any password.
    """
    # === Arrange ===
    change_data = {"current_password": "AnyPassword123!", "new_password": "NewPassword123!"}

    # === Act ===
    response = await client.post("/api/v1/auth/change-password", json=change_data)

    # === Assert ===
    assert response.status_code == 401
    assert "Not authenticated" in response.json()["detail"]
