from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.projects.adapters.persistence.project_repository import SQLAlchemyProjectRepository
from src.projects.ports.project_repository import ProjectRepository


def get_project_repository(
    db: AsyncSession = Depends(get_session),
) -> ProjectRepository:
    return SQLAlchemyProjectRepository(session=db)
