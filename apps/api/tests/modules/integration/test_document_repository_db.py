"""
Document Repository + Database Integration Tests (TS-INT-DB-DOC-001)

Refers to Suite ID: TS-INT-DB-DOC-001.

Tests the SqlAlchemyDocumentRepository against an in-memory SQLite database.
Validates CRUD operations, tenant isolation (simulated), and relationship management between Documents and Clauses.

Note: Uses SQLite for fast integration tests without external dependencies.
For full PostgreSQL RLS testing, see test_document_repository.py.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core import database as database_module
from src.core.auth.models import Tenant, User
from src.core.database import Base, get_session_with_tenant
from src.documents.adapters.persistence.models import ClauseORM, DocumentORM
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.documents.domain.models import Clause, ClauseType, Document, DocumentStatus, DocumentType
from src.projects.adapters.persistence.models import ProjectORM


@pytest_asyncio.fixture(scope="module")
async def sqlite_engine():
    """Create test SQLite in-memory engine."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Create all required tables
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                Tenant.__table__,
                User.__table__,
                ProjectORM.__table__,
                DocumentORM.__table__,
                ClauseORM.__table__,
            ],
        )

    # Set up session factory
    database_module._session_factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )

    yield engine

    await engine.dispose()
    database_module._session_factory = None


@pytest_asyncio.fixture
async def session(sqlite_engine) -> AsyncSession:
    """Create a fresh database session for each test."""
    session_factory = async_sessionmaker(
        bind=sqlite_engine,
        expire_on_commit=False,
        class_=AsyncSession
    )
    async with session_factory() as db:
        yield db


@pytest_asyncio.fixture
async def tenant_a_id() -> UUID:
    """Tenant A identifier."""
    return uuid4()


@pytest_asyncio.fixture
async def tenant_b_id() -> UUID:
    """Tenant B identifier."""
    return uuid4()


@pytest_asyncio.fixture
async def project_a(session: AsyncSession, tenant_a_id: UUID) -> ProjectORM:
    """Create a project for Tenant A."""
    project = ProjectORM(
        id=uuid4(),
        tenant_id=tenant_a_id,
        name="Tenant A Project",
        description="Test project for tenant A",
        code="A-1",
        project_type="construction",
        status="draft",
        estimated_budget=1000.0,
        currency="EUR",
        start_date=None,
        end_date=None,
        coherence_score=None,
        last_analysis_at=None,
        metadata_json={},
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


@pytest_asyncio.fixture
async def project_b(session: AsyncSession, tenant_b_id: UUID) -> ProjectORM:
    """Create a project for Tenant B."""
    project = ProjectORM(
        id=uuid4(),
        tenant_id=tenant_b_id,
        name="Tenant B Project",
        description="Test project for tenant B",
        code="B-1",
        project_type="construction",
        status="draft",
        estimated_budget=2000.0,
        currency="USD",
        start_date=None,
        end_date=None,
        coherence_score=None,
        last_analysis_at=None,
        metadata_json={},
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


@pytest.mark.asyncio
class TestDocumentRepositoryDB:
    """Refers to Suite ID: TS-INT-DB-DOC-001"""

    async def test_001_add_document(
        self, session: AsyncSession, tenant_a_id: UUID, project_a: ProjectORM
    ) -> None:
        """Test adding a document to the repository."""
        document = Document(
            id=uuid4(),
            project_id=project_a.id,
            document_type=DocumentType.CONTRACT,
            filename="contract.pdf",
            upload_status=DocumentStatus.UPLOADED,
            storage_url="s3://bucket/contract.pdf",
            file_size_bytes=2048,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            document_metadata={"source": "upload"},
        )

        repo = SqlAlchemyDocumentRepository(session)
        await repo.add(document)
        await repo.commit()

        # Verify it was added
        loaded = await repo.get_by_id(document.id)
        assert loaded is not None
        assert loaded.id == document.id
        assert loaded.filename == "contract.pdf"
        assert loaded.document_type == DocumentType.CONTRACT

    async def test_002_get_document_by_id(
        self, session: AsyncSession, tenant_a_id: UUID, project_a: ProjectORM
    ) -> None:
        """Test retrieving a document by ID."""
        document = Document(
            id=uuid4(),
            project_id=project_a.id,
            document_type=DocumentType.TECHNICAL_SPEC,
            filename="specs.pdf",
            upload_status=DocumentStatus.PARSED,
            storage_url="s3://bucket/specs.pdf",
            file_size_bytes=4096,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            document_metadata={},
        )

        repo = SqlAlchemyDocumentRepository(session)
        await repo.add(document)
        await repo.commit()

        loaded = await repo.get_by_id(document.id)
        assert loaded is not None
        assert loaded.id == document.id
        assert loaded.filename == "specs.pdf"
        assert loaded.file_size_bytes == 4096

        # Test non-existent ID
        non_existent = await repo.get_by_id(uuid4())
        assert non_existent is None

    async def test_003_get_document_with_clauses(
        self, session: AsyncSession, tenant_a_id: UUID, project_a: ProjectORM
    ) -> None:
        """Test retrieving a document with its clauses eagerly loaded."""
        document = Document(
            id=uuid4(),
            project_id=project_a.id,
            document_type=DocumentType.CONTRACT,
            filename="contract_with_clauses.pdf",
            upload_status=DocumentStatus.PARSED,
            storage_url="s3://bucket/contract_with_clauses.pdf",
            file_size_bytes=8192,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            document_metadata={},
        )

        clause1 = Clause(
            id=uuid4(),
            project_id=project_a.id,
            document_id=document.id,
            clause_code="1.1",
            clause_type=ClauseType.SCOPE,
            title="Project Scope",
            full_text="The scope of this project includes...",
            extraction_confidence=0.95,
        )

        clause2 = Clause(
            id=uuid4(),
            project_id=project_a.id,
            document_id=document.id,
            clause_code="2.1",
            clause_type=ClauseType.PAYMENT,
            title="Payment Terms",
            full_text="Payment shall be made within...",
            extraction_confidence=0.92,
        )

        repo = SqlAlchemyDocumentRepository(session)
        await repo.add(document)
        await repo.add_clause(clause1)
        await repo.add_clause(clause2)
        await repo.commit()

        loaded = await repo.get_document_with_clauses(document.id)
        assert loaded is not None
        assert loaded.id == document.id
        assert len(loaded.clauses) == 2
        assert loaded.clauses[0].clause_code in ["1.1", "2.1"]
        assert loaded.clauses[1].clause_code in ["1.1", "2.1"]

    async def test_004_update_document_status(
        self, session: AsyncSession, tenant_a_id: UUID, project_a: ProjectORM
    ) -> None:
        """Test updating document status."""
        document = Document(
            id=uuid4(),
            project_id=project_a.id,
            document_type=DocumentType.CONTRACT,
            filename="contract_to_parse.pdf",
            upload_status=DocumentStatus.UPLOADED,
            storage_url="s3://bucket/contract_to_parse.pdf",
            file_size_bytes=1024,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            document_metadata={},
        )

        repo = SqlAlchemyDocumentRepository(session)
        await repo.add(document)
        await repo.commit()

        # Update status to PARSING
        await repo.update_status(document.id, DocumentStatus.PARSING)
        await repo.commit()

        loaded = await repo.get_by_id(document.id)
        assert loaded.upload_status == DocumentStatus.PARSING

        # Update status to PARSED
        await repo.update_status(document.id, DocumentStatus.PARSED)
        await repo.commit()

        loaded = await repo.get_by_id(document.id)
        assert loaded.upload_status == DocumentStatus.PARSED

    async def test_005_update_storage_path(
        self, session: AsyncSession, tenant_a_id: UUID, project_a: ProjectORM
    ) -> None:
        """Test updating document storage path."""
        document = Document(
            id=uuid4(),
            project_id=project_a.id,
            document_type=DocumentType.CONTRACT,
            filename="contract_move.pdf",
            upload_status=DocumentStatus.UPLOADED,
            storage_url="s3://bucket/temp/contract_move.pdf",
            file_size_bytes=1024,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            document_metadata={},
        )

        repo = SqlAlchemyDocumentRepository(session)
        await repo.add(document)
        await repo.commit()

        # Update storage path
        new_path = "s3://bucket/permanent/contract_move.pdf"
        await repo.update_storage_path(document.id, new_path)
        await repo.commit()

        loaded = await repo.get_by_id(document.id)
        assert loaded.storage_url == new_path

    async def test_006_delete_document(
        self, session: AsyncSession, tenant_a_id: UUID, project_a: ProjectORM
    ) -> None:
        """Test deleting a document."""
        document = Document(
            id=uuid4(),
            project_id=project_a.id,
            document_type=DocumentType.CONTRACT,
            filename="contract_to_delete.pdf",
            upload_status=DocumentStatus.UPLOADED,
            storage_url="s3://bucket/contract_to_delete.pdf",
            file_size_bytes=1024,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            document_metadata={},
        )

        repo = SqlAlchemyDocumentRepository(session)
        await repo.add(document)
        await repo.commit()

        # Verify it exists
        loaded = await repo.get_by_id(document.id)
        assert loaded is not None

        # Delete it
        await repo.delete(document.id)
        await repo.commit()

        # Verify it's gone
        deleted = await repo.get_by_id(document.id)
        assert deleted is None

    async def test_007_list_documents_for_project_with_pagination(
        self, session: AsyncSession, tenant_a_id: UUID, project_a: ProjectORM
    ) -> None:
        """Test listing documents with pagination."""
        # Create 5 documents
        documents = []
        for i in range(5):
            doc = Document(
                id=uuid4(),
                project_id=project_a.id,
                document_type=DocumentType.TECHNICAL_SPEC,
                filename=f"spec_{i}.pdf",
                upload_status=DocumentStatus.UPLOADED,
                storage_url=f"s3://bucket/spec_{i}.pdf",
                file_size_bytes=1024 * (i + 1),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                document_metadata={},
            )
            documents.append(doc)

        repo = SqlAlchemyDocumentRepository(session)
        for doc in documents:
            await repo.add(doc)
        await repo.commit()

        # Test: Get first page (2 items)
        page1, total = await repo.list_for_project(project_a.id, skip=0, limit=2)
        assert len(page1) == 2
        assert total == 5

        # Test: Get second page (2 items)
        page2, total = await repo.list_for_project(project_a.id, skip=2, limit=2)
        assert len(page2) == 2
        assert total == 5

        # Test: Get third page (1 item remaining)
        page3, total = await repo.list_for_project(project_a.id, skip=4, limit=2)
        assert len(page3) == 1
        assert total == 5

    async def test_008_add_clause(
        self, session: AsyncSession, tenant_a_id: UUID, project_a: ProjectORM
    ) -> None:
        """Test adding a clause to the repository."""
        document = Document(
            id=uuid4(),
            project_id=project_a.id,
            document_type=DocumentType.CONTRACT,
            filename="contract_for_clause.pdf",
            upload_status=DocumentStatus.PARSED,
            storage_url="s3://bucket/contract_for_clause.pdf",
            file_size_bytes=2048,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            document_metadata={},
        )

        clause = Clause(
            id=uuid4(),
            project_id=project_a.id,
            document_id=document.id,
            clause_code="3.1",
            clause_type=ClauseType.DELIVERY,
            title="Delivery Schedule",
            full_text="Materials shall be delivered according to...",
            extraction_confidence=0.88,
        )

        repo = SqlAlchemyDocumentRepository(session)
        await repo.add(document)
        await repo.add_clause(clause)
        await repo.commit()

        # Verify clause was added
        exists = await repo.clause_exists(clause.id)
        assert exists is True

    async def test_009_list_clauses_for_document(
        self, session: AsyncSession, tenant_a_id: UUID, project_a: ProjectORM
    ) -> None:
        """Test listing all clauses for a specific document."""
        document = Document(
            id=uuid4(),
            project_id=project_a.id,
            document_type=DocumentType.CONTRACT,
            filename="contract_multi_clause.pdf",
            upload_status=DocumentStatus.PARSED,
            storage_url="s3://bucket/contract_multi_clause.pdf",
            file_size_bytes=4096,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            document_metadata={},
        )

        clauses = []
        for i in range(3):
            clause = Clause(
                id=uuid4(),
                project_id=project_a.id,
                document_id=document.id,
                clause_code=f"{i+1}.0",
                clause_type=ClauseType.GENERAL,
                title=f"Clause {i+1}",
                full_text=f"Text for clause {i+1}",
                extraction_confidence=0.9,
            )
            clauses.append(clause)

        repo = SqlAlchemyDocumentRepository(session)
        await repo.add(document)
        for clause in clauses:
            await repo.add_clause(clause)
        await repo.commit()

        loaded_clauses = await repo.list_clauses_for_document(document.id)
        assert len(loaded_clauses) == 3
        assert all(c.document_id == document.id for c in loaded_clauses)

    async def test_010_tenant_isolation_simulated(
        self,
        session: AsyncSession,
        tenant_a_id: UUID,
        tenant_b_id: UUID,
        project_a: ProjectORM,
        project_b: ProjectORM,
    ) -> None:
        """Test tenant isolation by verifying documents belong to correct projects."""
        doc_a = Document(
            id=uuid4(),
            project_id=project_a.id,
            document_type=DocumentType.CONTRACT,
            filename="tenant_a_contract.pdf",
            upload_status=DocumentStatus.UPLOADED,
            storage_url="s3://bucket/tenant_a_contract.pdf",
            file_size_bytes=1024,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            document_metadata={},
        )

        doc_b = Document(
            id=uuid4(),
            project_id=project_b.id,
            document_type=DocumentType.CONTRACT,
            filename="tenant_b_contract.pdf",
            upload_status=DocumentStatus.UPLOADED,
            storage_url="s3://bucket/tenant_b_contract.pdf",
            file_size_bytes=1024,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            document_metadata={},
        )

        repo = SqlAlchemyDocumentRepository(session)
        await repo.add(doc_a)
        await repo.add(doc_b)
        await repo.commit()

        # Verify documents are isolated by project
        docs_a, total_a = await repo.list_for_project(project_a.id, skip=0, limit=10)
        assert len(docs_a) == 1
        assert docs_a[0].id == doc_a.id

        docs_b, total_b = await repo.list_for_project(project_b.id, skip=0, limit=10)
        assert len(docs_b) == 1
        assert docs_b[0].id == doc_b.id

    async def test_011_list_for_project_empty_result(
        self, session: AsyncSession, tenant_a_id: UUID, project_a: ProjectORM
    ) -> None:
        """Test listing documents for a project with no documents returns empty list."""
        repo = SqlAlchemyDocumentRepository(session)

        docs, total = await repo.list_for_project(project_a.id, skip=0, limit=10)
        assert docs == []
        assert total == 0

    async def test_012_get_clause_by_document_and_code(
        self, session: AsyncSession, tenant_a_id: UUID, project_a: ProjectORM
    ) -> None:
        """Test retrieving a specific clause by document ID and clause code."""
        document = Document(
            id=uuid4(),
            project_id=project_a.id,
            document_type=DocumentType.CONTRACT,
            filename="contract_specific_clause.pdf",
            upload_status=DocumentStatus.PARSED,
            storage_url="s3://bucket/contract_specific_clause.pdf",
            file_size_bytes=2048,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            document_metadata={},
        )

        clause1 = Clause(
            id=uuid4(),
            project_id=project_a.id,
            document_id=document.id,
            clause_code="5.2",
            clause_type=ClauseType.WARRANTY,
            title="Warranty Period",
            full_text="The warranty period shall be...",
            extraction_confidence=0.94,
        )

        clause2 = Clause(
            id=uuid4(),
            project_id=project_a.id,
            document_id=document.id,
            clause_code="5.3",
            clause_type=ClauseType.WARRANTY,
            title="Warranty Coverage",
            full_text="The warranty covers...",
            extraction_confidence=0.91,
        )

        repo = SqlAlchemyDocumentRepository(session)
        await repo.add(document)
        await repo.add_clause(clause1)
        await repo.add_clause(clause2)
        await repo.commit()

        # Find specific clause by code
        found = await repo.get_clause_by_document_and_code(document.id, "5.2")
        assert found is not None
        assert found.id == clause1.id
        assert found.clause_code == "5.2"
        assert found.title == "Warranty Period"

        # Find another clause
        found2 = await repo.get_clause_by_document_and_code(document.id, "5.3")
        assert found2 is not None
        assert found2.id == clause2.id

        # Non-existent clause code
        not_found = await repo.get_clause_by_document_and_code(document.id, "9.9")
        assert not_found is None
