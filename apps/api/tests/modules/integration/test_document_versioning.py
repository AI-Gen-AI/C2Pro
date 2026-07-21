"""
TDD RED Phase: Tests for document versioning and re-upload flow
Part of TASK-BCK-023

These tests will FAIL until implementation is complete.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select, text

from src.core.database import init_db


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_database():
    """Initialize global database connection for versioning tests."""
    await init_db()
    yield


@pytest_asyncio.fixture
async def test_project(db):
    """Create a test project for document versioning tests."""
    from src.core.auth.models import Tenant
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
    await db.refresh(project)

    return project


@pytest.mark.requires_services
class TestDocumentVersioningSchema:
    """Test that document versioning schema exists in database."""

    @pytest.mark.asyncio
    async def test_version_column_exists(self, db):
        """GIVEN database schema WHEN querying documents columns THEN version column exists."""
        result = await db.execute(
            text("""
                SELECT column_name, data_type, column_default
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'documents' AND column_name = 'version'
            """)
        )
        row = result.fetchone()

        assert row is not None
        assert row[0] == "version"
        assert row[1] == "integer"
        assert "1" in str(row[2])  # Default value should be 1

    @pytest.mark.asyncio
    async def test_file_hash_column_exists(self, db):
        """GIVEN database schema WHEN querying documents columns THEN file_hash column exists."""
        result = await db.execute(
            text("""
                SELECT column_name, data_type, character_maximum_length
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'documents' AND column_name = 'file_hash'
            """)
        )
        row = result.fetchone()

        assert row is not None
        assert row[0] == "file_hash"
        assert row[1] == "character varying"
        assert row[2] == 64

    @pytest.mark.asyncio
    async def test_file_hash_index_exists(self, db):
        """GIVEN database schema WHEN querying indexes THEN file_hash index exists."""
        result = await db.execute(
            text("""
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public' AND tablename = 'documents' AND indexname = 'ix_documents_file_hash'
            """)
        )
        row = result.fetchone()

        assert row is not None
        assert row[0] == "ix_documents_file_hash"

    @pytest.mark.asyncio
    async def test_id_version_index_exists(self, db):
        """GIVEN database schema WHEN querying indexes THEN id+version composite index exists."""
        result = await db.execute(
            text("""
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public' AND tablename = 'documents' AND indexname = 'ix_documents_id_version'
            """)
        )
        row = result.fetchone()

        assert row is not None
        assert row[0] == "ix_documents_id_version"


@pytest.mark.requires_services
class TestDocumentVersionTracking:
    """Test document version tracking behavior."""

    @pytest.mark.asyncio
    async def test_new_document_defaults_to_version_1(self, db, test_project):
        """
        GIVEN a new document is created
        WHEN no version is specified
        THEN version defaults to 1.
        """
        from src.documents.adapters.persistence.models import DocumentORM

        document = DocumentORM(
            id=uuid4(),
            project_id=test_project.id,
            document_type="contract",
            filename="test.pdf",
            upload_status="uploaded",
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)

        assert document.version == 1

    @pytest.mark.asyncio
    async def test_document_file_hash_can_be_set(self, db, test_project):
        """
        GIVEN a new document is created
        WHEN file_hash is provided
        THEN file_hash is stored correctly.
        """
        from src.documents.adapters.persistence.models import DocumentORM

        test_hash = hashlib.sha256(b"test content").hexdigest()

        document = DocumentORM(
            id=uuid4(),
            project_id=test_project.id,
            document_type="contract",
            filename="test.pdf",
            upload_status="uploaded",
            file_hash=test_hash,
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)

        assert document.file_hash == test_hash

    @pytest.mark.asyncio
    async def test_version_can_be_incremented(self, db, test_project):
        """
        GIVEN a document exists
        WHEN version is explicitly incremented
        THEN version value is updated.
        """
        from src.documents.adapters.persistence.models import DocumentORM

        document = DocumentORM(
            id=uuid4(),
            project_id=test_project.id,
            document_type="contract",
            filename="test.pdf",
            upload_status="uploaded",
            version=1,
        )
        db.add(document)
        await db.commit()

        # Increment version
        document.version = 2
        await db.commit()
        await db.refresh(document)

        assert document.version == 2


@pytest.mark.requires_services
class TestReUploadDetection:
    """Test re-upload detection logic."""

    @pytest.mark.asyncio
    async def test_duplicate_file_hash_detection(self, db, test_project):
        """
        GIVEN a document with file_hash exists
        WHEN querying by file_hash
        THEN document is found.
        """
        from src.documents.adapters.persistence.models import DocumentORM

        test_hash = hashlib.sha256(b"test content").hexdigest()

        document = DocumentORM(
            id=uuid4(),
            project_id=test_project.id,
            document_type="contract",
            filename="test.pdf",
            upload_status="uploaded",
            file_hash=test_hash,
        )
        db.add(document)
        await db.commit()

        # Query by file_hash
        result = await db.execute(
            select(DocumentORM).where(DocumentORM.file_hash == test_hash)
        )
        found_document = result.scalar_one_or_none()

        assert found_document is not None
        assert found_document.id == document.id

    @pytest.mark.asyncio
    async def test_different_file_hash_creates_new_version(self, db, test_project):
        """
        GIVEN a document exists with file_hash A
        WHEN a new document with same ID but file_hash B is created
        THEN this should trigger version increment logic.

        Note: This test defines the requirement - implementation will handle this.
        """
        from src.documents.adapters.persistence.models import DocumentORM

        doc_id = uuid4()
        hash_v1 = hashlib.sha256(b"version 1 content").hexdigest()

        # Create version 1
        document_v1 = DocumentORM(
            id=doc_id,
            project_id=test_project.id,
            document_type="contract",
            filename="test.pdf",
            upload_status="parsed",
            file_hash=hash_v1,
            version=1,
        )
        db.add(document_v1)
        await db.commit()

        # In real implementation, re-upload would:
        # 1. Detect different file_hash
        # 2. Increment version
        # 3. Update file_hash
        # This test just verifies schema supports it
        hash_v2 = hashlib.sha256(b"version 2 content").hexdigest()
        document_v1.version = 2
        document_v1.file_hash = hash_v2
        await db.commit()
        await db.refresh(document_v1)

        assert document_v1.version == 2
        assert document_v1.file_hash == hash_v2


@pytest.mark.requires_services
class TestCancelInProgressAnalysis:
    """Test canceling in-progress analysis when document is re-uploaded."""

    @pytest.mark.asyncio
    async def test_analysis_status_can_be_updated(self, db, test_project):
        """
        GIVEN a document in PARSED_PENDING_ANALYSIS status
        WHEN re-upload occurs
        THEN status can be updated to cancel analysis.

        Note: Actual cancel logic will be in use case layer.
        """
        from src.documents.adapters.persistence.models import DocumentORM
        from src.documents.domain.models import DocumentStatus

        document = DocumentORM(
            id=uuid4(),
            project_id=test_project.id,
            document_type="contract",
            filename="test.pdf",
            upload_status=DocumentStatus.PARSED_PENDING_ANALYSIS,
            version=1,
        )
        db.add(document)
        await db.commit()

        # Simulate cancel by resetting to UPLOADED for re-processing
        document.upload_status = DocumentStatus.UPLOADED
        document.version = 2
        await db.commit()
        await db.refresh(document)

        assert document.upload_status == DocumentStatus.UPLOADED
        assert document.version == 2


@pytest.mark.requires_services
class TestVersionHistory:
    """Test version history tracking (future feature - defines requirements)."""

    @pytest.mark.asyncio
    async def test_query_by_document_id_and_version(self, db, test_project):
        """
        GIVEN multiple versions of a document
        WHEN querying by (id, version)
        THEN correct version is retrieved.

        Note: This test defines future requirement for version history.
        Current implementation stores only latest version.
        """
        from src.documents.adapters.persistence.models import DocumentORM

        doc_id = uuid4()

        document = DocumentORM(
            id=doc_id,
            project_id=test_project.id,
            document_type="contract",
            filename="test.pdf",
            upload_status="parsed",
            version=2,  # Simulating version 2
        )
        db.add(document)
        await db.commit()

        # Query by id and version
        result = await db.execute(
            select(DocumentORM).where(
                DocumentORM.id == doc_id,
                DocumentORM.version == 2
            )
        )
        found = result.scalar_one_or_none()

        assert found is not None
        assert found.version == 2


# Run these tests with: pytest apps/api/tests/modules/integration/test_document_versioning.py -v
# Expected: Tests should PASS after schema migration is applied
