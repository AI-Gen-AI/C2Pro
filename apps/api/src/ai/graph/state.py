from __future__ import annotations

from typing import Any, TypedDict

from langchain_core.messages import BaseMessage

Risk = dict[str, Any]
Task = dict[str, Any]


class AgentState(TypedDict):
    document_text: str
    project_id: str
    tenant_id: str
    risks: list[Risk]
    wbs: list[Task]
    messages: list[BaseMessage]
    next_step: str
    human_approval_required: bool
    analysis_id: str | None
