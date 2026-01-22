from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from src.ai.orchestrator import run_orchestration

router = APIRouter(
    prefix="",
    tags=["analysis"],
    responses={404: {"description": "Not found"}},
)


class AnalyzeRequest(BaseModel):
    document_text: str = Field(..., min_length=1)
    project_id: str = Field(..., min_length=1)
    document_id: str | None = None


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
async def analyze_document(payload: AnalyzeRequest, request: Request) -> AnalyzeResponse:
    initial_state = {
        "document_text": payload.document_text,
        "project_id": payload.project_id,
        "document_id": payload.document_id or payload.project_id,
        "doc_type": "",
        "tenant_id": str(getattr(request.state, "tenant_id", "")) or None,
        "messages": [],
        "extracted_risks": [],
        "extracted_wbs": [],
        "confidence_score": 0.0,
        "critique_notes": "",
        "human_feedback": "",
        "retry_count": 0,
        "human_approval_required": False,
        "analysis_id": None,
    }
    result = await run_orchestration(initial_state, thread_id=payload.project_id)
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
