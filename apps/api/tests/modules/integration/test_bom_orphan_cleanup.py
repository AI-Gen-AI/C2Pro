"""
Regression tests for TASK-DOC-BOM-ORPHAN-007, superseded by #860.
TS-INT-BOM-ORPHAN-001: NULL-source BOM rows are manual / legacy rows, never orphans.

The original sweep deleted NULL-source rows on every budget reparse because coherence
summed the BOM table as budget truth and they doubled the totals. #860 removes both
ends: coherence never reads the BOM table, and budget ingestion never writes it, so
the sweep (and with it the loss of manual / procurement-edited rows) is gone.
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select

from src.procurement.adapters.persistence.bom_repository import SQLAlchemyBOMRepository
from src.procurement.adapters.persistence.models import BOMItemORM
from src.procurement.domain.models import BOMCategory, BOMItem, ProcurementStatus


@pytest_asyncio.fixture
async def orphan_project(db):
    """Create tenant + project + a stub document for BOM orphan tests."""
    from src.core.auth.models import Tenant
    from src.documents.adapters.persistence.models import DocumentORM
    from src.projects.adapters.persistence.models import ProjectORM

    tenant = Tenant(
        id=uuid4(),
        name="Orphan Test Tenant",
        slug=f"orphan-{uuid4().hex[:8]}",
        subscription_plan="professional",
        is_active=True,
    )
    db.add(tenant)
    await db.commit()

    project = ProjectORM(
        id=uuid4(),
        tenant_id=tenant.id,
        name="Orphan Test Project",
        code=f"ORP-{uuid4().hex[:4].upper()}",
        start_date=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    # Stub document: needed so FK(documents.id) on BOM rows doesn't fail on INSERT.
    document = DocumentORM(
        id=uuid4(),
        project_id=project.id,
        tenant_id=tenant.id,
        document_type="contract",
        filename="orphan_stub.pdf",
        upload_status="parsed",
        version=1,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    return {"tenant": tenant, "project": project, "document": document}


def _make_bom_orm(project_id, source_document_id=None) -> BOMItemORM:
    """Build a minimal BOMItemORM row for seeding test data."""
    return BOMItemORM(
        id=uuid4(),
        project_id=project_id,
        item_code=f"BOM-{uuid4().hex[:4].upper()}",
        item_name="Test Item",
        category=BOMCategory.MATERIAL,
        quantity=Decimal("1"),
        unit="pcs",
        unit_price=Decimal("100.00"),
        currency="USD",
        procurement_status=ProcurementStatus.PENDING,
        source_document_id=source_document_id,
    )


class TestBomOrphanCleanup:
    """TASK-DOC-BOM-ORPHAN-007 regression suite under the #860 contract."""

    def test_source_document_sweep_is_removed(self):
        assert not hasattr(SQLAlchemyBOMRepository, "replace_for_source_document")

    @pytest.mark.asyncio
    async def test_null_source_and_other_document_rows_survive_a_create(self, db, orphan_project):
        """
        GIVEN manual NULL-source BOM rows and a row tied to a parsed document
        WHEN a new BOM row is created for that document
        THEN every existing row survives untouched and only the new row is added.
        """
        project = orphan_project["project"]
        tenant = orphan_project["tenant"]
        doc_id = orphan_project["document"].id

        existing = [
            _make_bom_orm(project.id, source_document_id=None),
            _make_bom_orm(project.id, source_document_id=None),
            _make_bom_orm(project.id, source_document_id=doc_id),
        ]
        db.add_all(existing)
        await db.commit()
        existing_ids = {row.id for row in existing}

        repo = SQLAlchemyBOMRepository(db)
        created = await repo.create(
            BOMItem(
                project_id=project.id,
                item_code="NEW-001",
                item_name="New manual item",
                quantity=Decimal("5"),
                unit="m2",
                unit_price=Decimal("50.00"),
                currency="USD",
                source_document_id=doc_id,
            ),
            tenant.id,
        )
        await db.commit()

        result = await db.execute(
            select(BOMItemORM).where(BOMItemORM.project_id == project.id)
        )
        surviving_ids = {row.id for row in result.scalars().all()}
        assert surviving_ids == existing_ids | {created.id}
