"""
Persistence use case for analysis results.

Orchestrates saving analysis records and generating alerts from risks.
Session lifecycle is owned by the caller.

WBS is a governed canonical project backbone (#830): an AI-extracted WBS is a
PROPOSAL. It is kept, exactly as extracted, in the analysis' ``result_json["wbs"]``
and qualified ``WBS_GOVERNANCE_REQUIRED``; the canonical WBS is never created,
deleted, replaced or relinked here -- not even a project's first WBS. Only the
governed WBS baseline authority (PC-1 / PC-2: human review + edit + approval of
the exact tree) may turn a proposal into Baseline #1 / #N+1. A visible WBS code
is not an identity, so nothing here matches proposals to canonical nodes.

Refers to TASK-IMPL-010.7.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from src.analysis.application.trusted_materialization import MaterializationQualification
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
    qualifications: tuple[str, ...] = ()


def wbs_governance_qualification(analysis_id: UUID, extracted_wbs: list[dict[str, Any]]) -> dict[str, Any]:
    """Where the WBS proposal lives, and that the canonical WBS was not modified."""
    return {
        "qualification": MaterializationQualification.WBS_GOVERNANCE_REQUIRED.value,
        "canonical_wbs_modified": False,
        "proposed_nodes": len(extracted_wbs),
        "proposal_source": {
            "table": "analyses",
            "analysis_id": str(analysis_id),
            "path": "result_json.wbs",
        },
    }


class PersistAnalysisUseCase:
    """Persists analysis records and risk alerts; an extracted WBS stays a proposal.

    The repository's session is owned by the caller (the context manager stays
    in the node).
    """

    def __init__(self, analysis_repo: IAnalysisRepository) -> None:
        self._analysis_repo = analysis_repo

    async def execute(self, command: PersistAnalysisCommand) -> PersistAnalysisResult:
        from src.analysis.ports.types import AlertWrite, AnalysisWrite
        from src.coherence.alert_generator import AlertGenerator

        analysis_type = (
            AnalysisType.RISK if command.extracted_risks else AnalysisType.SCHEDULE
        )
        analysis_id = uuid4()
        qualifications: tuple[str, ...] = ()
        governance: dict[str, Any] = {}
        if command.extracted_wbs:
            qualifications = (MaterializationQualification.WBS_GOVERNANCE_REQUIRED.value,)
            governance = {
                "wbs_governance": wbs_governance_qualification(analysis_id, command.extracted_wbs)
            }

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
                # The WBS proposal, exactly as extracted (recoverable for governance).
                "wbs": command.extracted_wbs,
                # Additive: existing keys are preserved; the assessment key is written
                # only when the assessment actually ran.
                **(command.single_document_assessment or {}),
                **governance,
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

        await self._analysis_repo.commit()

        return PersistAnalysisResult(analysis_id=analysis_id, qualifications=qualifications)
