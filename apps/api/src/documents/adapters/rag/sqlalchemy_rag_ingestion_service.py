"""
SqlAlchemy implementation of the IRagIngestionService port.
Uses RagService to split, embed, and store document chunks.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.documents.adapters.rag.rag_service import RagService
from src.documents.domain.models import Document
from src.documents.ports.rag_ingestion_service import IRagIngestionService

logger = structlog.get_logger()


class SqlAlchemyRagIngestionService(IRagIngestionService):
    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session
        self._rag_service = RagService(db_session)

    async def ingest_document_chunks(
        self,
        document: Document,
        parsed_payload: dict[str, Any],
        tenant_id: UUID,
    ) -> None:
        text_content = _extract_rag_text(parsed_payload).strip()
        if not text_content:
            return

        try:
            ingested = await self._rag_service.ingest_document(
                tenant_id=tenant_id,
                document_id=document.id,
                project_id=document.project_id,
                text_content=text_content,
                metadata={"document_type": document.document_type.value},
            )
            logger.info(
                "rag_ingest_completed",
                document_id=str(document.id),
                chunks=ingested,
                tenant_id=str(tenant_id),
            )
        except Exception as exc:
            logger.warning(
                "rag_ingest_failed",
                document_id=str(document.id),
                error=str(exc),
                tenant_id=str(tenant_id),
            )


def _extract_rag_text(parsed_payload: dict[str, Any]) -> str:
    """TS-UD-RAG-ERR-001: normalize parsed document payloads into searchable RAG text."""
    text_blocks = parsed_payload.get("text_blocks", [])
    if text_blocks:
        return "\n\n".join(
            block.get("text", "")
            for block in text_blocks
            if isinstance(block.get("text"), str)
        )

    clauses = parsed_payload.get("clauses", [])
    if clauses:
        return "\n\n".join(
            _format_clause_for_rag(clause)
            for clause in clauses
            if isinstance(clause, dict)
        )

    schedule_rows = parsed_payload.get("schedule", [])
    if schedule_rows:
        return "\n".join(
            _format_schedule_row_for_rag(row)
            for row in schedule_rows
            if isinstance(row, dict)
        )

    for key in ("full_text", "text", "raw_text"):
        value = parsed_payload.get(key)
        if isinstance(value, str):
            return value

    return ""


def _format_clause_for_rag(clause: dict[str, Any]) -> str:
    parts = []
    labels = {
        "clause_number": "Clause",
        "number": "Clause",
        "code": "Clause",
        "title": "Title",
        "heading": "Title",
        "page": "Page",
        "text": "Text",
        "content": "Text",
        "clause_text": "Text",
    }
    seen_labels = set()
    for key, label in labels.items():
        if label in seen_labels:
            continue
        value = clause.get(key)
        if value not in (None, ""):
            parts.append(f"{label}: {value}")
            seen_labels.add(label)
    return "; ".join(parts)


def _format_schedule_row_for_rag(row: dict[str, Any]) -> str:
    parts = []
    labels = {
        "wbs": "WBS",
        "task": "Task",
        "start_date": "Start",
        "end_date": "End",
        "duration": "Duration",
        "predecessors": "Predecessors",
    }
    for key, label in labels.items():
        value = row.get(key)
        if value not in (None, ""):
            parts.append(f"{label}: {value}")
    return "; ".join(parts)
