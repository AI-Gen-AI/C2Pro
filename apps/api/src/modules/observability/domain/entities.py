"""
I12 Observability Domain Entities
Test Suite IDs: TS-I12-OBS-DOM-001, TS-I12-OBS-DOM-003, TS-I12-OBS-APP-002
"""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

_REQUIRED_TRACE_METADATA_KEYS = {"tenant_id", "project_id"}
_REQUIRED_DRIFT_ALERT_METADATA_KEYS = {"dataset", "requires_ops_review"}
_ALLOWED_METADATA_SCALAR_TYPES = (str, int, float, bool)


class TraceContext(BaseModel):
    run_id: UUID = Field(default_factory=uuid4)
    parent_id: UUID | None = None
    name: str = Field(..., min_length=1)
    run_type: Literal["chain", "llm", "tool", "agent", "retriever", "embedding", "prompt", "chat"]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        # Keep compatibility with callers that send empty metadata, while
        # enforcing auditability once metadata is present.
        if not value:
            return value

        _validate_required_metadata_keys(value)
        _validate_scalar_metadata_values(value)
        return value

    @model_validator(mode="after")
    def validate_lineage(self) -> "TraceContext":
        if self.parent_id is not None and self.parent_id == self.run_id:
            raise ValueError("parent_id cannot be equal to run_id")
        return self


def _is_scalar_serializable(value: Any) -> bool:
    return isinstance(value, _ALLOWED_METADATA_SCALAR_TYPES) or value is None


def _validate_required_metadata_keys(metadata: dict[str, Any]) -> None:
    _validate_required_keys(metadata, _REQUIRED_TRACE_METADATA_KEYS)


def _validate_scalar_metadata_values(metadata: dict[str, Any]) -> None:
    for key, item in metadata.items():
        if not _is_scalar_serializable(item):
            raise ValueError(f"metadata value for '{key}' must be scalar and string-serializable")


def _validate_required_keys(metadata: dict[str, Any], required_keys: set[str]) -> None:
    missing = required_keys.difference(metadata.keys())
    if missing:
        raise ValueError(f"metadata missing required keys: {', '.join(sorted(missing))}")


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
    baseline_value: float = Field(..., ge=0.0, le=1.0)
    recent_value: float = Field(..., ge=0.0, le=1.0)
    is_drift_detected: bool
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_required_keys(value, _REQUIRED_DRIFT_ALERT_METADATA_KEYS)
        return value

    @model_validator(mode="after")
    def validate_message_mentions_metric(self) -> "DriftAlert":
        if self.metric_name.lower() not in self.message.lower():
            raise ValueError("message must reference metric_name")
        return self
