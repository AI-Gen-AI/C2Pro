"""
TS-INT-DOC-VER-002: Document re-upload endpoint integration tests.
"""
from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture
async def test_user_and_project(db):
    """Create test user and project for re-upload tests."""
    from src.core.auth.models import Tenant, User
    from src.projects.adapters.persistence.models import ProjectORM

    # Create tenant
    tenant = Tenant(
        id=uuid4(),
        name="Test Tenant",
        slug=f"test-{uuid4().hex[:8]}",
        subscription_plan="professional",
        is_active=True,
    )
    db.add(tenant)
    await db.commit()

    # Create user
    user = User(
        id=uuid4(),
        tenant_id=tenant.id,
        email="test@example.com",
        first_name="Test",
        last_name="User",
        role="admin",
    )
    db.add(user)
    await db.commit()

    # Create project
    project = ProjectORM(
        id=uuid4(),
        tenant_id=tenant.id,
        name="Test Project",
        code="TEST-001",
        start_date=datetime.now(),
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    return {"user": user, "project": project, "tenant": tenant}


@pytest_asyncio.fixture
async def test_document(db, test_user_and_project):
    """Create a test document for re-upload tests."""
    from src.documents.adapters.persistence.models import DocumentORM

    project = test_user_and_project["project"]
    user = test_user_and_project["user"]

    document = DocumentORM(
        id=uuid4(),
        project_id=project.id,
        document_type="contract",
        filename="test.pdf",
        upload_status="parsed",
        file_hash=hashlib.sha256(b"original content").hexdigest(),
        version=1,
        created_by=user.id,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    return document


class TestDocumentReuploadEndpoint:
    """Test PATCH /api/v1/documents/{id}/file endpoint."""

    @pytest.mark.asyncio
    async def test_reupload_endpoint_exists(
        self,
        client: AsyncClient,
        test_document,
        get_auth_headers: Callable,
        test_user_and_project,
    ):
        """
        GIVEN a document exists
        WHEN calling PATCH /api/v1/documents/{id}/file
        THEN endpoint responds (not 404).
        """
        headers = get_auth_headers(
            user=test_user_and_project["user"],
            tenant=test_user_and_project["tenant"],
        )

        response = await client.patch(
            f"/api/v1/documents/{test_document.id}/file",
            files={"file": ("test_new.pdf", b"new content", "application/pdf")},
            headers=headers,
        )

        assert response.status_code != 404

    @pytest.mark.asyncio
    async def test_reupload_with_same_hash_returns_no_change(
        self,
        client: AsyncClient,
        test_document,
        get_auth_headers: Callable,
        test_user_and_project,
    ):
        """
        GIVEN a document exists
        WHEN re-uploading same file (same hash)
        THEN version is NOT incremented.
        """

        original_hash = test_document.file_hash
        original_version = test_document.version
        headers = get_auth_headers(
            user=test_user_and_project["user"],
            tenant=test_user_and_project["tenant"],
        )

        response = await client.patch(
            f"/api/v1/documents/{test_document.id}/file",
            files={"file": ("test.pdf", b"original content", "application/pdf")},
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["version"] == original_version
        assert data["file_hash"] == original_hash

    @pytest.mark.asyncio
    async def test_reupload_with_different_hash_increments_version(
        self,
        client: AsyncClient,
        test_document,
        get_auth_headers: Callable,
        test_user_and_project,
    ):
        """
        GIVEN a document exists at version 1
        WHEN re-uploading different file (different hash)
        THEN version is incremented to 2.
        """
        original_version = test_document.version
        original_hash = test_document.file_hash
        headers = get_auth_headers(
            user=test_user_and_project["user"],
            tenant=test_user_and_project["tenant"],
        )

        response = await client.patch(
            f"/api/v1/documents/{test_document.id}/file",
            files={"file": ("test_v2.pdf", b"new version content", "application/pdf")},
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["version"] == original_version + 1
        assert data["file_hash"] != original_hash

    @pytest.mark.asyncio
    async def test_reupload_cancels_in_progress_analysis(
        self,
        client: AsyncClient,
        test_document,
        db,
        get_auth_headers: Callable,
        test_user_and_project,
    ):
        """
        GIVEN a document in PARSED_PENDING_ANALYSIS status
        WHEN re-uploading
        THEN status resets to UPLOADED for re-processing.
        """
        from src.documents.domain.models import DocumentStatus

        # Set document to pending analysis
        test_document.upload_status = DocumentStatus.PARSED_PENDING_ANALYSIS
        db.add(test_document)
        await db.commit()
        headers = get_auth_headers(
            user=test_user_and_project["user"],
            tenant=test_user_and_project["tenant"],
        )

        response = await client.patch(
            f"/api/v1/documents/{test_document.id}/file",
            files={"file": ("test_v2.pdf", b"new version content", "application/pdf")},
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["upload_status"] in ["uploaded", "queued"]

    @pytest.mark.asyncio
    async def test_reupload_nonexistent_document_returns_404(
        self,
        client: AsyncClient,
        get_auth_headers: Callable,
        test_user_and_project,
    ):
        """
        GIVEN a document does not exist
        WHEN calling PATCH /api/v1/documents/{id}/file
        THEN returns 404.
        """
        nonexistent_id = uuid4()
        headers = get_auth_headers(
            user=test_user_and_project["user"],
            tenant=test_user_and_project["tenant"],
        )

        response = await client.patch(
            f"/api/v1/documents/{nonexistent_id}/file",
            files={"file": ("test.pdf", b"content", "application/pdf")},
            headers=headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_reupload_without_file_returns_400(
        self,
        client: AsyncClient,
        test_document,
        get_auth_headers: Callable,
        test_user_and_project,
    ):
        """
        GIVEN a document exists
        WHEN calling PATCH without file parameter
        THEN returns 400 Bad Request.
        """
        headers = get_auth_headers(
            user=test_user_and_project["user"],
            tenant=test_user_and_project["tenant"],
        )

        response = await client.patch(
            f"/api/v1/documents/{test_document.id}/file",
            headers=headers,
        )

        assert response.status_code in [400, 422]
