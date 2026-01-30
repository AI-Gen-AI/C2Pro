from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.documents.ports.document_repository import IDocumentRepository
from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository
from src.procurement.ports.wbs_repository import IWBSRepository
from src.projects.adapters.persistence.project_repository import SQLAlchemyProjectRepository
from src.projects.ports.project_repository import ProjectRepository


def get_document_repository(
    db: AsyncSession = Depends(get_session),
) -> IDocumentRepository:
    return SqlAlchemyDocumentRepository(session=db)


def get_wbs_repository(
    db: AsyncSession = Depends(get_session),
) -> IWBSRepository:
    return SQLAlchemyWBSRepository(session=db)


def get_project_repository(
    db: AsyncSession = Depends(get_session),
) -> ProjectRepository:
    return SQLAlchemyProjectRepository(session=db)
