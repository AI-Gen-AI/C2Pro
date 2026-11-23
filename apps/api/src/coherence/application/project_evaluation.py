"""JV1-A17 post-approval coherence evaluation (draft, stacked on A15).

All scheduling requires a completed human approval and an explicitly bound tenant.
The background task opens a fresh tenant-scoped DB session; it never reuses the
HTTP request session. The evaluation uses deterministic low-budget mode.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID

import structlog
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session_with_tenant
from src.modules.hitl.domain.entities import ReviewStatus

logger = structlog.get_logger()


def queue_post_approval_evaluation(
    background_tasks: BackgroundTasks,
    *,
    review: Any,
    tenant_id: UUID,
    actor_user_id: UUID,
    newly_approved: bool,
) -> bool:
    """Only a *new* completed approval may request a project recalculation.

    Project identity is read from the authoritative server-resolved review,
    never from the HTTP client's approval payload. A contradictory tenant ID
    in the review fails closed.
    """
    if not newly_approved:
        return False
    review_status = getattr(review, "current_status", None)
    if review_status not in (ReviewStatus.APPROVED, ReviewStatus.APPROVED.value):
        return False

    metadata = getattr(review, "metadata", None) or {}
    item_data = getattr(review, "item_data", None) or {}
    if not isinstance(metadata, dict) or not isinstance(item_data, dict):
        return False

    try:
        recorded_tenants = [
            UUID(str(raw))
            for raw in (metadata.get("tenant_id"), item_data.get("tenant_id"))
            if raw is not None
        ]
        if any(recorded != tenant_id for recorded in recorded_tenants):
            logger.warning("a17_evaluation_refused_tenant_mismatch")
            return False

        recorded_projects = [
            UUID(str(raw))
            for raw in (metadata.get("project_id"), item_data.get("project_id"))
            if raw is not None
        ]
        if not recorded_projects or len(set(recorded_projects)) != 1:
            logger.warning("a17_evaluation_refused_project_conflict")
            return False
        project_id = recorded_projects[0]
    except (TypeError, ValueError, AttributeError):
        logger.warning("a17_evaluation_refused_invalid_identity")
        return False

    background_tasks.add_task(
        run_project_evaluation_after_approval,
        tenant_id=tenant_id,
        project_id=project_id,
        actor_user_id=actor_user_id,
    )
    return True


async def _run_evaluation(payload: Any, db: AsyncSession, user: Any) -> Any:
    """Compatibility adapter to the existing /coherence/evaluate use case.

    A17's subsequent extraction will move the endpoint body out of router.py.
    Keeping this late-bound avoids importing the HTTP router while the module
    is initialized and keeps the current public endpoint behavior unchanged.
    """
    from src.coherence.router import evaluate_project_coherence, get_flags_service

    return await evaluate_project_coherence(
        payload,
        include_diagnostics=False,
        db=db,
        current_user=user,
        flags_service=get_flags_service(db),
    )


async def run_project_evaluation_after_approval(
    *, tenant_id: UUID, project_id: UUID, actor_user_id: UUID
) -> None:
    """Re-evaluate in a fresh RLS-bound session after the response is accepted.

    Background work failures must not retroactively change a durable human
    decision into an HTTP failure. They remain observable and retryable by
    an explicit later evaluation; this draft does not silently claim success.
    """
    from src.coherence.router import CoherenceEvaluateRequest

    payload = CoherenceEvaluateRequest(
        project_id=project_id,
        low_budget_mode=True,
        include_rag_similarity=False,
    )
    actor = SimpleNamespace(tenant_id=tenant_id, id=actor_user_id)
    try:
        async with get_session_with_tenant(tenant_id) as db:
            await _run_evaluation(payload, db, actor)
    except Exception:
        # No exception details or document content in structured event fields.
        logger.exception("a17_postapproval_evaluation_failed")
        return
    logger.info("a17_postapproval_evaluation_finished", project_id=str(project_id))
