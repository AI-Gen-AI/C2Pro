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
from src.modules.documents.models import Document, DocumentType
from src.modules.documents.schemas import (
    DocumentDetailResponse,
    DocumentResponse,
    UploadFileResponse,
)
from src.modules.documents.service import DocumentService
from src.modules.projects.models import Project
from src.shared.storage import StorageService  # Import StorageService

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


# Dependency for DocumentService
async def get_document_service(
    db: AsyncSession = Depends(get_session),
    storage_service: StorageService = Depends(StorageService),  # Inject StorageService
) -> DocumentService:
    return DocumentService(db_session=db, storage_service=storage_service)


@router.post(
    "/projects/{project_id}/upload",
    response_model=UploadFileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a new document for a project",
    description="""
    Uploads a new document file and creates its record for a specific project.
    Supports various document types and performs basic file validation.
    """,
)
async def upload_document_endpoint(
    project_id: UUID,
    user_id: CurrentUserId,  # Get user_id from auth token
    document_type: DocumentType = Form(..., description="Type of the document"),
    file: UploadFile = File(..., description="The document file to upload"),
    document_service: DocumentService = Depends(get_document_service),
):
    try:
        new_document = await document_service.upload_document(
            project_id=project_id,
            file=file,
            document_type=document_type,
            user_id=user_id,  # Pass user_id for created_by
        )
        logger.info(
            "document_uploaded",
            document_id=str(new_document.id),
            project_id=str(project_id),
            filename=new_document.filename,
            user_id=str(user_id),
        )
        return UploadFileResponse(
            filename=new_document.filename,
            message="Document uploaded successfully",
            document_id=new_document.id,
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(
            "document_upload_error",
            project_id=str(project_id),
            filename=file.filename,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {e}",
        )


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
