"""TS-UD-PROC-BOM-IDEM-001 (#860): BOM persistence never sweeps rows by source document."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.sql.dml import Delete

from src.procurement.adapters.persistence.bom_repository import SQLAlchemyBOMRepository
from src.procurement.adapters.persistence.models import BOMItemORM
from src.procurement.domain.models import BOMItem
from tests.support.idempotency_fakes import FakeSession


def test_repository_has_no_source_document_replace_sweep() -> None:
    """#860: the budget-reparse delete-by-source + NULL-source orphan sweep is removed.

    Supersedes the set-replacement contract: automated budget ingestion no longer
    writes BOM, so nothing may bulk-delete manual / procurement-edited rows.
    """
    assert not hasattr(SQLAlchemyBOMRepository, "replace_for_source_document")


@pytest.mark.asyncio
async def test_create_with_source_document_id_never_deletes() -> None:
    """#860: a create carrying a source document is an insert, never a set replacement."""
    tenant_id = uuid4()
    project_id = uuid4()
    document_id = uuid4()
    session = FakeSession()
    repository = SQLAlchemyBOMRepository(session)  # type: ignore[arg-type]

    await repository.create(
        BOMItem(
            project_id=project_id,
            item_name="Concrete",
            quantity=Decimal("2"),
            source_document_id=document_id,
            bom_metadata={},
        ),
        tenant_id,
    )

    assert not any(isinstance(statement, Delete) for statement in session.statements)
    assert len(session.added) == 1
    assert isinstance(session.added[0], BOMItemORM)
    assert session.added[0].source_document_id == document_id


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
