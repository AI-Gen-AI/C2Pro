"""TS-ADR-013-GRAPH-001 - Documentation-health signal aggregation for ADR-018."""

from __future__ import annotations

import pytest

from src.analysis.domain.node_result import ErrorRecord, NodeResult, NodeStatus


def test_documentation_health_signal_counts_failed_and_degraded_nodes() -> None:
    """TS-ADR-013-GRAPH-001 - NodeResult counts become a typed graph-state signal."""
    from src.analysis.domain.documentation_health import build_documentation_health_signal

    signal = build_documentation_health_signal(
        [
            NodeResult(node="n4", status=NodeStatus.OK),
            NodeResult(
                node="n13",
                status=NodeStatus.DEGRADED,
                degradation_reason="hitl_routing_failed",
            ),
            NodeResult(node="n6", status=NodeStatus.SKIPPED, degradation_reason="missing_tenant_id"),
        ]
    )

    assert signal.total_count == 3
    assert signal.failed_count == 0
    assert signal.degraded_count == 1
    assert signal.skipped_count == 1
    assert signal.degraded_nodes == ["n13"]
    assert signal.skipped_nodes == ["n6"]


def test_graph_node_update_includes_documentation_health_signal() -> None:
    """TS-ADR-013-GRAPH-001 - Graph node deltas carry the ADR-018 health input."""
    from src.analysis.adapters.graph.nodes_extended import _node_update_with_health

    result = NodeResult(node="n13", status=NodeStatus.DEGRADED, degradation_reason="x")

    update = _node_update_with_health({"node_results": [result]}, existing_results=[])

    signal = update["documentation_health_signal"]
    assert signal.degraded_count == 1
    assert signal.failed_count == 0


def test_document_artifact_preserves_documentation_health_signal() -> None:
    """TS-ADR-013-GRAPH-001 - Tier-1 artifact carries runtime trust into Tier-2."""
    from src.analysis.adapters.graph.document_artifact_builder import build_document_artifact

    node_result = NodeResult(
        node="citation_validator",
        status=NodeStatus.FAILED,
        error=ErrorRecord(
            node="citation_validator",
            error_type="RuntimeError",
            message="citation failed",
        ),
    )

    artifact = build_document_artifact(
        {
            "document_id": "document-1",
            "doc_type": "contract",
            "documentation_health_signal": {
                "total_count": 1,
                "failed_count": 1,
                "degraded_count": 0,
                "skipped_count": 0,
                "failed_nodes": [node_result.node],
                "degraded_nodes": [],
                "skipped_nodes": [],
            },
        }
    )

    assert artifact.documentation_health_signal is not None
    assert artifact.documentation_health_signal.failed_count == 1
    assert artifact.documentation_health_signal.failed_nodes == ["citation_validator"]


@pytest.mark.asyncio
async def test_final_assembler_populates_documentation_health_signal_from_accumulated_node_results() -> None:
    """TS-ADR-013-GRAPH-001 - N16 publishes ADR-018 documentation health after fan-in."""
    from src.analysis.adapters.graph.nodes_extended import final_assembler_node

    state = {
        "project_id": "project-1",
        "document_id": "document-1",
        "doc_type": "contract",
        "document_category": "LEGAL",
        "analysis_id": "analysis-1",
        "extracted_risks": [],
        "extracted_wbs": [],
        "extracted_stakeholders": [],
        "bom_items": [],
        "coherence_score": None,
        "confidence_score": 0.9,
        "citation_validation_passed": False,
        "pii_redactions": [],
        "raci_matrix": [],
        "coherence_breakdown": {},
        "citations": [],
        "knowledge_graph_nodes": [],
        "knowledge_graph_edges": [],
        "decision_package": {},
        "human_approval_required": False,
        "human_feedback": "",
        "messages": [],
        "node_results": [
            NodeResult(
                node="coherence_scorer",
                status=NodeStatus.FAILED,
                error=ErrorRecord(
                    node="coherence_scorer",
                    error_type="RuntimeError",
                    message="coherence failed",
                    traceback_digest="abc123",
                ),
            ),
            NodeResult(
                node="human_interrupt",
                status=NodeStatus.DEGRADED,
                degradation_reason="hitl_routing_failed",
            ),
        ],
    }

    result = await final_assembler_node(state)  # type: ignore[arg-type]

    signal = result["documentation_health_signal"]
    assert signal.failed_count == 1
    assert signal.degraded_count == 1
    assert signal.failed_nodes == ["coherence_scorer"]
    assert signal.degraded_nodes == ["human_interrupt"]
