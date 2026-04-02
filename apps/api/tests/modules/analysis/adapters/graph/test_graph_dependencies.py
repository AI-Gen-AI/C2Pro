"""
Graph dependency wiring tests.

Refers to Suite ID: TS-ADP-GRAPH-DI-001.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.analysis.adapters.graph.schema import ProjectState


def _make_state(**overrides) -> ProjectState:
    defaults: dict = {
        "project_id": "00000000-0000-0000-0000-000000000001",
        "document_id": "00000000-0000-0000-0000-000000000002",
        "document_text": "Presupuesto base del proyecto.",
        "doc_type": "",
        "messages": [],
        "extracted_risks": [],
        "extracted_wbs": [],
        "confidence_score": 0.0,
        "critique_notes": "",
        "human_feedback": "",
        "retry_count": 0,
        "tenant_id": "00000000-0000-0000-0000-000000000099",
        "analysis_id": None,
        "human_approval_required": False,
        "document_parsed": False,
        "document_category": "",
        "anonymized_text": "",
        "pii_redactions": [],
        "extracted_stakeholders": [],
        "raci_matrix": [],
        "coherence_score": 0,
        "coherence_breakdown": {},
        "bom_items": [],
        "knowledge_graph_nodes": [],
        "knowledge_graph_edges": [],
        "decision_package": {},
        "citations": [],
        "citation_validation_passed": False,
        "final_report": {},
    }
    defaults.update(overrides)
    return defaults  # type: ignore[return-value]


class TestGraphDependencyProviders:
    @pytest.mark.asyncio
    async def test_doc_type_classification_uses_ai_provider(self, monkeypatch) -> None:
        from src.analysis.adapters.graph import nodes
        from src.analysis.adapters.ai import anthropic_client

        class ExplodingAIService:
            def __init__(self, *args, **kwargs) -> None:
                raise AssertionError("direct AIService construction is not allowed")

        class FakeAIService:
            async def run_extraction(self, system_prompt: str, user_content: str):
                return {"doc_type": "budget"}

        monkeypatch.setattr(
            anthropic_client,
            "AIService",
            ExplodingAIService,
        )
        monkeypatch.setattr(
            nodes,
            "get_ai_service",
            lambda tenant_id: FakeAIService(),
            raising=False,
        )

        result = await nodes._classify_doc_type("Presupuesto y capex total", "tenant")

        assert result == "budget"

    @pytest.mark.asyncio
    async def test_pii_anonymizer_uses_dependency_providers(self, monkeypatch) -> None:
        from src.analysis.adapters.graph import nodes_extended
        from src.anonymizer.application import anonymization_service
        from src.anonymizer.domain import pii_detector_service

        class ExplodingDetector:
            def __init__(self, *args, **kwargs) -> None:
                raise AssertionError("direct detector construction is not allowed")

        class ExplodingAnonymizer:
            def __init__(self, *args, **kwargs) -> None:
                raise AssertionError("direct anonymizer construction is not allowed")

        class FakeDetector:
            async def detect(self, text: str):
                return SimpleNamespace(
                    items=[
                        SimpleNamespace(
                            text="juan@acme.com",
                            pii_type=SimpleNamespace(name="EMAIL"),
                            start=12,
                            end=25,
                        )
                    ]
                )

        class FakeAnonymizer:
            async def anonymize(self, text: str, config) -> str:
                _ = config
                return text.replace("juan@acme.com", "[REDACTED]")

        monkeypatch.setattr(pii_detector_service, "PiiDetectorService", ExplodingDetector)
        monkeypatch.setattr(anonymization_service, "AnonymizationService", ExplodingAnonymizer)
        monkeypatch.setattr(
            nodes_extended,
            "get_pii_detector_service",
            lambda: FakeDetector(),
            raising=False,
        )
        monkeypatch.setattr(
            nodes_extended,
            "get_anonymization_service",
            lambda detector: FakeAnonymizer(),
            raising=False,
        )

        result = await nodes_extended.pii_anonymizer_node(
            _make_state(document_text="Contactar a juan@acme.com")
        )

        assert result["anonymized_text"] == "Contactar a [REDACTED]"
        assert result["pii_redactions"][0]["type"] == "EMAIL"

    @pytest.mark.asyncio
    async def test_coherence_scorer_uses_dependency_provider(self, monkeypatch) -> None:
        from src.analysis.adapters.graph import nodes_extended
        from src.coherence.application.services import coherence_calculation_service
        from src.coherence.domain.category_weights import CoherenceCategory

        class ExplodingService:
            def __init__(self, *args, **kwargs) -> None:
                raise AssertionError("direct coherence service construction is not allowed")

        class FakeService:
            def calculate_coherence(self, **kwargs):
                return SimpleNamespace(
                    global_score=88,
                    category_scores={category: 88 for category in CoherenceCategory},
                )

        monkeypatch.setattr(
            coherence_calculation_service,
            "CoherenceCalculationService",
            ExplodingService,
        )
        monkeypatch.setattr(
            nodes_extended,
            "build_coherence_calculation_service",
            lambda event_publisher=None: FakeService(),
            raising=False,
        )

        result = await nodes_extended.coherence_scorer_node(
            _make_state(extracted_wbs=[{"code": "1.1", "confidence": 0.9}])
        )

        assert result["coherence_score"] == 88
        assert result["coherence_breakdown"]["SCOPE"] == 88

    @pytest.mark.asyncio
    async def test_human_interrupt_uses_hitl_provider(self, monkeypatch) -> None:
        from src.analysis.adapters.graph import nodes
        from src.modules.hitl.application import ports

        routed: dict[str, object] = {}

        class ExplodingService:
            def __init__(self, *args, **kwargs) -> None:
                raise AssertionError("direct HITL service construction is not allowed")

        class FakeHitlService:
            async def route_for_review(self, **kwargs):
                routed.update(kwargs)
                return None

        class FakeSessionContext:
            async def __aenter__(self):
                return object()

            async def __aexit__(self, exc_type, exc, tb):
                return False

        monkeypatch.setattr(ports, "HumanInTheLoopService", ExplodingService)
        monkeypatch.setattr(
            nodes,
            "get_session_with_tenant",
            lambda tenant_id: FakeSessionContext(),
            raising=False,
        )
        monkeypatch.setattr(
            nodes,
            "get_hitl_service_for_graph",
            lambda session, tenant_id: FakeHitlService(),
            raising=False,
        )
        monkeypatch.setattr(
            nodes,
            "interrupt",
            lambda payload: payload,
            raising=False,
        )

        state = _make_state(
            doc_type="contract",
            confidence_score=0.3,
            critique_notes="Needs review",
        )
        result = await nodes.human_interrupt_node(state)

        assert routed["item_type"] == "contract"
        assert result["human_approval_required"] is True
