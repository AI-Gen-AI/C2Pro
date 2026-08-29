"""SnapshotWriter application service (ADR-015 / TASK-V3-015-05).

TS-UT-TSW-001
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from src.analysis.ports.analysis_repository import IAnalysisRepository
from src.core.tenants.types import TenantId
from src.health.application.contract_scorer import score_contract_dimension
from src.health.application.documentation_scorer import score_documentation_dimension
from src.health.application.governance_scorer import score_governance_dimension
from src.health.application.health_engine import assemble_health_vector
from src.health.application.risk_scorer import score_risk_dimension
from src.health.domain.analysis_assessment import decode_single_document_assessment
from src.health.domain.single_document_coverage import SingleDocumentCoverage
from src.project_state.domain.aggregate import ProjectState
from src.project_state.ports.project_state_repository import ProjectStateRepository
from src.temporal.domain.project_snapshot import ProjectSnapshot, SnapshotTrigger
from src.temporal.ports.project_event_repository import IProjectEventRepository
from src.temporal.ports.project_snapshot_repository import IProjectSnapshotRepository

_SNAPSHOT_EPOCH = datetime(1970, 1, 1)

# Triggers whose snapshot is produced BY a new analysis. For these the new analysis is
# authoritative: its assessment, or honest unavailable — never a prior one.
_ANALYSIS_AUTHORITATIVE_TRIGGERS = frozenset({SnapshotTrigger.GRAPH_COMPLETED})


class AssessmentLineage(StrEnum):
    """Why a snapshot does or does not carry a single-document assessment.

    ``coverage=None`` alone is ambiguous — it can mean "a new analysis ran and produced
    no usable assessment" or "no new analysis exists". Those are different product
    claims, so the resolution reports which one applies.
    """

    RESOLVED = "resolved"
    """A new analysis produced a valid versioned assessment."""

    UNAVAILABLE = "unavailable"
    """A new analysis exists but carries no usable assessment (legacy artifact, unknown
    version, or missing/malformed lineage). Honest unknown — NOT a prior assessment."""

    NO_NEW_ANALYSIS = "no_new_analysis"
    """This snapshot was not produced by an analysis (e.g. SCHEDULED), so the most recent
    valid assessment still stands and is carried forward."""


@dataclass(frozen=True)
class ResolvedAssessment:
    """Outcome of single-document assessment lineage resolution."""

    lineage: AssessmentLineage
    coverage: SingleDocumentCoverage | None = None


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class SnapshotWriter:
    """Writes honest, lightweight project snapshots without owning transactions."""

    def __init__(
        self,
        project_state_repository: ProjectStateRepository,
        snapshot_repository: IProjectSnapshotRepository,
        event_repository: IProjectEventRepository | None = None,
        analysis_repository: IAnalysisRepository | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._project_state_repository = project_state_repository
        self._snapshot_repository = snapshot_repository
        # Optional lineage readers (ADR-024 / P0b L4-3). Absent => the single-document
        # assessment is simply unavailable; the snapshot is still written honestly.
        self._event_repository = event_repository
        self._analysis_repository = analysis_repository
        self._clock = clock or _utcnow

    async def write_snapshot(
        self,
        project_id: UUID,
        tenant_id: TenantId,
        trigger: SnapshotTrigger,
        source_event_id: UUID | None = None,
    ) -> ProjectSnapshot:
        now = self._clock()
        existing = await self._find_existing_snapshot(
            project_id=project_id,
            tenant_id=tenant_id,
            trigger=trigger,
            captured_at=now,
            source_event_id=source_event_id,
        )
        if existing is not None:
            return existing

        state = await self._project_state_repository.get(project_id, tenant_id)
        counts = self._counts(state)
        totals = self._totals(state)
        prior_snapshot = await self._snapshot_repository.latest(project_id, tenant_id)
        resolved_assessment = await self._resolve_single_document_coverage(
            tenant_id=tenant_id,
            trigger=trigger,
            source_event_id=source_event_id,
            prior_snapshot=prior_snapshot,
        )
        health_vector = assemble_health_vector(
            project_id,
            tenant_id,
            signals=[
                score_risk_dimension(
                    state.risks if state is not None else [],
                    assessment_ran=state is not None,
                ),
                score_contract_dimension(
                    state.clauses if state is not None else [],
                    state.obligations if state is not None else [],
                    coherence_subscore=None,
                ),
                score_documentation_dimension(None),
                score_governance_dimension(None),
            ],
            prior_composite=self._prior_composite(prior_snapshot),
            single_document_coverage=resolved_assessment.coverage,
        )
        snapshot = ProjectSnapshot(
            snapshot_id=uuid4(),
            project_id=project_id,
            tenant_id=tenant_id,
            captured_at=now,
            trigger=trigger,
            health_vector=health_vector.model_dump(mode="json"),
            coherence_subscore=None,
            counts=counts,
            totals=totals,
            source_event_id=source_event_id,
            created_at=now,
        )
        return await self._snapshot_repository.append_snapshot(snapshot)

    async def _resolve_single_document_coverage(
        self,
        *,
        tenant_id: TenantId,
        trigger: SnapshotTrigger,
        source_event_id: UUID | None,
        prior_snapshot: ProjectSnapshot | None,
    ) -> ResolvedAssessment:
        """Resolve the single-document assessment, distinguishing the two "no coverage" states.

        A snapshot produced BY an analysis (``GRAPH_COMPLETED``) takes that analysis as
        authoritative. Lineage (ADR-024 / P0b L4-3): ``source_event_id`` -> the
        ``graph.completed`` event's ``analysis_id`` -> that analysis' ``result_json`` ->
        the versioned assessment. The assessment is READ, never recomputed — the
        ``CategoryRouter`` already ran once at analysis time (N8).

        If that analysis carries no usable assessment (legacy artifact, unknown version,
        missing or malformed lineage) the result is ``UNAVAILABLE`` with no coverage. It
        deliberately does NOT fall back to a prior assessment: a fresh analysis that
        produced nothing must never make an older assessment appear current.

        A snapshot NOT produced by an analysis (e.g. ``SCHEDULED``) carries the most recent
        valid assessment forward — no new analysis is not evidence that the previous
        assessment ceased to exist. With no prior assessment the coverage stays ``None``.
        """
        if trigger in _ANALYSIS_AUTHORITATIVE_TRIGGERS:
            coverage = await self._coverage_from_lineage(tenant_id, source_event_id)
            if coverage is None:
                return ResolvedAssessment(AssessmentLineage.UNAVAILABLE)
            return ResolvedAssessment(AssessmentLineage.RESOLVED, coverage)
        return ResolvedAssessment(
            AssessmentLineage.NO_NEW_ANALYSIS,
            self._carry_forward_coverage(prior_snapshot),
        )

    async def _coverage_from_lineage(
        self, tenant_id: TenantId, source_event_id: UUID | None
    ) -> SingleDocumentCoverage | None:
        if source_event_id is None or self._event_repository is None or self._analysis_repository is None:
            return None
        event = await self._event_repository.get(source_event_id, tenant_id)
        if event is None:
            return None
        raw_analysis_id = event.payload.get("analysis_id")
        if not isinstance(raw_analysis_id, str):
            return None
        try:
            analysis_id = UUID(raw_analysis_id)
        except ValueError:
            return None
        result_json = await self._analysis_repository.get_result_json(analysis_id, tenant_id)
        assessment = decode_single_document_assessment(result_json)
        return assessment.coverage if assessment is not None else None

    @staticmethod
    def _carry_forward_coverage(
        snapshot: ProjectSnapshot | None,
    ) -> SingleDocumentCoverage | None:
        """Carry the last known assessment forward; never fabricate one."""
        if snapshot is None:
            return None
        stored = snapshot.health_vector.get("single_document_coverage")
        if not isinstance(stored, dict):
            return None
        return SingleDocumentCoverage.model_validate(stored)

    async def _find_existing_snapshot(
        self,
        *,
        project_id: UUID,
        tenant_id: TenantId,
        trigger: SnapshotTrigger,
        captured_at: datetime,
        source_event_id: UUID | None,
    ) -> ProjectSnapshot | None:
        if source_event_id is not None:
            snapshots = await self._snapshot_repository.list_since(
                project_id, tenant_id, _SNAPSHOT_EPOCH
            )
            for snapshot in snapshots:
                if snapshot.source_event_id == source_event_id:
                    return snapshot

        if trigger is SnapshotTrigger.SCHEDULED:
            day_start = captured_at.replace(hour=0, minute=0, second=0, microsecond=0)
            snapshots = await self._snapshot_repository.list_since(project_id, tenant_id, day_start)
            for snapshot in snapshots:
                if snapshot.trigger is SnapshotTrigger.SCHEDULED:
                    return snapshot
        return None

    @staticmethod
    def _counts(state: ProjectState | None) -> dict[str, int]:
        if state is None:
            return {
                "clauses": 0,
                "obligations": 0,
                "risks": 0,
                "wbs_activities": 0,
                "budget_items": 0,
                "stakeholders": 0,
                "raci": 0,
            }
        return {
            "clauses": len(state.clauses),
            "obligations": len(state.obligations),
            "risks": len(state.risks),
            "wbs_activities": len(state.wbs_activities),
            "budget_items": len(state.budget_items),
            "stakeholders": len(state.stakeholders),
            "raci": len(state.raci),
        }

    @staticmethod
    def _totals(state: ProjectState | None) -> dict[str, object]:
        if state is None:
            return {"budget_amount": 0.0, "budget_amount_by_currency": {}}

        by_currency: dict[str, float] = {}
        for item in state.budget_items:
            amount = float(item.payload.amount)
            currency = item.payload.currency
            by_currency[currency] = by_currency.get(currency, 0.0) + amount
        return {
            "budget_amount": sum(by_currency.values()),
            "budget_amount_by_currency": by_currency,
        }

    @staticmethod
    def _prior_composite(snapshot: ProjectSnapshot | None) -> float | None:
        if snapshot is None:
            return None
        value = snapshot.health_vector.get("composite_score")
        if isinstance(value, int | float):
            return float(value)
        return None
