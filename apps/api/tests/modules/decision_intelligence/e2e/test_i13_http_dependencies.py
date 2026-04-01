"""
I13 - Decision Intelligence HTTP Dependency Injection
Test Suite ID: TS-I13-E2E-REAL-001
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from src.modules.decision_intelligence.adapters.http.router import (
    get_coherence_scoring_service,
    get_decision_orchestration_service,
    get_extraction_service,
    get_hitl_service,
    get_ingestion_service,
    get_retrieval_service,
)


def _request_with_state(**services: object) -> SimpleNamespace:
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(**services)))


def test_i13_http_dependency_providers_fail_closed_when_runtime_ports_are_not_wired() -> None:
    """
    TS-I13-E2E-REAL-001:
    Decision intelligence HTTP layer must fail closed with an explicit runtime
    error when real collaborators are not wired.
    """
    request = _request_with_state()

    for provider in (
        get_ingestion_service,
        get_extraction_service,
        get_retrieval_service,
        get_coherence_scoring_service,
        get_hitl_service,
    ):
        with pytest.raises(HTTPException, match="requires real port implementations"):
            provider(request=request)


def test_i13_http_dependency_providers_return_runtime_wired_ports() -> None:
    """
    TS-I13-E2E-REAL-001:
    Decision intelligence HTTP layer must expose the real collaborators that
    the runtime wires into app.state.
    """
    ingestion = AsyncMock()
    extraction = AsyncMock()
    retrieval = AsyncMock()
    coherence = AsyncMock()
    hitl = AsyncMock()
    request = _request_with_state(
        decision_ingestion_service=ingestion,
        decision_extraction_service=extraction,
        decision_retrieval_service=retrieval,
        decision_coherence_scoring_service=coherence,
        decision_hitl_service=hitl,
    )

    assert get_ingestion_service(request=request) is ingestion
    assert get_extraction_service(request=request) is extraction
    assert get_retrieval_service(request=request) is retrieval
    assert get_coherence_scoring_service(request=request) is coherence
    assert get_hitl_service(request=request) is hitl


def test_i13_orchestration_service_uses_injected_collaborators() -> None:
    """
    TS-I13-E2E-REAL-001:
    Decision orchestration provider must compose the service from injected
    collaborators rather than constructing them inline.
    """
    ingestion = AsyncMock()
    extraction = AsyncMock()
    retrieval = AsyncMock()
    coherence = AsyncMock()
    hitl = AsyncMock()

    service = get_decision_orchestration_service(
        ingestion_service=ingestion,
        extraction_service=extraction,
        retrieval_service=retrieval,
        coherence_scoring_service=coherence,
        hitl_service=hitl,
    )

    assert service.ingestion_service is ingestion
    assert service.extraction_service is extraction
    assert service.retrieval_service is retrieval
    assert service.coherence_scoring_service is coherence
    assert service.hitl_service is hitl
