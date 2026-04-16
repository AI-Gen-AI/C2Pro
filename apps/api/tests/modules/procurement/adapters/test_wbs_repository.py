from datetime import timezone
"""
WBS Repository Integration Tests (TDD - RED Phase)
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from docker.errors import DockerException
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from src.config import settings
from src.core import database as database_module
from src.core.database import Base, get_session_with_tenant
from src.procurement.adapters.persistence.models import Base as ProcurementBase
from src.procurement.adapters.persistence.models import WBSItemORM
from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository
from src.procurement.domain.models import WBSItem
from src.projects.adapters.persistence.models import ProjectORM


@pytest_asyncio.fixture
async def pg_engine():
    container = None
    previous_session_factory = database_module._session_factory
    try:
        container = PostgresContainer("postgres:15-alpine")
        container.start()
    except DockerException:
        container = None
    engine = None
    try:
        if container is not None:
            url = container.get_connection_url()
            if url.startswith("postgresql+psycopg2://"):
                url = url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        else:
            url = settings.database_url
            if url.startswith("postgresql://"):
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
            try:
                async with engine.begin() as conn:
                    await conn.execute(text("DROP TABLE IF EXISTS procurement_bom_items CASCADE"))
                    await conn.execute(text("DROP TABLE IF EXISTS procurement_wbs_items CASCADE"))
                    await conn.run_sync(Base.metadata.drop_all, tables=[ProjectORM.__table__])
            except OperationalError:
                pass
            await engine.dispose()
        database_module._session_factory = previous_session_factory
        if container is not None:
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
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(project_a)
        await session.commit()

        root_code = f"1-{uuid4().hex[:6]}"
        child_code = f"{root_code}.1"
        parent = WBSItem(
            project_id=project_a.id,
            code=root_code,
            name="Root",
            level=1,
        )
        child = WBSItem(
            project_id=project_a.id,
            code=child_code,
            name="Child",
            level=2,
            parent_code=root_code,
        )

        async with get_session_with_tenant(tenant_a) as tenant_a_session:
            repo = SQLAlchemyWBSRepository(tenant_a_session)
            await repo.create(parent)
            await repo.create(child)

            tree = await repo.get_tree(project_id=project_a.id, tenant_id=tenant_a)
            assert len(tree) == 1
            assert tree[0].code == root_code
            assert len(tree[0].children) == 1
            assert tree[0].children[0].code == child_code

            by_code = await repo.get_by_code(
                project_id=project_a.id,
                wbs_code=child_code,
                tenant_id=tenant_a,
            )
            assert by_code is not None
            assert by_code.code == child_code

        async with get_session_with_tenant(tenant_b) as tenant_b_session:
            tenant_b_repo = SQLAlchemyWBSRepository(tenant_b_session)
            tree_b = await tenant_b_repo.get_tree(project_id=project_a.id, tenant_id=tenant_b)
            assert tree_b == []

    @pytest.mark.asyncio
    async def test_same_wbs_code_allowed_across_projects(self, session: AsyncSession):
        """Refers to Suite ID: TS-INT-DB-WBS-001."""
        tenant_id = uuid4()
        project_a = ProjectORM(
            id=uuid4(),
            tenant_id=tenant_id,
            name="Tenant Project A",
            description=None,
            code=f"PA-{uuid4().hex[:6]}",
            project_type="construction",
            status="draft",
            estimated_budget=1000.0,
            currency="EUR",
            start_date=None,
            end_date=None,
            coherence_score=None,
            last_analysis_at=None,
            metadata_json={},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        project_b = ProjectORM(
            id=uuid4(),
            tenant_id=tenant_id,
            name="Tenant Project B",
            description=None,
            code=f"PB-{uuid4().hex[:6]}",
            project_type="construction",
            status="draft",
            estimated_budget=1000.0,
            currency="EUR",
            start_date=None,
            end_date=None,
            coherence_score=None,
            last_analysis_at=None,
            metadata_json={},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add_all([project_a, project_b])
        await session.commit()

        code = "1"
        item_a = WBSItem(project_id=project_a.id, code=code, name="A", level=1)
        item_b = WBSItem(project_id=project_b.id, code=code, name="B", level=1)

        async with get_session_with_tenant(tenant_id) as tenant_session:
            repo = SQLAlchemyWBSRepository(tenant_session)
            created_a = await repo.create(item_a)
            created_b = await repo.create(item_b)

            assert created_a.code == code
            assert created_b.code == code
            assert created_a.project_id != created_b.project_id
