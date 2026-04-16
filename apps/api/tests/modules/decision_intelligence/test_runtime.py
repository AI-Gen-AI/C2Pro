"""Tests for Decision Intelligence runtime composition root.

Refers to Suite ID: TS-I13-E2E-REAL-001.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.modules.decision_intelligence.application.ports import (
    CoherenceScoringPort,
    ExtractionPort,
    HITLPort,
    IngestionPort,
    RetrievalPort,
)
from src.modules.decision_intelligence.runtime import (
    DecisionIntelligenceServices,
    build_decision_intelligence_services,
)


@asynccontextmanager
async def _stub_session_provider():
    yield SimpleNamespace(execute=AsyncMock())


def test_build_services_returns_all_ports() -> None:
    wrapper = SimpleNamespace(generate=AsyncMock())
    services = build_decision_intelligence_services(
        session_provider=_stub_session_provider,
        embed_fn=AsyncMock(return_value=[[0.0] * 4]),
        anthropic_wrapper=wrapper,  # type: ignore[arg-type]
    )

    assert isinstance(services, DecisionIntelligenceServices)
    assert isinstance(services.ingestion, IngestionPort)
    assert isinstance(services.extraction, ExtractionPort)
    assert isinstance(services.retrieval, RetrievalPort)
    assert isinstance(services.coherence, CoherenceScoringPort)
    assert isinstance(services.hitl, HITLPort)


@pytest.mark.asyncio
async def test_built_services_can_be_attached_to_app_state_shape() -> None:
    wrapper = SimpleNamespace(generate=AsyncMock())
    services = build_decision_intelligence_services(
        session_provider=_stub_session_provider,
        embed_fn=AsyncMock(return_value=[[0.0] * 4]),
        anthropic_wrapper=wrapper,  # type: ignore[arg-type]
    )

    fake_state: dict[str, object] = {}
    fake_state["decision_ingestion_service"] = services.ingestion
    fake_state["decision_extraction_service"] = services.extraction
    fake_state["decision_retrieval_service"] = services.retrieval
    fake_state["decision_coherence_scoring_service"] = services.coherence
    fake_state["decision_hitl_service"] = services.hitl

    # Sanity: ingestion adapter still functions independently.
    result = await services.ingestion.ingest_document(b"hello world")
    assert result["source"] in {"plaintext", "pdf"}
