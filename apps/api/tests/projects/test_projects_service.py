"""
C2Pro - Projects Service Unit Tests

Comprehensive tests for project management service including:
- CRUD operations with tenant isolation
- Project querying and filtering
- Code uniqueness validation
- Statistics calculation
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from src.modules.projects.service import (
    get_project_by_id,
    get_project_by_code,
    ProjectService,
)
from src.modules.projects.models import Project, ProjectStatus, ProjectType
from src.modules.projects.schemas import (
    ProjectCreateRequest,
    ProjectUpdateRequest,
    ProjectFilters,
)
from src.modules.auth.models import Tenant, User
from src.core.exceptions import NotFoundError, ConflictError


# ===========================================
# HELPER FUNCTION TESTS
# ===========================================

class TestHelperFunctions:
    """Tests for project helper functions."""

    @pytest.mark.asyncio
    async def test_get_project_by_id_existing_project(self, db, test_tenant):
        """
        Should return project when ID exists and belongs to tenant.
        """
        # Create a project
        project = Project(
            tenant_id=test_tenant.id,
            name="Test Project",
            code="TEST-001",
            project_type=ProjectType.CONSTRUCTION,
            status=ProjectStatus.DRAFT,
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)

        # Retrieve by ID
        result = await get_project_by_id(db, project.id, test_tenant.id)

        assert result is not None
        assert result.id == project.id
        assert result.name == "Test Project"

    @pytest.mark.asyncio
    async def test_get_project_by_id_non_existing(self, db, test_tenant):
        """
        Should return None when project doesn't exist.
        """
        random_id = uuid4()
        result = await get_project_by_id(db, random_id, test_tenant.id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_project_by_id_wrong_tenant(self, db, test_tenant, test_tenant_2):
        """
        Should return None when project belongs to different tenant (tenant isolation).
        """
        # Create project for tenant 1
        project = Project(
            tenant_id=test_tenant.id,
            name="Tenant 1 Project",
            code="T1-001",
            project_type=ProjectType.CONSTRUCTION,
            status=ProjectStatus.DRAFT,
        )
        db.add(project)
        await db.commit()

        # Try to get with tenant 2 credentials
        result = await get_project_by_id(db, project.id, test_tenant_2.id)

        assert result is None  # Tenant isolation should prevent access

    @pytest.mark.asyncio
    async def test_get_project_by_code_existing(self, db, test_tenant):
        """
        Should return project when code exists in tenant.
        """
        project = Project(
            tenant_id=test_tenant.id,
            name="Coded Project",
            code="UNIQUE-CODE-123",
            project_type=ProjectType.ENGINEERING,
            status=ProjectStatus.ACTIVE,
        )
        db.add(project)
        await db.commit()

        result = await get_project_by_code(db, "UNIQUE-CODE-123", test_tenant.id)

        assert result is not None
        assert result.code == "UNIQUE-CODE-123"

    @pytest.mark.asyncio
    async def test_get_project_by_code_non_existing(self, db, test_tenant):
        """
        Should return None when code doesn't exist.
        """
        result = await get_project_by_code(db, "NON-EXISTENT", test_tenant.id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_project_by_code_tenant_isolation(self, db, test_tenant, test_tenant_2):
        """
        Should return None when code exists but in different tenant.
        """
        # Create project for tenant 1
        project = Project(
            tenant_id=test_tenant.id,
            name="Project",
            code="SHARED-CODE",
            project_type=ProjectType.CONSTRUCTION,
            status=ProjectStatus.DRAFT,
        )
        db.add(project)
        await db.commit()

        # Try to find in tenant 2
        result = await get_project_by_code(db, "SHARED-CODE", test_tenant_2.id)

        assert result is None  # Different tenant, should not find

    @pytest.mark.asyncio
    async def test_get_project_by_code_same_code_different_tenants(self, db, test_tenant, test_tenant_2):
        """
        Same code should be allowed in different tenants.
        """
        # Create project for tenant 1
        project1 = Project(
            tenant_id=test_tenant.id,
            name="Project 1",
            code="SAME-CODE",
            project_type=ProjectType.CONSTRUCTION,
            status=ProjectStatus.DRAFT,
        )
        # Create project for tenant 2 with same code
        project2 = Project(
            tenant_id=test_tenant_2.id,
            name="Project 2",
            code="SAME-CODE",
            project_type=ProjectType.INDUSTRIAL,
            status=ProjectStatus.ACTIVE,
        )
        db.add_all([project1, project2])
        await db.commit()

        # Should find project1 in tenant1
        result1 = await get_project_by_code(db, "SAME-CODE", test_tenant.id)
        assert result1 is not None
        assert result1.name == "Project 1"

        # Should find project2 in tenant2
        result2 = await get_project_by_code(db, "SAME-CODE", test_tenant_2.id)
        assert result2 is not None
        assert result2.name == "Project 2"


# ===========================================
# PROJECT SERVICE - CREATE TESTS
# ===========================================

class TestProjectServiceCreate:
    """Tests for project creation."""

    @pytest.mark.asyncio
    async def test_create_project_minimal_fields(self, db, test_tenant, test_user):
        """
        Should create project with only required fields.
        """
        request = ProjectCreateRequest(
            name="Minimal Project",
            project_type=ProjectType.CONSTRUCTION,
        )

        project = await ProjectService.create_project(
            db=db,
            tenant_id=test_tenant.id,
            user_id=test_user.id,
            request=request
        )

        assert project.id is not None
        assert project.tenant_id == test_tenant.id
        assert project.name == "Minimal Project"
        assert project.project_type == ProjectType.CONSTRUCTION
        assert project.status == ProjectStatus.DRAFT  # Always starts as draft

    @pytest.mark.asyncio
    async def test_create_project_all_fields(self, db, test_tenant, test_user):
        """
        Should create project with all optional fields.
        """
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=90)

        request = ProjectCreateRequest(
            name="Complete Project",
            description="A project with all fields filled",
            code="COMPLETE-001",
            project_type=ProjectType.INFRASTRUCTURE,
            estimated_budget=Decimal("1500000.00"),
            currency="EUR",
            start_date=start_date,
            end_date=end_date,
            metadata={"client": "ACME Corp", "priority": "high"}
        )

        project = await ProjectService.create_project(
            db=db,
            tenant_id=test_tenant.id,
            user_id=test_user.id,
            request=request
        )

        assert project.name == "Complete Project"
        assert project.description == "A project with all fields filled"
        assert project.code == "COMPLETE-001"
        assert project.project_type == ProjectType.INFRASTRUCTURE
        assert project.estimated_budget == Decimal("1500000.00")
        assert project.currency == "EUR"
        assert project.start_date == start_date
        assert project.end_date == end_date
        assert project.project_metadata == {"client": "ACME Corp", "priority": "high"}

    @pytest.mark.asyncio
    async def test_create_project_duplicate_code_same_tenant(self, db, test_tenant, test_user):
        """
        Should raise ConflictError when creating project with duplicate code in same tenant.
        """
        # Create first project
        request1 = ProjectCreateRequest(
            name="First Project",
            code="DUPLICATE-CODE",
            project_type=ProjectType.CONSTRUCTION,
        )
        await ProjectService.create_project(db, test_tenant.id, test_user.id, request1)

        # Try to create second project with same code
        request2 = ProjectCreateRequest(
            name="Second Project",
            code="DUPLICATE-CODE",
            project_type=ProjectType.ENGINEERING,
        )

        with pytest.raises(ConflictError, match="already exists"):
            await ProjectService.create_project(db, test_tenant.id, test_user.id, request2)

    @pytest.mark.asyncio
    async def test_create_project_same_code_different_tenants(self, db, test_tenant, test_tenant_2, test_user, test_user_2):
        """
        Should allow same code in different tenants.
        """
        request = ProjectCreateRequest(
            name="Project",
            code="MULTI-TENANT-CODE",
            project_type=ProjectType.OTHER,
        )

        # Create in tenant 1
        project1 = await ProjectService.create_project(
            db=db,
            tenant_id=test_tenant.id,
            user_id=test_user.id,
            request=request
        )

        # Create in tenant 2 with same code (should succeed)
        project2 = await ProjectService.create_project(
            db=db,
            tenant_id=test_tenant_2.id,
            user_id=test_user_2.id,
            request=request
        )

        assert project1.code == project2.code == "MULTI-TENANT-CODE"
        assert project1.tenant_id != project2.tenant_id


# ===========================================
# PROJECT SERVICE - GET TESTS
# ===========================================

class TestProjectServiceGet:
    """Tests for retrieving individual projects."""

    @pytest.mark.asyncio
    async def test_get_project_existing(self, db, test_tenant):
        """
        Should return project when it exists.
        """
        # Create project
        project = Project(
            tenant_id=test_tenant.id,
            name="Get Test Project",
            code="GET-001",
            project_type=ProjectType.CONSTRUCTION,
            status=ProjectStatus.ACTIVE,
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)

        # Get project
        result = await ProjectService.get_project(db, project.id, test_tenant.id)

        assert result.id == project.id
        assert result.name == "Get Test Project"

    @pytest.mark.asyncio
    async def test_get_project_non_existing(self, db, test_tenant):
        """
        Should raise NotFoundError when project doesn't exist.
        """
        random_id = uuid4()

        with pytest.raises(NotFoundError, match="Project not found"):
            await ProjectService.get_project(db, random_id, test_tenant.id)

    @pytest.mark.asyncio
    async def test_get_project_wrong_tenant(self, db, test_tenant, test_tenant_2):
        """
        Should raise NotFoundError when project belongs to different tenant.
        """
        # Create project for tenant 1
        project = Project(
            tenant_id=test_tenant.id,
            name="Isolated Project",
            project_type=ProjectType.CONSTRUCTION,
            status=ProjectStatus.DRAFT,
        )
        db.add(project)
        await db.commit()

        # Try to get with tenant 2 credentials
        with pytest.raises(NotFoundError, match="Project not found"):
            await ProjectService.get_project(db, project.id, test_tenant_2.id)


# ===========================================
# PROJECT SERVICE - LIST TESTS
# ===========================================

class TestProjectServiceList:
    """Tests for listing projects with pagination and filters."""

    @pytest.mark.asyncio
    async def test_list_projects_empty(self, db, test_tenant):
        """
        Should return empty list when no projects exist.
        """
        response = await ProjectService.list_projects(db, test_tenant.id)

        assert response.total == 0
        assert len(response.items) == 0
        assert response.page == 1
        assert response.total_pages == 1

    @pytest.mark.asyncio
    async def test_list_projects_pagination(self, db, test_tenant):
        """
        Should paginate results correctly.
        """
        # Create 25 projects
        projects = [
            Project(
                tenant_id=test_tenant.id,
                name=f"Project {i}",
                code=f"P-{i:03d}",
                project_type=ProjectType.CONSTRUCTION,
                status=ProjectStatus.ACTIVE,
            )
            for i in range(25)
        ]
        db.add_all(projects)
        await db.commit()

        # Get first page (default page_size=20)
        page1 = await ProjectService.list_projects(db, test_tenant.id, page=1, page_size=10)

        assert page1.total == 25
        assert len(page1.items) == 10
        assert page1.page == 1
        assert page1.total_pages == 3
        assert page1.has_next is True
        assert page1.has_prev is False

        # Get second page
        page2 = await ProjectService.list_projects(db, test_tenant.id, page=2, page_size=10)

        assert len(page2.items) == 10
        assert page2.page == 2
        assert page2.has_next is True
        assert page2.has_prev is True

        # Get third page
        page3 = await ProjectService.list_projects(db, test_tenant.id, page=3, page_size=10)

        assert len(page3.items) == 5  # Remaining items
        assert page3.page == 3
        assert page3.has_next is False
        assert page3.has_prev is True

    @pytest.mark.asyncio
    async def test_list_projects_tenant_isolation(self, db, test_tenant, test_tenant_2):
        """
        Should only return projects for specified tenant.
        """
        # Create projects for tenant 1
        for i in range(5):
            db.add(Project(
                tenant_id=test_tenant.id,
                name=f"Tenant 1 Project {i}",
                project_type=ProjectType.CONSTRUCTION,
                status=ProjectStatus.ACTIVE,
            ))

        # Create projects for tenant 2
        for i in range(3):
            db.add(Project(
                tenant_id=test_tenant_2.id,
                name=f"Tenant 2 Project {i}",
                project_type=ProjectType.ENGINEERING,
                status=ProjectStatus.DRAFT,
            ))

        await db.commit()

        # List for tenant 1
        response1 = await ProjectService.list_projects(db, test_tenant.id)
        assert response1.total == 5

        # List for tenant 2
        response2 = await ProjectService.list_projects(db, test_tenant_2.id)
        assert response2.total == 3

    @pytest.mark.asyncio
    async def test_list_projects_filter_by_status(self, db, test_tenant):
        """
        Should filter projects by status.
        """
        # Create projects with different statuses
        db.add_all([
            Project(tenant_id=test_tenant.id, name="Draft 1", project_type=ProjectType.CONSTRUCTION, status=ProjectStatus.DRAFT),
            Project(tenant_id=test_tenant.id, name="Draft 2", project_type=ProjectType.CONSTRUCTION, status=ProjectStatus.DRAFT),
            Project(tenant_id=test_tenant.id, name="Active 1", project_type=ProjectType.CONSTRUCTION, status=ProjectStatus.ACTIVE),
            Project(tenant_id=test_tenant.id, name="Completed 1", project_type=ProjectType.CONSTRUCTION, status=ProjectStatus.COMPLETED),
        ])
        await db.commit()

        # Filter by DRAFT
        filters = ProjectFilters(status=ProjectStatus.DRAFT)
        response = await ProjectService.list_projects(db, test_tenant.id, filters=filters)

        assert response.total == 2
        assert all(p.status == ProjectStatus.DRAFT for p in response.items)

    @pytest.mark.asyncio
    async def test_list_projects_filter_by_type(self, db, test_tenant):
        """
        Should filter projects by type.
        """
        db.add_all([
            Project(tenant_id=test_tenant.id, name="Const 1", project_type=ProjectType.CONSTRUCTION, status=ProjectStatus.DRAFT),
            Project(tenant_id=test_tenant.id, name="Eng 1", project_type=ProjectType.ENGINEERING, status=ProjectStatus.DRAFT),
            Project(tenant_id=test_tenant.id, name="Eng 2", project_type=ProjectType.ENGINEERING, status=ProjectStatus.DRAFT),
        ])
        await db.commit()

        filters = ProjectFilters(project_type=ProjectType.ENGINEERING)
        response = await ProjectService.list_projects(db, test_tenant.id, filters=filters)

        assert response.total == 2
        assert all(p.project_type == ProjectType.ENGINEERING for p in response.items)

    @pytest.mark.asyncio
    async def test_list_projects_search_by_name(self, db, test_tenant):
        """
        Should search projects by name.
        """
        db.add_all([
            Project(tenant_id=test_tenant.id, name="Airport Terminal", project_type=ProjectType.INFRASTRUCTURE, status=ProjectStatus.DRAFT),
            Project(tenant_id=test_tenant.id, name="Highway Bridge", project_type=ProjectType.INFRASTRUCTURE, status=ProjectStatus.DRAFT),
            Project(tenant_id=test_tenant.id, name="Office Building", project_type=ProjectType.CONSTRUCTION, status=ProjectStatus.DRAFT),
        ])
        await db.commit()

        # Search for "Airport"
        filters = ProjectFilters(search="Airport")
        response = await ProjectService.list_projects(db, test_tenant.id, filters=filters)

        assert response.total == 1
        assert response.items[0].name == "Airport Terminal"

    @pytest.mark.asyncio
    async def test_list_projects_search_by_code(self, db, test_tenant):
        """
        Should search projects by code.
        """
        db.add_all([
            Project(tenant_id=test_tenant.id, name="Project A", code="INFRA-2024-001", project_type=ProjectType.INFRASTRUCTURE, status=ProjectStatus.DRAFT),
            Project(tenant_id=test_tenant.id, name="Project B", code="CONST-2024-001", project_type=ProjectType.CONSTRUCTION, status=ProjectStatus.DRAFT),
        ])
        await db.commit()

        filters = ProjectFilters(search="INFRA")
        response = await ProjectService.list_projects(db, test_tenant.id, filters=filters)

        assert response.total == 1
        assert response.items[0].code == "INFRA-2024-001"

    @pytest.mark.asyncio
    async def test_list_projects_filter_by_date_range(self, db, test_tenant):
        """
        Should filter projects by creation date range.
        """
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)
        tomorrow = now + timedelta(days=1)

        # Create project and manually set created_at
        old_project = Project(
            tenant_id=test_tenant.id,
            name="Old Project",
            project_type=ProjectType.CONSTRUCTION,
            status=ProjectStatus.DRAFT,
        )
        db.add(old_project)
        await db.flush()
        old_project.created_at = yesterday

        new_project = Project(
            tenant_id=test_tenant.id,
            name="New Project",
            project_type=ProjectType.CONSTRUCTION,
            status=ProjectStatus.DRAFT,
        )
        db.add(new_project)
        await db.commit()

        # Filter for projects created after yesterday
        filters = ProjectFilters(created_after=yesterday)
        response = await ProjectService.list_projects(db, test_tenant.id, filters=filters)

        assert response.total >= 1  # At least the new project


# ===========================================
# PROJECT SERVICE - UPDATE TESTS
# ===========================================

class TestProjectServiceUpdate:
    """Tests for updating projects."""

    @pytest.mark.asyncio
    async def test_update_project_name(self, db, test_tenant):
        """
        Should update project name.
        """
        # Create project
        project = Project(
            tenant_id=test_tenant.id,
            name="Original Name",
            project_type=ProjectType.CONSTRUCTION,
            status=ProjectStatus.DRAFT,
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)

        # Update name
        request = ProjectUpdateRequest(name="Updated Name")
        updated = await ProjectService.update_project(db, project.id, test_tenant.id, request)

        assert updated.name == "Updated Name"
        assert updated.id == project.id

    @pytest.mark.asyncio
    async def test_update_project_multiple_fields(self, db, test_tenant):
        """
        Should update multiple fields at once.
        """
        project = Project(
            tenant_id=test_tenant.id,
            name="Project",
            project_type=ProjectType.CONSTRUCTION,
            status=ProjectStatus.DRAFT,
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)

        request = ProjectUpdateRequest(
            name="Updated Project",
            description="New description",
            status=ProjectStatus.ACTIVE,
            estimated_budget=Decimal("500000.00"),
            currency="USD"
        )

        updated = await ProjectService.update_project(db, project.id, test_tenant.id, request)

        assert updated.name == "Updated Project"
        assert updated.description == "New description"
        assert updated.status == ProjectStatus.ACTIVE
        assert updated.estimated_budget == Decimal("500000.00")
        assert updated.currency == "USD"

    @pytest.mark.asyncio
    async def test_update_project_code_to_duplicate(self, db, test_tenant):
        """
        Should raise ConflictError when updating code to duplicate value.
        """
        # Create two projects
        project1 = Project(
            tenant_id=test_tenant.id,
            name="Project 1",
            code="CODE-001",
            project_type=ProjectType.CONSTRUCTION,
            status=ProjectStatus.DRAFT,
        )
        project2 = Project(
            tenant_id=test_tenant.id,
            name="Project 2",
            code="CODE-002",
            project_type=ProjectType.CONSTRUCTION,
            status=ProjectStatus.DRAFT,
        )
        db.add_all([project1, project2])
        await db.commit()

        # Try to update project2's code to project1's code
        request = ProjectUpdateRequest(code="CODE-001")

        with pytest.raises(ConflictError, match="already exists"):
            await ProjectService.update_project(db, project2.id, test_tenant.id, request)

    @pytest.mark.asyncio
    async def test_update_project_code_to_same_value(self, db, test_tenant):
        """
        Should allow updating code to same value (no-op).
        """
        project = Project(
            tenant_id=test_tenant.id,
            name="Project",
            code="SAME-CODE",
            project_type=ProjectType.CONSTRUCTION,
            status=ProjectStatus.DRAFT,
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)

        # Update with same code
        request = ProjectUpdateRequest(code="SAME-CODE", name="Updated Name")
        updated = await ProjectService.update_project(db, project.id, test_tenant.id, request)

        assert updated.code == "SAME-CODE"
        assert updated.name == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_project_non_existing(self, db, test_tenant):
        """
        Should raise NotFoundError when project doesn't exist.
        """
        request = ProjectUpdateRequest(name="New Name")

        with pytest.raises(NotFoundError, match="Project not found"):
            await ProjectService.update_project(db, uuid4(), test_tenant.id, request)

    @pytest.mark.asyncio
    async def test_update_project_wrong_tenant(self, db, test_tenant, test_tenant_2):
        """
        Should raise NotFoundError when updating project from different tenant.
        """
        # Create project for tenant 1
        project = Project(
            tenant_id=test_tenant.id,
            name="Project",
            project_type=ProjectType.CONSTRUCTION,
            status=ProjectStatus.DRAFT,
        )
        db.add(project)
        await db.commit()

        # Try to update with tenant 2 credentials
        request = ProjectUpdateRequest(name="Hacked Name")

        with pytest.raises(NotFoundError, match="Project not found"):
            await ProjectService.update_project(db, project.id, test_tenant_2.id, request)


# ===========================================
# PROJECT SERVICE - DELETE TESTS
# ===========================================

class TestProjectServiceDelete:
    """Tests for deleting projects."""

    @pytest.mark.asyncio
    async def test_delete_project_existing(self, db, test_tenant):
        """
        Should delete project when it exists.
        """
        # Create project
        project = Project(
            tenant_id=test_tenant.id,
            name="To Delete",
            project_type=ProjectType.CONSTRUCTION,
            status=ProjectStatus.DRAFT,
        )
        db.add(project)
        await db.commit()
        project_id = project.id

        # Delete project
        await ProjectService.delete_project(db, project_id, test_tenant.id)

        # Verify deleted
        result = await get_project_by_id(db, project_id, test_tenant.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_project_non_existing(self, db, test_tenant):
        """
        Should raise NotFoundError when project doesn't exist.
        """
        with pytest.raises(NotFoundError, match="Project not found"):
            await ProjectService.delete_project(db, uuid4(), test_tenant.id)

    @pytest.mark.asyncio
    async def test_delete_project_wrong_tenant(self, db, test_tenant, test_tenant_2):
        """
        Should raise NotFoundError when deleting project from different tenant.
        """
        # Create project for tenant 1
        project = Project(
            tenant_id=test_tenant.id,
            name="Protected Project",
            project_type=ProjectType.CONSTRUCTION,
            status=ProjectStatus.ACTIVE,
        )
        db.add(project)
        await db.commit()

        # Try to delete with tenant 2 credentials
        with pytest.raises(NotFoundError, match="Project not found"):
            await ProjectService.delete_project(db, project.id, test_tenant_2.id)

        # Verify project still exists
        result = await get_project_by_id(db, project.id, test_tenant.id)
        assert result is not None


# ===========================================
# PROJECT SERVICE - STATS TESTS
# ===========================================

class TestProjectServiceStats:
    """Tests for project statistics."""

    @pytest.mark.asyncio
    async def test_get_project_stats_empty(self, db, test_tenant):
        """
        Should return zero stats when no projects exist.
        """
        stats = await ProjectService.get_project_stats(db, test_tenant.id)

        assert stats.total_projects == 0
        assert stats.active_projects == 0
        assert stats.draft_projects == 0
        assert stats.completed_projects == 0
        assert stats.archived_projects == 0
        assert stats.avg_coherence_score is None

    @pytest.mark.asyncio
    async def test_get_project_stats_by_status(self, db, test_tenant):
        """
        Should count projects by status correctly.
        """
        # Create projects with different statuses
        db.add_all([
            Project(tenant_id=test_tenant.id, name="Draft 1", project_type=ProjectType.CONSTRUCTION, status=ProjectStatus.DRAFT),
            Project(tenant_id=test_tenant.id, name="Draft 2", project_type=ProjectType.CONSTRUCTION, status=ProjectStatus.DRAFT),
            Project(tenant_id=test_tenant.id, name="Active 1", project_type=ProjectType.CONSTRUCTION, status=ProjectStatus.ACTIVE),
            Project(tenant_id=test_tenant.id, name="Active 2", project_type=ProjectType.CONSTRUCTION, status=ProjectStatus.ACTIVE),
            Project(tenant_id=test_tenant.id, name="Active 3", project_type=ProjectType.CONSTRUCTION, status=ProjectStatus.ACTIVE),
            Project(tenant_id=test_tenant.id, name="Completed 1", project_type=ProjectType.CONSTRUCTION, status=ProjectStatus.COMPLETED),
            Project(tenant_id=test_tenant.id, name="Archived 1", project_type=ProjectType.CONSTRUCTION, status=ProjectStatus.ARCHIVED),
        ])
        await db.commit()

        stats = await ProjectService.get_project_stats(db, test_tenant.id)

        assert stats.total_projects == 7
        assert stats.draft_projects == 2
        assert stats.active_projects == 3
        assert stats.completed_projects == 1
        assert stats.archived_projects == 1

    @pytest.mark.asyncio
    async def test_get_project_stats_coherence_score_average(self, db, test_tenant):
        """
        Should calculate average coherence score correctly.
        """
        # Create projects with coherence scores
        project1 = Project(
            tenant_id=test_tenant.id,
            name="Project 1",
            project_type=ProjectType.CONSTRUCTION,
            status=ProjectStatus.ACTIVE,
        )
        project1.coherence_score = 85.5

        project2 = Project(
            tenant_id=test_tenant.id,
            name="Project 2",
            project_type=ProjectType.CONSTRUCTION,
            status=ProjectStatus.ACTIVE,
        )
        project2.coherence_score = 92.3

        project3 = Project(
            tenant_id=test_tenant.id,
            name="Project 3",
            project_type=ProjectType.CONSTRUCTION,
            status=ProjectStatus.ACTIVE,
        )
        # No coherence score for this one

        db.add_all([project1, project2, project3])
        await db.commit()

        stats = await ProjectService.get_project_stats(db, test_tenant.id)

        # Average of 85.5 and 92.3 = 88.9
        assert stats.avg_coherence_score is not None
        assert abs(stats.avg_coherence_score - 88.9) < 0.1

    @pytest.mark.asyncio
    async def test_get_project_stats_tenant_isolation(self, db, test_tenant, test_tenant_2):
        """
        Should only calculate stats for specified tenant.
        """
        # Create projects for tenant 1
        for i in range(5):
            db.add(Project(
                tenant_id=test_tenant.id,
                name=f"T1 Project {i}",
                project_type=ProjectType.CONSTRUCTION,
                status=ProjectStatus.ACTIVE,
            ))

        # Create projects for tenant 2
        for i in range(3):
            db.add(Project(
                tenant_id=test_tenant_2.id,
                name=f"T2 Project {i}",
                project_type=ProjectType.ENGINEERING,
                status=ProjectStatus.DRAFT,
            ))

        await db.commit()

        # Get stats for tenant 1
        stats1 = await ProjectService.get_project_stats(db, test_tenant.id)
        assert stats1.total_projects == 5
        assert stats1.active_projects == 5

        # Get stats for tenant 2
        stats2 = await ProjectService.get_project_stats(db, test_tenant_2.id)
        assert stats2.total_projects == 3
        assert stats2.draft_projects == 3
