import os

# LEGACY: replaced by src.documents.adapters.http.router; kept for reference during migration.
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session, get_session_with_tenant
from src.core.security import CurrentTenantId, CurrentUserId
from src.modules.documents.models import Document, DocumentStatus, DocumentType
from src.modules.documents.schemas import (
    DocumentDetailResponse,
    DocumentQueuedResponse,
    DocumentResponse,
    DocumentUploadResponse,
    RagAnswerResponse,
    RagQuestionRequest,
    UploadFileResponse,
    DocumentListResponse,
    DocumentListItem,
    DocumentPollingStatus,
)
from src.modules.documents.service import DocumentService

from src.modules.projects.service import ProjectService
from src.services.rag_service import RagService
from src.shared.storage import StorageService
from src.config import settings
import pathlib

logger = structlog.get_logger()

router = APIRouter(
    prefix="",
    tags=["Documents"],
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
    },
)

# Allowed extensions for validation (CE-S4-010)
ALLOWED_EXTENSIONS = {
    ".pdf",
    ".xlsx",
    ".bc3",
}


# Dependency for DocumentService
async def get_document_service(
    db: AsyncSession = Depends(get_session),
    storage_service: StorageService = Depends(StorageService),
) -> DocumentService:
    return DocumentService(db_session=db, storage_service=storage_service)


@router.post(
    "/projects/{project_id}/documents",
    response_model=DocumentQueuedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a document for asynchronous processing",
    description="""
    Accepts a document, validates it, saves it to storage, and queues it for
    background processing. Responds immediately with a task ID.
    """,
)
async def upload_document_for_processing(
    project_id: UUID,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    document_type: DocumentType = Form(...),
    file: UploadFile = File(...),
    document_service: DocumentService = Depends(get_document_service),
    db: AsyncSession = Depends(get_session),
):
    """
    Handles the asynchronous upload and queuing of a document.
    """
    # 1. Validation
    # Check file size
    if file.size > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds limit of {settings.max_upload_size_mb}MB."
        )
    
    # Check file extension
    file_extension = pathlib.Path(file.filename).suffix.lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '{file_extension}' is not allowed."
        )

    # 2. Check if project exists and user has access
    await ProjectService.get_project(db=db, project_id=project_id, tenant_id=tenant_id)

    # 3. Create document record in DB with QUEUED status
    new_document = Document(
        project_id=project_id,
        document_type=document_type,
        filename=file.filename,
        file_format=file_extension,
        file_size_bytes=file.size,
        upload_status=DocumentStatus.UPLOADED,
        created_by=user_id,
    )
    db.add(new_document)
    await db.flush()

    # 4. Save file to storage
    try:
        # Use the new document's ID as the unique name to avoid collisions
        storage_path = await document_service.storage_service.upload_file(
            file_content=file.file, file_id=new_document.id, file_extension=file_extension
        )
        # Update record with final storage path
        new_document.storage_url = storage_path
        await db.commit()
        await db.refresh(new_document)
    except Exception as e:
        logger.error("document_storage_failed", error=str(e))
        new_document.upload_status = DocumentStatus.ERROR
        new_document.parsing_error = "Failed to save document to storage."
        await db.commit()
        raise HTTPException(status_code=500, detail="Failed to save document to storage.")

    # 5. Dispatch Celery task (lazy import to avoid heavy deps at startup)
    from src.tasks.ingestion_tasks import process_document_async
    task = process_document_async.delay(document_id=new_document.id)
    logger.info("document_processing_queued", document_id=str(new_document.id), task_id=task.id)

    # 6. Return 202 Accepted response
    response_data = DocumentResponse.model_validate(new_document).model_dump()
    response_data['task_id'] = task.id
    
    return DocumentQueuedResponse(**response_data)


@router.get(
    "/documents/{document_id}",
    response_model=DocumentDetailResponse,
    summary="Get document details by ID",
    description="Retrieves metadata and clauses for a specific document.",
)
async def get_document_endpoint(
    document_id: UUID,
    user_id: CurrentUserId,  # Ensure user is authenticated
    document_service: DocumentService = Depends(get_document_service),
    db: AsyncSession = Depends(get_session),  # Needed to explicitly load relationships
):
    try:
        # Use get_session_with_tenant for explicit RLS when fetching for current user
        # However, DocumentService.get_document already checks implicitly via project.tenant_id
        # when a tenant_id was passed. If not, the current tenant is set by middleware.
        # So we can just call the service.
        document = await document_service.get_document(document_id, user_id)
        # Ensure clauses are loaded for DocumentDetailResponse
        # document = await db.scalar(select(Document).options(selectinload(Document.clauses)).where(Document.id == document_id))
        # This will be handled by from_attributes in Pydantic and selectinload in the service layer if needed.

        logger.info("document_retrieved", document_id=str(document_id), user_id=str(user_id))
        return DocumentDetailResponse.model_validate(document)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(
            "document_retrieve_error", document_id=str(document_id), error=str(e), exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve document: {e}",
        )


@router.get(
    "/documents/{document_id}/download",
    summary="Download document file by ID",
    description="Downloads the physical file content of a specific document.",
)
async def download_document_endpoint(
    document_id: UUID,
    user_id: CurrentUserId,  # Ensure user is authenticated
    document_service: DocumentService = Depends(get_document_service),
):
    try:
        file_path, media_type = await document_service.download_document(document_id, user_id)
        logger.info("document_downloaded", document_id=str(document_id), user_id=str(user_id))
        return FileResponse(
            path=file_path, filename=os.path.basename(file_path), media_type=media_type
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(
            "document_download_error", document_id=str(document_id), error=str(e), exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download document: {e}",
        )


@router.post(
    "/projects/{project_id}/rag/answer",
    response_model=RagAnswerResponse,
    summary="Ask a question about project documents (RAG)",
    description="Runs vector search over project documents and answers using the retrieved context.",
)
async def answer_project_question(
    project_id: UUID,
    payload: RagQuestionRequest,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_session),
):
    await ProjectService.get_project(db=db, project_id=project_id, tenant_id=tenant_id)
    rag_service = RagService(db)
    result = await rag_service.answer_question(
        question=payload.question,
        project_id=project_id,
        top_k=payload.top_k or 5,
    )
    return RagAnswerResponse(
        answer=result.answer,
        sources=[
            {
                "content": chunk.content,
                "metadata": chunk.metadata,
                "similarity": chunk.similarity,
            }
            for chunk in result.sources
        ],
    )


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document by ID",
    description="Deletes a document record and its associated file from storage.",
)
async def delete_document_endpoint(
    document_id: UUID,
    user_id: CurrentUserId,  # Ensure user is authenticated
    document_service: DocumentService = Depends(get_document_service),
):
    try:
        await document_service.delete_document(document_id, user_id)
        logger.info("document_deleted", document_id=str(document_id), user_id=str(user_id))
        return status.HTTP_204_NO_CONTENT
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(
            "document_delete_error", document_id=str(document_id), error=str(e), exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {e}",
        )


@router.get(
    "/projects/{project_id}/documents",
    response_model=DocumentListResponse,
    summary="List documents for a project",
    description="Retrieves document metadata for polling upload status.",
)
async def list_documents_for_project(
    project_id: UUID,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_session),
    skip: int = Query(default=0, ge=0, description="Number of documents to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum number of documents to return"),
    document_service: DocumentService = Depends(get_document_service),
):
    try:
        documents, total_count = await document_service.list_project_documents(
            project_id=project_id, tenant_id=tenant_id, skip=skip, limit=limit
        )

        logger.info(
            "documents_listed",
            project_id=str(project_id),
            user_id=str(user_id),
            count=len(documents),
            total_count=total_count,
            skip=skip,
            limit=limit,
        )
        return DocumentListResponse(
            items=documents,
            total_count=total_count,
            skip=skip,
            limit=limit,
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error("document_list_error", project_id=str(project_id), error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list documents for project: {e}",
        )


@router.post(
    "/{document_id}/parse",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Parse a document by ID",
    description="Parses the uploaded document and stores parsed metadata.",
)
async def parse_document_endpoint(
    document_id: UUID,
    user_id: CurrentUserId,
    document_service: DocumentService = Depends(get_document_service),
):
    try:
        await document_service.parse_document(document_id, user_id)
        logger.info("document_parsed", document_id=str(document_id), user_id=str(user_id))
        return DocumentUploadResponse(
            document_id=document_id,
            status=DocumentStatus.PARSED,
            message="Document parsed successfully",
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error("document_parse_error", document_id=str(document_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse document: {e}",
        )
