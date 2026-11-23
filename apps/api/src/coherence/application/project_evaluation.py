"""JV1-A17 post-approval coherence evaluation (draft, stacked on A15).

All scheduling requires a completed human approval and an explicitly bound tenant.
The background task opens a fresh tenant-scoped DB session; it never reuses the
HTTP request session. The evaluation uses deterministic low-budget mode.
"""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from hashlib import blake2b
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import structlog
from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.coherence.adapters.persistence.models import CoherenceResultORM
from src.coherence.adapters.persistence.withheld_evaluation import record_withheld_evaluation
from src.coherence.application.disposition_review import build_scoring_snapshot
from src.coherence.domain.v2_constants import SCORE_VERSION_V1
from src.coherence.graph.nodes import v1_unassessed_reasons
from src.coherence.graph.state import EvaluationConfig
from src.core.database import get_session_with_tenant
from src.modules.hitl.domain.entities import ReviewStatus
from src.projects.adapters.persistence.models import ProjectORM

logger = structlog.get_logger()


def queue_post_approval_evaluation(
    background_tasks: BackgroundTasks,
    *,
    review: Any,
    tenant_id: UUID,
    actor_user_id: UUID,
    newly_approved: bool,
) -> bool:
    """Only a *new* completed approval may request a project recalculation.

    Project identity is read from the authoritative server-resolved review,
    never from the HTTP client's approval payload. A contradictory tenant ID
    in the review fails closed.
    """
    if not newly_approved:
        return False
    review_status = getattr(review, "current_status", None)
    if review_status not in (ReviewStatus.APPROVED, ReviewStatus.APPROVED.value):
        return False

    metadata = getattr(review, "metadata", None) or {}
    item_data = getattr(review, "item_data", None) or {}
    if not isinstance(metadata, dict) or not isinstance(item_data, dict):
        return False

    try:
        recorded_tenants = [
            UUID(str(raw))
            for raw in (metadata.get("tenant_id"), item_data.get("tenant_id"))
            if raw is not None
        ]
        if any(recorded != tenant_id for recorded in recorded_tenants):
            logger.warning("a17_evaluation_refused_tenant_mismatch")
            return False

        recorded_projects = [
            UUID(str(raw))
            for raw in (metadata.get("project_id"), item_data.get("project_id"))
            if raw is not None
        ]
        if not recorded_projects or len(set(recorded_projects)) != 1:
            logger.warning("a17_evaluation_refused_project_conflict")
            return False
        project_id = recorded_projects[0]
    except (TypeError, ValueError, AttributeError):
        logger.warning("a17_evaluation_refused_invalid_identity")
        return False

    review_key = metadata.get("row_id") or getattr(review, "item_id", None)
    try:
        review_id = UUID(str(review_key))
    except (TypeError, ValueError, AttributeError):
        logger.warning("a17_evaluation_refused_missing_review_identity")
        return False

    background_tasks.add_task(
        run_project_evaluation_after_approval,
        tenant_id=tenant_id,
        project_id=project_id,
        actor_user_id=actor_user_id,
        review_id=review_id,
    )
    return True


async def _run_evaluation(payload: Any, db: AsyncSession, user: Any, *, review_id: UUID) -> Any:
    """Execute the extracted service in one caller-owned transaction.

    Disable all optional LLM crosschecks and v2 shadow runs; deterministic
    Coherence is evaluated from canonical approved source evidence only.
    """
    from src.coherence.router import _coherence_evaluation_ports

    return await evaluate_coherence_in_application(
        payload,
        include_diagnostics=True,
        db=db,
        current_user=user,
        flags_service=None,
        ports=_coherence_evaluation_ports(),
        auto_commit=False,
        approval_id=str(review_id),
        skip_shadow=True,
        disable_llm=True,
    )


def _approval_lock_key(tenant_id: UUID, project_id: UUID, review_id: UUID) -> int:
    identity = f"jv1-a17:{tenant_id}:{project_id}:{review_id}".encode()
    return int.from_bytes(blake2b(identity, digest_size=8).digest(), "big") & ((1 << 63) - 1)


async def run_project_evaluation_after_approval(
    *, tenant_id: UUID, project_id: UUID, actor_user_id: UUID, review_id: UUID
) -> None:
    """Transaction-fenced exactly-once persistence for an approved review row.

    A transaction-level PostgreSQL advisory lock is acquired before checking
    the committed marker and is held through graph evaluation and commit.
    This is not an in-memory lock; it works across application workers.
    """
    from src.coherence.router import CoherenceEvaluateRequest

    payload = CoherenceEvaluateRequest(
        project_id=project_id,
        low_budget_mode=True,
        include_rag_similarity=False,
    )
    actor = SimpleNamespace(tenant_id=tenant_id, id=actor_user_id)
    try:
        async with get_session_with_tenant(tenant_id) as db:
            await db.execute(
                text("SELECT pg_advisory_xact_lock(:lock_key)"),
                {"lock_key": _approval_lock_key(tenant_id, project_id, review_id)},
            )
            committed = await db.scalar(
                select(CoherenceResultORM.id)
                .where(
                    CoherenceResultORM.tenant_id == tenant_id,
                    CoherenceResultORM.project_id == project_id,
                    CoherenceResultORM.scoring_snapshot["a17_approval_id"].astext == str(review_id),
                )
                .limit(1)
            )
            if committed is not None:
                logger.info("a17_evaluation_skipped_already_persisted")
                return
            # The extracted service must leave commit to the outer transaction,
            # otherwise the advisory lock would be released before the marker.
            await _run_evaluation(payload, db, actor, review_id=review_id)
            # Commit is executed by get_session_with_tenant's context manager
            # after all pending rows and their approval marker are durable.
    except Exception:
        logger.exception("a17_postapproval_evaluation_failed")
        raise
    logger.info("a17_postapproval_evaluation_completed")


@dataclass(frozen=True)
class EvaluationPorts:
    contracts_pending: Any
    contract_withheld_reason: Any
    contract_pending_result: Any
    get_clauses: Any
    schedule_finish: Any
    llm_crosscheck_enabled: Any
    run_graph: Any
    mirror_alerts: Any
    reconciliation_type: Any
    rescore: Any
    annotate_hint: Any
    canonical_canary: Any
    v2_shadow: Any
    v2_enabled: Any
    convert_result: Any


async def evaluate_coherence_in_application(
    payload: Any,
    *,
    include_diagnostics: bool,
    db: AsyncSession,
    current_user: Any,
    flags_service: Any,
    ports: EvaluationPorts,
    auto_commit: bool = True,
    approval_id: str | None = None,
    skip_shadow: bool = False,
    disable_llm: bool = False,
) -> Any:
    """Service-owned coherence graph, alert reconciliation and persistence.
    Router supplies collaborators so old test patch points remain stable.
    """
    _contracts_awaiting_approval = ports.contracts_pending
    _contract_withheld_reason = ports.contract_withheld_reason
    _contract_pending_approval_result = ports.contract_pending_result
    get_clauses_from_rag = ports.get_clauses
    load_schedule_planned_finish = ports.schedule_finish
    coherence_llm_crosscheck_enabled_for_tenant = ports.llm_crosscheck_enabled
    evaluate_coherence_async = ports.run_graph
    _mirror_coherence_alerts_to_alerts_table = ports.mirror_alerts
    _CoherenceAlertReconciliation = ports.reconciliation_type
    _apply_disposition_aware_rescore = ports.rescore
    _annotate_missing_technical_hint = ports.annotate_hint
    _maybe_apply_canonical_canary = ports.canonical_canary
    _run_v2_shadow_on_evaluate = ports.v2_shadow
    _v2_enabled_for = ports.v2_enabled
    _convert_enriched_to_coherence_result = ports.convert_result
    # Determine clauses source
    if payload.clauses:
        clauses = payload.clauses
    elif payload.project_id:
        # S3: a contract that has no canonical/approved current input blocks any
        # relational Coherence Score, even if Budget/Schedule clauses are already
        # searchable. The old check only ran when *no* RAG clauses existed, so it
        # could score unrelated documents before a human approved the contract.
        # A trusted revision A with proposed revision B remains canonical via
        # current_revision_lateral, so normal S6 revision continuity is preserved.
        if await _contracts_awaiting_approval(db, payload.project_id, current_user.tenant_id):
            # Pending (or rejected) is not an evaluation result: do not persist a Score or
            # change the alert register before this human authority decision.
            return _contract_pending_approval_result(
                include_diagnostics,
                await _contract_withheld_reason(db, payload.project_id, current_user.tenant_id),
            )
        clauses = await get_clauses_from_rag(
            db, payload.project_id, current_user.tenant_id, payload.max_chunks
        )
        if not clauses:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No document clauses found. Please upload and parse documents first.",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either project_id or clauses must be provided.",
        )

    logger.info(
        "coherence_evaluate_start",
        clauses_count=len(clauses),
        low_budget_mode=payload.low_budget_mode,
        include_rag_similarity=payload.include_rag_similarity,
        include_diagnostics=include_diagnostics,
    )

    # Resolve the LLM cross-clause depth flag per tenant (default off). Adds a bounded LLM
    # call to detect semantic contradictions between clause pairs; the deterministic floor
    # is always on regardless. Resolved here so the graph node stays free of the flags service.
    llm_crosscheck_enabled = False
    if flags_service is not None and not disable_llm:
        try:
            llm_crosscheck_enabled = await coherence_llm_crosscheck_enabled_for_tenant(
                current_user.tenant_id, flags_service=flags_service
            )
        except Exception:
            logger.warning("coherence_llm_crosscheck_flag_resolution_failed", exc_info=True)

    # Load the project name for the project-identity (LOC-MISMATCH) comparator. Best-effort +
    # RLS-scoped (the session carries the tenant), so it only resolves the caller's own project.
    project_name: str | None = None
    if payload.project_id:
        with suppress(Exception):
            project_name = await db.scalar(
                select(ProjectORM.name).where(ProjectORM.id == payload.project_id)
            )

    # The schedule's observed planned finish (with its document/revision/row identity) for the
    # contract-completion comparator. Best-effort: a failure leaves the comparison absent.
    schedule_planned_finish: dict[str, Any] | None = None
    schedule_assessable = True
    if payload.project_id:
        try:
            schedule_planned_finish = await load_schedule_planned_finish(
                db, payload.project_id, current_user.tenant_id
            )
        except Exception:
            logger.warning("coherence_schedule_planned_finish_load_failed", exc_info=True)
            schedule_assessable = False
        # A schedule the comparison could not read (stale revision stamp, several schedules, malformed
        # observation) was not evaluated: that is not "fixed", so nothing may be auto-resolved.
        if isinstance(schedule_planned_finish, dict) and "reason" in schedule_planned_finish:
            schedule_assessable = False

    # Create evaluation config
    config = EvaluationConfig(
        low_budget_mode=payload.low_budget_mode,
        include_rag_similarity=payload.include_rag_similarity,
        llm_crosscheck_enabled=llm_crosscheck_enabled,
        tenant_id=str(current_user.tenant_id),
        project_id=str(payload.project_id) if payload.project_id else None,
        project_name=project_name,
        schedule_planned_finish=schedule_planned_finish,
    )

    # Evaluate using LangGraph subgraph
    enriched_result = await evaluate_coherence_async(
        clauses=clauses,
        project_id=str(payload.project_id) if payload.project_id else "manual",
        config=config,
    )

    logger.info(
        "coherence_detection_complete",
        alerts_count=len(enriched_result.alerts),
        overall_score=enriched_result.overall_score,
    )
    detected_result = enriched_result
    reconciliation: _CoherenceAlertReconciliation | None = None

    # B1-09: durable human disposition is part of the scoring input authority.
    # Reconcile first (same transaction), then re-score the complete FindingSignals.
    # A validated false positive is excluded; ACKNOWLEDGED/accepted variance remains.
    # An incomplete audit may still surface evidence-backed findings. Preserve those
    # in the Alert ledger without inventing a score or auto-resolving older findings
    # that cannot be reassessed from the incomplete evidence.
    if payload.project_id and (enriched_result.overall_score is not None or enriched_result.alerts):
        reconciliation = await _mirror_coherence_alerts_to_alerts_table(
            db=db,
            project_id=payload.project_id,
            tenant_id=current_user.tenant_id,
            alerts=enriched_result.alerts,
            clauses=clauses,
            auto_resolve=enriched_result.overall_score is not None,
            evaluation_complete=schedule_assessable,
        )
        if enriched_result.overall_score is not None and isinstance(
            reconciliation, _CoherenceAlertReconciliation
        ):
            enriched_result = _apply_disposition_aware_rescore(
                enriched_result,
                reconciliation,
                clauses=clauses,
                config=config,
            )

    # Referenced-but-missing hint: if the technical dimension was withheld for lack
    # of evidence but the documents reference a technical specifications pliego, tell
    # the user what to upload — honest and actionable, never a fabricated score.
    _annotate_missing_technical_hint(enriched_result, clauses)

    # ADR-017 canary runs only after B1 disposition filtering so both scorers see
    # the same eligible finding set.
    enriched_result = await _maybe_apply_canonical_canary(
        enriched_result, tenant_id=current_user.tenant_id, flags_service=flags_service
    )

    logger.info(
        "coherence_evaluate_complete",
        alerts_count=len(enriched_result.alerts),
        findings_count=len(enriched_result.finding_signals),
        overall_score=enriched_result.overall_score,
        score_version=enriched_result.score_version,
    )

    # Persist result so the dashboard always reflects the latest evaluation.
    # Keep the exact detected FindingSignals and their identity basis so a later
    # validated false-positive review can replay the same scorer/version.
    if payload.project_id and enriched_result.overall_score is not None:
        scoring_snapshot = None
        if isinstance(reconciliation, _CoherenceAlertReconciliation):
            scoring_snapshot = build_scoring_snapshot(
                detected_result=detected_result,
                finding_keys_by_alert_index=reconciliation.finding_keys_by_alert_index,
                records_by_finding_key=reconciliation.records_by_finding_key,
                clauses=list(clauses),
                config=config,
                score_version=enriched_result.score_version or SCORE_VERSION_V1,
            )
        if approval_id is not None:
            scoring_snapshot = dict(scoring_snapshot or {})
            scoring_snapshot["a17_approval_id"] = approval_id
        # Normalize legacy "SCHEDULE"→"TIME" so dashboard sub_scores keys match COHERENCE_CATEGORIES
        _CAT_ALIAS = {"SCHEDULE": "TIME", "FINANCIAL": "BUDGET", "GENERAL": "SCOPE"}

        def _norm_cat(cat: str) -> str:
            key = cat.upper()
            return _CAT_ALIAS.get(key, key)

        category_scores = {
            _norm_cat(item.category): item.score for item in enriched_result.category_breakdown
        }
        category_details = [
            {
                "category": _norm_cat(item.category),
                "score": item.score,
                "alert_count": item.alert_count,
                "severity_breakdown": dict(item.severity_breakdown)
                if item.severity_breakdown
                else {},
                "impact_percentage": item.impact_percentage,
            }
            for item in enriched_result.category_breakdown
        ]
        alerts_data = [
            {
                "rule_id": a.rule_id,
                "severity": a.severity,
                "category": a.category,
                "message": a.message,
                "evidence": (
                    {
                        "source_clause_id": a.evidence.source_clause_id,
                        "claim": a.evidence.claim,
                        "quote": a.evidence.quote,
                    }
                    if a.evidence
                    else None
                ),
            }
            for a in enriched_result.alerts
        ]
        db.add(
            CoherenceResultORM(
                project_id=payload.project_id,
                tenant_id=current_user.tenant_id,
                global_score=round(enriched_result.overall_score),
                category_scores=category_scores,
                category_details=category_details,
                alerts=alerts_data,
                score_version=enriched_result.score_version or SCORE_VERSION_V1,
                score_reason=enriched_result.score_reason,
                score_missing_dimensions=enriched_result.score_missing_dimensions,
                scoring_snapshot=scoring_snapshot,
            )
        )
        # Alert lifecycle was reconciled before scoring with commit=False.
        # This one commit makes the disposition-aware score and Alert state durable together.
        if auto_commit:
            await db.commit()
    elif payload.project_id and (reconciliation is not None or enriched_result.score_reason):
        # A scoreless evaluation can still contain actionable findings. Persist the
        # alert ledger without creating a fake CoherenceResult or changing trusted
        # score authority. auto_resolve=False preserves older human dispositions.
        # S3: its REASON is kept as an append-only withheld-evaluation event so the persisted
        # dashboard can repeat it after a reload or a new login (never a number in its place).
        await record_withheld_evaluation(
            db,
            project_id=payload.project_id,
            tenant_id=current_user.tenant_id,
            actor_user_id=getattr(current_user, "id", None),
            reason=enriched_result.score_reason,
            missing_dimensions=list(enriched_result.score_missing_dimensions or []),
            score_version=enriched_result.score_version,
            alert_count=len(enriched_result.alerts),
        )
        if auto_commit:
            await db.commit()

    # V2 shadow: run real CoherenceV2Orchestrator and emit delta event.
    # Guard mirrors _maybe_add_v2_dashboard: only fires when both flags are True.
    # Never raises — failures are caught so the V1 response is unaffected.
    # TASK-COH-V2-WIRE-ORCHESTRATOR
    if payload.project_id and not skip_shadow:
        from src.config import get_settings  # local import — avoids circular dep

        _settings = get_settings()
        if await _v2_enabled_for(current_user.tenant_id, flags_service) and getattr(
            _settings, "coherence_v2_shadow_mode", True
        ):
            await _run_v2_shadow_on_evaluate(
                v1_result=enriched_result,
                project_id=payload.project_id,
                tenant_id=current_user.tenant_id,
                db=db,
                withheld_categories=v1_unassessed_reasons(clauses, enriched_result),
            )

    # Return diagnostics if requested (Task 7.4)
    if include_diagnostics:
        return enriched_result

    # Otherwise return backward-compatible response (Task 7.3)
    return _convert_enriched_to_coherence_result(enriched_result)
