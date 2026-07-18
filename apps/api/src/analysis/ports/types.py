"""
Protocol types for Analysis ports.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from src.analysis.domain.enums import (
    AlertSeverity,
    AlertStatus,
    AlertType,
    AnalysisStatus,
    AnalysisType,
)
from src.core.json_types import JsonDict, JsonValue


@dataclass(frozen=True)
class AnalysisWrite:
    """Tenant-owned analysis data accepted by the persistence port."""

    id: UUID
    tenant_id: UUID
    project_id: UUID
    analysis_type: AnalysisType
    status: AnalysisStatus
    result_json: JsonDict
    coherence_score: int | float | None
    coherence_breakdown: JsonDict
    alerts_count: int
    completed_at: datetime


@dataclass(frozen=True)
class AlertWrite:
    """Tenant-owned alert data accepted by the persistence port."""

    tenant_id: UUID
    project_id: UUID
    analysis_id: UUID | None
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    description: str
    category: str | None
    impact_level: str | None
    alert_metadata: JsonDict
    rule_id: str | None
    source_clause_id: UUID | None
    related_clause_ids: list[UUID] | None
    affected_entities: JsonDict
    recommendation: str | None


class AlertRecord(Protocol):
    id: UUID
    project_id: UUID
    analysis_id: UUID | None
    severity: AlertSeverity
    category: str | None
    rule_id: str | None
    title: str
    description: str
    recommendation: str | None
    source_clause_id: UUID | None
    related_clause_ids: list[UUID] | None
    affected_entities: JsonDict
    impact_level: str | None
    alert_metadata: JsonDict
    status: AlertStatus
    resolved_at: datetime | None
    resolved_by: UUID | None
    resolution_notes: str | None

class AnalysisRecord(Protocol):
    id: UUID
    project_id: UUID
    analysis_type: AnalysisType
    status: AnalysisStatus
    result_json: JsonValue
    coherence_score: int | None
    alerts_count: int
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
