"""PQ-HITL-04B2: provisional event persistence, not trusted-state settlement.

Unexposed adapter. Caller must supply authenticated reviewer and tenant
from server context, plus source identity verified against bound candidate.
Transaction lifetime belongs to caller; no endpoint or workflow resume.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.hitl.domain.finding_decision import (
    FindingDecisionDraft,
    stable_finding_id,
)


class FindingDecisionIdentityError(ValueError):
    pass


class FindingDecisionRevisionConflict(RuntimeError):
    pass


class FindingDecisionIdempotencyConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class FindingDecisionWriteReceipt:
    event_id: UUID
    ledger_revision: int
    replayed: bool


_LOCK = text("""
SELECT id, project_id FROM public.review_items
WHERE id = cast(:review_row_id as uuid) AND tenant_id = cast(:tenant_id as uuid)
AND current_status::text IN ('PENDING_REVIEW_REQUIRED','PENDING_REVIEW_CONDITIONAL','ESCALATED')
FOR UPDATE
""")

_REPLAY = text("""
SELECT event_id, ledger_revision, tenant_id, review_row_id, document_id,
document_revision_id, artifact_id, artifact_version, artifact_hash,
generation, fencing_token, thread_id, checkpoint_id, finding_id, finding_kind,
action, reviewer_id, reason, proposed_text, expected_ledger_revision
FROM public.hitl_finding_decisions
WHERE tenant_id = cast(:tenant_id as uuid)
AND review_row_id = cast(:review_row_id as uuid)
AND idempotency_key = :idempotency_key
""")

_CURRENT = text("""
SELECT coalesce(max(ledger_revision), 0) AS ledger_revision
FROM public.hitl_finding_decisions
WHERE tenant_id = cast(:tenant_id as uuid)
AND review_row_id = cast(:review_row_id as uuid)
""")
