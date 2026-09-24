"""N17 for a fenced HITL resume: ONE atomic, tenant-scoped transaction.

C2PRO P0b crash-safe HITL resume V3, sections 7-8.

This is the most important durability boundary in the resume path, and the
one the previous designs got wrong in two different ways:

* V1/V2 split N17 across MULTIPLE commits -- PersistAnalysisUseCase
  committed the analysis itself, and ``record_project_event_and_enqueue_
  snapshot`` then opened a SECOND session/transaction for the event. A crash
  between them left an analysis with no event, and a retry could not tell
  which half had landed.
* Nothing re-verified ownership at write time, so a worker whose lease had
  expired (and which had already been fenced out by a takeover) could still
  commit business effects.

V3 does all core N17 work in one transaction on one session:

    SELECT resume_operations ... FOR UPDATE   -- authority, serialised
    verify attempt/owner/fence/lease
    lock project row                          -- serialise canonical WBS
    detect existing analysis BY resume_operation_id
      -> if present: return it; repeat NOTHING
    else persist analysis + alerts + canonical WBS
         + ProjectEvent('analysis.persisted')
         + operation.analysis_id / provenance / phase=N17_DURABLE
    COMMIT ONCE

Any exception rolls back every core effect together.

Event semantics: N17 emits ``analysis.persisted``, NOT ``graph.completed``.
The graph continues after N17, so "the analysis is durable" and "the graph
finished" are different facts and are recorded separately -- conflating them
is what let a mid-graph crash look like a completed run. ``graph.completed``
is emitted later, only against a verified terminal checkpoint.

The snapshot/projection enqueue stays OUTSIDE this transaction, after
commit: it is a replay-safe projection trigger, not part of approval
truthfulness, and it must never be able to roll back durable business state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlalchemy import delete, select, text

from src.analysis.domain.enums import AnalysisStatus, AnalysisType

logger = structlog.get_logger()

ANALYSIS_PERSISTED_EVENT = "analysis.persisted"
GRAPH_COMPLETED_EVENT = "graph.completed"


@dataclass(frozen=True)
class ResumeProvenance:
    """Which attempt of which operation is doing this write."""

    operation_id: UUID
    attempt_id: UUID
    owner_token: UUID
    fencing_token: int
    decision_revision: int
    tenant_id: UUID

    @classmethod
    def from_state(cls, state: dict[str, Any]) -> ResumeProvenance | None:
        raw = state.get("resume_provenance") or {}
        if not raw or not raw.get("operation_id"):
            return None
        try:
            return cls(
                operation_id=UUID(str(raw["operation_id"])),
                attempt_id=UUID(str(raw["attempt_id"])),
                owner_token=UUID(str(raw["owner_token"])),
                fencing_token=int(raw["fencing_token"]),
                decision_revision=int(raw["decision_revision"]),
                tenant_id=UUID(str(state["tenant_id"])),
            )
        except (KeyError, ValueError, TypeError):
            logger.warning("hitl_resume_provenance_unparseable", provenance=raw)
            return None


@dataclass(frozen=True)
class AtomicPersistResult:
    analysis_id: UUID
    created: bool


async def persist_resume_analysis_atomically(
    *,
    state: dict[str, Any],
    provenance: ResumeProvenance,
    session_factory: Any = None,
    fault: Any = None,
) -> AtomicPersistResult:
    """Persist every core N17 effect for this operation, or none of them."""
    from src.analysis.adapters.persistence.analysis_repository import (
        SqlAlchemyAnalysisRepository,
    )
    from src.analysis.adapters.persistence.models import Analysis
    from src.analysis.ports.types import AlertWrite, AnalysisWrite
    from src.coherence.alert_generator import AlertGenerator
    from src.modules.hitl.adapters.persistence import resume_ownership
    from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository
    from src.temporal.adapters.persistence.models import ProjectEventORM
    from src.wbs.adapters.persistence.models import WBSNodeORM

    tenant_id = provenance.tenant_id
    project_id = UUID(str(state["project_id"]))
    extracted_risks = state.get("extracted_risks") or []
    extracted_wbs = state.get("extracted_wbs") or []

    ownership = _ownership_view(provenance)

    async with _session(session_factory, tenant_id) as session:
        # 1-2. Authority, serialised on the operation row itself.
        await resume_ownership.verify_in_transaction(session, ownership)

        # 3. Serialise canonical WBS replacement against concurrent writers
        # for the same project (ADR-025: one canonical WBS per project).
        await session.execute(
            text("SELECT id FROM projects WHERE id = cast(:p as uuid) FOR UPDATE"),
            {"p": str(project_id)},
        )

        # 4-5. Operation-keyed detection. This -- not a project-wide lookup --
        # is what makes a replay of THIS operation a no-op while leaving
        # legitimate other analyses of the same project alone.
        existing = (
            await session.execute(
                select(Analysis.id).where(
                    Analysis.resume_operation_id == provenance.operation_id
                )
            )
        ).scalars().first()
        if existing is not None:
            logger.info(
                "hitl_resume_n17_already_durable",
                operation_id=str(provenance.operation_id),
                analysis_id=str(existing),
            )
            return AtomicPersistResult(analysis_id=existing, created=False)

        # 6. First execution: every core effect, one transaction.
        analysis_id = uuid4()
        completed_at = datetime.now(UTC).replace(tzinfo=None)
        analysis_type = AnalysisType.RISK if extracted_risks else AnalysisType.SCHEDULE
        repo = SqlAlchemyAnalysisRepository(session)

        await repo.add_analysis(
            AnalysisWrite(
                id=analysis_id,
                tenant_id=tenant_id,
                project_id=project_id,
                analysis_type=analysis_type,
                status=AnalysisStatus.COMPLETED,
                coherence_score=state.get("coherence_score"),
                coherence_breakdown=state.get("coherence_breakdown") or {},
                alerts_count=len(extracted_risks),
                completed_at=completed_at,
                result_json={
                    "risks": extracted_risks,
                    "wbs": extracted_wbs,
                    **(state.get("single_document_assessment") or {}),
                },
                resume_operation_id=provenance.operation_id,
                resume_attempt_id=provenance.attempt_id,
                fencing_token=provenance.fencing_token,
                decision_revision=provenance.decision_revision,
            ),
            tenant_id=tenant_id,
        )
        await repo.flush()
        if fault is not None:
            await fault("after_analysis")

        if extracted_risks:
            generator = AlertGenerator(project_id=project_id, analysis_id=analysis_id)
            await repo.add_alerts(
                [
                    AlertWrite(
                        tenant_id=tenant_id,
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
                    for dto in generator.generate_risk_alerts(extracted_risks)
                ],
                tenant_id=tenant_id,
            )
            await repo.flush()
        if fault is not None:
            await fault("after_alerts")

        if extracted_wbs:
            await session.execute(
                delete(WBSNodeORM).where(
                    WBSNodeORM.project_id == project_id,
                    WBSNodeORM.tenant_id == tenant_id,
                )
            )
            await SQLAlchemyWBSRepository(session).bulk_create_from_dicts(
                project_id, extracted_wbs, tenant_id
            )
            await session.flush()
        if fault is not None:
            await fault("after_wbs")

        # The core event is part of THIS transaction. The partial unique
        # index on (resume_operation_id, event_type) is the durable guard
        # against a duplicate for the same operation.
        now = datetime.now(UTC).replace(tzinfo=None)
        # Inserted WITH its provenance in one statement. An append-then-
        # update would be wrong twice over: the update could match other
        # operations' events for the same project and collide on the
        # partial unique index, and it would briefly leave the row
        # unattributed inside the transaction.
        session.add(
            ProjectEventORM(
                event_id=uuid4(),
                project_id=project_id,
                tenant_id=tenant_id,
                event_type=ANALYSIS_PERSISTED_EVENT,
                payload={
                    "analysis_id": str(analysis_id),
                    "document_id": state.get("document_id"),
                    "resume_operation_id": str(provenance.operation_id),
                    "resume_attempt_id": str(provenance.attempt_id),
                    "fencing_token": provenance.fencing_token,
                    "decision_revision": provenance.decision_revision,
                },
                actor="analysis_graph",
                evidence_refs=[],
                occurred_at=now,
                created_at=now,
                resume_operation_id=provenance.operation_id,
                resume_attempt_id=provenance.attempt_id,
            )
        )
        await session.flush()
        if fault is not None:
            await fault("after_event")

        await session.execute(
            text(
                "UPDATE resume_operations "
                "   SET analysis_id = cast(:analysis_id as uuid), "
                "       phase = 'N17_DURABLE', updated_at = clock_timestamp() "
                " WHERE id = cast(:op as uuid) "
                "   AND current_attempt_id = cast(:att as uuid) "
                "   AND fencing_token = cast(:fence as bigint)"
            ),
            {
                "analysis_id": str(analysis_id),
                "op": str(provenance.operation_id),
                "att": str(provenance.attempt_id),
                "fence": provenance.fencing_token,
            },
        )
        if fault is not None:
            await fault("after_phase")

        # 7. COMMIT ONCE -- performed by the session context manager.

    logger.info(
        "hitl_resume_n17_durable",
        operation_id=str(provenance.operation_id),
        attempt_id=str(provenance.attempt_id),
        analysis_id=str(analysis_id),
    )
    return AtomicPersistResult(analysis_id=analysis_id, created=True)


def _ownership_view(provenance: ResumeProvenance) -> Any:
    """Minimal Ownership for the in-transaction authority check."""
    from src.modules.hitl.adapters.persistence.resume_ownership import Ownership, Phase

    return Ownership(
        operation_id=provenance.operation_id,
        attempt_id=provenance.attempt_id,
        owner_token=provenance.owner_token,
        fencing_token=provenance.fencing_token,
        decision_revision=provenance.decision_revision,
        tenant_id=provenance.tenant_id,
        review_row_id=provenance.operation_id,  # unused by the check
        decision="",
        phase=Phase.RUNNING,
        source_checkpoint_id=None,
        terminal_checkpoint_id=None,
        analysis_id=None,
        project_id=None,
        document_id=None,
        failure_count=0,
    )


def _session(session_factory: Any, tenant_id: UUID) -> Any:
    if session_factory is not None:
        return session_factory(tenant_id)
    from src.core.database import get_session_with_tenant

    return get_session_with_tenant(tenant_id)
