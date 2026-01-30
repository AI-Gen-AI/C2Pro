"""
HTTP adapter (FastAPI router) for the Stakeholders module.
"""
from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.security import CurrentTenantId, CurrentUserId
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.stakeholders.adapters.persistence.sqlalchemy_stakeholder_repository import (
    SqlAlchemyStakeholderRepository,
)
from src.stakeholders.application.create_stakeholder_use_case import CreateStakeholderUseCase
from src.stakeholders.application.delete_stakeholder_use_case import DeleteStakeholderUseCase
from src.stakeholders.application.helpers import score_from_metadata
from src.stakeholders.application.list_project_stakeholders_use_case import (
    ListProjectStakeholdersUseCase,
)
from src.stakeholders.application.update_stakeholder_use_case import UpdateStakeholderUseCase
from src.stakeholders.application.dtos import (
    StakeholderCreateRequest,
    StakeholderResponseOut,
    StakeholderUpdateRequest,
)
from src.stakeholders.domain.models import Stakeholder

logger = structlog.get_logger()

router = APIRouter(
    prefix="/stakeholders",
    tags=["Stakeholders"],
    responses={404: {"description": "Not Found"}},
)


def get_repository(db: AsyncSession = Depends(get_session)) -> SqlAlchemyStakeholderRepository:
    return SqlAlchemyStakeholderRepository(session=db)

def get_document_repository(
    db: AsyncSession = Depends(get_session),
) -> SqlAlchemyDocumentRepository:
    return SqlAlchemyDocumentRepository(session=db)


def get_list_use_case(
    repo: SqlAlchemyStakeholderRepository = Depends(get_repository),
) -> ListProjectStakeholdersUseCase:
    return ListProjectStakeholdersUseCase(repository=repo)


def get_create_use_case(
    repo: SqlAlchemyStakeholderRepository = Depends(get_repository),
) -> CreateStakeholderUseCase:
    return CreateStakeholderUseCase(repository=repo)


def get_update_use_case(
    repo: SqlAlchemyStakeholderRepository = Depends(get_repository),
) -> UpdateStakeholderUseCase:
    return UpdateStakeholderUseCase(repository=repo)


def get_delete_use_case(
    repo: SqlAlchemyStakeholderRepository = Depends(get_repository),
) -> DeleteStakeholderUseCase:
    return DeleteStakeholderUseCase(repository=repo)


@router.get(
    "/projects/{project_id}",
    response_model=list[StakeholderResponseOut],
    summary="List stakeholders for a project",
)
async def list_project_stakeholders(
    project_id: UUID,
    _tenant_id: CurrentTenantId,
    _user_id: CurrentUserId,
    list_use_case: ListProjectStakeholdersUseCase = Depends(get_list_use_case),
) -> list[StakeholderResponseOut]:
    stakeholders, _ = await list_use_case.execute(project_id=project_id)
    return [_to_response(stakeholder) for stakeholder in stakeholders]


@router.post(
    "/projects/{project_id}",
    response_model=StakeholderResponseOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create stakeholder manually",
)
async def create_project_stakeholder(
    project_id: UUID,
    payload: StakeholderCreateRequest,
    _tenant_id: CurrentTenantId,
    user_id: CurrentUserId,
    document_repository: SqlAlchemyDocumentRepository = Depends(get_document_repository),
    create_use_case: CreateStakeholderUseCase = Depends(get_create_use_case),
) -> StakeholderResponseOut:
    if payload.stakeholder_metadata is not None and not isinstance(
        payload.stakeholder_metadata, dict
    ):
        raise HTTPException(status_code=400, detail="stakeholder_metadata must be a dict")

    if payload.source_clause_id:
        exists = await document_repository.clause_exists(payload.source_clause_id)
        if not exists:
            raise HTTPException(status_code=400, detail="source_clause_id not found")

    stakeholder = await create_use_case.execute(
        project_id=project_id, user_id=user_id, payload=payload
    )
    logger.info(
        "stakeholder_created",
        project_id=str(project_id),
        stakeholder_id=str(stakeholder.id),
        user_id=str(user_id),
    )
    return _to_response(stakeholder)


@router.patch(
    "/{stakeholder_id}",
    response_model=StakeholderResponseOut,
    summary="Update stakeholder",
)
async def update_stakeholder(
    stakeholder_id: UUID,
    payload: StakeholderUpdateRequest,
    _tenant_id: CurrentTenantId,
    user_id: CurrentUserId,
    document_repository: SqlAlchemyDocumentRepository = Depends(get_document_repository),
    update_use_case: UpdateStakeholderUseCase = Depends(get_update_use_case),
) -> StakeholderResponseOut:
    if payload.stakeholder_metadata is not None and not isinstance(
        payload.stakeholder_metadata, dict
    ):
        raise HTTPException(status_code=400, detail="stakeholder_metadata must be a dict")

    if payload.source_clause_id:
        exists = await document_repository.clause_exists(payload.source_clause_id)
        if not exists:
            raise HTTPException(status_code=400, detail="source_clause_id not found")

    try:
        stakeholder = await update_use_case.execute(
            stakeholder_id=stakeholder_id, user_id=user_id, payload=payload
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="Stakeholder not found")

    return _to_response(stakeholder)


@router.delete(
    "/{stakeholder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete stakeholder",
)
async def delete_stakeholder(
    stakeholder_id: UUID,
    _tenant_id: CurrentTenantId,
    _user_id: CurrentUserId,
    delete_use_case: DeleteStakeholderUseCase = Depends(get_delete_use_case),
) -> None:
    await delete_use_case.execute(stakeholder_id=stakeholder_id)
    return None


def _to_response(stakeholder: Stakeholder) -> StakeholderResponseOut:
    metadata = stakeholder.stakeholder_metadata or {}
    return StakeholderResponseOut(
        id=stakeholder.id,
        project_id=stakeholder.project_id,
        name=stakeholder.name,
        role=stakeholder.role,
        company=stakeholder.organization,
        department=stakeholder.department,
        email=stakeholder.email,
        phone=stakeholder.phone,
        power_level=stakeholder.power_level,
        interest_level=stakeholder.interest_level,
        quadrant=stakeholder.quadrant,
        source_clause_id=stakeholder.source_clause_id,
        power_score=score_from_metadata(metadata, "power_score", stakeholder.power_level),
        interest_score=score_from_metadata(metadata, "interest_score", stakeholder.interest_level),
    )
