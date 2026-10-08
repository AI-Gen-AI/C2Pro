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

_APPEND = text("""
INSERT INTO public.hitl_finding_decisions (
  event_id, tenant_id, project_id, review_row_id, document_id, document_revision_id,
  artifact_id, artifact_version, artifact_hash, generation, fencing_token,
  thread_id, checkpoint_id, finding_id, source_item_id, source_ordinal,
  finding_kind, action, reviewer_id, created_by, reason, proposed_text,
  expected_ledger_revision, ledger_revision, idempotency_key
) VALUES (
  :event_id, :tenant_id, :project_id, :review_row_id, :document_id, :document_revision_id,
  :artifact_id, :artifact_version, :artifact_hash, :generation, :fencing_token,
  :thread_id, :checkpoint_id, :finding_id, :source_item_id, :source_ordinal,
  :finding_kind, :action, :reviewer_id, :created_by, :reason, :proposed_text,
  :expected_ledger_revision, :ledger_revision, :idempotency_key
) RETURNING event_id, ledger_revision
""")


def _binding(draft: FindingDecisionDraft) -> dict[str, object]:
    c = draft.candidate
    return {
        "tenant_id": c.tenant_id,
        "review_row_id": c.review_row_id,
        "document_id": c.document_id,
        "document_revision_id": c.document_revision_id,
        "artifact_id": c.artifact_id,
        "artifact_version": c.artifact_version,
        "artifact_hash": c.artifact_hash,
        "generation": c.generation,
        "fencing_token": c.fencing_token,
        "thread_id": c.thread_id,
        "checkpoint_id": c.checkpoint_id,
        "finding_id": draft.finding_id,
        "finding_kind": draft.finding_kind.value,
        "action": draft.action.value,
        "reviewer_id": draft.reviewer_id,
        "reason": draft.reason,
        "proposed_text": draft.proposed_text,
        "expected_ledger_revision": draft.expected_ledger_revision,
    }
