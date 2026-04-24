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
def tenant_id():
    """Fixture for tenant ID."""
    return uuid4()


@pytest.fixture
def project_id():
    """Fixture for project ID."""
    return uuid4()


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
        assert child.lft > parent.lft
        assert child.rgt < parent.rgt
        assert child.is_leaf is True

        # Verify parent is updated
        parent_reloaded = await repo.get_by_id(parent.id, tenant_id)
        assert parent_reloaded.is_leaf is False  # Now has children

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
