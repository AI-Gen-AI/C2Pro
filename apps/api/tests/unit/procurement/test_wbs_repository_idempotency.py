"""TS-UD-PROC-WBS-IDEM-001: WBS persistence is idempotent per source document.

Mirrors the BOM idempotency contract (``test_bom_repository_idempotency``) with one
deliberate divergence: WBS rows can be created manually or via AI generation with
NO source document, so ``replace_for_source_document`` MUST NOT sweep NULL-source
rows. It deletes ONLY the rows produced by the given source document.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.sql.dml import Delete

from src.procurement.adapters.persistence.models import WBSItemORM
from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository
from src.procurement.domain.models import WBSItem, WBSItemType
from tests.support.idempotency_fakes import FakeSession


def _wbs_item(project_id: object, document_id: object, code: str, name: str) -> WBSItem:
    return WBSItem(
        project_id=project_id,  # type: ignore[arg-type]
        code=code,
        name=name,
        level=1,
        item_type=WBSItemType.ACTIVITY,
        source_document_id=document_id,  # type: ignore[arg-type]
        wbs_metadata={"source_document_id": str(document_id)},
    )


@pytest.mark.asyncio
async def test_replace_for_source_document_deletes_then_inserts_new_set() -> None:
    """TS-UD-PROC-WBS-IDEM-001: same-schedule reparse replaces only its own WBS set."""
    tenant_id = uuid4()
    project_id = uuid4()
    document_id = uuid4()
    session = FakeSession()
    repository = SQLAlchemyWBSRepository(session)  # type: ignore[arg-type]

    created = await repository.replace_for_source_document(
        project_id=project_id,
        source_document_id=document_id,
        wbs_items=[
            _wbs_item(project_id, document_id, "SCH-001", "Mobilization"),
            _wbs_item(project_id, document_id, "SCH-002", "Excavation"),
        ],
        tenant_id=tenant_id,
    )

    delete_statements = [s for s in session.statements if isinstance(s, Delete)]
    # Exactly ONE delete — scoped to this source document. Unlike BOM, WBS does
    # NOT sweep NULL-source rows (those may be manual/AI-generated WBS items).
    assert len(delete_statements) == 1
    compiled = str(delete_statements[0].compile(compile_kwargs={"literal_binds": False}))
    assert "procurement_wbs_items.project_id" in compiled
    assert "procurement_wbs_items.source_document_id" in compiled
    assert "IS NULL" not in compiled

    assert len(session.added) == 2
    assert all(isinstance(orm, WBSItemORM) for orm in session.added)
    assert all(orm.source_document_id == document_id for orm in session.added)
    assert [item.code for item in created] == ["SCH-001", "SCH-002"]


@pytest.mark.asyncio
async def test_create_without_source_document_id_leaves_column_null_and_no_delete() -> None:
    """TS-UD-PROC-WBS-IDEM-001: manual/legacy WBS rows without a source document are untouched."""
    tenant_id = uuid4()
    project_id = uuid4()
    session = FakeSession()
    repository = SQLAlchemyWBSRepository(session)  # type: ignore[arg-type]

    await repository.create(
        tenant_id,
        WBSItem(project_id=project_id, code="1.0", name="Manual node", level=1),
    )

    assert not any(isinstance(s, Delete) for s in session.statements)
    assert session.added[0].source_document_id is None
