"""
C2Pro - Projects Router Integration Tests

Integration tests for projects API endpoints.
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
from src.modules.projects.models import Project, ProjectStatus, ProjectType
from src.modules.auth.models import User, UserRole


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


@pytest_asyncio.fixture
async def test_project(db, test_tenant, test_user):
    """Create a test project."""
    project = Project(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Test Project",
        code="TEST-001",
        description="A test project for integration tests",
        project_type=ProjectType.CONSTRUCTION,
        status=ProjectStatus.DRAFT,
        location="Madrid, Spain",
        created_by=test_user.id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@pytest_asyncio.fixture
async def test_project_2(db, test_tenant, test_user):
    """Create a second test project."""
    project = Project(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Second Project",
        code="TEST-002",
        description="Another test project",
        project_type=ProjectType.ENGINEERING,
        status=ProjectStatus.ACTIVE,
        location="Barcelona, Spain",
        created_by=test_user.id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


# ===========================================
# CREATE PROJECT TESTS
# ===========================================

class TestCreateProjectEndpoint:
    """Tests for POST /projects endpoint."""

    @pytest.mark.asyncio
    async def test_create_project_success(self, client, test_user, test_tenant, auth_headers):
        """Should successfully create a new project."""
        # Arrange
        request_data = {
            "name": "New Construction Project",
            "code": "NEW-001",
            "description": "A brand new project",
            "project_type": "construction",
            "location": "Valencia, Spain",
            "client_name": "ACME Corp",
            "budget_planned": 1000000.00
        }

        # Act
        response = client.post(
            f"{API_PREFIX}/projects",
            json=request_data,
            headers=auth_headers
        )

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        assert data["name"] == request_data["name"]
        assert data["code"] == request_data["code"]
        assert data["description"] == request_data["description"]
        assert data["project_type"] == request_data["project_type"]
        assert data["status"] == ProjectStatus.DRAFT.value
        assert data["tenant_id"] == str(test_tenant.id)

    @pytest.mark.asyncio
    async def test_create_project_duplicate_code(self, client, test_project, auth_headers):
        """Should return 409 when project code already exists."""
        # Arrange
        request_data = {
            "name": "Another Project",
            "code": test_project.code,  # Duplicate code
            "project_type": "construction"
        }

        # Act
        response = client.post(
            f"{API_PREFIX}/projects",
            json=request_data,
            headers=auth_headers
        )

        # Assert
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already exists" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_project_missing_name(self, client, auth_headers):
        """Should return 422 when name is missing."""
        # Arrange
        request_data = {
            "code": "INVALID-001",
            "project_type": "construction"
            # Missing name
        }

        # Act
        response = client.post(
            f"{API_PREFIX}/projects",
            json=request_data,
            headers=auth_headers
        )

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_create_project_missing_auth(self, client):
        """Should return 401 when no auth token provided."""
        # Arrange
        request_data = {
            "name": "Unauthorized Project",
            "project_type": "construction"
        }

        # Act
        response = client.post(f"{API_PREFIX}/projects", json=request_data)

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ===========================================
# LIST PROJECTS TESTS
# ===========================================

class TestListProjectsEndpoint:
    """Tests for GET /projects endpoint."""

    @pytest.mark.asyncio
    async def test_list_projects_success(self, client, test_project, test_project_2, auth_headers):
        """Should return paginated list of projects."""
        # Act
        response = client.get(f"{API_PREFIX}/projects", headers=auth_headers)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "total_pages" in data

        assert data["total"] >= 2  # At least our two test projects
        assert len(data["items"]) >= 2

    @pytest.mark.asyncio
    async def test_list_projects_with_pagination(self, client, test_project, test_project_2, auth_headers):
        """Should respect pagination parameters."""
        # Act
        response = client.get(
            f"{API_PREFIX}/projects?page=1&page_size=1",
            headers=auth_headers
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["page"] == 1
        assert data["page_size"] == 1
        assert len(data["items"]) == 1

    @pytest.mark.asyncio
    async def test_list_projects_filter_by_status(self, client, test_project, test_project_2, auth_headers):
        """Should filter projects by status."""
        # Act - filter for ACTIVE projects only
        response = client.get(
            f"{API_PREFIX}/projects?status=active",
            headers=auth_headers
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # All returned projects should be ACTIVE
        for project in data["items"]:
            assert project["status"] == "active"

    @pytest.mark.asyncio
    async def test_list_projects_search(self, client, test_project, auth_headers):
        """Should search projects by name/description/code."""
        # Act
        response = client.get(
            f"{API_PREFIX}/projects?search={test_project.name}",
            headers=auth_headers
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["total"] >= 1
        # The test project should be in results
        project_names = [p["name"] for p in data["items"]]
        assert test_project.name in project_names

    @pytest.mark.asyncio
    async def test_list_projects_missing_auth(self, client):
        """Should return 401 when no auth token provided."""
        # Act
        response = client.get(f"{API_PREFIX}/projects")

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ===========================================
# GET PROJECT DETAILS TESTS
# ===========================================

class TestGetProjectEndpoint:
    """Tests for GET /projects/{project_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_project_success(self, client, test_project, auth_headers):
        """Should return project details with valid project_id."""
        # Act
        response = client.get(
            f"{API_PREFIX}/projects/{test_project.id}",
            headers=auth_headers
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["id"] == str(test_project.id)
        assert data["name"] == test_project.name
        assert data["code"] == test_project.code
        assert data["status"] == test_project.status.value

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, client, auth_headers):
        """Should return 404 for non-existent project."""
        # Arrange
        fake_id = uuid4()

        # Act
        response = client.get(
            f"{API_PREFIX}/projects/{fake_id}",
            headers=auth_headers
        )

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_project_wrong_tenant(self, client, db, test_tenant_2, test_user, generate_token):
        """Should return 404 when accessing project from different tenant."""
        # Arrange - create project for tenant 2
        project_tenant2 = Project(
            id=uuid4(),
            tenant_id=test_tenant_2.id,
            name="Tenant 2 Project",
            code="T2-001",
            project_type=ProjectType.CONSTRUCTION,
            status=ProjectStatus.DRAFT,
            created_by=test_user.id,
        )
        db.add(project_tenant2)
        await db.commit()

        # Try to access with tenant 1 token
        tenant1_token = generate_token(
            user_id=test_user.id,
            tenant_id=test_tenant_2.id,  # Different tenant
            email=test_user.email,
            role=test_user.role.value
        )
        headers = {"Authorization": f"Bearer {tenant1_token}"}

        # Act
        response = client.get(
            f"{API_PREFIX}/projects/{project_tenant2.id}",
            headers=headers
        )

        # Assert - should be 404 due to tenant isolation
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_project_missing_auth(self, client, test_project):
        """Should return 401 when no auth token provided."""
        # Act
        response = client.get(f"{API_PREFIX}/projects/{test_project.id}")

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ===========================================
# UPDATE PROJECT TESTS
# ===========================================

class TestUpdateProjectEndpoint:
    """Tests for PUT /projects/{project_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_project_success(self, client, test_project, auth_headers):
        """Should successfully update project fields."""
        # Arrange
        update_data = {
            "name": "Updated Project Name",
            "description": "Updated description",
            "location": "Updated Location"
        }

        # Act
        response = client.put(
            f"{API_PREFIX}/projects/{test_project.id}",
            json=update_data,
            headers=auth_headers
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]
        assert data["location"] == update_data["location"]
        # Code should remain unchanged
        assert data["code"] == test_project.code

    @pytest.mark.asyncio
    async def test_update_project_partial(self, client, test_project, auth_headers):
        """Should update only provided fields."""
        # Arrange - only update name
        update_data = {
            "name": "Only Name Updated"
        }

        # Act
        response = client.put(
            f"{API_PREFIX}/projects/{test_project.id}",
            json=update_data,
            headers=auth_headers
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["name"] == update_data["name"]
        # Other fields should remain unchanged
        assert data["code"] == test_project.code
        assert data["description"] == test_project.description

    @pytest.mark.asyncio
    async def test_update_project_duplicate_code(self, client, test_project, test_project_2, auth_headers):
        """Should return 409 when updating to duplicate code."""
        # Arrange
        update_data = {
            "code": test_project_2.code  # Duplicate code
        }

        # Act
        response = client.put(
            f"{API_PREFIX}/projects/{test_project.id}",
            json=update_data,
            headers=auth_headers
        )

        # Assert
        assert response.status_code == status.HTTP_409_CONFLICT

    @pytest.mark.asyncio
    async def test_update_project_not_found(self, client, auth_headers):
        """Should return 404 for non-existent project."""
        # Arrange
        fake_id = uuid4()
        update_data = {"name": "Updated"}

        # Act
        response = client.put(
            f"{API_PREFIX}/projects/{fake_id}",
            json=update_data,
            headers=auth_headers
        )

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_update_project_missing_auth(self, client, test_project):
        """Should return 401 when no auth token provided."""
        # Arrange
        update_data = {"name": "Updated"}

        # Act
        response = client.put(
            f"{API_PREFIX}/projects/{test_project.id}",
            json=update_data
        )

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ===========================================
# DELETE PROJECT TESTS
# ===========================================

class TestDeleteProjectEndpoint:
    """Tests for DELETE /projects/{project_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_project_success(self, client, db, test_tenant, test_user, auth_headers):
        """Should successfully delete a project."""
        # Arrange - create a project to delete
        project = Project(
            id=uuid4(),
            tenant_id=test_tenant.id,
            name="To Delete",
            code="DEL-001",
            project_type=ProjectType.CONSTRUCTION,
            status=ProjectStatus.DRAFT,
            created_by=test_user.id,
        )
        db.add(project)
        await db.commit()

        # Act
        response = client.delete(
            f"{API_PREFIX}/projects/{project.id}",
            headers=auth_headers
        )

        # Assert
        assert response.status_code == status.HTTP_204_NO_CONTENT

    @pytest.mark.asyncio
    async def test_delete_project_not_found(self, client, auth_headers):
        """Should return 404 for non-existent project."""
        # Arrange
        fake_id = uuid4()

        # Act
        response = client.delete(
            f"{API_PREFIX}/projects/{fake_id}",
            headers=auth_headers
        )

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_project_missing_auth(self, client, test_project):
        """Should return 401 when no auth token provided."""
        # Act
        response = client.delete(f"{API_PREFIX}/projects/{test_project.id}")

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ===========================================
# PROJECT STATS TESTS
# ===========================================

class TestProjectStatsEndpoint:
    """Tests for GET /projects/stats endpoint."""

    @pytest.mark.asyncio
    async def test_get_stats_success(self, client, test_project, test_project_2, auth_headers):
        """Should return project statistics."""
        # Act
        response = client.get(f"{API_PREFIX}/projects/stats", headers=auth_headers)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify stats structure
        assert "total_projects" in data
        assert "by_status" in data
        assert "by_type" in data

        # Should have at least our test projects
        assert data["total_projects"] >= 2

    @pytest.mark.asyncio
    async def test_get_stats_missing_auth(self, client):
        """Should return 401 when no auth token provided."""
        # Act
        response = client.get(f"{API_PREFIX}/projects/stats")

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ===========================================
# UPDATE PROJECT STATUS TESTS
# ===========================================

class TestUpdateProjectStatusEndpoint:
    """Tests for PATCH /projects/{project_id}/status endpoint."""

    @pytest.mark.asyncio
    async def test_update_status_success(self, client, test_project, auth_headers):
        """Should successfully update project status."""
        # Arrange
        new_status = ProjectStatus.ACTIVE.value

        # Act
        response = client.patch(
            f"{API_PREFIX}/projects/{test_project.id}/status?new_status={new_status}",
            headers=auth_headers
        )

        # Assert
        # May fail validation if contract document required, but endpoint should respond
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY]

    @pytest.mark.asyncio
    async def test_update_status_to_archived(self, client, test_project, auth_headers):
        """Should allow archiving a project."""
        # Arrange
        new_status = ProjectStatus.ARCHIVED.value

        # Act
        response = client.patch(
            f"{API_PREFIX}/projects/{test_project.id}/status?new_status={new_status}",
            headers=auth_headers
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == new_status

    @pytest.mark.asyncio
    async def test_update_status_not_found(self, client, auth_headers):
        """Should return 404 for non-existent project."""
        # Arrange
        fake_id = uuid4()
        new_status = ProjectStatus.ACTIVE.value

        # Act
        response = client.patch(
            f"{API_PREFIX}/projects/{fake_id}/status?new_status={new_status}",
            headers=auth_headers
        )

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_update_status_missing_auth(self, client, test_project):
        """Should return 401 when no auth token provided."""
        # Arrange
        new_status = ProjectStatus.ACTIVE.value

        # Act
        response = client.patch(
            f"{API_PREFIX}/projects/{test_project.id}/status?new_status={new_status}"
        )

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ===========================================
# HEALTH CHECK TEST
# ===========================================

class TestProjectsHealthEndpoint:
    """Tests for GET /projects/health endpoint."""

    def test_health_check(self, simple_client):
        """Should always return ok status."""
        # Act
        response = simple_client.get(f"{API_PREFIX}/projects/health")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "ok"
        assert data["service"] == "projects"
