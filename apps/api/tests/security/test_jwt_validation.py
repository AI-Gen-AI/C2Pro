from datetime import timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient

from src.modules.auth.models import Tenant, User  # Import models for database setup
from src.modules.projects.models import Project


@pytest.mark.asyncio
@pytest.mark.security
async def test_protected_endpoint_with_valid_jwt(
    client: AsyncClient, get_auth_headers, cleanup_database
):
    """
    A request to a protected endpoint with a valid JWT should be successful.
    """
    # === Arrange ===
    # Create tenant, user, and project directly in database
    from src.core.database import _session_factory

    test_user_id = uuid4()
    test_tenant_id = uuid4()
    test_project_id = uuid4()

    # Create data in actual database (not in test transaction)
    async with _session_factory() as session:
        tenant = Tenant(id=test_tenant_id, name="Test Tenant")
        session.add(tenant)
        await session.flush()

        user = User(
            id=test_user_id,
            email="test@example.com",
            tenant_id=test_tenant_id,
            hashed_password="hashedpassword",
        )
        session.add(user)
        await session.flush()

        project = Project(id=test_project_id, name="Test Project", tenant_id=test_tenant_id)
        session.add(project)
        await session.commit()

    try:
        headers = get_auth_headers(user_id=test_user_id, tenant_id=test_tenant_id)

        # === Act ===
        # Make a request to a protected endpoint (e.g., list projects).
        response = await client.get("/api/v1/projects/", headers=headers)

        # === Assert ===
        # Expect a successful status code and paginated response.
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total_count" in data
        assert isinstance(data["items"], list)

    finally:
        # Clean up: delete the test data using superuser connection
        await cleanup_database(
            projects=[test_project_id], users=[test_user_id], tenants=[test_tenant_id]
        )


@pytest.mark.asyncio
@pytest.mark.security
async def test_protected_endpoint_with_invalid_signature_jwt(
    client: AsyncClient, create_test_token
):
    """
    A request with a JWT signed with an incorrect secret key should be rejected.
    """
    # === Arrange ===
    # Generate a token with a different secret key.
    invalid_token = create_test_token(
        user_id=uuid4(), tenant_id=uuid4(), secret_key="a-different-secret"
    )
    invalid_headers = {"Authorization": f"Bearer {invalid_token}"}

    # === Act ===
    response = await client.get("/api/v1/projects/", headers=invalid_headers)

    # === Assert ===
    # Expect a 401 Unauthorized error.
    assert response.status_code == 401
    assert "Invalid authentication credentials" in response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.security
async def test_protected_endpoint_with_expired_jwt(client: AsyncClient, create_test_token):
    """
    A request with an expired JWT should be rejected.
    """
    # === Arrange ===
    # Generate a token that has already expired.
    expired_token = create_test_token(
        user_id=uuid4(), tenant_id=uuid4(), expires_delta=timedelta(seconds=-60)
    )
    expired_headers = {"Authorization": f"Bearer {expired_token}"}

    # === Act ===
    response = await client.get("/api/v1/projects/", headers=expired_headers)

    # === Assert ===
    # Expect a 401 Unauthorized error.
    assert response.status_code == 401
    assert "Token has expired" in response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.security
async def test_protected_endpoint_with_missing_jwt(client: AsyncClient):
    """
    A request to a protected endpoint without any JWT should be rejected.
    """
    # === Arrange ===
    # No headers are prepared.

    # === Act ===
    response = await client.get("/api/v1/projects/")

    # === Assert ===
    # Expect a 401 Unauthorized error.
    assert response.status_code == 401
    assert "Invalid authentication credentials" in response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.security
async def test_protected_endpoint_with_jwt_for_non_existent_tenant(
    client: AsyncClient, create_test_token
):
    """
    A JWT with a `tenant_id` that does not exist in the database should be rejected.
    This prevents a validly signed token from a different system or a deleted tenant
    from being used.
    """
    # === Arrange ===
    # Generate a token with a random, non-existent tenant_id.
    non_existent_tenant_id = uuid4()
    orphan_token = create_test_token(user_id=uuid4(), tenant_id=non_existent_tenant_id)
    orphan_headers = {"Authorization": f"Bearer {orphan_token}"}

    # === Act ===
    response = await client.get("/api/v1/projects/", headers=orphan_headers)

    # === Assert ===
    # Expect a 401 Unauthorized error because the tenant does not exist.
    assert response.status_code == 401
    assert "Invalid authentication context" in response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.security
async def test_jwt_refresh_token_valid(client: AsyncClient, create_test_token, cleanup_database):
    """
    A valid refresh token should successfully return a new access token.
    """
    # === Arrange ===
    # Create tenant and user directly in database, bypassing test transaction
    from src.core.database import _session_factory
    from src.modules.auth.models import Tenant, User

    test_user_id = uuid4()
    test_tenant_id = uuid4()

    # Create tenant and user in actual database (not in test transaction)
    async with _session_factory() as session:
        tenant = Tenant(id=test_tenant_id, name="Refresh Test Tenant")
        session.add(tenant)
        await session.flush()

        user = User(
            id=test_user_id,
            email="refresh_user@example.com",
            tenant_id=test_tenant_id,
            hashed_password="hashedpassword",
        )
        session.add(user)
        await session.commit()

    try:
        refresh_token = create_test_token(
            user_id=test_user_id,
            tenant_id=test_tenant_id,
            token_type="refresh",
            expires_delta=timedelta(minutes=10),  # Ensure it's not expired
        )

        # === Act ===
        response = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})

        # === Assert ===
        assert response.status_code == 200
        assert "access_token" in response.json()
        assert "refresh_token" in response.json()  # Should return new refresh token as well

    finally:
        # Clean up: delete the test data using superuser connection
        await cleanup_database(users=[test_user_id], tenants=[test_tenant_id])


@pytest.mark.asyncio
@pytest.mark.security
async def test_jwt_refresh_token_expired(client: AsyncClient, create_test_token):
    """
    An expired refresh token should be rejected.
    """
    # === Arrange ===
    expired_refresh_token = create_test_token(
        user_id=uuid4(),
        tenant_id=uuid4(),
        token_type="refresh",
        expires_delta=timedelta(seconds=-60),  # Expired
    )

    # === Act ===
    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": expired_refresh_token}
    )

    # === Assert ===
    assert response.status_code == 401
    assert "Token has expired" in response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.security
async def test_jwt_refresh_token_invalid_signature(client: AsyncClient, create_test_token):
    """
    A refresh token with an invalid signature should be rejected.
    """
    # === Arrange ===
    invalid_refresh_token = create_test_token(
        user_id=uuid4(),
        tenant_id=uuid4(),
        token_type="refresh",
        secret_key="some-other-secret",  # Invalid signature
    )

    # === Act ===
    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": invalid_refresh_token}
    )

    # === Assert ===
    assert response.status_code == 401
    assert "Invalid authentication credentials" in response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.security
async def test_jwt_refresh_token_wrong_type(client: AsyncClient, create_test_token, db_session):
    """
    An access token used as a refresh token should be rejected.
    """
    # === Arrange ===
    test_user_id = uuid4()
    test_tenant_id = uuid4()

    tenant = Tenant(id=test_tenant_id, name="Test Tenant")
    db_session.add(tenant)
    await db_session.flush()
    await db_session.refresh(tenant)

    user = User(
        id=test_user_id,
        email="wrong_type_user@example.com",
        tenant_id=test_tenant_id,
        hashed_password="hashedpassword",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    access_token_as_refresh = create_test_token(
        user_id=test_user_id,
        tenant_id=test_tenant_id,
        token_type="access",  # Use an access token here
    )

    # === Act ===
    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": access_token_as_refresh}
    )

    # === Assert ===
    assert response.status_code == 401
    assert "Invalid token type, expected 'refresh'" in response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.security
async def test_cross_tenant_access_denied(client: AsyncClient, get_auth_headers, cleanup_database):
    """
    A user from one tenant should not be able to access resources (e.g., projects)
    belonging to another tenant, even if authenticated.
    """
    # === Arrange ===
    # Create data directly in database
    from src.core.database import _session_factory

    tenant_a_id = uuid4()
    tenant_b_id = uuid4()
    user_a_id = uuid4()
    user_b_id = uuid4()
    project_b_id = uuid4()

    # Create tenants, users, and project in actual database
    async with _session_factory() as session:
        tenant_a = Tenant(id=tenant_a_id, name="Tenant A")
        tenant_b = Tenant(id=tenant_b_id, name="Tenant B")
        session.add_all([tenant_a, tenant_b])
        await session.flush()

        user_a = User(
            id=user_a_id,
            email="user_a@example.com",
            tenant_id=tenant_a_id,
            hashed_password="hashedpassword",
        )
        user_b = User(
            id=user_b_id,
            email="user_b@example.com",
            tenant_id=tenant_b_id,
            hashed_password="hashedpassword",
        )
        session.add_all([user_a, user_b])
        await session.flush()

        # Create a project for Tenant B
        project_b = Project(id=project_b_id, name="Project B", tenant_id=tenant_b_id)
        session.add(project_b)
        await session.commit()

    try:
        # Get auth headers for User A
        headers_user_a = get_auth_headers(user_id=user_a_id, tenant_id=tenant_a_id)

        # === Act ===
        # User A tries to access Project B's resources
        response = await client.get(f"/api/v1/projects/{project_b_id}", headers=headers_user_a)

        # === Assert ===
        # User A should not be authorized to see Project B, even if Project B exists.
        # Due to RLS, the project will not be found in User A's context.
        assert response.status_code == 404
        assert "Project not found" in response.json()["detail"]

    finally:
        # Clean up: delete the test data using superuser connection
        await cleanup_database(
            projects=[project_b_id],
            users=[user_a_id, user_b_id],
            tenants=[tenant_a_id, tenant_b_id],
        )
