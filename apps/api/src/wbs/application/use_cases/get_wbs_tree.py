"""
C2Pro - Get WBS Tree Use Case

Retrieve WBS tree structure using nested set model.

TASK-BCK-029: WBS API Endpoint with nested set model
"""

from dataclasses import dataclass
from uuid import UUID

from src.wbs.adapters.persistence.wbs_node_repository import WBSNodeRepository
from src.wbs.domain.models import WBSNode


@dataclass
class GetWBSTreeRequest:
    """Request to get WBS tree."""

    project_id: UUID
    tenant_id: UUID
    node_id: UUID | None = None  # If provided, get subtree from this node


class GetWBSTreeUseCase:
    """
    Get WBS tree for a project.

    Uses nested set model for efficient tree retrieval in single query.
    """

    def __init__(self, repository: WBSNodeRepository):
        self.repository = repository

    async def execute(self, request: GetWBSTreeRequest) -> list[WBSNode]:
        """
        Get WBS tree.

        If node_id is provided, returns subtree from that node.
        Otherwise, returns entire project tree.
        """
        if request.node_id:
            # Get subtree starting from specific node
            return await self.repository.get_descendants(
                request.node_id, request.tenant_id, include_self=True
            )
        else:
            # Get entire project tree
            return await self.repository.get_tree(request.project_id, request.tenant_id)
