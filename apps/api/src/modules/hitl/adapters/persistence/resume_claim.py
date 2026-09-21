"""DB-authoritative exactly-once claim for a HITL workflow resume.

C2PRO P0b true-resume hotfix -- exactly-once boundary.

Reproduced defect: two approve calls for the same review (sequentially OR
concurrently) each drove the graph to completion, executing N17 twice and
persisting two analyses plus two graph.completed events. Verified against a
real compiled graph + real AsyncPostgresSaver.

Why this lives in its own short transaction rather than in the request's:
``get_session`` (core/database.py) commits only AFTER the endpoint returns,
so the whole HITL request is one long transaction. A compare-and-set
flushed there would be invisible to other API workers until the request
finished -- useless as a mutual-exclusion gate -- and a ``SELECT ... FOR
UPDATE`` held there would block the graph itself, because graph nodes open
their OWN sessions/connections (``get_session_with_tenant``) and
``human_interrupt_node`` writes review rows on resume. That combination
self-deadlocks: the request cannot commit until the graph returns, and the
graph cannot proceed until the request commits.

So the claim is a single atomic UPDATE committed immediately in a dedicated
session, before the graph runs. Exactly one caller observes a returned row.

The claim deliberately does NOT change current_status. The review stays
PENDING until the workflow has actually reached durable completion, which
keeps the externally visible status truthful (a claimed-but-unfinished
review is still pending, not approved) and is also what keeps
``route_for_review``'s find_active_review idempotency guard effective when
the resumed interrupt node re-executes from the top -- otherwise that
re-execution would create an additional review row.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import text

logger = structlog.get_logger()

_PENDING_STATUSES = ("PENDING_REVIEW_REQUIRED", "PENDING_REVIEW_CONDITIONAL")

# Single-statement compare-and-set. Postgres evaluates the WHERE and applies
# the row update atomically, so concurrent callers serialise on the row and
# exactly one sees a RETURNING row. The `resume_claim IS NULL` predicate is
# the "compare"; writing the token is the "set".
_CLAIM_SQL = text(
    """
    UPDATE review_items
       SET review_metadata = coalesce(review_metadata, '{}'::jsonb)
                             || jsonb_build_object(
                                    'resume_claim',
                                    jsonb_build_object(
                                        'token', cast(:token as text),
                                        'checkpoint_id', cast(:checkpoint_id as text),
                                        'claimed_at', cast(:claimed_at as text)
                                    )
                                )
     WHERE id = cast(:row_id as uuid)
       AND tenant_id = cast(:tenant_id as uuid)
       AND current_status = ANY(cast(:pending_statuses as reviewstatus[]))
       AND (review_metadata -> 'resume_claim') IS NULL
    RETURNING id
    """
)

_RELEASE_SQL = text(
    """
    UPDATE review_items
       SET review_metadata = coalesce(review_metadata, '{}'::jsonb) - 'resume_claim'
     WHERE id = cast(:row_id as uuid)
       AND tenant_id = cast(:tenant_id as uuid)
       AND review_metadata -> 'resume_claim' ->> 'token' = cast(:token as text)
    RETURNING id
    """
)


async def claim_resume(
    *,
    row_id: UUID,
    tenant_id: UUID,
    checkpoint_id: str | None,
    token: str,
    claimed_at: str,
    session_factory: Any = None,
) -> bool:
    """Atomically claim this review for exactly one resume attempt.

    Returns True for the single winning caller, False for every other
    caller (already claimed, already decided, or not this tenant's row).
    Commits in its own transaction so the outcome is immediately visible
    to other API workers.
    """
    session_cm = _resolve_session(session_factory, tenant_id)
    async with session_cm as session:
        result = await session.execute(
            _CLAIM_SQL,
            {
                "row_id": str(row_id),
                "tenant_id": str(tenant_id),
                "checkpoint_id": checkpoint_id,
                "token": token,
                "claimed_at": claimed_at,
                "pending_statuses": list(_PENDING_STATUSES),
            },
        )
        claimed = result.first() is not None
    logger.info(
        "hitl_resume_claim",
        row_id=str(row_id),
        checkpoint_id=checkpoint_id,
        claimed=claimed,
    )
    return claimed


async def release_resume_claim(
    *,
    row_id: UUID,
    tenant_id: UUID,
    token: str,
    session_factory: Any = None,
) -> bool:
    """Release a claim this caller owns, so a failed resume stays retryable.

    Only the holder of ``token`` can release, so a late/rogue caller can
    never clear someone else's in-flight claim.
    """
    session_cm = _resolve_session(session_factory, tenant_id)
    async with session_cm as session:
        result = await session.execute(
            _RELEASE_SQL,
            {"row_id": str(row_id), "tenant_id": str(tenant_id), "token": token},
        )
        released = result.first() is not None
    logger.info("hitl_resume_claim_released", row_id=str(row_id), released=released)
    return released


def _resolve_session(session_factory: Any, tenant_id: UUID) -> Any:
    """Async context manager yielding a session that commits on clean exit.

    Defaults to the application's tenant-scoped session (which sets the RLS
    tenant and commits on exit); tests inject their own factory.
    """
    if session_factory is not None:
        return session_factory(tenant_id)
    from src.core.database import get_session_with_tenant

    return get_session_with_tenant(tenant_id)
