"""Who may take the FINAL human decision on a review (approve / reject / resume): an active human of the tenant.

The final decision is the act that turns a PROPOSED candidate into TRUSTED (or terminates it). It was reachable by any
authenticated principal of the tenant -- including VIEWER and API -- and ``/hitl/resume/{id}`` carried no actor at
all. This module is the single role rule for that act. It reuses the identity authority the findings routes already
use (``authorize_finding_reviewer``: a server-side principal, active, ADMIN or USER, of the current tenant) and is
enforced twice: at the HTTP boundary (before any state is read) and in ``ResumeWorkflowUseCase.execute`` (so no other
caller can finalize without a proven decider).

What this is NOT: a project-level permission. Being an active ADMIN/USER of the tenant still says nothing about a
particular project's review; that is the ratified D1-D8 model (S5-01/S5-02) and is not implemented here. Likewise it
does not grant ADMIN or USER anything they could not already do.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.modules.hitl.application.finding_review_authorization import (
    FindingReviewerNotAuthorized,
    authorize_finding_reviewer,
)


class FinalDecisionNotAuthorized(PermissionError):
    """The caller is not an active human of this tenant, so it cannot approve, reject or resume a review.

    A ``PermissionError`` (not a ``ValueError``) on purpose: the HITL routes map ``ValueError`` to 400/404 and must
    never answer a denial as a bad request.
    """


@dataclass(frozen=True)
class AuthorizedFinalDecider:
    """Proof that the server authenticated a human of ``tenant_id``. Never built from request JSON."""

    tenant_id: UUID
    user_id: UUID
    display_name: str


def authorize_final_decider(user: Any, *, tenant_id: UUID) -> AuthorizedFinalDecider:
    """Fail closed: VIEWER, API, inactive, another tenant's user or no principal at all are all refused."""
    try:
        reviewer = authorize_finding_reviewer(user, tenant_id=tenant_id)
    except FindingReviewerNotAuthorized as exc:
        raise FinalDecisionNotAuthorized("an active human reviewer of the current tenant is required") from exc
    name = getattr(user, "full_name", None)
    return AuthorizedFinalDecider(
        tenant_id=reviewer.tenant_id,
        user_id=reviewer.reviewer_id,
        display_name=name.strip() if isinstance(name, str) and name.strip() else str(reviewer.reviewer_id),
    )


__all__ = ["AuthorizedFinalDecider", "FinalDecisionNotAuthorized", "authorize_final_decider"]
