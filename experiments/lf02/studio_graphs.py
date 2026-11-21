"""LF02: export the *actual* C2Pro LangGraph graphs to the Studio Agent Server.

No node functions, routing, prompts or graph edges are reimplemented here.
This must run with ENVIRONMENT=test, an isolated DB and no production credentials.
"""
from __future__ import annotations

from langchain_core.runnables import RunnableConfig


def full_c2pro(config: RunnableConfig | None = None):
    """Main source graph from apps/api; compiled without production checkpointer."""
    from src.analysis.adapters.graph.workflow import compile_workflow
    return compile_workflow(checkpointer=None, persist_diagram=False)


def project_graph(config: RunnableConfig | None = None):
    """Real ProjectGraph from apps/api, not a visual approximation."""
    from src.analysis.adapters.graph.project_graph import build_project_graph
    return build_project_graph()
