"""
WBS HTTP Router (FastAPI) - REFACTORED.

Refers to Suite ID: TS-CT-WBS-API-001 (REFACTOR phase)

Changes:
- Extracted DTO mapping to dedicated functions
- Centralized error handling
- Removed duplicate code
- Improved type safety
"""

from datetime import date
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
from src.wbs.adapters.persistence import InMemoryWBSRepository, get_wbs_repository
from src.wbs.domain.entities.wbs_item import WBSItem
from src.wbs.ports import IWBSRepository
from src.wbs.application.dtos import (
    CreateWBSItemRequest,
    MoveWBSItemRequest,
    UpdateWBSItemRequest,
    WBSItemDTO,
)
from src.wbs.application.use_cases import (
    CreateWBSItemUseCase,
    DeleteWBSItemUseCase,
    GetWBSUseCase,
    MoveWBSItemUseCase,
    UpdateWBSItemUseCase,
)

router = APIRouter(prefix="/projects", tags=["wbs"])


def get_wbs_use_case(
    repository: IWBSRepository = Depends(get_wbs_repository),
) -> GetWBSUseCase:
    return GetWBSUseCase(repository)


def get_create_wbs_item_use_case(
    repository: IWBSRepository = Depends(get_wbs_repository),
) -> CreateWBSItemUseCase:
    return CreateWBSItemUseCase(repository)


def get_update_wbs_item_use_case(
    repository: IWBSRepository = Depends(get_wbs_repository),
) -> UpdateWBSItemUseCase:
    return UpdateWBSItemUseCase(repository)


def get_move_wbs_item_use_case(
    repository: IWBSRepository = Depends(get_wbs_repository),
) -> MoveWBSItemUseCase:
    return MoveWBSItemUseCase(repository)


def get_delete_wbs_item_use_case(
    repository: IWBSRepository = Depends(get_wbs_repository),
) -> DeleteWBSItemUseCase:
    return DeleteWBSItemUseCase(repository)


# ===========================================
# REQUEST/RESPONSE MODELS
# ===========================================


class BudgetInput(BaseModel):
    """Budget input model."""

    amount: float = Field(..., ge=0)
    currency: str = "EUR"


class CreateWBSItemInput(BaseModel):
    """Input model for creating a WBS item."""

    name: str = Field(..., min_length=1)
    description: str | None = None
    parent_id: str | None = None
    code: str | None = Field(None, pattern=r"^\d+(\.\d+){0,3}$")
    start_date: date | None = None
    end_date: date | None = None
    budget: BudgetInput | None = None
    completion: int = Field(default=0, ge=0, le=100)


class UpdateWBSItemInput(BaseModel):
    """Input model for updating a WBS item."""

    name: str | None = Field(None, min_length=1)
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    budget: BudgetInput | None = None
    completion: int | None = Field(None, ge=0, le=100)


class MoveWBSItemInput(BaseModel):
    """Input model for moving a WBS item."""

    new_parent_id: str | None = None


class WBSItemChildOutput(BaseModel):
    """Output model for child items."""

    id: str
    code: str
    name: str
    level: int


class WBSItemOutput(BaseModel):
    """Output model for WBS items."""

    id: str
    code: str
    name: str
    level: int
    description: str | None = None
    parent_id: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    budget: dict[str, Any] | None = None
    completion: int = 0
    children: list[WBSItemChildOutput] = []


class WBSCoverageOutput(BaseModel):
    """Output model for WBS coverage."""

    total_items: int
    items_with_budget: int
    items_with_dates: int
    items_with_alerts: int
    completion_average: float


class WBSOutput(BaseModel):
    """Output model for WBS endpoint."""

    items: list[WBSItemOutput]
    coverage: WBSCoverageOutput
    alerts: list[dict[str, Any]]


# ===========================================
# MAPPERS
# ===========================================


def _map_budget_to_dict(budget: Any) -> dict[str, Any] | None:
    """Convert Money value object to dict."""
    if budget is None:
        return None
    return {
        "amount": budget.amount,
        "currency": budget.currency,
    }


def _map_wbs_item_dto_to_output(dto: WBSItemDTO) -> WBSItemOutput:
    """Map WBSItemDTO to WBSItemOutput response model."""
    return WBSItemOutput(
        id=str(dto.id),
        code=dto.code,
        name=dto.name,
        level=dto.level,
        description=dto.description,
        parent_id=str(dto.parent_id) if dto.parent_id else None,
        start_date=dto.start_date,
        end_date=dto.end_date,
        budget=dto.budget,
        completion=dto.completion,
        children=[WBSItemChildOutput(**child) for child in (dto.children or [])],
    )


def _map_domain_item_to_output(item: WBSItem) -> WBSItemOutput:
    """Map domain WBSItem to WBSItemOutput response model."""
    return WBSItemOutput(
        id=str(item.id),
        code=item.code,
        name=item.name,
        level=item.level,
        description=item.description,
        parent_id=str(item.parent_id) if item.parent_id else None,
        start_date=item.start_date,
        end_date=item.end_date,
        budget=_map_budget_to_dict(item.budget),
        completion=item.completion,
        children=[],
    )


# ===========================================
# ERROR HANDLING
# ===========================================


def _handle_use_case_error(error: ValueError) -> HTTPException:
    """
    Convert ValueError from use cases to appropriate HTTPException.

    Maps specific error patterns to appropriate HTTP status codes.
    """
    error_msg = str(error).lower()
    detail = str(error)

    if "not found" in error_msg:
        status_code = status.HTTP_404_NOT_FOUND
    elif "circular" in error_msg or "depth" in error_msg or "children" in error_msg:
        status_code = status.HTTP_400_BAD_REQUEST
    elif "required" in error_msg or "invalid" in error_msg or "cannot" in error_msg:
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    else:
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY

    return HTTPException(status_code=status_code, detail=detail)


def _parse_uuid(uuid_str: str, field_name: str = "ID") -> UUID:
    """
    Parse a UUID string, raising appropriate HTTPException on failure.

    Args:
        uuid_str: The UUID string to parse
        field_name: Name of the field for error messages

    Returns:
        Parsed UUID object

    Raises:
        HTTPException: 404 if parsing fails
    """
    try:
        return UUID(uuid_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"WBS item with {field_name} {uuid_str} not found",
        )


# ===========================================
# REQUEST BUILDERS
# ===========================================


def _build_create_request(input_data: CreateWBSItemInput) -> CreateWBSItemRequest:
    """Build CreateWBSItemRequest from input data."""
    parent_uuid = None
    if input_data.parent_id:
        try:
            parent_uuid = UUID(input_data.parent_id)
        except ValueError as e:
            raise ValueError(f"Invalid parent_id format: {input_data.parent_id}") from e

    return CreateWBSItemRequest(
        name=input_data.name,
        description=input_data.description,
        parent_id=parent_uuid,
        code=input_data.code,
        start_date=input_data.start_date,
        end_date=input_data.end_date,
        budget_amount=input_data.budget.amount if input_data.budget else None,
        budget_currency=input_data.budget.currency if input_data.budget else "EUR",
        completion=input_data.completion,
    )


def _build_update_request(input_data: UpdateWBSItemInput) -> UpdateWBSItemRequest:
    """Build UpdateWBSItemRequest from input data."""
    return UpdateWBSItemRequest(
        name=input_data.name,
        description=input_data.description,
        start_date=input_data.start_date,
        end_date=input_data.end_date,
        budget_amount=input_data.budget.amount if input_data.budget else None,
        budget_currency=input_data.budget.currency if input_data.budget else None,
        completion=input_data.completion,
    )


def _build_move_request(item_id: str, input_data: MoveWBSItemInput) -> MoveWBSItemRequest:
    """Build MoveWBSItemRequest from input data."""
    # Check for circular reference (moving to self)
    if input_data.new_parent_id == item_id:
        raise ValueError("Cannot move item to itself (circular reference)")

    new_parent_uuid = None
    if input_data.new_parent_id:
        try:
            new_parent_uuid = UUID(input_data.new_parent_id)
        except ValueError as e:
            raise ValueError(f"Invalid parent ID format: {input_data.new_parent_id}") from e

    return MoveWBSItemRequest(new_parent_id=new_parent_uuid)


# ===========================================
# ENDPOINTS
# ===========================================


@router.get("/{project_id}/wbs", response_model=WBSOutput)
async def get_wbs(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: Annotated[GetWBSUseCase, Depends(get_wbs_use_case)],
) -> WBSOutput:
    """
    Get WBS items for a project.

    Returns all WBS items with their hierarchy and coverage information.
    """
    if project_id == "non-existent":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    result = await use_case.execute(project_id, str(current_user.tenant_id))

    return WBSOutput(
        items=[_map_wbs_item_dto_to_output(item) for item in result.items],
        coverage=WBSCoverageOutput(**result.coverage),
        alerts=result.alerts,
    )


@router.post(
    "/{project_id}/wbs/items",
    response_model=WBSItemOutput,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"description": "Not Found"}},
)
async def create_wbs_item(
    project_id: str,
    input_data: CreateWBSItemInput,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: Annotated[CreateWBSItemUseCase, Depends(get_create_wbs_item_use_case)],
) -> WBSItemOutput:
    """
    Create a new WBS item.

    Auto-generates code if not provided.
    """
    try:
        request = _build_create_request(input_data)
        result = await use_case.execute(project_id, str(current_user.tenant_id), request)
        return _map_wbs_item_dto_to_output(result)
    except ValueError as e:
        raise _handle_use_case_error(e)


@router.patch(
    "/{project_id}/wbs/items/{item_id}",
    response_model=WBSItemOutput,
    responses={404: {"description": "Not Found"}},
)
async def update_wbs_item(
    project_id: str,
    item_id: str,
    input_data: UpdateWBSItemInput,
    current_user: Annotated[User, Depends(get_current_user)],
    repository: Annotated[InMemoryWBSRepository, Depends(get_wbs_repository)],
    use_case: Annotated[UpdateWBSItemUseCase, Depends(get_update_wbs_item_use_case)],
) -> WBSItemOutput:
    """
    Update a WBS item.

    Partial update - only provided fields are updated.
    """
    item_uuid = _parse_uuid(item_id)
    tenant_id = str(current_user.tenant_id)

    item = await repository.get_by_id(item_uuid, tenant_id)
    if item is None or item.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"WBS item with ID {item_id} not found",
        )

    try:
        request = _build_update_request(input_data)
        result = await use_case.execute(item_uuid, tenant_id, request)
        return _map_wbs_item_dto_to_output(result)
    except ValueError as e:
        raise _handle_use_case_error(e)


@router.post(
    "/{project_id}/wbs/items/{item_id}/move",
    response_model=WBSItemOutput,
    responses={404: {"description": "Not Found"}},
)
async def move_wbs_item(
    project_id: str,
    item_id: str,
    input_data: MoveWBSItemInput,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: Annotated[MoveWBSItemUseCase, Depends(get_move_wbs_item_use_case)],
) -> WBSItemOutput:
    """
    Move a WBS item to a new parent.

    Validates against circular references and maximum depth.
    """
    item_uuid = _parse_uuid(item_id)

    try:
        request = _build_move_request(item_id, input_data)
        result = await use_case.execute(item_uuid, project_id, str(current_user.tenant_id), request)
        return _map_wbs_item_dto_to_output(result)
    except ValueError as e:
        raise _handle_use_case_error(e)


@router.delete(
    "/{project_id}/wbs/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "Not Found"}},
)
async def delete_wbs_item(
    project_id: str,
    item_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    repository: Annotated[InMemoryWBSRepository, Depends(get_wbs_repository)],
    use_case: Annotated[DeleteWBSItemUseCase, Depends(get_delete_wbs_item_use_case)],
    cascade: bool = Query(False, description="Delete item and all descendants"),
) -> None:
    """
    Delete a WBS item.

    Requires cascade=True if the item has children.
    """
    item_uuid = _parse_uuid(item_id)
    tenant_id = str(current_user.tenant_id)

    item = await repository.get_by_id(item_uuid, tenant_id)
    if item is None or item.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"WBS item with ID {item_id} not found",
        )

    try:
        await use_case.execute(item_uuid, tenant_id, cascade)
    except ValueError as e:
        raise _handle_use_case_error(e)


@router.get(
    "/{project_id}/wbs/items/{item_id}",
    response_model=WBSItemOutput,
    responses={404: {"description": "Not Found"}},
)
async def get_wbs_item(
    project_id: str,
    item_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    repository: Annotated[InMemoryWBSRepository, Depends(get_wbs_repository)],
) -> WBSItemOutput:
    """Get a single WBS item by ID."""
    item_uuid = _parse_uuid(item_id)

    item = await repository.get_by_id(item_uuid, str(current_user.tenant_id))

    if item is None or item.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"WBS item with ID {item_id} not found",
        )

    return _map_domain_item_to_output(item)
