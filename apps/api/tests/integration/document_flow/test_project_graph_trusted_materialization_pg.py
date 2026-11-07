"""Real isolated PostgreSQL proof for trusted KG identity upsert (no live tenant)."""

from uuid import uuid4

import pytest
from sqlalchemy import func, select, text

from src.analysis.adapters.persistence.models import KnowledgeGraphEdgeORM, KnowledgeGraphNodeORM
from src.analysis.adapters.persistence.trusted_artifact_graph_materializer import (
    SqlAlchemyTrustedArtifactGraphMaterializer,
)
from src.analysis.domain.contracts import DocumentArtifact
from tests.integration.document_flow.test_contract_schedule_completion_flow import _project


@pytest.mark.asyncio
async def test_trusted_kg_identity_upsert_is_persisted_and_idempotent(db, test_user):
    project_id = await _project(db, test_user.tenant_id)
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": str(test_user.tenant_id)},
    )
    revision_id = str(uuid4())
    artifact = DocumentArtifact(
        document_id=str(uuid4()),
        document_revision_id=revision_id,
        doc_type="contract",
    )
    materializer = SqlAlchemyTrustedArtifactGraphMaterializer(db)

    first = await materializer.materialize_trusted_artifacts(
        project_id=project_id,
        tenant_id=test_user.tenant_id,
        artifacts=[artifact],
    )
    second = await materializer.materialize_trusted_artifacts(
        project_id=project_id,
        tenant_id=test_user.tenant_id,
        artifacts=[artifact],
    )
    await db.flush()
    nodes = (await db.execute(
        select(KnowledgeGraphNodeORM).where(KnowledgeGraphNodeORM.project_id == project_id)
    )).scalars().all()
    edges = (await db.execute(
        select(KnowledgeGraphEdgeORM).where(KnowledgeGraphEdgeORM.project_id == project_id)
    )).scalars().all()

    assert (first.node_count, first.edge_count) == (2, 1)
    assert (second.node_count, second.edge_count) == (2, 1)
    assert len(nodes) == 2
    assert len(edges) == 1
    assert {node.entity_type for node in nodes} == {"PROJECT", "TRUSTED_DOCUMENT"}
    assert edges[0].properties["document_revision_id"] == revision_id

    with pytest.raises(PermissionError, match="tenant"):
        await materializer.materialize_trusted_artifacts(
            project_id=project_id,
            tenant_id=uuid4(),
            artifacts=[artifact],
        )
