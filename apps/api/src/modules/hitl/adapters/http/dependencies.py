"""FastAPI dependency injection for HITL module."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.security import CurrentTenantId
from src.modules.hitl.adapters.notifications.log_notification_service import (
    LogNotificationService,
)
from src.modules.hitl.adapters.persistence.repository import (
    SqlAlchemyReviewQueueRepository,
)
from src.modules.hitl.application.ports import HumanInTheLoopService
from src.modules.hitl.domain.services import ConfidenceRouter


def get_review_queue_repo(
    db: AsyncSession = Depends(get_session),
    tenant_id: CurrentTenantId = None,  # type: ignore[assignment]
) -> SqlAlchemyReviewQueueRepository:
    return SqlAlchemyReviewQueueRepository(session=db, tenant_id=tenant_id)


def get_hitl_service(
    repo: SqlAlchemyReviewQueueRepository = Depends(get_review_queue_repo),
) -> HumanInTheLoopService:
    return HumanInTheLoopService(
        review_queue_repo=repo,
        notification_service=LogNotificationService(),
        confidence_router=ConfidenceRouter(),
    )
