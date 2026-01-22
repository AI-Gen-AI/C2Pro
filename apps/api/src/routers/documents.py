from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum
import datetime

# --- Enums ---
class DocumentStatus(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

# --- Pydantic Models ---

class DocumentBase(BaseModel):
    filename: str
    size: int
    status: DocumentStatus
    error_message: Optional[str] = None

class DocumentRead(DocumentBase):
    id: int
    project_id: int
    created_at: datetime.datetime

    class Config:
        orm_mode = True

# --- API Router ---
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
import os
import shutil
# from .. import models
# from ..core.db import get_db
# from ..core.security import get_current_active_user
# from ..tasks.ingestion_tasks import process_document_async

# --- Placeholders ---
class Document:
    pass
def get_db():
    pass
def get_current_active_user():
    pass
def user_can_read_project(user, project_id):
    return True
def process_document_async():
    class DummyTask:
        def delay(self, *args, **kwargs):
            pass
    return DummyTask()

UPLOAD_DIR = "/tmp/uploads"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = {".pdf", ".xlsx", ".bc3"}

router = APIRouter(
    prefix="/documents",
    tags=["documents"],
    responses={404: {"description": "Not found"}},
)

@router.post("/projects/{project_id}/documents", response_model=DocumentRead, status_code=202)
async def upload_document(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    # current_user: models.User = Depends(get_current_active_user),
):
    """
    Upload a document for processing.
    """
    # Security: Check if user has access to the project
    # if not user_can_write_to_project(current_user, project_id):
    #     raise HTTPException(status_code=403, detail="Not authorized to upload to this project")

    # Validate file
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File extension '{file_ext}' not allowed.")

    # Note: file.file is a file-like object. To get the size, we need to seek.
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File size exceeds the 50MB limit.")

    # Save file to a temporary location
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, f"{project_id}_{file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Create document record in DB
    db_document = Document(
        project_id=project_id,
        filename=file.filename,
        size=file_size,
        status=DocumentStatus.QUEUED,
        file_path=file_path
    )
    db.add(db_document)
    db.commit()
    db.refresh(db_document)

    # Trigger async processing
    process_document_async.delay(db_document.id)

    return db_document

@router.get("/projects/{project_id}/documents", response_model=List[DocumentRead])
async def list_documents_for_project(
    project_id: int,
    db: Session = Depends(get_db),
    # current_user: models.User = Depends(get_current_active_user),
):
    """
    List all documents for a specific project.
    This endpoint is used by the frontend for polling the status of uploads.
    """
    # Security: Check if user has access to the project
    # if not user_can_read_project(current_user, project_id):
    #     raise HTTPException(status_code=403, detail="Not authorized to view documents for this project")

    documents = (
        db.query(Document)
        .filter(Document.project_id == project_id)
        .order_by(Document.created_at.desc())
        .all()
    )
    return documents

@router.get("/documents/{document_id}")
async def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    # current_user: models.User = Depends(get_current_active_user),
):
    """
    Get a single document's details or download it.
    (Optional: could return a signed URL for S3)
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Security: Check if user has access to the project this document belongs to
    # if not user_can_read_project(current_user, document.project_id):
    #     raise HTTPException(status_code=403, detail="Not authorized to access this document")

    # For local storage, return a FileResponse
    if not os.path.exists(document.file_path):
        raise HTTPException(status_code=404, detail="File not found on server.")

    from fastapi.responses import FileResponse
    return FileResponse(document.file_path, filename=document.filename)

@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    # current_user: models.User = Depends(get_current_active_user),
):
    """
    Delete a document.
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Security: Check if user has write access to the project
    # if not user_can_write_to_project(current_user, document.project_id):
    #     raise HTTPException(status_code=403, detail="Not authorized to delete this document")

    # (Optional) Advanced: Attempt to revoke a running Celery task
    if document.status in [DocumentStatus.QUEUED, DocumentStatus.PROCESSING]:
        # from celery.app.control import Control
        # from your_celery_app import app as celery_app
        # celery_app.control.revoke(task_id_associated_with_document, terminate=True)
        pass # Placeholder for task revocation logic

    # Delete the physical file
    if os.path.exists(document.file_path):
        os.remove(document.file_path)

    # Delete the database record
    db.delete(document)
    db.commit()

    return
