"""L2 semantic classification contract for ADR-016.

TS-UT-CI-SEM-001
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["info", "low", "medium", "high", "critical"]


class SemanticClassification(BaseModel):
    """Structured LLM output for one modified clause pair."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    semantic_summary: str
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)


__all__ = ["SemanticClassification"]
