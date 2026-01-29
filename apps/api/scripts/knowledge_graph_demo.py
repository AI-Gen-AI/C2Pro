from __future__ import annotations

import argparse
import asyncio
from uuid import UUID

import networkx as nx

from src.core.database import close_db, get_session_with_tenant, init_db
from src.analysis.adapters.graph.knowledge_graph import ProjectKnowledgeGraph


async def _run(project_id: UUID, tenant_id: UUID, source: str, target: str) -> None:
    await init_db()
    async with get_session_with_tenant(tenant_id) as session:
        graph_service = ProjectKnowledgeGraph(session)
        await graph_service.build_graph(project_id)
        paths = graph_service.find_impact_chain(source, target, max_paths=3, cutoff=8)
        if not paths:
            print("No paths found.")
            return
        for idx, path in enumerate(paths, start=1):
            print(f"Path {idx}:")
            for node, edge in zip(path.nodes, path.edges + ["END"]):
                print(f"  {node} --[{edge}]-->")
            print("")
    await close_db()


def main() -> None:
    parser = argparse.ArgumentParser(description="Knowledge graph demo.")
    parser.add_argument("--project-id")
    parser.add_argument("--tenant-id")
    parser.add_argument("--source", help="Source node id, e.g. rsk_<uuid>")
    parser.add_argument("--target", help="Target node id, e.g. stk_<uuid>")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run with in-memory demo graph (no database required).",
    )
    args = parser.parse_args()

    if args.demo:
        graph = _demo_graph()
        graph_service = ProjectKnowledgeGraph(db_session=None)  # type: ignore[arg-type]
        graph_service.graph = graph
        source = args.source or "rsk_demo"
        target = args.target or "stk_demo"
        paths = graph_service.find_impact_chain(source, target, max_paths=3, cutoff=6)
        if not paths:
            print("No paths found.")
            return
        for idx, path in enumerate(paths, start=1):
            print(f"Path {idx}:")
            for node, edge in zip(path.nodes, path.edges + ["END"]):
                print(f"  {node} --[{edge}]-->")
            print("")
        return

    if not args.project_id or not args.tenant_id or not args.source or not args.target:
        raise SystemExit("project-id, tenant-id, source, and target are required without --demo.")

    asyncio.run(
        _run(
            project_id=UUID(args.project_id),
            tenant_id=UUID(args.tenant_id),
            source=args.source,
            target=args.target,
        )
    )


if __name__ == "__main__":
    main()


def _demo_graph() -> nx.DiGraph:
    graph = nx.DiGraph()
    graph.add_node("stk_demo", type="STAKEHOLDER", label="Director Financiero")
    graph.add_node("tsk_demo", type="TASK", label="Cimentacion")
    graph.add_node("rsk_demo", type="RISK", label="Penalizacion sin cap")
    graph.add_node("cl_demo", type="CLAUSE", label="Clausula 14.2")

    graph.add_edge("stk_demo", "tsk_demo", relation="MANAGES")
    graph.add_edge("rsk_demo", "tsk_demo", relation="IMPACTS")
    graph.add_edge("rsk_demo", "cl_demo", relation="DERIVED_FROM")
    return graph
