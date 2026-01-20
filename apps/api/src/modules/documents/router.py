import os
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session, get_session_with_tenant
from src.core.security import (  # Assuming CurrentTenantId is also available
    CurrentUserId,
)
from src.modules.documents.models import Document, DocumentStatus, DocumentType
from src.modules.documents.schemas import (
    DocumentDetailResponse,
    DocumentQueuedResponse, # New response model
    DocumentResponse,
    DocumentUploadResponse,
    UploadFileResponse,
)
from src.modules.documents.service import DocumentService
from src.modules.projects.models import Project
from src.shared.storage import StorageService
from src.config import settings
import pathlib

logger = structlog.get_logger()

router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
    },
)

# Allowed MIME types for validation
ALLOWED_MIME_TYPES = {
    ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".bc3": "text/plain", # BC3 is a plain text format
    ".xer": "text/plain", # Primavera P6 XER are often text/xml or text/plain
    ".mpp": "application/vnd.ms-project",
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
    if file_extension not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '{file_extension}' is not allowed."
        )

    # Check MIME type using python-magic
    file_content = await file.read()
    await file.seek(0) # Reset file pointer after reading
    
    import magic
    detected_mime = magic.from_buffer(file_content, mime=True)
    if detected_mime != ALLOWED_MIME_TYPES[file_extension]:
         # Be a bit lenient for text-based formats
        if not (file_extension in [".bc3", ".xer"] and "text" in detected_mime):
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file format. Expected {ALLOWED_MIME_TYPES[file_extension]}, but got {detected_mime}."
            )

    # 2. Check if project exists and user has access (implicitly done by service)
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # 3. Create document record in DB with QUEUED status
    try:
        new_document = await document_service.create_document_record(
            project_id=project_id,
            filename=file.filename,
            file_size=file.size,
            file_format=file_extension,
            document_type=document_type,
            user_id=user_id,
            status="QUEUED"
        )
    except Exception as e:
        logger.error("document_db_creation_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create document record.")

    # 4. Save file to storage
    try:
        # Use the new document's ID as the unique name to avoid collisions
        storage_path = await document_service.storage_service.upload_file(
            file_content=file.file, file_id=new_document.id, file_extension=file_extension
        )
        # Update record with final storage path
        await document_service.update_storage_path(document_id=new_document.id, path=storage_path)
    except Exception as e:
        logger.error("document_storage_failed", error=str(e))
        await document_service.update_status(document_id=new_document.id, status="ERROR")
        raise HTTPException(status_code=500, detail="Failed to save document to storage.")

    # 5. Dispatch Celery task (lazy import to avoid heavy deps at startup)
    from src.tasks.ingestion_tasks import process_document_async
    task = process_document_async.delay(document_id=new_document.id)
    logger.info("document_processing_queued", document_id=str(new_document.id), task_id=task.id)

    # 6. Return 202 Accepted response
    # We need to manually construct the response as Pydantic can't validate the hybrid model
    response_data = DocumentResponse.model_validate(new_document).model_dump()
    response_data['task_id'] = task.id
    
    return DocumentQueuedResponse(**response_data)


@router.get(
    "/{document_id}",
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
    "/{document_id}/download",
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


@router.delete(
    "/{document_id}",
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


# Endpoint to list documents for a project (needed for UI)
@router.get(
    "/projects/{project_id}",
    response_model=list[DocumentResponse],
    summary="List documents for a project",
    description="Retrieves a list of all documents associated with a specific project.",
)
async def list_documents_for_project(
    project_id: UUID,
    user_id: CurrentUserId,  # Ensure user is authenticated
    db: AsyncSession = Depends(get_session),
):
    try:
        # Use get_session_with_tenant to ensure RLS and fetch documents
        project_result = await db.execute(select(Project).where(Project.id == project_id))
        project = project_result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

        async with get_session_with_tenant(project.tenant_id) as tenant_db:
            documents_result = await tenant_db.execute(
                select(Document).where(Document.project_id == project_id)
            )
            documents = documents_result.scalars().all()
            logger.info(
                "documents_listed",
                project_id=str(project_id),
                user_id=str(user_id),
                count=len(documents),
            )
            return [DocumentResponse.model_validate(doc) for doc in documents]
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
