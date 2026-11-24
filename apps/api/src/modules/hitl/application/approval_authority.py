"""S5-04 + S5-05: the final approval is bound to a CURRENT reconciliation and to a still-valid grant at promotion time.

Two moments, one authority record:

* S5-04 -- BEFORE any resume operation exists (``require_reconciled_approval``): under ``enforce``, an approval of a
  candidate-bound analysis review needs a reconciliation that is consistent, has no blocker (NEEDS_INFO, undecided
  finding, material verified open critique) and needs no derived candidate. Otherwise ``ReconciliationBlocksApproval``
  (nothing is created, nothing is recorded). The proof -- who decided, on which project, under which grant, against
  which reconciliation digest -- is returned and stored on the claimed operation (``operation_metadata.authority``).
* S5-05 -- INSIDE the transaction that commits the FIRST TRUSTED (``revalidate_at_promotion``, called from
  ``_apply_trust_decision`` right before ``commit_candidate``): the decider is still an active human of the tenant, still
  holds APPROVE_CANDIDATE on the review's project (the grant row is read ``FOR SHARE``: a revocation, an UPDATE of that
  row, waits for this transaction or has already committed and is seen), and the reconciliation recomputed under
  ``FOR SHARE`` of the review row (the ledger writer's ``FOR UPDATE`` conflicts) has the very digest that was approved.
  Any failure raises and rolls the promotion back: no partial TRUSTED state.

``off`` and ``audit`` keep today's legacy rule (transitional, NOT secure); ``enforce`` with no recorded authority fails
closed. NOT claimed: that a grant was issued by an authenticated human administrator (P1 SQL administrative authority:
NOT_VERIFIED), production of derived candidates (Vn+1: NOT_IMPLEMENTED), typed critique (UNEVALUATED).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import text

from src.analysis.domain.trust import artifact_digest
from src.modules.hitl.application.finding_reconciliation_service import (
    FindingReconciliationService,
    ReconciliationStale,
    has_verified_literal_source,
)
from src.modules.hitl.application.finding_review_authorization import FindingReviewerNotAuthorized
from src.modules.hitl.application.project_review_authorization import (
    AuthorizationMode,
    ProjectAuthorizationDenied,
    ProjectCapability,
    ProjectReviewAuthorizer,
)
from src.modules.hitl.application.review_findings_view import ReviewFindingsUnavailable
from src.modules.hitl.domain.finding_reconciliation import (
    BlockerCode,
    ReconciliationReceipt,
    ReconciliationResult,
)

logger = structlog.get_logger()

AUTHORITY_KEY = "authority"
AUTHORITY_VERSION = 1


class ReconciliationBlocksApproval(RuntimeError):
    """The approval cannot be taken on this candidate as it stands (HTTP 409). Nothing was created or recorded."""

    def __init__(self, result: ReconciliationResult) -> None:
        self.status = result.status.value
        self.blockers = tuple(b.code.value for b in result.blockers)
        self.derivations = tuple(d.code.value for d in result.derivations)
        self.inconsistencies = tuple(result.inconsistencies)
        super().__init__(
            "the reconciliation of the finding decisions does not allow approving this candidate: "
            f"status={self.status} blockers={list(self.blockers)} derivations={list(self.derivations)} "
            f"inconsistencies={list(self.inconsistencies)}"
        )


class PromotionNotAuthorized(PermissionError):
    """The first TRUSTED promotion was refused inside its own transaction (rolled back; HTTP 403/409)."""


@dataclass(frozen=True)
class ApprovalAuthority:
    version: int
    tenant_id: str
    user_id: str
    project_id: str
    review_row_id: str
    grant_id: str | None
    receipt: dict[str, Any]

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, raw: Any) -> ApprovalAuthority | None:
        if not isinstance(raw, dict) or raw.get("version") != AUTHORITY_VERSION:
            return None
        try:
            return cls(
                version=int(raw["version"]), tenant_id=str(raw["tenant_id"]), user_id=str(raw["user_id"]),
                project_id=str(raw["project_id"]), review_row_id=str(raw["review_row_id"]),
                grant_id=str(raw["grant_id"]) if raw.get("grant_id") else None, receipt=dict(raw["receipt"]),
            )
        except (KeyError, TypeError, ValueError):
            return None


def is_reconcilable(review_metadata: Any) -> bool:
    """A candidate-bound ANALYSIS review (structured-source trust has its own, single-act decision)."""
    return (
        isinstance(review_metadata, dict)
        and review_metadata.get("trust_candidate_required") is True
        and review_metadata.get("trust_kind") != "structured_source"
        and isinstance(review_metadata.get("candidate_binding"), dict)
    )


def _receipt_to_json(receipt: ReconciliationReceipt) -> dict[str, Any]:
    return {k: (str(v) if isinstance(v, UUID) else v) for k, v in asdict(receipt).items()}


def _receipt_from_json(raw: dict[str, Any]) -> ReconciliationReceipt:
    return ReconciliationReceipt(
        digest=str(raw["digest"]), policy_version=str(raw["policy_version"]),
        review_row_id=UUID(str(raw["review_row_id"])), project_id=UUID(str(raw["project_id"])),
        artifact_id=UUID(str(raw["artifact_id"])), artifact_version=int(raw["artifact_version"]),
        artifact_hash=str(raw["artifact_hash"]), generation=int(raw["generation"]),
        fencing_token=int(raw["fencing_token"]), ledger_revision=int(raw["ledger_revision"]),
        signable_as_is=bool(raw["signable_as_is"]), effective_content_digest=str(raw["effective_content_digest"]),
    )



# A retry after N17 must NOT try to re-reconcile a proposal that N17 already
# atomically promoted to TRUSTED. It recovers an immutable, previously taken
# decision, never signs an unreviewed candidate. All identifiers and the
# original decision hash are matched to the durable operation, and the
# production ownership CAS below still guards lease, phase and lineage.
_DURABLE_APPROVAL_RECOVERY = text("""
SELECT o.operation_metadata -> 'authority' AS saved_authority,
       r.project_id, a.artifact_id, a.artifact_hash, a.artifact_version
FROM public.resume_operations o
JOIN public.review_items r
  ON r.id = o.review_row_id AND r.tenant_id = o.tenant_id
JOIN public.document_artifacts a
  ON a.tenant_id = r.tenant_id AND a.project_id = r.project_id
 AND a.document_id = r.document_id
WHERE o.review_row_id = cast(:review_id as uuid)
  AND o.tenant_id = cast(:tenant_id as uuid)
  AND o.document_id = r.document_id AND o.project_id = r.project_id
  AND o.thread_id = r.thread_id
  AND o.source_checkpoint_id = r.checkpoint_id
  AND o.decision = 'approve'
  AND o.decision_hash = :decision_hash
  AND o.phase IN ('N17_DURABLE', 'GRAPH_COMPLETED')
  AND cast(r.current_status as text) IN
      ('PENDING_REVIEW_REQUIRED', 'PENDING_REVIEW_CONDITIONAL', 'ESCALATED')
  AND r.review_metadata ->> 'trust_candidate_required' = 'true'
  AND r.review_metadata -> 'candidate_binding' ->> 'artifact_id' = a.artifact_id::text
  AND r.review_metadata -> 'candidate_binding' ->> 'artifact_version' = a.artifact_version::text
  AND r.review_metadata -> 'candidate_binding' ->> 'artifact_hash' = a.artifact_hash
  AND a.trust_state = 'trusted' AND a.lifecycle_status = 'active'
""")


async def recorded_durable_approval(
    authorizer: ProjectReviewAuthorizer,
    *, tenant_id: UUID, user_id: UUID, review_row_id: UUID, decision_hash: str,
) -> tuple[bool, ApprovalAuthority | None]:
    """Read-only recovery proof for ALREADY durable approval; fail closed.

    A false result means ordinary S5-04 reconciliation is still mandatory.
    A true result never bypasses a first-time decision: N17 must already have
    committed the exact, now-TRUSTED artifact, and the original approval
    receipt must be preserved in ENFORCE mode.
    """
    row = (await authorizer.session.execute(
        _DURABLE_APPROVAL_RECOVERY,
        {"tenant_id": str(tenant_id), "review_id": str(review_row_id),
         "decision_hash": decision_hash},
    )).first()
    if row is None:
        return False, None
    recorded = ApprovalAuthority.from_json(row[0])
    mode = await authorizer.mode(tenant_id)
    if mode is AuthorizationMode.ENFORCE and recorded is None:
        raise PromotionNotAuthorized(
            "durable operation has no recorded human approval authority"
        )
    if recorded is not None:
        receipt = recorded.receipt
        if (
            recorded.tenant_id != str(tenant_id)
            or recorded.user_id != str(user_id)
            or recorded.project_id != str(row.project_id)
            or recorded.review_row_id != str(review_row_id)
            or receipt.get("artifact_id") != str(row.artifact_id)
            or receipt.get("artifact_hash") != row.artifact_hash
            or receipt.get("artifact_version") != row.artifact_version
            or receipt.get("signable_as_is") is not True
        ):
            raise PromotionNotAuthorized(
                "durable approval proof does not match the exact trusted artifact"
            )
    return True, recorded


async def require_reconciled_approval(
    authorizer: ProjectReviewAuthorizer,
    *,
    tenant_id: UUID,
    user_id: UUID,
    review_row_id: UUID,
    review_metadata: Any,
) -> ApprovalAuthority | None:
    """S5-04. ``None`` = not applicable (legacy mode, or not a candidate-bound analysis review): no authority is recorded."""
    if not is_reconcilable(review_metadata):
        return None
    mode = await authorizer.mode(tenant_id)
    service = FindingReconciliationService(authorizer.session, authorizer)
    try:
        result = await service.reconcile_for_member(
            tenant_id=tenant_id, user_id=user_id, review_row_id=review_row_id,
            capability=ProjectCapability.APPROVE_CANDIDATE,
        )
    except ReviewFindingsUnavailable as exc:
        raise ReconciliationStale("the candidate or its processing authority is no longer current") from exc
    # SEC-04: even the transitional OFF/AUDIT modes cannot treat an empty
    # candidate as proof that its extraction covered the source. Keep their
    # existing handling of nonempty/undecided candidates otherwise unchanged.
    if not result.outcomes or any(
        b.code is BlockerCode.SOURCE_EVIDENCE_UNVERIFIED for b in result.blockers
    ):
        raise ReconciliationBlocksApproval(result)
    if mode is AuthorizationMode.OFF:
        return None
    if not result.signable_as_is:
        if mode is AuthorizationMode.AUDIT:
            logger.warning(
                "hitl_reconciliation_would_block_approval", tenant_id=str(tenant_id), review_row_id=str(review_row_id),
                blockers=[b.code.value for b in result.blockers], derivations=[d.code.value for d in result.derivations],
            )
            return None
        raise ReconciliationBlocksApproval(result)
    if mode is AuthorizationMode.AUDIT:
        return None
    proof = await authorizer.require(
        tenant_id=tenant_id, user_id=user_id, project_id=result.project_id, capability=ProjectCapability.APPROVE_CANDIDATE
    )
    return ApprovalAuthority(
        version=AUTHORITY_VERSION, tenant_id=str(tenant_id), user_id=str(user_id), project_id=str(result.project_id),
        review_row_id=str(review_row_id), grant_id=str(proof.grant_id) if proof.grant_id else None,
        receipt=_receipt_to_json(result.receipt()),
    )


_REVIEW_FOR_PROMOTION = text(
    "SELECT project_id, review_metadata FROM public.review_items "
    "WHERE id = cast(:r as uuid) AND tenant_id = cast(:t as uuid)"
)
_AUTHORITY = text(
    "SELECT operation_metadata -> :key FROM public.resume_operations "
    "WHERE review_row_id = cast(:r as uuid) AND tenant_id = cast(:t as uuid)"
)
_TRUST_STATE = text(
    "SELECT a.trust_state, a.payload, a.artifact_hash FROM public.document_artifacts a "
    "WHERE a.artifact_id = cast(:a as uuid) AND a.tenant_id = cast(:t as uuid)"
)


async def revalidate_at_promotion(
    session: Any, *, tenant_id: UUID, review_row_id: UUID, artifact_id: UUID
) -> None:
    """S5-05. Call INSIDE the transaction that is about to commit the first TRUSTED, right before the commit statement.

    A candidate that is already TRUSTED (committed by N17 of this same operation) is not a first promotion: its
    own transaction already revalidated, and finalization must stay idempotent.
    """
    artifact = (await session.execute(_TRUST_STATE, {"a": str(artifact_id), "t": str(tenant_id)})).first()
    if artifact is None or str(artifact[0]).lower() != "proposed":
        return
    review = (await session.execute(_REVIEW_FOR_PROMOTION, {"r": str(review_row_id), "t": str(tenant_id)})).first()
    if review is None or not is_reconcilable(review[1]):
        return
    # The source gate is mandatory even for a previously claimed legacy-mode
    # operation. The promotion transaction uses the persisted exact artifact,
    # not the request or a historical human confirmation.
    payload, digest = artifact[1], artifact[2]
    bound = review[1]["candidate_binding"]
    risks = payload.get("extracted_risks") if isinstance(payload, dict) else None
    if (
        str(bound.get("artifact_id")) != str(artifact_id)
        or bound.get("artifact_hash") != digest
        or not isinstance(payload, dict)
        or artifact_digest(payload) != digest
        or not isinstance(risks, list)
        or not risks
        or any(not has_verified_literal_source(risk) for risk in risks)
    ):
        raise PromotionNotAuthorized("the exact candidate lacks verified literal source evidence")
    authorizer = ProjectReviewAuthorizer(session)
    mode = await authorizer.mode(tenant_id)
    if mode is not AuthorizationMode.ENFORCE:
        return

    raw = (await session.execute(_AUTHORITY, {"key": AUTHORITY_KEY, "r": str(review_row_id), "t": str(tenant_id)})).scalar_one_or_none()
    authority = ApprovalAuthority.from_json(raw)
    if (
        authority is None
        or authority.tenant_id != str(tenant_id)
        or authority.review_row_id != str(review_row_id)
        or authority.project_id != str(review[0])
    ):
        raise PromotionNotAuthorized(
            "no approval authority was recorded for this decision under enforce: the first TRUSTED promotion is refused"
        )
    receipt = _receipt_from_json(authority.receipt)
    try:
        # grant row FOR SHARE + member re-read + review row FOR SHARE + ledger re-reconciled: one consistent view
        current = await FindingReconciliationService(session, authorizer).verify_current_for_member(
            receipt, tenant_id=tenant_id, user_id=UUID(authority.user_id), capability=ProjectCapability.APPROVE_CANDIDATE
        )
        # Defense in depth: a matching digest alone is insufficient if the
        # candidate is not currently eligible for a final human signature.
        if not current.signable_as_is:
            raise PromotionNotAuthorized("the current reconciliation is not eligible for TRUSTED promotion")
    except ProjectAuthorizationDenied as exc:
        raise PromotionNotAuthorized(f"the approver no longer holds {exc.capability.value} on the project: {exc}") from exc
    except ReconciliationStale as exc:
        raise PromotionNotAuthorized(f"the reconciliation the approval was taken against is stale: {exc}") from exc
    except FindingReviewerNotAuthorized as exc:  # the decider is not an active human member any more
        raise PromotionNotAuthorized(f"the approver is no longer an active human member of the tenant: {exc}") from exc
