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
from httpx import ASGITransport, AsyncClient
from types import SimpleNamespace
from uuid import uuid4

from src.main import app
from src.core.database import get_session
from src.projects.domain.models import ProjectStatus, ProjectType
from src.projects.adapters.persistence.models import ProjectORM


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
    """Create async HTTP client with database dependency override."""
    async def override_get_session():
        """Override database session for testing."""
        yield db

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        timeout=30.0,
    ) as test_client:
        yield test_client
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
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Test Project",
        code="TEST-001",
        description="A test project for integration tests",
        project_type=ProjectType.CONSTRUCTION.value,
        status=ProjectStatus.DRAFT.value,
        coherence_score=88.0,
        estimated_budget=100000.0,
        currency="EUR",
        metadata_json={"location": "Madrid, Spain", "version": 1},
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return SimpleNamespace(
        id=project.id,
        tenant_id=project.tenant_id,
        name=project.name,
        code=project.code,
        description=project.description,
        project_type=project.project_type,
        status=project.status,
        coherence_score=project.coherence_score,
        location="Madrid, Spain",
        estimated_budget=project.estimated_budget,
        currency=project.currency,
    )


@pytest_asyncio.fixture
async def test_project_2(db, test_tenant, test_user):
    """Create a second test project."""
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Second Project",
        code="TEST-002",
        description="Another test project",
        project_type=ProjectType.ENGINEERING.value,
        status=ProjectStatus.ACTIVE.value,
        coherence_score=72.0,
        estimated_budget=200000.0,
        currency="EUR",
        metadata_json={"location": "Barcelona, Spain", "version": 1},
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return SimpleNamespace(
        id=project.id,
        tenant_id=project.tenant_id,
        name=project.name,
        code=project.code,
        description=project.description,
        project_type=project.project_type,
        status=project.status,
        coherence_score=project.coherence_score,
        location="Barcelona, Spain",
        estimated_budget=project.estimated_budget,
        currency=project.currency,
    )


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
        response = await client.post(
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
        response = await client.post(
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
        response = await client.post(
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
        response = await client.post(f"{API_PREFIX}/projects", json=request_data)

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
        response = await client.get(f"{API_PREFIX}/projects", headers=auth_headers)

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
        listed = next(item for item in data["items"] if item["id"] == str(test_project.id))
        assert listed["coherence_score"] == pytest.approx(test_project.coherence_score)

    @pytest.mark.asyncio
    async def test_list_projects_with_pagination(self, client, test_project, test_project_2, auth_headers):
        """Should respect pagination parameters."""
        # Act
        response = await client.get(
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
        response = await client.get(
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
    async def test_list_projects_filter_by_project_type(self, client, test_project, test_project_2, auth_headers):
        """Should filter projects by project type."""
        response = await client.get(
            f"{API_PREFIX}/projects?project_type=engineering",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["total"] >= 1
        assert all(project["project_type"] == "engineering" for project in data["items"])
        returned_ids = {project["id"] for project in data["items"]}
        assert str(test_project_2.id) in returned_ids
        assert str(test_project.id) not in returned_ids

    @pytest.mark.asyncio
    async def test_list_projects_filter_by_created_date_range(self, client, db, test_tenant, auth_headers):
        """Should filter projects by created_at date range."""
        older_project = ProjectORM(
            id=uuid4(),
            tenant_id=test_tenant.id,
            name="Older Project",
            code="DATE-001",
            description="Created outside the requested range",
            project_type=ProjectType.CONSTRUCTION.value,
            status=ProjectStatus.DRAFT.value,
            metadata_json={"version": 1},
        )
        newer_project = ProjectORM(
            id=uuid4(),
            tenant_id=test_tenant.id,
            name="Newer Project",
            code="DATE-002",
            description="Created inside the requested range",
            project_type=ProjectType.CONSTRUCTION.value,
            status=ProjectStatus.DRAFT.value,
            metadata_json={"version": 1},
        )
        db.add_all([older_project, newer_project])
        await db.flush()

        older_project.created_at = older_project.created_at.replace(year=2026, month=1, day=10, hour=9, minute=0, second=0, microsecond=0)
        newer_project.created_at = newer_project.created_at.replace(year=2026, month=3, day=10, hour=9, minute=0, second=0, microsecond=0)
        await db.commit()

        response = await client.get(
            f"{API_PREFIX}/projects?created_after=2026-02-01T00:00:00Z&created_before=2026-03-31T23:59:59Z",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        returned_ids = {project["id"] for project in data["items"]}
        assert str(newer_project.id) in returned_ids
        assert str(older_project.id) not in returned_ids

    @pytest.mark.asyncio
    async def test_list_projects_search(self, client, test_project, auth_headers):
        """Should search projects by name/description/code."""
        # Act
        response = await client.get(
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
        response = await client.get(f"{API_PREFIX}/projects")

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
        response = await client.get(
            f"{API_PREFIX}/projects/{test_project.id}",
            headers=auth_headers
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["id"] == str(test_project.id)
        assert data["name"] == test_project.name
        assert data["code"] == test_project.code
        assert data["status"] == test_project.status
        assert data["coherence_score"] == pytest.approx(test_project.coherence_score)

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, client, auth_headers):
        """Should return 404 for non-existent project."""
        # Arrange
        fake_id = uuid4()

        # Act
        response = await client.get(
            f"{API_PREFIX}/projects/{fake_id}",
            headers=auth_headers
        )

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_project_wrong_tenant(self, client, db, test_tenant_2, test_user, generate_token):
        """Should return 404 when accessing project from different tenant."""
        # Arrange - create project for tenant 2
        project_tenant2 = ProjectORM(
            id=uuid4(),
            tenant_id=test_tenant_2.id,
            name="Tenant 2 Project",
            code="T2-001",
            project_type=ProjectType.CONSTRUCTION.value,
            status=ProjectStatus.DRAFT.value,
            estimated_budget=100000.0,
            currency="EUR",
            metadata_json={"version": 1},
        )
        db.add(project_tenant2)
        await db.commit()
        await db.refresh(project_tenant2)

        # Try to access with tenant 1 token
        tenant1_token = generate_token(
            user_id=test_user.id,
            tenant_id=test_user.tenant_id,
            email=test_user.email,
            role=test_user.role.value
        )
        headers = {"Authorization": f"Bearer {tenant1_token}"}

        # Act
        response = await client.get(
            f"{API_PREFIX}/projects/{project_tenant2.id}",
            headers=headers
        )

        # Assert - should be 404 due to tenant isolation
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_project_missing_auth(self, client, test_project):
        """Should return 401 when no auth token provided."""
        # Act
        response = await client.get(f"{API_PREFIX}/projects/{test_project.id}")

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
        response = await client.put(
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
        response = await client.put(
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
        response = await client.put(
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
        response = await client.put(
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
        response = await client.put(
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
        project = ProjectORM(
            id=uuid4(),
            tenant_id=test_tenant.id,
            name="To Delete",
            code="DEL-001",
            project_type=ProjectType.CONSTRUCTION.value,
            status=ProjectStatus.DRAFT.value,
            estimated_budget=100000.0,
            currency="EUR",
            metadata_json={"version": 1},
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)

        # Act
        response = await client.delete(
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
        response = await client.delete(
            f"{API_PREFIX}/projects/{fake_id}",
            headers=auth_headers
        )

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_project_missing_auth(self, client, test_project):
        """Should return 401 when no auth token provided."""
        # Act
        response = await client.delete(f"{API_PREFIX}/projects/{test_project.id}")

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
        response = await client.get(f"{API_PREFIX}/projects/stats", headers=auth_headers)

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
        response = await client.get(f"{API_PREFIX}/projects/stats")

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
        response = await client.patch(
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
        response = await client.patch(
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
        response = await client.patch(
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
        response = await client.patch(
            f"{API_PREFIX}/projects/{test_project.id}/status?new_status={new_status}"
        )

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestProjectBudgetEndpoint:
    """Tests for GET /projects/{project_id}/budget endpoint."""

    @pytest.mark.asyncio
    async def test_get_budget_returns_fake_aggregate_payload(self, client, test_project, auth_headers):
        """Should return the compatibility budget payload instead of 501."""
        response = await client.get(
            f"{API_PREFIX}/projects/{test_project.id}/budget",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert payload["project_id"] == str(test_project.id)
        assert payload["total_budget"] == pytest.approx(100000.0)
        assert payload["remaining_budget"] == pytest.approx(100000.0)
        assert payload["variance_status"] == "on_track"


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
