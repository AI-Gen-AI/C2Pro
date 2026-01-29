"""
Legacy RAG ingestion adapter.

Bridges the new Documents module port to existing RagService.
"""
from __future__ import annotations

from uuid import UUID

import structlog

from src.core.database import get_session_with_tenant
from src.documents.adapters.rag.rag_service import RagService

from src.documents.domain.models import Document
from src.documents.ports.rag_ingestion_service import IRagIngestionService

logger = structlog.get_logger()


class LegacyRagIngestionService(IRagIngestionService):
    async def ingest_document_chunks(
        self,
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
