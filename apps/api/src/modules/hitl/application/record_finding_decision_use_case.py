"""PQ-HITL-04C4: reconstruct exact candidate identity from tenant-scoped review.

Application-only. No route, graph resume, settlement or TRUSTED promotion.
Future endpoint must use get_current_user and CurrentTenantId in the same
request-scoped RLS transaction and must never pass client actor identities.
"""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.hitl.adapters.persistence.finding_decision_writer import (
    FindingDecisionIdentityError,
    FindingDecisionLedgerWriter,
    FindingDecisionWriteReceipt,
)
from src.modules.hitl.application.finding_review_authorization import (
    FindingDecisionSubmission,
    authorize_finding_reviewer,
)
from src.modules.hitl.domain.finding_decision import (
    CandidateReviewIdentity,
    FindingDecisionDraft,
    FindingDecisionKind,
    stable_finding_id,
)

_READ_PENDING = text("""
SELECT id, project_id, document_id, thread_id, checkpoint_id,
       lineage_generation, lineage_fencing_token, review_metadata
FROM public.review_items
WHERE id = cast(:review_row_id as uuid)
  AND tenant_id = cast(:tenant_id as uuid)
  AND current_status::text IN
      ('PENDING_REVIEW_REQUIRED','PENDING_REVIEW_CONDITIONAL','ESCALATED')
""")


class RecordFindingDecisionUseCase:
    """Record one provisional RISK finding without inventing a trusted state."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self,
        *,
        tenant_id: UUID,
        user: object,
        review_row_id: UUID,
        submission: FindingDecisionSubmission,
    ) -> FindingDecisionWriteReceipt:
        actor = authorize_finding_reviewer(user, tenant_id=tenant_id)
        row = (
            await self._session.execute(
                _READ_PENDING, {"tenant_id": tenant_id, "review_row_id": review_row_id}
            )
        ).mappings().first()
        if row is None or row.get("id") != review_row_id:
            raise FindingDecisionIdentityError("no actionable review for tenant")

        metadata = row.get("review_metadata")
        bound = metadata.get("candidate_binding") if isinstance(metadata, Mapping) else None
        if not (
            isinstance(metadata, Mapping)
            and metadata.get("trust_candidate_required") is True
            and isinstance(bound, Mapping)
            and bound.get("artifact_id") == str(submission.artifact_id)
            and bound.get("document_id") == str(row.get("document_id"))
            and str(bound.get("artifact_version")) == str(submission.artifact_version)
            and bound.get("artifact_hash") == submission.artifact_hash
            and row.get("lineage_generation") == submission.generation
            and row.get("lineage_fencing_token") == submission.fencing_token
            and row.get("project_id") is not None
            and row.get("document_id") is not None
            and row.get("thread_id")
            and row.get("checkpoint_id")
        ):
            raise FindingDecisionIdentityError(
                "candidate pin is missing, different or superseded"
            )

        # The document_id, thread and checkpoint below are read from the
        # authoritative row, NOT from the submitted JSON. Its exact artifact
        # and current processing grant are rechecked under the writer's
        # review-row lock, including before any idempotent replay.
        candidate = CandidateReviewIdentity(
            tenant_id=tenant_id,
            review_row_id=review_row_id,
            document_id=row["document_id"],
            document_revision_id=submission.document_revision_id,
            artifact_id=submission.artifact_id,
            artifact_version=submission.artifact_version,
            artifact_hash=submission.artifact_hash,
            generation=submission.generation,
            fencing_token=submission.fencing_token,
            thread_id=row["thread_id"],
            checkpoint_id=row["checkpoint_id"],
        )
        kind = FindingDecisionKind.RISK
        finding_id = stable_finding_id(
            candidate,
            kind,
            source_item_id=submission.source_item_id,
            ordinal=submission.ordinal,
        )
        draft = FindingDecisionDraft(
            candidate=candidate,
            finding_id=finding_id,
            finding_kind=kind,
            action=submission.action,
            reviewer_id=str(actor.reviewer_id),
            expected_ledger_revision=submission.expected_ledger_revision,
            reason=submission.reason,
            proposed_text=submission.proposed_text,
        )
        return await FindingDecisionLedgerWriter(self._session).record(
            tenant_id=actor.tenant_id,
            authenticated_reviewer_id=str(actor.reviewer_id),
            source_item_id=submission.source_item_id,
            ordinal=submission.ordinal,
            idempotency_key=submission.idempotency_key,
            draft=draft,
        )
