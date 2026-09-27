"""Bounded recovery for documents abandoned by async worker loss.

Issue #711 / #706: a worker crash must not leave a document in processing forever.
The primary ingestion guarantee is Celery late-ACK redelivery. This periodic
reconciler is the durable backstop for broker/enqueue loss and for analysis
tasks, which intentionally do not use late ACK until mid-graph replay is proven
safe.

The sweep is deliberately conservative:
- only stale PARSING / PARSED_PENDING_ANALYSIS documents are candidates;
- pending HITL review is never treated as abandoned work;
- every candidate is rechecked under its own tenant and a row lock;
- attempts are bounded per document generation and processing stage;
- provider misconfiguration fails to an explicit retryable ERROR instead of
  burning transient retries forever.
"""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from enum import StrEnum
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import text

from src.core.tasks.celery_app import celery_app
from src.documents.domain.models import DocumentStatus
from src.documents.ports.rag_ingestion_service import RagIngestionOutcome

logger = structlog.get_logger()

DEFAULT_BATCH_SIZE = 20
DEFAULT_STALE_AFTER_SECONDS = 900
MAX_RECOVERY_ATTEMPTS = 3
RECOVERY_METADATA_KEY = "processing_recovery"

_RECOVERABLE_STATUSES = (
    DocumentStatus.PARSING.value,
    DocumentStatus.PARSED_PENDING_ANALYSIS.value,
)

_SCAN_SQL = text(
    """
    SELECT document_id AS id, tenant_id
      FROM system_recovery.list_stale_document_candidates(
          :stale_after,
          :limit
      )
    """
)

_CLAIM_SQL = text(
    """
    SELECT d.id,
           d.tenant_id,
           d.upload_status::text AS upload_status,
           d.document_metadata,
           d.version,
           (
               SELECT r.revision_id
                 FROM document_revisions r
                WHERE r.document_id = d.id
                  AND r.tenant_id = d.tenant_id
                  AND r.valid_to IS NULL
                ORDER BY r.rev_no DESC
                LIMIT 1
           ) AS current_revision_id,
           EXISTS (
               SELECT 1
                 FROM review_items ri
                WHERE ri.document_id = d.id
                  AND ri.tenant_id = d.tenant_id
                  AND ri.current_status::text IN (
                      'PENDING_REVIEW_REQUIRED',
                      'PENDING_REVIEW_CONDITIONAL',
                      'ESCALATED'
                  )
           ) AS hitl_pending
      FROM documents d
     WHERE d.id = CAST(:document_id AS uuid)
       AND d.tenant_id = CAST(:tenant_id AS uuid)
       AND d.upload_status::text = ANY(:statuses)
       AND d.updated_at <= clock_timestamp() - make_interval(secs => :stale_after)
     FOR UPDATE OF d SKIP LOCKED
    """
)

_RECORD_ATTEMPT_SQL = text(
    """
    UPDATE documents
       SET document_metadata =
               COALESCE(document_metadata, '{}'::jsonb)
               || jsonb_build_object(
                    'processing_recovery',
                    CAST(:recovery AS jsonb)
                  ),
           updated_at = clock_timestamp()
     WHERE id = CAST(:document_id AS uuid)
       AND tenant_id = CAST(:tenant_id AS uuid)
    """
)

_MARK_RETRYABLE_FAILURE_SQL = text(
    """
    UPDATE documents
       SET upload_status = CAST('error' AS document_status),
           parsing_error = :error_message,
           document_metadata =
               COALESCE(document_metadata, '{}'::jsonb)
               || jsonb_build_object(
                    'processing_recovery',
                    CAST(:recovery AS jsonb)
                  ),
           updated_at = clock_timestamp()
     WHERE id = CAST(:document_id AS uuid)
       AND tenant_id = CAST(:tenant_id AS uuid)
    """
)


class RecoveryAction(StrEnum):
    SKIP = "skip"
    REQUEUE_INGESTION = "requeue_ingestion"
    REQUEUE_ANALYSIS = "requeue_analysis"
    FAIL_RETRYABLE = "fail_retryable"


def classify_stale_document(
    *,
    status: DocumentStatus,
    hitl_pending: bool,
    attempts: int,
    rag_outcome: str | None,
) -> RecoveryAction:
    """Return the bounded recovery action for one revalidated stale document."""
    if hitl_pending:
        return RecoveryAction.SKIP
    if status not in {
        DocumentStatus.PARSING,
        DocumentStatus.PARSED_PENDING_ANALYSIS,
    }:
        return RecoveryAction.SKIP
    if rag_outcome == RagIngestionOutcome.MISCONFIGURED.value:
        return RecoveryAction.FAIL_RETRYABLE
    if attempts >= MAX_RECOVERY_ATTEMPTS:
        return RecoveryAction.FAIL_RETRYABLE
    if status is DocumentStatus.PARSING:
        return RecoveryAction.REQUEUE_INGESTION
    return RecoveryAction.REQUEUE_ANALYSIS


def recovery_attempts_for(
    metadata: dict[str, Any] | None,
    *,
    stage: DocumentStatus,
    generation: str,
) -> int:
    """Read attempts only when they belong to this exact stage/generation."""
    raw = (metadata or {}).get(RECOVERY_METADATA_KEY)
    if not isinstance(raw, dict):
        return 0
    if raw.get("stage") != stage.value or raw.get("generation") != generation:
        return 0
    attempts = raw.get("attempts", 0)
    return attempts if isinstance(attempts, int) and attempts >= 0 else 0


def _generation(*, version: int, revision_id: UUID | None) -> str:
    return f"v{version}:{revision_id if revision_id is not None else 'legacy'}"


def _recovery_payload(
    *,
    stage: DocumentStatus,
    generation: str,
    attempts: int,
    outcome: str,
    reason: str | None = None,
) -> str:
    payload: dict[str, object] = {
        "stage": stage.value,
        "generation": generation,
        "attempts": attempts,
        "outcome": outcome,
    }
    if reason is not None:
        payload["reason"] = reason
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


async def _sweep_async(
    batch_size: int = DEFAULT_BATCH_SIZE,
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
    *,
    session_factory: Any = None,
    ingestion_task: Any = None,
    analysis_task: Any = None,
) -> dict[str, int | str]:
    """Run one bounded cross-tenant scan and tenant-scoped recovery pass."""
    if session_factory is None:
        from src.core.database import init_db

        result = init_db()
        if asyncio.iscoroutine(result):
            await result
        session_factory = _production_session

    if ingestion_task is None or analysis_task is None:
        from src.core.tasks.ingestion_tasks import (
            process_document_analysis_async,
            process_document_async,
        )

        ingestion_task = ingestion_task or process_document_async
        analysis_task = analysis_task or process_document_analysis_async

    async with session_factory(None) as session:
        rows = (
            await session.execute(
                _SCAN_SQL,
                {
                    "stale_after": stale_after_seconds,
                    "limit": batch_size,
                },
            )
        ).all()

    requeued_ingestion = 0
    requeued_analysis = 0
    failed_retryable = 0
    skipped_hitl = 0
    skipped_race = 0
    enqueue_failed = 0

    for candidate in rows:
        tenant_id = UUID(str(candidate.tenant_id))
        document_id = UUID(str(candidate.id))
        dispatch: tuple[RecoveryAction, UUID | None] | None = None

        async with session_factory(tenant_id) as session:
            row = (
                await session.execute(
                    _CLAIM_SQL,
                    {
                        "document_id": str(document_id),
                        "tenant_id": str(tenant_id),
                        "statuses": list(_RECOVERABLE_STATUSES),
                        "stale_after": stale_after_seconds,
                    },
                )
            ).one_or_none()
            if row is None:
                skipped_race += 1
                continue

            status = DocumentStatus(str(row.upload_status))
            metadata = dict(row.document_metadata or {})
            current_revision_id = (
                UUID(str(row.current_revision_id))
                if row.current_revision_id is not None
                else None
            )
            generation = _generation(
                version=int(row.version),
                revision_id=current_revision_id,
            )
            attempts = recovery_attempts_for(
                metadata,
                stage=status,
                generation=generation,
            )
            rag_outcome = metadata.get("rag_ingestion_outcome")
            action = classify_stale_document(
                status=status,
                hitl_pending=bool(row.hitl_pending),
                attempts=attempts,
                rag_outcome=str(rag_outcome) if rag_outcome is not None else None,
            )

            if action is RecoveryAction.SKIP:
                if bool(row.hitl_pending):
                    skipped_hitl += 1
                else:
                    skipped_race += 1
                continue

            if action is RecoveryAction.FAIL_RETRYABLE:
                reason = (
                    "configuration_required"
                    if rag_outcome == RagIngestionOutcome.MISCONFIGURED.value
                    else "attempts_exhausted"
                )
                error_message = (
                    "Analysis provider configuration requires attention before retry."
                    if reason == "configuration_required"
                    else "Automatic processing recovery exhausted; retry is available."
                )
                await session.execute(
                    _MARK_RETRYABLE_FAILURE_SQL,
                    {
                        "document_id": str(document_id),
                        "tenant_id": str(tenant_id),
                        "error_message": error_message,
                        "recovery": _recovery_payload(
                            stage=status,
                            generation=generation,
                            attempts=attempts,
                            outcome=RecoveryAction.FAIL_RETRYABLE.value,
                            reason=reason,
                        ),
                    },
                )
                failed_retryable += 1
                continue

            next_attempt = attempts + 1
            await session.execute(
                _RECORD_ATTEMPT_SQL,
                {
                    "document_id": str(document_id),
                    "tenant_id": str(tenant_id),
                    "recovery": _recovery_payload(
                        stage=status,
                        generation=generation,
                        attempts=next_attempt,
                        outcome=action.value,
                    ),
                },
            )
            dispatch = (action, current_revision_id)

        if dispatch is None:
            continue

        action, current_revision_id = dispatch
        try:
            if action is RecoveryAction.REQUEUE_INGESTION:
                ingestion_task.apply_async(
                    kwargs={
                        "document_id": str(document_id),
                        "revision_id": (
                            str(current_revision_id)
                            if current_revision_id is not None
                            else None
                        ),
                    },
                    queue="document_parsing",
                )
                requeued_ingestion += 1
            else:
                analysis_task.apply_async(
                    kwargs={
                        "tenant_id": str(tenant_id),
                        "document_id": str(document_id),
                    },
                    queue="document_parsing",
                )
                requeued_analysis += 1
        except Exception:
            enqueue_failed += 1
            logger.exception(
                "document_recovery_enqueue_failed",
                document_id=str(document_id),
                tenant_id=str(tenant_id),
                action=action.value,
            )

    return {
        "status": "ok",
        "scanned": len(rows),
        "requeued_ingestion": requeued_ingestion,
        "requeued_analysis": requeued_analysis,
        "failed_retryable": failed_retryable,
        "skipped_hitl": skipped_hitl,
        "skipped_race": skipped_race,
        "enqueue_failed": enqueue_failed,
    }


@asynccontextmanager
async def _production_session(tenant_id: UUID | None) -> Any:
    from src.core.database import get_raw_session

    async with get_raw_session() as session:
        if tenant_id is not None:
            await session.execute(
                text("SELECT set_config('app.current_tenant', :tenant, true)"),
                {"tenant": str(tenant_id)},
            )
        yield session
        await session.commit()


@celery_app.task(name="documents.reconcile_stale_processing", bind=True)
def reconcile_stale_processing(
    self: Any,
    batch_size: int = DEFAULT_BATCH_SIZE,
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
) -> dict[str, int | str]:
    _ = self
    return asyncio.run(
        _sweep_async(
            batch_size=batch_size,
            stale_after_seconds=stale_after_seconds,
        )
    )
