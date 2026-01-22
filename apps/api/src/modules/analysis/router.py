from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from src.ai.graph.workflow import get_graph_app

router = APIRouter(
    prefix="",
    tags=["analysis"],
    responses={404: {"description": "Not found"}},
)


class AnalyzeRequest(BaseModel):
    document_text: str = Field(..., min_length=1)
    project_id: str = Field(..., min_length=1)


class AnalyzeResponse(BaseModel):
    project_id: str
    analysis_id: str | None
    risks: list[dict[str, Any]]
    wbs: list[dict[str, Any]]
    next_step: str
    human_approval_required: bool
    messages: list[str]


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_document(payload: AnalyzeRequest, request: Request) -> AnalyzeResponse:
    app = get_graph_app()
    initial_state = {
        "document_text": payload.document_text,
        "project_id": payload.project_id,
        "tenant_id": str(getattr(request.state, "tenant_id", "")),
        "risks": [],
        "wbs": [],
        "messages": [],
        "next_step": "",
        "human_approval_required": False,
        "analysis_id": None,
    }
    result = await app.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": payload.project_id}},
    )
    message_contents = [
        message.content for message in result.get("messages", []) if hasattr(message, "content")
    ]
    return AnalyzeResponse(
        project_id=result["project_id"],
        analysis_id=result.get("analysis_id"),
        risks=result["risks"],
        wbs=result["wbs"],
        next_step=result["next_step"],
        human_approval_required=result["human_approval_required"],
        messages=message_contents,
    )
