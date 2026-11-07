"""Celery tasks for ADR-017 ProjectGraph execution.

TS-UT-ADR017-TRG-001
"""

from __future__ import annotations

import hashlib
import inspect
import json
import logging
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, text

from src.analysis.adapters.graph.project_graph import (
    build_project_graph,
    is_project_graph_enabled,
)
from src.analysis.adapters.graph.project_graph_state import ProjectGraphState
from src.analysis.adapters.persistence.document_artifact_repository import (
    SqlAlchemyDocumentArtifactRepository,
)
from src.analysis.adapters.persistence.trusted_artifact_graph_materializer import (
    SqlAlchemyTrustedArtifactGraphMaterializer,
)
from src.analysis.ports.document_artifact_repository import IDocumentArtifactRepository
from src.core.database import get_raw_session, init_db
from src.core.dlq.dlq_service import DLQService
from src.core.tasks.async_runtime import run_async_db_task
from src.core.tasks.celery_app import celery_app
from src.core.tasks.project_graph_governance import ProjectGraphGovernance
from src.core.tenants.types import TenantId, require_tenant_id
from src.temporal.adapters.persistence.project_snapshot_repository import (
    SqlAlchemyProjectSnapshotRepository,
)

logger = logging.getLogger(__name__)


async def _maybe_await(value: object) -> None:
    if inspect.isawaitable(value):
        await value


async def enqueue_project_graph(
    *,
    project_id: UUID,
    tenant_id: UUID,
    trigger_event_id: UUID | None = None,
    governance: ProjectGraphGovernance | None = None,
) -> None:
    if not await is_project_graph_enabled(tenant_id):
        return
    active_governance = governance or ProjectGraphGovernance()
    if not await active_governance.should_enqueue_project(project_id):
        return
    run_project_graph.delay(
        project_id=str(project_id),
        tenant_id=str(tenant_id),
        trigger_event_id=str(trigger_event_id) if trigger_event_id else None,
    )


def summarize_canonical_source_revisions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Summarize only revision-bound XLSX observations, never promote to baselines."""
    groups: dict[tuple[str, str, str, str], int] = defaultdict(int)
    for row in rows:
        family = str(row.get("family") or "")
        document_id = str(row.get("document_id") or "")
        revision_id = str(row.get("revision_id") or "")
        blob_hash = str(row.get("blob_hash") or "")
        if family not in {"budget", "schedule"} or not document_id or not revision_id or not blob_hash:
            continue
        groups[(family, document_id, revision_id, blob_hash)] += 1
    return [
        {
            "family": family,
            "document_id": doc,
            "revision_id": revision,
            "blob_sha256": digest,
            "observed_rows": count,
            "role": "source_observation_only_not_approved_baseline",
        }
        for (family, doc, revision, digest), count in sorted(groups.items())
    ]


async def persist_provisional_source_discrepancies(
    session: Any, *, project_id: UUID, tenant_id: TenantId,
    comparison: dict[str, Any] | None,
) -> bool:
    """Append only changed source-cited observations; NEVER canonical alerts/scores.

    Uses project + tenant scoped latest-event lookup, and the ProjectGraph
    transaction owns the commit. Exact repeat runs produce no duplicate event.
    """
    findings = (comparison or {}).get("findings")
    if not isinstance(findings, list) or not findings:
        return False
    if any(
        item.get("state") != "PROVISIONAL" or item.get("scored") is not False
        or len(item.get("sources") or []) != 2
        for item in findings
    ):
        raise ValueError("SOURCE_DISCREPANCY_MUST_BE_PROVISIONAL_AND_BI_SOURCED")
    from src.temporal.adapters.persistence.models import ProjectEventORM

    event_type = "project_graph.source_discrepancies_observed"
    encoded = json.dumps(findings, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    fingerprint = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    last = (
        await session.execute(
            select(ProjectEventORM.payload).where(
                ProjectEventORM.project_id == project_id,
                ProjectEventORM.tenant_id == tenant_id,
                ProjectEventORM.event_type == event_type,
            ).order_by(ProjectEventORM.occurred_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if isinstance(last, dict) and last.get("fingerprint") == fingerprint:
        return False

    references = [
        {
            "document_id": source["document_id"],
            "revision_id": source["revision_id"],
            "source_locator": source["source_locator"],
            "role": source["role"],
            **({"unit_sha256": source["unit_sha256"]} if source.get("unit_sha256") else {}),
            **({"blob_sha256": source["blob_sha256"]} if source.get("blob_sha256") else {}),
            **({"source_quote_sha256": source["source_quote_sha256"]} if source.get("source_quote_sha256") else {}),
        }
        for finding in findings for source in finding["sources"]
    ]
    now = datetime.now(UTC).replace(tzinfo=None)
    session.add(ProjectEventORM(
        project_id=project_id, tenant_id=tenant_id, event_type=event_type,
        payload={
            "state": "PROVISIONAL", "scoring_policy": "not_scored",
            "requires_human_review": True, "fingerprint": fingerprint,
            "findings": findings,
        },
        evidence_refs=references, actor="project_graph_source_comparator",
        occurred_at=now, created_at=now,
    ))
    await session.flush()
    return True


async def run_project_graph_once(
    *,
    project_id: UUID,
    tenant_id: TenantId,
    artifact_repository: IDocumentArtifactRepository,
    trigger_event_id: UUID | None = None,
    structured_source_refs: list[dict[str, Any]] | None = None,
    structured_source_units: list[dict[str, Any]] | None = None,
    structured_document_quotes: list[dict[str, Any]] | None = None,
    snapshot_repository: Any | None = None,
    knowledge_graph_materializer: Any | None = None,
    alert_correlation_runner: Any | None = None,
) -> dict[str, object]:
    # #714: canonical input is TRUSTED artifacts only -- never a pending
    # PROPOSED candidate, even when it is the newest row for its document.
    artifacts = await artifact_repository.list_trusted_for_project(
        project_id=project_id,
        tenant_id=tenant_id,
    )
    graph_input: ProjectGraphState = {
        "project_id": project_id,
        "tenant_id": tenant_id,
        "trigger_event_id": trigger_event_id,
        "previous_snapshot_id": None,
        "changed_artifact_ids": [],
        "artifacts": artifacts,
        "structured_source_refs": list(structured_source_refs or []),
        "structured_source_units": list(structured_source_units or []),
        "structured_document_quotes": list(structured_document_quotes or []),
        "coherence_result": None,
        "impact_result": None,
        "health_result": None,
        "snapshot_id": None,
        "node_results": [],
        "artifact_repository": artifact_repository,
    }
    if snapshot_repository is not None:
        graph_input["snapshot_repository"] = snapshot_repository
    if alert_correlation_runner is not None:
        graph_input["alert_correlation_runner"] = alert_correlation_runner
    result = await build_project_graph().ainvoke(graph_input)
    failed_nodes = [
        node.node
        for node in result.get("node_results", [])
        if getattr(node, "status", None).value == "failed"
    ]
    if failed_nodes:
        raise RuntimeError(f"ProjectGraph execution failed: {', '.join(failed_nodes)}")
    if snapshot_repository is not None and artifacts and result.get("snapshot_id") is None:
        raise RuntimeError("ProjectGraph snapshot missing; trusted projection not acknowledged")
    graph_materialization: dict[str, int] | None = None
    if knowledge_graph_materializer is not None:
        materialized = await knowledge_graph_materializer.materialize_trusted_artifacts(
            project_id=project_id,
            tenant_id=tenant_id,
            artifacts=artifacts,
        )
        graph_materialization = {
            "node_count": materialized.node_count,
            "edge_count": materialized.edge_count,
        }
    # #714: acknowledge the durable trusted -> ProjectGraph obligations of
    # exactly the artifacts this completed run loaded. The caller commits it
    # together with the run; a failed run rolls it back and stays pending.
    mark_projected = getattr(artifact_repository, "mark_loaded_projected", None)
    projected = (
        await mark_projected(project_id=project_id, tenant_id=tenant_id)
        if mark_projected is not None
        else 0
    )
    return {
        "status": "ok",
        "projected_obligations": projected,
        "artifact_count": len(artifacts),
        "structured_source_revision_count": len(structured_source_refs or []),
        "structured_source_comparison": result.get("structured_source_comparison"),
        "snapshot_id": str(result["snapshot_id"]) if result.get("snapshot_id") else None,
        "knowledge_graph_materialization": graph_materialization,
        "node_result_count": len(result.get("node_results", [])),
        "coherence_result": _serializable(result.get("coherence_result")),
        "node_results": result.get("node_results", []),
    }


def _serializable(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


async def _run_project_graph_async(
    *,
    project_id: UUID,
    tenant_id: TenantId,
    trigger_event_id: UUID | None = None,
    governance: ProjectGraphGovernance | None = None,
) -> dict[str, object]:
    active_governance = governance or ProjectGraphGovernance()
    if not await active_governance.acquire_tenant_slot(tenant_id):
        run_project_graph.apply_async(
            kwargs={
                "project_id": str(project_id),
                "tenant_id": str(tenant_id),
                "trigger_event_id": str(trigger_event_id) if trigger_event_id else None,
            },
            countdown=active_governance.requeue_countdown_seconds,
        )
        return {"status": "requeued", "artifact_count": 0, "node_result_count": 0}

    await _maybe_await(init_db())
    try:
        async with get_raw_session() as session:
            try:
                await session.execute(text(f"SET LOCAL app.current_tenant = '{tenant_id}'"))
                from src.documents.application.structured_source_units import (
                    load_canonical_source_units,
                )

                # Read canonical immutable source revisions through their own
                # tenant-scoped provenance seam. Never create DocumentArtifact
                # or ProjectGraph materialization obligations from these rows.
                rows: list[dict[str, Any]] = []
                for family in ("budget", "schedule"):
                    rows.extend(
                        await load_canonical_source_units(
                            session=session,
                            tenant_id=tenant_id,
                            project_id=project_id,
                            family=family,
                        )
                    )
                source_refs = summarize_canonical_source_revisions(rows)
                from src.analysis.adapters.graph.source_clause_evidence import (
                    load_revision_bound_source_quotes,
                )
                quotes = await load_revision_bound_source_quotes(
                    session=session, tenant_id=tenant_id, project_id=project_id,
                )
                result = await run_project_graph_once(
                    project_id=project_id,
                    tenant_id=tenant_id,
                    trigger_event_id=trigger_event_id,
                    artifact_repository=SqlAlchemyDocumentArtifactRepository(session),
                    structured_source_refs=source_refs,
                    structured_source_units=rows,
                    structured_document_quotes=quotes,
                    snapshot_repository=SqlAlchemyProjectSnapshotRepository(session),
                    knowledge_graph_materializer=SqlAlchemyTrustedArtifactGraphMaterializer(session),
                )
                # Persist only PROVISIONAL, dual-source citations in the same
                # transaction as Tier-2. No promotion to canonical alerts.
                await persist_provisional_source_discrepancies(
                    session, project_id=project_id, tenant_id=tenant_id,
                    comparison=result.get("structured_source_comparison"),
                )
                await session.commit()
                await active_governance.clear_project_pending(project_id)
                return result
            except Exception:
                await session.rollback()
                logger.exception(
                    "project_graph_run_failed",
                    extra={
                        "project_id": str(project_id),
                        "tenant_id": str(tenant_id),
                        "trigger_event_id": str(trigger_event_id) if trigger_event_id else None,
                    },
                )
                raise
    finally:
        await active_governance.release_tenant_slot(tenant_id)


async def record_project_graph_dead_letter(
    *,
    project_id: UUID,
    tenant_id: TenantId,
    trigger_event_id: UUID | None,
    error: Exception,
) -> UUID:
    return await DLQService().push(
        tenant_id=tenant_id,
        task_type="project_graph.run",
        document_id=None,
        payload={
            "project_id": str(project_id),
            "tenant_id": str(tenant_id),
            "trigger_event_id": str(trigger_event_id) if trigger_event_id else None,
        },
        error_message=str(error),
        error_traceback=None,
        max_retries=0,
    )


async def _record_project_graph_dead_letter_with_db(
    *,
    project_id: UUID,
    tenant_id: TenantId,
    trigger_event_id: UUID | None,
    error: Exception,
) -> UUID:
    await _maybe_await(init_db())
    return await record_project_graph_dead_letter(
        project_id=project_id,
        tenant_id=tenant_id,
        trigger_event_id=trigger_event_id,
        error=error,
    )


@celery_app.task(
    name="project_graph.run",
    bind=True,
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=60,
)
def run_project_graph(
    self: Any,  # noqa: ARG001
    *,
    project_id: str,
    tenant_id: str,
    trigger_event_id: str | None = None,
) -> dict[str, object]:
    project_uuid = UUID(project_id)
    tenant_uuid = require_tenant_id(tenant_id)
    trigger_uuid = UUID(trigger_event_id) if trigger_event_id else None
    try:
        return run_async_db_task(
            _run_project_graph_async(
                project_id=project_uuid,
                tenant_id=tenant_uuid,
                trigger_event_id=trigger_uuid,
            )
        )
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            run_async_db_task(
                _record_project_graph_dead_letter_with_db(
                    project_id=project_uuid,
                    tenant_id=tenant_uuid,
                    trigger_event_id=trigger_uuid,
                    error=exc,
                )
            )
            raise
        raise self.retry(exc=exc, countdown=60) from exc


__all__ = [
    "enqueue_project_graph",
    "record_project_graph_dead_letter",
    "run_project_graph",
    "run_project_graph_once",
]


# -- #714 durable trusted -> ProjectGraph reconciliation ------------------------

RECONCILE_BATCH_SIZE = 50
RECONCILE_GRACE_SECONDS = 120
MAX_RECONCILE_ENQUEUES = 12

_PENDING_PROJECTIONS_SQL = text(
    """
    SELECT tenant_id, project_id,
           max(enqueue_attempts) AS attempts,
           min(coalesce(last_checked_at, created_at)) AS oldest
      FROM system_recovery.trusted_projection_index
     WHERE projection_state = 'pending'
       AND created_at <= (clock_timestamp() AT TIME ZONE 'UTC')
                          - make_interval(secs => :grace)
     GROUP BY tenant_id, project_id
     ORDER BY oldest
     LIMIT :limit
    """
)

_TOUCH_PENDING_SQL = text(
    """
    UPDATE system_recovery.trusted_projection_index
       SET last_checked_at = (clock_timestamp() AT TIME ZONE 'UTC'),
           enqueue_attempts = enqueue_attempts + :increment
     WHERE tenant_id = cast(:tenant_id as uuid)
       AND project_id = cast(:project_id as uuid)
       AND projection_state = 'pending'
    """
)


async def reconcile_trusted_projections(
    *,
    batch_size: int = RECONCILE_BATCH_SIZE,
    grace_seconds: int = RECONCILE_GRACE_SECONDS,
) -> dict[str, int]:
    """Re-dispatch trusted commits whose ProjectGraph projection was lost.

    Scans only the internal system_recovery routing table (no business rows,
    no RLS bypass). A pending obligation older than the fast-path grace is
    re-enqueued through the normal ``enqueue_project_graph``; it is only
    ever cleared by a completed ProjectGraph run (``mark_loaded_projected``).
    Flag-disabled tenants are skipped without being marked projected, and
    repeated failures stop after ``MAX_RECONCILE_ENQUEUES`` so a broken
    project cannot turn into a retry storm -- the obligation stays pending
    as durable operator evidence.
    """
    counts = {"scanned": 0, "enqueued": 0, "flag_disabled": 0, "exhausted": 0}
    await _maybe_await(init_db())
    async with get_raw_session() as session:
        rows = (
            await session.execute(
                _PENDING_PROJECTIONS_SQL, {"grace": grace_seconds, "limit": batch_size}
            )
        ).all()
        for row in rows:
            counts["scanned"] += 1
            tenant_id = require_tenant_id(str(row.tenant_id))
            project_id = UUID(str(row.project_id))
            increment = 0
            if int(row.attempts) >= MAX_RECONCILE_ENQUEUES:
                counts["exhausted"] += 1
                logger.error(
                    "trusted_projection_reconcile_exhausted",
                    extra={"project_id": str(project_id), "tenant_id": str(tenant_id)},
                )
            elif not await is_project_graph_enabled(tenant_id):
                counts["flag_disabled"] += 1
            else:
                await enqueue_project_graph(project_id=project_id, tenant_id=tenant_id)
                counts["enqueued"] += 1
                increment = 1
            await session.execute(
                _TOUCH_PENDING_SQL,
                {"tenant_id": str(tenant_id), "project_id": str(project_id), "increment": increment},
            )
        await session.commit()
    logger.info("trusted_projection_reconcile", extra=counts)
    return counts


@celery_app.task(name="project_graph.reconcile_trusted_projections")
def reconcile_trusted_projections_task() -> dict[str, int]:
    return run_async_db_task(reconcile_trusted_projections())
