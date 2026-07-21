"""
TDD RED Phase: Tests for DLQ (Dead Letter Queue) operations
Part of TASK-BCK-022

These tests will FAIL until DLQ implementation is complete.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select, text

from src.core.database import init_db


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_database():
    """Initialize global database connection for DLQ service tests."""
    # DLQService uses get_session_with_tenant() which needs init_db()
    await init_db()
    yield


@pytest_asyncio.fixture
async def test_document(db):
    """Create a test document for DLQ foreign key constraint."""
    from src.core.auth.models import Tenant
    from src.documents.adapters.persistence.models import DocumentORM
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

    # Create document
    document = DocumentORM(
        id=uuid4(),
        project_id=project.id,
        tenant_id=tenant.id,
        document_type="contract",
        filename="test.pdf",
        upload_status="parsed",
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    return document


class TestDLQTableExists:
    """Test that dlq_failed_tasks table exists in database."""

    @pytest.mark.asyncio
    async def test_dlq_table_exists(self, db):
        """GIVEN database schema WHEN querying dlq_failed_tasks THEN table exists."""
        # Query pg_tables to check table existence
        result = await db.execute(
            text("""
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public' AND tablename = 'dlq_failed_tasks'
            """)
        )
        table_exists = result.scalar_one_or_none()

        assert table_exists == "dlq_failed_tasks"

    @pytest.mark.asyncio
    async def test_dlq_table_has_required_columns(self, db):
        """GIVEN dlq_failed_tasks table WHEN inspecting schema THEN all required columns exist."""
        # Query information_schema to check columns
        result = await db.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'dlq_failed_tasks'
            """)
        )
        columns = {row[0] for row in result.fetchall()}

        required_columns = {
            "id",
            "tenant_id",
            "task_type",
            "document_id",
            "payload_json",
            "error_message",
            "error_traceback",
            "retry_count",
            "max_retries",
            "status",
            "created_at",
            "updated_at",
            "next_retry_at",
        }

        assert required_columns.issubset(columns), f"Missing columns: {required_columns - columns}"


class TestDLQService:
    """Test DLQ service operations."""

    @pytest.mark.asyncio
    async def test_push_to_dlq_creates_record(self, db, test_document):
        """
        GIVEN an analysis trigger failure
        WHEN pushing to DLQ
        THEN a record is created in dlq_failed_tasks.
        """
        from src.core.dlq.dlq_service import DLQService
        from src.projects.adapters.persistence.models import ProjectORM

        # Get tenant_id from test_document's project
        project = await db.get(ProjectORM, test_document.project_id)
        tenant_id = project.tenant_id
        document_id = test_document.id

        dlq_service = DLQService()
        dlq_id = await dlq_service.push(
            tenant_id=tenant_id,
            task_type="document_analysis",
            document_id=document_id,
            payload={"document_id": str(document_id)},
            error_message="Analysis orchestrator unavailable",
            error_traceback="Traceback...",
        )

        # Verify record created
        from src.core.dlq.models import DLQFailedTask

        result = await db.execute(
            select(DLQFailedTask).where(DLQFailedTask.id == dlq_id)
        )
        dlq_record = result.scalar_one_or_none()

        assert dlq_record is not None
        assert dlq_record.task_type == "document_analysis"
        assert dlq_record.document_id == document_id
        assert dlq_record.status == "pending"
        assert dlq_record.retry_count == 0
        assert dlq_record.max_retries == 3

    @pytest.mark.asyncio
    async def test_dlq_calculates_next_retry_exponential_backoff(self, db, test_document):
        """
        GIVEN a DLQ record with retry_count=1
        WHEN calculating next_retry_at
        THEN exponential backoff is applied (2^retry_count minutes).
        """
        from src.core.dlq.dlq_service import DLQService
        from src.projects.adapters.persistence.models import ProjectORM

        # Get tenant_id from test_document's project
        project = await db.get(ProjectORM, test_document.project_id)
        tenant_id = project.tenant_id
        document_id = test_document.id

        dlq_service = DLQService()
        dlq_id = await dlq_service.push(
            tenant_id=tenant_id,
            task_type="document_analysis",
            document_id=document_id,
            payload={"document_id": str(document_id)},
            error_message="Transient failure",
        )

        # Simulate retry
        await dlq_service.increment_retry(dlq_id)

        from src.core.dlq.models import DLQFailedTask

        result = await db.execute(
            select(DLQFailedTask).where(DLQFailedTask.id == dlq_id)
        )
        dlq_record = result.scalar_one()

        # Retry 1: 2^1 = 2 minutes
        expected_next_retry = dlq_record.updated_at + timedelta(minutes=2)
        assert abs((dlq_record.next_retry_at - expected_next_retry).total_seconds()) < 1

    @pytest.mark.asyncio
    async def test_dlq_status_exhausted_after_max_retries(self, db, test_document):
        """
        GIVEN a DLQ record with retry_count=3
        WHEN incrementing retry
        THEN status becomes 'exhausted' (no more retries).
        """
        from src.core.dlq.dlq_service import DLQService
        from src.projects.adapters.persistence.models import ProjectORM

        # Get tenant_id from test_document's project
        project = await db.get(ProjectORM, test_document.project_id)
        tenant_id = project.tenant_id
        document_id = test_document.id

        dlq_service = DLQService()
        dlq_id = await dlq_service.push(
            tenant_id=tenant_id,
            task_type="document_analysis",
            document_id=document_id,
            payload={"document_id": str(document_id)},
            error_message="Permanent failure",
        )

        # Simulate 3 retries
        for _ in range(3):
            await dlq_service.increment_retry(dlq_id)

        from src.core.dlq.models import DLQFailedTask

        result = await db.execute(
            select(DLQFailedTask).where(DLQFailedTask.id == dlq_id)
        )
        dlq_record = result.scalar_one()

        assert dlq_record.status == "exhausted"
        assert dlq_record.retry_count == 3
        assert dlq_record.next_retry_at is None


class TestDLQAdminEndpoint:
    """Legacy RED-phase placeholders for unimplemented DLQ admin endpoints."""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Legacy RED-phase placeholder; admin DLQ endpoints are not implemented in-app.")
    async def test_get_dlq_list_returns_pending_tasks(self):
        """
        GIVEN DLQ records exist
        WHEN calling GET /api/v1/admin/dlq
        THEN all pending tasks are returned.
        """
        # This will FAIL until we implement the endpoint
        from httpx import AsyncClient

        async with AsyncClient() as client:
            response = await client.get(
                "http://localhost:8000/api/v1/admin/dlq",
                params={"status": "pending"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "tasks" in data
            assert isinstance(data["tasks"], list)

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Legacy RED-phase placeholder; admin DLQ endpoints are not implemented in-app.")
    async def test_retry_dlq_task_endpoint_triggers_reanalysis(self):
        """
        GIVEN a DLQ record
        WHEN calling POST /api/v1/admin/dlq/{id}/retry
        THEN task is retried and status updated.
        """
        # This will FAIL until we implement retry endpoint
        from httpx import AsyncClient

        dlq_id = uuid4()

        async with AsyncClient() as client:
            response = await client.post(
                f"http://localhost:8000/api/v1/admin/dlq/{dlq_id}/retry"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "retrying"


# Run these tests with: pytest apps/api/tests/modules/integration/test_dlq_operations.py -v
# Expected: ALL TESTS FAIL (RED phase)
