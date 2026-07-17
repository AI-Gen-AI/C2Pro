"""
Protocol types for Analysis ports.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from src.analysis.domain.enums import AlertSeverity, AlertStatus, AnalysisStatus, AnalysisType
from src.core.json_types import JsonDict


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
    result_json: Any | None
    coherence_score: int | None
    alerts_count: int
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
