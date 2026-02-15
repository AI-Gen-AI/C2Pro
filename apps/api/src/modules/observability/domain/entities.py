"""
I12 Observability Domain Entities
Test Suite IDs: TS-I12-OBS-DOM-001, TS-I12-OBS-APP-002
"""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TraceContext(BaseModel):
    run_id: UUID = Field(default_factory=uuid4)
    parent_id: UUID | None = None
    name: str = Field(..., min_length=1)
    run_type: Literal["chain", "llm", "tool", "agent", "retriever", "embedding", "prompt", "chat"]
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvalMetricResult(BaseModel):
    metric_name: str
    value: float
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DriftAlarmConfig(BaseModel):
    metric_name: str
    threshold_percentage_drop: float = Field(..., ge=0.0, le=1.0)
    min_absolute_value: float | None = Field(default=None, ge=0.0, le=1.0)
    escalation_target_email: str


class DriftAlert(BaseModel):
    alert_id: UUID = Field(default_factory=uuid4)
    metric_name: str
    baseline_value: float
    recent_value: float
    is_drift_detected: bool
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)

