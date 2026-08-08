"""
Regression tests for TASK-DOC-BOM-ORPHAN-007.
TS-INT-BOM-ORPHAN-001: replace_for_source_document must purge NULL-source orphans.
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
    """Regression suite for TASK-DOC-BOM-ORPHAN-007."""

    @pytest.mark.asyncio
    async def test_replace_removes_null_source_orphans(self, db, orphan_project):
        """
        GIVEN a project has BOM rows with source_document_id=NULL (legacy/orphaned)
        WHEN replace_for_source_document is called for a new document parse
        THEN the NULL-source rows are removed and only the new rows survive.

        Prevents false budget-reconciliation deviations caused by orphaned rows
        doubling the project BOM totals (pilot: 40 rows instead of expected 20).
        """
        project = orphan_project["project"]
        tenant = orphan_project["tenant"]
        doc_id = orphan_project["document"].id

        orphan1 = _make_bom_orm(project.id, source_document_id=None)
        orphan2 = _make_bom_orm(project.id, source_document_id=None)
        orphan3 = _make_bom_orm(project.id, source_document_id=None)
        db.add_all([orphan1, orphan2, orphan3])
        await db.commit()

        result = await db.execute(
            select(BOMItemORM).where(BOMItemORM.project_id == project.id)
        )
        assert len(result.scalars().all()) == 3

        new_items = [
            BOMItem(
                project_id=project.id,
                item_code="NEW-001",
                item_name="New Parse Item",
                quantity=Decimal("5"),
                unit="m2",
                unit_price=Decimal("50.00"),
                currency="USD",
                source_document_id=doc_id,
            )
        ]

        repo = SQLAlchemyBOMRepository(db)
        created = await repo.replace_for_source_document(
            project_id=project.id,
            source_document_id=doc_id,
            bom_items=new_items,
            tenant_id=tenant.id,
        )
        await db.commit()

        result = await db.execute(
            select(BOMItemORM).where(BOMItemORM.project_id == project.id)
        )
        surviving = result.scalars().all()
        assert len(surviving) == 1, (
            f"Expected 1 BOM row after replace, got {len(surviving)} — "
            f"orphaned NULL-source rows may have survived"
        )
        assert surviving[0].source_document_id == doc_id
        assert len(created) == 1

    @pytest.mark.asyncio
    async def test_replace_keeps_other_document_rows_intact(self, db, orphan_project):
        """
        GIVEN a project has BOM rows from two different parsed documents (doc_A and doc_B)
        WHEN replace_for_source_document is called for doc_A only
        THEN doc_B's rows survive untouched.
        """
        from src.documents.adapters.persistence.models import DocumentORM

        project = orphan_project["project"]
        tenant = orphan_project["tenant"]

        # Create a second stub document so FK constraints are satisfied for doc_B.
        doc_b = DocumentORM(
            id=uuid4(),
            project_id=project.id,
            tenant_id=tenant.id,
            document_type="budget",
            filename="doc_b.pdf",
            upload_status="parsed",
            version=1,
        )
        db.add(doc_b)
        await db.commit()

        doc_a_id = orphan_project["document"].id
        doc_b_id = doc_b.id

        row_a = _make_bom_orm(project.id, source_document_id=doc_a_id)
        row_b = _make_bom_orm(project.id, source_document_id=doc_b_id)
        db.add_all([row_a, row_b])
        await db.commit()

        new_items_for_a = [
            BOMItem(
                project_id=project.id,
                item_code="A-NEW-001",
                item_name="Replacement for doc A",
                quantity=Decimal("2"),
                unit="pcs",
                unit_price=Decimal("30.00"),
                currency="USD",
                source_document_id=doc_a_id,
            )
        ]

        repo = SQLAlchemyBOMRepository(db)
        await repo.replace_for_source_document(
            project_id=project.id,
            source_document_id=doc_a_id,
            bom_items=new_items_for_a,
            tenant_id=tenant.id,
        )
        await db.commit()

        result = await db.execute(
            select(BOMItemORM).where(BOMItemORM.project_id == project.id)
        )
        surviving = result.scalars().all()
        source_ids = {r.source_document_id for r in surviving}

        assert doc_b_id in source_ids, "doc_B rows must survive after doc_A replace"
        assert doc_a_id in source_ids, "doc_A replacement rows must be present"
        assert len(surviving) == 2
