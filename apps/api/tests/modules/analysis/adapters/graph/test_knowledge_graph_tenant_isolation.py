"""Tenant-isolation tests for the project graph adapter.

Test Suite: TS-UAD-PER-GRP-001
Backlog: TASK-BCK-095
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.analysis.adapters.graph.knowledge_graph import ProjectKnowledgeGraph


def _graph() -> tuple[
    ProjectKnowledgeGraph,
    MagicMock,
    MagicMock,
    MagicMock,
    MagicMock,
]:
    stakeholder_repository = MagicMock()
    stakeholder_repository.get_stakeholders_by_project = AsyncMock(return_value=([], 0))
    stakeholder_repository.list_raci_assignments = AsyncMock(return_value=[])

    wbs_repository = MagicMock()
    wbs_repository.get_by_project = AsyncMock(return_value=[])

    alert_repository = MagicMock()
    alert_repository.list_for_project = AsyncMock(
        return_value=SimpleNamespace(items=[])
    )

    document_repository = MagicMock()
    document_repository.get_clauses_by_ids = AsyncMock(return_value=[])

    graph = ProjectKnowledgeGraph(
        stakeholder_repository=stakeholder_repository,
        wbs_repository=wbs_repository,
        alert_repository=alert_repository,
        document_repository=document_repository,
    )
    return (
        graph,
        stakeholder_repository,
        wbs_repository,
        alert_repository,
        document_repository,
    )


@pytest.mark.asyncio
async def test_build_graph_propagates_authenticated_tenant_to_all_project_reads() -> None:
    """TS-UAD-PER-GRP-001: every project read receives the authenticated tenant."""
    (
        graph,
        stakeholder_repository,
        wbs_repository,
        alert_repository,
        document_repository,
    ) = _graph()
    project_id = uuid4()
    tenant_id = uuid4()
    clause_id = uuid4()
    wbs_repository.get_by_project.return_value = [
        SimpleNamespace(
            id=uuid4(),
            code="1.1",
            parent_code=None,
            name="Tenant-scoped task",
            source_clause_id=clause_id,
        )
    ]

    result = await graph.build_graph(project_id, tenant_id)

    assert len(result) == 1
    stakeholder_repository.get_stakeholders_by_project.assert_awaited_once_with(
        project_id=project_id,
        tenant_id=tenant_id,
        skip=0,
        limit=1000,
    )
    wbs_repository.get_by_project.assert_awaited_once_with(project_id, tenant_id)
    alert_repository.list_for_project.assert_awaited_once_with(
        project_id=project_id,
        tenant_id=tenant_id,
        category="risk",
        limit=500,
    )
    document_repository.get_clauses_by_ids.assert_awaited_once_with(
        tenant_id, [clause_id]
    )
    stakeholder_repository.list_raci_assignments.assert_awaited_once_with(
        project_id, tenant_id
    )
