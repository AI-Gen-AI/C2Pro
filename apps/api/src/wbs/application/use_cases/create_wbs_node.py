"""
C2Pro - Create WBS Node Use Case

Create a new WBS node in nested set tree.

TASK-BCK-029: WBS API Endpoint with nested set model
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from src.wbs.adapters.persistence.wbs_node_repository import WBSNodeRepository
from src.wbs.domain.enums import WBSNodeStatus, WBSNodeType
from src.wbs.domain.models import WBSNode


@dataclass
class CreateWBSNodeRequest:
    """Request to create a new WBS node."""

    project_id: UUID
    tenant_id: UUID
    code: str
    name: str
    node_type: WBSNodeType
    parent_id: UUID | None = None
    description: str | None = None
    status: WBSNodeStatus = WBSNodeStatus.NOT_STARTED
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    budget_allocated: float | None = None
    metadata: dict[str, Any] | None = None


class CreateWBSNodeUseCase:
    """
    Create a new WBS node.

    Inserts node into nested set tree at correct position.
    """

    def __init__(self, repository: WBSNodeRepository):
        self.repository = repository

    async def execute(self, request: CreateWBSNodeRequest) -> WBSNode:
        """
        Create a new WBS node.

        If parent_id is None, creates a root node.
        Otherwise, inserts as last child of parent.
        """
        return await self.repository.create(
            project_id=request.project_id,
            tenant_id=request.tenant_id,
            code=request.code,
            name=request.name,
            parent_id=request.parent_id,
            node_type=request.node_type,
            description=request.description,
            status=request.status,
            planned_start=request.planned_start,
            planned_end=request.planned_end,
            budget_allocated=request.budget_allocated,
            metadata=request.metadata or {},
        )
