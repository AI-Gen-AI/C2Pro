"""
Alert Application DTOs.

Request and Response Data Transfer Objects.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class AlertRuleConfigPayload(BaseModel):
    id: str
    name: str
    description: str
    enabled: bool
    threshold: int
    severity: str


class AlertSubscriptionConfigPayload(BaseModel):
    emailEnabled: bool = False
    emailAddress: str = ""
    slackEnabled: bool = False
    slackChannel: str = ""

    @field_validator("emailAddress", "slackChannel", mode="before")
    @classmethod
    def _strip_delivery_target(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def validate_delivery_targets(self) -> AlertSubscriptionConfigPayload:
        if self.emailEnabled:
            local_part, separator, domain_part = self.emailAddress.partition("@")
            if not separator or not local_part or "." not in domain_part:
                raise ValueError("emailAddress must be a valid email when email notifications are enabled")

        if self.slackEnabled and (not self.slackChannel.startswith("#") or len(self.slackChannel) < 2):
            raise ValueError("slackChannel must start with # when Slack notifications are enabled")

        return self


class AlertWorkspaceSettingsPayload(BaseModel):
    rules: list[AlertRuleConfigPayload] = Field(default_factory=list)
    subscriptions: AlertSubscriptionConfigPayload | None = None


class CreateAlertRequest(BaseModel):
    project_id: UUID
    rule_code: str
    category: Literal["SCOPE", "BUDGET", "QUALITY", "TECHNICAL", "LEGAL", "TIME"]
    severity: Literal["low", "medium", "high", "critical"]
    message: str
    affected_entities: dict = Field(default_factory=dict)


class ReviewAlertRequest(BaseModel):
    decision: Literal["approve", "reject"]
    comment: str = ""


class BulkReviewRequest(BaseModel):
    alert_ids: list[str]
    decision: Literal["approve", "reject"]
    comment: str = ""


class BulkDeleteRequest(BaseModel):
    alert_ids: list[str]
    status_filter: str | None = None


class AttachEvidenceRequest(BaseModel):
    type: Literal["note", "screenshot", "document_excerpt"]
    content: str
    source: str = "manual_review"


class ResolveAlertRequest(BaseModel):
    resolution: str
    resolved_by: UUID | None = None  # Optional — router uses CurrentUserId when absent
    root_cause: str | None = None


class BulkResolveRequest(BaseModel):
    alert_ids: list[str]
    resolution: str
    root_cause: str | None = None


class AlertResponse(BaseModel):
    id: UUID
    project_id: UUID
    tenant_id: UUID
    rule_code: str
    category: str
    severity: str
    message: str
    status: str
    affected_entities: dict = Field(default_factory=dict)
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    root_cause: str | None = None
    sla_policy_name: str | None = None
    sla_due_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class AlertListResponse(BaseModel):
    items: list[AlertResponse]
    total: int


class AlertHistoryResponse(BaseModel):
    alert_id: str
    items: list[dict]


class BulkOperationResponse(BaseModel):
    processed_count: int
    decision: str | None = None
    warning: str | None = None
    status: str | None = None
    alert_ids: list[str] | None = None


class EvidenceResponse(BaseModel):
    alert_id: str
    evidence_count: int


class DeleteResponse(BaseModel):
    deleted_count: int
