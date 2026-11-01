"""S5-03: load the exact candidate + the COMPLETE ledger of a review under the caller's project authority, reconcile it.

The contract with the next increments (nothing here signs, trusts or promotes):

* S5-04 (the signature) calls ``reconcile`` for the review it is about to sign, REQUIRING ``APPROVE_CANDIDATE`` on the
  review's project, signs only when ``result.signable_as_is`` and binds its act to ``result.receipt()``.
* S5-05 (the first TRUSTED) calls ``verify_current(receipt, ..., lock=True)`` INSIDE the transaction that commits the
  TRUSTED state, together with ``ProjectReviewAuthorizer.revalidate``. ``lock=True`` takes ``FOR SHARE`` on the review
  row, which the ledger writer's ``FOR UPDATE`` conflicts with: while the transaction lives no decision can be appended,
  so the digest it just verified is the digest that is committed. THAT atomicity is S5-05's, not claimed here.
* Without the lock a reconciliation is a consistent-enough READ whose digest still changes if any decision is appended,
  the candidate is replaced or its processing authority moves: a receipt that no longer matches is ``ReconciliationStale``.

The project is the review row's own (never the client's). READ_REVIEW is the floor for reading the ledger; a caller that
will sign passes ``APPROVE_CANDIDATE``.
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.domain.trust import artifact_digest
from src.modules.hitl.application.finding_review_authorization import authorize_finding_reviewer
from src.modules.hitl.application.project_review_authorization import (
    ProjectCapability,
    ProjectReviewAuthorizer,
)
from src.modules.hitl.application.review_findings_view import (
    _CANDIDATE,
    _REVIEW,
    ReviewFindingsUnavailable,
)
from src.modules.hitl.domain.finding_decision import (
    CandidateReviewIdentity,
    FindingDecisionKind,
    stable_finding_id,
)
from src.modules.hitl.domain.finding_reconciliation import (
    CandidateFinding,
    CritiqueCoverage,
    CritiqueObservation,
    ReconciliationInput,
    ReconciliationReceipt,
    ReconciliationResult,
    events_from_rows,
    reconcile,
)
from src.modules.hitl.domain.finding_source_membership import risk_source_item_id


class ReconciliationStale(RuntimeError):
    """The receipt no longer describes the review: a decision was appended, the candidate or its authority moved."""


_LEDGER = text("""
SELECT event_id, ledger_revision, expected_ledger_revision, tenant_id, review_row_id, document_id, document_revision_id,
       artifact_id, artifact_version, artifact_hash, generation, fencing_token, finding_id, finding_kind, action,
       reviewer_id, reason, proposed_text, recorded_at
FROM public.hitl_finding_decisions
WHERE tenant_id = cast(:tenant_id as uuid) AND review_row_id = cast(:review_row_id as uuid)
ORDER BY ledger_revision, event_id
""")


class CritiqueSource(Protocol):
    def load(
        self, review_metadata: dict[str, Any], candidate_payload: dict[str, Any]
    ) -> tuple[tuple[CritiqueObservation, ...], CritiqueCoverage]: ...


class MetadataCritiqueSource:
    """What exists today: free-text ``critique_notes`` with NO typed materiality / evidence.

    It therefore never fabricates an observation: prose is declared ``UNSTRUCTURED_NOT_EVALUATED`` (an advisory the
    signature step can see), and the absence of prose is ``NONE_PRESENT``. A typed envelope replaces this source.
    """

    def load(
        self, review_metadata: dict[str, Any], candidate_payload: dict[str, Any]  # noqa: ARG002
    ) -> tuple[tuple[CritiqueObservation, ...], CritiqueCoverage]:
        notes = review_metadata.get("critique_notes")
        if isinstance(notes, str) and notes.strip():
            return (), CritiqueCoverage.UNSTRUCTURED_NOT_EVALUATED
        return (), CritiqueCoverage.NONE_PRESENT


class FindingReconciliationService:
    def __init__(
        self,
        session: AsyncSession,
        authorizer: ProjectReviewAuthorizer | None = None,
        critique_source: CritiqueSource | None = None,
    ) -> None:
        self._session = session
        self._authorizer = authorizer or ProjectReviewAuthorizer(session)
        self._critiques = critique_source or MetadataCritiqueSource()

    async def reconcile(
        self,
        *,
        tenant_id: UUID,
        user: object,
        review_row_id: UUID,
        capability: ProjectCapability = ProjectCapability.READ_REVIEW,
        lock: bool = False,
    ) -> ReconciliationResult:
        """Raises ``FindingReviewerNotAuthorized`` (not a human of the tenant), ``ProjectAuthorizationDenied`` (no grant
        on the review's project) or ``ReviewFindingsUnavailable`` (no actionable candidate-bound review) -- before any
        ledger row is read."""
        actor = authorize_finding_reviewer(user, tenant_id=tenant_id)
        review_sql = text(_REVIEW.text + (" FOR SHARE" if lock else ""))
        review = (
            await self._session.execute(review_sql, {"tenant_id": actor.tenant_id, "review_row_id": review_row_id})
        ).mappings().first()
        if review is None:
            raise ReviewFindingsUnavailable("no actionable review for tenant")
        await self._authorizer.require(
            tenant_id=actor.tenant_id, user_id=actor.reviewer_id, project_id=review["project_id"],
            capability=capability, lock=lock,
        )

        metadata = review.get("review_metadata")
        bound = metadata.get("candidate_binding") if isinstance(metadata, dict) else None
        if not (
            isinstance(metadata, dict)
            and metadata.get("trust_candidate_required") is True
            and metadata.get("trust_kind") != "structured_source"
            and isinstance(bound, dict)
            and bound.get("document_id") == str(review["document_id"])
            and review["project_id"] is not None
        ):
            raise ReviewFindingsUnavailable("review is not bound to an analysis candidate")
        try:
            artifact_id = UUID(str(bound.get("artifact_id")))
            artifact_version = int(str(bound.get("artifact_version")))
        except (TypeError, ValueError) as exc:
            raise ReviewFindingsUnavailable("review candidate pin is malformed") from exc
        artifact_hash = str(bound.get("artifact_hash") or "")
        candidate = (
            await self._session.execute(
                _CANDIDATE,
                {
                    "artifact_id": artifact_id, "tenant_id": actor.tenant_id, "project_id": review["project_id"],
                    "document_id": review["document_id"], "artifact_version": artifact_version, "artifact_hash": artifact_hash,
                },
            )
        ).mappings().first()
        payload = candidate.get("payload") if candidate is not None else None
        if (
            candidate is None
            or not isinstance(payload, dict)
            or artifact_digest(payload) != artifact_hash
            or candidate["generation"] != review["lineage_generation"]
            or candidate["fencing_token"] != review["lineage_fencing_token"]
            or not review["thread_id"]
            or not review["checkpoint_id"]
        ):
            raise ReviewFindingsUnavailable("the candidate is missing, changed or superseded")

        identity = CandidateReviewIdentity(
            tenant_id=actor.tenant_id, review_row_id=review_row_id, document_id=review["document_id"],
            document_revision_id=candidate["document_revision_id"], artifact_id=artifact_id,
            artifact_version=artifact_version, artifact_hash=artifact_hash, generation=review["lineage_generation"],
            fencing_token=review["lineage_fencing_token"], thread_id=str(review["thread_id"]),
            checkpoint_id=str(review["checkpoint_id"]),
        )
        findings: list[CandidateFinding] = []
        risks = payload.get("extracted_risks")
        for ordinal, risk in enumerate(risks if isinstance(risks, list) else []):
            if not isinstance(risk, dict) or not risk:
                continue
            source_item_id = risk_source_item_id(risk)
            findings.append(
                CandidateFinding(
                    ordinal, source_item_id,
                    stable_finding_id(identity, FindingDecisionKind.RISK, source_item_id=source_item_id, ordinal=ordinal),
                )
            )
        rows = (
            await self._session.execute(_LEDGER, {"tenant_id": actor.tenant_id, "review_row_id": review_row_id})
        ).mappings().all()
        critiques, coverage = self._critiques.load(metadata, payload)
        return reconcile(
            ReconciliationInput(
                identity=identity, project_id=review["project_id"], findings=tuple(findings),
                ledger=events_from_rows([dict(r) for r in rows]), critiques=critiques, critique_coverage=coverage,
            )
        )

    async def verify_current(
        self,
        receipt: ReconciliationReceipt,
        *,
        tenant_id: UUID,
        user: object,
        capability: ProjectCapability = ProjectCapability.APPROVE_CANDIDATE,
        lock: bool = True,
    ) -> ReconciliationResult:
        """Re-reconcile NOW and require the very digest that was signed against (S5-05 calls this under its lock).

        A candidate that disappeared or changed, or any digest difference, is ``ReconciliationStale``. An authorization
        failure stays a ``ProjectAuthorizationDenied`` (a revocation before the operation is not "stale").
        """
        try:
            fresh = await self.reconcile(
                tenant_id=tenant_id, user=user, review_row_id=receipt.review_row_id, capability=capability, lock=lock
            )
        except ReviewFindingsUnavailable as exc:
            raise ReconciliationStale(f"the reconciled candidate is no longer the review's: {exc}") from exc
        if fresh.digest != receipt.digest or fresh.project_id != receipt.project_id:
            raise ReconciliationStale("the ledger, the candidate or its processing authority changed since the reconciliation")
        return fresh


__all__ = [
    "CritiqueSource",
    "FindingReconciliationService",
    "MetadataCritiqueSource",
    "ReconciliationStale",
]
