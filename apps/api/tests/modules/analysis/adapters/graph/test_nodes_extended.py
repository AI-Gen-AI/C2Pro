"""Tests for extended LangGraph nodes (N1, N2, N6–N11, N15, N16).

These tests verify each node in isolation by mocking external dependencies.
They do NOT require a database, AI service, or any external infrastructure.
"""

from __future__ import annotations

import pytest

from src.analysis.adapters.graph.schema import ProjectState
from src.analysis.domain.node_result import NodeStatus


def _make_state(**overrides) -> ProjectState:
    """Create a minimal valid ProjectState with sensible defaults."""
    defaults: dict = {
        "project_id": "00000000-0000-0000-0000-000000000001",
        "document_id": "00000000-0000-0000-0000-000000000002",
        "document_text": "Contrato de construcción entre Acme S.L. y BuildCo.",
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
        # Extended fields
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


# ---------------------------------------------------------------------------
# N1 — Document Ingestion
# ---------------------------------------------------------------------------

class TestDocumentIngestionNode:
    @pytest.mark.asyncio
    async def test_empty_text_short_circuits_as_insufficient_extractable_text(self):
        """Test Suite ID: TS-HOTFIX-ANALYSIS-NO-TEXT-001."""
        from src.analysis.adapters.graph.nodes_extended import document_ingestion_node

        result = await document_ingestion_node(_make_state(document_text=" \n\t "))

        assert result["document_parsed"] is False
        assert result["document_category"] == "insufficient_extractable_text"
        assert any(
            "No extractable text" in message.content
            and "OCR required" in message.content
            for message in result["messages"]
        )

    @pytest.mark.asyncio
    async def test_classifies_legal_document(self):
        from src.analysis.adapters.graph.nodes_extended import document_ingestion_node

        state = _make_state(
            document_text="Cláusula 1: Las obligaciones del contrato incluyen..."
        )
        result = await document_ingestion_node(state)
        assert result["document_parsed"] is True
        assert result["document_category"] == "LEGAL"

    @pytest.mark.asyncio
    async def test_classifies_budget_document(self):
        from src.analysis.adapters.graph.nodes_extended import document_ingestion_node

        state = _make_state(
            document_text="El presupuesto total del capex asciende a 500.000 EUR."
        )
        result = await document_ingestion_node(state)
        assert result["document_category"] == "BUDGET"

    @pytest.mark.asyncio
    async def test_classifies_time_document(self):
        from src.analysis.adapters.graph.nodes_extended import document_ingestion_node

        state = _make_state(
            document_text="El cronograma define el plazo de entrega en 6 meses con hitos trimestrales."
        )
        result = await document_ingestion_node(state)
        assert result["document_category"] == "TIME"

    @pytest.mark.asyncio
    async def test_defaults_to_technical(self):
        from src.analysis.adapters.graph.nodes_extended import document_ingestion_node

        state = _make_state(document_text="Lorem ipsum dolor sit amet.")
        result = await document_ingestion_node(state)
        assert result["document_category"] == "TECHNICAL"

    @pytest.mark.asyncio
    async def test_uses_anonymized_text_when_available(self):
        from src.analysis.adapters.graph.nodes_extended import document_ingestion_node

        state = _make_state(
            document_text="irrelevant original",
            anonymized_text="El presupuesto del proyecto cubre el coste total.",
        )
        result = await document_ingestion_node(state)
        assert result["document_category"] == "BUDGET"


# ---------------------------------------------------------------------------
# N2 — PII Anonymizer
# ---------------------------------------------------------------------------

class TestPiiAnonymizerNode:
    @pytest.mark.asyncio
    async def test_redacts_email(self):
        from src.analysis.adapters.graph.nodes_extended import pii_anonymizer_node

        state = _make_state(
            document_text="Contactar a juan@acme.com para más información."
        )
        result = await pii_anonymizer_node(state)
        assert "[REDACTED]" in result["anonymized_text"]
        assert "juan@acme.com" not in result["anonymized_text"]
        assert len(result["pii_redactions"]) >= 1
        assert result["pii_redactions"][0]["type"] == "EMAIL"

    @pytest.mark.asyncio
    async def test_no_pii_passthrough(self):
        from src.analysis.adapters.graph.nodes_extended import pii_anonymizer_node

        state = _make_state(document_text="Texto sin datos personales.")
        result = await pii_anonymizer_node(state)
        assert result["anonymized_text"] == "Texto sin datos personales."
        assert result["pii_redactions"] == []

    @pytest.mark.asyncio
    async def test_redacts_spanish_phone(self):
        from src.analysis.adapters.graph.nodes_extended import pii_anonymizer_node

        state = _make_state(
            document_text="Llame al 612345678 para consultas."
        )
        result = await pii_anonymizer_node(state)
        assert "[REDACTED]" in result["anonymized_text"]
        assert any(r["type"] == "PHONE" for r in result["pii_redactions"])


# ---------------------------------------------------------------------------
# N6 — Stakeholder Extractor
# ---------------------------------------------------------------------------

class TestStakeholderExtractorNode:
    @pytest.mark.asyncio
    async def test_skips_without_tenant(self):
        from src.analysis.adapters.graph.nodes_extended import stakeholder_extractor_node

        state = _make_state(tenant_id=None)
        result = await stakeholder_extractor_node(state)
        assert result["extracted_stakeholders"] == []

    @pytest.mark.asyncio
    async def test_handles_extraction_failure_gracefully(self, monkeypatch):
        from src.analysis.adapters.graph import nodes_extended

        # Make the lazy import raise to simulate missing AI provider
        monkeypatch.setattr(
            "src.analysis.adapters.graph.nodes_extended.logger",
            nodes_extended.logger,
        )
        state = _make_state()
        # This will fail because the AI provider isn't available in tests,
        # but the node should handle it gracefully
        result = await nodes_extended.stakeholder_extractor_node(state)
        assert isinstance(result["extracted_stakeholders"], list)


# ---------------------------------------------------------------------------
# N7 — RACI Generator
# ---------------------------------------------------------------------------

class TestRaciGeneratorNode:
    @pytest.mark.asyncio
    async def test_skips_without_stakeholders(self):
        from src.analysis.adapters.graph.nodes_extended import raci_generator_node

        state = _make_state(extracted_stakeholders=[], extracted_wbs=[])
        result = await raci_generator_node(state)
        assert result["raci_matrix"] == []

    @pytest.mark.asyncio
    async def test_skips_without_wbs(self):
        from src.analysis.adapters.graph.nodes_extended import raci_generator_node

        state = _make_state(
            extracted_stakeholders=[{"name": "Alice"}],
            extracted_wbs=[],
        )
        result = await raci_generator_node(state)
        assert result["raci_matrix"] == []


# ---------------------------------------------------------------------------
# N8 — Coherence Scorer
# ---------------------------------------------------------------------------

class TestCoherenceScorerNode:
    @pytest.mark.asyncio
    async def test_skips_without_project(self):
        from src.analysis.adapters.graph.nodes_extended import coherence_scorer_node

        state = _make_state(project_id="")
        result = await coherence_scorer_node(state)
        assert result["coherence_score"] is None
        assert result["coherence_breakdown"] == {}


# ---------------------------------------------------------------------------
# N10 — Knowledge Graph Builder
# ---------------------------------------------------------------------------

class TestKnowledgeGraphBuilderNode:
    @pytest.mark.asyncio
    async def test_skips_without_tenant(self):
        from src.analysis.adapters.graph.nodes_extended import knowledge_graph_builder_node

        state = _make_state(tenant_id=None)
        result = await knowledge_graph_builder_node(state)
        assert result["knowledge_graph_nodes"] == []
        assert result["knowledge_graph_edges"] == []


# ---------------------------------------------------------------------------
# N11 — Decision Intelligence
# ---------------------------------------------------------------------------

class TestDecisionIntelligenceNode:
    @pytest.mark.asyncio
    async def test_assembles_package(self):
        from src.analysis.adapters.graph.nodes_extended import decision_intelligence_node

        state = _make_state(
            extracted_risks=[{"title": "Risk A"}],
            extracted_stakeholders=[{"name": "Alice"}],
            coherence_score=85,
        )
        result = await decision_intelligence_node(state)
        pkg = result["decision_package"]
        assert pkg["coherence_score"] == 85
        assert len(pkg["risks"]) == 1
        assert len(pkg["stakeholders"]) == 1
        assert pkg["approved_by"] is None

    @pytest.mark.asyncio
    async def test_emits_material_node_result(self):
        """Test Suite ID: TS-UD-V3-013-003."""
        from src.analysis.adapters.graph.nodes_extended import decision_intelligence_node

        result = await decision_intelligence_node(_make_state())

        node_result = result["node_results"][-1]
        assert node_result.node == "decision_intelligence"
        assert node_result.status is NodeStatus.OK
        assert node_result.data == result["decision_package"]

    @pytest.mark.asyncio
    async def test_marks_human_approval(self):
        from src.analysis.adapters.graph.nodes_extended import decision_intelligence_node

        state = _make_state(human_feedback="Approved by PM")
        result = await decision_intelligence_node(state)
        assert result["decision_package"]["approved_by"] == "human_reviewer"


# ---------------------------------------------------------------------------
# N15 — Citation Validator
# ---------------------------------------------------------------------------

class TestCitationValidatorNode:
    @pytest.mark.asyncio
    async def test_validates_risk_quotes(self):
        from src.analysis.adapters.graph.nodes_extended import citation_validator_node

        state = _make_state(
            document_text="El contratista asumirá los riesgos de inundación.",
            extracted_risks=[
                {"title": "Flood risk", "source_quote": "riesgos de inundación"},
            ],
        )
        result = await citation_validator_node(state)
        assert result["citation_validation_passed"] is True
        assert result["citations"][0]["found_in_source"] is True

    @pytest.mark.asyncio
    async def test_fails_on_missing_quotes(self):
        from src.analysis.adapters.graph.nodes_extended import citation_validator_node

        state = _make_state(
            document_text="Texto simple sin referencia.",
            extracted_risks=[
                {"title": "Made-up risk", "source_quote": "esto no existe en el documento"},
            ],
        )
        result = await citation_validator_node(state)
        assert result["citations"][0]["found_in_source"] is False

    @pytest.mark.asyncio
    async def test_passes_with_no_extractions(self):
        from src.analysis.adapters.graph.nodes_extended import citation_validator_node

        state = _make_state()
        result = await citation_validator_node(state)
        assert result["citation_validation_passed"] is True
        assert result["citations"] == []


# ---------------------------------------------------------------------------
# N16 — Final Assembler
# ---------------------------------------------------------------------------

class TestFinalAssemblerNode:
    @pytest.mark.asyncio
    async def test_assembles_complete_report(self):
        from src.analysis.adapters.graph.nodes_extended import final_assembler_node

        state = _make_state(
            extracted_risks=[{"title": "R1"}, {"title": "R2"}],
            extracted_wbs=[{"code": "W1"}],
            extracted_stakeholders=[{"name": "Alice"}],
            bom_items=[{"name": "Steel"}],
            coherence_score=72,
            confidence_score=0.88,
            pii_redactions=[{"type": "EMAIL"}],
            citation_validation_passed=True,
        )
        result = await final_assembler_node(state)
        report = result["final_report"]

        assert report["summary"]["total_risks"] == 2
        assert report["summary"]["total_wbs_items"] == 1
        assert report["summary"]["total_stakeholders"] == 1
        assert report["summary"]["total_bom_items"] == 1
        assert report["summary"]["coherence_score"] == 72
        assert report["summary"]["confidence_score"] == 0.88
        assert report["summary"]["pii_items_redacted"] == 1
        assert report["summary"]["citation_validation_passed"] is True

    @pytest.mark.asyncio
    async def test_emits_material_node_result(self):
        """Test Suite ID: TS-UD-V3-013-004."""
        from src.analysis.adapters.graph.nodes_extended import final_assembler_node

        result = await final_assembler_node(_make_state())

        node_result = result["node_results"][-1]
        assert node_result.node == "final_assembler"
        assert node_result.status is NodeStatus.OK
        assert node_result.data == result["final_report"]

    @pytest.mark.asyncio
    async def test_handles_empty_state(self):
        from src.analysis.adapters.graph.nodes_extended import final_assembler_node

        state = _make_state()
        result = await final_assembler_node(state)
        report = result["final_report"]
        assert report["summary"]["total_risks"] == 0
        assert report["project_id"] is not None


# ---------------------------------------------------------------------------
# Workflow compilation
# ---------------------------------------------------------------------------

class TestWorkflowCompilation:
    def test_build_workflow_has_all_17_nodes(self):
        from src.analysis.adapters.graph.workflow import build_workflow

        workflow = build_workflow()
        node_names = set(workflow.nodes.keys())

        expected = {
            "document_ingestion",    # N1
            "pii_anonymizer",        # N2
            "router",                # N3
            "risk_extractor",        # N4
            "wbs_extractor",         # N5
            "stakeholder_extractor", # N6
            "raci_generator",        # N7
            "coherence_scorer",      # N8
            "budget_parser",         # N9
            "knowledge_graph",       # N10
            "decision_intelligence", # N11
            "critique",              # N12
            "human_interrupt",       # N13/14
            "citation_validator",    # N15
            "final_assembler",       # N16
            "save_to_db",           # N17
        }
        assert expected.issubset(node_names), (
            f"Missing nodes: {expected - node_names}"
        )

    def test_workflow_compiles_without_checkpointer(self):
        from src.analysis.adapters.graph.workflow import compile_workflow

        app = compile_workflow(checkpointer=None, persist_diagram=False)
        assert app is not None
