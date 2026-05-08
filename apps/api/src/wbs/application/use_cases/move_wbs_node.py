"""
C2Pro - Move WBS Node Use Case

Move a WBS node and its subtree to a new parent in nested set tree.

TASK-BCK-029: WBS API Endpoint with nested set model
"""

from dataclasses import dataclass
from uuid import UUID

from src.wbs.adapters.persistence.wbs_node_repository import WBSNodeRepository
from src.wbs.domain.models import WBSNode


@dataclass
class MoveWBSNodeRequest:
    """Request to move a WBS node."""

    node_id: UUID
    tenant_id: UUID
    new_parent_id: UUID | None


class MoveWBSNodeUseCase:
    """
    Move a WBS node.

    Updates nested set tree boundaries to move subtree.
    """

    def __init__(self, repository: WBSNodeRepository):
        self.repository = repository

    async def execute(self, request: MoveWBSNodeRequest) -> WBSNode | None:
        """
        Move a WBS node and its descendants.
        """
        return await self.repository.move_node(
            node_id=request.node_id,
            tenant_id=request.tenant_id,
            new_parent_id=request.new_parent_id,
        )
