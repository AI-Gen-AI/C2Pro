"""Recovery may acquire an existing decision, never author a human revision.

The scan is only a hint. Every identity field, backoff and lease is compared
again in the short acquisition transaction. No graph work holds its locks.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text

from src.modules.hitl.adapters.persistence import resume_ownership as claims
from src.modules.hitl.adapters.persistence.repository import SqlAlchemyReviewQueueRepository
from src.modules.hitl.domain.entities import ReviewItem, ReviewStatus


@dataclass(frozen=True)
class ResumeRecoveryRequest:
    operation_id: UUID
    review_row_id: UUID
    tenant_id: UUID
    expected_decision: str
    expected_decision_hash: str | None
    expected_decision_revision: int
    expected_fencing_token: int


class RecoveryOutcome(StrEnum):
    ACQUIRED = "ACQUIRED"  # Internal: not counted as successful recovery.
    RECOVERED = "RECOVERED"
    STALE = "STALE"
    BUSY = "BUSY"
    NOT_DUE = "NOT_DUE"
    ALREADY_FINALIZED = "ALREADY_FINALIZED"
    OPERATOR_REQUIRED = "OPERATOR_REQUIRED"
    NOT_VISIBLE = "NOT_VISIBLE"


@dataclass(frozen=True)
class RecoveryClaim:
    outcome: RecoveryOutcome
    ownership: claims.Ownership | None = None
    review: ReviewItem | None = None
    thread_id: str | None = None
    feedback: str | None = None
    reviewer: str | None = None


# Shared by both grant and quarantine: neither may act on a stale scan or
# supersede a live owner, even in FAILED_RETRYABLE. Row locks serialize this
# against human acquisition, heartbeat, N17 and finalization.
_EXPECTED_AND_AVAILABLE = """
    id = cast(:operation_id as uuid)
    AND review_row_id = cast(:review_row_id as uuid)
    AND tenant_id = cast(:tenant_id as uuid)
    AND decision IS NOT DISTINCT FROM cast(:decision as text)
    AND decision_hash IS NOT DISTINCT FROM cast(:decision_hash as text)
    AND decision_revision = :decision_revision
    AND fencing_token = :fencing_token
    AND phase IN ('PENDING', 'RUNNING', 'FAILED_RETRYABLE', 'N17_DURABLE', 'GRAPH_COMPLETED')
    AND (next_attempt_at IS NULL OR next_attempt_at <= clock_timestamp())
    AND ((owner_token IS NULL AND lease_expires_at IS NULL)
         OR lease_expires_at <= clock_timestamp())
"""

_ACQUIRE_RECOVERY_SQL = text(
    """
    UPDATE resume_operations
       SET current_attempt_id = cast(:attempt_id as uuid),
           owner_token = cast(:owner_token as uuid),
           fencing_token = fencing_token + 1,
           phase = CASE WHEN phase IN ('N17_DURABLE', 'GRAPH_COMPLETED')
                        THEN phase ELSE 'RUNNING' END,
           heartbeat_at = clock_timestamp(),
           lease_expires_at = clock_timestamp()
               + make_interval(secs => cast(:lease_seconds as double precision)),
           operation_metadata = coalesce(operation_metadata, '{}'::jsonb)
               || jsonb_build_object('feedback', cast(:feedback as text)),
           updated_at = clock_timestamp()
     WHERE """
    + _EXPECTED_AND_AVAILABLE
    + " RETURNING *"
)

_QUARANTINE_SQL = text(
    """
    UPDATE resume_operations
       SET phase = 'OPERATOR_REQUIRED',
           fencing_token = fencing_token + 1,
           owner_token = NULL, lease_expires_at = NULL, next_attempt_at = NULL,
           last_error = :reason,
           operation_metadata = coalesce(operation_metadata, '{}'::jsonb)
               || jsonb_build_object('recovery_refusal', cast(:reason as text),
                                     'recovery_refused_phase', phase),
           updated_at = clock_timestamp()
     WHERE """
    + _EXPECTED_AND_AVAILABLE
    + " RETURNING id"
)


def _feedback(row: Any, review: ReviewItem) -> tuple[str | None, str | None]:
    metadata = row.operation_metadata or {}
    if "feedback" in metadata:
        # Explicit empty is valid; absent/null/non-text is not empty.
        value = metadata["feedback"]
        if (
            isinstance(value, str)
            and claims.decision_hash(row.decision, value) == row.decision_hash
        ):
            return value, None
        return None, "authoritative_feedback_hash_mismatch"

    # Legacy row fields are candidates, not authority by themselves. The
    # operation's durable decision hash must validate the exact plaintext.
    # Attempt rows contain hashes, not plaintext; generic project events or
    # another attempt's checkpoint must not supply an invented decision.
    for value in (review.metadata.get("review_decision"), review.metadata.get("rejection_reason")):
        if (
            isinstance(value, str)
            and claims.decision_hash(row.decision, value) == row.decision_hash
        ):
            return value, None
    return None, "missing_authoritative_feedback"


async def acquire_for_reconciliation(
    expected: ResumeRecoveryRequest,
    *,
    lease_seconds: int = claims.DEFAULT_LEASE_SECONDS,
    session_factory: Any = None,
) -> RecoveryClaim:
    """CAS the exact scanned decision; never INSERT an operation or revise it."""
    params = {
        "operation_id": str(expected.operation_id),
        "review_row_id": str(expected.review_row_id),
        "tenant_id": str(expected.tenant_id),
        "decision": expected.expected_decision,
        "decision_hash": expected.expected_decision_hash,
        "decision_revision": expected.expected_decision_revision,
        "fencing_token": expected.expected_fencing_token,
    }
    async with claims._session(session_factory, expected.tenant_id) as session:
        row = (
            await session.execute(
                text("""
            SELECT *,
                   ((owner_token IS NULL AND lease_expires_at IS NULL)
                    OR lease_expires_at <= clock_timestamp()) AS available,
                   (next_attempt_at IS NULL OR next_attempt_at <= clock_timestamp()) AS due
              FROM resume_operations
             WHERE id = cast(:operation_id as uuid) AND tenant_id = cast(:tenant_id as uuid)
             FOR UPDATE
        """),
                params,
            )
        ).first()
        if row is None:
            return RecoveryClaim(RecoveryOutcome.NOT_VISIBLE)
        if (
            row.review_row_id != expected.review_row_id
            or row.decision != expected.expected_decision
            or row.decision_hash != expected.expected_decision_hash
            or row.decision_revision != expected.expected_decision_revision
            or row.fencing_token != expected.expected_fencing_token
        ):
            return RecoveryClaim(RecoveryOutcome.STALE)
        if row.phase in {claims.Phase.FINALIZED_APPROVED, claims.Phase.FINALIZED_REJECTED}:
            return RecoveryClaim(RecoveryOutcome.ALREADY_FINALIZED)
        if row.phase == claims.Phase.OPERATOR_REQUIRED:
            return RecoveryClaim(RecoveryOutcome.OPERATOR_REQUIRED)
        if not row.available:
            return RecoveryClaim(RecoveryOutcome.BUSY)
        if not row.due:
            return RecoveryClaim(RecoveryOutcome.NOT_DUE)

        repo = SqlAlchemyReviewQueueRepository(session, expected.tenant_id)
        review = await repo.get_review_item_by_row_id(expected.review_row_id, for_update=True)
        if review is None:
            return RecoveryClaim(RecoveryOutcome.NOT_VISIBLE)

        feedback, reason = _feedback(row, review)
        if row.decision not in {"approve", "reject"}:
            reason = "invalid_durable_decision"
        elif not row.thread_id or not row.source_checkpoint_id:
            reason = "missing_immutable_checkpoint_identity"
        elif review.current_status not in {
            ReviewStatus.PENDING_REVIEW_REQUIRED,
            ReviewStatus.PENDING_REVIEW_CONDITIONAL,
        }:
            reason = "review_operation_status_mismatch"

        if reason is not None:
            quarantined = (
                await session.execute(_QUARANTINE_SQL, {**params, "reason": reason})
            ).first()
            if quarantined is None:
                return RecoveryClaim(RecoveryOutcome.STALE)
            # Advancing the fence prevents an expired worker's failure
            # handler from reviving this explicit operator-required halt.
            await session.execute(
                text("""
                UPDATE resume_operation_attempts
                   SET outcome = 'ABANDONED', reason = :reason, ended_at = clock_timestamp()
                 WHERE operation_id = cast(:operation_id as uuid)
                   AND tenant_id = cast(:tenant_id as uuid) AND outcome = 'ACTIVE'
            """),
                {**params, "reason": reason},
            )
            return RecoveryClaim(RecoveryOutcome.OPERATOR_REQUIRED)

        attempt_id, owner_token = uuid4(), uuid4()
        acquired = (
            await session.execute(
                _ACQUIRE_RECOVERY_SQL,
                {
                    **params,
                    "attempt_id": str(attempt_id),
                    "owner_token": str(owner_token),
                    "lease_seconds": lease_seconds,
                    "feedback": feedback,
                },
            )
        ).first()
        if acquired is None:
            return RecoveryClaim(RecoveryOutcome.STALE)
        await session.execute(
            claims._SUPERSEDE_PRIOR_ATTEMPTS_SQL,
            {
                "operation_id": str(row.id),
                "fencing_token": acquired.fencing_token,
                "reason": "reconciliation_takeover",
            },
        )
        await session.execute(
            claims._INSERT_ATTEMPT_SQL,
            {
                "id": str(attempt_id),
                "tenant_id": str(expected.tenant_id),
                "operation_id": str(row.id),
                "owner_token": str(owner_token),
                "fencing_token": acquired.fencing_token,
                "decision_revision": row.decision_revision,
                "decision": row.decision,
                "decision_hash": row.decision_hash,
                "reviewer": row.reviewer,
                "source_checkpoint_id": row.source_checkpoint_id,
            },
        )
        ownership = claims.Ownership(
            operation_id=row.id,
            attempt_id=attempt_id,
            owner_token=owner_token,
            fencing_token=acquired.fencing_token,
            decision_revision=row.decision_revision,
            tenant_id=expected.tenant_id,
            review_row_id=expected.review_row_id,
            decision=row.decision,
            phase=claims.Phase(acquired.phase),
            source_checkpoint_id=row.source_checkpoint_id,
            terminal_checkpoint_id=row.terminal_checkpoint_id,
            analysis_id=row.analysis_id,
            project_id=row.project_id,
            document_id=row.document_id,
            failure_count=row.failure_count,
        )
        return RecoveryClaim(
            RecoveryOutcome.ACQUIRED,
            ownership,
            review,
            row.thread_id,
            feedback,
            row.reviewer,
        )
