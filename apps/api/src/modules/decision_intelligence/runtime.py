"""Composition root for Decision Intelligence runtime services.

Builds the real port adapters required by the I13 orchestration flow
and exposes them through a single ``DecisionIntelligenceServices``
bundle. Invoked from ``src/main.py`` during FastAPI lifespan startup so
that the HTTP router can resolve collaborators from ``app.state``
without needing per-request dependency injection.

Refers to Suite ID: TS-I13-E2E-REAL-001.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.ai.anthropic_wrapper import AnthropicWrapper, get_anthropic_wrapper
from src.modules.decision_intelligence.adapters.ports.coherence_scoring_port_adapter import (
    CoherenceScoringPortAdapter,
)
from src.modules.decision_intelligence.adapters.ports.extraction_port_adapter import (
    ExtractionPortAdapter,
)
from src.modules.decision_intelligence.adapters.ports.ingestion_port_adapter import (
    IngestionPortAdapter,
)
from src.modules.decision_intelligence.adapters.ports.retrieval_port_adapter import (
    RetrievalPortAdapter,
)
from src.modules.decision_intelligence.application.ports import (
    CoherenceScoringPort,
    ExtractionPort,
    HITLPort,
    IngestionPort,
    RetrievalPort,
)
from src.modules.hitl.adapters.notifications.log_notification_service import (
    LogNotificationService,
)
from src.modules.hitl.adapters.persistence.repository import (
    SqlAlchemyReviewQueueRepository,
)
from src.modules.hitl.application.human_in_the_loop_service import HumanInTheLoopService
from src.modules.hitl.domain.entities import ImpactLevel
from src.modules.hitl.domain.services import ConfidenceRouter
from src.modules.scoring.application.ports import CoherenceScoringService

logger = structlog.get_logger()

SessionProvider = Callable[[], AbstractAsyncContextManager[AsyncSession]]
EmbedFn = Callable[[list[str]], Awaitable[list[list[float]]]]


@dataclass(frozen=True)
class DecisionIntelligenceServices:
    """Bundle of runtime-wired Decision Intelligence port adapters."""

    ingestion: IngestionPort
    extraction: ExtractionPort
    retrieval: RetrievalPort
    coherence: CoherenceScoringPort
    hitl: HITLPort


class _SessionFactoryHITLAdapter:
    """HITLPort implementation that opens fresh sessions per call.

    ``HumanInTheLoopService`` requires a live ``AsyncSession`` via its
    review-queue repository, but the Decision Intelligence adapters are
    process-scoped (attached to ``app.state``). This adapter defers
    session creation until each port call so that sessions never leak
    across requests.
    """

    def __init__(self, *, session_provider: SessionProvider) -> None:
        self._session_provider = session_provider
        self._confidence_router = ConfidenceRouter()
        self._notification_service = LogNotificationService()

    async def route_for_review(
        self,
        item_id: UUID,
        item_type: str,
        confidence: float,
        impact_level: str,
        item_data: dict[str, Any],
    ) -> str:
        try:
            level = ImpactLevel(impact_level.upper())
        except ValueError:
            level = ImpactLevel.MEDIUM

        async with self._session_provider() as session:
            service = self._build_service(session)
            status = await service.route_for_review(
                item_id=item_id,
                item_type=item_type,
                confidence=confidence,
                impact_level=level,
                item_data=item_data,
            )
            return status.value

    async def approve_item(
        self,
        item_id: UUID,
        reviewer_id: UUID,
        reviewer_name: str,
    ) -> dict[str, Any]:
        async with self._session_provider() as session:
            service = self._build_service(session)
            item = await service.approve_item(
                item_id=item_id,
                reviewer_id=reviewer_id,
                reviewer_name=reviewer_name,
            )
            return {
                "item_id": str(item.item_id),
                "item_type": item.item_type,
                "current_status": item.current_status.value,
                "confidence": item.confidence,
                "impact_level": item.impact_level.value,
                "approved_by": item.approved_by,
                "approved_at": item.approved_at.isoformat() if item.approved_at else None,
            }

    def _build_service(self, session: AsyncSession) -> HumanInTheLoopService:
        repo = SqlAlchemyReviewQueueRepository(session=session)
        return HumanInTheLoopService(
            review_queue_repo=repo,
            notification_service=self._notification_service,
            confidence_router=self._confidence_router,
        )


def _default_session_provider() -> SessionProvider:
    """Return an async context manager yielding a raw DB session."""

    from src.core.database import get_raw_session

    def _provider() -> AbstractAsyncContextManager[AsyncSession]:
        return get_raw_session()

    return _provider


def _default_embed_fn() -> EmbedFn:
    """Return the OpenAI embeddings helper used by the RAG pipeline."""

    from src.documents.adapters.rag.rag_service import _embed_texts

    async def _embed(texts: list[str]) -> list[list[float]]:
        return await _embed_texts(texts)

    return _embed


def build_decision_intelligence_services(
    *,
    session_provider: SessionProvider | None = None,
    embed_fn: EmbedFn | None = None,
    anthropic_wrapper: AnthropicWrapper | None = None,
    coherence_scoring_service: CoherenceScoringService | None = None,
) -> DecisionIntelligenceServices:
    """Compose the Decision Intelligence services bundle.

    Every parameter is optional so tests can inject doubles. Production
    callers (``main.py``) pass no arguments and rely on the defaults
    backed by the real infrastructure (pgvector, OpenAI embeddings,
    Anthropic wrapper, SQLAlchemy session factory).
    """

    provider = session_provider or _default_session_provider()
    embed = embed_fn or _default_embed_fn()
    wrapper = anthropic_wrapper or get_anthropic_wrapper()
    scoring_service = coherence_scoring_service or CoherenceScoringService()

    ingestion = IngestionPortAdapter()
    extraction = ExtractionPortAdapter(wrapper=wrapper)
    retrieval = RetrievalPortAdapter(session_provider=provider, embed_fn=embed)
    coherence = CoherenceScoringPortAdapter(service=scoring_service)
    hitl = _SessionFactoryHITLAdapter(session_provider=provider)

    logger.info(
        "decision_intelligence_services_built",
        ingestion=type(ingestion).__name__,
        extraction=type(extraction).__name__,
        retrieval=type(retrieval).__name__,
        coherence=type(coherence).__name__,
        hitl=type(hitl).__name__,
    )
    return DecisionIntelligenceServices(
        ingestion=ingestion,
        extraction=extraction,
        retrieval=retrieval,
        coherence=coherence,
        hitl=hitl,
    )


@asynccontextmanager
async def _noop_session() -> AsyncIterator[AsyncSession]:  # pragma: no cover - helper
    """Placeholder so type-checkers accept ``AbstractAsyncContextManager[AsyncSession]``.

    Not intended for runtime use. ``build_decision_intelligence_services``
    always resolves a real provider.
    """
    raise RuntimeError("_noop_session must not be called")
    yield
