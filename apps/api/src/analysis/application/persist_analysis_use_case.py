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

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
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
    # C2PRO P0b crash-safe resume: stable identity of the operation this
    # persistence belongs to. When set, N17 becomes idempotent for that
    # operation -- a replay after a crash returns the analysis already
    # committed instead of creating a second one. ``None`` keeps the
    # historical behaviour for every non-HITL caller.
    idempotency_key: str | None = None


@dataclass(frozen=True)
class PersistAnalysisResult:
    """Result of persistence operation."""

    analysis_id: UUID
    # False when this call found an analysis already persisted for the same
    # idempotency_key, i.e. it was a replay. Callers use it to suppress
    # duplicate side effects such as a second graph.completed event.
    created: bool = True


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
        from src.wbs.adapters.persistence.models import WBSNodeORM

        # C2PRO P0b crash-safe resume: fence N17 on the operation identity
        # BEFORE doing any work. A crash between this commit and the caller
        # recording completion would otherwise replay the whole persistence.
        if command.idempotency_key:
            existing = await self._find_by_idempotency_key(
                command.idempotency_key, command.tenant_id
            )
            if existing is not None:
                return PersistAnalysisResult(analysis_id=existing, created=False)

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
            idempotency_key=command.idempotency_key,
            result_json={
                "risks": command.extracted_risks,
                "wbs": command.extracted_wbs,
                # Additive: existing keys are preserved; the assessment key is written
                # only when the assessment actually ran.
                **(command.single_document_assessment or {}),
            },
        )
        await self._analysis_repo.add_analysis(analysis, tenant_id=command.tenant_id)
        try:
            await self._analysis_repo.flush()
        except IntegrityError:
            # Lost the race against a concurrent replay of the SAME
            # operation: the partial unique index on analyses.idempotency_key
            # is the authoritative arbiter, so adopt the winner rather than
            # persisting a duplicate.
            await self._session.rollback()
            existing = await self._find_by_idempotency_key(
                command.idempotency_key, command.tenant_id
            )
            if existing is None:
                raise
            return PersistAnalysisResult(analysis_id=existing, created=False)

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
            # The analysis replaces the project's canonical WBS (ADR-025: one WBS per project).
            await self._session.execute(
                delete(WBSNodeORM).where(
                    WBSNodeORM.project_id == command.project_id,
                    WBSNodeORM.tenant_id == command.tenant_id,
                )
            )
            await self._wbs_repo.bulk_create_from_dicts(
                command.project_id, command.extracted_wbs
            )

        await self._analysis_repo.commit()

        return PersistAnalysisResult(analysis_id=analysis_id, created=True)

    async def _find_by_idempotency_key(
        self, idempotency_key: str | None, tenant_id: UUID
    ) -> UUID | None:
        if not idempotency_key:
            return None
        from src.analysis.adapters.persistence.models import Analysis

        found = (
            await self._session.execute(
                select(Analysis.id).where(
                    Analysis.idempotency_key == idempotency_key,
                    Analysis.tenant_id == tenant_id,
                )
            )
        ).scalars().first()
        return found
