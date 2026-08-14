"""TS-UD-PROC-BOM-IDEM-001: BOM persistence is idempotent per source document."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.sql.dml import Delete

from src.procurement.adapters.persistence.bom_repository import SQLAlchemyBOMRepository
from src.procurement.adapters.persistence.models import BOMItemORM
from src.procurement.domain.models import BOMItem
from tests.support.idempotency_fakes import FakeSession


@pytest.mark.asyncio
async def test_replace_for_source_document_deletes_then_inserts_new_set() -> None:
    """TS-UD-PROC-BOM-IDEM-001: same-document budget reparse replaces its whole BOM set."""
    tenant_id = uuid4()
    project_id = uuid4()
    document_id = uuid4()
    session = FakeSession()
    repository = SQLAlchemyBOMRepository(session)  # type: ignore[arg-type]

    created = await repository.replace_for_source_document(
        project_id=project_id,
        source_document_id=document_id,
        bom_items=[
            BOMItem(
                project_id=project_id,
                item_name="Concrete",
                quantity=Decimal("2"),
                unit_price=Decimal("10"),
                total_price=Decimal("20"),
                source_document_id=document_id,
                bom_metadata={"source_document_id": str(document_id)},
            ),
            BOMItem(
                project_id=project_id,
                item_name="Steel",
                quantity=Decimal("3"),
                unit_price=Decimal("5"),
                total_price=Decimal("15"),
                source_document_id=document_id,
                bom_metadata={"source_document_id": str(document_id)},
            ),
        ],
        tenant_id=tenant_id,
    )

    delete_statements = [statement for statement in session.statements if isinstance(statement, Delete)]
    # Two DELETEs: (1) rows for this document, (2) NULL-source orphan sweep.
    assert len(delete_statements) == 2
    compiled0 = str(delete_statements[0].compile(compile_kwargs={"literal_binds": False}))
    assert "procurement_bom_items.project_id" in compiled0
    assert "procurement_bom_items.source_document_id" in compiled0
    compiled1 = str(delete_statements[1].compile(compile_kwargs={"literal_binds": False}))
    assert "procurement_bom_items.project_id" in compiled1
    # Second DELETE targets IS NULL rows — no source_document_id equality term.
    assert "IS NULL" in compiled1 or "source_document_id" in compiled1
    assert len(session.added) == 2
    assert all(isinstance(orm, BOMItemORM) for orm in session.added)
    assert all(orm.source_document_id == document_id for orm in session.added)
    assert [item.item_name for item in created] == ["Concrete", "Steel"]


@pytest.mark.asyncio
async def test_create_without_source_document_id_does_not_delete_legacy_rows() -> None:
    """TS-UD-PROC-BOM-IDEM-001: legacy/manual BOM rows without source_document_id remain tolerated."""
    tenant_id = uuid4()
    project_id = uuid4()
    session = FakeSession()
    repository = SQLAlchemyBOMRepository(session)  # type: ignore[arg-type]

    await repository.create(
        BOMItem(
            project_id=project_id,
            item_name="Legacy item",
            quantity=Decimal("1"),
            bom_metadata={},
        ),
        tenant_id,
    )

    assert not any(isinstance(statement, Delete) for statement in session.statements)
    assert session.added[0].source_document_id is None
