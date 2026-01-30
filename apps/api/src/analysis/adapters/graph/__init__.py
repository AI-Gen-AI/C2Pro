"""
Analysis Graph Adapters

LangGraph workflow and knowledge graph services.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.graph.knowledge_graph import ProjectKnowledgeGraph, GraphPath
from src.analysis.adapters.persistence.alert_repository import SqlAlchemyAlertRepository
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository
from src.stakeholders.adapters.persistence.sqlalchemy_stakeholder_repository import (
    SqlAlchemyStakeholderRepository,
)

def build_project_knowledge_graph(session: AsyncSession) -> ProjectKnowledgeGraph:
    return ProjectKnowledgeGraph(
        stakeholder_repository=SqlAlchemyStakeholderRepository(session),
        wbs_repository=SQLAlchemyWBSRepository(session),
        alert_repository=SqlAlchemyAlertRepository(session),
        document_repository=SqlAlchemyDocumentRepository(session),
    )


__all__ = ["ProjectKnowledgeGraph", "GraphPath", "build_project_knowledge_graph"]
