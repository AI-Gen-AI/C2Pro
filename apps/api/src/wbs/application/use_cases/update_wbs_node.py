"""
C2Pro - Update WBS Node Use Case

Update WBS node metadata (not structure).

TASK-BCK-029: WBS API Endpoint with nested set model
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.wbs.adapters.persistence.wbs_node_repository import WBSNodeRepository
from src.wbs.domain.enums import WBSNodeStatus, WBSNodeType
from src.wbs.domain.models import WBSNode


@dataclass
class UpdateWBSNodeRequest:
    """Request to update a WBS node."""

    node_id: UUID
    tenant_id: UUID
    name: str | None = None
    description: str | None = None
    status: WBSNodeStatus | None = None
    node_type: WBSNodeType | None = None
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    actual_start: datetime | None = None
    actual_end: datetime | None = None
    budget_allocated: float | None = None
    budget_spent: float | None = None
    metadata: dict | None = None


class UpdateWBSNodeUseCase:
    """
    Update WBS node metadata.

    Does not change tree structure (parent, lft, rgt, depth).
    For moving nodes, a separate MoveWBSNode use case would be needed.
    """

    def __init__(self, repository: WBSNodeRepository):
        self.repository = repository

    async def execute(self, request: UpdateWBSNodeRequest) -> WBSNode | None:
        """
        Update WBS node metadata.

        Returns None if node not found.
        """
        # Build kwargs with only provided fields
        kwargs = {}
        if request.name is not None:
            kwargs["name"] = request.name
        if request.description is not None:
            kwargs["description"] = request.description
        if request.status is not None:
            kwargs["status"] = request.status
        if request.node_type is not None:
            kwargs["node_type"] = request.node_type
        if request.planned_start is not None:
            kwargs["planned_start"] = request.planned_start
        if request.planned_end is not None:
            kwargs["planned_end"] = request.planned_end
        if request.actual_start is not None:
            kwargs["actual_start"] = request.actual_start
        if request.actual_end is not None:
            kwargs["actual_end"] = request.actual_end
        if request.budget_allocated is not None:
            kwargs["budget_allocated"] = request.budget_allocated
        if request.budget_spent is not None:
            kwargs["budget_spent"] = request.budget_spent
        if request.metadata is not None:
            kwargs["metadata"] = request.metadata

        return await self.repository.update(request.node_id, request.tenant_id, **kwargs)
