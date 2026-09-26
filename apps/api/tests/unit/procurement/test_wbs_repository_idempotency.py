"""TS-UD-PROC-WBS-IDEM-001: WBS persistence is idempotent per source document.

Mirrors the BOM idempotency contract (``test_bom_repository_idempotency``) with one
deliberate divergence: WBS nodes can be created manually or via AI generation with
NO source document, so ``replace_for_source_document`` MUST NOT sweep NULL-source
nodes. It deletes ONLY the nodes produced by the given source document (and their
subtrees), in the canonical Project Controls WBS (ADR-025).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.sql.dml import Delete
from sqlalchemy.sql.selectable import Select

from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository
from src.procurement.domain.models import WBSItem, WBSItemType


class _Rows:
    def __init__(self, ids: list[object]) -> None:
        self._ids = ids

    def scalars(self) -> _Rows:
        return self

    def all(self) -> list[object]:
        return self._ids

    def scalar_one_or_none(self) -> object:
        return uuid4()


class _Session:
    """Records statements; the first source-document lookup returns ``previous_ids``."""

    def __init__(self, previous_ids: list[object]) -> None:
        self.statements: list[object] = []
        self._previous_ids = previous_ids
        self.identity_map: dict[object, object] = {}

    async def execute(self, statement: object, *_args: object, **_kwargs: object) -> _Rows:
        self.statements.append(statement)
        if isinstance(statement, Select) and "source_document_id" in str(statement):
            return _Rows(self._previous_ids)
        return _Rows([])

    def expunge(self, _instance: object) -> None:  # pragma: no cover - nothing tracked
        pass


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


def _repository(session: _Session, inserted: list[WBSItem], monkeypatch: pytest.MonkeyPatch) -> SQLAlchemyWBSRepository:
    repository = SQLAlchemyWBSRepository(session)  # type: ignore[arg-type]

    async def _insert(project_id, items, tenant_id):  # noqa: ANN001
        inserted.extend(items)
        return items

    async def _to_domain_list(orms, project_id, tenant_id):  # noqa: ANN001
        return list(orms)

    async def _subtree_ids(root_ids, project_id, tenant_id):  # noqa: ANN001
        return set(root_ids)

    async def _renumber(project_id, tenant_id):  # noqa: ANN001
        return None

    monkeypatch.setattr(repository, "_insert", _insert)
    monkeypatch.setattr(repository, "_to_domain_list", _to_domain_list)
    monkeypatch.setattr(repository, "_subtree_ids", _subtree_ids)
    monkeypatch.setattr(repository, "_renumber", _renumber)
    return repository


@pytest.mark.asyncio
async def test_replace_for_source_document_deletes_then_inserts_new_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """TS-UD-PROC-WBS-IDEM-001: same-schedule reparse replaces only its own WBS set."""
    tenant_id = uuid4()
    project_id = uuid4()
    document_id = uuid4()
    previous = [uuid4(), uuid4()]
    session = _Session(previous)
    inserted: list[WBSItem] = []
    repository = _repository(session, inserted, monkeypatch)

    created = await repository.replace_for_source_document(
        project_id=project_id,
        source_document_id=document_id,
        wbs_items=[
            _wbs_item(project_id, document_id, "SCH-001", "Mobilization"),
            _wbs_item(project_id, document_id, "SCH-002", "Excavation"),
        ],
        tenant_id=tenant_id,
    )

    lookups = [s for s in session.statements if isinstance(s, Select) and "source_document_id" in str(s)]
    assert len(lookups) == 1
    lookup = str(lookups[0])
    assert "wbs_nodes.project_id" in lookup
    assert "wbs_nodes.tenant_id" in lookup
    assert "wbs_nodes.source_document_id" in lookup
    # Unlike BOM, WBS does NOT sweep NULL-source nodes (manual/AI-generated WBS).
    assert "IS NULL" not in lookup

    deletes = [s for s in session.statements if isinstance(s, Delete)]
    assert len(deletes) == 1
    assert "wbs_nodes.id IN" in str(deletes[0])

    assert [item.code for item in inserted] == ["SCH-001", "SCH-002"]
    assert all(item.source_document_id == document_id for item in inserted)
    assert [item.code for item in created] == ["SCH-001", "SCH-002"]


@pytest.mark.asyncio
async def test_create_without_source_document_id_leaves_column_null_and_no_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    """TS-UD-PROC-WBS-IDEM-001: manual/legacy WBS nodes without a source document are untouched."""
    tenant_id = uuid4()
    project_id = uuid4()
    session = _Session([])
    inserted: list[WBSItem] = []
    repository = _repository(session, inserted, monkeypatch)

    await repository.create(tenant_id, WBSItem(project_id=project_id, code="1.0", name="Manual node", level=1))

    assert not any(isinstance(s, Delete) for s in session.statements)
    assert inserted[0].source_document_id is None


@pytest.mark.asyncio
async def test_replace_for_source_document_rejects_cross_project_item(monkeypatch: pytest.MonkeyPatch) -> None:
    """TS-UD-PROC-WBS-IDEM-001: a WBS item from another project is rejected before insert."""
    tenant_id = uuid4()
    project_id = uuid4()
    other_project_id = uuid4()
    document_id = uuid4()
    inserted: list[WBSItem] = []
    repository = _repository(_Session([]), inserted, monkeypatch)

    with pytest.raises(ValueError, match="project_id"):
        await repository.replace_for_source_document(
            project_id=project_id,
            source_document_id=document_id,
            wbs_items=[_wbs_item(other_project_id, document_id, "SCH-001", "Mobilization")],
            tenant_id=tenant_id,
        )
    assert inserted == []
