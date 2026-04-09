"""
C2Pro - Delete WBS Node Use Case

Delete WBS node and all its descendants.

TASK-BCK-029: WBS API Endpoint with nested set model
"""

from dataclasses import dataclass
from uuid import UUID

from src.wbs.adapters.persistence.wbs_node_repository import WBSNodeRepository


@dataclass
class DeleteWBSNodeRequest:
    """Request to delete a WBS node."""

    node_id: UUID
    tenant_id: UUID


class DeleteWBSNodeUseCase:
    """
    Delete WBS node and all descendants.

    Uses nested set boundaries to efficiently delete entire subtree.
    """

    def __init__(self, repository: WBSNodeRepository):
        self.repository = repository

    async def execute(self, request: DeleteWBSNodeRequest) -> bool:
        """
        Delete WBS node and all its descendants.

        Returns True if deleted, False if node not found.
        """
        return await self.repository.delete(request.node_id, request.tenant_id)
