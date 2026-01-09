from uuid import uuid4

import pytest
from httpx import AsyncClient

from src.modules.auth.models import Tenant, User
from src.modules.projects.models import Project


@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.parametrize(
    "payload",
    [
        "' OR '1'='1",
        "' OR 1=1; --",
        "'; DROP TABLE projects; --",
        "UNION SELECT null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null FROM users; --",  # Adjusted UNION to match expected Project schema columns (approx)
        "SLEEP(5);",  # Time-based injection payload
    ],
)
async def test_sql_injection_in_project_search(
    client: AsyncClient, get_auth_headers, cleanup_database, payload: str
):
    """
    Tests that a search endpoint is not vulnerable to common SQL injection payloads.
    """
    # === Arrange ===
    # Create test data directly in database
    from src.core.database import _session_factory

    tenant_id = uuid4()
    user_id = uuid4()
    project_id = uuid4()

    # Create tenant, user, and project in actual database
    async with _session_factory() as session:
        tenant = Tenant(id=tenant_id, name="Test Tenant Search")
        session.add(tenant)
        await session.flush()

        user = User(
            id=user_id,
            email="search@example.com",
            tenant_id=tenant_id,
            hashed_password="hashedpassword",
        )
        session.add(user)
        await session.flush()

        project = Project(id=project_id, name="Safe Project", tenant_id=tenant_id)
        session.add(project)
        await session.commit()

    try:
        headers = get_auth_headers(user_id=user_id, tenant_id=tenant_id)

        # === Act ===
        # Make a request to the search endpoint with the SQL injection payload.
        response = await client.get(
            "/api/v1/projects/", params={"search": payload}, headers=headers
        )

        # === Assert ===
        # 1. The API must not crash. A 500 Internal Server Error indicates a critical failure.
        assert response.status_code != 500

        # 2. The API should handle the malicious input gracefully.
        #    Expected responses:
        #    - 200 OK with an empty list of items, if the sanitization is effective.
        #    - 422 Unprocessable Entity or 400 Bad Request, if an input validation layer detects the malicious pattern.
        #    SQLAlchemy ORM typically handles parameter sanitization, so 200 OK with empty list is common.
        assert response.status_code == 200

        # 3. Ensure no data was unexpectedly returned. The list should be empty if the payload is truly malicious.
        assert response.json()["items"] == []
        assert response.json()["total_count"] == 0

    finally:
        # Clean up: delete the test data using superuser connection
        await cleanup_database(projects=[project_id], users=[user_id], tenants=[tenant_id])


@pytest.mark.asyncio
@pytest.mark.security
async def test_sql_injection_in_path_parameter(
    client: AsyncClient, get_auth_headers, cleanup_database
):
    """
    Tests that a path parameter is not vulnerable to SQL injection.
    FastAPI and Pydantic typically prevent this by validating data types.
    """
    # === Arrange ===
    # Create test data directly in database
    from src.core.database import _session_factory

    tenant_id = uuid4()
    user_id = uuid4()

    # Create tenant and user in actual database
    async with _session_factory() as session:
        tenant = Tenant(id=tenant_id, name="Path Test Tenant")
        session.add(tenant)
        await session.flush()

        user = User(
            id=user_id,
            email="path@example.com",
            tenant_id=tenant_id,
            hashed_password="hashedpassword",
        )
        session.add(user)
        await session.commit()

    try:
        headers = get_auth_headers(user_id=user_id, tenant_id=tenant_id)

        # A SQL injection payload that might be tried on an endpoint like /projects/{id}
        sql_injection_id = "00000000-0000-0000-0000-000000000000'; DROP TABLE users; --"

        # === Act ===
        response = await client.get(f"/api/v1/projects/{sql_injection_id}", headers=headers)

        # === Assert ===
        # FastAPI, when using UUID type hinting for path parameters, will automatically
        # return a 422 Unprocessable Entity error because the payload is not a valid UUID.
        # This is the expected, secure behavior.
        assert response.status_code == 422
        # Pydantic v2 error message format
        assert "valid UUID" in response.json()["detail"][0]["msg"]

    finally:
        # Clean up: delete the test data using superuser connection
        await cleanup_database(users=[user_id], tenants=[tenant_id])
