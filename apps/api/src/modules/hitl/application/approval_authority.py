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

from src.modules.hitl.application.finding_reconciliation_service import (
    FindingReconciliationService,
    ReconciliationStale,
)
from src.modules.hitl.application.finding_review_authorization import FindingReviewerNotAuthorized
from src.modules.hitl.application.project_review_authorization import (
    AuthorizationMode,
    ProjectAuthorizationDenied,
    ProjectCapability,
    ProjectReviewAuthorizer,
)
from src.modules.hitl.domain.finding_reconciliation import (
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
    if mode is AuthorizationMode.OFF:
        return None
    service = FindingReconciliationService(authorizer.session, authorizer)
    result = await service.reconcile_for_member(
        tenant_id=tenant_id, user_id=user_id, review_row_id=review_row_id, capability=ProjectCapability.APPROVE_CANDIDATE
    )
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
    "SELECT a.trust_state FROM public.document_artifacts a "
    "WHERE a.artifact_id = cast(:a as uuid) AND a.tenant_id = cast(:t as uuid)"
)


async def revalidate_at_promotion(
    session: Any, *, tenant_id: UUID, review_row_id: UUID, artifact_id: UUID
) -> None:
    """S5-05. Call INSIDE the transaction that is about to commit the first TRUSTED, right before the commit statement.

    A candidate that is already TRUSTED (committed by N17 of this same operation) is not a first promotion: its
    own transaction already revalidated, and finalization must stay idempotent.
    """
    trust_state = (await session.execute(_TRUST_STATE, {"a": str(artifact_id), "t": str(tenant_id)})).scalar_one_or_none()
    if str(trust_state or "").lower() != "proposed":
        return
    review = (await session.execute(_REVIEW_FOR_PROMOTION, {"r": str(review_row_id), "t": str(tenant_id)})).first()
    if review is None or not is_reconcilable(review[1]):
        return
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
        await FindingReconciliationService(session, authorizer).verify_current_for_member(
            receipt, tenant_id=tenant_id, user_id=UUID(authority.user_id), capability=ProjectCapability.APPROVE_CANDIDATE
        )
    except ProjectAuthorizationDenied as exc:
        raise PromotionNotAuthorized(f"the approver no longer holds {exc.capability.value} on the project: {exc}") from exc
    except ReconciliationStale as exc:
        raise PromotionNotAuthorized(f"the reconciliation the approval was taken against is stale: {exc}") from exc
    except FindingReviewerNotAuthorized as exc:  # the decider is not an active human member any more
        raise PromotionNotAuthorized(f"the approver is no longer an active human member of the tenant: {exc}") from exc
