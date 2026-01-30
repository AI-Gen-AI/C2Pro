from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

import networkx as nx


class KnowledgeGraphPort(ABC):
    @abstractmethod
    async def build_graph(self, project_id: UUID, tenant_id: UUID) -> nx.DiGraph:
        ...
