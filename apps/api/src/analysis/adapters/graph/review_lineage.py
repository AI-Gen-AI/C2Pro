"""Taking a review's checkpoint lineage over for the current processing attempt.

C2PRO #758.

A takeover inherits the ReviewItem its predecessor created -- `route_for_review`
deduplicates on the document -- so that row keeps naming the SUPERSEDED
attempt's thread and checkpoint until somebody rebinds it. Until then a human
approving the review resumes the dead attempt's lineage, and a direct HITL
resume runs outside the processing authority, so the #711 fence cannot stop it.

This lives in its own module because the claim must happen at the moment an
attempt becomes authoritative -- BEFORE its graph starts -- and is re-asserted
at the HITL gate as defense-in-depth. Both callers need the same fenced,
idempotent operation.
"""

from __future__ import annotations

from uuid import UUID

import structlog

from src.analysis.adapters.graph.dependencies import get_hitl_service_for_graph
from src.core.checkpoint_lineage import is_authority_scoped_analysis_thread
from src.core.database import get_session_with_tenant
from src.core.processing_authority import current_authority, fence_current
from src.core.resume_lineage import authority_lineage, read_review_lineage

__all__ = ["claim_review_lineage_for_current_attempt"]


async def claim_review_lineage_for_current_attempt(
    *, thread_id: str | None, tenant_id: str | None, document_id: str | None
) -> None:
    """Bind the active review to THIS processing attempt's checkpoint thread.

    #758. Deliberately narrow:

    * no-ops outside a processing worker (``current_authority()`` is None), so
      a direct HITL resume -- which re-executes this node from the top -- can
      never rewrite the lineage it is resuming;
    * no-ops unless this run's thread is authority-scoped, so legacy lineages
      (including the UUID-style threads still present in production, which
      carry no checkpoint id) keep working exactly as before;
    * no-ops when the review already names this thread AND already records
      this exact attempt's processing lineage.

    That last condition is why a review this attempt created itself is still
    claimed. ``route_for_review`` writes the thread but knows nothing about
    the #711 grant, so the row would otherwise carry a thread with no
    generation or fence beside it -- unfenced, and therefore exempt from the
    currency comparison every later seam performs (see
    :mod:`src.core.resume_lineage`). Stamping it here is what makes a fresh
    review fenced from the moment it becomes actionable.

    Fails CLOSED for an authority-scoped attempt: if ownership of the lineage
    cannot be established, this attempt must not go on to present an
    actionable review that resumes somebody else's checkpoint. Raising here
    leaves the document pending and retryable, which is the honest outcome --
    unlike the routing block above, which fails OPEN to an interrupt because
    pausing for a human is safer than auto-approving.
    """
    if not thread_id or not tenant_id or not document_id:
        return
    authority = current_authority()
    if authority is None:
        return
    if not is_authority_scoped_analysis_thread(thread_id):
        return
    generation, fencing_token = authority_lineage(authority)

    async with get_session_with_tenant(UUID(tenant_id)) as session:
        # Same fence as every other durable seam: a worker that lost
        # authority cannot take a lineage over.
        await fence_current(session)
        service = get_hitl_service_for_graph(session=session, tenant_id=UUID(tenant_id))
        review = await service.review_queue_repo.find_active_review(
            document_id=UUID(document_id),
            review_type="analysis_critique",
        )
        if review is None:
            return
        row_id = review.metadata.get("row_id")
        if not row_id:
            raise RuntimeError(
                "cannot claim the checkpoint lineage: active review for document "
                f"{document_id} has no row identity"
            )
        lineage = await read_review_lineage(
            session, review_row_id=UUID(str(row_id)), tenant_id=UUID(tenant_id)
        )
        if (
            lineage is not None
            and lineage.thread_id == thread_id
            and lineage.lineage_generation == generation
            and lineage.lineage_fencing_token == fencing_token
        ):
            return
        await service.review_queue_repo.claim_checkpoint_lineage(
            row_id=UUID(str(row_id)),
            thread_id=thread_id,
            lineage_generation=generation,
            lineage_fencing_token=fencing_token,
        )
        structlog.get_logger().info(
            "checkpoint_lineage_claimed",
            document_id=document_id,
            thread_id=thread_id,
            superseded_thread_id=lineage.thread_id if lineage else None,
            lineage_generation=generation,
            lineage_fencing_token=fencing_token,
        )
