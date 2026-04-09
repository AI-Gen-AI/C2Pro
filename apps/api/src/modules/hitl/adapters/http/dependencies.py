"""
I11 HITL HTTP dependency wiring.
Test Suite ID: TS-I11-HITL-HTTP-001
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.security import CurrentTenantId
from src.modules.hitl.adapters.notifications.log_notification_service import (
    LogNotificationService,
)
from src.modules.hitl.adapters.persistence.notification_config_repository import (  # TASK-BCK-025
    NotificationConfigRepository,
)
from src.modules.hitl.adapters.persistence.repository import (
    SqlAlchemyReviewQueueRepository,
)
from src.modules.hitl.application.ports import HumanInTheLoopService
from src.modules.hitl.application.resume_workflow_use_case import (
    ResumeWorkflowUseCase,  # TASK-BCK-024
)
from src.modules.hitl.domain.services import ConfidenceRouter
from src.modules.hitl.ports.notification_service import INotificationService


def get_review_queue_repo(
    db: AsyncSession = Depends(get_session),
    tenant_id: CurrentTenantId = None,  # type: ignore[assignment]
) -> SqlAlchemyReviewQueueRepository:
    return SqlAlchemyReviewQueueRepository(session=db, tenant_id=tenant_id)


def get_notification_service() -> INotificationService:
    return LogNotificationService()


def get_confidence_router() -> ConfidenceRouter:
    return ConfidenceRouter()


def get_hitl_service(
    repo: SqlAlchemyReviewQueueRepository = Depends(get_review_queue_repo),
    notification_service: INotificationService = Depends(get_notification_service),
    confidence_router: ConfidenceRouter = Depends(get_confidence_router),
) -> HumanInTheLoopService:
    return HumanInTheLoopService(
        review_queue_repo=repo,
        notification_service=notification_service,
        confidence_router=confidence_router,
    )


# TASK-BCK-024: Resume workflow use case
def get_resume_workflow_use_case(
    repo: SqlAlchemyReviewQueueRepository = Depends(get_review_queue_repo),
) -> ResumeWorkflowUseCase:
    return ResumeWorkflowUseCase(review_queue_repo=repo)


# TASK-BCK-025: Notification configuration repository
def get_notification_config_repository(
    db: AsyncSession = Depends(get_session),
) -> NotificationConfigRepository:
    return NotificationConfigRepository(session=db)
