from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.documents.application.check_clause_exists_use_case import CheckClauseExistsUseCase
from src.documents.application.get_clause_text_map_use_case import GetClauseTextMapUseCase


def get_document_repository(
    db: AsyncSession = Depends(get_session),
) -> SqlAlchemyDocumentRepository:
    return SqlAlchemyDocumentRepository(session=db)


def get_clause_exists_use_case(
    repo: SqlAlchemyDocumentRepository = Depends(get_document_repository),
) -> CheckClauseExistsUseCase:
    return CheckClauseExistsUseCase(document_repository=repo)


def get_clause_text_map_use_case(
    repo: SqlAlchemyDocumentRepository = Depends(get_document_repository),
) -> GetClauseTextMapUseCase:
    return GetClauseTextMapUseCase(document_repository=repo)
