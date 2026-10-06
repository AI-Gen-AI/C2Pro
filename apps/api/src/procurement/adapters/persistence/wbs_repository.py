"""
SQLAlchemy implementation of the WBS repository over the canonical Project Controls WBS.

ADR-025 / MASTER: one project owns one canonical hierarchical WBS, persisted in ``wbs_nodes``
(nested set). Every application WBS read and write (projects WBS API, RACI, procurement,
reporting) goes through this adapter, so no caller can create a parallel hierarchy.

PC-1R / ADR-029 structural rules:

- the project is the implicit root: top-level branches have ``parent_id IS NULL``;
- hierarchy authority is ``(parent_id, sort_order)``; ``lft``/``rgt``/``depth`` are derived
  caches rebuilt deterministically after every structural write (siblings ordered by
  ``sort_order``, never by code), and ``level`` is ``depth + 1``;
- the visible ``code`` is display data: parents are resolved by id (``parent_code`` is only a
  convenience resolved inside the same project) and a recode keeps the node's identity;
- node ids are minted here, never taken from the caller;
- a parent must belong to the same tenant AND project;
- every structural write first locks the project row, so concurrent writes serialize;
- deleting a node deletes its subtree, but never one that still carries RACI or BOM links.
- ``item_type`` maps to ``node_type``; an unset type is stored as the column default and marked
  as inferred so it round-trips as ``None``.

Refers to Suite ID: TS-INT-DB-WBS-001.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import Table, bindparam, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import C2ProException, ConflictError
from src.core.tenants.types import TenantId
from src.procurement.adapters.persistence.models import BOMItemORM
from src.procurement.domain.models import WBSItem
from src.procurement.ports.wbs_repository import IWBSRepository
from src.projects.adapters.persistence.models import ProjectORM
from src.shared_kernel.enums import WBSItemType
from src.stakeholders.adapters.persistence.models import StakeholderWBSRaciORM
from src.wbs.adapters.persistence.models import WBSNodeORM
from src.wbs.domain.enums import WBSNodeType

# Reserved metadata key for canonical-WBS bookkeeping; never exposed through WBSItem.wbs_metadata.
_CANONICAL_KEY = "_adr025"
# Temporary nested-set coordinates for freshly inserted rows (satisfy lft > 0 and lft < rgt)
# until the project is renumbered in the same unit of work.
_TEMP_OFFSET = 1_000_000_000
# Temporary sibling positions that sort after every real one ("append"); the rebuild densifies
# them in the same transaction (uq_wbs_nodes_sibling_order is deferred to commit).
_APPEND_BASE = 1_000_000


class WBSNodeLinkedError(ConflictError):
    """A WBS node (or its subtree) still carries RACI or BOM links: it cannot be deleted silently."""

    def __init__(self, wbs_id: UUID, raci_links: int, bom_links: int) -> None:
        C2ProException.__init__(
            self,
            message=(
                f"WBS node {wbs_id} cannot be deleted: its subtree still has {raci_links} RACI "
                f"assignment(s) and {bom_links} BOM link(s). Reassign or remove them first."
            ),
            code="WBS_NODE_HAS_LINKS",
            status_code=409,
            details={"wbs_id": str(wbs_id), "raci_links": raci_links, "bom_links": bom_links},
        )


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
            parent_id=orm.parent_id,
            parent_code=code_by_id.get(orm.parent_id) if orm.parent_id else None,
            sort_order=orm.sort_order,
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

    def _new_orm(self, item: WBSItem, *, node_id: UUID, tenant_id: UUID, position: int) -> WBSNodeORM:
        node_type, inferred = _node_type(item.item_type)
        return WBSNodeORM(
            id=node_id,
            project_id=item.project_id,
            tenant_id=tenant_id,
            # Linked after the whole batch exists (the parent FK is not deferrable).
            parent_id=None,
            sort_order=_APPEND_BASE + position,
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
            version=1,
            metadata_json=_stored_metadata(item.wbs_metadata, node_type_inferred=inferred),
        )

    # ------------------------------------------------------------------ helpers
    async def _lock_project(self, project_id: UUID, tenant_id: UUID) -> None:
        """Serialize structural writes per project (and reject projects outside the tenant)."""
        result = await self.session.execute(
            select(ProjectORM.id)
            .where(ProjectORM.id == project_id)
            .where(ProjectORM.tenant_id == tenant_id)
            .with_for_update()
        )
        if result.scalar_one_or_none() is None:
            raise PermissionError("Cannot write WBS items for project outside tenant")

    async def _locked_node(self, wbs_id: UUID, tenant_id: UUID) -> WBSNodeORM | None:
        """Lock the node's project, then re-read the node as it stands after the lock."""
        project_id = (
            await self.session.execute(
                select(WBSNodeORM.project_id).where(WBSNodeORM.id == wbs_id, WBSNodeORM.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if project_id is None:
            return None
        await self._lock_project(project_id, tenant_id)
        return (
            await self.session.execute(
                select(WBSNodeORM)
                .where(WBSNodeORM.id == wbs_id, WBSNodeORM.tenant_id == tenant_id)
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()

    async def _project_nodes(self, project_id: UUID, tenant_id: UUID) -> list[WBSNodeORM]:
        """All project nodes in hierarchy order (the nested set is derived from sort_order)."""
        result = await self.session.execute(
            select(WBSNodeORM)
            .where(WBSNodeORM.project_id == project_id, WBSNodeORM.tenant_id == tenant_id)
            .order_by(WBSNodeORM.lft, WBSNodeORM.id)
        )
        return list(result.scalars().all())

    async def _code_by_id(self, project_id: UUID, tenant_id: UUID) -> dict[UUID, str]:
        result = await self.session.execute(
            select(WBSNodeORM.id, WBSNodeORM.code).where(
                WBSNodeORM.project_id == project_id, WBSNodeORM.tenant_id == tenant_id
            )
        )
        return {row.id: row.code for row in result.all()}

    async def _structure(self, project_id: UUID, tenant_id: UUID) -> dict[UUID, tuple[UUID | None, int]]:
        result = await self.session.execute(
            select(WBSNodeORM.id, WBSNodeORM.parent_id, WBSNodeORM.sort_order).where(
                WBSNodeORM.project_id == project_id, WBSNodeORM.tenant_id == tenant_id
            )
        )
        return {row.id: (row.parent_id, row.sort_order) for row in result.all()}

    async def _project_parent(self, parent_id: UUID, project_id: UUID, tenant_id: UUID) -> UUID:
        """A parent must be a node of the SAME project and tenant (never resolved through its code)."""
        found = (
            await self.session.execute(
                select(WBSNodeORM.id).where(
                    WBSNodeORM.id == parent_id,
                    WBSNodeORM.project_id == project_id,
                    WBSNodeORM.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if found is None:
            raise ValueError(f"WBS parent {parent_id} is not a node of project {project_id}")
        return found

    async def _parent_by_code(self, parent_code: str, project_id: UUID, tenant_id: UUID) -> UUID:
        found = (
            await self.session.execute(
                select(WBSNodeORM.id).where(
                    WBSNodeORM.project_id == project_id,
                    WBSNodeORM.code == parent_code,
                    WBSNodeORM.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if found is None:
            raise ValueError(f"WBS parent code {parent_code!r} does not exist in project {project_id}")
        return found

    async def _rebuild(
        self, project_id: UUID, tenant_id: UUID, positions: dict[UUID, int] | None = None
    ) -> None:
        """Densify sibling order and recompute lft/rgt/depth for the whole project.

        ``positions`` places the given nodes at a 1-based position among their siblings; every
        other sibling keeps its relative ``sort_order``. Only rows whose values change are written.
        """
        result = await self.session.execute(
            select(
                WBSNodeORM.id, WBSNodeORM.parent_id, WBSNodeORM.sort_order,
                WBSNodeORM.lft, WBSNodeORM.rgt, WBSNodeORM.depth,
            ).where(WBSNodeORM.project_id == project_id, WBSNodeORM.tenant_id == tenant_id)
        )
        rows = {row.id: row for row in result.all()}
        if not rows:
            return
        placed = positions or {}
        children: dict[UUID | None, list[UUID]] = defaultdict(list)
        for row in rows.values():
            if row.parent_id is not None and row.parent_id not in rows:
                raise ValueError(f"WBS node {row.id} has a parent outside project {project_id}")
            children[row.parent_id].append(row.id)
        for parent, siblings in children.items():
            ordered = sorted(
                (sibling for sibling in siblings if sibling not in placed),
                key=lambda node_id: (rows[node_id].sort_order, str(node_id)),
            )
            for node_id in sorted((s for s in siblings if s in placed), key=lambda s: placed[s]):
                ordered.insert(max(0, min(placed[node_id] - 1, len(ordered))), node_id)
            children[parent] = ordered

        coordinates: list[dict[str, Any]] = []
        counter = 0
        visited: set[UUID] = set()

        def visit(node_id: UUID, depth: int, position: int) -> None:
            nonlocal counter
            visited.add(node_id)
            counter += 1
            left = counter
            for child_position, child_id in enumerate(children.get(node_id, []), start=1):
                visit(child_id, depth + 1, child_position)
            counter += 1
            row = rows[node_id]
            if (row.lft, row.rgt, row.depth, row.sort_order) != (left, counter, depth, position):
                coordinates.append(
                    {"b_id": node_id, "b_lft": left, "b_rgt": counter, "b_depth": depth, "b_sort": position}
                )

        for position, top_id in enumerate(children.get(None, []), start=1):
            visit(top_id, 0, position)
        if len(visited) != len(rows):
            raise ValueError(f"WBS hierarchy of project {project_id} contains a cycle")
        if coordinates:
            table = cast(Table, WBSNodeORM.__table__)
            await self.session.execute(
                update(table)
                .where(table.c.id == bindparam("b_id"))
                .values(
                    lft=bindparam("b_lft"), rgt=bindparam("b_rgt"),
                    depth=bindparam("b_depth"), sort_order=bindparam("b_sort"),
                ),
                coordinates,
                execution_options={"synchronize_session": False},
            )
        for instance in list(self.session.identity_map.values()):
            if isinstance(instance, WBSNodeORM) and instance.project_id == project_id:
                self.session.expire(instance, ["lft", "rgt", "depth", "sort_order", "parent_id"])

    async def _insert(self, project_id: UUID, items: list[WBSItem], tenant_id: UUID) -> list[WBSNodeORM]:
        """Insert a batch (parents may appear in any order) under the project lock, then rebuild."""
        await self._lock_project(project_id, tenant_id)
        minted = {item.id: uuid4() for item in items}  # node ids are always minted here
        batch_by_code = {item.code: minted[item.id] for item in items}
        orms = [
            self._new_orm(item, node_id=minted[item.id], tenant_id=tenant_id, position=position)
            for position, item in enumerate(items)
        ]
        self.session.add_all(orms)
        await self.session.flush()

        parent_links: list[dict[str, Any]] = []
        positions: dict[UUID, int] = {}
        for item in items:
            node_id = minted[item.id]
            parent_id: UUID | None = None
            if item.parent_id is not None:
                parent_id = minted.get(item.parent_id) or await self._project_parent(
                    item.parent_id, project_id, tenant_id
                )
            elif item.parent_code:
                parent_id = batch_by_code.get(item.parent_code) or await self._parent_by_code(
                    item.parent_code, project_id, tenant_id
                )
            if parent_id == node_id:
                raise ValueError(f"WBS item {item.code!r} cannot be its own parent")
            if parent_id is not None:
                parent_links.append({"b_id": node_id, "b_parent": parent_id})
            if item.sort_order is not None:
                positions[node_id] = item.sort_order
        if parent_links:
            table = cast(Table, WBSNodeORM.__table__)
            await self.session.execute(
                update(table).where(table.c.id == bindparam("b_id")).values(parent_id=bindparam("b_parent")),
                parent_links,
                execution_options={"synchronize_session": False},
            )
        await self._rebuild(project_id, tenant_id, positions)
        return orms

    async def _subtree_ids(self, root_ids: set[UUID], project_id: UUID, tenant_id: UUID) -> set[UUID]:
        children: dict[UUID, list[UUID]] = defaultdict(list)
        for node_id, (parent_id, _order) in (await self._structure(project_id, tenant_id)).items():
            if parent_id is not None:
                children[parent_id].append(node_id)
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
        """Create a new WBS item in the canonical project WBS (the id is minted here)."""
        orms = await self._insert(wbs_item.project_id, [wbs_item], tenant_id)
        return (await self._to_domain_list(orms, wbs_item.project_id, tenant_id))[0]

    async def get_by_id(self, wbs_id: UUID, tenant_id: UUID) -> WBSItem | None:
        """Retrieve a WBS item by ID."""
        orm = (
            await self.session.execute(
                select(WBSNodeORM)
                .where(WBSNodeORM.id == wbs_id, WBSNodeORM.tenant_id == tenant_id)
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if orm is None:
            return None
        return self._orm_to_domain(orm, await self._code_by_id(orm.project_id, tenant_id))

    async def get_by_project(self, project_id: UUID, tenant_id: UUID) -> list[WBSItem]:
        """Retrieve all WBS items for a project, in hierarchy order."""
        orms = await self._project_nodes(project_id, tenant_id)
        code_by_id = {orm.id: orm.code for orm in orms}
        return [self._orm_to_domain(orm, code_by_id) for orm in orms]

    async def get_by_code(self, project_id: UUID, wbs_code: str, tenant_id: UUID) -> WBSItem | None:
        """Retrieve a WBS item by its (display) code within a project."""
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
        """Retrieve the direct children of a WBS item, in sibling order."""
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
                .where(
                    WBSNodeORM.parent_id == parent.id,
                    WBSNodeORM.project_id == parent.project_id,
                    WBSNodeORM.tenant_id == tenant_id,
                )
                .order_by(WBSNodeORM.sort_order, WBSNodeORM.id)
            )
        ).scalars().all()
        code_by_id = {parent.id: parent.code, **{orm.id: orm.code for orm in orms}}
        return [self._orm_to_domain(orm, code_by_id) for orm in orms]

    async def get_tree(self, project_id: UUID, tenant_id: UUID) -> list[WBSItem]:
        """Retrieve the complete canonical WBS tree: top-level branches with nested children."""
        orms = await self._project_nodes(project_id, tenant_id)
        code_by_id = {orm.id: orm.code for orm in orms}
        items = {orm.id: self._orm_to_domain(orm, code_by_id) for orm in orms}
        roots: list[WBSItem] = []
        for orm in orms:  # nested-set order, so every children list is in sibling order
            item = items[orm.id]
            parent = items.get(orm.parent_id) if orm.parent_id else None
            if parent is None:
                roots.append(item)
            else:
                parent.children.append(item)
        return roots

    async def update(self, wbs_id: UUID, wbs_item: WBSItem, tenant_id: UUID) -> WBSItem | None:
        """Update a WBS item (optimistic locking on ``version``).

        ``code`` may change (recode keeps the identity). The parent is taken from ``parent_id``;
        ``parent_code`` is only consulted when ``parent_id`` is None. A changed parent appends the
        node to its new siblings unless ``sort_order`` asks for a different position.
        """
        orm = await self._locked_node(wbs_id, tenant_id)
        if orm is None:
            return None
        if wbs_item.version != orm.version:
            raise ConflictError("WBSItem", field="version", value=str(wbs_id))

        node_type, inferred = _node_type(wbs_item.item_type)
        orm.code = wbs_item.code
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

        if wbs_item.parent_id is not None:
            new_parent: UUID | None = await self._project_parent(wbs_item.parent_id, orm.project_id, tenant_id)
        elif wbs_item.parent_code:
            new_parent = await self._parent_by_code(wbs_item.parent_code, orm.project_id, tenant_id)
        else:
            new_parent = None

        # Items read back from this repository carry their stored position, so an unchanged
        # sort_order is "no position requested", not "keep index N under the new parent".
        requested = wbs_item.sort_order if wbs_item.sort_order != orm.sort_order else None
        positions: dict[UUID, int] = {}
        structural_change = False
        if new_parent != orm.parent_id:
            if new_parent is not None and new_parent in await self._subtree_ids({orm.id}, orm.project_id, tenant_id):
                raise ValueError("A WBS item cannot be moved under itself or its descendants")
            depth = 0 if new_parent is None else (
                await self.session.execute(select(WBSNodeORM.depth).where(WBSNodeORM.id == new_parent))
            ).scalar_one() + 1
            orm.parent_id = new_parent
            orm.depth = depth  # the rebuild below fixes the whole moved subtree
            orm.sort_order = _APPEND_BASE
            structural_change = True
        if requested is not None:
            positions[orm.id] = requested
            structural_change = True

        await self.session.flush()
        if structural_change:
            await self._rebuild(orm.project_id, tenant_id, positions)
        await self.session.refresh(orm)
        return self._orm_to_domain(orm, await self._code_by_id(orm.project_id, tenant_id))

    async def delete(self, wbs_id: UUID, tenant_id: UUID) -> bool:
        """Delete a WBS item and its whole subtree -- never one that still has RACI or BOM links."""
        orm = await self._locked_node(wbs_id, tenant_id)
        if orm is None:
            return False
        project_id = orm.project_id
        subtree = await self._subtree_ids({orm.id}, project_id, tenant_id)
        raci_links = (
            await self.session.execute(
                select(func.count()).select_from(StakeholderWBSRaciORM).where(
                    StakeholderWBSRaciORM.wbs_item_id.in_(subtree)
                )
            )
        ).scalar_one()
        bom_links = (
            await self.session.execute(
                select(func.count()).select_from(BOMItemORM).where(BOMItemORM.wbs_item_id.in_(subtree))
            )
        ).scalar_one()
        if raci_links or bom_links:
            raise WBSNodeLinkedError(wbs_id, raci_links, bom_links)
        await self.session.execute(
            delete(WBSNodeORM).where(WBSNodeORM.id.in_(subtree)).execution_options(synchronize_session=False)
        )
        for instance in list(self.session.identity_map.values()):
            if isinstance(instance, WBSNodeORM) and instance.id in subtree:
                self.session.expunge(instance)
        await self._rebuild(project_id, tenant_id)
        return True

    async def bulk_create(self, wbs_items: list[WBSItem], tenant_id: UUID) -> list[WBSItem]:
        """Create multiple WBS items at once with tenant isolation (ids are minted here)."""
        by_project: dict[UUID, list[WBSItem]] = defaultdict(list)
        for wbs_item in wbs_items:
            by_project[wbs_item.project_id].append(wbs_item)

        created: dict[int, WBSItem] = {}
        for project_id, items in by_project.items():
            orms = await self._insert(project_id, items, tenant_id)
            for item, created_item in zip(items, await self._to_domain_list(orms, project_id, tenant_id), strict=True):
                created[id(item)] = created_item
        return [created[id(item)] for item in wbs_items]

    async def bulk_create_from_dicts(
        self,
        project_id: UUID,
        items: list[dict[str, object]],
        tenant_id: UUID,
    ) -> list[WBSItem]:
        """Build WBSItem domain objects from raw dicts and persist them.

        This is the cross-context entry point: callers outside the procurement
        bounded context pass plain dicts and the repository handles domain-object
        construction internally.
        """

        def _parse_decimal(value: Any) -> Decimal | None:
            if value is None:
                return None
            try:
                return Decimal(str(value))
            except Exception:
                return None

        def _parse_datetime(value: Any) -> datetime | None:
            # Extraction payloads carry ISO-8601 strings; the canonical WBS stores timestamptz.
            if value is None or isinstance(value, datetime):
                return value
            try:
                return datetime.fromisoformat(str(value))
            except ValueError:
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
                    planned_start=_parse_datetime(item.get("planned_start")),
                    planned_end=_parse_datetime(item.get("planned_end")),
                    wbs_metadata={"confidence": item.get("confidence"), "raw": item},
                )
            )

        return await self.bulk_create(wbs_items, tenant_id)
