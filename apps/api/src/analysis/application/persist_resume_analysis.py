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
    lock project row                          -- serialise canonical writes
    detect existing analysis BY resume_operation_id
      -> if present: return it; repeat NOTHING
    approve: promote the exact bound candidate (#714)
    materialize it (C3b-1 trusted_materialization: stale guard, analysis
         + alerts, keyed by artifact_id; WBS deferred to governance)
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
from sqlalchemy import select, text

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
    from src.analysis.adapters.persistence.models import Analysis
    from src.analysis.application import trusted_materialization as materializer
    from src.analysis.domain.trust import StaleCandidateError
    from src.modules.hitl.adapters.persistence import resume_ownership
    from src.temporal.adapters.persistence.models import ProjectEventORM

    tenant_id = provenance.tenant_id
    project_id = UUID(str(state["project_id"]))
    document_id = _uuid_or_none(state.get("document_id"))

    ownership = _ownership_view(provenance)

    async with _session(session_factory, tenant_id) as session:
        # 0. Canonical cross-aggregate lock order (finalize_v3, C3b-1):
        # DOCUMENT before RESUME_OPERATION, so the materializer's stale guard
        # runs with the document serialised and no inverse edge exists.
        if document_id is not None:
            await materializer.lock_document(
                session, tenant_id=tenant_id, document_id=document_id
            )

        # 1-2. Authority, serialised on the operation row itself.
        operation = await resume_ownership.verify_in_transaction(session, ownership)

        # 3. Serialise canonical writes against concurrent writers for the
        # same project (ADR-025: one canonical WBS per project).
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

        # #714: persisted != trusted. An approved decision promotes its exact
        # bound candidate in THIS transaction (leaving a pending, artifact-
        # keyed materialization obligation, C3b-1), so the canonical effects
        # below can never land without the trusted transition; a stale or
        # superseded binding rolls all of them back.
        commit = await resume_ownership.commit_trust_in_transaction(
            session, tenant_id=tenant_id, operation=operation
        )

        # 6. First execution: the ONE canonical materializer, same transaction.
        content = materializer.MaterializationContent.from_state(state)
        link = materializer.ResumeLink(
            operation_id=provenance.operation_id,
            attempt_id=provenance.attempt_id,
            fencing_token=provenance.fencing_token,
            decision_revision=provenance.decision_revision,
        )
        created = True
        if commit is not None:
            outcome = await materializer.materialize_in_transaction(
                session,
                ref=materializer.ArtifactRef(
                    artifact_id=commit.binding.artifact_id,
                    document_id=commit.binding.document_id,
                    artifact_version=commit.binding.artifact_version,
                    artifact_hash=commit.binding.artifact_hash,
                    project_id=commit.project_id,
                    tenant_id=tenant_id,
                ),
                content=content,
                resume=link,
                actor="analysis_graph",
                fault=fault,
            )
            if outcome.status is materializer.MaterializationStatus.OBSOLETE:
                # The approved artifact is not the trusted-current one: the
                # approval fails closed and the trust commit rolls back too.
                raise StaleCandidateError(
                    f"Approved candidate {commit.binding.artifact_id} is not the "
                    f"trusted-current artifact ({outcome.reason}); refusing to materialize"
                )
            assert outcome.analysis_id is not None
            analysis_id = outcome.analysis_id
            created = outcome.status is materializer.MaterializationStatus.CREATED
        else:
            # Pre-#714 review: nothing was proposed or bound, so there is no
            # artifact identity -- same core effects, no obligation.
            analysis_id, _ = await materializer.write_canonical_effects(
                session,
                tenant_id=tenant_id,
                project_id=project_id,
                content=content,
                source_artifact_id=None,
                resume=link,
                fault=fault,
            )

        # The core event is part of THIS transaction. The partial unique
        # index on (resume_operation_id, event_type) is the durable guard
        # against a duplicate for the same operation. An artifact this
        # operation found already materialized gets no second event.
        now = datetime.now(UTC).replace(tzinfo=None)
        if created:
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
    return AtomicPersistResult(analysis_id=analysis_id, created=created)


def _uuid_or_none(value: Any) -> UUID | None:
    try:
        return UUID(str(value)) if value else None
    except ValueError:
        return None


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
