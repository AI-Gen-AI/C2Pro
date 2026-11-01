"""Durable record of an evaluation that withheld its Score (S3).

``/coherence/evaluate`` deliberately persists NO ``CoherenceResult`` when the evidence cannot support a Score
(``global_score`` is NOT NULL and 0-100: a fake row would invent a number). Before this, the reason therefore lived in
that single HTTP answer and the persisted dashboard could not repeat it. The withheld evaluation is now an append-only
``coherence.evaluation_withheld`` project event (existing table, tenant-scoped, no migration) carrying only the reason,
the missing dimensions and the score version -- never clause text or a prompt. The caller owns the transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.coherence.domain.score_reasons import WITHHELD_EVALUATION_EVENT
from src.temporal.adapters.persistence.models import ProjectEventORM
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.domain.project_event import ProjectEvent


@dataclass(frozen=True)
class WithheldEvaluation:
    reason: str
    missing_dimensions: list[str] | None
    score_version: Literal["coherence-v1", "coherence-v2"] | None
    alert_count: int
    evaluated_at: datetime


async def record_withheld_evaluation(
    db: AsyncSession,
    *,
    project_id: UUID,
    tenant_id: UUID,
    actor_user_id: UUID | None,
    reason: str | None,
    missing_dimensions: list[str] | None,
    score_version: str | None,
    alert_count: int,
) -> None:
    """Append the withheld evaluation. A scoreless result without a reason is not recorded (nothing to say)."""
    if not reason:
        return
    now = datetime.now(UTC).replace(tzinfo=None)
    await SqlAlchemyProjectEventRepository(db).append(
        ProjectEvent(
            event_id=uuid4(),
            project_id=project_id,
            tenant_id=tenant_id,
            event_type=WITHHELD_EVALUATION_EVENT,
            payload={
                "score_reason": reason,
                "score_missing_dimensions": list(missing_dimensions or []),
                "score_version": score_version,
                "alert_count": alert_count,
            },
            actor=f"user:{actor_user_id}" if actor_user_id else None,
            occurred_at=now,
            created_at=now,
        )
    )


async def latest_withheld_evaluation(
    db: AsyncSession, *, project_id: UUID, tenant_id: UUID
) -> WithheldEvaluation | None:
    """The newest withheld evaluation of THIS tenant's project, or None."""
    row = await db.scalar(
        select(ProjectEventORM)
        .where(
            ProjectEventORM.project_id == project_id,
            ProjectEventORM.tenant_id == tenant_id,
            ProjectEventORM.event_type == WITHHELD_EVALUATION_EVENT,
        )
        .order_by(ProjectEventORM.occurred_at.desc(), ProjectEventORM.created_at.desc())
        .limit(1)
    )
    if row is None:
        return None
    payload = row.payload or {}
    reason = payload.get("score_reason")
    if not isinstance(reason, str) or not reason:
        return None
    missing = payload.get("score_missing_dimensions")
    version = payload.get("score_version")
    count = payload.get("alert_count")
    return WithheldEvaluation(
        reason=reason,
        missing_dimensions=[str(m) for m in missing] if isinstance(missing, list) else None,
        score_version=version if version in ("coherence-v1", "coherence-v2") else None,
        alert_count=int(count) if isinstance(count, int) else 0,
        evaluated_at=row.occurred_at,
    )


__all__ = ["WithheldEvaluation", "latest_withheld_evaluation", "record_withheld_evaluation"]
