"""
Unit tests for WBS Node Repository.

Tests nested set model operations.

TASK-BCK-029: WBS API Endpoint with nested set model
"""

from uuid import uuid4

import pytest

from src.wbs.adapters.persistence.wbs_node_repository import WBSNodeRepository
from src.wbs.domain.enums import WBSNodeStatus, WBSNodeType

pytestmark = pytest.mark.integration


@pytest.fixture
async def tenant_id(async_session):
    """Fixture for tenant ID."""
    from src.core.auth.models import Tenant
    tenant = Tenant(
        id=uuid4(),
        name="Test Tenant",
        slug=f"test-tenant-{uuid4().hex[:6]}",
    )
    async_session.add(tenant)
    await async_session.commit()
    return tenant.id


@pytest.fixture
async def project_id(async_session, tenant_id):
    """Fixture for project ID."""
    from src.projects.adapters.persistence.models import ProjectORM
    project = ProjectORM(
        id=uuid4(),
        tenant_id=tenant_id,
        name="Test Project",
    )
    async_session.add(project)
    await async_session.commit()
    return project.id


class TestWBSNodeRepositoryCreate:
    """Test WBS node creation with nested set positioning."""

    async def test_create_root_node(self, async_session, project_id, tenant_id):
        """Test creating a root node (no parent)."""
        repo = WBSNodeRepository(async_session)

        node = await repo.create(
            project_id=project_id,
            tenant_id=tenant_id,
            code="1",
            name="Root Node",
            parent_id=None,
            node_type=WBSNodeType.WORK_PACKAGE,
        )

        assert node.id is not None
        assert node.code == "1"
        assert node.name == "Root Node"
        assert node.lft == 1
        assert node.rgt == 2
        assert node.depth == 0
        assert node.parent_id is None
        assert node.is_root is True
        assert node.is_leaf is True

    async def test_create_child_node(self, async_session, project_id, tenant_id):
        """Test creating a child node under a parent."""
        repo = WBSNodeRepository(async_session)

        # Create parent
        parent = await repo.create(
            project_id=project_id,
            tenant_id=tenant_id,
            code="1",
            name="Parent",
            parent_id=None,
            node_type=WBSNodeType.DELIVERABLE,
        )

        # Create child
        child = await repo.create(
            project_id=project_id,
            tenant_id=tenant_id,
            code="1.1",
            name="Child",
            parent_id=parent.id,
            node_type=WBSNodeType.ACTIVITY,
        )

        assert child.parent_id == parent.id
        assert child.depth == 1
        assert child.is_leaf is True

        # Adding a child expands the parent's interval to contain it, so reload
        # the parent — the returned `parent` value object is an immutable snapshot
        # taken before the nested-set shift (its rgt is still the pre-shift value).
        parent_reloaded = await repo.get_by_id(parent.id, tenant_id)
        assert parent_reloaded.is_leaf is False  # Now has children
        assert child.lft > parent_reloaded.lft
        assert child.rgt < parent_reloaded.rgt

    async def test_create_multiple_siblings(self, async_session, project_id, tenant_id):
        """Test creating multiple sibling nodes."""
        repo = WBSNodeRepository(async_session)

        # Create parent
        parent = await repo.create(
            project_id=project_id,
            tenant_id=tenant_id,
            code="1",
            name="Parent",
            parent_id=None,
            node_type=WBSNodeType.WORK_PACKAGE,
        )

        # Create first child
        child1 = await repo.create(
            project_id=project_id,
            tenant_id=tenant_id,
            code="1.1",
            name="Child 1",
            parent_id=parent.id,
            node_type=WBSNodeType.ACTIVITY,
        )

        # Create second child
        child2 = await repo.create(
            project_id=project_id,
            tenant_id=tenant_id,
            code="1.2",
            name="Child 2",
            parent_id=parent.id,
            node_type=WBSNodeType.ACTIVITY,
        )

        # Verify nested set properties
        assert child1.lft < child1.rgt < child2.lft < child2.rgt
        assert parent.lft < child1.lft
        assert child2.rgt < parent.rgt


class TestWBSNodeRepositoryQuery:
    """Test WBS node query operations."""

    async def test_get_tree(self, async_session, project_id, tenant_id):
        """Test getting entire tree in hierarchical order."""
        repo = WBSNodeRepository(async_session)

        # Create tree structure:
        #   1
        #   ├── 1.1
        #   │   └── 1.1.1
        #   └── 1.2
        root = await repo.create(
            project_id=project_id,
            tenant_id=tenant_id,
            code="1",
            name="Root",
            parent_id=None,
            node_type=WBSNodeType.WORK_PACKAGE,
        )

        child1 = await repo.create(
            project_id=project_id,
            tenant_id=tenant_id,
            code="1.1",
            name="Child 1",
            parent_id=root.id,
            node_type=WBSNodeType.ACTIVITY,
        )

        await repo.create(
            project_id=project_id,
            tenant_id=tenant_id,
            code="1.1.1",
            name="Grandchild",
            parent_id=child1.id,
            node_type=WBSNodeType.MILESTONE,
        )

        await repo.create(
            project_id=project_id,
            tenant_id=tenant_id,
            code="1.2",
            name="Child 2",
            parent_id=root.id,
            node_type=WBSNodeType.ACTIVITY,
        )

        # Get tree
        tree = await repo.get_tree(project_id, tenant_id)

        # Verify order (should be lft order: root, 1.1, 1.1.1, 1.2)
        assert len(tree) == 4
        assert tree[0].code == "1"
        assert tree[1].code == "1.1"
        assert tree[2].code == "1.1.1"
        assert tree[3].code == "1.2"

    async def test_get_descendants(self, async_session, project_id, tenant_id):
        """Test getting all descendants of a node."""
        repo = WBSNodeRepository(async_session)

        # Create tree structure
        root = await repo.create(
            project_id=project_id,
            tenant_id=tenant_id,
            code="1",
            name="Root",
            parent_id=None,
            node_type=WBSNodeType.WORK_PACKAGE,
        )

        child1 = await repo.create(
            project_id=project_id,
            tenant_id=tenant_id,
            code="1.1",
            name="Child 1",
            parent_id=root.id,
            node_type=WBSNodeType.ACTIVITY,
        )

        await repo.create(
            project_id=project_id,
            tenant_id=tenant_id,
            code="1.1.1",
            name="Grandchild",
            parent_id=child1.id,
            node_type=WBSNodeType.MILESTONE,
        )

        await repo.create(
            project_id=project_id,
            tenant_id=tenant_id,
            code="1.2",
            name="Child 2",
            parent_id=root.id,
            node_type=WBSNodeType.ACTIVITY,
        )

        # Get descendants of root (all nodes)
        descendants = await repo.get_descendants(root.id, tenant_id, include_self=False)
        assert len(descendants) == 3
        assert {d.code for d in descendants} == {"1.1", "1.1.1", "1.2"}

        # Get descendants of child1 (only grandchild)
        descendants = await repo.get_descendants(child1.id, tenant_id, include_self=False)
        assert len(descendants) == 1
        assert descendants[0].code == "1.1.1"

        # Get descendants with include_self
        descendants = await repo.get_descendants(child1.id, tenant_id, include_self=True)
        assert len(descendants) == 2
        assert {d.code for d in descendants} == {"1.1", "1.1.1"}

    async def test_get_ancestors(self, async_session, project_id, tenant_id):
        """Test getting all ancestors of a node."""
        repo = WBSNodeRepository(async_session)

        # Create tree structure
        root = await repo.create(
            project_id=project_id,
            tenant_id=tenant_id,
            code="1",
            name="Root",
            parent_id=None,
            node_type=WBSNodeType.WORK_PACKAGE,
        )

        child = await repo.create(
            project_id=project_id,
            tenant_id=tenant_id,
            code="1.1",
            name="Child",
            parent_id=root.id,
            node_type=WBSNodeType.ACTIVITY,
        )

        grandchild = await repo.create(
            project_id=project_id,
            tenant_id=tenant_id,
            code="1.1.1",
            name="Grandchild",
            parent_id=child.id,
            node_type=WBSNodeType.MILESTONE,
        )

        # Get ancestors of grandchild (root and child)
        ancestors = await repo.get_ancestors(grandchild.id, tenant_id)
        assert len(ancestors) == 2
        assert ancestors[0].code == "1"
        assert ancestors[1].code == "1.1"

        # Get ancestors of root (none)
        ancestors = await repo.get_ancestors(root.id, tenant_id)
        assert len(ancestors) == 0


class TestWBSNodeRepositoryUpdate:
    """Test WBS node update operations."""

    async def test_update_metadata(self, async_session, project_id, tenant_id):
        """Test updating node metadata without changing structure."""
        repo = WBSNodeRepository(async_session)

        node = await repo.create(
            project_id=project_id,
            tenant_id=tenant_id,
            code="1",
            name="Original Name",
            parent_id=None,
            node_type=WBSNodeType.WORK_PACKAGE,
        )

        original_lft = node.lft
        original_rgt = node.rgt

        # Update metadata
        updated = await repo.update(
            node.id,
            tenant_id,
            name="Updated Name",
            description="New description",
            status=WBSNodeStatus.IN_PROGRESS,
            budget_spent=100.0,
        )

        assert updated.name == "Updated Name"
        assert updated.description == "New description"
        assert updated.status == WBSNodeStatus.IN_PROGRESS
        assert updated.budget_spent == 100.0

        # Verify structure unchanged
        assert updated.lft == original_lft
        assert updated.rgt == original_rgt


class TestWBSNodeRepositoryDelete:
    """Test WBS node deletion operations."""

    async def test_delete_leaf_node(self, async_session, project_id, tenant_id):
        """Test deleting a leaf node."""
        repo = WBSNodeRepository(async_session)

        # Create two siblings
        root = await repo.create(
            project_id=project_id,
            tenant_id=tenant_id,
            code="1",
            name="Root",
            parent_id=None,
            node_type=WBSNodeType.WORK_PACKAGE,
        )

        child1 = await repo.create(
            project_id=project_id,
            tenant_id=tenant_id,
            code="1.1",
            name="Child 1",
            parent_id=root.id,
            node_type=WBSNodeType.ACTIVITY,
        )

        await repo.create(
            project_id=project_id,
            tenant_id=tenant_id,
            code="1.2",
            name="Child 2",
            parent_id=root.id,
            node_type=WBSNodeType.ACTIVITY,
        )

        # Delete child1
        success = await repo.delete(child1.id, tenant_id)
        assert success is True

        # Verify tree integrity
        tree = await repo.get_tree(project_id, tenant_id)
        assert len(tree) == 2  # root and child2 remain
        assert {n.code for n in tree} == {"1", "1.2"}

    async def test_delete_with_descendants(self, async_session, project_id, tenant_id):
        """Test deleting a node with descendants (cascade delete)."""
        repo = WBSNodeRepository(async_session)

        # Create tree structure
        root = await repo.create(
            project_id=project_id,
            tenant_id=tenant_id,
            code="1",
            name="Root",
            parent_id=None,
            node_type=WBSNodeType.WORK_PACKAGE,
        )

        child = await repo.create(
            project_id=project_id,
            tenant_id=tenant_id,
            code="1.1",
            name="Child",
            parent_id=root.id,
            node_type=WBSNodeType.ACTIVITY,
        )

        grandchild = await repo.create(
            project_id=project_id,
            tenant_id=tenant_id,
            code="1.1.1",
            name="Grandchild",
            parent_id=child.id,
            node_type=WBSNodeType.MILESTONE,
        )

        await repo.create(
            project_id=project_id,
            tenant_id=tenant_id,
            code="1.2",
            name="Child 2",
            parent_id=root.id,
            node_type=WBSNodeType.ACTIVITY,
        )

        # Delete child (should also delete grandchild)
        success = await repo.delete(child.id, tenant_id)
        assert success is True

        # Verify tree
        tree = await repo.get_tree(project_id, tenant_id)
        assert len(tree) == 2  # root and child2 remain
        assert {n.code for n in tree} == {"1", "1.2"}

        # Verify grandchild is also deleted
        grandchild_check = await repo.get_by_id(grandchild.id, tenant_id)
        assert grandchild_check is None


class TestWBSNodeRepositoryMove:
    """Test WBS node move operations in nested set."""

    async def test_move_node_to_new_parent(self, async_session, project_id, tenant_id):
        """Test moving a node to a different parent."""
        repo = WBSNodeRepository(async_session)

        # Create structure:
        # 1
        # ├── 1.1
        # └── 1.2 (target parent)
        root = await repo.create(project_id, tenant_id, "1", "Root", None, WBSNodeType.WORK_PACKAGE)
        child1 = await repo.create(project_id, tenant_id, "1.1", "Child 1", root.id, WBSNodeType.ACTIVITY)
        child2 = await repo.create(project_id, tenant_id, "1.2", "Child 2", root.id, WBSNodeType.ACTIVITY)

        # Move 1.1 to be child of 1.2
        moved = await repo.move_node(child1.id, tenant_id, child2.id)

        assert moved.parent_id == child2.id
        assert moved.depth == 2

        # Verify tree order: 1, 1.2, 1.1
        tree = await repo.get_tree(project_id, tenant_id)
        assert len(tree) == 3
        assert tree[0].id == root.id
        assert tree[1].id == child2.id
        assert tree[2].id == child1.id

        # Verify nested set integrity
        assert tree[0].lft == 1
        assert tree[0].rgt == 6
        assert tree[1].lft == 2
        assert tree[1].rgt == 5
        assert tree[2].lft == 3
        assert tree[2].rgt == 4

    async def test_move_subtree(self, async_session, project_id, tenant_id):
        """Test moving a node that has its own children."""
        repo = WBSNodeRepository(async_session)

        # Create structure:
        # A
        # ├── B
        # │   └── C
        # └── D (target parent)
        node_a = await repo.create(project_id, tenant_id, "A", "A", None, WBSNodeType.WORK_PACKAGE)
        node_b = await repo.create(project_id, tenant_id, "B", "B", node_a.id, WBSNodeType.DELIVERABLE)
        node_c = await repo.create(project_id, tenant_id, "C", "C", node_b.id, WBSNodeType.ACTIVITY)
        node_d = await repo.create(project_id, tenant_id, "D", "D", node_a.id, WBSNodeType.DELIVERABLE)

        # Move B to D
        await repo.move_node(node_b.id, tenant_id, node_d.id)

        # Verify C moved with B
        node_c_updated = await repo.get_by_id(node_c.id, tenant_id)
        assert node_c_updated.parent_id == node_b.id
        assert node_c_updated.depth == 3 # A(0) -> D(1) -> B(2) -> C(3)

        tree = await repo.get_tree(project_id, tenant_id)
        # Expected order: A, D, B, C
        assert [n.name for n in tree] == ["A", "D", "B", "C"]

    async def test_move_to_root(self, async_session, project_id, tenant_id):
        """Test moving a child node to root."""
        repo = WBSNodeRepository(async_session)

        root = await repo.create(project_id, tenant_id, "1", "Root", None, WBSNodeType.WORK_PACKAGE)
        child = await repo.create(project_id, tenant_id, "1.1", "Child", root.id, WBSNodeType.ACTIVITY)

        # Move child to root
        moved = await repo.move_node(child.id, tenant_id, None)

        assert moved.parent_id is None
        assert moved.depth == 0

        tree = await repo.get_tree(project_id, tenant_id)
        assert len(tree) == 2
        assert tree[0].depth == 0
        assert tree[1].depth == 0

    async def test_invalid_move_to_self(self, async_session, project_id, tenant_id):
        """Test that moving a node to itself fails."""
        repo = WBSNodeRepository(async_session)
        node = await repo.create(project_id, tenant_id, "1", "Node", None, WBSNodeType.WORK_PACKAGE)

        with pytest.raises(ValueError, match="Cannot move node to itself"):
            await repo.move_node(node.id, tenant_id, node.id)

    async def test_invalid_move_to_descendant(self, async_session, project_id, tenant_id):
        """Test that moving a node to its own descendant fails."""
        repo = WBSNodeRepository(async_session)
        parent = await repo.create(project_id, tenant_id, "1", "Parent", None, WBSNodeType.WORK_PACKAGE)
        child = await repo.create(project_id, tenant_id, "1.1", "Child", parent.id, WBSNodeType.ACTIVITY)

        with pytest.raises(ValueError, match="Cannot move node to its own descendant"):
            await repo.move_node(parent.id, tenant_id, child.id)
