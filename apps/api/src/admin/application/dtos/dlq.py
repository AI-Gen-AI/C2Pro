"""Test Suite ID: TS-BCK-042-001.

DTOs for DLQ admin operations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

DLQStatus = Literal["pending", "retrying", "exhausted"]


class DLQEntryResponse(BaseModel):
    """TS-BCK-042-001: Serialized DLQ entry for admin responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    task_type: str
    document_id: UUID | None
    payload_json: dict[str, Any]
    error_message: str
    error_traceback: str | None
    retry_count: int
    max_retries: int
    status: str
    created_at: datetime
    updated_at: datetime
    next_retry_at: datetime | None


class DLQListResponse(BaseModel):
    """TS-BCK-042-001: Admin DLQ list response with pagination metadata."""

    entries: list[DLQEntryResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class DLQRetryResponse(BaseModel):
    """TS-BCK-042-001: Admin DLQ retry response."""

    id: UUID
    status: Literal["retrying"]
