"""Real PostgreSQL regression for the trusted-document ProjectGraph materializer.

The materializer is a projection of an already TRUSTED artifact set; this test
does not grant trust to a document or permit model-generated WBS to become a
baseline. Runs in the disposable integration-test PostgreSQL database.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select, text

from src.analysis.adapters.persistence.models import (
    KnowledgeGraphEdgeORM,
    KnowledgeGraphNodeORM,
)
from src.analysis.adapters.persistence.trusted_artifact_graph_materializer import (
    KnowledgeGraphMaterialization,
    SqlAlchemyTrustedArtifactGraphMaterializer,
)
from src.analysis.domain.contracts import DocumentArtifact
from tests.integration.document_flow.test_contract_schedule_completion_flow import _project

pytestmark = pytest.mark.asyncio


async def test_real_pg_trusted_document_projection_idempotent_and_tenant_scoped(
    db,
    test_user,
) -> None:
    project_id = await _project(db, test_user.tenant_id)
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tenant, true)"),
        {"tenant": str(test_user.tenant_id)},
    )
    materializer = SqlAlchemyTrustedArtifactGraphMaterializer(db)
    document_id = uuid4()
    revision_one = uuid4()
    artifact_one = DocumentArtifact(
        document_id=str(document_id),
        document_revision_id=str(revision_one),
        doc_type="contract",
    )

    first = await materializer.materialize_trusted_artifacts(
        project_id=project_id,
        tenant_id=test_user.tenant_id,
        artifacts=[artifact_one],
    )
    second = await materializer.materialize_trusted_artifacts(
        project_id=project_id,
        tenant_id=test_user.tenant_id,
        artifacts=[artifact_one],
    )
    assert first == second == KnowledgeGraphMaterialization(node_count=2, edge_count=1)

    nodes = list(
        (
            await db.execute(
                select(KnowledgeGraphNodeORM).where(KnowledgeGraphNodeORM.project_id == project_id)
            )
        )
        .scalars()
        .all()
    )
    edges = list(
        (
            await db.execute(
                select(KnowledgeGraphEdgeORM).where(KnowledgeGraphEdgeORM.project_id == project_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(nodes) == 2, "Project and trusted document must not duplicate on retry"
    assert len(edges) == 1, "The project→document relationship must be idempotent"
    project_node = next(n for n in nodes if n.entity_type == "PROJECT")
    doc_node = next(n for n in nodes if n.entity_type == "TRUSTED_DOCUMENT")
    assert doc_node.entity_id == document_id
    assert doc_node.properties["document_revision_id"] == str(revision_one)
    assert doc_node.properties["evidence_state"] == "trusted_artifact_identity_only"
    assert edges[0].source_node_id == project_node.id
    assert edges[0].target_node_id == doc_node.id
    assert edges[0].relationship_type == "HAS_TRUSTED_DOCUMENT_ARTIFACT"

    # A trusted revision change must refresh the identity in place, not leave
    # a duplicate document node or increase the number of edges.
    revision_two = uuid4()
    await materializer.materialize_trusted_artifacts(
        project_id=project_id,
        tenant_id=test_user.tenant_id,
        artifacts=[
            DocumentArtifact(
                document_id=str(document_id),
                document_revision_id=str(revision_two),
                doc_type="contract",
            )
        ],
    )
    updated = (
        await db.execute(
            select(KnowledgeGraphNodeORM).where(
                KnowledgeGraphNodeORM.project_id == project_id,
                KnowledgeGraphNodeORM.entity_type == "TRUSTED_DOCUMENT",
            )
        )
    ).scalar_one()
    assert updated.id == doc_node.id
    # UPSERT is executed as SQL Core; ORM identity-map values require refresh.
    # The assertion must inspect PostgreSQL state, not the previous Python cache.
    await db.refresh(updated)
    assert updated.properties["document_revision_id"] == str(revision_two)
    assert (
        len(
            (
                await db.execute(
                    select(KnowledgeGraphEdgeORM).where(
                        KnowledgeGraphEdgeORM.project_id == project_id
                    )
                )
            )
            .scalars()
            .all()
        )
        == 1
    )

    # Authorized project identity must be checked in addition to RLS:
    # a foreign tenant cannot create any canonical graph relation here.
    with pytest.raises(PermissionError, match="project is not available"):
        await materializer.materialize_trusted_artifacts(
            project_id=project_id,
            tenant_id=uuid4(),
            artifacts=[artifact_one],
        )
    assert (
        await db.scalar(
            text("SELECT count(*) FROM knowledge_graph_nodes WHERE project_id=:pid"),
            {"pid": project_id},
        )
    ) == 2
    assert (
        await db.scalar(
            text("SELECT count(*) FROM knowledge_graph_edges WHERE project_id=:pid"),
            {"pid": project_id},
        )
    ) == 1

    # ProjectGraph identity projection must not create risk alerts or claim
    # that Coherence was evaluated.
    assert (
        await db.scalar(
            text("SELECT count(*) FROM alerts WHERE project_id=:pid"), {"pid": project_id}
        )
    ) == 0
    assert (
        await db.scalar(
            text("SELECT count(*) FROM coherence_results WHERE project_id=:pid"),
            {"pid": project_id},
        )
    ) == 0
