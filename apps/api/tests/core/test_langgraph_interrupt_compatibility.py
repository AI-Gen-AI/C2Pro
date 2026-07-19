"""Regression tests for LangGraph interrupt import compatibility.

Test Suite ID: TS-BCK-051-001
"""


def test_graph_nodes_import_with_installed_langgraph_release_candidate() -> None:
    """TS-BCK-051-001: graph nodes must import with langgraph 1.0.10rc1."""
    from langgraph.types import interrupt

    from src.analysis.adapters.graph import nodes

    assert nodes.interrupt is interrupt
