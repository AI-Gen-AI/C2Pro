from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.analysis.adapters.graph import build_project_knowledge_graph
from src.analysis.application.build_project_knowledge_graph_use_case import (
    BuildProjectKnowledgeGraphUseCase,
)
from src.analysis.ports.knowledge_graph import KnowledgeGraphPort


def get_knowledge_graph(
    db: AsyncSession = Depends(get_session),
) -> KnowledgeGraphPort:
    return build_project_knowledge_graph(db)


def get_build_graph_use_case(
    knowledge_graph: KnowledgeGraphPort = Depends(get_knowledge_graph),
) -> BuildProjectKnowledgeGraphUseCase:
    return BuildProjectKnowledgeGraphUseCase(knowledge_graph)
