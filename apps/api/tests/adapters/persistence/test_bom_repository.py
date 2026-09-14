
"""
BOM Repository Integration Tests (TDD - RED Phase)

BOM lines are downstream of the canonical Project Controls WBS (``wbs_nodes``, ADR-025).

Refers to Suite ID: TS-INT-DB-BOM-001.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from docker.errors import DockerException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

from src.core import database as core_database
from src.core.database import Base, get_session_with_tenant
from src.procurement.adapters.persistence.bom_repository import SQLAlchemyBOMRepository
from src.procurement.adapters.persistence.models import BOMItemORM, BudgetItemORM
from src.procurement.domain.models import BOMCategory, BOMItem, ProcurementStatus
from src.projects.adapters.persistence.models import ProjectORM
from src.wbs.adapters.persistence.models import WBSNodeORM


@pytest_asyncio.fixture(scope="session")
async def pg_engine():
    try:
        container = PostgresContainer("postgres:15-alpine")
        container.start()
    except DockerException as exc:
        pytest.skip(f"Docker unavailable for testcontainers: {exc}")
    engine = None
    try:
        url = container.get_connection_url()
        url = url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(
            url,
            echo=False,
            poolclass=NullPool,
            connect_args={"statement_cache_size": 0},
        )
        core_database._engine = engine
        core_database._session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, tables=[ProjectORM.__table__])
            # Minimal FK-target stubs (tenants for the canonical WBS, documents for source lineage).
            await conn.execute(text("CREATE TABLE IF NOT EXISTS tenants (id uuid PRIMARY KEY)"))
            await conn.execute(text("CREATE TABLE IF NOT EXISTS documents (id uuid PRIMARY KEY)"))
            await conn.run_sync(
                Base.metadata.create_all,
                tables=[
                    BudgetItemORM.__table__,
                    WBSNodeORM.__table__,
                    BOMItemORM.__table__,
                ],
            )
        yield engine
    finally:
        core_database._engine = None
        core_database._session_factory = None
        if engine is not None:
            await engine.dispose()
        if container is not None:
            container.stop()


@pytest_asyncio.fixture
async def session(pg_engine) -> AsyncSession:
    session_factory = async_sessionmaker(bind=pg_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        yield db


def _project(tenant_id, code: str) -> ProjectORM:
    return ProjectORM(
        id=uuid4(),
        tenant_id=tenant_id,
        name="Tenant A Project",
        description=None,
        code=code,
        project_type="construction",
        status="draft",
        estimated_budget=5000.0,
        currency="EUR",
        start_date=None,
        end_date=None,
        coherence_score=None,
        last_analysis_at=None,
        metadata_json={},
        created_at=datetime.now(UTC).replace(tzinfo=None),
        updated_at=datetime.now(UTC).replace(tzinfo=None),
    )


async def _canonical_node(session: AsyncSession, project: ProjectORM, code: str) -> WBSNodeORM:
    await session.execute(text("INSERT INTO tenants (id) VALUES (:id) ON CONFLICT DO NOTHING"), {"id": project.tenant_id})
    node = WBSNodeORM(
        id=uuid4(),
        project_id=project.id,
        tenant_id=project.tenant_id,
        code=code,
        name="Root",
        lft=1,
        rgt=2,
        depth=0,
    )
    session.add(node)
    await session.commit()
    return node


@pytest.mark.asyncio
async def test_bom_repository_filters_by_project_wbs_and_tenant(session: AsyncSession):
    """
    BOM repository should persist items and enforce tenant filtering.
    """
    tenant_a = uuid4()
    tenant_b = uuid4()

    project_a = _project(tenant_a, f"A-{uuid4().hex[:6]}")
    session.add(project_a)
    await session.commit()

    wbs_item = await _canonical_node(session, project_a, f"1-{uuid4().hex[:6]}")

    repo = SQLAlchemyBOMRepository(session)
    bom_item = BOMItem(
        id=uuid4(),
        project_id=project_a.id,
        wbs_item_id=wbs_item.id,
        item_code="BOM-001",
        item_name="Steel Beam",
        description="Primary beam",
        category=BOMCategory.MATERIAL,
        quantity=Decimal("10"),
        unit="pcs",
        unit_price=Decimal("125.50"),
        currency="EUR",
        supplier="Supplier A",
        lead_time_days=14,
        procurement_status=ProcurementStatus.REQUESTED,
        bom_metadata={"grade": "S275"},
    )
    created = await repo.create(bom_item, tenant_a)
    assert created.item_code == "BOM-001"
    assert created.total_price == Decimal("1255.00")

    by_project = await repo.get_by_project(project_a.id, tenant_a)
    assert len(by_project) == 1
    assert by_project[0].item_name == "Steel Beam"

    by_wbs = await repo.get_by_wbs_item(wbs_item.id, tenant_a)
    assert len(by_wbs) == 1
    assert by_wbs[0].item_code == "BOM-001"

    by_category = await repo.get_by_category(project_a.id, BOMCategory.MATERIAL, tenant_a)
    assert len(by_category) == 1

    by_status = await repo.get_by_status(project_a.id, ProcurementStatus.REQUESTED, tenant_a)
    assert len(by_status) == 1

    async with get_session_with_tenant(tenant_b) as tenant_b_session:
        tenant_b_repo = SQLAlchemyBOMRepository(tenant_b_session)
        tenant_b_items = await tenant_b_repo.get_by_project(project_a.id, tenant_b)
        assert tenant_b_items == []


@pytest.mark.asyncio
async def test_bom_repository_create_rejects_project_outside_tenant(session: AsyncSession):
    """
    BOM repository create should reject writes when the project is outside the caller tenant.
    """
    tenant_a = uuid4()
    tenant_b = uuid4()

    project_a = _project(tenant_a, f"A-{uuid4().hex[:6]}")
    session.add(project_a)
    await session.commit()

    wbs_item = await _canonical_node(session, project_a, f"2-{uuid4().hex[:6]}")

    repo = SQLAlchemyBOMRepository(session)
    bom_item = BOMItem(
        id=uuid4(),
        project_id=project_a.id,
        wbs_item_id=wbs_item.id,
        item_code="BOM-002",
        item_name="Concrete",
        description="Tenant mismatch",
        category=BOMCategory.MATERIAL,
        quantity=Decimal("2"),
        unit="m3",
        unit_price=Decimal("50.00"),
        currency="EUR",
        supplier="Supplier B",
        lead_time_days=7,
        procurement_status=ProcurementStatus.REQUESTED,
    )

    with pytest.raises(PermissionError, match="outside tenant"):
        await repo.create(bom_item, tenant_b)
