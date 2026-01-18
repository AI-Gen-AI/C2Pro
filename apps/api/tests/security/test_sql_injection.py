"""
C2Pro - SQL Injection Tests

Tests to verify that the API is not vulnerable to SQL injection attacks.
Validates input sanitization, parameterized queries, and type validation.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.parametrize("payload", [
    "' OR '1'='1",
    "' OR 1=1; --",
    "'; DROP TABLE projects; --",
    "UNION SELECT id, name FROM users; --",
    "1'; UPDATE projects SET name='hacked' WHERE '1'='1",
    "' UNION SELECT NULL, NULL, NULL--",
])
async def test_sql_injection_in_project_search(
    client: AsyncClient,
    payload: str,
    get_auth_headers,
):
    """
    Tests that a search endpoint is not vulnerable to common SQL injection payloads.

    This test assumes a search filter is applied to a GET endpoint for projects,
    for example: `GET /projects?search=...`

    The API should:
    1. Not crash (no 500 errors)
    2. Not leak data from other tables
    3. Handle malicious input gracefully (200 with empty results or 400 Bad Request)
    """
    # === Arrange ===
    # Get valid authentication headers
    headers = await get_auth_headers()

    # === Act ===
    # Make a request to the search endpoint with the SQL injection payload
    # The endpoint '/projects' with a 'search' query parameter is assumed based on
    # the ProjectFilters schema in 'projects/schemas.py'
    response = await client.get("/projects/", params={"search": payload}, headers=headers)

    # === Assert ===
    # 1. The API must not crash. A 500 Internal Server Error indicates a critical failure
    assert response.status_code != 500, f"Server crashed with payload: {payload}"

    # 2. The API should handle the malicious input gracefully
    # Expected responses:
    #    - 200 OK with an empty list of items (sanitization effective)
    #    - 400 Bad Request (input validation detected malicious pattern)
    #    - 422 Unprocessable Entity (validation error)
    assert response.status_code in [200, 400, 422], f"Unexpected status {response.status_code} for payload: {payload}"

    # 3. If the status is 200, ensure the response is safe
    # The query should return no results (assuming no projects match the literal search)
    if response.status_code == 200:
        data = response.json()
        # Handle both list and paginated responses
        items = data if isinstance(data, list) else data.get("items", [])

        # Either no items, or items are legitimate projects (not leaked data from other tables)
        # We can't easily verify the latter without knowing what legitimate projects exist,
        # but we can check that the response structure is correct
        if items:
            # Verify response structure looks like projects, not arbitrary data
            for item in items:
                assert "id" in item
                # Should have project-specific fields
                assert any(key in item for key in ["name", "code", "type"])


@pytest.mark.asyncio
@pytest.mark.security
async def test_sql_injection_in_path_parameter(
    client: AsyncClient,
    get_auth_headers,
):
    """
    Tests that a path parameter is not vulnerable to SQL injection.
    Modern frameworks like FastAPI usually prevent this by validating data types.

    When a UUID type is expected in the path, FastAPI will automatically reject
    non-UUID values with a 422 Unprocessable Entity error.
    """
    # === Arrange ===
    # An injection payload that might be tried on an endpoint like /projects/{id}
    sql_injection_id = "00000000-0000-0000-0000-000000000000'; DROP TABLE users; --"
    headers = await get_auth_headers()

    # === Act ===
    response = await client.get(f"/projects/{sql_injection_id}", headers=headers)

    # === Assert ===
    # FastAPI, when using UUID type hinting for path parameters, will automatically
    # return a 422 Unprocessable Entity error because the payload is not a valid UUID.
    # This is the expected, secure behavior.
    assert response.status_code == 422
    error_detail = response.json()
    assert "detail" in error_detail


@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.parametrize("field,payload", [
    ("name", "'; DROP TABLE projects; --"),
    ("code", "' OR '1'='1"),
    ("description", "<script>alert('xss')</script>' AND '1'='1"),
])
async def test_sql_injection_in_project_creation(
    client: AsyncClient,
    get_auth_headers,
    field: str,
    payload: str,
):
    """
    Tests that project creation endpoints are not vulnerable to SQL injection.

    Malicious payloads should be stored as literal strings (escaped properly)
    and not executed as SQL commands.
    """
    # === Arrange ===
    headers = await get_auth_headers()

    # Build project data with malicious payload in specified field
    project_data = {
        "name": "Test Project",
        "code": f"TEST-{hash(payload) % 10000}",
        "type": "construction",
    }
    project_data[field] = payload

    # === Act ===
    response = await client.post("/projects/", json=project_data, headers=headers)

    # === Assert ===
    # 1. The API should not crash
    assert response.status_code != 500

    # 2. Request should either succeed (with payload stored as literal string)
    #    or be rejected with validation error
    if response.status_code in [200, 201]:
        # If accepted, verify the payload was stored as a literal string
        project = response.json()
        assert project[field] == payload, "Payload should be stored literally, not executed"

    elif response.status_code in [400, 422]:
        # Validation rejected the input (acceptable if there's input sanitization)
        pass

    else:
        pytest.fail(f"Unexpected status code {response.status_code}")
