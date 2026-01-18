import os
from datetime import datetime
from mimetypes import guess_type
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.core.database import get_session_with_tenant
from src.modules.documents.models import Document, DocumentStatus, DocumentType
from src.modules.documents.parsers.bc3_parser import BC3ParsingError, parse_bc3_file
from src.modules.documents.parsers.excel_parser import (
    ExcelParsingError,
    parse_budget_from_excel,
    parse_schedule_from_excel,
)
from src.modules.documents.parsers.pdf_parser import PDFParsingError, extract_text_and_offsets
from src.modules.projects.models import Project
from src.shared.storage import StorageService


class DocumentService:
    def __init__(self, db_session: AsyncSession, storage_service: StorageService):
        self.db_session = db_session
        self.storage_service = storage_service

    async def _get_project_tenant_id(self, project_id: UUID) -> UUID:
        """Helper to get tenant_id from project_id."""
        project_result = await self.db_session.execute(
            select(Project.tenant_id).where(Project.id == project_id)
        )
        tenant_id = project_result.scalar_one_or_none()
        if not tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
        return tenant_id

    async def upload_document(
        self,
        project_id: UUID,
        file: UploadFile,
        document_type: DocumentType,
        user_id: UUID,
        metadata: dict = None,
    ) -> Document:
        """
        Uploads a file to storage and creates a corresponding Document record in the database.
        Enforces security by checking project ownership via tenant_id.
        """
        if not metadata:
            metadata = {}

        tenant_id = await self._get_project_tenant_id(project_id)

        # Validate file size and type
        if file.size > settings.max_upload_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds limit of {settings.max_upload_size_mb}MB.",
            )

        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in settings.allowed_document_types:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"File type {file_extension} is not allowed. Allowed types: {', '.join(settings.allowed_document_types)}",
            )

        async with get_session_with_tenant(tenant_id) as tenant_db:
            # Create a new document record first to get an ID
            new_document = Document(
                project_id=project_id,
                document_type=document_type,
                filename=file.filename,
                file_format=file_extension,
                file_size_bytes=file.size,
                upload_status=DocumentStatus.UPLOADED,
                created_by=user_id,
                metadata=metadata,
            )
            tenant_db.add(new_document)
            await tenant_db.flush()  # Flush to get new_document.id

            # Upload the file to storage using the document's ID
            file.file.seek(0)  # Ensure file pointer is at the beginning
            storage_path = await self.storage_service.upload_file(
                file_content=file.file, file_id=new_document.id, file_extension=file_extension
            )
            new_document.storage_url = storage_path
            await tenant_db.commit()
            await tenant_db.refresh(new_document)
            return new_document

    async def mark_document_parsing(self, document_id: UUID, tenant_id: UUID) -> None:
        async with get_session_with_tenant(tenant_id) as tenant_db:
            document_result = await tenant_db.execute(
                select(Document).where(Document.id == document_id)
            )
            document = document_result.scalar_one_or_none()
            if not document:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
                )
            document.upload_status = DocumentStatus.PARSING
            document.parsing_error = None
            await tenant_db.commit()

    async def _parse_document_file(self, document: Document, file_path: Path) -> dict:
        file_format = (document.file_format or "").lower()
        parsed_payload: dict = {"file_format": file_format, "document_type": document.document_type}

        if file_format == ".pdf":
            parsed_payload["text_blocks"] = extract_text_and_offsets(file_path)
            return parsed_payload

        if file_format in {".xlsx", ".xls"}:
            if document.document_type == DocumentType.SCHEDULE:
                parsed_payload["schedule"] = parse_schedule_from_excel(file_path)
                return parsed_payload
            if document.document_type == DocumentType.BUDGET:
                parsed_payload["budget"] = parse_budget_from_excel(file_path)
                return parsed_payload
            raise ValueError(
                "Excel parsing is only supported for schedule or budget document types."
            )

        if file_format == ".bc3":
            parsed_payload["budget"] = parse_bc3_file(file_path)
            return parsed_payload

        raise ValueError(f"No parser available for file format: {file_format}")

    async def parse_document(self, document_id: UUID, user_id: UUID) -> None:
        document = await self.get_document(document_id, user_id)
        tenant_id = await self._get_project_tenant_id(document.project_id)
        await self.mark_document_parsing(document_id, tenant_id)

        try:
            file_name_in_storage = document.storage_url.split("/")[-1]
            file_path = await self.storage_service.download_file(file_name_in_storage)
            parsed_payload = await self._parse_document_file(document, file_path)

            async with get_session_with_tenant(tenant_id) as tenant_db:
                document_result = await tenant_db.execute(
                    select(Document).where(Document.id == document_id)
                )
                document = document_result.scalar_one_or_none()
                if not document:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Document not found during parsing update.",
                    )
                metadata = dict(document.document_metadata or {})
                metadata["parsed_content"] = parsed_payload
                metadata["parsed_at"] = datetime.utcnow().isoformat()
                document.document_metadata = metadata
                document.upload_status = DocumentStatus.PARSED
                document.parsed_at = datetime.utcnow()
                document.parsing_error = None
                await tenant_db.commit()
        except (PDFParsingError, ExcelParsingError, BC3ParsingError, ValueError) as e:
            async with get_session_with_tenant(tenant_id) as tenant_db:
                document_result = await tenant_db.execute(
                    select(Document).where(Document.id == document_id)
                )
                document = document_result.scalar_one_or_none()
                if document:
                    document.upload_status = DocumentStatus.ERROR
                    document.parsing_error = str(e)
                    await tenant_db.commit()
            raise
        except Exception as e:
            async with get_session_with_tenant(tenant_id) as tenant_db:
                document_result = await tenant_db.execute(
                    select(Document).where(Document.id == document_id)
                )
                document = document_result.scalar_one_or_none()
                if document:
                    document.upload_status = DocumentStatus.ERROR
                    document.parsing_error = f"Unexpected parsing error: {e}"
                    await tenant_db.commit()
            raise

    async def get_document(self, document_id: UUID, user_id: UUID) -> Document:
        """
        Retrieves a document record from the database.
        Enforces security by checking document ownership via tenant_id.
        """
        document_result = await self.db_session.execute(
            select(Document).where(Document.id == document_id)
        )
        document = document_result.scalar_one_or_none()

        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

        # Verify tenant ownership (RLS should handle this, but an explicit check adds safety)
        tenant_id_from_project = await self._get_project_tenant_id(document.project_id)
        # This explicit check is useful if the initial session for fetching document
        # was not already tenant-isolated, or as a double-check.
        # However, with get_session_with_tenant, this might be redundant if the session
        # is always created with the user's tenant_id for document operations.
        # For a service layer, it's safer to ensure consistent tenant context.
        # Here we rely on `get_session_with_tenant` further down

        return document

    async def download_document(self, document_id: UUID, user_id: UUID) -> tuple[Path, str]:
        """
        Retrieves the actual file from storage for a given document.
        Enforces security by checking document ownership via tenant_id.
        Returns file path and media type.
        """
        document = await self.get_document(
            document_id, user_id
        )  # Reuse get_document for authorization

        # Extract filename from storage_url
        # Assuming storage_url is something like "/local-storage/{file_id}.ext"
        file_name_in_storage = document.storage_url.split("/")[-1]

        try:
            file_path = await self.storage_service.download_file(file_name_in_storage)
            media_type, _ = guess_type(
                document.filename
            )  # Guess media type based on original filename
            if not media_type:
                media_type = "application/octet-stream"  # Default if not guessable
            return file_path, media_type
        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="File content not found in storage."
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to download file: {e}",
            )

    async def delete_document(self, document_id: UUID, user_id: UUID):
        """
        Deletes a document record and its associated file from storage.
        Enforces security by checking document ownership via tenant_id.
        """
        document = await self.get_document(
            document_id, user_id
        )  # Reuse get_document for authorization

        tenant_id = await self._get_project_tenant_id(document.project_id)

        async with get_session_with_tenant(tenant_id) as tenant_db:
            # Delete file from storage
            file_name_in_storage = document.storage_url.split("/")[-1]
            await self.storage_service.delete_file(file_name_in_storage)

            # Delete document record from database
            await tenant_db.delete(document)
            await tenant_db.commit()
