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


class FindingDecisionLedgerWriter:
    """Append provisional reviewer intent inside caller-owned transaction.

    DB RLS and the INSERT guard revalidate the exact pending candidate; no
    APPROVED/TRUSTED state transitions happen in this adapter.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        tenant_id: UUID,
        authenticated_reviewer_id: str,
        source_item_id: str,
        ordinal: int,
        idempotency_key: str,
        draft: FindingDecisionDraft,
    ) -> FindingDecisionWriteReceipt:
        c = draft.candidate
        if (
            tenant_id != c.tenant_id
            or authenticated_reviewer_id != draft.reviewer_id
            or not authenticated_reviewer_id.strip()
            or not source_item_id.strip()
            or ordinal < 0
            or len(idempotency_key.strip()) < 8
        ):
            raise FindingDecisionIdentityError("tenant, reviewer or source identity mismatch")
        actual_fingerprint = stable_finding_id(
            c, draft.finding_kind, source_item_id=source_item_id, ordinal=ordinal
        )
        if draft.finding_id != actual_fingerprint:
            raise FindingDecisionIdentityError("finding fingerprint mismatch")

        keys = {
            "tenant_id": tenant_id,
            "review_row_id": c.review_row_id,
            "idempotency_key": idempotency_key,
        }
        locked = (await self._session.execute(_LOCK, keys)).mappings().first()
        if locked is None or locked.get("project_id") is None:
            raise FindingDecisionIdentityError("missing active tenant-scoped review row")

        binding = _binding(draft)
        existing = (await self._session.execute(_REPLAY, keys)).mappings().first()
        if existing is not None:
            if any(existing.get(name) != value for name, value in binding.items()):
                raise FindingDecisionIdempotencyConflict("replay key has different contents")
            return FindingDecisionWriteReceipt(
                event_id=existing["event_id"],
                ledger_revision=int(existing["ledger_revision"]),
                replayed=True,
            )

        current = (await self._session.execute(_CURRENT, keys)).mappings().first()
        last_revision = int(current["ledger_revision"]) if current else 0
        if last_revision != draft.expected_ledger_revision:
            raise FindingDecisionRevisionConflict("stale ledger revision")

        from uuid import uuid4

        record = {
            **binding,
            **keys,
            "project_id": locked["project_id"],
            "source_item_id": source_item_id,
            "source_ordinal": ordinal,
            "created_by": authenticated_reviewer_id,
            "event_id": uuid4(),
            "ledger_revision": last_revision + 1,
        }
        result = (await self._session.execute(_APPEND, record)).mappings().first()
        if result is None:
            raise FindingDecisionRevisionConflict("ledger event not returned")
        return FindingDecisionWriteReceipt(
            event_id=result["event_id"],
            ledger_revision=int(result["ledger_revision"]),
            replayed=False,
        )
