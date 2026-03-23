"""
Integration tests for the /projects API router.

This test suite verifies the functionality and security of the core
projects CRUD endpoints, with a special focus on multi-tenant isolation.
"""

import pytest
from httpx import AsyncClient

# Mark all tests in this file as using the asyncio backend
pytestmark = pytest.mark.anyio


async def test_create_project_success(
    client: AsyncClient, 
    get_auth_headers, 
    create_test_user_and_tenant
):
    """
    Tests successful creation of a new project.
    Verifies:
    - 201 Created status code.
    - Response data matches the input.
    - The correct tenant_id is assigned automatically.
    """
    # Arrange: Create a user and tenant for the test
    user, tenant = await create_test_user_and_tenant(
        tenant_name="Test Tenant Create", user_email="create-user@test.com"
    )
    headers = get_auth_headers(user_id=user.id, tenant_id=tenant.id)
    
    project_data = {
        "name": "New Test Project",
        "description": "A project created via integration test.",
        "code": "TEST-001",
        "estimated_budget": 100000.0,
        "currency": "USD"
    }

    # Act: Make the API call to create the project
    response = await client.post("/api/v1/projects", json=project_data, headers=headers)

    # Assert: Check the response
    assert response.status_code == 201
    response_data = response.json()
    
    assert response_data["name"] == project_data["name"]
    assert response_data["description"] == project_data["description"]
    assert response_data["tenant_id"] == str(tenant.id)
    assert response_data["status"] == "draft" # Should default to DRAFT


async def test_get_project_isolation_failure(
    client: AsyncClient, 
    get_auth_headers, 
    create_test_user_and_tenant
):
    """
    Tests multi-tenant isolation (Security Gate).
    Verifies that a user from one tenant cannot access a project belonging
    to another tenant.
    """
    # Arrange: Create two separate users in two separate tenants
    user_a, tenant_a = await create_test_user_and_tenant(
        tenant_name="Tenant A", user_email="user-a@tenant-a.com"
    )
    user_b, tenant_b = await create_test_user_and_tenant(
        tenant_name="Tenant B", user_email="user-b@tenant-b.com"
    )

    headers_a = get_auth_headers(user_id=user_a.id, tenant_id=tenant_a.id)
    headers_b = get_auth_headers(user_id=user_b.id, tenant_id=tenant_b.id)

    # Act 1: User A creates a project in Tenant A
    project_data = {"name": "Project in Tenant A"}
    response_create = await client.post("/api/v1/projects", json=project_data, headers=headers_a)
    assert response_create.status_code == 201
    project_a_id = response_create.json()["id"]

    # Act 2: User B attempts to access the project created by User A
    response_get = await client.get(f"/api/v1/projects/{project_a_id}", headers=headers_b)

    # Assert: The request must fail with 404 Not Found
    # It should not be 403 Forbidden, as that would reveal the existence of the project.
    assert response_get.status_code == 404


async def test_patch_project_success(
    client: AsyncClient,
    get_auth_headers,
    create_test_user_and_tenant
):
    """
    Tests successful partial update of an existing project using PATCH.
    """
    # Arrange: Create a user, tenant, and a project
    user, tenant = await create_test_user_and_tenant(
        tenant_name="Test Tenant Patch", user_email="patch-user@test.com"
    )
    headers = get_auth_headers(user_id=user.id, tenant_id=tenant.id)
    
    project_data = {
        "name": "Project to be Patched",
        "description": "Initial description.",
        "status": "draft"
    }
    response_create = await client.post("/api/v1/projects", json=project_data, headers=headers)
    assert response_create.status_code == 201
    project_id = response_create.json()["id"]
    original_name = response_create.json()["name"]
    current_version = response_create.json()["version"]

    patch_data = {
        "description": "Updated description via PATCH.",
        "status": "active",
        "expected_version": current_version,
    }

    # Act: Make the PATCH request
    response_patch = await client.patch(f"/api/v1/projects/{project_id}", json=patch_data, headers=headers)

    # Assert
    assert response_patch.status_code == 200
    updated_data = response_patch.json()

    assert updated_data["id"] == project_id
    assert updated_data["description"] == patch_data["description"]
    assert updated_data["status"] == patch_data["status"]
    # Verify that fields not in the patch data remain unchanged
    assert updated_data["name"] == original_name

async def test_delete_project_success(
    client: AsyncClient,
    get_auth_headers,
    create_test_user_and_tenant
):
    """
    Tests successful deletion of a project.
    """
    # Arrange
    user, tenant = await create_test_user_and_tenant(
        tenant_name="Test Tenant Delete", user_email="delete-user@test.com"
    )
    headers = get_auth_headers(user_id=user.id, tenant_id=tenant.id)
    project_data = {"name": "Project to be Deleted"}
    
    response_create = await client.post("/api/v1/projects", json=project_data, headers=headers)
    assert response_create.status_code == 201
    project_id = response_create.json()["id"]

    # Act
    response_delete = await client.delete(f"/api/v1/projects/{project_id}", headers=headers)

    # Assert
    assert response_delete.status_code == 204

    # Verify the project is gone
    response_get = await client.get(f"/api/v1/projects/{project_id}", headers=headers)
    assert response_get.status_code == 404


async def test_list_project_documents_polling_response(
    client: AsyncClient,
    get_auth_headers,
    create_test_user_and_tenant,
):
    """
    Tests document upload endpoint contract for an existing project.
    """
    user, tenant = await create_test_user_and_tenant(
        tenant_name="Test Tenant Docs", user_email="docs-user@test.com"
    )
    headers = get_auth_headers(user_id=user.id, tenant_id=tenant.id)

    create_response = await client.post(
        "/api/v1/projects",
        json={"name": "Docs Project"},
        headers=headers,
    )
    assert create_response.status_code == 201
    project_id = create_response.json()["id"]

    response = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        headers=headers,
        data={"document_type": "contract"},
        files={"file": ("contract.pdf", b"test file", "application/pdf")},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["project_id"] == project_id


async def test_list_project_documents_tenant_isolation(
    client: AsyncClient,
    get_auth_headers,
    create_test_user_and_tenant,
):
    """
    Verifies that a user cannot upload documents for a project in another tenant.
    """
    user_a, tenant_a = await create_test_user_and_tenant(
        tenant_name="Tenant A Docs", user_email="tenant-a-docs@test.com"
    )
    user_b, tenant_b = await create_test_user_and_tenant(
        tenant_name="Tenant B Docs", user_email="tenant-b-docs@test.com"
    )
    headers_b = get_auth_headers(user_id=user_b.id, tenant_id=tenant_b.id)

    headers_a = get_auth_headers(user_id=user_a.id, tenant_id=tenant_a.id)
    create_response = await client.post(
        "/api/v1/projects",
        json={"name": "Tenant A Project"},
        headers=headers_a,
    )
    assert create_response.status_code == 201
    project_id = create_response.json()["id"]

    response = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        headers=headers_b,
        data={"document_type": "contract"},
        files={"file": ("contract.pdf", b"test file", "application/pdf")},
    )

    assert response.status_code == 404
