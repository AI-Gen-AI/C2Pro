"""
Analysis Graph Adapters

LangGraph workflow and knowledge graph services.

Uses lazy imports (PEP 562) so that importing submodules like
``schema.py`` (pure types) doesn't pull in SQLAlchemy, persistence
adapters, or the full database stack.
"""

from __future__ import annotations

import importlib
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from src.analysis.adapters.graph.knowledge_graph import ProjectKnowledgeGraph, GraphPath

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "ProjectKnowledgeGraph":        ("src.analysis.adapters.graph.knowledge_graph", "ProjectKnowledgeGraph"),
    "GraphPath":                    ("src.analysis.adapters.graph.knowledge_graph", "GraphPath"),
}

__all__ = ["ProjectKnowledgeGraph", "GraphPath", "build_project_knowledge_graph"]


def build_project_knowledge_graph(session: AsyncSession) -> ProjectKnowledgeGraph:
    from src.analysis.adapters.graph.knowledge_graph import ProjectKnowledgeGraph as _PKG
    from src.analysis.adapters.persistence.alert_repository import SqlAlchemyAlertRepository
    from src.documents.adapters.persistence.sqlalchemy_document_repository import (
        SqlAlchemyDocumentRepository,
    )
    from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository
    from src.stakeholders.adapters.persistence.sqlalchemy_stakeholder_repository import (
        SqlAlchemyStakeholderRepository,
    )

    return _PKG(
        stakeholder_repository=SqlAlchemyStakeholderRepository(session),
        wbs_repository=SQLAlchemyWBSRepository(session),
        alert_repository=SqlAlchemyAlertRepository(session),
        document_repository=SqlAlchemyDocumentRepository(session),
    )


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        module_path, attr = _LAZY_IMPORTS[name]
        mod = importlib.import_module(module_path)
        value = getattr(mod, attr)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'src.analysis.adapters.graph' has no attribute {name!r}")
