import os

# LEGACY: replaced by use cases in src.documents; kept for reference during migration.
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from mimetypes import guess_type
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.config import settings
from src.core.database import get_session_with_tenant
from src.modules.documents.models import Document, DocumentStatus, DocumentType
from src.modules.documents.schemas import DocumentListItem, DocumentPollingStatus
from src.modules.documents.parsers.bc3_parser import BC3ParsingError, parse_bc3_file
from src.modules.documents.parsers.excel_parser import (
    ExcelParsingError,
    parse_budget_from_excel,
    parse_schedule_from_excel,
)
from src.modules.documents.parsers.pdf_parser import PDFParsingError, extract_text_and_offsets
from src.modules.projects.models import Project
from src.modules.stakeholders.models import BOMItem, Stakeholder, WBSItem, WBSItemType
from src.services.rag_service import RagService
from src.services.stakeholder_classifier import StakeholderClassifier, StakeholderInput
from src.shared.storage import StorageService

logger = structlog.get_logger()


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
                document_metadata=metadata,
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

    def _parse_datetime_value(self, value: object) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

    def _parse_decimal(self, value: object) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    def _normalize_name_from_email(self, email: str) -> str:
        local_part = email.split("@")[0]
        cleaned = re.sub(r"[._-]+", " ", local_part).strip()
        return cleaned.title() if cleaned else email

    async def _parse_document_file(self, document: Document, file_path: Path) -> dict:
        file_format = (document.file_format or "").lower()
        parsed_payload: dict = {
            "file_format": file_format,
            "document_type": document.document_type.value,
        }

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

    async def _extract_entities(
        self, document: Document, parsed_payload: dict, tenant_id: UUID
    ) -> dict[str, int]:
        extraction_summary = {"stakeholders": 0, "wbs_items": 0, "bom_items": 0}

        async with get_session_with_tenant(tenant_id) as tenant_db:
            if document.document_type == DocumentType.CONTRACT:
                text_blocks = parsed_payload.get("text_blocks", [])
                emails = set()
                new_stakeholders: list[Stakeholder] = []
                stakeholder_inputs: list[StakeholderInput] = []
                for block in text_blocks:
                    text = block.get("text", "")
                    if not isinstance(text, str):
                        continue
                    for email in re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", text):
                        emails.add(email.lower())

                for email in emails:
                    existing = await tenant_db.scalar(
                        select(Stakeholder).where(
                            Stakeholder.project_id == document.project_id,
                            Stakeholder.email == email,
                        )
                    )
                    if existing:
                        continue
                    stakeholder = Stakeholder(
                        project_id=document.project_id,
                        name=self._normalize_name_from_email(email),
                        email=email,
                        extracted_from_document_id=document.id,
                        stakeholder_metadata={"source_document_id": str(document.id)},
                    )
                    tenant_db.add(stakeholder)
                    new_stakeholders.append(stakeholder)
                    stakeholder_inputs.append(
                        StakeholderInput(
                            name=stakeholder.name,
                            role=stakeholder.role,
                            company=stakeholder.organization,
                        )
                    )
                    extraction_summary["stakeholders"] += 1

                if new_stakeholders:
                    classifier = StakeholderClassifier(tenant_id=str(tenant_id))
                    try:
                        enriched = await classifier.classify_batch(
                            stakeholder_inputs,
                            contract_type=document.document_type.value,
                        )
                    except Exception as exc:
                        logger.warning("stakeholder_classification_failed", error=str(exc))
                    else:
                        for stakeholder, result in zip(new_stakeholders, enriched):
                            stakeholder.power_level = result.power_level
                            stakeholder.interest_level = result.interest_level
                            stakeholder.quadrant = result.quadrant_db
                            metadata = dict(stakeholder.stakeholder_metadata or {})
                            metadata["classification"] = {
                                "power_score": result.power_score,
                                "interest_score": result.interest_score,
                                "quadrant": result.quadrant.value,
                            }
                            stakeholder.stakeholder_metadata = metadata

            if document.document_type == DocumentType.SCHEDULE:
                for index, task in enumerate(parsed_payload.get("schedule", []), start=1):
                    task_name = task.get("task")
                    if not task_name:
                        continue
                    wbs_code = f"SCH-{index:03d}"
                    existing = await tenant_db.scalar(
                        select(WBSItem).where(
                            WBSItem.project_id == document.project_id,
                            WBSItem.wbs_code == wbs_code,
                        )
                    )
                    if existing:
                        continue
                    wbs_item = WBSItem(
                        project_id=document.project_id,
                        wbs_code=wbs_code,
                        name=str(task_name),
                        description=None,
                        level=1,
                        item_type=WBSItemType.ACTIVITY,
                        planned_start=self._parse_datetime_value(task.get("start_date")),
                        planned_end=self._parse_datetime_value(task.get("end_date")),
                        wbs_metadata={"source_document_id": str(document.id)},
                    )
                    tenant_db.add(wbs_item)
                    extraction_summary["wbs_items"] += 1

            if document.document_type == DocumentType.BUDGET:
                budget_payload = parsed_payload.get("budget")
                if isinstance(budget_payload, list):
                    for index, item in enumerate(budget_payload, start=1):
                        item_name = item.get("item")
                        quantity = self._parse_decimal(item.get("quantity"))
                        if not item_name or quantity is None:
                            continue
                        item_code = f"BUD-{index:04d}"
                        existing = await tenant_db.scalar(
                            select(BOMItem).where(
                                BOMItem.project_id == document.project_id,
                                BOMItem.item_name == item_name,
                                BOMItem.unit == item.get("unit"),
                            )
                        )
                        if existing:
                            continue
                        bom_item = BOMItem(
                            project_id=document.project_id,
                            item_code=item_code,
                            item_name=str(item_name),
                            quantity=quantity,
                            unit=item.get("unit"),
                            unit_price=self._parse_decimal(item.get("unit_price")),
                            total_price=self._parse_decimal(item.get("total")),
                            currency="EUR",
                            bom_metadata={"source_document_id": str(document.id)},
                        )
                        tenant_db.add(bom_item)
                        extraction_summary["bom_items"] += 1
                elif isinstance(budget_payload, dict):
                    for chapter in budget_payload.get("chapters", []):
                        for unit in chapter.get("units", []):
                            item_name = unit.get("description")
                            quantity = self._parse_decimal(unit.get("quantity"))
                            if not item_name or quantity is None:
                                continue
                            item_code = unit.get("code")
                            existing = await tenant_db.scalar(
                                select(BOMItem).where(
                                    BOMItem.project_id == document.project_id,
                                    BOMItem.item_name == item_name,
                                    BOMItem.unit == unit.get("unit"),
                                )
                            )
                            if existing:
                                continue
                            bom_item = BOMItem(
                                project_id=document.project_id,
                                item_code=item_code,
                                item_name=str(item_name),
                                quantity=quantity,
                                unit=unit.get("unit"),
                                unit_price=self._parse_decimal(unit.get("price")),
                                total_price=self._parse_decimal(unit.get("total")),
                                currency="EUR",
                                bom_metadata={
                                    "source_document_id": str(document.id),
                                    "chapter_code": chapter.get("code"),
                                },
                            )
                            tenant_db.add(bom_item)
                            extraction_summary["bom_items"] += 1

            if any(extraction_summary.values()):
                await tenant_db.commit()
            return extraction_summary

    async def parse_document(self, document_id: UUID, user_id: UUID) -> None:
        document = await self.get_document(document_id, user_id)
        tenant_id = await self._get_project_tenant_id(document.project_id)
        await self.mark_document_parsing(document_id, tenant_id)

        try:
            file_name_in_storage = document.storage_url.split("/")[-1]
            file_path = await self.storage_service.download_file(file_name_in_storage)
            parsed_payload = await self._parse_document_file(document, file_path)
            extraction_summary = await self._extract_entities(
                document=document,
                parsed_payload=parsed_payload,
                tenant_id=tenant_id,
            )

            await self._ingest_rag_chunks(
                document=document,
                parsed_payload=parsed_payload,
                tenant_id=tenant_id,
            )

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
                metadata["extraction_summary"] = extraction_summary
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

    async def _ingest_rag_chunks(
        self,
        *,
        document: Document,
        parsed_payload: dict,
        tenant_id: UUID,
    ) -> None:
        text_blocks = parsed_payload.get("text_blocks", [])
        if not text_blocks:
            return

        text_content = "\n\n".join(
            block.get("text", "") for block in text_blocks if isinstance(block.get("text"), str)
        ).strip()
        if not text_content:
            return

        async with get_session_with_tenant(tenant_id) as tenant_db:
            rag_service = RagService(tenant_db)
            try:
                ingested = await rag_service.ingest_document(
                    document_id=document.id,
                    project_id=document.project_id,
                    text_content=text_content,
                    metadata={"document_type": document.document_type.value},
                )
                logger.info(
                    "rag_ingest_completed",
                    document_id=str(document.id),
                    chunks=ingested,
                )
            except Exception as exc:
                logger.warning(
                    "rag_ingest_failed",
                    document_id=str(document.id),
                    error=str(exc),
                )

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

    async def create_and_queue_document(
        self,
        project_id: UUID,
        file: UploadFile,
        document_type: DocumentType,
        user_id: UUID,
    ) -> Document:
        """
        Creates a document record with QUEUED status.
        This is the first, synchronous step in the async processing workflow.
        """
        tenant_id = await self._get_project_tenant_id(project_id)
        
        async with get_session_with_tenant(tenant_id) as tenant_db:
            file_extension = os.path.splitext(file.filename)[1].lower()
            
            new_document = Document(
                project_id=project_id,
                document_type=document_type,
                filename=file.filename,
                file_format=file_extension,
                file_size_bytes=file.size,
                upload_status=DocumentStatus.QUEUED,
                created_by=user_id,
                tenant_id=tenant_id,
            )
            tenant_db.add(new_document)
            await tenant_db.commit()
            await tenant_db.refresh(new_document)
            
            return new_document

    async def update_storage_path(self, document_id: UUID, path: str):
        """Updates the storage_url for a document within the correct tenant context."""
        doc_result = await self.db_session.execute(select(Document.tenant_id).where(Document.id == document_id))
        tenant_id = doc_result.scalar_one_or_none()
        if not tenant_id:
            return

        async with get_session_with_tenant(tenant_id) as db:
            doc_to_update = await db.get(Document, document_id)
            if doc_to_update:
                doc_to_update.storage_url = path
                await db.commit()

    async def update_status(self, document_id: UUID, status: DocumentStatus):
        """Updates the status for a document within the correct tenant context."""
        doc_result = await self.db_session.execute(select(Document.tenant_id).where(Document.id == document_id))
        tenant_id = doc_result.scalar_one_or_none()
        if not tenant_id:
            return

        async with get_session_with_tenant(tenant_id) as db:
            doc_to_update = await db.get(Document, document_id)
            if doc_to_update:
                doc_to_update.upload_status = status
                await db.commit()

    async def create_and_queue_document(
        self,
        project_id: UUID,
        file: UploadFile,
        document_type: DocumentType,
        user_id: UUID,
    ) -> Document:
        """
        Creates a document record with QUEUED status and saves the file.
        This is the first step in the async processing workflow.
        """
        tenant_id = await self._get_project_tenant_id(project_id)
        
        async with get_session_with_tenant(tenant_id) as tenant_db:
            file_extension = os.path.splitext(file.filename)[1].lower()
            
            # Create a new document record with QUEUED status
            new_document = Document(
                project_id=project_id,
                document_type=document_type,
                filename=file.filename,
                file_format=file_extension,
                file_size_bytes=file.size,
                upload_status=DocumentStatus.QUEUED, # Start as QUEUED
                created_by=user_id,
                tenant_id=tenant_id,
            )
            tenant_db.add(new_document)
            await tenant_db.commit()
            await tenant_db.refresh(new_document)
            
            return new_document

    async def update_storage_path(self, document_id: UUID, path: str):
        """Updates the storage_url for a document."""
        # This requires a new session as it might be called from a different context
        async with get_session_with_tenant() as db:
            result = await db.execute(select(Document).where(Document.id == document_id))
            document = result.scalar_one_or_none()
            if document:
                document.storage_url = path
                await db.commit()

    async def update_status(self, document_id: UUID, status: DocumentStatus):
        """Updates the status for a document."""
        async with get_session_with_tenant() as db:
            result = await db.execute(select(Document).where(Document.id == document_id))
            document = result.scalar_one_or_none()
            if document:
                document.upload_status = status
                await db.commit()

    async def list_project_documents(
        self, project_id: UUID, tenant_id: UUID, skip: int = 0, limit: int = 20
    ) -> tuple[list[DocumentListItem], int]:
        """
        Lists documents for a specific project, with pagination and tenant isolation.
        """
        # 1. Verify project exists and belongs to the tenant
        # Use a subquery or directly join if Project is available,
        # otherwise fetch explicitly. For now, explicit fetch.
        project = await self.db_session.scalar(
            select(Project).where(Project.id == project_id, Project.tenant_id == tenant_id)
        )
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

        # 2. Build the base query for documents
        stmt = (
            select(
                Document.id,
                Document.filename,
                Document.upload_status,
                Document.parsing_error,
                Document.created_at,
                Document.file_size_bytes,
            )
            .where(Document.project_id == project_id)
            .order_by(Document.created_at.desc())
        )

        # 3. Get total count for pagination metadata
        count_stmt = select(func.count()).where(Document.project_id == project_id)
        total_count_result = await self.db_session.execute(count_stmt)
        total_count = total_count_result.scalar_one()

        # 4. Apply pagination
        stmt = stmt.offset(skip).limit(limit)

        # 5. Execute query and fetch results
        documents_result = await self.db_session.execute(stmt)
        document_rows = documents_result.all()

        # 6. Map results to DocumentListItem
        items: list[DocumentListItem] = []
        for row in document_rows:
            # Normalize status
            normalized_status = self._normalize_document_status_for_polling(row.upload_status)
            items.append(
                DocumentListItem(
                    id=row.id,
                    filename=row.filename,
                    status=normalized_status,
                    error_message=row.parsing_error if normalized_status == DocumentPollingStatus.ERROR else None,
                    uploaded_at=row.created_at,
                    file_size_bytes=row.file_size_bytes or 0,
                )
            )
        return items, total_count
    
    def _normalize_document_status_for_polling(self, document_status: DocumentStatus) -> DocumentPollingStatus:
        """
        Helper to map internal DocumentStatus to external DocumentPollingStatus.
        """
        if document_status == DocumentStatus.UPLOADED:
            return DocumentPollingStatus.QUEUED
        if document_status == DocumentStatus.PARSING:
            return DocumentPollingStatus.PROCESSING
        if document_status == DocumentStatus.PARSED:
            return DocumentPollingStatus.PARSED
        if document_status == DocumentStatus.ERROR:
            return DocumentPollingStatus.ERROR
        # Default to processing for any unhandled or intermediate statuses
        return DocumentPollingStatus.PROCESSING

