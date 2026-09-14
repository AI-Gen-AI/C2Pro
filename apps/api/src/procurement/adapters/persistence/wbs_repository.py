"""
SQLAlchemy implementation of the WBS repository over the canonical Project Controls WBS.

ADR-025 / MASTER: one project owns one canonical hierarchical WBS, persisted in ``wbs_nodes``
(nested set). Every application WBS read and write (projects WBS API, document ingestion, analysis
persistence, RACI, procurement, reporting) goes through this adapter, so no caller can create a
parallel hierarchy. The ``IWBSRepository`` port and the ``WBSItem`` domain shape are unchanged:

- ``parent_code`` is resolved to/from ``parent_id`` within the project;
- ``level`` is the tree level (``depth + 1``) of the canonical hierarchy;
- ``item_type`` maps to ``node_type``; an unset type is stored as the column default and marked
  as inferred so it round-trips as ``None``;
- the nested set (``lft``/``rgt``/``depth``) is renumbered deterministically per project after
  every structural write (children ordered by code);
- deleting a node deletes its subtree (the previous store cascaded children via its parent FK).

Refers to Suite ID: TS-INT-DB-WBS-001.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Table, bindparam, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import ConflictError
from src.core.tenants.types import TenantId
from src.procurement.domain.models import WBSItem
from src.procurement.ports.wbs_repository import IWBSRepository
from src.projects.adapters.persistence.models import ProjectORM
from src.shared_kernel.enums import WBSItemType
from src.wbs.adapters.persistence.models import WBSNodeORM
from src.wbs.domain.enums import WBSNodeType

# Reserved metadata key for canonical-WBS bookkeeping; never exposed through WBSItem.wbs_metadata.
_CANONICAL_KEY = "_adr025"
# Temporary nested-set coordinates for freshly inserted rows (satisfy lft > 0 and lft < rgt)
# until the project is renumbered in the same unit of work.
_TEMP_OFFSET = 1_000_000_000


def _node_type(item_type: WBSItemType | None) -> tuple[WBSNodeType, bool]:
    if item_type is None:
        return WBSNodeType.WORK_PACKAGE, True
    return WBSNodeType(WBSItemType(item_type).value), False


def _item_type(orm: WBSNodeORM) -> WBSItemType | None:
    bookkeeping = (orm.metadata_json or {}).get(_CANONICAL_KEY) or {}
    if bookkeeping.get("node_type_inferred"):
        return None
    try:
        return WBSItemType(WBSNodeType(orm.node_type).value)
    except ValueError:  # e.g. milestone: a canonical node type with no procurement equivalent
        return None


def _public_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    return {key: value for key, value in (metadata or {}).items() if key != _CANONICAL_KEY}


def _stored_metadata(public: dict[str, Any] | None, *, node_type_inferred: bool, previous: dict[str, Any] | None = None) -> dict[str, Any]:
    bookkeeping = dict(((previous or {}).get(_CANONICAL_KEY)) or {})
    bookkeeping["node_type_inferred"] = node_type_inferred
    stored = _public_metadata(public)
    stored[_CANONICAL_KEY] = bookkeeping
    return stored


class SQLAlchemyWBSRepository(IWBSRepository):
    """WBS repository backed by the canonical Project Controls WBS (``wbs_nodes``)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------------------------------------------------------ mapping
    def _orm_to_domain(self, orm: WBSNodeORM, code_by_id: dict[UUID, str]) -> WBSItem:
        return WBSItem(
            id=orm.id,
            project_id=orm.project_id,
            code=orm.code,
            name=orm.name,
            description=orm.description,
            level=orm.depth + 1,
            parent_code=code_by_id.get(orm.parent_id) if orm.parent_id else None,
            item_type=_item_type(orm),
            # Numeric columns load as Decimal (the ORM annotation says float for wbs_node callers).
            budget_allocated=cast("Decimal | None", orm.budget_allocated),
            budget_spent=cast(Decimal, orm.budget_spent) if orm.budget_spent is not None else Decimal(0),
            planned_start=orm.planned_start,
            planned_end=orm.planned_end,
            actual_start=orm.actual_start,
            actual_end=orm.actual_end,
            source_clause_id=orm.source_clause_id,
            source_document_id=orm.source_document_id,
            version=orm.version,
            wbs_metadata=_public_metadata(orm.metadata_json),
            children=[],
        )

    def _new_orm(self, item: WBSItem, tenant_id: UUID, position: int) -> WBSNodeORM:
        node_type, inferred = _node_type(item.item_type)
        return WBSNodeORM(
            id=item.id,
            project_id=item.project_id,
            tenant_id=tenant_id,
            parent_id=None,
            code=item.code,
            name=item.name,
            description=item.description,
            lft=_TEMP_OFFSET + 2 * position + 1,
            rgt=_TEMP_OFFSET + 2 * position + 2,
            depth=0,
            node_type=node_type,
            budget_allocated=item.budget_allocated,
            budget_spent=item.budget_spent if item.budget_spent is not None else Decimal(0),
            planned_start=item.planned_start,
            planned_end=item.planned_end,
            actual_start=item.actual_start,
            actual_end=item.actual_end,
            source_clause_id=item.source_clause_id,
            source_document_id=item.source_document_id,
            version=item.version or 1,
            metadata_json=_stored_metadata(item.wbs_metadata, node_type_inferred=inferred),
        )

    # ------------------------------------------------------------------ helpers
    async def _ensure_project_in_tenant(self, project_id: UUID, tenant_id: UUID) -> None:
        """Reject writes for projects outside the caller tenant."""
        result = await self.session.execute(
            select(ProjectORM.id)
            .where(ProjectORM.id == project_id)
            .where(ProjectORM.tenant_id == tenant_id)
        )
        if result.scalar_one_or_none() is None:
            raise PermissionError("Cannot create WBS items for project outside tenant")

    async def _project_nodes(self, project_id: UUID, tenant_id: UUID) -> list[WBSNodeORM]:
        result = await self.session.execute(
            select(WBSNodeORM)
            .where(WBSNodeORM.project_id == project_id, WBSNodeORM.tenant_id == tenant_id)
            .order_by(WBSNodeORM.code)
        )
        return list(result.scalars().all())

    async def _code_by_id(self, project_id: UUID, tenant_id: UUID) -> dict[UUID, str]:
        result = await self.session.execute(
            select(WBSNodeORM.id, WBSNodeORM.code).where(
                WBSNodeORM.project_id == project_id, WBSNodeORM.tenant_id == tenant_id
            )
        )
        return {row.id: row.code for row in result.all()}

    async def _renumber(self, project_id: UUID, tenant_id: UUID) -> None:
        """Recompute lft/rgt/depth for the whole project (children ordered by code)."""
        result = await self.session.execute(
            select(WBSNodeORM.id, WBSNodeORM.parent_id, WBSNodeORM.code).where(
                WBSNodeORM.project_id == project_id, WBSNodeORM.tenant_id == tenant_id
            )
        )
        rows = result.all()
        if not rows:
            return
        ids = {row.id for row in rows}
        children: dict[UUID | None, list[tuple[str, UUID]]] = defaultdict(list)
        for row in rows:
            parent = row.parent_id if row.parent_id in ids else None
            children[parent].append((row.code, row.id))
        for siblings in children.values():
            siblings.sort()

        coordinates: list[dict[str, Any]] = []
        counter = 0

        def visit(node_id: UUID, depth: int) -> None:
            nonlocal counter
            counter += 1
            lft = counter
            for _code, child_id in children.get(node_id, []):
                visit(child_id, depth + 1)
            counter += 1
            coordinates.append({"b_id": node_id, "b_lft": lft, "b_rgt": counter, "b_depth": depth})

        for _code, root_id in children[None]:
            visit(root_id, 0)

        table = cast(Table, WBSNodeORM.__table__)
        await self.session.execute(
            update(table)
            .where(table.c.id == bindparam("b_id"))
            .values(lft=bindparam("b_lft"), rgt=bindparam("b_rgt"), depth=bindparam("b_depth")),
            coordinates,
            execution_options={"synchronize_session": False},
        )
        for instance in list(self.session.identity_map.values()):
            if isinstance(instance, WBSNodeORM) and instance.project_id == project_id:
                self.session.expire(instance, ["lft", "rgt", "depth"])

    async def _insert(self, project_id: UUID, items: list[WBSItem], tenant_id: UUID) -> list[WBSNodeORM]:
        """Insert items (parents may appear in any order in the batch) and renumber the project."""
        existing = {code: node_id for node_id, code in (await self._code_by_id(project_id, tenant_id)).items()}
        batch_codes = {item.code: item.id for item in items}
        orms = [self._new_orm(item, tenant_id, position) for position, item in enumerate(items)]
        self.session.add_all(orms)
        await self.session.flush()

        parent_links: list[dict[str, Any]] = []
        for item in items:
            if not item.parent_code:
                continue
            parent_id = batch_codes.get(item.parent_code) or existing.get(item.parent_code)
            if parent_id is None:
                raise ValueError(
                    f"WBS parent code {item.parent_code!r} does not exist in project {project_id}"
                )
            if parent_id == item.id:
                raise ValueError(f"WBS item {item.code!r} cannot be its own parent")
            parent_links.append({"b_id": item.id, "b_parent": parent_id})
        if parent_links:
            table = cast(Table, WBSNodeORM.__table__)
            await self.session.execute(
                update(table).where(table.c.id == bindparam("b_id")).values(parent_id=bindparam("b_parent")),
                parent_links,
                execution_options={"synchronize_session": False},
            )
            for orm in orms:
                self.session.expire(orm, ["parent_id"])
        await self._renumber(project_id, tenant_id)
        return orms

    async def _subtree_ids(self, root_ids: set[UUID], project_id: UUID, tenant_id: UUID) -> set[UUID]:
        result = await self.session.execute(
            select(WBSNodeORM.id, WBSNodeORM.parent_id).where(
                WBSNodeORM.project_id == project_id, WBSNodeORM.tenant_id == tenant_id
            )
        )
        children: dict[UUID, list[UUID]] = defaultdict(list)
        for row in result.all():
            if row.parent_id is not None:
                children[row.parent_id].append(row.id)
        collected: set[UUID] = set()
        stack = list(root_ids)
        while stack:
            node_id = stack.pop()
            if node_id in collected:
                continue
            collected.add(node_id)
            stack.extend(children.get(node_id, []))
        return collected

    async def _to_domain_list(self, orms: list[WBSNodeORM], project_id: UUID, tenant_id: UUID) -> list[WBSItem]:
        code_by_id = await self._code_by_id(project_id, tenant_id)
        for orm in orms:
            await self.session.refresh(orm)
        return [self._orm_to_domain(orm, code_by_id) for orm in orms]

    # ------------------------------------------------------------------ port
    async def create(self, tenant_id: TenantId, wbs_item: WBSItem) -> WBSItem:
        """Create a new WBS item in the canonical project WBS."""
        await self._ensure_project_in_tenant(wbs_item.project_id, tenant_id)
        orms = await self._insert(wbs_item.project_id, [wbs_item], tenant_id)
        return (await self._to_domain_list(orms, wbs_item.project_id, tenant_id))[0]

    async def get_by_id(self, wbs_id: UUID, tenant_id: UUID) -> WBSItem | None:
        """Retrieve a WBS item by ID."""
        orm = (
            await self.session.execute(
                select(WBSNodeORM).where(WBSNodeORM.id == wbs_id, WBSNodeORM.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if orm is None:
            return None
        return self._orm_to_domain(orm, await self._code_by_id(orm.project_id, tenant_id))

    async def get_by_project(self, project_id: UUID, tenant_id: UUID) -> list[WBSItem]:
        """Retrieve all WBS items for a project (ordered by code)."""
        orms = await self._project_nodes(project_id, tenant_id)
        code_by_id = {orm.id: orm.code for orm in orms}
        return [self._orm_to_domain(orm, code_by_id) for orm in orms]

    async def get_by_code(self, project_id: UUID, wbs_code: str, tenant_id: UUID) -> WBSItem | None:
        """Retrieve a WBS item by its code within a project."""
        orm = (
            await self.session.execute(
                select(WBSNodeORM).where(
                    WBSNodeORM.project_id == project_id,
                    WBSNodeORM.code == wbs_code,
                    WBSNodeORM.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if orm is None:
            return None
        return self._orm_to_domain(orm, await self._code_by_id(project_id, tenant_id))

    async def get_children(self, parent_id: UUID, tenant_id: UUID) -> list[WBSItem]:
        """Retrieve the direct children of a WBS item."""
        parent = (
            await self.session.execute(
                select(WBSNodeORM).where(WBSNodeORM.id == parent_id, WBSNodeORM.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if parent is None:
            return []
        orms = (
            await self.session.execute(
                select(WBSNodeORM)
                .where(WBSNodeORM.parent_id == parent.id, WBSNodeORM.tenant_id == tenant_id)
                .order_by(WBSNodeORM.code)
            )
        ).scalars().all()
        code_by_id = {parent.id: parent.code, **{orm.id: orm.code for orm in orms}}
        return [self._orm_to_domain(orm, code_by_id) for orm in orms]

    async def get_tree(self, project_id: UUID, tenant_id: UUID) -> list[WBSItem]:
        """Retrieve the complete canonical WBS tree for a project."""
        orms = await self._project_nodes(project_id, tenant_id)
        code_by_id = {orm.id: orm.code for orm in orms}
        items = {orm.id: self._orm_to_domain(orm, code_by_id) for orm in orms}
        roots: list[WBSItem] = []
        for orm in orms:  # ordered by code, so children lists are ordered by code too
            item = items[orm.id]
            parent = items.get(orm.parent_id) if orm.parent_id else None
            if parent is None:
                roots.append(item)
            else:
                parent.children.append(item)
        return roots

    async def update(self, wbs_id: UUID, wbs_item: WBSItem, tenant_id: UUID) -> WBSItem | None:
        """Update an existing WBS item (optimistic locking on ``version``)."""
        orm = (
            await self.session.execute(
                select(WBSNodeORM).where(WBSNodeORM.id == wbs_id, WBSNodeORM.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if orm is None:
            return None
        if wbs_item.version != orm.version:
            raise ConflictError("WBSItem", field="version", value=str(wbs_id))

        node_type, inferred = _node_type(wbs_item.item_type)
        orm.name = wbs_item.name
        orm.description = wbs_item.description
        orm.node_type = node_type
        orm.budget_allocated = cast(Any, wbs_item.budget_allocated)
        orm.budget_spent = cast(Any, wbs_item.budget_spent)
        orm.planned_start = wbs_item.planned_start
        orm.planned_end = wbs_item.planned_end
        orm.actual_start = wbs_item.actual_start
        orm.actual_end = wbs_item.actual_end
        orm.metadata_json = _stored_metadata(
            wbs_item.wbs_metadata, node_type_inferred=inferred, previous=orm.metadata_json
        )
        orm.version = orm.version + 1

        structural_change = False
        if wbs_item.parent_code:
            parent = (
                await self.session.execute(
                    select(WBSNodeORM).where(
                        WBSNodeORM.project_id == orm.project_id,
                        WBSNodeORM.code == wbs_item.parent_code,
                        WBSNodeORM.tenant_id == tenant_id,
                    )
                )
            ).scalar_one_or_none()
            if parent is None:
                raise ValueError(f"WBS parent code {wbs_item.parent_code!r} does not exist in project")
            if parent.id != orm.parent_id:
                if parent.id in await self._subtree_ids({orm.id}, orm.project_id, tenant_id):
                    raise ValueError("A WBS item cannot be moved under itself or its descendants")
                orm.parent_id = parent.id
                structural_change = True

        await self.session.flush()
        if structural_change:
            await self._renumber(orm.project_id, tenant_id)
        await self.session.refresh(orm)
        return self._orm_to_domain(orm, await self._code_by_id(orm.project_id, tenant_id))

    async def delete(self, wbs_id: UUID, tenant_id: UUID) -> bool:
        """Delete a WBS item and its whole subtree."""
        orm = (
            await self.session.execute(
                select(WBSNodeORM).where(WBSNodeORM.id == wbs_id, WBSNodeORM.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if orm is None:
            return False
        project_id = orm.project_id
        subtree = await self._subtree_ids({orm.id}, project_id, tenant_id)
        await self.session.execute(
            delete(WBSNodeORM).where(WBSNodeORM.id.in_(subtree)).execution_options(synchronize_session=False)
        )
        for instance in list(self.session.identity_map.values()):
            if isinstance(instance, WBSNodeORM) and instance.id in subtree:
                self.session.expunge(instance)
        await self._renumber(project_id, tenant_id)
        return True

    async def delete_for_project(self, project_id: UUID, tenant_id: UUID) -> None:
        """Remove the project's whole WBS (used when an analysis replaces it)."""
        await self.session.execute(
            delete(WBSNodeORM)
            .where(WBSNodeORM.project_id == project_id, WBSNodeORM.tenant_id == tenant_id)
            .execution_options(synchronize_session=False)
        )

    async def replace_for_source_document(
        self,
        *,
        project_id: UUID,
        source_document_id: UUID,
        wbs_items: list[WBSItem],
        tenant_id: UUID,
    ) -> list[WBSItem]:
        """Replace all WBS nodes produced by one parsed source document.

        Idempotent per source document: deletes the nodes previously produced by the same
        ``source_document_id`` (with their subtrees) and inserts the new set. Nodes without a
        source document (manual or AI-generated) are not swept (TS-UD-PROC-WBS-IDEM-001).
        """
        await self._ensure_project_in_tenant(project_id, tenant_id)
        previous = (
            await self.session.execute(
                select(WBSNodeORM.id).where(
                    WBSNodeORM.project_id == project_id,
                    WBSNodeORM.tenant_id == tenant_id,
                    WBSNodeORM.source_document_id == source_document_id,
                )
            )
        ).scalars().all()
        if previous:
            subtree = await self._subtree_ids(set(previous), project_id, tenant_id)
            await self.session.execute(
                delete(WBSNodeORM).where(WBSNodeORM.id.in_(subtree)).execution_options(synchronize_session=False)
            )
            for instance in list(self.session.identity_map.values()):
                if isinstance(instance, WBSNodeORM) and instance.id in subtree:
                    self.session.expunge(instance)

        for item in wbs_items:
            if item.project_id != project_id:
                raise ValueError("WBS item project_id must match replacement project_id")
            item.source_document_id = source_document_id
        if not wbs_items:
            await self._renumber(project_id, tenant_id)
            return []
        orms = await self._insert(project_id, wbs_items, tenant_id)
        return await self._to_domain_list(orms, project_id, tenant_id)

    async def bulk_create(self, wbs_items: list[WBSItem], tenant_id: UUID) -> list[WBSItem]:
        """Create multiple WBS items at once with tenant isolation (used for AI generation)."""
        by_project: dict[UUID, list[WBSItem]] = defaultdict(list)
        for wbs_item in wbs_items:
            by_project[wbs_item.project_id].append(wbs_item)
        for project_id in by_project:
            await self._ensure_project_in_tenant(project_id, tenant_id)

        created: dict[UUID, WBSItem] = {}
        for project_id, items in by_project.items():
            orms = await self._insert(project_id, items, tenant_id)
            for item in await self._to_domain_list(orms, project_id, tenant_id):
                created[item.id] = item
        return [created[item.id] for item in wbs_items]

    async def bulk_create_from_dicts(
        self,
        project_id: UUID,
        items: list[dict[str, object]],
        tenant_id: UUID,
    ) -> list[WBSItem]:
        """Build WBSItem domain objects from raw dicts and persist them.

        This is the cross-context entry point: callers outside the procurement
        bounded context pass plain dicts (e.g. from AI extraction) and the
        repository handles domain-object construction internally.
        """

        def _parse_decimal(value: Any) -> Decimal | None:
            if value is None:
                return None
            try:
                return Decimal(str(value))
            except Exception:
                return None

        wbs_items: list[WBSItem] = []
        for item in items:
            code = str(item.get("code") or "").strip() or f"T{len(wbs_items) + 1}"
            level = code.count(".") + 1 if code else 1
            item_type_raw = str(item.get("item_type") or "").lower()
            item_type = None
            for candidate in WBSItemType:
                if candidate.value == item_type_raw:
                    item_type = candidate
                    break

            wbs_items.append(
                WBSItem(
                    project_id=project_id,
                    code=code,
                    name=cast("str", item.get("name") or "WBS Item"),
                    description=cast("str | None", item.get("description")),
                    level=level,
                    parent_code=cast("str | None", item.get("parent_code")),
                    item_type=item_type,
                    budget_allocated=_parse_decimal(item.get("budget_allocated")),
                    planned_start=cast(Any, item.get("planned_start")),
                    planned_end=cast(Any, item.get("planned_end")),
                    wbs_metadata={"confidence": item.get("confidence"), "raw": item},
                )
            )

        return await self.bulk_create(wbs_items, tenant_id)
