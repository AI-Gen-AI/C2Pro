"""Tests for report and decision package assembly domain services.

TASK-IMPL-010.4: Pure data transformation, no framework dependencies.
"""

from __future__ import annotations

from src.analysis.domain.report_assembly import (
    DecisionPackageAssemblyService,
    DecisionPackageInput,
    ReportAssemblyService,
    ReportInput,
)


class TestReportAssemblyService:
    def setup_method(self):
        self.service = ReportAssemblyService()

    def test_assembles_complete_report(self):
        inp = ReportInput(
            project_id="proj-1",
            document_id="doc-1",
            doc_type="contract",
            document_category="LEGAL",
            analysis_id="analysis-1",
            extracted_risks=[{"title": "R1"}, {"title": "R2"}],
            extracted_wbs=[{"code": "W1"}],
            extracted_stakeholders=[{"name": "Alice"}],
            bom_items=[{"name": "Steel"}],
            coherence_score=72,
            coherence_score_version="coherence-v1",
            confidence_score=0.88,
            citation_validation_passed=True,
            pii_redactions=[{"type": "EMAIL"}],
            raci_matrix=[{"stakeholder": "Alice", "role": "R"}],
            coherence_breakdown={"LEGAL": 80},
            citations=[{"quote": "clause 1"}],
            knowledge_graph_nodes=[{"id": "n1"}],
            knowledge_graph_edges=[{"source": "n1", "target": "n2"}],
            decision_package={"coherence_score": 72},
            human_approval_required=False,
            human_feedback="",
        )
        report = self.service.assemble(inp)

        assert report["summary"]["total_risks"] == 2
        assert report["summary"]["total_wbs_items"] == 1
        assert report["summary"]["total_stakeholders"] == 1
        assert report["summary"]["total_bom_items"] == 1
        assert report["summary"]["coherence_score"] == 72
        assert report["summary"]["coherence_score_version"] == "coherence-v1"
        assert report["summary"]["confidence_score"] == 0.88
        assert report["summary"]["pii_items_redacted"] == 1
        assert report["summary"]["citation_validation_passed"] is True
        assert report["project_id"] == "proj-1"
        assert report["doc_type"] == "contract"

    def test_handles_empty_state(self):
        inp = ReportInput(
            project_id="proj-1",
            document_id="doc-1",
            doc_type="",
            document_category="",
            analysis_id=None,
            extracted_risks=[],
            extracted_wbs=[],
            extracted_stakeholders=[],
            bom_items=[],
            coherence_score=0,
            coherence_score_version=None,
            confidence_score=0.0,
            citation_validation_passed=False,
            pii_redactions=[],
            raci_matrix=[],
            coherence_breakdown={},
            citations=[],
            knowledge_graph_nodes=[],
            knowledge_graph_edges=[],
            decision_package={},
            human_approval_required=False,
            human_feedback="",
        )
        report = self.service.assemble(inp)

        assert report["summary"]["total_risks"] == 0
        assert report["summary"]["total_wbs_items"] == 0
        assert report["project_id"] == "proj-1"

    def test_report_contains_all_sections(self):
        inp = ReportInput(
            project_id="p",
            document_id="d",
            doc_type="budget",
            document_category="BUDGET",
            analysis_id=None,
            extracted_risks=[],
            extracted_wbs=[],
            extracted_stakeholders=[],
            bom_items=[],
            coherence_score=0,
            coherence_score_version=None,
            confidence_score=0.0,
            citation_validation_passed=False,
            pii_redactions=[],
            raci_matrix=[],
            coherence_breakdown={},
            citations=[],
            knowledge_graph_nodes=[],
            knowledge_graph_edges=[],
            decision_package={},
            human_approval_required=False,
            human_feedback="",
        )
        report = self.service.assemble(inp)

        expected_keys = {
            "project_id", "document_id", "doc_type", "document_category",
            "analysis_id", "summary", "risks", "wbs_items", "stakeholders",
            "raci_matrix", "bom_items", "coherence_breakdown", "citations",
            "knowledge_graph", "decision_package", "human_approval_required",
            "human_feedback",
        }
        assert expected_keys.issubset(set(report.keys()))
        assert "nodes" in report["knowledge_graph"]
        assert "edges" in report["knowledge_graph"]


class TestDecisionPackageAssemblyService:
    def setup_method(self):
        self.service = DecisionPackageAssemblyService()

    def test_assembles_package(self):
        inp = DecisionPackageInput(
            coherence_score=85,
            coherence_score_version="coherence-v1",
            extracted_risks=[{"title": "Risk A"}],
            extracted_stakeholders=[{"name": "Alice"}],
            extracted_wbs=[{"code": "W1"}],
            bom_items=[{"name": "Steel"}],
            citations=[{"quote": "clause 1"}],
            citation_validation_passed=True,
            human_feedback="",
        )
        pkg = self.service.assemble(inp)

        assert pkg["coherence_score"] == 85
        assert pkg["coherence_score_version"] == "coherence-v1"
        assert len(pkg["risks"]) == 1
        assert len(pkg["stakeholders"]) == 1
        assert pkg["approved_by"] is None

    def test_marks_human_approval(self):
        inp = DecisionPackageInput(
            coherence_score=50,
            coherence_score_version="coherence-v1",
            extracted_risks=[],
            extracted_stakeholders=[],
            extracted_wbs=[],
            bom_items=[],
            citations=[],
            citation_validation_passed=False,
            human_feedback="Approved by PM",
        )
        pkg = self.service.assemble(inp)

        assert pkg["approved_by"] == "human_reviewer"

    def test_no_approval_without_feedback(self):
        inp = DecisionPackageInput(
            coherence_score=90,
            coherence_score_version="coherence-v1",
            extracted_risks=[],
            extracted_stakeholders=[],
            extracted_wbs=[],
            bom_items=[],
            citations=[],
            citation_validation_passed=True,
            human_feedback="",
        )
        pkg = self.service.assemble(inp)

        assert pkg["approved_by"] is None
        assert pkg["approved_at"] is None

    def test_citation_quotes_extracted(self):
        inp = DecisionPackageInput(
            coherence_score=75,
            coherence_score_version="coherence-v1",
            extracted_risks=[],
            extracted_stakeholders=[],
            extracted_wbs=[],
            bom_items=[],
            citations=[
                {"quote": "clause 1", "type": "risk"},
                {"quote": "clause 2", "type": "wbs"},
            ],
            citation_validation_passed=True,
            human_feedback="",
        )
        pkg = self.service.assemble(inp)

        assert pkg["citations"] == ["clause 1", "clause 2"]
