"""S4: read ONE original Budget/Schedule row an alert or evidence points at (tenant-scoped, hash- and authority-checked)."""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.application.structured_source_row_view import (
    ImmutableStructuredRowFinder,
    ResolveStructuredSourceRowService,
)
from src.analysis.application.structured_source_trust import StructuredTrustError
from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
from src.core.database import get_session_with_tenant
from src.core.tenants.types import require_tenant_id
from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser
from src.documents.adapters.storage.factory import build_storage_service

router = APIRouter(tags=["Structured source rows"])


class StructuredSourceRowResponse(BaseModel):
    family: Literal["budget", "schedule"]
    document_id: UUID
    revision_id: UUID
    rev_no: int
    source_locator: str
    blob_sha256: str
    authority: Literal["TRUSTED_CURRENT", "UNTRUSTED_SINGLE_REVISION"]
    row: dict[str, Any]
    source_assessment: Literal["NOT_ASSESSED"] = "NOT_ASSESSED"


async def get_structured_row_session(
    current_user: User = Depends(get_current_user),
) -> AsyncIterator[AsyncSession]:
    async with get_session_with_tenant(require_tenant_id(current_user.tenant_id)) as session:
        yield session


def _finder() -> ImmutableStructuredRowFinder:
    return ImmutableStructuredRowFinder(storage=build_storage_service(), parser=ExcelFileParser())


@router.get(
    "/documents/{document_id}/revisions/{revision_id}/structured-source-rows",
    response_model=StructuredSourceRowResponse,
    responses={
        401: {"description": "Authentication required"},
        404: {"description": "Unknown document/revision, or one of another tenant"},
        409: {"description": "Stale reference (other bytes or not the current revision) or unreadable original"},
    },
    summary="Read the exact original Budget row / Schedule activity a reference names",
)
async def read_structured_source_row(
    document_id: UUID,
    revision_id: UUID,
    locator: str = Query(min_length=1, max_length=500),
    expected_blob_hash: str | None = Query(default=None, pattern=r"^[0-9a-f]{64}$"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_structured_row_session),
) -> StructuredSourceRowResponse:
    try:
        view = await ResolveStructuredSourceRowService(session, _finder()).execute(
            tenant_id=require_tenant_id(current_user.tenant_id),
            document_id=document_id,
            revision_id=revision_id,
            source_locator=locator,
            expected_blob_hash=expected_blob_hash,
        )
    except StructuredTrustError as exc:
        raise HTTPException(status_code=exc.status, detail={"code": exc.code, "message": str(exc)}) from exc
    return StructuredSourceRowResponse(
        family=view.family,
        document_id=view.document_id,
        revision_id=view.revision_id,
        rev_no=view.rev_no,
        source_locator=view.source_locator,
        blob_sha256=view.blob_sha256,
        authority=view.authority,
        row=view.row,
    )


__all__ = ["StructuredSourceRowResponse", "router"]
