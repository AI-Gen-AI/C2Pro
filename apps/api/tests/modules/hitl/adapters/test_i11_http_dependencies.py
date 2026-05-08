"""
I11 - HITL HTTP Dependency Injection
Test Suite ID: TS-I11-HITL-HTTP-001
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from src.modules.hitl.adapters.http.dependencies import (
    get_confidence_router,
    get_hitl_service,
    get_notification_service,
)
from src.modules.hitl.adapters.notifications.log_notification_service import (
    LogNotificationService,
)
from src.modules.hitl.adapters.notifications.notification_router import (
    NotificationRouter,
)
from src.modules.hitl.domain.services import ConfidenceRouter
from src.modules.hitl.ports.review_queue_repository import IReviewQueueRepository


def test_i11_notification_dependency_returns_adapter_instance() -> None:
    """
    TS-I11-HITL-HTTP-001:
    HTTP dependency layer must expose a dedicated notification provider.
    """
    service = get_notification_service()

    assert isinstance(service, NotificationRouter)


def test_i11_confidence_router_dependency_returns_domain_router() -> None:
    """
    TS-I11-HITL-HTTP-001:
    HTTP dependency layer must expose a dedicated confidence router provider.
    """
    router = get_confidence_router()

    assert isinstance(router, ConfidenceRouter)


def test_i11_hitl_service_uses_injected_collaborators() -> None:
    """
    TS-I11-HITL-HTTP-001:
    HITL service provider must compose the service from injected collaborators
    rather than constructing them inline.
    """
    repo = AsyncMock(spec=IReviewQueueRepository)
    notification_service = LogNotificationService()
    confidence_router = ConfidenceRouter()

    service = get_hitl_service(
        repo=repo,
        notification_service=notification_service,
        confidence_router=confidence_router,
    )

    assert service.review_queue_repo is repo
    assert service.notification_service is notification_service
    assert service.confidence_router is confidence_router
