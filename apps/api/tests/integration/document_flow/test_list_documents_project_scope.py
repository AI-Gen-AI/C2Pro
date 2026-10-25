"""``GET /projects/{id}/documents`` answers 404 for a project the caller cannot see (ACC-01 S8).

REAL PostgreSQL, the REAL router handler, REAL repositories. An own project without documents is a
legitimate empty list (200); a project that does not exist and a project that belongs to ANOTHER
tenant are indistinguishable, neutral 404s -- never a 200 with an empty list, which would confirm the
project exists to a caller who has no business knowing.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.documents.adapters.http import router as documents_router
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.documents.application.list_project_documents_use_case import ListProjectDocumentsUseCase
from src.projects.adapters.persistence.project_repository import SQLAlchemyProjectRepository
from tests.integration.document_flow.test_contract_schedule_completion_flow import _project

pytestmark = pytest.mark.asyncio


async def _list(db: AsyncSession, user: Any, project_id: Any) -> Any:
    return await documents_router.list_documents_for_project(
        project_id=project_id,
        tenant_id=user.tenant_id,
        _user_id=user.id,
        skip=0,
        limit=20,
        list_use_case=ListProjectDocumentsUseCase(
            SqlAlchemyDocumentRepository(db), SQLAlchemyProjectRepository(db)
        ),
        pending_review_lookup=lambda *_: {},
    )


async def test_an_own_project_without_documents_is_an_empty_200(db: AsyncSession, test_user: Any) -> None:
    project_id = await _project(db, test_user.tenant_id)

    listed = await _list(db, test_user, project_id)

    assert listed.items == [] and listed.total_count == 0


async def test_a_project_that_does_not_exist_is_a_404(db: AsyncSession, test_user: Any) -> None:
    with pytest.raises(HTTPException) as denied:
        await _list(db, test_user, uuid4())

    assert denied.value.status_code == 404


async def test_another_tenants_project_is_the_same_neutral_404(db: AsyncSession, test_user: Any) -> None:
    foreign_project = await _project(db, uuid4())  # a different tenant owns it
    with pytest.raises(HTTPException) as foreign:
        await _list(db, test_user, foreign_project)
    with pytest.raises(HTTPException) as missing:
        await _list(db, test_user, uuid4())

    assert foreign.value.status_code == 404
    assert foreign.value.detail == missing.value.detail, "foreign and missing must be indistinguishable"
