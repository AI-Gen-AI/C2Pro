"""
WBS Repository Integration Tests (TDD - RED Phase)
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from src.core import database as database_module
from src.core.database import Base, get_session_with_tenant
from src.procurement.adapters.persistence.models import Base as ProcurementBase, WBSItemORM
from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository
from src.procurement.domain.models import WBSItem
from src.projects.adapters.persistence.models import ProjectORM


@pytest_asyncio.fixture
async def pg_engine():
    container = PostgresContainer("postgres:15-alpine")
    container.start()
    engine = None
    try:
        url = container.get_connection_url()
        if url.startswith("postgresql+psycopg2://"):
            url = url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, tables=[ProjectORM.__table__])
            await conn.run_sync(ProcurementBase.metadata.create_all, tables=[WBSItemORM.__table__])
        database_module._session_factory = async_sessionmaker(
            bind=engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )
        yield engine
    finally:
        if engine is not None:
            await engine.dispose()
        database_module._session_factory = None
        container.stop()


@pytest_asyncio.fixture
async def session(pg_engine) -> AsyncSession:
    session_factory = async_sessionmaker(bind=pg_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        yield db


class TestWBSRepositoryIntegration:
    """Refers to Suite ID: TS-INT-DB-WBS-001."""

    @pytest.mark.asyncio
    async def test_wbs_tree_hierarchy_and_tenant_filtering(self, session: AsyncSession):
        """
        WBS tree retrieval should include parent/child and enforce tenant isolation.
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

        parent = WBSItem(
            project_id=project_a.id,
            code="1",
            name="Root",
            level=1,
        )
        child = WBSItem(
            project_id=project_a.id,
            code="1.1",
            name="Child",
            level=2,
            parent_code="1",
        )

        async with get_session_with_tenant(tenant_a) as tenant_a_session:
            repo = SQLAlchemyWBSRepository(tenant_a_session)
            await repo.create(parent)
            await repo.create(child)

            tree = await repo.get_tree(project_id=project_a.id, tenant_id=tenant_a)
            assert len(tree) == 1
            assert tree[0].code == "1"
            assert len(tree[0].children) == 1
            assert tree[0].children[0].code == "1.1"

            by_code = await repo.get_by_code(project_id=project_a.id, wbs_code="1.1", tenant_id=tenant_a)
            assert by_code is not None
            assert by_code.code == "1.1"

        async with get_session_with_tenant(tenant_b) as tenant_b_session:
            tenant_b_repo = SQLAlchemyWBSRepository(tenant_b_session)
            tree_b = await tenant_b_repo.get_tree(project_id=project_a.id, tenant_id=tenant_b)
            assert tree_b == []
