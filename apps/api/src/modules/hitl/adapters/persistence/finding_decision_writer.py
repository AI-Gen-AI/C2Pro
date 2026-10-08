"""PQ-HITL-04B2: provisional event persistence, not trusted-state settlement.

Unexposed adapter. Caller must supply authenticated reviewer and tenant
from server context, plus source identity verified against bound candidate.
Transaction lifetime belongs to caller; no endpoint or workflow resume.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.domain.trust import artifact_digest
from src.modules.hitl.domain.finding_decision import (
    FindingDecisionDraft,
    FindingDecisionKind,
    stable_finding_id,
)
from src.modules.hitl.domain.finding_source_membership import (
    FindingSourceNotBound,
    verify_risk_source_membership,
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


# Refuse runtime writes through postgres/service_role or a table owner,
# even with FORCE RLS: BYPASSRLS and superuser sessions can skip policies.
# Preflight in the SAME transaction before the review lock or any replay.
# This intentionally denies operation until a dedicated, unprivileged LOGIN
# principal has been provisioned with only the required tenant-scoped grants.
_SAFE_DB_ROLE = text("""
SELECT (
    current_user = session_user
    AND current_setting('app.current_tenant', true) = :tenant_id
    AND EXISTS (
        SELECT 1 FROM pg_roles r
         WHERE r.rolname = current_user
           AND r.rolcanlogin
           AND NOT r.rolsuper
           AND NOT r.rolbypassrls
    )
    AND has_table_privilege(current_user, 'public.hitl_finding_decisions', 'SELECT')
    AND has_table_privilege(current_user, 'public.hitl_finding_decisions', 'INSERT')
    -- RLS and the row trigger DO NOT protect TRUNCATE; inherited write and
    -- maintenance capabilities also violate the append-only contract.
    AND NOT has_table_privilege(current_user, 'public.hitl_finding_decisions', 'UPDATE')
    AND NOT has_table_privilege(current_user, 'public.hitl_finding_decisions', 'DELETE')
    AND NOT has_table_privilege(current_user, 'public.hitl_finding_decisions', 'TRUNCATE')
    AND NOT has_table_privilege(current_user, 'public.hitl_finding_decisions', 'REFERENCES')
    AND NOT has_table_privilege(current_user, 'public.hitl_finding_decisions', 'TRIGGER')
    AND EXISTS (
        SELECT 1 FROM pg_class c
         WHERE c.oid = 'public.hitl_finding_decisions'::regclass
           AND c.relrowsecurity
           AND c.relforcerowsecurity
           AND NOT pg_has_role(
               (SELECT r.oid FROM pg_roles r WHERE r.rolname = current_user),
               c.relowner,
               'MEMBER'
           )
    )
) AS safe_hitl_writer_role
""")

_LOCK = text("""
SELECT id, project_id, document_id, thread_id, checkpoint_id,
       lineage_generation, lineage_fencing_token, review_metadata
FROM public.review_items
WHERE id = cast(:review_row_id as uuid) AND tenant_id = cast(:tenant_id as uuid)
AND current_status::text IN ('PENDING_REVIEW_REQUIRED','PENDING_REVIEW_CONDITIONAL','ESCALATED')
FOR UPDATE
""")

_CANDIDATE_SOURCE = text("""
SELECT a.payload FROM public.document_artifacts a
JOIN public.document_processing_operations o
  ON o.document_id = a.document_id AND o.tenant_id = a.tenant_id
WHERE a.artifact_id = cast(:artifact_id as uuid)
  AND a.tenant_id = cast(:tenant_id as uuid)
  AND a.project_id = cast(:project_id as uuid)
  AND a.document_id = cast(:document_id as uuid)
  AND a.document_revision_id = cast(:revision_id as uuid)
  AND a.artifact_version = :artifact_version
  AND a.artifact_hash = :artifact_hash
  AND a.trust_state = 'proposed'
  AND o.revision_id = a.document_revision_id
  AND o.generation = :generation
  AND o.fencing_token = :fencing_token
  AND o.stage = 'ANALYSIS'
""")

_REPLAY = text("""
SELECT event_id, ledger_revision, tenant_id, review_row_id, document_id,
document_revision_id, artifact_id, artifact_version, artifact_hash,
generation, fencing_token, thread_id, checkpoint_id, finding_id,
source_item_id, source_ordinal, finding_kind, action, reviewer_id, reason, proposed_text, expected_ledger_revision
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
        if draft.finding_kind is not FindingDecisionKind.RISK:
            raise FindingDecisionIdentityError(
                "critique observations require their own typed persisted evidence envelope"
            )

        # RLS is only meaningful when the connection itself cannot bypass
        # it; verifying the caller's tenant UUID alone is not a DB authority.
        principal = (
            await self._session.execute(_SAFE_DB_ROLE, {"tenant_id": str(tenant_id)})
        ).mappings().first()
        if not principal or principal.get("safe_hitl_writer_role") is not True:
            raise FindingDecisionIdentityError(
                "database principal is not authorized for non-bypass HITL ledger writes"
            )

        keys = {
            "tenant_id": tenant_id,
            "review_row_id": c.review_row_id,
            "idempotency_key": idempotency_key,
        }
        locked = (await self._session.execute(_LOCK, keys)).mappings().first()
        if locked is None or locked.get("project_id") is None:
            raise FindingDecisionIdentityError("missing active tenant-scoped review row")
        metadata = locked.get("review_metadata") or {}
        bound = metadata.get("candidate_binding") or {}
        if (
            metadata.get("trust_candidate_required") is not True
            or locked.get("document_id") != c.document_id
            or locked.get("thread_id") != c.thread_id
            or locked.get("checkpoint_id") != c.checkpoint_id
            or locked.get("lineage_generation") != c.generation
            or locked.get("lineage_fencing_token") != c.fencing_token
            or bound.get("artifact_id") != str(c.artifact_id)
            or bound.get("document_id") != str(c.document_id)
            or str(bound.get("artifact_version")) != str(c.artifact_version)
            or bound.get("artifact_hash") != c.artifact_hash
        ):
            raise FindingDecisionIdentityError("pending review was rebound or superseded")

        # Validate actual membership in the exact proposed payload under the
        # SAME RLS-protected transaction. Joining the authority enforces a live
        # generation/fence without locking it after the review row (#758).
        candidate_row = (
            await self._session.execute(
                _CANDIDATE_SOURCE,
                {
                    "artifact_id": c.artifact_id,
                    "tenant_id": tenant_id,
                    "project_id": locked["project_id"],
                    "document_id": c.document_id,
                    "revision_id": c.document_revision_id,
                    "artifact_version": c.artifact_version,
                    "artifact_hash": c.artifact_hash,
                    "generation": c.generation,
                    "fencing_token": c.fencing_token,
                },
            )
        ).mappings().first()
        payload = candidate_row.get("payload") if candidate_row is not None else None
        if not isinstance(payload, Mapping) or artifact_digest(payload) != c.artifact_hash:
            raise FindingDecisionIdentityError(
                "exact current proposed candidate payload is missing or changed"
            )
        try:
            verify_risk_source_membership(
                payload, source_item_id=source_item_id, ordinal=ordinal
            )
        except FindingSourceNotBound as exc:
            raise FindingDecisionIdentityError(
                "requested finding is not a member of the exact candidate"
            ) from exc

        binding = {
            **_binding(draft),
            "source_item_id": source_item_id,
            "source_ordinal": ordinal,
        }
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
