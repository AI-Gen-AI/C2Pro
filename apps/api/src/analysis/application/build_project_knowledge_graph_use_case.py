from __future__ import annotations

from uuid import UUID

import networkx as nx

from src.analysis.ports.knowledge_graph import KnowledgeGraphPort


class BuildProjectKnowledgeGraphUseCase:
    def __init__(self, knowledge_graph: KnowledgeGraphPort) -> None:
        self.knowledge_graph = knowledge_graph

    async def execute(self, project_id: UUID, tenant_id: UUID) -> nx.DiGraph:
        return await self.knowledge_graph.build_graph(project_id, tenant_id)
