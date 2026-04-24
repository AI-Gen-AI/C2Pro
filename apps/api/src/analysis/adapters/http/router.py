from __future__ import annotations

import json
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.graph.orchestrator_adapter import WorkflowOrchestrator
from src.analysis.adapters.persistence.models import Analysis
from src.analysis.application.analyze_document_use_case import AnalyzeDocumentUseCase
from src.analysis.domain.enums import AnalysisStatus
from src.coherence.adapters.persistence.models import CoherenceResultORM
from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
from src.core.database import get_session
from src.documents.adapters.persistence.models import DocumentORM
from src.projects.adapters.persistence.models import ProjectORM

router = APIRouter(
    prefix="/analysis",
    tags=["analysis"],
    responses={404: {"description": "Not found"}},
)

PROCESSING_STAGE_TEMPLATE: list[dict[str, int | str]] = [
    {"stage": 1, "name": "Extracting text", "progress": 16},
    {"stage": 2, "name": "Identifying clauses", "progress": 33},
    {"stage": 3, "name": "Cross-referencing", "progress": 50},
    {"stage": 4, "name": "Detecting anomalies", "progress": 66},
    {"stage": 5, "name": "Calculating weights", "progress": 83},
]


def _sse_frame(event: str, data: dict[str, Any]) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()


def _build_completion_payload(
    *,
    document_count: int,
    global_score: int,
    completed_at: str | None,
) -> dict[str, Any]:
    return {
        "global_score": global_score,
        "documents_analyzed": document_count,
        "completed_at": completed_at,
        "analysis_status": AnalysisStatus.COMPLETED.value,
        "verification_stage": "analysis_completed",
        "proof_source": "analysis_and_coherence_persistence",
    }


async def _resolve_processing_summary(
    db: AsyncSession,
    project_id: UUID,
    tenant_id: UUID,
) -> tuple[int, int, str | None]:
    project_result = await db.execute(
        select(ProjectORM).where(
            ProjectORM.id == project_id,
            ProjectORM.tenant_id == tenant_id,
        )
    )
    project = project_result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    document_count_result = await db.execute(
        select(func.count(DocumentORM.id)).where(DocumentORM.project_id == project_id)
    )
    document_count = int(document_count_result.scalar_one() or 0)

    analysis_result = await db.execute(
        select(Analysis)
        .where(
            Analysis.project_id == project_id,
            Analysis.status == AnalysisStatus.COMPLETED,
        )
        .order_by(Analysis.completed_at.desc().nullslast(), Analysis.created_at.desc())
        .limit(1)
    )
    latest_analysis = analysis_result.scalar_one_or_none()

    coherence_result = await db.execute(
        select(CoherenceResultORM)
        .where(CoherenceResultORM.project_id == project_id)
        .order_by(CoherenceResultORM.calculated_at.desc())
        .limit(1)
    )
    latest_coherence = coherence_result.scalar_one_or_none()

    global_score = 0
    if latest_analysis and latest_analysis.coherence_score is not None:
        global_score = int(latest_analysis.coherence_score)
    elif latest_coherence is not None:
        global_score = latest_coherence.global_score
    elif project.coherence_score is not None:
        global_score = int(project.coherence_score)

    completed_at = None
    if latest_analysis and latest_analysis.completed_at is not None:
        completed_at = latest_analysis.completed_at.isoformat()
    elif latest_coherence is not None:
        completed_at = latest_coherence.calculated_at.isoformat()
    elif project.last_analysis_at is not None:
        completed_at = project.last_analysis_at.isoformat()

    return document_count, global_score, completed_at

def get_orchestrator() -> WorkflowOrchestrator:
    return WorkflowOrchestrator()

def get_analyze_use_case(
    orchestrator: WorkflowOrchestrator = Depends(get_orchestrator),
) -> AnalyzeDocumentUseCase:
    return AnalyzeDocumentUseCase(orchestrator)


async def get_document_text_from_rag(
    db: AsyncSession,
    project_id: UUID,
    tenant_id: UUID,
    document_id: UUID | None = None,
    prompt: str = "",
    top_k: int = 10,
) -> tuple[str, list[dict[str, Any]]]:
    """Fetch document text from RAG chunks and build context, with parsed_text fallback."""
    if document_id:
        chunk_stmt = text("""
            SELECT dc.content, dc.metadata
            FROM document_chunks dc
            JOIN projects p ON dc.project_id = p.id
            WHERE dc.project_id = CAST(:project_id AS uuid)
              AND dc.document_id = CAST(:document_id AS uuid)
              AND p.tenant_id = CAST(:tenant_id AS uuid)
            ORDER BY dc.created_at DESC
            LIMIT :limit
        """)
        chunk_params = {
            "project_id": str(project_id),
            "document_id": str(document_id),
            "tenant_id": str(tenant_id),
            "limit": top_k,
        }
    else:
        chunk_stmt = text("""
            SELECT dc.content, dc.metadata
            FROM document_chunks dc
            JOIN projects p ON dc.project_id = p.id
            WHERE dc.project_id = CAST(:project_id AS uuid)
              AND p.tenant_id = CAST(:tenant_id AS uuid)
            ORDER BY dc.created_at DESC
            LIMIT :limit
        """)
        chunk_params = {
            "project_id": str(project_id),
            "tenant_id": str(tenant_id),
            "limit": top_k * 3,
        }

    result = await db.execute(chunk_stmt, chunk_params)
    rows = result.fetchall()

    chunks = [{"content": row[0], "metadata": row[1] or {}} for row in rows]
    if chunks:
        context = "\n\n---\n\n".join(c["content"] for c in chunks)
        full_text = f"CONSULTA: {prompt}\n\nDOCUMENTOS:\n{context}"
        return full_text, chunks

    if document_id:
        doc_stmt = text("""
            SELECT d.id, d.document_type::text, d.document_metadata
            FROM documents d
            JOIN projects p ON d.project_id = p.id
            WHERE d.project_id = CAST(:project_id AS uuid)
              AND d.id = CAST(:document_id AS uuid)
              AND p.tenant_id = CAST(:tenant_id AS uuid)
              AND d.upload_status IN ('parsed', 'parsed_pending_analysis', 'analyzed')
            ORDER BY d.created_at DESC
        """)
        doc_params = {
            "project_id": str(project_id),
            "document_id": str(document_id),
            "tenant_id": str(tenant_id),
        }
    else:
        doc_stmt = text("""
            SELECT d.id, d.document_type::text, d.document_metadata
            FROM documents d
            JOIN projects p ON d.project_id = p.id
            WHERE d.project_id = CAST(:project_id AS uuid)
              AND p.tenant_id = CAST(:tenant_id AS uuid)
              AND d.upload_status IN ('parsed', 'parsed_pending_analysis', 'analyzed')
            ORDER BY d.created_at DESC
        """)
        doc_params = {
            "project_id": str(project_id),
            "tenant_id": str(tenant_id),
        }

    doc_result = await db.execute(doc_stmt, doc_params)
    documents = doc_result.fetchall()
    fallback_docs = []
    for row in documents:
        doc_id = str(row[0])
        doc_type = row[1] or "unknown"
        metadata = row[2] or {}
        parsed_text = metadata.get("parsed_text") if isinstance(metadata, dict) else None
        if isinstance(parsed_text, str) and parsed_text.strip():
            fallback_docs.append(
                {
                    "content": parsed_text.strip(),
                    "metadata": {
                        "document_id": doc_id,
                        "document_type": doc_type,
                        "source": "document_metadata.parsed_text",
                    },
                }
            )

    if not fallback_docs:
        return "", []

    context = "\n\n---\n\n".join(c["content"] for c in fallback_docs)
    full_text = f"CONSULTA: {prompt}\n\nDOCUMENTOS:\n{context}"
    return full_text, fallback_docs


class AnalyzeRequest(BaseModel):
    project_id: UUID = Field(..., description="Project ID to analyze documents from")
    document_id: UUID | None = Field(None, description="Optional specific document ID. If not provided, analyzes all project documents.")
    analysis_prompt: str = Field(
        default="Analiza todos los documentos del proyecto y extrae: 1) Partes contratantes, 2) Objeto del contrato, 3) Duración, 4) Importe, 5) Posibles riesgos",
        description="Analysis prompt/question for the documents"
    )


class AnalyzeResponse(BaseModel):
    project_id: str
    analysis_id: str | None
    risks: list[dict[str, Any]]
    wbs: list[dict[str, Any]]
    human_approval_required: bool
    doc_type: str
    confidence_score: float
    critique_notes: str
    retry_count: int
    messages: list[str]


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_document(
    payload: AnalyzeRequest,
    _request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
    use_case: AnalyzeDocumentUseCase = Depends(get_analyze_use_case),
) -> AnalyzeResponse:
    document_text, sources = await get_document_text_from_rag(
        db=db,
        project_id=payload.project_id,
        tenant_id=current_user.tenant_id,
        document_id=payload.document_id,
        prompt=payload.analysis_prompt,
        top_k=10,
    )

    if not document_text:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No documents found for analysis. Please upload and parse documents first.",
        )

    tenant_id = str(current_user.tenant_id) if current_user.tenant_id else None
    result = await use_case.execute(
        document_text=document_text,
        project_id=str(payload.project_id),
        document_id=str(payload.document_id) if payload.document_id else None,
        tenant_id=tenant_id,
    )
    message_contents = [
        message.content for message in result.get("messages", []) if hasattr(message, "content")
    ]
    return AnalyzeResponse(
        project_id=result["project_id"],
        analysis_id=result.get("analysis_id"),
        risks=result["extracted_risks"],
        wbs=result["extracted_wbs"],
        human_approval_required=result["human_approval_required"],
        doc_type=result.get("doc_type", ""),
        confidence_score=result.get("confidence_score", 0.0),
        critique_notes=result.get("critique_notes", ""),
        retry_count=result.get("retry_count", 0),
        messages=message_contents,
    )


@router.get("/projects/{project_id}/process/stream")
async def stream_project_processing(
    project_id: UUID,
    _request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> StreamingResponse:
    tenant_id = current_user.tenant_id

    document_count, global_score, completed_at = await _resolve_processing_summary(
        db,
        project_id,
        tenant_id,
    )

    async def event_stream():
        for stage in PROCESSING_STAGE_TEMPLATE:
            yield _sse_frame("stage", stage)
        yield _sse_frame(
            "complete",
            _build_completion_payload(
                document_count=document_count,
                global_score=global_score,
                completed_at=completed_at,
            ),
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
