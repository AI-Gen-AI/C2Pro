"""
C2Pro - JWT Validation Tests

Tests for JWT authentication and authorization.
Validates token signatures, expiry, and tenant isolation.
"""

import pytest
from httpx import AsyncClient
from uuid import uuid4


@pytest.mark.asyncio
@pytest.mark.security
async def test_protected_endpoint_with_valid_jwt(
    client: AsyncClient,
    get_auth_headers,
):
    """
    A request to a protected endpoint with a valid JWT should be successful.
    """
    # === Arrange ===
    # Get valid headers for a test user
    headers = await get_auth_headers()

    # === Act ===
    # Make a request to a protected endpoint (e.g., list projects)
    response = await client.get("/projects/", headers=headers)

    # === Assert ===
    # Expect a successful status code
    assert response.status_code == 200
    # Response should be a list or paginated result
    data = response.json()
    assert "items" in data or isinstance(data, list)


@pytest.mark.asyncio
@pytest.mark.security
async def test_protected_endpoint_with_invalid_signature_jwt(
    client: AsyncClient,
    generate_token,
):
    """
    A request with a JWT signed with an incorrect secret key should be rejected.
    """
    # === Arrange ===
    # Generate a token with a different secret key
    invalid_token = generate_token(secret_key="a-different-secret-key-12345")
    invalid_headers = {"Authorization": f"Bearer {invalid_token}"}

    # === Act ===
    response = await client.get("/projects/", headers=invalid_headers)

    # === Assert ===
    # Expect a 401 Unauthorized error
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.security
async def test_protected_endpoint_with_expired_jwt(
    client: AsyncClient,
    generate_token,
):
    """
    A request with an expired JWT should be rejected.
    """
    # === Arrange ===
    # Generate a token that has already expired (60 seconds ago)
    expired_token = generate_token(expires_delta_seconds=-60)
    expired_headers = {"Authorization": f"Bearer {expired_token}"}

    # === Act ===
    response = await client.get("/projects/", headers=expired_headers)

    # === Assert ===
    # Expect a 401 Unauthorized error
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.security
async def test_protected_endpoint_with_missing_jwt(client: AsyncClient):
    """
    A request to a protected endpoint without any JWT should be rejected.
    """
    # === Arrange ===
    # No headers are prepared (no Authorization header)

    # === Act ===
    response = await client.get("/projects/")

    # === Assert ===
    # Expect a 401 Unauthorized error
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.security
async def test_protected_endpoint_with_jwt_for_non_existent_tenant(
    client: AsyncClient,
    generate_token,
):
    """
    A JWT with a `tenant_id` that does not exist in the database should be rejected.
    This prevents a validly signed token from a different system or a deleted tenant
    from being used.
    """
    # === Arrange ===
    # Generate a token with a random, non-existent tenant_id
    non_existent_tenant_id = uuid4()
    orphan_token = generate_token(tenant_id=non_existent_tenant_id)
    orphan_headers = {"Authorization": f"Bearer {orphan_token}"}

    # === Act ===
    response = await client.get("/projects/", headers=orphan_headers)

    # === Assert ===
    # Expect a 401 or 403 error, as the credential is not valid for any tenant in this system
    # The middleware should reject tokens for non-existent tenants
    assert response.status_code in [401, 403, 404]
