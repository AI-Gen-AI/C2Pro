"""
Persistence use case for analysis results.

Orchestrates saving analysis records, generating alerts from risks,
and replacing WBS snapshots. Session lifecycle is owned by the caller.

Refers to TASK-IMPL-010.7.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.domain.enums import AnalysisStatus, AnalysisType
from src.analysis.ports.analysis_repository import IAnalysisRepository


@dataclass(frozen=True)
class PersistAnalysisCommand:
    """Input for persisting analysis results."""

    project_id: UUID
    tenant_id: UUID
    extracted_risks: list[dict[str, Any]]
    extracted_wbs: list[dict[str, Any]]
    coherence_score: int | float | None
    coherence_breakdown: dict[str, Any]
    # ADR-024 / P0b L4-3: versioned single-document assessment fragment produced at N8.
    # ``None`` => not evaluated for this analysis; the key is then simply absent from
    # result_json, which readers must treat as UNAVAILABLE (never "evaluated, empty").
    single_document_assessment: dict[str, Any] | None = None


@dataclass(frozen=True)
class PersistAnalysisResult:
    """Result of persistence operation."""

    analysis_id: UUID


class PersistAnalysisUseCase:
    """Persists analysis records, risk alerts, and WBS items.

    Session is received via injection — caller owns the lifecycle
    (context manager stays in the node).
    """

    def __init__(
        self,
        analysis_repo: IAnalysisRepository,
        wbs_repo: Any,  # SQLAlchemyWBSRepository
        session: AsyncSession,
    ) -> None:
        self._analysis_repo = analysis_repo
        self._wbs_repo = wbs_repo
        self._session = session

    async def execute(self, command: PersistAnalysisCommand) -> PersistAnalysisResult:
        from src.analysis.ports.types import AlertWrite, AnalysisWrite
        from src.coherence.alert_generator import AlertGenerator
        from src.procurement.adapters.persistence.models import WBSItemORM

        analysis_type = (
            AnalysisType.RISK if command.extracted_risks else AnalysisType.SCHEDULE
        )
        analysis_id = uuid4()

        completed_at = datetime.now(UTC).replace(tzinfo=None)
        analysis = AnalysisWrite(
            id=analysis_id,
            tenant_id=command.tenant_id,
            project_id=command.project_id,
            analysis_type=analysis_type,
            status=AnalysisStatus.COMPLETED,
            coherence_score=command.coherence_score,
            coherence_breakdown=command.coherence_breakdown,
            alerts_count=len(command.extracted_risks),
            completed_at=completed_at,
            result_json={
                "risks": command.extracted_risks,
                "wbs": command.extracted_wbs,
                # Additive: existing keys are preserved; the assessment key is written
                # only when the assessment actually ran.
                **(command.single_document_assessment or {}),
            },
        )
        await self._analysis_repo.add_analysis(analysis, tenant_id=command.tenant_id)
        await self._analysis_repo.flush()

        if command.extracted_risks:
            generator = AlertGenerator(
                project_id=command.project_id,
                analysis_id=analysis_id,
            )
            alert_dtos = generator.generate_risk_alerts(command.extracted_risks)
            alerts = [
                AlertWrite(
                    tenant_id=command.tenant_id,
                    project_id=dto.project_id,
                    analysis_id=dto.analysis_id,
                    alert_type=dto.alert_type,
                    severity=dto.severity,
                    title=dto.title,
                    message=dto.description,
                    description=dto.description,
                    category=dto.category,
                    impact_level=dto.impact_level,
                    alert_metadata=dto.alert_metadata,
                    rule_id=dto.rule_id,
                    source_clause_id=dto.source_clause_id,
                    related_clause_ids=dto.related_clause_ids,
                    affected_entities=dto.affected_entities,
                    recommendation=dto.recommendation,
                )
                for dto in alert_dtos
            ]
            await self._analysis_repo.add_alerts(alerts, tenant_id=command.tenant_id)

        if command.extracted_wbs:
            await self._session.execute(
                delete(WBSItemORM).where(
                    WBSItemORM.project_id == command.project_id
                )
            )
            await self._wbs_repo.bulk_create_from_dicts(
                command.project_id, command.extracted_wbs
            )

        await self._analysis_repo.commit()

        return PersistAnalysisResult(analysis_id=analysis_id)
