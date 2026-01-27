from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

Risk = dict[str, Any]
Task = dict[str, Any]


class ProjectState(TypedDict):
    project_id: str
    document_id: str
    document_text: str
    doc_type: str
    messages: Annotated[list[BaseMessage], add_messages]
    extracted_risks: list[Risk]
    extracted_wbs: list[Task]
    confidence_score: float
    critique_notes: str
    human_feedback: str
    retry_count: int
    tenant_id: str | None
    analysis_id: str | None
    human_approval_required: bool
