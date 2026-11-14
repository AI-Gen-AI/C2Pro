"""
LangGraph dependency providers.

Refers to Suite ID: TS-ADP-GRAPH-DI-001.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.ai.anthropic_client import AIService
from src.anonymizer.application.anonymization_service import AnonymizationService
from src.anonymizer.domain.pii_detector_service import PiiDetectorService
from src.modules.hitl.adapters.notifications.log_notification_service import (
    LogNotificationService,
)
from src.modules.hitl.adapters.persistence.repository import (
    SqlAlchemyReviewQueueRepository,
)
from src.modules.hitl.application.ports import HumanInTheLoopService
from src.modules.hitl.domain.services import ConfidenceRouter


def get_ai_service(tenant_id: str | None) -> AIService:
    """Build the AI service used by graph nodes."""
    return AIService(tenant_id=tenant_id)


def get_pii_detector_service() -> PiiDetectorService:
    """Build the PII detector used by the graph anonymizer."""
    return PiiDetectorService()


def get_anonymization_service(
    detector: PiiDetectorService,
) -> AnonymizationService:
    """Build the anonymization service used by the graph anonymizer."""
    return AnonymizationService(pii_detector=detector)


def get_hitl_service_for_graph(
    session: AsyncSession,
    tenant_id: UUID,
) -> HumanInTheLoopService:
    """Build the HITL service used by graph interrupt routing."""
    repo = SqlAlchemyReviewQueueRepository(session=session, tenant_id=tenant_id)
    return HumanInTheLoopService(
        review_queue_repo=repo,
        notification_service=LogNotificationService(),
        confidence_router=ConfidenceRouter(),
    )



def build_omniroute_pilot_ai_service(
    tenant_id: str | None,
    *,
    base_url: str,
    api_key: str,
    model: str,
) -> AIService:
    """Explicit C2Pro graph DI seam for isolated OmniRoute pilot evaluations.

    The existing get_ai_service() path is deliberately unchanged. Call this
    factory only from synthetic/staging QA; it does not auto-select an external
    model for a real tenant or replace production Anthropic routing.
    """
    from src.config import settings
    from src.analysis.adapters.ai.omniroute_pilot import OmniRoutePilotClient

    if settings.environment == "production":
        raise RuntimeError("OmniRoute pilot requires a non-production environment")
    return AIService(
        tenant_id=tenant_id,
        wrapper=OmniRoutePilotClient(
            base_url=base_url,
            api_key=api_key,
            model=model,
        ),
    )
