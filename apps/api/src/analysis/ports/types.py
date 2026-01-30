"""
Protocol types for Analysis ports.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Protocol
from uuid import UUID

from src.analysis.domain.enums import AlertSeverity, AlertStatus, AnalysisStatus, AnalysisType

class AlertRecord(Protocol):
    id: UUID
    project_id: UUID
    analysis_id: Optional[UUID]
    severity: AlertSeverity
    category: Optional[str]
    rule_id: Optional[str]
    title: str
    description: str
    recommendation: Optional[str]
    source_clause_id: Optional[UUID]
    related_clause_ids: Optional[list[UUID]]
    affected_entities: dict
    impact_level: Optional[str]
    alert_metadata: dict
    status: AlertStatus
    resolved_at: Optional[datetime]
    resolved_by: Optional[UUID]
    resolution_notes: Optional[str]

class AnalysisRecord(Protocol):
    id: UUID
    project_id: UUID
    analysis_type: AnalysisType
    status: AnalysisStatus
    result_json: Any | None
    coherence_score: int | None
    alerts_count: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
