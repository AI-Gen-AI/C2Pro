"""
C2Pro - WBS Node Repository

SQLAlchemy repository implementation for WBSNode using Nested Set Model.

Refers to Suite ID: TS-INT-DB-WBS-001.
TASK-BCK-029: WBS API Endpoint with nested set model
"""

from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.wbs.adapters.persistence.models import WBSNodeORM
from src.wbs.domain.enums import WBSNodeStatus, WBSNodeType
from src.wbs.domain.models import WBSNode


class WBSNodeRepository:
    """
    Repository for WBS nodes using Nested Set Model.

    Provides efficient tree operations:
    - get_descendants: O(1) query for all descendants
    - get_ancestors: O(1) query for all ancestors
    - get_tree: O(1) query for entire subtree
    - move_node: O(n) where n is nodes affected
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, node_id: UUID, tenant_id: UUID) -> WBSNode | None:
        """Get a WBS node by ID."""
        stmt = (
            select(WBSNodeORM)
            .where(
                and_(
                    WBSNodeORM.id == node_id,
                    WBSNodeORM.tenant_id == tenant_id,
                )
            )
            .options(selectinload(WBSNodeORM.project))
        )
        result = await self.session.execute(stmt)
        orm_node = result.scalar_one_or_none()
        return self._to_domain(orm_node) if orm_node else None

    async def get_tree(self, project_id: UUID, tenant_id: UUID) -> list[WBSNode]:
        """
        Get entire WBS tree for a project in hierarchical order.

        Uses nested set lft ordering for efficient tree traversal.
        """
        stmt = (
            select(WBSNodeORM)
            .where(
                and_(
                    WBSNodeORM.project_id == project_id,
                    WBSNodeORM.tenant_id == tenant_id,
                )
            )
            .order_by(WBSNodeORM.lft)
        )
        result = await self.session.execute(stmt)
        orm_nodes = result.scalars().all()
        return [self._to_domain(node) for node in orm_nodes]

    async def get_descendants(
        self, node_id: UUID, tenant_id: UUID, include_self: bool = False
    ) -> list[WBSNode]:
        """
        Get all descendants of a node (efficient with nested set).

        WHERE lft > parent.lft AND rgt < parent.rgt
        """
        # First get the parent node to get lft/rgt boundaries
        parent = await self.get_by_id(node_id, tenant_id)
        if not parent:
            return []

        # Query descendants using nested set boundaries
        if include_self:
            stmt = (
                select(WBSNodeORM)
                .where(
                    and_(
                        WBSNodeORM.tenant_id == tenant_id,
                        WBSNodeORM.project_id == parent.project_id,
                        WBSNodeORM.lft >= parent.lft,
                        WBSNodeORM.rgt <= parent.rgt,
                    )
                )
                .order_by(WBSNodeORM.lft)
            )
        else:
            stmt = (
                select(WBSNodeORM)
                .where(
                    and_(
                        WBSNodeORM.tenant_id == tenant_id,
                        WBSNodeORM.project_id == parent.project_id,
                        WBSNodeORM.lft > parent.lft,
                        WBSNodeORM.rgt < parent.rgt,
                    )
                )
                .order_by(WBSNodeORM.lft)
            )

        result = await self.session.execute(stmt)
        orm_nodes = result.scalars().all()
        return [self._to_domain(node) for node in orm_nodes]

    async def get_ancestors(self, node_id: UUID, tenant_id: UUID) -> list[WBSNode]:
        """
        Get all ancestors of a node (efficient with nested set).

        WHERE lft < node.lft AND rgt > node.rgt
        """
        # First get the node to get lft/rgt boundaries
        node = await self.get_by_id(node_id, tenant_id)
        if not node:
            return []

        # Query ancestors using nested set boundaries
        stmt = (
            select(WBSNodeORM)
            .where(
                and_(
                    WBSNodeORM.tenant_id == tenant_id,
                    WBSNodeORM.project_id == node.project_id,
                    WBSNodeORM.lft < node.lft,
                    WBSNodeORM.rgt > node.rgt,
                )
            )
            .order_by(WBSNodeORM.lft)
        )

        result = await self.session.execute(stmt)
        orm_nodes = result.scalars().all()
        return [self._to_domain(node) for node in orm_nodes]

    async def get_root_nodes(self, project_id: UUID, tenant_id: UUID) -> list[WBSNode]:
        """Get all root nodes (depth=0) for a project."""
        stmt = (
            select(WBSNodeORM)
            .where(
                and_(
                    WBSNodeORM.project_id == project_id,
                    WBSNodeORM.tenant_id == tenant_id,
                    WBSNodeORM.depth == 0,
                )
            )
            .order_by(WBSNodeORM.lft)
        )
        result = await self.session.execute(stmt)
        orm_nodes = result.scalars().all()
        return [self._to_domain(node) for node in orm_nodes]

    async def create(
        self,
        project_id: UUID,
        tenant_id: UUID,
        code: str,
        name: str,
        parent_id: UUID | None,
        node_type: WBSNodeType,
        **kwargs,
    ) -> WBSNode:
        """
        Create a new WBS node and insert into nested set.

        If parent_id is None, creates a root node.
        Otherwise, inserts as last child of parent.
        """
        # Calculate lft, rgt, depth based on parent
        if parent_id is None:
            # Root node - find max rgt and place after it
            stmt = select(WBSNodeORM.rgt).where(
                and_(
                    WBSNodeORM.project_id == project_id,
                    WBSNodeORM.tenant_id == tenant_id,
                )
            )
            result = await self.session.execute(stmt)
            max_rgt = result.scalar()
            lft = (max_rgt or 0) + 1
            rgt = lft + 1
            depth = 0
        else:
            # Child node - insert as last child of parent
            parent_orm = await self.session.get(WBSNodeORM, parent_id)
            if not parent_orm or parent_orm.tenant_id != tenant_id:
                raise ValueError(f"Parent node {parent_id} not found")

            # Make space for new node by shifting existing nodes
            # All nodes with lft > parent.rgt need to shift by 2
            await self.session.execute(
                update(WBSNodeORM)
                .where(
                    and_(
                        WBSNodeORM.project_id == project_id,
                        WBSNodeORM.tenant_id == tenant_id,
                        WBSNodeORM.lft > parent_orm.rgt,
                    )
                )
                .values(lft=WBSNodeORM.lft + 2)
            )
            await self.session.execute(
                update(WBSNodeORM)
                .where(
                    and_(
                        WBSNodeORM.project_id == project_id,
                        WBSNodeORM.tenant_id == tenant_id,
                        WBSNodeORM.rgt >= parent_orm.rgt,
                    )
                )
                .values(rgt=WBSNodeORM.rgt + 2)
            )

            # Insert new node at parent's current rgt position
            lft = parent_orm.rgt
            rgt = parent_orm.rgt + 1
            depth = parent_orm.depth + 1

        # Create ORM model
        orm_node = WBSNodeORM(
            project_id=project_id,
            tenant_id=tenant_id,
            code=code,
            name=name,
            description=kwargs.get("description"),
            lft=lft,
            rgt=rgt,
            depth=depth,
            parent_id=parent_id,
            node_type=node_type,
            status=kwargs.get("status", WBSNodeStatus.NOT_STARTED),
            planned_start=kwargs.get("planned_start"),
            planned_end=kwargs.get("planned_end"),
            actual_start=kwargs.get("actual_start"),
            actual_end=kwargs.get("actual_end"),
            budget_allocated=kwargs.get("budget_allocated"),
            budget_spent=kwargs.get("budget_spent", 0.0),
            metadata_json=kwargs.get("metadata", {}),
        )

        self.session.add(orm_node)
        await self.session.flush()
        await self.session.refresh(orm_node)

        return self._to_domain(orm_node)

    async def update(
        self, node_id: UUID, tenant_id: UUID, **kwargs
    ) -> WBSNode | None:
        """
        Update a WBS node (metadata only, not structure).

        For moving nodes, use move_node().
        """
        stmt = (
            select(WBSNodeORM)
            .where(
                and_(
                    WBSNodeORM.id == node_id,
                    WBSNodeORM.tenant_id == tenant_id,
                )
            )
        )
        result = await self.session.execute(stmt)
        orm_node = result.scalar_one_or_none()

        if not orm_node:
            return None

        # Update allowed fields (not lft, rgt, depth, parent_id)
        if "name" in kwargs:
            orm_node.name = kwargs["name"]
        if "description" in kwargs:
            orm_node.description = kwargs["description"]
        if "status" in kwargs:
            orm_node.status = kwargs["status"]
        if "node_type" in kwargs:
            orm_node.node_type = kwargs["node_type"]
        if "planned_start" in kwargs:
            orm_node.planned_start = kwargs["planned_start"]
        if "planned_end" in kwargs:
            orm_node.planned_end = kwargs["planned_end"]
        if "actual_start" in kwargs:
            orm_node.actual_start = kwargs["actual_start"]
        if "actual_end" in kwargs:
            orm_node.actual_end = kwargs["actual_end"]
        if "budget_allocated" in kwargs:
            orm_node.budget_allocated = kwargs["budget_allocated"]
        if "budget_spent" in kwargs:
            orm_node.budget_spent = kwargs["budget_spent"]
        if "metadata" in kwargs:
            orm_node.metadata_json = kwargs["metadata"]

        await self.session.flush()
        await self.session.refresh(orm_node)

        return self._to_domain(orm_node)

    async def delete(self, node_id: UUID, tenant_id: UUID) -> bool:
        """
        Delete a WBS node and all its descendants.

        Uses nested set boundaries to efficiently delete subtree.
        """
        node = await self.get_by_id(node_id, tenant_id)
        if not node:
            return False

        # Delete all descendants (including self)
        width = node.rgt - node.lft + 1

        # Delete nodes in subtree
        stmt = (
            select(WBSNodeORM)
            .where(
                and_(
                    WBSNodeORM.tenant_id == tenant_id,
                    WBSNodeORM.project_id == node.project_id,
                    WBSNodeORM.lft >= node.lft,
                    WBSNodeORM.rgt <= node.rgt,
                )
            )
        )
        result = await self.session.execute(stmt)
        nodes_to_delete = result.scalars().all()

        for node_orm in nodes_to_delete:
            await self.session.delete(node_orm)

        # Shift remaining nodes left
        await self.session.execute(
            update(WBSNodeORM)
            .where(
                and_(
                    WBSNodeORM.project_id == node.project_id,
                    WBSNodeORM.tenant_id == tenant_id,
                    WBSNodeORM.lft > node.rgt,
                )
            )
            .values(lft=WBSNodeORM.lft - width)
        )
        await self.session.execute(
            update(WBSNodeORM)
            .where(
                and_(
                    WBSNodeORM.project_id == node.project_id,
                    WBSNodeORM.tenant_id == tenant_id,
                    WBSNodeORM.rgt > node.rgt,
                )
            )
            .values(rgt=WBSNodeORM.rgt - width)
        )

        await self.session.flush()
        return True

    def _to_domain(self, orm: WBSNodeORM) -> WBSNode:
        """Convert ORM model to domain model."""
        return WBSNode(
            id=orm.id,
            project_id=orm.project_id,
            tenant_id=orm.tenant_id,
            code=orm.code,
            name=orm.name,
            description=orm.description,
            lft=orm.lft,
            rgt=orm.rgt,
            depth=orm.depth,
            parent_id=orm.parent_id,
            node_type=orm.node_type,
            status=orm.status,
            planned_start=orm.planned_start,
            planned_end=orm.planned_end,
            actual_start=orm.actual_start,
            actual_end=orm.actual_end,
            budget_allocated=orm.budget_allocated,
            budget_spent=orm.budget_spent,
            metadata=orm.metadata_json,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )
