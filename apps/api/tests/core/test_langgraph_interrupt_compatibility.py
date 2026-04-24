"""Regression tests for LangGraph interrupt import compatibility.

Test Suite ID: TS-BCK-051-001
"""


def test_graph_nodes_import_with_installed_langgraph_release_candidate() -> None:
    """TS-BCK-051-001: graph nodes must import with langgraph 1.0.10rc1."""
    from src.analysis.adapters.graph import nodes

    result = nodes.interrupt({"reason": "compatibility_check"})

    assert getattr(result, "value", None) == {"reason": "compatibility_check"}
