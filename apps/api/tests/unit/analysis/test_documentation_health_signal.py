"""TS-ADR-013-GRAPH-001 - Documentation-health signal aggregation for ADR-018."""

from __future__ import annotations

from src.analysis.domain.node_result import NodeResult, NodeStatus


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
