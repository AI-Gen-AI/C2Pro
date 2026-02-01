"""
Documents Repository Integration Tests (TDD - RED Phase)

Refers to Suite ID: TS-INT-DB-CLS-001.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from src.core.database import Base
from src.core.database import get_session_with_tenant
from src.projects.adapters.persistence.models import ProjectORM
from src.documents.adapters.persistence.models import DocumentORM, ClauseORM
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.documents.domain.models import Document, DocumentStatus, DocumentType, Clause, ClauseType


@pytest_asyncio.fixture(scope="session")
async def pg_engine():
    container = PostgresContainer("postgres:15-alpine")
    container.start()
    try:
        url = container.get_connection_url().replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield engine
    finally:
        await engine.dispose()
        container.stop()


@pytest_asyncio.fixture
async def session(pg_engine) -> AsyncSession:
    session_factory = async_sessionmaker(bind=pg_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        yield db


@pytest.mark.asyncio
async def test_clause_repository_crud_and_tenant_filtering(session: AsyncSession):
    """
    CRUD for Clause via SqlAlchemyDocumentRepository and tenant isolation.
    """
    tenant_a = uuid4()
    tenant_b = uuid4()
    project_a = ProjectORM(
        id=uuid4(),
        tenant_id=tenant_a,
        name="Tenant A Project",
        description=None,
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
    session.add(project_a)
    await session.commit()

    repo = SqlAlchemyDocumentRepository(session)

    document = Document(
        id=uuid4(),
        project_id=project_a.id,
        document_type=DocumentType.CONTRACT,
        filename="contract.pdf",
        upload_status=DocumentStatus.UPLOADED,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        document_metadata={},
    )
    await repo.add(document)
    await repo.commit()

    clause = Clause(
        id=uuid4(),
        project_id=project_a.id,
        document_id=document.id,
        clause_code="1.1",
        clause_type=ClauseType.SCOPE,
        title="Scope",
        full_text="Scope text",
        extraction_confidence=0.9,
    )
    await repo.add_clause(clause)
    await repo.commit()

    found = await repo.list_clauses_for_document(document.id)
    assert len(found) == 1
    assert found[0].clause_code == "1.1"

    # Critical security test: tenant isolation via RLS/session context
    async with get_session_with_tenant(tenant_b) as tenant_b_session:
        tenant_b_repo = SqlAlchemyDocumentRepository(tenant_b_session)
        clauses_for_tenant_b = await tenant_b_repo.list_clauses_for_document(document.id)
        assert clauses_for_tenant_b == []
