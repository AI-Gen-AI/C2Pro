"""
C2Pro - WBS Node HTTP Router (FastAPI)

API endpoints for WBS nodes using nested set model.

TASK-BCK-029: WBS API Endpoint with nested set model
Refers to Suite ID: TS-INT-DB-WBS-001
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
from src.core.database import get_db
from src.wbs.adapters.persistence.wbs_node_repository import WBSNodeRepository
from src.wbs.application.use_cases.create_wbs_node import (
    CreateWBSNodeRequest,
    CreateWBSNodeUseCase,
)
from src.wbs.application.use_cases.delete_wbs_node import (
    DeleteWBSNodeRequest,
    DeleteWBSNodeUseCase,
)
from src.wbs.application.use_cases.get_wbs_tree import (
    GetWBSTreeRequest,
    GetWBSTreeUseCase,
)
from src.wbs.application.use_cases.move_wbs_node import (
    MoveWBSNodeRequest,
    MoveWBSNodeUseCase,
)
from src.wbs.application.use_cases.update_wbs_node import (
    UpdateWBSNodeRequest,
    UpdateWBSNodeUseCase,
)
from src.wbs.domain.enums import WBSNodeStatus, WBSNodeType
from src.wbs.domain.models import WBSNode

router = APIRouter(prefix="/wbs-tree", tags=["wbs-tree"])


# ===========================================
# DEPENDENCY INJECTION
# ===========================================


def get_wbs_node_repository(
    session: AsyncSession = Depends(get_db),
) -> WBSNodeRepository:
    """Get WBS node repository."""
    return WBSNodeRepository(session)


# ===========================================
# REQUEST/RESPONSE MODELS
# ===========================================


class CreateWBSNodeInput(BaseModel):
    """Input model for creating a WBS node."""

    project_id: str = Field(..., description="Project UUID")
    code: str = Field(..., min_length=1, max_length=50, description="WBS code (e.g., '1.2.3')")
    name: str = Field(..., min_length=1, max_length=255)
    node_type: WBSNodeType
    parent_id: str | None = Field(None, description="Parent node UUID (None for root)")
    description: str | None = None
    status: WBSNodeStatus = WBSNodeStatus.NOT_STARTED
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    budget_allocated: float | None = Field(None, ge=0)
    metadata: dict = Field(default_factory=dict)


class UpdateWBSNodeInput(BaseModel):
    """Input model for updating a WBS node."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    status: WBSNodeStatus | None = None
    node_type: WBSNodeType | None = None
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    actual_start: datetime | None = None
    actual_end: datetime | None = None
    budget_allocated: float | None = Field(None, ge=0)
    budget_spent: float | None = Field(None, ge=0)
    metadata: dict | None = None


class MoveWBSNodeInput(BaseModel):
    """Input model for moving/reordering a WBS node."""

    new_parent_id: str | None = Field(None, description="New parent node UUID (None for root)")


class WBSNodeOutput(BaseModel):
    """Output model for WBS nodes."""

    id: str
    project_id: str
    tenant_id: str
    code: str
    name: str
    description: str | None
    lft: int
    rgt: int
    depth: int
    parent_id: str | None
    node_type: WBSNodeType
    status: WBSNodeStatus
    planned_start: datetime | None
    planned_end: datetime | None
    actual_start: datetime | None
    actual_end: datetime | None
    budget_allocated: float | None
    budget_spent: float
    metadata: dict
    created_at: datetime
    updated_at: datetime
    is_leaf: bool
    is_root: bool
    children_count: int
    budget_variance: float | None = None
    budget_utilization_pct: float | None = None


# ===========================================
# MAPPERS
# ===========================================


def _map_node_to_output(node: WBSNode) -> WBSNodeOutput:
    """Map WBSNode domain model to output response model."""
    return WBSNodeOutput(
        id=str(node.id),
        project_id=str(node.project_id),
        tenant_id=str(node.tenant_id),
        code=node.code,
        name=node.name,
        description=node.description,
        lft=node.lft,
        rgt=node.rgt,
        depth=node.depth,
        parent_id=str(node.parent_id) if node.parent_id else None,
        node_type=node.node_type,
        status=node.status,
        planned_start=node.planned_start,
        planned_end=node.planned_end,
        actual_start=node.actual_start,
        actual_end=node.actual_end,
        budget_allocated=node.budget_allocated,
        budget_spent=node.budget_spent,
        metadata=node.metadata,
        created_at=node.created_at,
        updated_at=node.updated_at,
        is_leaf=node.is_leaf,
        is_root=node.is_root,
        children_count=node.children_count,
        budget_variance=node.budget_variance,
        budget_utilization_pct=node.budget_utilization_pct,
    )


def _parse_uuid(uuid_str: str, field_name: str = "ID") -> UUID:
    """Parse a UUID string, raising appropriate HTTPException on failure."""
    try:
        return UUID(uuid_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name} format: {uuid_str}",
        )


# ===========================================
# ENDPOINTS
# ===========================================


@router.get("/projects/{project_id}/tree", response_model=list[WBSNodeOutput])
async def get_wbs_tree(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    repository: Annotated[WBSNodeRepository, Depends(get_wbs_node_repository)],
) -> list[WBSNodeOutput]:
    """
    Get WBS tree for a project.

    Returns all nodes in hierarchical order using nested set lft sorting.
    Efficient single-query retrieval.
    """
    project_uuid = _parse_uuid(project_id, "project_id")

    use_case = GetWBSTreeUseCase(repository)
    request = GetWBSTreeRequest(
        project_id=project_uuid,
        tenant_id=UUID(str(current_user.tenant_id)),
    )

    nodes = await use_case.execute(request)
    return [_map_node_to_output(node) for node in nodes]


@router.get("/projects/{project_id}/nodes/{node_id}/subtree", response_model=list[WBSNodeOutput])
async def get_wbs_subtree(
    project_id: str,
    node_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    repository: Annotated[WBSNodeRepository, Depends(get_wbs_node_repository)],
) -> list[WBSNodeOutput]:
    """
    Get subtree from a specific node.

    Returns node and all its descendants using efficient nested set query.
    """
    project_uuid = _parse_uuid(project_id, "project_id")
    node_uuid = _parse_uuid(node_id, "node_id")

    use_case = GetWBSTreeUseCase(repository)
    request = GetWBSTreeRequest(
        project_id=project_uuid,
        tenant_id=UUID(str(current_user.tenant_id)),
        node_id=node_uuid,
    )

    nodes = await use_case.execute(request)
    return [_map_node_to_output(node) for node in nodes]


@router.get(
    "/projects/{project_id}/nodes/{node_id}",
    response_model=WBSNodeOutput,
    responses={404: {"description": "Not Found"}},
)
async def get_wbs_node(
    project_id: str,
    node_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    repository: Annotated[WBSNodeRepository, Depends(get_wbs_node_repository)],
) -> WBSNodeOutput:
    """Get a single WBS node by ID."""
    node_uuid = _parse_uuid(node_id, "node_id")

    node = await repository.get_by_id(node_uuid, UUID(str(current_user.tenant_id)))

    if node is None or str(node.project_id) != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"WBS node with ID {node_id} not found",
        )

    return _map_node_to_output(node)


@router.get("/projects/{project_id}/nodes/{node_id}/descendants", response_model=list[WBSNodeOutput])
async def get_wbs_descendants(
    _project_id: Annotated[str, Path(alias="project_id")],
    node_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    repository: Annotated[WBSNodeRepository, Depends(get_wbs_node_repository)],
    include_self: bool = False,
) -> list[WBSNodeOutput]:
    """
    Get all descendants of a node.

    Uses efficient nested set query: WHERE lft > parent.lft AND rgt < parent.rgt
    """
    node_uuid = _parse_uuid(node_id, "node_id")

    nodes = await repository.get_descendants(
        node_uuid,
        UUID(str(current_user.tenant_id)),
        include_self=include_self,
    )

    return [_map_node_to_output(node) for node in nodes]


@router.get("/projects/{project_id}/nodes/{node_id}/ancestors", response_model=list[WBSNodeOutput])
async def get_wbs_ancestors(
    _project_id: Annotated[str, Path(alias="project_id")],
    node_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    repository: Annotated[WBSNodeRepository, Depends(get_wbs_node_repository)],
) -> list[WBSNodeOutput]:
    """
    Get all ancestors of a node (path from root to node).

    Uses efficient nested set query: WHERE lft < node.lft AND rgt > node.rgt
    """
    node_uuid = _parse_uuid(node_id, "node_id")

    nodes = await repository.get_ancestors(
        node_uuid,
        UUID(str(current_user.tenant_id)),
    )

    return [_map_node_to_output(node) for node in nodes]


@router.post(
    "/projects/{project_id}/nodes",
    response_model=WBSNodeOutput,
    status_code=status.HTTP_201_CREATED,
)
async def create_wbs_node(
    project_id: str,
    input_data: CreateWBSNodeInput,
    current_user: Annotated[User, Depends(get_current_user)],
    repository: Annotated[WBSNodeRepository, Depends(get_wbs_node_repository)],
) -> WBSNodeOutput:
    """
    Create a new WBS node.

    Inserts node into nested set tree at correct position.
    If parent_id is None, creates a root node.
    """
    # Validate project_id matches input
    if input_data.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="project_id in path must match project_id in body",
        )

    project_uuid = _parse_uuid(project_id, "project_id")
    parent_uuid = _parse_uuid(input_data.parent_id, "parent_id") if input_data.parent_id else None

    try:
        use_case = CreateWBSNodeUseCase(repository)
        request = CreateWBSNodeRequest(
            project_id=project_uuid,
            tenant_id=UUID(str(current_user.tenant_id)),
            code=input_data.code,
            name=input_data.name,
            node_type=input_data.node_type,
            parent_id=parent_uuid,
            description=input_data.description,
            status=input_data.status,
            planned_start=input_data.planned_start,
            planned_end=input_data.planned_end,
            budget_allocated=input_data.budget_allocated,
            metadata=input_data.metadata,
        )

        node = await use_case.execute(request)
        return _map_node_to_output(node)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )


@router.patch(
    "/projects/{project_id}/nodes/{node_id}",
    response_model=WBSNodeOutput,
    responses={404: {"description": "Not Found"}},
)
async def update_wbs_node(
    project_id: str,
    node_id: str,
    input_data: UpdateWBSNodeInput,
    current_user: Annotated[User, Depends(get_current_user)],
    repository: Annotated[WBSNodeRepository, Depends(get_wbs_node_repository)],
) -> WBSNodeOutput:
    """
    Update a WBS node (metadata only).

    Does not change tree structure (parent, lft, rgt, depth).
    """
    node_uuid = _parse_uuid(node_id, "node_id")

    # Verify node exists and belongs to project
    existing = await repository.get_by_id(node_uuid, UUID(str(current_user.tenant_id)))
    if existing is None or str(existing.project_id) != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"WBS node with ID {node_id} not found",
        )

    try:
        use_case = UpdateWBSNodeUseCase(repository)
        request = UpdateWBSNodeRequest(
            node_id=node_uuid,
            tenant_id=UUID(str(current_user.tenant_id)),
            name=input_data.name,
            description=input_data.description,
            status=input_data.status,
            node_type=input_data.node_type,
            planned_start=input_data.planned_start,
            planned_end=input_data.planned_end,
            actual_start=input_data.actual_start,
            actual_end=input_data.actual_end,
            budget_allocated=input_data.budget_allocated,
            budget_spent=input_data.budget_spent,
            metadata=input_data.metadata,
        )

        node = await use_case.execute(request)
        if node is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"WBS node with ID {node_id} not found",
            )

        return _map_node_to_output(node)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )


@router.delete(
    "/projects/{project_id}/nodes/{node_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "Not Found"}},
)
async def delete_wbs_node(
    project_id: str,
    node_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    repository: Annotated[WBSNodeRepository, Depends(get_wbs_node_repository)],
) -> None:
    """
    Delete a WBS node and all its descendants.

    Uses efficient nested set deletion - all descendants are removed.
    """
    node_uuid = _parse_uuid(node_id, "node_id")

    # Verify node exists and belongs to project
    existing = await repository.get_by_id(node_uuid, UUID(str(current_user.tenant_id)))
    if existing is None or str(existing.project_id) != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"WBS node with ID {node_id} not found",
        )

    use_case = DeleteWBSNodeUseCase(repository)
    request = DeleteWBSNodeRequest(
        node_id=node_uuid,
        tenant_id=UUID(str(current_user.tenant_id)),
    )

    success = await use_case.execute(request)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"WBS node with ID {node_id} not found",
        )


@router.patch(
    "/projects/{project_id}/nodes/{node_id}/reorder",
    response_model=WBSNodeOutput,
    responses={404: {"description": "Not Found"}},
)
async def reorder_wbs_node(
    project_id: str,
    node_id: str,
    input_data: MoveWBSNodeInput,
    current_user: Annotated[User, Depends(get_current_user)],
    repository: Annotated[WBSNodeRepository, Depends(get_wbs_node_repository)],
) -> WBSNodeOutput:
    """
    Move a WBS node and its subtree to a new parent.

    Updates the nested set tree structure.
    """
    node_uuid = _parse_uuid(node_id, "node_id")
    new_parent_uuid = _parse_uuid(input_data.new_parent_id, "new_parent_id") if input_data.new_parent_id else None

    # Verify node exists and belongs to project
    existing = await repository.get_by_id(node_uuid, UUID(str(current_user.tenant_id)))
    if existing is None or str(existing.project_id) != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"WBS node with ID {node_id} not found",
        )

    try:
        use_case = MoveWBSNodeUseCase(repository)
        request = MoveWBSNodeRequest(
            node_id=node_uuid,
            tenant_id=UUID(str(current_user.tenant_id)),
            new_parent_id=new_parent_uuid,
        )

        node = await use_case.execute(request)
        if node is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"WBS node with ID {node_id} not found",
            )

        return _map_node_to_output(node)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
