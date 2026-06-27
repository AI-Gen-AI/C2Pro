"""
Use Case for parsing a document, extracting entities, and ingesting for RAG.
"""
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import structlog
from fastapi import HTTPException, status

from src.documents.domain.models import DocumentStatus
from src.documents.ports.document_repository import IDocumentRepository
from src.documents.ports.entity_extraction_service import IEntityExtractionService
from src.documents.ports.file_parser_service import IFileParserService
from src.documents.ports.rag_ingestion_service import IRagIngestionService
from src.documents.ports.storage_service import IStorageService

logger = structlog.get_logger()


def _extract_parsed_text(parsed_payload: dict) -> str:
    """Extract readable text from parsed payload for analysis fallback.

    Mirrors the priority chain from _extract_rag_text in the RAG ingestion
    service, adding budget handling that was previously missing.
    """
    # Priority 1: PDF text blocks
    text_blocks = parsed_payload.get("text_blocks", [])
    if text_blocks:
        return "\n\n".join(
            block.get("text", "")
            for block in text_blocks
            if isinstance(block.get("text"), str)
        ).strip()

    # Priority 2: Legacy/extracted clauses
    clauses = parsed_payload.get("clauses", [])
    if clauses:
        parts: list[str] = []
        for clause in clauses:
            if not isinstance(clause, dict):
                continue
            title = clause.get("title", "")
            content = clause.get("content", clause.get("text", ""))
            if title and content:
                parts.append(f"{title}: {content}")
            elif content:
                parts.append(str(content))
        if parts:
            return "\n\n".join(parts).strip()

    # Priority 3: Schedule rows
    schedule_rows = parsed_payload.get("schedule", [])
    if schedule_rows:
        lines: list[str] = []
        for row in schedule_rows:
            if not isinstance(row, dict):
                continue
            desc = row.get("description", row.get("activity", row.get("task", "")))
            start = row.get("start_date", row.get("start", ""))
            end = row.get("end_date", row.get("end", ""))
            parts_row = [str(desc)]
            if start:
                parts_row.append(f"start: {start}")
            if end:
                parts_row.append(f"end: {end}")
            lines.append(" | ".join(parts_row))
        if lines:
            return "\n".join(lines).strip()

    # Priority 4: Budget chapters (Excel BUDGET / BC3)
    budget = parsed_payload.get("budget", {})
    if isinstance(budget, dict):
        budget_parts: list[str] = []
        header = budget.get("header", {})
        if isinstance(header, dict) and "project_name" in header:
            budget_parts.append(f"Project: {header['project_name']}")
        chapters = budget.get("chapters", [])
        for ch in chapters:
            if not isinstance(ch, dict):
                continue
            code = ch.get("code", ch.get("chapter_code", ""))
            description = ch.get("description", ch.get("name", ""))
            amount = ch.get("amount", ch.get("total", ""))
            line = f"  {code} {description}"
            if amount:
                line += f" — {amount}"
            budget_parts.append(line)
        if len(budget_parts) > 1:
            return "\n".join(budget_parts).strip()

    # Priority 5: Generic raw text keys
    for key in ("full_text", "text", "raw_text", "content"):
        value = parsed_payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def _extract_budget_stated_total(parsed_payload: dict) -> float | int | None:
    """TS-COH-BUD-RECON-004: extract budget declared total from parser payload."""
    budget = parsed_payload.get("budget")
    stated_total = getattr(budget, "stated_total", None)
    if isinstance(stated_total, int | float) and not isinstance(stated_total, bool):
        return stated_total
    if isinstance(budget, dict):
        dict_total = budget.get("stated_total")
        if isinstance(dict_total, int | float) and not isinstance(dict_total, bool):
            return dict_total
    return None


class ParseDocumentUseCase:
    def __init__(
        self,
        document_repository: IDocumentRepository,
        storage_service: IStorageService,
        file_parser_service: IFileParserService,
        entity_extraction_service: IEntityExtractionService,
        rag_ingestion_service: IRagIngestionService,
    ):
        self.document_repository = document_repository
        self.storage_service = storage_service
        self.file_parser_service = file_parser_service
        self.entity_extraction_service = entity_extraction_service
        self.rag_ingestion_service = rag_ingestion_service

    async def execute(self, tenant_id: UUID, document_id: UUID, user_id: UUID) -> None:  # noqa: ARG002 — user_id reserved for future audit/permissions
        # 1. Get document and ensure it exists
        document = await self.document_repository.get_by_id(tenant_id, document_id)
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found or access denied.")

        # 2. Mark document as PARSING
        await self.document_repository.update_status(tenant_id, document_id, DocumentStatus.PARSING)
        await self.document_repository.commit()

        try:
            # 3. Download the file
            # Assuming storage_url will be based on document.id and its extension
            # For now, we mimic the original service's logic: extract filename from what would be storage_url
            file_name_in_storage = f"{document.id}{Path(document.filename).suffix}" # Construct based on stored ID and original extension
            file_path = await self.storage_service.download_file(file_name_in_storage)

            # 4. Parse the document file
            parsed_payload = await self.file_parser_service.parse_document_file(document, file_path)

            # 5. Extract entities (Stakeholders, WBS, BOM)
            await self.entity_extraction_service.extract_entities_from_document(
                document=document,
                parsed_payload=parsed_payload,
                tenant_id=tenant_id,
            )

            # 6. Ingest for RAG
            await self.rag_ingestion_service.ingest_document_chunks(
                document=document,
                parsed_payload=parsed_payload,
                tenant_id=tenant_id,
            )

            # 7. Extract parsed_text and store in document_metadata
            # This enables the analysis endpoint to find and use the document text.
            parsed_text = _extract_parsed_text(parsed_payload)
            metadata = dict(document.document_metadata or {})
            if parsed_text:
                metadata["parsed_text"] = parsed_text
            stated_total = _extract_budget_stated_total(parsed_payload)
            if stated_total is not None:
                metadata["stated_total"] = stated_total
            await self.document_repository.update_metadata(tenant_id, document_id, metadata)

            # 8. Update document status to PARSED
            await self.document_repository.update_status(
                tenant_id,
                document_id,
                DocumentStatus.PARSED,
                parsing_error=None,
                parsed_at=datetime.now(UTC),
            )

            await self.document_repository.commit()

        except Exception as e:
            logger.error("document_parsing_failed", document_id=document_id, error=str(e))
            await self.document_repository.update_status(
                tenant_id, document_id, DocumentStatus.ERROR, parsing_error=str(e)
            )
            await self.document_repository.commit()
            raise # Re-raise to ensure error is propagated
