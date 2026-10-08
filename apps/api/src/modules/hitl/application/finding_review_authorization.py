"""Human-only reviewer identity and input validation for PQ-HITL-04C3.

This is an application-boundary contract, not an HTTP endpoint or a final
approval. A future route MUST obtain User from the authenticated session,
tenant from middleware and scoped review-row identity from the URL. Never
accept a client-supplied reviewer_id, tenant_id or review-row id.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.core.auth.models import UserRole
from src.modules.hitl.domain.finding_decision import FindingDecisionAction


class FindingReviewerNotAuthorized(ValueError):
    """The caller cannot record human HITL decisions for this tenant."""


@dataclass(frozen=True)
class AuthorizedFindingReviewer:
    tenant_id: UUID
    reviewer_id: UUID


def authorize_finding_reviewer(
    user: Any,
    *,
    tenant_id: UUID,
) -> AuthorizedFindingReviewer:
    """Derive principal from auth, not request JSON; fail closed for API/viewer."""
    if (
        user is None
        or not isinstance(getattr(user, "id", None), UUID)
        or not isinstance(getattr(user, "tenant_id", None), UUID)
        or user.tenant_id != tenant_id
        or getattr(user, "is_active", False) is not True
        or getattr(user, "role", None) not in {UserRole.ADMIN, UserRole.USER}
    ):
        raise FindingReviewerNotAuthorized("active human reviewer of current tenant required")
    return AuthorizedFindingReviewer(tenant_id=tenant_id, reviewer_id=user.id)


class FindingDecisionSubmission(BaseModel):
    """Client may pin the candidate and propose an action; never the actor.

    Server must reconstruct the exact CandidateReviewIdentity from the
    tenant-scoped review row, artifact and processing authority in the same
    transaction. This payload is only an optimistic-concurrency expectation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_id: UUID
    artifact_version: int = Field(ge=1)
    artifact_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_revision_id: UUID
    generation: int = Field(ge=0)
    fencing_token: int = Field(ge=0)
    source_item_id: str = Field(min_length=1)
    ordinal: int = Field(ge=0)
    action: FindingDecisionAction
    expected_ledger_revision: int = Field(ge=0)
    idempotency_key: str = Field(min_length=8, max_length=128)
    reason: str | None = None
    proposed_text: str | None = None

    @model_validator(mode="after")
    def enforce_provisional_action(self) -> FindingDecisionSubmission:
        if not self.source_item_id.strip() or not self.idempotency_key.strip():
            raise ValueError("stable source identity and replay key required")
        if self.action is FindingDecisionAction.CORRECTION_PROPOSED:
            if not (self.reason and self.reason.strip()):
                raise ValueError("proposed correction requires a reason")
            if not (self.proposed_text and self.proposed_text.strip()):
                raise ValueError("proposed correction requires replacement text")
        elif self.proposed_text is not None:
            raise ValueError("only corrections may carry replacement text")
        if self.action in (
            FindingDecisionAction.DISMISSED,
            FindingDecisionAction.NEEDS_INFO,
        ) and not (self.reason and self.reason.strip()):
            raise ValueError("non-confirmation decisions require a reason")
        return self
